"""Tests for Google services — Maps, Calendar, Weather."""
from datetime import date

import httpx
import pytest
import respx

from app.models.itinerary import ActivitySlot, BudgetBreakdown, Itinerary, ItineraryDay, TimeSlot
from app.services.google_calendar import CalendarService
from app.services.google_maps import GoogleMapsService
from app.services.weather import WeatherService


@pytest.fixture(autouse=True)
def clear_geocode_cache():
    """Clear geocode cache before each test to prevent cross-test interference."""
    GoogleMapsService._geocode_cache.clear()
    yield
    GoogleMapsService._geocode_cache.clear()


# --- Google Maps Tests ---

class TestGoogleMapsService:
    """Test Google Maps service with mocked HTTP responses."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_geocode_success(self):
        respx.get("https://maps.googleapis.com/maps/api/geocode/json").mock(
            return_value=httpx.Response(200, json={
                "results": [{"geometry": {"location": {"lat": 48.8566, "lng": 2.3522}}}]
            })
        )
        service = GoogleMapsService()
        result = await service.geocode("Paris")
        assert result["latitude"] == 48.8566
        assert result["longitude"] == 2.3522

    @respx.mock
    @pytest.mark.asyncio
    async def test_geocode_not_found(self):
        respx.get("https://maps.googleapis.com/maps/api/geocode/json").mock(
            return_value=httpx.Response(200, json={"results": []})
        )
        service = GoogleMapsService()
        result = await service.geocode("NonexistentPlace12345")
        assert result == {}

    @respx.mock
    @pytest.mark.asyncio
    async def test_geocode_api_error(self):
        respx.get("https://maps.googleapis.com/maps/api/geocode/json").mock(
            return_value=httpx.Response(500)
        )
        service = GoogleMapsService()
        result = await service.geocode("Paris")
        assert result == {}

    @respx.mock
    @pytest.mark.asyncio
    async def test_search_places_success(self):
        respx.post("https://places.googleapis.com/v1/places:searchText").mock(
            return_value=httpx.Response(200, json={
                "places": [
                    {"displayName": {"text": "Louvre"}, "id": "place1", "rating": 4.7}
                ]
            })
        )
        service = GoogleMapsService()
        results = await service.search_places(
            "museums in Paris", {"latitude": 48.8566, "longitude": 2.3522}
        )
        assert len(results) == 1

    @respx.mock
    @pytest.mark.asyncio
    async def test_search_places_empty(self):
        respx.post("https://places.googleapis.com/v1/places:searchText").mock(
            return_value=httpx.Response(200, json={"places": []})
        )
        service = GoogleMapsService()
        results = await service.search_places("xyz", {"latitude": 0, "longitude": 0})
        assert results == []

    @respx.mock
    @pytest.mark.asyncio
    async def test_distance_matrix_success(self):
        respx.get("https://maps.googleapis.com/maps/api/distancematrix/json").mock(
            return_value=httpx.Response(200, json={
                "rows": [{"elements": [{"duration": {"value": 1800, "text": "30 mins"}}]}],
                "status": "OK"
            })
        )
        service = GoogleMapsService()
        result = await service.get_distance_matrix(["Paris"], ["Lyon"])
        assert result["status"] == "OK"


# --- Weather Tests ---

class TestWeatherService:
    """Test weather forecast service."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_forecast_success(self):
        respx.get("https://api.open-meteo.com/v1/forecast").mock(
            return_value=httpx.Response(200, json={
                "daily": {
                    "time": ["2026-05-10", "2026-05-11"],
                    "temperature_2m_max": [25.0, 30.0],
                    "temperature_2m_min": [15.0, 18.0],
                    "precipitation_probability_max": [10, 80],
                    "weather_code": [1, 65],
                }
            })
        )
        service = WeatherService()
        forecast = await service.get_forecast(
            48.8566, 2.3522, date(2026, 5, 10), date(2026, 5, 11)
        )
        assert len(forecast) == 2
        assert forecast[0]["temp_max"] == 25.0

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_forecast_api_error(self):
        respx.get("https://api.open-meteo.com/v1/forecast").mock(
            return_value=httpx.Response(500)
        )
        service = WeatherService()
        forecast = await service.get_forecast(48.8, 2.35, date(2026, 5, 10), date(2026, 5, 11))
        assert forecast == []

    def test_should_swap_indoor_rain(self):
        service = WeatherService()
        assert service.should_swap_indoor({"precipitation_prob": 70, "temp_max": 25, "weather_code": 1})

    def test_should_swap_indoor_extreme_heat(self):
        service = WeatherService()
        assert service.should_swap_indoor({"precipitation_prob": 10, "temp_max": 45, "weather_code": 1})

    def test_should_swap_indoor_thunderstorm(self):
        service = WeatherService()
        assert service.should_swap_indoor({"precipitation_prob": 30, "temp_max": 25, "weather_code": 95})

    def test_should_not_swap_indoor_nice_day(self):
        service = WeatherService()
        assert not service.should_swap_indoor({"precipitation_prob": 10, "temp_max": 25, "weather_code": 1})


# --- Calendar Tests ---

class TestCalendarService:
    """Test .ics calendar generation."""

    def _make_itinerary(self):
        slot = ActivitySlot(
            time_slot=TimeSlot.morning,
            activity_name="Visit Louvre",
            description="Explore the famous museum",
            duration_minutes=180,
            estimated_cost=20.0,
            category="activity",
            location={"lat": 48.8606, "lng": 2.3376, "address": "Louvre, Paris"},
        )
        day = ItineraryDay(
            day_number=1, date=date(2026, 5, 15),
            slots=[slot], day_budget=20.0,
        )
        budget = BudgetBreakdown(total_budget=1000, spent=20, remaining=980)
        return Itinerary(id="cal-test", destination="Paris", days=[day], budget=budget)

    def test_generate_ics_valid(self):
        service = CalendarService()
        itinerary = self._make_itinerary()
        ics = service.generate_ics(itinerary)
        assert isinstance(ics, bytes)
        content = ics.decode("utf-8")
        assert "BEGIN:VCALENDAR" in content
        assert "Visit Louvre" in content
        assert "BEGIN:VEVENT" in content
        assert "END:VCALENDAR" in content

    def test_generate_ics_has_location(self):
        service = CalendarService()
        itinerary = self._make_itinerary()
        ics = service.generate_ics(itinerary)
        assert b"Louvre" in ics

    def test_generate_ics_multiple_days(self):
        slot1 = ActivitySlot(
            time_slot=TimeSlot.morning, activity_name="Day 1",
            description="Morning", duration_minutes=120,
            estimated_cost=10, category="activity",
        )
        slot2 = ActivitySlot(
            time_slot=TimeSlot.afternoon, activity_name="Day 2",
            description="Afternoon", duration_minutes=120,
            estimated_cost=10, category="activity",
        )
        days = [
            ItineraryDay(day_number=1, date=date(2026, 5, 15), slots=[slot1], day_budget=10),
            ItineraryDay(day_number=2, date=date(2026, 5, 16), slots=[slot2], day_budget=10),
        ]
        budget = BudgetBreakdown(total_budget=100, spent=20, remaining=80)
        itinerary = Itinerary(id="multi", destination="Rome", days=days, budget=budget)
        service = CalendarService()
        ics = service.generate_ics(itinerary)
        content = ics.decode("utf-8")
        assert content.count("BEGIN:VEVENT") == 2
