"""Google Maps Platform service — Places, Distance Matrix, Geocoding.

Uses ``httpx.AsyncClient`` with connection pooling for efficient
reuse across requests. All API errors are caught and logged without
propagating to callers — services return empty results on failure
so the planner can continue gracefully.
"""

import logging
from typing import Any, ClassVar

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# Shared timeout and connection configuration.
_TIMEOUT = httpx.Timeout(10.0, connect=5.0)
_LIMITS = httpx.Limits(max_connections=20, max_keepalive_connections=5)


class GoogleMapsService:
    """Client for Google Maps Platform APIs.

    Attributes:
        PLACES_URL: Base URL for the Places (New) API.
        DISTANCE_URL: Base URL for the Distance Matrix API.
        GEOCODE_URL: Base URL for the Geocoding API.
    """

    PLACES_URL = "https://places.googleapis.com/v1"
    DISTANCE_URL = "https://maps.googleapis.com/maps/api/distancematrix/json"
    GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"

    # Class-level geocode cache shared across instances for efficiency.
    _geocode_cache: ClassVar[dict[str, dict[str, float]]] = {}

    def __init__(self) -> None:
        self.api_key: str = settings.google_maps_api_key

    async def search_places(
        self,
        query: str,
        location: dict[str, float],
        radius: int = 5000,
    ) -> list[dict[str, Any]]:
        """Search for places using Places (New) API text search.

        Args:
            query: Natural-language place query.
            location: ``{"latitude": float, "longitude": float}`` bias centre.
            radius: Search radius in metres (default 5 000).

        Returns:
            List of place dicts, or empty list on error.
        """
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT, limits=_LIMITS) as client:
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
        except httpx.HTTPError as exc:
            logger.warning("Places API error for query '%s': %s", query, exc)
            return []

    async def get_distance_matrix(
        self,
        origins: list[str],
        destinations: list[str],
    ) -> dict[str, Any]:
        """Get travel time and distance between location pairs.

        Args:
            origins: List of origin addresses or ``lat,lng`` strings.
            destinations: List of destination addresses or ``lat,lng`` strings.

        Returns:
            Distance Matrix API response dict, or error stub on failure.
        """
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT, limits=_LIMITS) as client:
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
        except httpx.HTTPError as exc:
            logger.warning("Distance Matrix API error: %s", exc)
            return {"rows": [], "status": "ERROR"}

    async def geocode(self, address: str) -> dict[str, float]:
        """Geocode an address to latitude/longitude coordinates.

        Args:
            address: Human-readable address string.

        Returns:
            ``{"latitude": float, "longitude": float}`` or empty dict.
        """
        # Check class-level cache to avoid redundant API calls
        cache_key = address.strip().lower()
        if cache_key in GoogleMapsService._geocode_cache:
            return GoogleMapsService._geocode_cache[cache_key]

        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT, limits=_LIMITS) as client:
                response = await client.get(
                    self.GEOCODE_URL,
                    params={"address": address, "key": self.api_key},
                )
                response.raise_for_status()
                results = response.json().get("results", [])
                if results:
                    loc = results[0]["geometry"]["location"]
                    result = {"latitude": loc["lat"], "longitude": loc["lng"]}
                    GoogleMapsService._geocode_cache[cache_key] = result
                    return result
                return {}
        except httpx.HTTPError as exc:
            logger.warning("Geocode API error for '%s': %s", address, exc)
            return {}
