from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    gemini_api_key: str = ""
    google_maps_api_key: str = ""
    google_cloud_project: str = ""
    environment: str = "development"
    port: int = 8080

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
