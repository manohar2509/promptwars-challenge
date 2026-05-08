"""Persistence layer — Firestore for production, in-memory for development."""
import logging
from datetime import datetime, timedelta, timezone
from app.models.itinerary import Itinerary
from app.config import settings

logger = logging.getLogger(__name__)


class FirestoreService:
    """Save and load itineraries. Uses in-memory storage in development."""

    _memory_store: dict = {}

    def __init__(self):
        self.db = None
        if settings.environment == "production" and settings.google_cloud_project:
            try:
                from google.cloud import firestore
                self.db = firestore.AsyncClient(
                    project=settings.google_cloud_project
                )
                logger.info("Firestore client initialized")
            except Exception as e:
                logger.warning("Firestore unavailable, using in-memory: %s", e)

    async def save_itinerary(self, itinerary: Itinerary) -> str:
        """Save an itinerary to storage."""
        if self.db is None:
            return self._memory_save(itinerary)

        doc_ref = self.db.collection("itineraries").document(itinerary.id)
        data = itinerary.model_dump(mode="json")
        data["expires_at"] = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        await doc_ref.set(data)
        return itinerary.id

    async def get_itinerary(self, itinerary_id: str) -> Itinerary | None:
        """Load an itinerary from storage."""
        if self.db is None:
            return self._memory_get(itinerary_id)

        doc = await self.db.collection("itineraries").document(itinerary_id).get()
        if doc.exists:
            data = doc.to_dict()
            data.pop("expires_at", None)
            return Itinerary.model_validate(data)
        return None

    async def update_itinerary(self, itinerary: Itinerary) -> None:
        """Update an existing itinerary."""
        itinerary.updated_at = datetime.now(timezone.utc)
        await self.save_itinerary(itinerary)

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
    def clear_memory_store(cls):
        """Clear in-memory store (for testing)."""
        cls._memory_store.clear()
