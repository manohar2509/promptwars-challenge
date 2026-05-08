"""Constraint validation and budget rebalancing for itineraries.

Post-generation validation layer that checks budget limits, schedule
conflicts, and day completeness. When violations are detected, the
service can invoke the AI planner to rebalance costs automatically.
"""

import logging

from app.models.constraints import ConstraintViolation, ValidationResult, ViolationType
from app.models.itinerary import Itinerary
from app.services.google_maps import GoogleMapsService

logger = logging.getLogger(__name__)


class ConstraintService:
    """Validate itinerary constraints and rebalance budgets.

    Runs a configurable set of constraint checks against a generated
    itinerary and returns a ``ValidationResult`` with violations and
    auto-fix annotations.
    """

    def __init__(self) -> None:
        self.maps = GoogleMapsService()

    async def validate_itinerary(self, itinerary: Itinerary) -> ValidationResult:
        """Run all constraint checks on an itinerary.

        Args:
            itinerary: The itinerary to validate.

        Returns:
            A ``ValidationResult`` indicating whether the itinerary
            passes all constraints, with details on any violations.
        """
        violations: list[ConstraintViolation] = []
        auto_fixed: list[str] = []

        violations.extend(self._check_budget(itinerary))
        violations.extend(self._check_schedule_conflicts(itinerary))
        violations.extend(self._check_empty_days(itinerary))

        return ValidationResult(
            valid=not any(v.severity == "error" for v in violations),
            violations=violations,
            auto_fixed=auto_fixed,
        )

    # ------------------------------------------------------------------
    # Individual constraint checks
    # ------------------------------------------------------------------

    @staticmethod
    def _check_budget(itinerary: Itinerary) -> list[ConstraintViolation]:
        """Check if total costs exceed or approach the budget limit.

        Returns an error-level violation if budget is exceeded, or a
        warning if budget usage is above 90 %.
        """
        total_spent = sum(
            slot.estimated_cost
            for day in itinerary.days
            for slot in day.slots
        )
        violations: list[ConstraintViolation] = []
        if total_spent > itinerary.budget.total_budget:
            violations.append(
                ConstraintViolation(
                    type=ViolationType.budget_overflow,
                    severity="error",
                    message=(
                        f"Budget exceeded: ${total_spent:.2f} > "
                        f"${itinerary.budget.total_budget:.2f}"
                    ),
                    affected_day=0,
                    affected_slot="all",
                    suggestion="Reduce accommodation tier or remove premium activities",
                )
            )
        elif total_spent > itinerary.budget.total_budget * 0.9:
            violations.append(
                ConstraintViolation(
                    type=ViolationType.budget_overflow,
                    severity="warning",
                    message=(
                        f"Budget is 90%+ used: ${total_spent:.2f} of "
                        f"${itinerary.budget.total_budget:.2f}"
                    ),
                    affected_day=0,
                    affected_slot="all",
                    suggestion="Consider having some buffer for unexpected expenses",
                )
            )
        return violations

    @staticmethod
    def _check_schedule_conflicts(itinerary: Itinerary) -> list[ConstraintViolation]:
        """Check for duplicate time slots within a single day."""
        violations: list[ConstraintViolation] = []
        for day in itinerary.days:
            slots_used = [s.time_slot for s in day.slots]
            if len(slots_used) != len(set(slots_used)):
                violations.append(
                    ConstraintViolation(
                        type=ViolationType.schedule_conflict,
                        severity="error",
                        message=f"Day {day.day_number} has duplicate time slots",
                        affected_day=day.day_number,
                        affected_slot="multiple",
                        suggestion="Remove or reassign duplicate slots",
                    )
                )
        return violations

    @staticmethod
    def _check_empty_days(itinerary: Itinerary) -> list[ConstraintViolation]:
        """Check for days with too few activities (< 2 slots)."""
        violations: list[ConstraintViolation] = []
        for day in itinerary.days:
            if len(day.slots) < 2:
                violations.append(
                    ConstraintViolation(
                        type=ViolationType.schedule_conflict,
                        severity="warning",
                        message=f"Day {day.day_number} has only {len(day.slots)} activity",
                        affected_day=day.day_number,
                        affected_slot="all",
                        suggestion="Consider adding more activities to fill the day",
                    )
                )
        return violations

    # ------------------------------------------------------------------
    # Budget rebalancing via AI
    # ------------------------------------------------------------------

    async def rebalance_budget(self, itinerary: Itinerary) -> Itinerary:
        """Use Gemini to rebalance budget when overflow is detected.

        Delegates to ``PlannerService.refine_itinerary`` with a
        cost-reduction prompt. Import is deferred to avoid circular
        imports between planner ↔ constraints.

        Args:
            itinerary: The over-budget itinerary to fix.

        Returns:
            A budget-compliant itinerary (best-effort).
        """
        from app.services.planner import PlannerService

        planner = PlannerService()
        overage = itinerary.budget.spent - itinerary.budget.total_budget
        return await planner.refine_itinerary(
            itinerary,
            f"The total cost exceeds the budget by ${overage:.0f}. "
            f"Reduce costs by: 1) downgrading accommodation tier first, "
            f"2) replacing expensive activities with free/cheap alternatives, "
            f"3) simplifying meals. Keep the same destinations and travel style. "
            f"Total budget must not exceed ${itinerary.budget.total_budget:.0f}.",
        )
