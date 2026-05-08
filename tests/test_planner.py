"""Tests for AI planning engine with mocked Gemini responses."""
import pytest
import json
from datetime import date, timedelta
from unittest.mock import patch, AsyncMock, MagicMock

from app.services.planner import PlannerService
from app.models.preferences import TravelPreferences, TravelStyle, Interest


def _valid_prefs(**overrides):
    defaults = {
        "destination": "Paris",
        "start_date": date.today() + timedelta(days=7),
        "end_date": date.today() + timedelta(days=10),
        "budget_amount": 1500.0,
        "interests": ["culture", "food"],
        "travel_style": "solo",
    }
    defaults.update(overrides)
    return TravelPreferences(**defaults)


class TestPlannerService:
    """Test planner with mock mode (no API key)."""

    def test_mock_itinerary_generated(self):
        service = PlannerService()
        prefs = _valid_prefs()
        itinerary = service._mock_itinerary(prefs)
        assert itinerary.destination == "Paris"
        assert len(itinerary.days) == 3
        assert itinerary.budget.total_budget == 1500.0

    def test_mock_itinerary_has_3_slots_per_day(self):
        service = PlannerService()
        prefs = _valid_prefs()
        itinerary = service._mock_itinerary(prefs)
        for day in itinerary.days:
            assert len(day.slots) == 3

    def test_mock_itinerary_budget_within_limit(self):
        service = PlannerService()
        prefs = _valid_prefs()
        itinerary = service._mock_itinerary(prefs)
        assert itinerary.budget.spent <= itinerary.budget.total_budget

    def test_mock_itinerary_1_day_trip(self):
        service = PlannerService()
        prefs = _valid_prefs(
            start_date=date.today() + timedelta(days=1),
            end_date=date.today() + timedelta(days=2),
        )
        itinerary = service._mock_itinerary(prefs)
        assert len(itinerary.days) == 1

    def test_mock_itinerary_has_alternatives(self):
        service = PlannerService()
        prefs = _valid_prefs()
        itinerary = service._mock_itinerary(prefs)
        # At least the morning slot should have alternatives
        assert len(itinerary.days[0].slots[0].alternatives) >= 1

    def test_parse_itinerary_valid(self):
        service = PlannerService()
        prefs = _valid_prefs()
        raw = {
            "days": [
                {
                    "day_number": 1,
                    "date": (date.today() + timedelta(days=7)).isoformat(),
                    "day_summary": "Day 1 in Paris",
                    "slots": [
                        {
                            "time_slot": "morning",
                            "activity_name": "Louvre Museum",
                            "description": "Visit the Louvre",
                            "duration_minutes": 180,
                            "estimated_cost": 20,
                            "category": "activity",
                            "weather_sensitive": False,
                            "accessibility_notes": "",
                            "alternatives": [],
                        },
                        {
                            "time_slot": "afternoon",
                            "activity_name": "Lunch at cafe",
                            "description": "Local French food",
                            "duration_minutes": 90,
                            "estimated_cost": 35,
                            "category": "food",
                            "weather_sensitive": False,
                            "accessibility_notes": "",
                        },
                        {
                            "time_slot": "evening",
                            "activity_name": "Seine River cruise",
                            "description": "Evening cruise",
                            "duration_minutes": 120,
                            "estimated_cost": 45,
                            "category": "activity",
                            "weather_sensitive": True,
                            "accessibility_notes": "Wheelchair accessible",
                        },
                    ],
                }
            ],
            "budget": {
                "total_budget": 1500,
                "accommodation": 400,
                "transport": 200,
                "food": 500,
                "activities": 400,
            },
        }
        itinerary = service._parse_itinerary(raw, prefs)
        assert itinerary.destination == "Paris"
        assert len(itinerary.days) == 1
        assert len(itinerary.days[0].slots) == 3
        assert itinerary.budget.total_budget == 1500

    def test_parse_itinerary_handles_malformed_slots(self):
        service = PlannerService()
        prefs = _valid_prefs()
        raw = {
            "days": [
                {
                    "day_number": 1,
                    "date": (date.today() + timedelta(days=7)).isoformat(),
                    "slots": [
                        {"bad": "data"},
                        {
                            "time_slot": "morning",
                            "activity_name": "Good Slot",
                            "description": "Valid",
                            "duration_minutes": 60,
                            "estimated_cost": 10,
                            "category": "activity",
                        },
                    ],
                }
            ],
            "budget": {},
        }
        itinerary = service._parse_itinerary(raw, prefs)
        assert len(itinerary.days) == 1
        assert len(itinerary.days[0].slots) == 1

    @pytest.mark.asyncio
    async def test_generate_falls_back_to_mock(self):
        """Without API key, generate should return mock data."""
        service = PlannerService()
        prefs = _valid_prefs()
        itinerary = await service.generate_itinerary(prefs, [], [])
        assert itinerary.destination == "Paris"
        assert len(itinerary.days) == prefs.num_days

    @pytest.mark.asyncio
    async def test_refine_no_api_key_returns_original(self):
        """Without API key, refine should return original itinerary."""
        service = PlannerService()
        prefs = _valid_prefs()
        original = service._mock_itinerary(prefs)
        refined = await service.refine_itinerary(original, "make it better")
        assert refined.id == original.id


class TestConstraintService:
    """Test constraint validation."""

    @pytest.mark.asyncio
    async def test_budget_within_limit_is_valid(self):
        from app.services.constraints import ConstraintService
        service = ConstraintService()
        planner = PlannerService()
        prefs = _valid_prefs()
        itinerary = planner._mock_itinerary(prefs)
        result = await service.validate_itinerary(itinerary)
        assert result.valid is True

    @pytest.mark.asyncio
    async def test_schedule_conflict_detected(self):
        from app.services.constraints import ConstraintService
        from app.models.itinerary import (
            Itinerary, ItineraryDay, ActivitySlot, BudgetBreakdown, TimeSlot
        )
        service = ConstraintService()
        # Create day with duplicate morning slots
        slot1 = ActivitySlot(
            time_slot=TimeSlot.morning, activity_name="A",
            description="x", duration_minutes=60, estimated_cost=10, category="activity",
        )
        slot2 = ActivitySlot(
            time_slot=TimeSlot.morning, activity_name="B",
            description="x", duration_minutes=60, estimated_cost=10, category="activity",
        )
        day = ItineraryDay(day_number=1, date=date.today(), slots=[slot1, slot2], day_budget=20)
        budget = BudgetBreakdown(total_budget=1000, spent=20, remaining=980)
        itinerary = Itinerary(id="test", destination="Test", days=[day], budget=budget)
        result = await service.validate_itinerary(itinerary)
        assert result.valid is False
        assert any(v.type.value == "schedule_conflict" for v in result.violations)
