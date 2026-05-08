"""Calendar export service — generates .ics files from itineraries."""
from icalendar import Calendar, Event
from datetime import datetime, timedelta
from app.models.itinerary import Itinerary


class CalendarService:
    """Generate .ics calendar files from itineraries."""

    SLOT_HOURS = {"morning": 9, "afternoon": 13, "evening": 18}

    def generate_ics(self, itinerary: Itinerary) -> bytes:
        """Generate .ics file content from an itinerary."""
        cal = Calendar()
        cal.add("prodid", "-//Travel Planning Engine//EN")
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

    def _slot_to_datetime(self, day_date, time_slot_value: str) -> datetime:
        """Convert a day date and time slot to a datetime."""
        hour = self.SLOT_HOURS.get(time_slot_value, 9)
        return datetime.combine(
            day_date, datetime.min.time().replace(hour=hour)
        )

    def _build_description(self, slot) -> str:
        """Build a rich event description from slot data."""
        parts = [slot.description]
        if slot.estimated_cost > 0:
            parts.append(f"Estimated cost: ${slot.estimated_cost:.2f}")
        if slot.accessibility_notes:
            parts.append(f"Accessibility: {slot.accessibility_notes}")
        return "\n".join(parts)
