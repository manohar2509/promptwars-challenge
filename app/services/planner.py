"""AI-powered trip planning engine using Google Gemini."""
import json
import logging
from uuid import uuid4
from datetime import datetime, timedelta

import google.generativeai as genai

from app.config import settings
from app.models.preferences import TravelPreferences
from app.models.itinerary import (
    Itinerary, ItineraryDay, ActivitySlot, BudgetBreakdown, TimeSlot
)

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an expert travel planner AI. Generate detailed, realistic day-by-day travel itineraries.

RULES:
- Each day MUST have exactly 3 slots: morning, afternoon, evening
- Respect the budget constraint STRICTLY — total costs must not exceed the given budget
- Consider accessibility needs and dietary restrictions
- Include a diverse mix of activities matching the user's interests
- Each slot must have these fields:
  - time_slot: "morning" | "afternoon" | "evening"
  - activity_name: string (specific venue/activity name)
  - description: string (2-3 sentences describing the experience)
  - duration_minutes: integer (30-480)
  - estimated_cost: number (realistic local pricing, 0 for free activities)
  - category: "food" | "transport" | "activity" | "accommodation"
  - weather_sensitive: boolean (true for outdoor activities)
  - accessibility_notes: string (relevant accessibility info)
  - alternatives: array of 2 alternative activity objects (same structure, no nested alternatives)
- Each day needs: day_number, date (YYYY-MM-DD format), slots array, day_summary
- Include a budget object with: total_budget, accommodation, transport, food, activities

OUTPUT FORMAT: Valid JSON only. No markdown, no explanations."""


class PlannerService:
    """Generate and refine travel itineraries using Gemini AI."""

    def __init__(self):
        if settings.gemini_api_key:
            genai.configure(api_key=settings.gemini_api_key)
            self.model = genai.GenerativeModel(
                "gemini-2.0-flash",
                system_instruction=SYSTEM_PROMPT,
            )
        else:
            self.model = None
            logger.warning("Gemini API key not set — planner will use mock data")

    async def generate_itinerary(
        self,
        preferences: TravelPreferences,
        places: list[dict],
        weather: list[dict],
    ) -> Itinerary:
        """Generate a complete itinerary from preferences, places, and weather."""
        if self.model is None:
            return self._mock_itinerary(preferences)

        prompt = self._build_planning_prompt(preferences, places, weather)

        try:
            response = await self.model.generate_content_async(
                prompt,
                generation_config=genai.GenerationConfig(
                    response_mime_type="application/json",
                    temperature=0.7,
                ),
            )
            raw = json.loads(response.text)
            return self._parse_itinerary(raw, preferences)
        except Exception as e:
            logger.error("Gemini planning error: %s", e)
            return self._mock_itinerary(preferences)

    async def refine_itinerary(
        self, itinerary: Itinerary, user_message: str
    ) -> Itinerary:
        """Refine existing itinerary based on natural language instruction."""
        if self.model is None:
            return itinerary

        prompt = f"""Current itinerary (JSON):
{itinerary.model_dump_json(indent=2)}

User request: {user_message}

Modify ONLY the affected slots. Keep the same id, destination, and dates.
Return the COMPLETE updated itinerary as valid JSON."""

        try:
            response = await self.model.generate_content_async(
                prompt,
                generation_config=genai.GenerationConfig(
                    response_mime_type="application/json",
                    temperature=0.5,
                ),
            )
            raw = json.loads(response.text)
            updated = self._parse_itinerary(raw, None)
            # Preserve original ID
            updated.id = itinerary.id
            return updated
        except Exception as e:
            logger.error("Gemini refinement error: %s", e)
            return itinerary

    def _build_planning_prompt(
        self,
        prefs: TravelPreferences,
        places: list[dict],
        weather: list[dict],
    ) -> str:
        """Build the planning prompt with all context."""
        # Generate date list for itinerary days
        dates = [
            (prefs.start_date + timedelta(days=i)).isoformat()
            for i in range(prefs.num_days)
        ]

        return f"""Plan a {prefs.num_days}-day trip to {prefs.destination}.

PREFERENCES:
- Budget: {prefs.budget_amount} {prefs.budget_currency} (STRICT LIMIT)
- Travel style: {prefs.travel_style.value}
- Group size: {prefs.group_size}
- Interests: {', '.join(i.value for i in prefs.interests)}
- Dates: {prefs.start_date} to {prefs.end_date}
- Day dates: {', '.join(dates)}

ACCESSIBILITY REQUIREMENTS:
{prefs.accessibility.model_dump_json(indent=2)}

AVAILABLE VENUES (from Google Places):
{json.dumps(places[:20], indent=2, default=str)}

WEATHER FORECAST:
{json.dumps(weather, indent=2, default=str)}

Generate a complete {prefs.num_days}-day itinerary with realistic local pricing.
Each day must have day_number (starting from 1), date, 3 slots (morning/afternoon/evening), and day_summary.
Include a budget breakdown object."""

    def _parse_itinerary(self, raw: dict, prefs: TravelPreferences | None) -> Itinerary:
        """Parse Gemini JSON response into a validated Itinerary model."""
        days = []
        for day_raw in raw.get("days", []):
            slots = []
            for slot_raw in day_raw.get("slots", []):
                # Parse alternatives (no nesting)
                alt_list = []
                for alt in slot_raw.pop("alternatives", []):
                    alt.pop("alternatives", None)  # No nested alternatives
                    try:
                        alt_list.append(ActivitySlot(**alt))
                    except Exception:
                        pass  # Skip malformed alternatives

                # Clean slot data
                slot_raw.pop("alternatives", None)
                try:
                    slot = ActivitySlot(**slot_raw, alternatives=alt_list[:2])
                    slots.append(slot)
                except Exception as e:
                    logger.warning("Skipping malformed slot: %s", e)

            if not slots:
                continue

            try:
                day = ItineraryDay(
                    day_number=day_raw.get("day_number", len(days) + 1),
                    date=day_raw.get("date", "2026-01-01"),
                    slots=slots,
                    day_summary=day_raw.get("day_summary", ""),
                    day_budget=sum(s.estimated_cost for s in slots),
                )
                days.append(day)
            except Exception as e:
                logger.warning("Skipping malformed day: %s", e)

        budget_raw = raw.get("budget", {})
        total = prefs.budget_amount if prefs else budget_raw.get("total_budget", 0)
        spent = sum(d.day_budget for d in days)

        budget = BudgetBreakdown(
            total_budget=total,
            spent=spent,
            accommodation=budget_raw.get("accommodation", 0),
            transport=budget_raw.get("transport", 0),
            food=budget_raw.get("food", 0),
            activities=budget_raw.get("activities", 0),
            remaining=max(0, total - spent),
        )

        return Itinerary(
            id=str(uuid4()),
            destination=prefs.destination if prefs else raw.get("destination", "Unknown"),
            days=days,
            budget=budget,
            preferences_summary=raw.get("preferences_summary", ""),
        )

    def _mock_itinerary(self, prefs: TravelPreferences) -> Itinerary:
        """Generate a mock itinerary for development/testing."""
        days = []
        daily_budget = prefs.budget_amount / max(prefs.num_days, 1)

        for i in range(prefs.num_days):
            day_date = prefs.start_date + timedelta(days=i)
            slots = [
                ActivitySlot(
                    time_slot=TimeSlot.morning,
                    activity_name=f"Morning activity in {prefs.destination}",
                    description=f"Explore {prefs.destination} in the morning. A great way to start the day.",
                    duration_minutes=180,
                    estimated_cost=round(daily_budget * 0.3, 2),
                    category="activity",
                    weather_sensitive=True,
                    alternatives=[
                        ActivitySlot(
                            time_slot=TimeSlot.morning,
                            activity_name=f"Alternative morning in {prefs.destination}",
                            description="An alternative morning activity.",
                            duration_minutes=120,
                            estimated_cost=round(daily_budget * 0.2, 2),
                            category="activity",
                        )
                    ],
                ),
                ActivitySlot(
                    time_slot=TimeSlot.afternoon,
                    activity_name=f"Lunch & afternoon in {prefs.destination}",
                    description=f"Enjoy local cuisine and explore the afternoon scene in {prefs.destination}.",
                    duration_minutes=240,
                    estimated_cost=round(daily_budget * 0.4, 2),
                    category="food",
                    weather_sensitive=False,
                ),
                ActivitySlot(
                    time_slot=TimeSlot.evening,
                    activity_name=f"Evening in {prefs.destination}",
                    description=f"Wind down with an evening experience in {prefs.destination}.",
                    duration_minutes=180,
                    estimated_cost=round(daily_budget * 0.3, 2),
                    category="activity",
                    weather_sensitive=False,
                ),
            ]
            day_cost = sum(s.estimated_cost for s in slots)
            days.append(
                ItineraryDay(
                    day_number=i + 1,
                    date=day_date,
                    slots=slots,
                    day_summary=f"Day {i + 1} exploring {prefs.destination}",
                    day_budget=day_cost,
                )
            )

        total_spent = sum(d.day_budget for d in days)
        budget = BudgetBreakdown(
            total_budget=prefs.budget_amount,
            spent=total_spent,
            accommodation=round(total_spent * 0.35, 2),
            transport=round(total_spent * 0.15, 2),
            food=round(total_spent * 0.30, 2),
            activities=round(total_spent * 0.20, 2),
            remaining=round(prefs.budget_amount - total_spent, 2),
        )

        return Itinerary(
            id=str(uuid4()),
            destination=prefs.destination,
            days=days,
            budget=budget,
            preferences_summary=f"{prefs.num_days}-day {prefs.travel_style.value} trip to {prefs.destination}",
        )
