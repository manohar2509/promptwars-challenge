"""Constraint violation models for itinerary validation.

These models capture validation issues found during post-generation
constraint checking (budget overflow, schedule conflicts, etc.) and
carry remediation suggestions for the AI rebalancer.
"""

from enum import Enum

from pydantic import BaseModel, Field


class ViolationType(str, Enum):
    """Types of constraint violations detected during validation."""

    budget_overflow = "budget_overflow"
    schedule_conflict = "schedule_conflict"
    travel_time_exceeded = "travel_time_exceeded"
    weather_conflict = "weather_conflict"
    venue_unavailable = "venue_unavailable"


class ConstraintViolation(BaseModel):
    """A single constraint violation with remediation suggestion.

    Attributes:
        type: Category of the violation.
        severity: ``warning`` or ``error``.
        message: Human-readable description.
        affected_day: Day number affected (0 = all days).
        affected_slot: Slot label or ``all``.
        suggestion: Remediation hint for the AI rebalancer.
    """

    type: ViolationType
    severity: str = Field(..., pattern=r"^(warning|error)$")
    message: str = Field(..., min_length=1, max_length=500)
    affected_day: int = Field(ge=0)
    affected_slot: str = Field(..., min_length=1, max_length=50)
    suggestion: str = Field(default="", max_length=500)


class ValidationResult(BaseModel):
    """Result of constraint validation on an itinerary.

    Attributes:
        valid: ``True`` if no error-level violations were found.
        violations: List of detected violations.
        auto_fixed: List of issues that were automatically corrected.
    """

    valid: bool
    violations: list[ConstraintViolation] = Field(default_factory=list)
    auto_fixed: list[str] = Field(default_factory=list)
