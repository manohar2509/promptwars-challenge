"""Calendar export service — generates .ics files from itineraries.

Produces RFC 5545-compliant iCalendar files that can be imported into
Google Calendar, Apple Calendar, Outlook, and other standards-compliant
calendar applications.
"""

from datetime import datetime, timedelta
from typing import Any

from icalendar import Calendar, Event

from app.models.itinerary import ActivitySlot, Itinerary


class CalendarService:
    """Generate .ics calendar files from itineraries.

    Slot start times are mapped from the symbolic time slot names
    (morning, afternoon, evening) to fixed local hours.
    """

    SLOT_HOURS: dict[str, int] = {"morning": 9, "afternoon": 13, "evening": 18}

    def generate_ics(self, itinerary: Itinerary) -> bytes:
        """Generate .ics file content from an itinerary.

        Args:
            itinerary: The itinerary to export.

        Returns:
            Raw bytes of the iCalendar file.
        """
        cal = Calendar()
        cal.add("prodid", "-//TravelAI Planning Engine//EN")
        cal.add("version", "2.0")
        cal.add("calscale", "GREGORIAN")
        cal.add("x-wr-calname", f"Trip to {itinerary.destination}")

        for day in itinerary.days:
            for slot in day.slots:
                event = Event()
                event.add("summary", slot.activity_name)
                event.add("description", self._build_description(slot))

                start_time = self._slot_to_datetime(day.date, slot.time_slot.value)
                event.add("dtstart", start_time)
                event.add("dtend", start_time + timedelta(minutes=slot.duration_minutes))

                if slot.location:
                    event.add("location", slot.location.get("address", ""))

                event.add("categories", [slot.category])
                cal.add_component(event)

        return cal.to_ical()

    def _slot_to_datetime(self, day_date: Any, time_slot_value: str) -> datetime:
        """Convert a day date and time slot to a datetime.

        Args:
            day_date: The calendar date of the day.
            time_slot_value: One of ``morning``, ``afternoon``, ``evening``.

        Returns:
            A ``datetime`` at the corresponding local hour.
        """
        hour = self.SLOT_HOURS.get(time_slot_value, 9)
        return datetime.combine(
            day_date, datetime.min.time().replace(hour=hour)
        )

    @staticmethod
    def _build_description(slot: ActivitySlot) -> str:
        """Build a rich event description from slot data.

        Args:
            slot: The activity slot to describe.

        Returns:
            Multi-line description string.
        """
        parts = [slot.description]
        if slot.estimated_cost > 0:
            parts.append(f"Estimated cost: ${slot.estimated_cost:.2f}")
        if slot.accessibility_notes:
            parts.append(f"Accessibility: {slot.accessibility_notes}")
        return "\n".join(parts)
