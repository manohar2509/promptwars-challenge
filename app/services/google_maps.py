"""Google Maps Platform service — Places, Distance Matrix, Geocoding."""
import httpx
import logging
from app.config import settings

logger = logging.getLogger(__name__)


class GoogleMapsService:
    """Client for Google Maps Platform APIs."""

    PLACES_URL = "https://places.googleapis.com/v1"
    DISTANCE_URL = "https://maps.googleapis.com/maps/api/distancematrix/json"
    GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"

    def __init__(self):
        self.api_key = settings.google_maps_api_key

    async def search_places(
        self, query: str, location: dict, radius: int = 5000
    ) -> list[dict]:
        """Search for places using Places (New) API text search."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self.PLACES_URL}/places:searchText",
                    headers={
                        "X-Goog-Api-Key": self.api_key,
                        "X-Goog-FieldMask": (
                            "places.displayName,places.id,places.rating,"
                            "places.priceLevel,places.formattedAddress,"
                            "places.location,places.photos,"
                            "places.regularOpeningHours,"
                            "places.accessibilityOptions"
                        ),
                    },
                    json={
                        "textQuery": query,
                        "locationBias": {
                            "circle": {
                                "center": location,
                                "radius": radius,
                            }
                        },
                    },
                )
                response.raise_for_status()
                return response.json().get("places", [])
        except httpx.HTTPError as e:
            logger.warning("Places API error: %s", e)
            return []

    async def get_distance_matrix(
        self, origins: list[str], destinations: list[str]
    ) -> dict:
        """Get travel time and distance between location pairs."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    self.DISTANCE_URL,
                    params={
                        "origins": "|".join(origins),
                        "destinations": "|".join(destinations),
                        "key": self.api_key,
                        "mode": "transit",
                    },
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as e:
            logger.warning("Distance Matrix API error: %s", e)
            return {"rows": [], "status": "ERROR"}

    async def geocode(self, address: str) -> dict:
        """Geocode an address to latitude/longitude coordinates."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    self.GEOCODE_URL,
                    params={"address": address, "key": self.api_key},
                )
                response.raise_for_status()
                results = response.json().get("results", [])
                if results:
                    loc = results[0]["geometry"]["location"]
                    return {"latitude": loc["lat"], "longitude": loc["lng"]}
                return {}
        except httpx.HTTPError as e:
            logger.warning("Geocode API error: %s", e)
            return {}
