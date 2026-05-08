"""Pydantic data models for travel preferences, itineraries, and constraints.

All models use strict validation with type hints, field constraints,
and custom validators to ensure data integrity at the boundary.
"""

from app.models.constraints import (
    ConstraintViolation,
    ValidationResult,
    ViolationType,
)
from app.models.itinerary import (
    ActivitySlot,
    BudgetBreakdown,
    Itinerary,
    ItineraryDay,
    TimeSlot,
)
from app.models.preferences import (
    AccessibilityNeeds,
    Interest,
    TravelPreferences,
    TravelStyle,
)

__all__ = [
    "TravelPreferences",
    "TravelStyle",
    "Interest",
    "AccessibilityNeeds",
    "Itinerary",
    "ItineraryDay",
    "ActivitySlot",
    "BudgetBreakdown",
    "TimeSlot",
    "ConstraintViolation",
    "ValidationResult",
    "ViolationType",
]
