"""Service modules for external API integrations and business logic.

Services:
- ``planner``: AI itinerary generation using Google Gemini.
- ``google_maps``: Places, Geocoding, and Distance Matrix via Google Maps Platform.
- ``weather``: Open-Meteo weather forecast integration.
- ``constraints``: Budget and schedule validation engine.
- ``firestore``: Persistence layer (Firestore in production, in-memory for dev).
- ``google_calendar``: iCalendar (.ics) export for Google Calendar.
"""

__all__ = [
    "planner",
    "google_maps",
    "weather",
    "constraints",
    "firestore",
    "google_calendar",
]
