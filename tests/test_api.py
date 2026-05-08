"""Tests for API endpoints."""
import pytest
from datetime import date, timedelta
from app.services.firestore import FirestoreService
from app.services.planner import PlannerService
from app.models.preferences import TravelPreferences


@pytest.fixture(autouse=True)
def clear_store():
    FirestoreService.clear_memory_store()
    yield
    FirestoreService.clear_memory_store()


def _valid_prefs_dict():
    return {
        "destination": "Paris",
        "start_date": (date.today() + timedelta(days=7)).isoformat(),
        "end_date": (date.today() + timedelta(days=10)).isoformat(),
        "budget_amount": 1500.0,
        "budget_currency": "USD",
        "interests": ["culture", "food"],
        "travel_style": "solo",
        "group_size": 1,
    }


async def _seed_itinerary():
    """Create and store a mock itinerary, return its ID."""
    prefs = TravelPreferences(**{
        "destination": "Paris",
        "start_date": date.today() + timedelta(days=7),
        "end_date": date.today() + timedelta(days=10),
        "budget_amount": 1500.0,
        "interests": ["culture", "food"],
        "travel_style": "solo",
    })
    planner = PlannerService()
    itinerary = planner._mock_itinerary(prefs)
    storage = FirestoreService()
    await storage.save_itinerary(itinerary)
    return itinerary.id


class TestHealthEndpoint:
    @pytest.mark.asyncio
    async def test_health(self, client):
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"


class TestCreatePlan:
    @pytest.mark.asyncio
    async def test_create_plan_json(self, client):
        """Test plan creation returns JSON."""
        response = await client.post("/api/plan", json=_valid_prefs_dict())
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data["destination"] == "Paris"
        assert len(data["days"]) == 3

    @pytest.mark.asyncio
    async def test_create_plan_htmx_redirect(self, client):
        """Test HTMX plan creation returns HX-Redirect."""
        response = await client.post(
            "/api/plan",
            json=_valid_prefs_dict(),
            headers={"HX-Request": "true"},
        )
        assert response.status_code == 204
        assert "HX-Redirect" in response.headers
        assert response.headers["HX-Redirect"].startswith("/plan/")

    @pytest.mark.asyncio
    async def test_create_plan_invalid_input(self, client):
        """Test validation error for bad input."""
        response = await client.post("/api/plan", json={"destination": ""})
        assert response.status_code == 422


class TestGetPlan:
    @pytest.mark.asyncio
    async def test_get_existing_plan(self, client):
        plan_id = await _seed_itinerary()
        response = await client.get(f"/api/plan/{plan_id}")
        assert response.status_code == 200
        assert response.json()["id"] == plan_id

    @pytest.mark.asyncio
    async def test_get_nonexistent_plan(self, client):
        response = await client.get("/api/plan/nonexistent")
        assert response.status_code == 404


class TestRefinePlan:
    @pytest.mark.asyncio
    async def test_refine_plan(self, client):
        plan_id = await _seed_itinerary()
        response = await client.post(
            f"/api/plan/{plan_id}/refine",
            json={"text": "Make day 1 more relaxed"},
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_refine_empty_message(self, client):
        plan_id = await _seed_itinerary()
        response = await client.post(
            f"/api/plan/{plan_id}/refine",
            json={"text": ""},
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_refine_nonexistent(self, client):
        response = await client.post(
            "/api/plan/fake/refine",
            json={"text": "hello"},
        )
        assert response.status_code == 404


class TestDisruptSlot:
    @pytest.mark.asyncio
    async def test_disrupt_slot(self, client):
        plan_id = await _seed_itinerary()
        response = await client.post(
            f"/api/plan/{plan_id}/disrupt",
            json={"day": 1, "slot": "morning", "reason": "closed"},
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_disrupt_missing_fields(self, client):
        plan_id = await _seed_itinerary()
        response = await client.post(
            f"/api/plan/{plan_id}/disrupt",
            json={"reason": "closed"},
        )
        assert response.status_code == 400


class TestExportCalendar:
    @pytest.mark.asyncio
    async def test_export_ics(self, client):
        plan_id = await _seed_itinerary()
        response = await client.get(f"/api/plan/{plan_id}/export")
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/calendar; charset=utf-8"
        assert b"BEGIN:VCALENDAR" in response.content

    @pytest.mark.asyncio
    async def test_export_nonexistent(self, client):
        response = await client.get("/api/plan/fake/export")
        assert response.status_code == 404
