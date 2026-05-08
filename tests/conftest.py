"""Shared test fixtures for the Travel Planning Engine.

Provides:
- ``anyio_backend`` — locks the async backend to asyncio.
- ``client`` — async HTTP client for endpoint testing.
- Rate limiter bypass for test environments.
"""

import os

# Set high rate limit for tests BEFORE importing the app
os.environ.setdefault("RATE_LIMIT_PER_MINUTE", "1000")

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
def anyio_backend():
    """Use asyncio as the async backend for all tests."""
    return "asyncio"


@pytest.fixture
async def client():
    """Async HTTP client for testing FastAPI endpoints.

    Uses ``httpx.ASGITransport`` for in-process testing without
    a real network connection.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
