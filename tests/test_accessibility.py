"""Tests for accessibility features — ARIA attributes, semantic HTML, keyboard nav.

These tests verify that the HTML output follows WCAG 2.1 AA guidelines
including proper ARIA roles, labels, and landmark elements.
"""

from datetime import date, timedelta

import pytest

from app.models.preferences import TravelPreferences
from app.services.firestore import FirestoreService
from app.services.planner import PlannerService


@pytest.fixture(autouse=True)
def clear_store():
    """Clear in-memory store before each test."""
    FirestoreService.clear_memory_store()
    yield
    FirestoreService.clear_memory_store()


class TestHomepageAccessibility:
    """Test accessibility attributes on the homepage."""

    @pytest.mark.asyncio
    async def test_has_lang_attribute(self, client):
        """HTML element should have lang='en'."""
        resp = await client.get("/")
        assert resp.status_code == 200
        assert 'lang="en"' in resp.text

    @pytest.mark.asyncio
    async def test_has_skip_link(self, client):
        """Page should have a skip-to-content link."""
        resp = await client.get("/")
        assert "skip-link" in resp.text
        assert "#main-content" in resp.text

    @pytest.mark.asyncio
    async def test_has_main_landmark(self, client):
        """Page should have a <main> element with role='main'."""
        resp = await client.get("/")
        assert 'role="main"' in resp.text
        assert 'id="main-content"' in resp.text

    @pytest.mark.asyncio
    async def test_has_nav_landmark(self, client):
        """Page should have a <nav> element with role='navigation'."""
        resp = await client.get("/")
        assert 'role="navigation"' in resp.text
        assert 'aria-label="Main navigation"' in resp.text

    @pytest.mark.asyncio
    async def test_has_footer_landmark(self, client):
        """Page should have a <footer> with role='contentinfo'."""
        resp = await client.get("/")
        assert 'role="contentinfo"' in resp.text

    @pytest.mark.asyncio
    async def test_form_labels_present(self, client):
        """All form inputs should have associated labels."""
        resp = await client.get("/")
        html = resp.text
        assert 'for="destination"' in html
        assert 'for="start_date"' in html
        assert 'for="end_date"' in html
        assert 'for="budget_amount"' in html
        assert 'for="budget_currency"' in html

    @pytest.mark.asyncio
    async def test_required_fields_marked(self, client):
        """Required fields should have visual and semantic indicators."""
        resp = await client.get("/")
        html = resp.text
        assert 'required' in html
        assert 'aria-hidden="true"' in html  # Decorative asterisks

    @pytest.mark.asyncio
    async def test_has_viewport_meta(self, client):
        """Page should have a viewport meta tag for mobile responsiveness."""
        resp = await client.get("/")
        assert "viewport" in resp.text
        assert "width=device-width" in resp.text

    @pytest.mark.asyncio
    async def test_error_area_has_aria_live(self, client):
        """Error display area should have aria-live for screen readers."""
        resp = await client.get("/")
        assert 'aria-live="polite"' in resp.text or 'aria-live="assertive"' in resp.text

    @pytest.mark.asyncio
    async def test_decorative_emojis_hidden(self, client):
        """Decorative emoji should have aria-hidden='true'."""
        resp = await client.get("/")
        assert 'aria-hidden="true"' in resp.text


class TestItineraryPageAccessibility:
    """Test accessibility on the itinerary page."""

    @pytest.mark.asyncio
    async def test_itinerary_page_has_h1(self, client):
        """Itinerary page should have a single H1."""
        prefs = TravelPreferences(
            destination="Paris",
            start_date=date.today() + timedelta(days=7),
            end_date=date.today() + timedelta(days=10),
            budget_amount=1500.0,
            interests=["culture"],
            travel_style="solo",
        )
        planner = PlannerService()
        storage = FirestoreService()
        itinerary = planner._mock_itinerary(prefs)
        await storage.save_itinerary(itinerary)

        resp = await client.get(f"/plan/{itinerary.id}")
        assert resp.status_code == 200
        assert "<h1" in resp.text

    @pytest.mark.asyncio
    async def test_day_tabs_have_aria_roles(self, client):
        """Day tabs should have proper ARIA tab roles."""
        prefs = TravelPreferences(
            destination="Tokyo",
            start_date=date.today() + timedelta(days=5),
            end_date=date.today() + timedelta(days=8),
            budget_amount=2000.0,
            interests=["food"],
            travel_style="couple",
        )
        planner = PlannerService()
        storage = FirestoreService()
        itinerary = planner._mock_itinerary(prefs)
        await storage.save_itinerary(itinerary)

        resp = await client.get(f"/plan/{itinerary.id}")
        assert resp.status_code == 200
        assert 'role="tablist"' in resp.text
        assert 'role="tab"' in resp.text
        assert 'aria-selected' in resp.text
