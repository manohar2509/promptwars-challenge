"""Weather forecast service using Open-Meteo API.

Fetches daily weather forecasts and determines whether outdoor
activities should be swapped to indoor alternatives based on
precipitation, temperature extremes, and severe weather codes.
"""

import logging
from datetime import date
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# WMO weather codes indicating severe conditions that warrant indoor swaps.
SEVERE_WEATHER_CODES: frozenset[int] = frozenset({
    65, 67,        # heavy rain / freezing rain
    71, 73, 75, 77,  # snowfall
    80, 82,        # rain showers
    85, 86,        # snow showers
    95, 96, 99,    # thunderstorms
})

# Shared timeout configuration.
_TIMEOUT = httpx.Timeout(10.0, connect=5.0)


class WeatherService:
    """Fetch weather forecasts and make outdoor/indoor scheduling decisions.

    Uses the free Open-Meteo API (no API key required).
    """

    BASE_URL = "https://api.open-meteo.com/v1/forecast"

    async def get_forecast(
        self,
        latitude: float,
        longitude: float,
        start_date: date,
        end_date: date,
    ) -> list[dict[str, Any]]:
        """Fetch daily weather forecast from Open-Meteo.

        Args:
            latitude: Destination latitude.
            longitude: Destination longitude.
            start_date: First forecast day.
            end_date: Last forecast day (inclusive).

        Returns:
            List of daily forecast dicts with temp, precipitation, and
            weather codes. Returns empty list on API error.
        """
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                response = await client.get(
                    self.BASE_URL,
                    params={
                        "latitude": latitude,
                        "longitude": longitude,
                        "daily": (
                            "temperature_2m_max,temperature_2m_min,"
                            "precipitation_probability_max,weather_code"
                        ),
                        "start_date": start_date.isoformat(),
                        "end_date": end_date.isoformat(),
                        "timezone": "auto",
                    },
                )
                response.raise_for_status()
                data = response.json()["daily"]
                return [
                    {
                        "date": data["time"][i],
                        "temp_max": data["temperature_2m_max"][i],
                        "temp_min": data["temperature_2m_min"][i],
                        "precipitation_prob": data["precipitation_probability_max"][i],
                        "weather_code": data["weather_code"][i],
                    }
                    for i in range(len(data["time"]))
                ]
        except (httpx.HTTPError, KeyError) as exc:
            logger.warning("Weather API error: %s", exc)
            return []

    @staticmethod
    def should_swap_indoor(forecast_day: dict[str, Any]) -> bool:
        """Determine if outdoor activities should be moved indoors.

        Conditions that trigger an indoor swap:
        - Precipitation probability > 60 %
        - Maximum temperature > 42 °C (extreme heat)
        - WMO severe weather code (thunderstorm, heavy snow, etc.)

        Args:
            forecast_day: Single day forecast dict from ``get_forecast``.

        Returns:
            ``True`` if outdoor activities should be swapped indoors.
        """
        return (
            forecast_day.get("precipitation_prob", 0) > 60
            or forecast_day.get("temp_max", 25) > 42
            or forecast_day.get("weather_code", 0) in SEVERE_WEATHER_CODES
        )
