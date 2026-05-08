"""API routes for travel planning engine."""
import logging
import os
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from fastapi.templating import Jinja2Templates

from app.models.preferences import TravelPreferences
from app.services.planner import PlannerService
from app.services.google_maps import GoogleMapsService
from app.services.weather import WeatherService
from app.services.constraints import ConstraintService
from app.services.firestore import FirestoreService
from app.services.google_calendar import CalendarService

logger = logging.getLogger(__name__)

router = APIRouter()
templates = Jinja2Templates(
    directory=os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
)

# Service instances
planner = PlannerService()
maps = GoogleMapsService()
weather = WeatherService()
constraints = ConstraintService()
storage = FirestoreService()
calendar = CalendarService()


@router.post("/plan")
async def create_plan(request: Request, preferences: TravelPreferences):
    """Generate a new travel itinerary from preferences."""
    # 1. Geocode destination
    location = await maps.geocode(preferences.destination)
    if not location:
        if request.headers.get("HX-Request"):
            return templates.TemplateResponse(
                "partials/alert_banner.html",
                {"request": request, "message": f"Could not find destination: {preferences.destination}", "level": "error"},
                status_code=400,
            )
        raise HTTPException(400, f"Could not find destination: {preferences.destination}")

    # 2. Search places matching interests
    places = []
    for interest in preferences.interests:
        results = await maps.search_places(
            f"{interest.value} in {preferences.destination}", location
        )
        places.extend(results)

    # 3. Get weather forecast
    forecast = await weather.get_forecast(
        location["latitude"],
        location["longitude"],
        preferences.start_date,
        preferences.end_date,
    )

    # 4. Generate itinerary via Gemini
    itinerary = await planner.generate_itinerary(preferences, places, forecast)

    # 5. Validate constraints
    result = await constraints.validate_itinerary(itinerary)
    if not result.valid:
        try:
            itinerary = await constraints.rebalance_budget(itinerary)
        except Exception as e:
            logger.warning("Budget rebalance failed: %s", e)

    # 6. Save to storage
    await storage.save_itinerary(itinerary)
    logger.info("Created itinerary %s for %s", itinerary.id, preferences.destination)

    # 7. Return redirect for HTMX or JSON for API
    if request.headers.get("HX-Request"):
        return Response(
            status_code=204,
            headers={"HX-Redirect": f"/plan/{itinerary.id}"},
        )
    return itinerary.model_dump(mode="json")


@router.get("/plan/{plan_id}")
async def get_plan(plan_id: str):
    """Retrieve an existing itinerary as JSON."""
    itinerary = await storage.get_itinerary(plan_id)
    if not itinerary:
        raise HTTPException(404, "Itinerary not found")
    return itinerary.model_dump(mode="json")


@router.get("/plan/{plan_id}/day/{day_num}")
async def get_day(request: Request, plan_id: str, day_num: int):
    """Return a single day's HTML partial for HTMX tab switching."""
    itinerary = await storage.get_itinerary(plan_id)
    if not itinerary:
        raise HTTPException(404, "Itinerary not found")

    day = next((d for d in itinerary.days if d.day_number == day_num), None)
    if not day:
        raise HTTPException(404, "Day not found")

    return templates.TemplateResponse(
        "partials/day_view.html",
        {"request": request, "day": day, "plan_id": plan_id, "itinerary": itinerary},
    )


@router.post("/plan/{plan_id}/refine")
async def refine_plan(request: Request, plan_id: str):
    """Refine itinerary with natural language instruction."""
    itinerary = await storage.get_itinerary(plan_id)
    if not itinerary:
        raise HTTPException(404, "Itinerary not found")

    body = await request.form()
    message = body.get("text", "").strip()
    if not message:
        try:
            json_body = await request.json()
            message = json_body.get("text", "").strip()
        except Exception:
            pass
    if not message:
        raise HTTPException(400, "Message text is required")
    if len(message) > 1000:
        raise HTTPException(400, "Message too long (max 1000 characters)")

    updated = await planner.refine_itinerary(itinerary, message)
    await storage.update_itinerary(updated)

    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(
            "partials/itinerary_full.html",
            {"request": request, "itinerary": updated, "plan_id": updated.id},
        )
    return updated.model_dump(mode="json")


@router.post("/plan/{plan_id}/disrupt")
async def disrupt_slot(request: Request, plan_id: str):
    """Mark a slot as disrupted and get AI-generated replacement."""
    itinerary = await storage.get_itinerary(plan_id)
    if not itinerary:
        raise HTTPException(404, "Itinerary not found")

    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        body = await request.json()
    else:
        form = await request.form()
        body = dict(form)
    day_num = body.get("day")
    slot_name = body.get("slot")
    reason = body.get("reason", "unavailable")

    if not day_num or not slot_name:
        raise HTTPException(400, "day and slot are required")

    updated = await planner.refine_itinerary(
        itinerary,
        f"The {slot_name} activity on day {day_num} is {reason}. "
        f"Replace it with a suitable alternative keeping the same budget range.",
    )
    await storage.update_itinerary(updated)

    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(
            "partials/itinerary_full.html",
            {"request": request, "itinerary": updated, "plan_id": updated.id},
        )
    return updated.model_dump(mode="json")


@router.get("/plan/{plan_id}/export")
async def export_calendar(plan_id: str):
    """Export itinerary as .ics calendar file."""
    itinerary = await storage.get_itinerary(plan_id)
    if not itinerary:
        raise HTTPException(404, "Itinerary not found")

    ics_content = calendar.generate_ics(itinerary)
    return Response(
        content=ics_content,
        media_type="text/calendar",
        headers={
            "Content-Disposition": f"attachment; filename=trip-{plan_id[:8]}.ics"
        },
    )
