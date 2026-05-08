"""Application settings loaded from environment variables.

Uses Pydantic Settings for type-safe configuration with automatic
environment variable binding. Supports optional Google Cloud Secret
Manager for production deployments.
"""

import logging
from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    Attributes:
        gemini_api_key: Google Gemini API key for AI planning.
        google_maps_api_key: Google Maps Platform API key.
        google_cloud_project: GCP project ID for Firestore and Cloud Run.
        environment: Runtime environment (development | production).
        port: HTTP server port.
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR).
        max_request_body_bytes: Maximum allowed request body size.
        rate_limit_per_minute: Maximum API requests per IP per minute.
    """

    gemini_api_key: str = ""
    google_maps_api_key: str = ""
    google_cloud_project: str = ""
    environment: str = "development"
    port: int = Field(default=8080, ge=1, le=65535)
    log_level: str = Field(default="INFO", pattern=r"^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")
    max_request_body_bytes: int = Field(default=1_048_576, ge=1024)  # 1 MiB
    rate_limit_per_minute: int = Field(default=30, ge=1, le=1000)

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    @field_validator("gemini_api_key", "google_maps_api_key")
    @classmethod
    def warn_empty_keys(cls, v: str, info) -> str:
        """Log a warning if API keys are empty (expected in development)."""
        if not v:
            logger.warning("Config: %s is empty — feature will use fallback", info.field_name)
        return v

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment == "production"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached singleton Settings instance.

    Using ``lru_cache`` ensures the ``.env`` file is only read once and
    the same ``Settings`` object is reused across the application.
    """
    return Settings()


# Module-level convenience alias (backwards-compatible).
settings = get_settings()
