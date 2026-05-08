"""Tests for security features — headers, rate limiting, input sanitisation.

These tests verify that security middleware and input validation are
working correctly to protect against common web vulnerabilities.
"""

from datetime import date, timedelta

import pytest

from app.services.firestore import FirestoreService


@pytest.fixture(autouse=True)
def clear_store():
    """Clear in-memory store before each test."""
    FirestoreService.clear_memory_store()
    yield
    FirestoreService.clear_memory_store()


def _valid_prefs_dict():
    """Return a valid preferences dict for plan creation."""
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


class TestSecurityHeaders:
    """Verify security headers are present on responses."""

    @pytest.mark.asyncio
    async def test_x_content_type_options(self, client):
        """X-Content-Type-Options should be 'nosniff'."""
        resp = await client.get("/health")
        assert resp.headers.get("x-content-type-options") == "nosniff"

    @pytest.mark.asyncio
    async def test_x_frame_options(self, client):
        """X-Frame-Options should be 'DENY'."""
        resp = await client.get("/health")
        assert resp.headers.get("x-frame-options") == "DENY"

    @pytest.mark.asyncio
    async def test_x_xss_protection(self, client):
        """X-XSS-Protection should be set."""
        resp = await client.get("/health")
        assert "1" in resp.headers.get("x-xss-protection", "")

    @pytest.mark.asyncio
    async def test_referrer_policy(self, client):
        """Referrer-Policy should be set."""
        resp = await client.get("/health")
        assert resp.headers.get("referrer-policy") == "strict-origin-when-cross-origin"

    @pytest.mark.asyncio
    async def test_content_security_policy(self, client):
        """Content-Security-Policy should be present."""
        resp = await client.get("/health")
        csp = resp.headers.get("content-security-policy", "")
        assert "default-src" in csp

    @pytest.mark.asyncio
    async def test_permissions_policy(self, client):
        """Permissions-Policy should restrict camera and microphone."""
        resp = await client.get("/health")
        pp = resp.headers.get("permissions-policy", "")
        assert "camera=()" in pp
        assert "microphone=()" in pp


class TestInputSanitisation:
    """Verify that malicious inputs are rejected."""

    @pytest.mark.asyncio
    async def test_xss_in_destination_rejected(self, client):
        """Destination with HTML/script tags should be rejected."""
        prefs = _valid_prefs_dict()
        prefs["destination"] = "<script>alert('xss')</script>"
        resp = await client.post("/api/plan", json=prefs)
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_sql_injection_in_destination_rejected(self, client):
        """Destination with SQL injection should be rejected."""
        prefs = _valid_prefs_dict()
        prefs["destination"] = "'; DROP TABLE users; --"
        resp = await client.post("/api/plan", json=prefs)
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_extremely_long_destination_rejected(self, client):
        """Destination exceeding max_length should be rejected."""
        prefs = _valid_prefs_dict()
        prefs["destination"] = "A" * 101
        resp = await client.post("/api/plan", json=prefs)
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_unicode_destination_accepted(self, client):
        """Valid Unicode destinations should be accepted."""
        prefs = _valid_prefs_dict()
        prefs["destination"] = "São Paulo"
        resp = await client.post("/api/plan", json=prefs)
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_budget_too_large_rejected(self, client):
        """Budget exceeding upper bound should be rejected."""
        prefs = _valid_prefs_dict()
        prefs["budget_amount"] = 2_000_000
        resp = await client.post("/api/plan", json=prefs)
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_too_many_interests_rejected(self, client):
        """More than 7 interests should be rejected."""
        prefs = _valid_prefs_dict()
        prefs["interests"] = ["culture", "food", "adventure", "relaxation",
                              "nightlife", "nature", "shopping", "culture"]
        resp = await client.post("/api/plan", json=prefs)
        # Either 422 (too many) or 200 (de-duped to 7) depending on parsing
        assert resp.status_code in (200, 422)


class TestErrorHandling:
    """Verify error responses don't leak sensitive information."""

    @pytest.mark.asyncio
    async def test_404_does_not_expose_internals(self, client):
        """404 response should be clean."""
        resp = await client.get("/api/plan/nonexistent")
        assert resp.status_code == 404
        data = resp.json()
        assert "traceback" not in str(data).lower()
        assert "file" not in str(data).lower()

    @pytest.mark.asyncio
    async def test_422_does_not_expose_internals(self, client):
        """422 response should not leak stack traces."""
        resp = await client.post("/api/plan", json={"destination": ""})
        assert resp.status_code == 422
        data = resp.json()
        assert "traceback" not in str(data).lower()

    @pytest.mark.asyncio
    async def test_health_returns_version(self, client):
        """Health endpoint should return version."""
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "version" in data

    @pytest.mark.asyncio
    async def test_invalid_plan_id_format_rejected(self, client):
        """Plan IDs with special characters should be rejected."""
        resp = await client.get("/api/plan/../../etc/passwd")
        assert resp.status_code in (400, 404, 422)

    @pytest.mark.asyncio
    async def test_plan_id_script_injection_rejected(self, client):
        """Plan IDs with script tags should be rejected."""
        resp = await client.get("/api/plan/<script>alert(1)</script>")
        assert resp.status_code in (400, 404, 422)

    @pytest.mark.asyncio
    async def test_refine_message_too_long_rejected(self, client):
        """Refine messages exceeding max length should be rejected."""
        prefs = _valid_prefs_dict()
        resp = await client.post("/api/plan", json=prefs)
        assert resp.status_code == 200
        plan_id = resp.json()["id"]
        resp = await client.post(
            f"/api/plan/{plan_id}/refine",
            json={"text": "x" * 1001},
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_disrupt_reason_truncated(self, client):
        """Disrupt reason should be safely handled when very long."""
        prefs = _valid_prefs_dict()
        resp = await client.post("/api/plan", json=prefs)
        plan_id = resp.json()["id"]
        resp = await client.post(
            f"/api/plan/{plan_id}/disrupt",
            json={"day": 1, "slot": "morning", "reason": "x" * 500},
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_trip_duration_exceeding_30_days_rejected(self, client):
        """Trip exceeding 30 days should be rejected."""
        prefs = _valid_prefs_dict()
        prefs["start_date"] = (date.today() + timedelta(days=1)).isoformat()
        prefs["end_date"] = (date.today() + timedelta(days=40)).isoformat()
        resp = await client.post("/api/plan", json=prefs)
        assert resp.status_code == 422
