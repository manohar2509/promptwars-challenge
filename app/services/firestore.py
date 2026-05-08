"""Persistence layer — Firestore for production, in-memory for development.

The ``FirestoreService`` transparently switches between Google Cloud
Firestore (production) and a process-local dictionary (development)
so the rest of the application never needs to know which backend is active.
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import ClassVar

from app.config import settings
from app.models.itinerary import Itinerary

logger = logging.getLogger(__name__)


class FirestoreService:
    """Save and load itineraries with automatic backend selection.

    In **production** (``ENVIRONMENT=production``), uses Google Cloud
    Firestore with a 7-day TTL on documents. In **development**, falls
    back to an in-memory dictionary that persists for the process lifetime.

    The class-level ``_memory_store`` is shared across all instances so
    data is consistent regardless of where the service is instantiated.
    """

    _memory_store: ClassVar[dict[str, dict]] = {}

    def __init__(self) -> None:
        self.db = None
        if settings.is_production and settings.google_cloud_project:
            try:
                from google.cloud import firestore

                self.db = firestore.AsyncClient(
                    project=settings.google_cloud_project,
                )
                logger.info("Firestore client initialised for project %s", settings.google_cloud_project)
            except Exception as exc:
                logger.warning("Firestore unavailable, using in-memory: %s", exc)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def save_itinerary(self, itinerary: Itinerary) -> str:
        """Persist an itinerary to storage.

        Args:
            itinerary: The itinerary model to save.

        Returns:
            The itinerary ID.
        """
        if self.db is None:
            return self._memory_save(itinerary)

        doc_ref = self.db.collection("itineraries").document(itinerary.id)
        data = itinerary.model_dump(mode="json")
        data["expires_at"] = (
            datetime.now(UTC) + timedelta(days=7)
        ).isoformat()
        await doc_ref.set(data)
        return itinerary.id

    async def get_itinerary(self, itinerary_id: str) -> Itinerary | None:
        """Load an itinerary from storage.

        Args:
            itinerary_id: UUID string of the itinerary.

        Returns:
            The itinerary model, or ``None`` if not found.
        """
        if self.db is None:
            return self._memory_get(itinerary_id)

        doc = await self.db.collection("itineraries").document(itinerary_id).get()
        if doc.exists:
            data = doc.to_dict()
            data.pop("expires_at", None)
            return Itinerary.model_validate(data)
        return None

    async def update_itinerary(self, itinerary: Itinerary) -> None:
        """Update an existing itinerary (sets ``updated_at`` to now).

        Args:
            itinerary: The updated itinerary model.
        """
        itinerary.updated_at = datetime.now(UTC)
        await self.save_itinerary(itinerary)

    # ------------------------------------------------------------------
    # In-memory backend (development / testing)
    # ------------------------------------------------------------------

    def _memory_save(self, itinerary: Itinerary) -> str:
        """Save to in-memory store (development only)."""
        FirestoreService._memory_store[itinerary.id] = itinerary.model_dump(mode="json")
        logger.debug("Saved itinerary %s to memory", itinerary.id)
        return itinerary.id

    def _memory_get(self, itinerary_id: str) -> Itinerary | None:
        """Load from in-memory store (development only)."""
        data = FirestoreService._memory_store.get(itinerary_id)
        if data:
            return Itinerary.model_validate(data)
        return None

    @classmethod
    def clear_memory_store(cls) -> None:
        """Clear in-memory store (for testing)."""
        cls._memory_store.clear()
