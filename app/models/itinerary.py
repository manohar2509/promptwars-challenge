"""Itinerary data models for trip representation.

These models describe the output of the AI planner: a multi-day
itinerary with scheduled activity slots, budget tracking, and metadata.
All fields are strongly typed and constrained for safe serialisation.
"""

from datetime import UTC, date, datetime
from enum import Enum

from pydantic import BaseModel, Field


class TimeSlot(str, Enum):
    """Time periods within a day."""

    morning = "morning"
    afternoon = "afternoon"
    evening = "evening"


class ActivitySlot(BaseModel):
    """A single activity within a day's schedule.

    Attributes:
        time_slot: Morning, afternoon, or evening.
        place_id: Optional Google Places ID for deep-linking.
        activity_name: Human-readable venue or activity name.
        description: 2-3 sentence description of the experience.
        duration_minutes: Expected duration (30-480 minutes).
        estimated_cost: Estimated cost in local currency (>= 0).
        category: One of food, transport, activity, accommodation.
        location: Optional geocoded coordinates and address.
        alternatives: Up to 2 alternative activities for this slot.
        weather_sensitive: True if the activity is outdoors.
        accessibility_notes: Relevant accessibility information.
    """

    time_slot: TimeSlot
    place_id: str | None = None
    activity_name: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., max_length=1000)
    duration_minutes: int = Field(ge=30, le=480)
    estimated_cost: float = Field(ge=0)
    category: str = Field(
        ...,
        pattern=r"^(food|transport|activity|accommodation)$",
        description="Activity category.",
    )
    location: dict | None = None  # {"lat": float, "lng": float, "address": str}
    alternatives: list["ActivitySlot"] = Field(default_factory=list, max_length=2)
    weather_sensitive: bool = False
    accessibility_notes: str = Field(default="", max_length=500)


class ItineraryDay(BaseModel):
    """A single day in the itinerary with scheduled activities.

    Attributes:
        day_number: 1-indexed day number within the trip.
        date: Calendar date for this day.
        slots: 1-4 activity slots scheduled for this day.
        day_summary: AI-generated summary of the day's plan.
        day_budget: Total estimated spend for this day.
    """

    day_number: int = Field(ge=1)
    date: date
    slots: list[ActivitySlot] = Field(min_length=1, max_length=4)
    day_summary: str = Field(default="", max_length=500)
    day_budget: float = Field(ge=0)


class BudgetBreakdown(BaseModel):
    """Budget allocation and tracking across categories.

    Attributes:
        total_budget: User-specified budget cap.
        spent: Computed total across all slots.
        accommodation: Accommodation sub-total.
        transport: Transport sub-total.
        food: Food and dining sub-total.
        activities: Activities and experiences sub-total.
        remaining: ``total_budget - spent`` (clamped ≥ 0).
    """

    total_budget: float = Field(ge=0)
    spent: float = Field(default=0, ge=0)
    accommodation: float = Field(default=0, ge=0)
    transport: float = Field(default=0, ge=0)
    food: float = Field(default=0, ge=0)
    activities: float = Field(default=0, ge=0)
    remaining: float = Field(default=0)


class Itinerary(BaseModel):
    """Complete trip itinerary with days, budget, and metadata.

    Attributes:
        id: Unique identifier (UUID4 string).
        destination: Trip destination city or region.
        days: Ordered list of itinerary days.
        budget: Aggregated budget breakdown.
        created_at: UTC timestamp of creation.
        updated_at: UTC timestamp of last modification.
        preferences_summary: Human-readable summary of user preferences.
        status: Lifecycle status — active, completed, or cancelled.
    """

    id: str = Field(..., min_length=1, max_length=64)
    destination: str = Field(..., min_length=1, max_length=200)
    days: list[ItineraryDay] = Field(min_length=1)
    budget: BudgetBreakdown
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    preferences_summary: str = Field(default="", max_length=500)
    status: str = Field(
        default="active",
        pattern=r"^(active|completed|cancelled)$",
        description="Itinerary lifecycle status.",
    )
