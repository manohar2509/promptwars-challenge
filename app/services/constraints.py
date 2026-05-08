"""Constraint validation and budget rebalancing for itineraries."""
import logging
from app.models.itinerary import Itinerary
from app.models.constraints import ConstraintViolation, ValidationResult, ViolationType
from app.services.google_maps import GoogleMapsService

logger = logging.getLogger(__name__)


class ConstraintService:
    """Validate itinerary constraints and rebalance budgets."""

    def __init__(self):
        self.maps = GoogleMapsService()

    async def validate_itinerary(self, itinerary: Itinerary) -> ValidationResult:
        """Run all constraint checks on an itinerary."""
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

    def _check_budget(self, itinerary: Itinerary) -> list[ConstraintViolation]:
        """Check if total costs exceed budget."""
        total_spent = sum(
            slot.estimated_cost
            for day in itinerary.days
            for slot in day.slots
        )
        violations = []
        if total_spent > itinerary.budget.total_budget:
            violations.append(
                ConstraintViolation(
                    type=ViolationType.budget_overflow,
                    severity="error",
                    message=f"Budget exceeded: ${total_spent:.2f} > ${itinerary.budget.total_budget:.2f}",
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
                    message=f"Budget is 90%+ used: ${total_spent:.2f} of ${itinerary.budget.total_budget:.2f}",
                    affected_day=0,
                    affected_slot="all",
                    suggestion="Consider having some buffer for unexpected expenses",
                )
            )
        return violations

    def _check_schedule_conflicts(self, itinerary: Itinerary) -> list[ConstraintViolation]:
        """Check for duplicate time slots within a day."""
        violations = []
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

    def _check_empty_days(self, itinerary: Itinerary) -> list[ConstraintViolation]:
        """Check for days with too few activities."""
        violations = []
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

    async def rebalance_budget(self, itinerary: Itinerary) -> Itinerary:
        """Use Gemini to rebalance budget when overflow detected."""
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
