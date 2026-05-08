"""Itinerary data models for trip representation."""
from pydantic import BaseModel, Field
from datetime import date, datetime, timezone
from typing import Optional
from enum import Enum


class TimeSlot(str, Enum):
    """Time periods within a day."""
    morning = "morning"
    afternoon = "afternoon"
    evening = "evening"


class ActivitySlot(BaseModel):
    """A single activity within a day's schedule."""
    time_slot: TimeSlot
    place_id: Optional[str] = None
    activity_name: str
    description: str
    duration_minutes: int = Field(ge=30, le=480)
    estimated_cost: float = Field(ge=0)
    category: str  # food, transport, activity, accommodation
    location: Optional[dict] = None  # {"lat": float, "lng": float, "address": str}
    alternatives: list["ActivitySlot"] = Field(default_factory=list, max_length=2)
    weather_sensitive: bool = False
    accessibility_notes: str = ""


class ItineraryDay(BaseModel):
    """A single day in the itinerary with scheduled activities."""
    day_number: int = Field(ge=1)
    date: date
    slots: list[ActivitySlot] = Field(min_length=1, max_length=4)
    day_summary: str = ""
    day_budget: float = Field(ge=0)


class BudgetBreakdown(BaseModel):
    """Budget allocation and tracking across categories."""
    total_budget: float
    spent: float = 0
    accommodation: float = 0
    transport: float = 0
    food: float = 0
    activities: float = 0
    remaining: float = 0


class Itinerary(BaseModel):
    """Complete trip itinerary with days, budget, and metadata."""
    id: str
    destination: str
    days: list[ItineraryDay]
    budget: BudgetBreakdown
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    preferences_summary: str = ""
    status: str = "active"  # active, completed, cancelled
