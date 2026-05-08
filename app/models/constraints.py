"""Constraint violation models for itinerary validation."""
from pydantic import BaseModel
from enum import Enum


class ViolationType(str, Enum):
    """Types of constraint violations."""
    budget_overflow = "budget_overflow"
    schedule_conflict = "schedule_conflict"
    travel_time_exceeded = "travel_time_exceeded"
    weather_conflict = "weather_conflict"
    venue_unavailable = "venue_unavailable"


class ConstraintViolation(BaseModel):
    """A single constraint violation with remediation suggestion."""
    type: ViolationType
    severity: str  # warning, error
    message: str
    affected_day: int
    affected_slot: str
    suggestion: str = ""


class ValidationResult(BaseModel):
    """Result of constraint validation on an itinerary."""
    valid: bool
    violations: list[ConstraintViolation] = []
    auto_fixed: list[str] = []
