"""Tests for persistence layer — in-memory storage."""
from datetime import date

import pytest

from app.models.itinerary import ActivitySlot, BudgetBreakdown, Itinerary, ItineraryDay, TimeSlot
from app.services.firestore import FirestoreService


@pytest.fixture(autouse=True)
def clear_store():
    """Clear in-memory store before each test."""
    FirestoreService.clear_memory_store()
    yield
    FirestoreService.clear_memory_store()


def _make_itinerary(itinerary_id: str = "test-1") -> Itinerary:
    slot = ActivitySlot(
        time_slot=TimeSlot.morning,
        activity_name="Test Activity",
        description="A test",
        duration_minutes=60,
        estimated_cost=10.0,
        category="activity",
    )
    day = ItineraryDay(day_number=1, date=date(2026, 6, 1), slots=[slot], day_budget=10.0)
    budget = BudgetBreakdown(total_budget=100, spent=10, remaining=90)
    return Itinerary(id=itinerary_id, destination="Test City", days=[day], budget=budget)


class TestFirestoreService:
    """Test in-memory storage (development mode)."""

    @pytest.mark.asyncio
    async def test_save_and_get(self):
        service = FirestoreService()
        itinerary = _make_itinerary()
        await service.save_itinerary(itinerary)
        loaded = await service.get_itinerary("test-1")
        assert loaded is not None
        assert loaded.id == "test-1"
        assert loaded.destination == "Test City"

    @pytest.mark.asyncio
    async def test_get_nonexistent(self):
        service = FirestoreService()
        result = await service.get_itinerary("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_update(self):
        service = FirestoreService()
        itinerary = _make_itinerary()
        await service.save_itinerary(itinerary)
        itinerary.destination = "Updated City"
        await service.update_itinerary(itinerary)
        loaded = await service.get_itinerary("test-1")
        assert loaded.destination == "Updated City"

    @pytest.mark.asyncio
    async def test_multiple_itineraries(self):
        service = FirestoreService()
        await service.save_itinerary(_make_itinerary("a"))
        await service.save_itinerary(_make_itinerary("b"))
        a = await service.get_itinerary("a")
        b = await service.get_itinerary("b")
        assert a is not None
        assert b is not None
        assert a.id != b.id

    @pytest.mark.asyncio
    async def test_clear_memory_store(self):
        service = FirestoreService()
        await service.save_itinerary(_make_itinerary())
        FirestoreService.clear_memory_store()
        result = await service.get_itinerary("test-1")
        assert result is None
