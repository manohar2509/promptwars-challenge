"""Page routes — serves HTML pages via Jinja2 templates."""
import json
import os
from fastapi import APIRouter, Request, HTTPException
from fastapi.templating import Jinja2Templates

from app.config import settings
from app.services.firestore import FirestoreService

router = APIRouter()
templates = Jinja2Templates(
    directory=os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
)
storage = FirestoreService()


@router.get("/")
async def home(request: Request):
    """Render the landing page with trip preference form."""
    return templates.TemplateResponse("index.html", {"request": request})


@router.get("/plan/{plan_id}")
async def itinerary_page(request: Request, plan_id: str):
    """Render the full itinerary page."""
    itinerary = await storage.get_itinerary(plan_id)
    if not itinerary:
        raise HTTPException(404, "Itinerary not found")

    # Pre-serialize days to JSON for the template (Pydantic models aren't JSON-serializable by default)
    itinerary_days_json = json.dumps(
        [day.model_dump(mode="json") for day in itinerary.days]
    )

    return templates.TemplateResponse(
        "itinerary.html",
        {
            "request": request,
            "itinerary": itinerary,
            "itinerary_days_json": itinerary_days_json,
            "plan_id": plan_id,
            "maps_api_key": settings.google_maps_api_key,
        },
    )
