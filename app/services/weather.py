"""Weather forecast service using Open-Meteo API."""
import httpx
import logging
from datetime import date

logger = logging.getLogger(__name__)

# WMO weather codes indicating severe conditions
SEVERE_WEATHER_CODES = {
    65, 67,  # heavy rain / freezing rain
    71, 73, 75, 77,  # snowfall
    80, 82,  # rain showers
    85, 86,  # snow showers
    95, 96, 99,  # thunderstorms
}


class WeatherService:
    """Fetch weather forecasts and make outdoor/indoor decisions."""

    BASE_URL = "https://api.open-meteo.com/v1/forecast"

    async def get_forecast(
        self,
        latitude: float,
        longitude: float,
        start_date: date,
        end_date: date,
    ) -> list[dict]:
        """Fetch daily weather forecast from Open-Meteo."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
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
        except (httpx.HTTPError, KeyError) as e:
            logger.warning("Weather API error: %s", e)
            return []

    def should_swap_indoor(self, forecast_day: dict) -> bool:
        """Determine if outdoor activities should be moved indoors."""
        return (
            forecast_day.get("precipitation_prob", 0) > 60
            or forecast_day.get("temp_max", 25) > 42
            or forecast_day.get("weather_code", 0) in SEVERE_WEATHER_CODES
        )
