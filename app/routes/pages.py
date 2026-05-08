"""Page routes — serves HTML pages via Jinja2 templates.

These routes render server-side HTML using Jinja2 and pass
context variables (itinerary data, Maps API key, coordinates)
to the templates for interactive client-side features.
"""

import json
import os
import re
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.templating import Jinja2Templates

from app.config import settings
from app.services.firestore import FirestoreService
from app.services.google_maps import GoogleMapsService

_PLAN_ID_PATTERN = re.compile(r"^[a-zA-Z0-9\-]{1,64}$")

router = APIRouter()
templates = Jinja2Templates(
    directory=os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
)
storage = FirestoreService()
maps_service = GoogleMapsService()


@router.get("/")
async def home(request: Request) -> Any:
    """Render the landing page with trip preference form.

    Args:
        request: The incoming HTTP request.

    Returns:
        Rendered ``index.html`` template.
    """
    return templates.TemplateResponse("index.html", {"request": request})


@router.get("/plan/{plan_id}")
async def itinerary_page(request: Request, plan_id: str) -> Any:
    """Render the full itinerary page with map, budget, and chat.

    Args:
        request: The incoming HTTP request.
        plan_id: UUID of the itinerary to display.

    Returns:
        Rendered ``itinerary.html`` template with itinerary context.

    Raises:
        HTTPException: 404 if itinerary not found.
    """
    if not _PLAN_ID_PATTERN.match(plan_id):
        raise HTTPException(400, "Invalid plan ID format")

    itinerary = await storage.get_itinerary(plan_id)
    if not itinerary:
        raise HTTPException(404, "Itinerary not found")

    # Pre-serialize days to JSON for the template
    # (Pydantic models aren't JSON-serializable by Jinja2 default filters)
    itinerary_days_json = json.dumps(
        [day.model_dump(mode="json") for day in itinerary.days]
    )

    # Geocode destination for map fallback centre
    dest_coords = await maps_service.geocode(itinerary.destination)
    dest_lat = dest_coords.get("latitude", 0)
    dest_lng = dest_coords.get("longitude", 0)

    return templates.TemplateResponse(
        "itinerary.html",
        {
            "request": request,
            "itinerary": itinerary,
            "itinerary_days_json": itinerary_days_json,
            "plan_id": plan_id,
            "maps_api_key": settings.google_maps_api_key,
            "dest_lat": dest_lat,
            "dest_lng": dest_lng,
        },
    )
