"""Integration tests — full flows with mocked external APIs."""
from datetime import date, timedelta

import pytest

from app.models.preferences import TravelPreferences
from app.services.constraints import ConstraintService
from app.services.firestore import FirestoreService
from app.services.google_calendar import CalendarService
from app.services.planner import PlannerService


@pytest.fixture(autouse=True)
def clear_store():
    FirestoreService.clear_memory_store()
    yield
    FirestoreService.clear_memory_store()


def _prefs(**kw):
    defaults = {
        "destination": "Paris",
        "start_date": date.today() + timedelta(days=7),
        "end_date": date.today() + timedelta(days=10),
        "budget_amount": 1500.0,
        "interests": ["culture", "food"],
        "travel_style": "solo",
    }
    defaults.update(kw)
    return TravelPreferences(**defaults)


class TestFullPlanningFlow:
    """Test: preferences → generate → store → retrieve → export."""

    @pytest.mark.asyncio
    async def test_generate_store_retrieve(self):
        prefs = _prefs()
        planner = PlannerService()
        storage = FirestoreService()

        itinerary = await planner.generate_itinerary(prefs, [], [])
        assert itinerary.destination == "Paris"
        assert len(itinerary.days) == 3

        await storage.save_itinerary(itinerary)
        loaded = await storage.get_itinerary(itinerary.id)
        assert loaded is not None
        assert loaded.id == itinerary.id
        assert len(loaded.days) == 3

    @pytest.mark.asyncio
    async def test_generate_and_export_ics(self):
        prefs = _prefs()
        planner = PlannerService()
        calendar = CalendarService()

        itinerary = await planner.generate_itinerary(prefs, [], [])
        ics = calendar.generate_ics(itinerary)
        assert b"BEGIN:VCALENDAR" in ics
        assert b"BEGIN:VEVENT" in ics
        # Should have events for all slots
        content = ics.decode("utf-8")
        assert content.count("BEGIN:VEVENT") == len(itinerary.days) * 3

    @pytest.mark.asyncio
    async def test_generate_validate_constraints(self):
        prefs = _prefs()
        planner = PlannerService()
        constraints = ConstraintService()

        itinerary = await planner.generate_itinerary(prefs, [], [])
        result = await constraints.validate_itinerary(itinerary)
        assert result.valid is True

    @pytest.mark.asyncio
    async def test_refine_preserves_id(self):
        prefs = _prefs()
        planner = PlannerService()
        storage = FirestoreService()

        itinerary = await planner.generate_itinerary(prefs, [], [])
        original_id = itinerary.id
        await storage.save_itinerary(itinerary)

        refined = await planner.refine_itinerary(itinerary, "make it relaxed")
        assert refined.id == original_id

    @pytest.mark.asyncio
    async def test_full_api_flow_json(self, client):
        """POST /api/plan → GET /api/plan/{id} → GET /api/plan/{id}/export."""
        prefs = {
            "destination": "Tokyo",
            "start_date": (date.today() + timedelta(days=7)).isoformat(),
            "end_date": (date.today() + timedelta(days=9)).isoformat(),
            "budget_amount": 2000.0,
            "budget_currency": "USD",
            "interests": ["food", "culture"],
            "travel_style": "couple",
            "group_size": 2,
        }
        # Create
        resp = await client.post("/api/plan", json=prefs)
        assert resp.status_code == 200
        data = resp.json()
        plan_id = data["id"]
        assert data["destination"] == "Tokyo"

        # Retrieve
        resp = await client.get(f"/api/plan/{plan_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == plan_id

        # Export
        resp = await client.get(f"/api/plan/{plan_id}/export")
        assert resp.status_code == 200
        assert b"BEGIN:VCALENDAR" in resp.content

    @pytest.mark.asyncio
    async def test_refine_api_flow(self, client):
        """POST /api/plan → POST /api/plan/{id}/refine."""
        prefs = {
            "destination": "Rome",
            "start_date": (date.today() + timedelta(days=5)).isoformat(),
            "end_date": (date.today() + timedelta(days=7)).isoformat(),
            "budget_amount": 1000.0,
            "interests": ["culture"],
            "travel_style": "solo",
        }
        resp = await client.post("/api/plan", json=prefs)
        plan_id = resp.json()["id"]

        resp = await client.post(
            f"/api/plan/{plan_id}/refine",
            json={"text": "Add more food experiences"},
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_disrupt_api_flow(self, client):
        """POST /api/plan → POST /api/plan/{id}/disrupt."""
        prefs = {
            "destination": "London",
            "start_date": (date.today() + timedelta(days=5)).isoformat(),
            "end_date": (date.today() + timedelta(days=7)).isoformat(),
            "budget_amount": 1200.0,
            "interests": ["culture"],
            "travel_style": "solo",
        }
        resp = await client.post("/api/plan", json=prefs)
        plan_id = resp.json()["id"]

        resp = await client.post(
            f"/api/plan/{plan_id}/disrupt",
            json={"day": 1, "slot": "morning", "reason": "closed"},
        )
        assert resp.status_code == 200


class TestEdgeCases:
    """Edge case and error handling tests."""

    @pytest.mark.asyncio
    async def test_zero_budget_rejected(self, client):
        prefs = {
            "destination": "Paris",
            "start_date": (date.today() + timedelta(days=7)).isoformat(),
            "end_date": (date.today() + timedelta(days=10)).isoformat(),
            "budget_amount": 0,
            "interests": ["culture"],
            "travel_style": "solo",
        }
        resp = await client.post("/api/plan", json=prefs)
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_negative_budget_rejected(self, client):
        prefs = {
            "destination": "Paris",
            "start_date": (date.today() + timedelta(days=7)).isoformat(),
            "end_date": (date.today() + timedelta(days=10)).isoformat(),
            "budget_amount": -100,
            "interests": ["culture"],
            "travel_style": "solo",
        }
        resp = await client.post("/api/plan", json=prefs)
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_empty_interests_rejected(self, client):
        prefs = {
            "destination": "Paris",
            "start_date": (date.today() + timedelta(days=7)).isoformat(),
            "end_date": (date.today() + timedelta(days=10)).isoformat(),
            "budget_amount": 1000,
            "interests": [],
            "travel_style": "solo",
        }
        resp = await client.post("/api/plan", json=prefs)
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_empty_destination_rejected(self, client):
        prefs = {
            "destination": "",
            "start_date": (date.today() + timedelta(days=7)).isoformat(),
            "end_date": (date.today() + timedelta(days=10)).isoformat(),
            "budget_amount": 1000,
            "interests": ["culture"],
            "travel_style": "solo",
        }
        resp = await client.post("/api/plan", json=prefs)
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_past_start_date_rejected(self, client):
        prefs = {
            "destination": "Paris",
            "start_date": (date.today() - timedelta(days=1)).isoformat(),
            "end_date": (date.today() + timedelta(days=2)).isoformat(),
            "budget_amount": 1000,
            "interests": ["culture"],
            "travel_style": "solo",
        }
        resp = await client.post("/api/plan", json=prefs)
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_end_before_start_rejected(self, client):
        prefs = {
            "destination": "Paris",
            "start_date": (date.today() + timedelta(days=10)).isoformat(),
            "end_date": (date.today() + timedelta(days=5)).isoformat(),
            "budget_amount": 1000,
            "interests": ["culture"],
            "travel_style": "solo",
        }
        resp = await client.post("/api/plan", json=prefs)
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_invalid_currency_rejected(self, client):
        prefs = {
            "destination": "Paris",
            "start_date": (date.today() + timedelta(days=7)).isoformat(),
            "end_date": (date.today() + timedelta(days=10)).isoformat(),
            "budget_amount": 1000,
            "budget_currency": "usd",
            "interests": ["culture"],
            "travel_style": "solo",
        }
        resp = await client.post("/api/plan", json=prefs)
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_group_size_too_large_rejected(self, client):
        prefs = {
            "destination": "Paris",
            "start_date": (date.today() + timedelta(days=7)).isoformat(),
            "end_date": (date.today() + timedelta(days=10)).isoformat(),
            "budget_amount": 1000,
            "interests": ["culture"],
            "travel_style": "group",
            "group_size": 25,
        }
        resp = await client.post("/api/plan", json=prefs)
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_nonexistent_plan_404(self, client):
        resp = await client.get("/api/plan/does-not-exist")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_refine_empty_text_400(self, client):
        # Seed a plan first
        prefs = {
            "destination": "Paris",
            "start_date": (date.today() + timedelta(days=7)).isoformat(),
            "end_date": (date.today() + timedelta(days=9)).isoformat(),
            "budget_amount": 1000,
            "interests": ["culture"],
            "travel_style": "solo",
        }
        resp = await client.post("/api/plan", json=prefs)
        plan_id = resp.json()["id"]
        resp = await client.post(f"/api/plan/{plan_id}/refine", json={"text": ""})
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_refine_too_long_text_400(self, client):
        prefs = {
            "destination": "Paris",
            "start_date": (date.today() + timedelta(days=7)).isoformat(),
            "end_date": (date.today() + timedelta(days=9)).isoformat(),
            "budget_amount": 1000,
            "interests": ["culture"],
            "travel_style": "solo",
        }
        resp = await client.post("/api/plan", json=prefs)
        plan_id = resp.json()["id"]
        resp = await client.post(
            f"/api/plan/{plan_id}/refine",
            json={"text": "x" * 1001},
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_disrupt_missing_fields_400(self, client):
        prefs = {
            "destination": "Paris",
            "start_date": (date.today() + timedelta(days=7)).isoformat(),
            "end_date": (date.today() + timedelta(days=9)).isoformat(),
            "budget_amount": 1000,
            "interests": ["culture"],
            "travel_style": "solo",
        }
        resp = await client.post("/api/plan", json=prefs)
        plan_id = resp.json()["id"]
        resp = await client.post(f"/api/plan/{plan_id}/disrupt", json={})
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_one_day_trip(self, client):
        prefs = {
            "destination": "Goa",
            "start_date": (date.today() + timedelta(days=1)).isoformat(),
            "end_date": (date.today() + timedelta(days=2)).isoformat(),
            "budget_amount": 500,
            "interests": ["relaxation"],
            "travel_style": "solo",
        }
        resp = await client.post("/api/plan", json=prefs)
        assert resp.status_code == 200
        assert len(resp.json()["days"]) == 1

    @pytest.mark.asyncio
    async def test_long_trip(self, client):
        prefs = {
            "destination": "India",
            "start_date": (date.today() + timedelta(days=1)).isoformat(),
            "end_date": (date.today() + timedelta(days=15)).isoformat(),
            "budget_amount": 5000,
            "interests": ["culture", "food", "nature"],
            "travel_style": "couple",
        }
        resp = await client.post("/api/plan", json=prefs)
        assert resp.status_code == 200
        assert len(resp.json()["days"]) == 14

    @pytest.mark.asyncio
    async def test_special_characters_destination(self, client):
        prefs = {
            "destination": "São Paulo",
            "start_date": (date.today() + timedelta(days=7)).isoformat(),
            "end_date": (date.today() + timedelta(days=9)).isoformat(),
            "budget_amount": 1000,
            "interests": ["food"],
            "travel_style": "solo",
        }
        resp = await client.post("/api/plan", json=prefs)
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_all_interests(self, client):
        prefs = {
            "destination": "Barcelona",
            "start_date": (date.today() + timedelta(days=7)).isoformat(),
            "end_date": (date.today() + timedelta(days=10)).isoformat(),
            "budget_amount": 2000,
            "interests": ["culture", "food", "adventure", "relaxation", "nightlife", "nature", "shopping"],
            "travel_style": "group",
            "group_size": 5,
        }
        resp = await client.post("/api/plan", json=prefs)
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_accessibility_options(self, client):
        prefs = {
            "destination": "Paris",
            "start_date": (date.today() + timedelta(days=7)).isoformat(),
            "end_date": (date.today() + timedelta(days=9)).isoformat(),
            "budget_amount": 1000,
            "interests": ["culture"],
            "travel_style": "solo",
            "accessibility": {
                "wheelchair_accessible": True,
                "elevator_required": True,
                "dietary_restrictions": ["vegan", "gluten-free"],
                "mobility_notes": "Uses motorized wheelchair",
            },
        }
        resp = await client.post("/api/plan", json=prefs)
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_health_endpoint(self, client):
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
        assert resp.json()["version"] == "1.0.0"
