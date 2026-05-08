"""Tests for Pydantic models — preferences, itinerary, constraints."""
import pytest
from datetime import date, timedelta
from pydantic import ValidationError
from app.models.preferences import (
    TravelPreferences, TravelStyle, Interest, AccessibilityNeeds
)
from app.models.itinerary import (
    ActivitySlot, ItineraryDay, Itinerary, BudgetBreakdown, TimeSlot
)
from app.models.constraints import (
    ConstraintViolation, ValidationResult, ViolationType
)


# --- Preferences Tests ---

class TestTravelPreferences:
    """Test TravelPreferences validation."""

    def _valid_prefs(self, **overrides):
        defaults = {
            "destination": "Paris",
            "start_date": date.today() + timedelta(days=7),
            "end_date": date.today() + timedelta(days=10),
            "budget_amount": 1500.0,
            "budget_currency": "USD",
            "interests": ["culture", "food"],
            "travel_style": "solo",
            "group_size": 1,
        }
        defaults.update(overrides)
        return TravelPreferences(**defaults)

    def test_valid_preferences(self):
        prefs = self._valid_prefs()
        assert prefs.destination == "Paris"
        assert prefs.num_days == 3

    def test_end_before_start_fails(self):
        with pytest.raises(ValidationError, match="end_date must be after start_date"):
            self._valid_prefs(
                start_date=date.today() + timedelta(days=10),
                end_date=date.today() + timedelta(days=5),
            )

    def test_same_start_end_fails(self):
        d = date.today() + timedelta(days=7)
        with pytest.raises(ValidationError):
            self._valid_prefs(start_date=d, end_date=d)

    def test_past_start_date_fails(self):
        with pytest.raises(ValidationError, match="start_date cannot be in the past"):
            self._valid_prefs(start_date=date.today() - timedelta(days=1))

    def test_zero_budget_fails(self):
        with pytest.raises(ValidationError):
            self._valid_prefs(budget_amount=0)

    def test_negative_budget_fails(self):
        with pytest.raises(ValidationError):
            self._valid_prefs(budget_amount=-100)

    def test_empty_destination_fails(self):
        with pytest.raises(ValidationError):
            self._valid_prefs(destination="")

    def test_single_char_destination_fails(self):
        with pytest.raises(ValidationError):
            self._valid_prefs(destination="X")

    def test_long_destination_fails(self):
        with pytest.raises(ValidationError):
            self._valid_prefs(destination="X" * 101)

    def test_empty_interests_fails(self):
        with pytest.raises(ValidationError):
            self._valid_prefs(interests=[])

    def test_invalid_currency_fails(self):
        with pytest.raises(ValidationError):
            self._valid_prefs(budget_currency="usd")

    def test_group_size_zero_fails(self):
        with pytest.raises(ValidationError):
            self._valid_prefs(group_size=0)

    def test_group_size_over_20_fails(self):
        with pytest.raises(ValidationError):
            self._valid_prefs(group_size=21)

    def test_one_day_trip(self):
        prefs = self._valid_prefs(
            start_date=date.today() + timedelta(days=1),
            end_date=date.today() + timedelta(days=2),
        )
        assert prefs.num_days == 1

    def test_30_day_trip(self):
        prefs = self._valid_prefs(
            start_date=date.today() + timedelta(days=1),
            end_date=date.today() + timedelta(days=31),
        )
        assert prefs.num_days == 30

    def test_all_interests(self):
        prefs = self._valid_prefs(interests=list(Interest))
        assert len(prefs.interests) == 7

    def test_accessibility_defaults(self):
        prefs = self._valid_prefs()
        assert prefs.accessibility.wheelchair_accessible is False
        assert prefs.accessibility.dietary_restrictions == []

    def test_accessibility_custom(self):
        prefs = self._valid_prefs(
            accessibility={
                "wheelchair_accessible": True,
                "elevator_required": True,
                "dietary_restrictions": ["vegan", "gluten-free"],
                "mobility_notes": "Uses wheelchair"
            }
        )
        assert prefs.accessibility.wheelchair_accessible is True
        assert len(prefs.accessibility.dietary_restrictions) == 2


# --- Itinerary Tests ---

class TestItineraryModels:
    """Test itinerary data models."""

    def _make_slot(self, **overrides):
        defaults = {
            "time_slot": "morning",
            "activity_name": "Visit Museum",
            "description": "Explore the national museum",
            "duration_minutes": 120,
            "estimated_cost": 25.0,
            "category": "activity",
        }
        defaults.update(overrides)
        return ActivitySlot(**defaults)

    def test_valid_slot(self):
        slot = self._make_slot()
        assert slot.activity_name == "Visit Museum"
        assert slot.weather_sensitive is False

    def test_slot_duration_min(self):
        slot = self._make_slot(duration_minutes=30)
        assert slot.duration_minutes == 30

    def test_slot_duration_too_short(self):
        with pytest.raises(ValidationError):
            self._make_slot(duration_minutes=10)

    def test_slot_duration_too_long(self):
        with pytest.raises(ValidationError):
            self._make_slot(duration_minutes=500)

    def test_slot_negative_cost(self):
        with pytest.raises(ValidationError):
            self._make_slot(estimated_cost=-10)

    def test_slot_with_alternatives(self):
        alt = self._make_slot(activity_name="Alternative")
        slot = self._make_slot(alternatives=[alt])
        assert len(slot.alternatives) == 1

    def test_slot_with_location(self):
        slot = self._make_slot(location={"lat": 48.8566, "lng": 2.3522, "address": "Paris"})
        assert slot.location["lat"] == 48.8566

    def test_itinerary_day(self):
        slot = self._make_slot()
        day = ItineraryDay(
            day_number=1,
            date=date.today(),
            slots=[slot],
            day_budget=25.0,
        )
        assert day.day_number == 1

    def test_budget_breakdown(self):
        budget = BudgetBreakdown(
            total_budget=1000, spent=750,
            accommodation=300, transport=100, food=200, activities=150,
            remaining=250,
        )
        assert budget.remaining == 250

    def test_full_itinerary(self):
        slot = self._make_slot()
        day = ItineraryDay(day_number=1, date=date.today(), slots=[slot], day_budget=25.0)
        budget = BudgetBreakdown(total_budget=1000, spent=25, remaining=975)
        itinerary = Itinerary(
            id="test-123", destination="Paris",
            days=[day], budget=budget,
        )
        assert itinerary.id == "test-123"
        assert itinerary.status == "active"

    def test_itinerary_json_serialization(self):
        slot = self._make_slot()
        day = ItineraryDay(day_number=1, date=date.today(), slots=[slot], day_budget=25.0)
        budget = BudgetBreakdown(total_budget=1000, spent=25, remaining=975)
        itinerary = Itinerary(id="test-123", destination="Paris", days=[day], budget=budget)
        json_data = itinerary.model_dump(mode="json")
        restored = Itinerary.model_validate(json_data)
        assert restored.id == itinerary.id


# --- Constraints Tests ---

class TestConstraintModels:
    """Test constraint validation models."""

    def test_constraint_violation(self):
        v = ConstraintViolation(
            type=ViolationType.budget_overflow,
            severity="error",
            message="Budget exceeded",
            affected_day=1,
            affected_slot="all",
        )
        assert v.type == ViolationType.budget_overflow

    def test_valid_result(self):
        result = ValidationResult(valid=True)
        assert result.valid is True
        assert result.violations == []

    def test_invalid_result(self):
        v = ConstraintViolation(
            type=ViolationType.schedule_conflict,
            severity="error",
            message="Duplicate slots",
            affected_day=2,
            affected_slot="morning",
        )
        result = ValidationResult(valid=False, violations=[v])
        assert result.valid is False
        assert len(result.violations) == 1
