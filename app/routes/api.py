"""API routes for the TravelAI planning engine.

Provides JSON REST endpoints for plan CRUD, natural-language refinement,
disruption handling, and iCalendar export. All endpoints include input
validation, error handling, and support for both JSON and HTMX clients.
"""

import asyncio
import logging
import os
import re
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from fastapi.templating import Jinja2Templates

from app.models.preferences import TravelPreferences
from app.services.constraints import ConstraintService
from app.services.firestore import FirestoreService
from app.services.google_calendar import CalendarService
from app.services.google_maps import GoogleMapsService
from app.services.planner import PlannerService
from app.services.weather import WeatherService

logger = logging.getLogger(__name__)

router = APIRouter()
templates = Jinja2Templates(
    directory=os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
)

# Service instances (stateless — safe to share across requests).
planner = PlannerService()
maps = GoogleMapsService()
weather = WeatherService()
constraints = ConstraintService()
storage = FirestoreService()
calendar = CalendarService()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_MAX_REFINE_LENGTH = 1000
_MAX_PLACES_PER_INTEREST = 10
_PLAN_ID_PATTERN = re.compile(r"^[a-zA-Z0-9\-]{1,64}$")


def _validate_plan_id(plan_id: str) -> None:
    """Validate plan_id format to prevent injection attacks.

    Args:
        plan_id: The plan ID string to validate.

    Raises:
        HTTPException: 400 if the plan_id format is invalid.
    """
    if not _PLAN_ID_PATTERN.match(plan_id):
        raise HTTPException(400, "Invalid plan ID format")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/plan")
async def create_plan(request: Request, preferences: TravelPreferences) -> Any:
    """Generate a new travel itinerary from user preferences.

    Pipeline:
    1. Geocode the destination via Google Maps.
    2. Search Google Places for venues matching user interests (parallel).
    3. Fetch weather forecast from Open-Meteo.
    4. Generate itinerary via Google Gemini AI.
    5. Enrich activity slots with geocoded coordinates (parallel).
    6. Validate constraints (budget, schedule).
    7. Persist to Firestore / in-memory storage.
    8. Return JSON or HTMX redirect.

    Args:
        request: The incoming HTTP request (used for content negotiation).
        preferences: Validated user travel preferences.

    Returns:
        JSON itinerary dict, or an HTMX 204 redirect to the plan page.
    """
    # 1. Geocode destination
    location = await maps.geocode(preferences.destination)
    if not location:
        if request.headers.get("HX-Request"):
            return templates.TemplateResponse(
                "partials/alert_banner.html",
                {
                    "request": request,
                    "message": f"Could not find destination: {preferences.destination}",
                    "level": "error",
                },
                status_code=400,
            )
        raise HTTPException(400, f"Could not find destination: {preferences.destination}")

    # 2. Search places matching interests (parallel)
    place_tasks = [
        maps.search_places(
            f"{interest.value} in {preferences.destination}", location
        )
        for interest in preferences.interests
    ]
    place_results = await asyncio.gather(*place_tasks, return_exceptions=True)
    places: list[dict] = []
    for result in place_results:
        if isinstance(result, list):
            places.extend(result[:_MAX_PLACES_PER_INTEREST])

    # 3. Get weather forecast
    forecast = await weather.get_forecast(
        location["latitude"],
        location["longitude"],
        preferences.start_date,
        preferences.end_date,
    )

    # 4. Generate itinerary via Gemini
    itinerary = await planner.generate_itinerary(preferences, places, forecast)

    # 5. Enrich slots with geocoded locations (parallel)
    async def _enrich_slot(slot, dest: str) -> None:
        """Geocode a slot's activity name if location data is missing."""
        if not slot.location or not slot.location.get("lat"):
            geo = await maps.geocode(f"{slot.activity_name}, {dest}")
            if geo:
                slot.location = {
                    "lat": geo["latitude"],
                    "lng": geo["longitude"],
                    "address": slot.activity_name,
                }

    enrich_tasks = [
        _enrich_slot(slot, preferences.destination)
        for day in itinerary.days
        for slot in day.slots
    ]
    await asyncio.gather(*enrich_tasks, return_exceptions=True)

    # 6. Validate constraints
    result = await constraints.validate_itinerary(itinerary)
    if not result.valid:
        try:
            itinerary = await constraints.rebalance_budget(itinerary)
        except Exception as exc:
            logger.warning("Budget rebalance failed: %s", exc)

    # 7. Save to storage
    await storage.save_itinerary(itinerary)
    logger.info("Created itinerary %s for %s", itinerary.id, preferences.destination)

    # 8. Return redirect for HTMX or JSON for API
    if request.headers.get("HX-Request"):
        return Response(
            status_code=204,
            headers={"HX-Redirect": f"/plan/{itinerary.id}"},
        )
    return itinerary.model_dump(mode="json")


@router.get("/plan/{plan_id}")
async def get_plan(plan_id: str) -> dict:
    """Retrieve an existing itinerary as JSON.

    Args:
        plan_id: UUID of the itinerary.

    Returns:
        Full itinerary JSON.

    Raises:
        HTTPException: 404 if itinerary not found.
    """
    _validate_plan_id(plan_id)
    itinerary = await storage.get_itinerary(plan_id)
    if not itinerary:
        raise HTTPException(404, "Itinerary not found")
    return itinerary.model_dump(mode="json")


@router.get("/plan/{plan_id}/day/{day_num}")
async def get_day(request: Request, plan_id: str, day_num: int) -> Any:
    """Return a single day's HTML partial for HTMX tab switching.

    Args:
        request: HTTP request (used for template rendering).
        plan_id: UUID of the itinerary.
        day_num: 1-indexed day number.

    Returns:
        Jinja2 HTML partial response.

    Raises:
        HTTPException: 404 if itinerary or day not found.
    """
    _validate_plan_id(plan_id)
    if day_num < 1 or day_num > 30:
        raise HTTPException(400, "Invalid day number")

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
async def refine_plan(request: Request, plan_id: str) -> Any:
    """Refine an itinerary with a natural-language instruction.

    Accepts both ``application/x-www-form-urlencoded`` (HTMX forms)
    and ``application/json`` request bodies.

    Args:
        request: HTTP request containing the refinement message.
        plan_id: UUID of the itinerary.

    Returns:
        Updated itinerary (JSON or HTMX partial).

    Raises:
        HTTPException: 404 if not found, 400 if message is empty/too long.
    """
    _validate_plan_id(plan_id)
    itinerary = await storage.get_itinerary(plan_id)
    if not itinerary:
        raise HTTPException(404, "Itinerary not found")

    # Parse message from form or JSON body
    message = ""
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        try:
            json_body = await request.json()
            message = str(json_body.get("text", "")).strip()
        except Exception:  # noqa: BLE001
            logger.debug("Failed to parse JSON body for refine")
    else:
        try:
            body = await request.form()
            message = str(body.get("text", "")).strip()
        except Exception:  # noqa: BLE001
            logger.debug("Failed to parse form body for refine")

    # Fallback: try JSON if form parsing yielded nothing
    if not message:
        try:
            json_body = await request.json()
            message = str(json_body.get("text", "")).strip()
        except Exception:  # noqa: BLE001
            logger.debug("Failed to parse fallback JSON body")

    if not message:
        raise HTTPException(400, "Message text is required")
    if len(message) > _MAX_REFINE_LENGTH:
        raise HTTPException(400, f"Message too long (max {_MAX_REFINE_LENGTH} characters)")

    updated = await planner.refine_itinerary(itinerary, message)
    await storage.update_itinerary(updated)

    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(
            "partials/itinerary_full.html",
            {"request": request, "itinerary": updated, "plan_id": updated.id},
        )
    return updated.model_dump(mode="json")


@router.post("/plan/{plan_id}/disrupt")
async def disrupt_slot(request: Request, plan_id: str) -> Any:
    """Mark a slot as disrupted and get an AI-generated replacement.

    Args:
        request: HTTP request with ``day``, ``slot``, and optional ``reason``.
        plan_id: UUID of the itinerary.

    Returns:
        Updated itinerary with the disrupted slot replaced.

    Raises:
        HTTPException: 404 if not found, 400 if required fields missing.
    """
    _validate_plan_id(plan_id)
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
    reason = str(body.get("reason", "unavailable"))[:200]  # Limit reason length

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
async def export_calendar(plan_id: str) -> Response:
    """Export itinerary as a downloadable .ics calendar file.

    Args:
        plan_id: UUID of the itinerary.

    Returns:
        ``text/calendar`` response with Content-Disposition attachment header.

    Raises:
        HTTPException: 404 if itinerary not found.
    """
    _validate_plan_id(plan_id)
    itinerary = await storage.get_itinerary(plan_id)
    if not itinerary:
        raise HTTPException(404, "Itinerary not found")

    ics_content = calendar.generate_ics(itinerary)
    return Response(
        content=ics_content,
        media_type="text/calendar",
        headers={
            "Content-Disposition": f'attachment; filename="trip-{plan_id[:8]}.ics"',
        },
    )
