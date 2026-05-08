"""Travel preference models for user input validation."""
from pydantic import BaseModel, Field, field_validator
from enum import Enum
from datetime import date


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
    """Accessibility requirements for trip planning."""
    wheelchair_accessible: bool = False
    elevator_required: bool = False
    dietary_restrictions: list[str] = Field(default_factory=list)
    mobility_notes: str = ""


class TravelPreferences(BaseModel):
    """Complete user travel preferences for itinerary generation."""
    destination: str = Field(..., min_length=2, max_length=100)
    start_date: date
    end_date: date
    budget_amount: float = Field(..., gt=0)
    budget_currency: str = Field(default="USD", pattern=r"^[A-Z]{3}$")
    interests: list[Interest] = Field(..., min_length=1)
    travel_style: TravelStyle
    group_size: int = Field(default=1, ge=1, le=20)
    accessibility: AccessibilityNeeds = Field(default_factory=AccessibilityNeeds)

    @field_validator("end_date")
    @classmethod
    def end_after_start(cls, v, info):
        if "start_date" in info.data and v <= info.data["start_date"]:
            raise ValueError("end_date must be after start_date")
        return v

    @field_validator("start_date")
    @classmethod
    def start_not_past(cls, v):
        if v < date.today():
            raise ValueError("start_date cannot be in the past")
        return v

    @property
    def num_days(self) -> int:
        """Calculate trip duration in days."""
        return (self.end_date - self.start_date).days
