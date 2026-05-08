"""Travel preference models for user input validation.

Defines the strongly-typed request schema for trip planning. All fields
are validated with Pydantic v2 constraints to reject malformed input
before it reaches the AI planner or external APIs.
"""

import re
from datetime import date
from enum import Enum

from pydantic import BaseModel, Field, field_validator


class TravelStyle(str, Enum):
    """Supported travel styles."""

    solo = "solo"
    couple = "couple"
    family = "family"
    group = "group"


class Interest(str, Enum):
    """Activity interest categories."""

    culture = "culture"
    food = "food"
    adventure = "adventure"
    relaxation = "relaxation"
    nightlife = "nightlife"
    nature = "nature"
    shopping = "shopping"


class AccessibilityNeeds(BaseModel):
    """Accessibility requirements for trip planning.

    These fields are forwarded to the AI planner so generated itineraries
    respect mobility, dietary, and physical-access constraints.
    """

    wheelchair_accessible: bool = False
    elevator_required: bool = False
    dietary_restrictions: list[str] = Field(
        default_factory=list,
        max_length=10,
        description="List of dietary restrictions (e.g. vegan, halal).",
    )
    mobility_notes: str = Field(
        default="",
        max_length=500,
        description="Free-text mobility notes for the AI planner.",
    )


# Regex: Unicode letters, spaces, hyphens, apostrophes, periods, commas.
_DESTINATION_PATTERN = re.compile(r"^[\w\s\-',.\u00C0-\u024F]+$")


class TravelPreferences(BaseModel):
    """Complete user travel preferences for itinerary generation.

    Every field that reaches the AI planner or an external API is
    validated here. The ``@field_validator`` methods enforce business
    rules that cannot be expressed with simple ``Field(...)`` constraints.
    """

    destination: str = Field(
        ...,
        min_length=2,
        max_length=100,
        description="City, country, or region to visit.",
    )
    start_date: date
    end_date: date
    budget_amount: float = Field(
        ...,
        gt=0,
        le=1_000_000,
        description="Total trip budget (must be positive).",
    )
    budget_currency: str = Field(
        default="USD",
        pattern=r"^[A-Z]{3}$",
        description="ISO 4217 currency code.",
    )
    interests: list[Interest] = Field(
        ...,
        min_length=1,
        max_length=7,
        description="At least one interest category is required.",
    )
    travel_style: TravelStyle
    group_size: int = Field(
        default=1,
        ge=1,
        le=20,
        description="Number of travellers (1-20).",
    )
    accessibility: AccessibilityNeeds = Field(default_factory=AccessibilityNeeds)

    @field_validator("destination")
    @classmethod
    def validate_destination_characters(cls, v: str) -> str:
        """Reject destinations with suspicious or injection-prone characters."""
        v = v.strip()
        if not _DESTINATION_PATTERN.match(v):
            raise ValueError(
                "Destination must contain only letters, spaces, hyphens, "
                "apostrophes, or periods."
            )
        return v

    @field_validator("end_date")
    @classmethod
    def end_after_start(cls, v: date, info) -> date:
        """Ensure the trip end date is strictly after the start date and within 30 days."""
        if "start_date" in info.data and v <= info.data["start_date"]:
            raise ValueError("end_date must be after start_date")
        if "start_date" in info.data and (v - info.data["start_date"]).days > 30:
            raise ValueError("Trip duration cannot exceed 30 days")
        return v

    @field_validator("start_date")
    @classmethod
    def start_not_past(cls, v: date) -> date:
        """Reject start dates that are in the past."""
        if v < date.today():
            raise ValueError("start_date cannot be in the past")
        return v

    @property
    def num_days(self) -> int:
        """Calculate trip duration in days."""
        return (self.end_date - self.start_date).days
