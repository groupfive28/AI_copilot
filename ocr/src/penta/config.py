from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).resolve().parent.parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="penta_", env_file=_ENV_FILE, extra="ignore")

    @model_validator(mode="before")
    @classmethod
    def _strip_quotes(cls, data: Any) -> Any:
        """pydantic-settings' own .env parser strips a "quoted value", but
        Docker's --env-file (and a plain shell `export`) doesn't — the quotes
        become part of the string. Strip one matching pair defensively so
        this works the same regardless of how it's launched."""
        if not isinstance(data, dict):
            return data
        for key, value in data.items():
            if isinstance(value, str) and len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                data[key] = value[1:-1]
        return data

    gcp_project_id: str = ""
    gcp_location: str = "us"  # "us" or "eu"

    # Default/fallback processor — used for any document_type not present in
    # document_processors below (or when a request omits document_type).
    # Typically a plain Document OCR processor.
    gcp_processor_id: str = ""

    # Per-document-category processor routing
    document_processors: dict[str, str] = {}

    storage_bucket: str = ""

    poll_interval_seconds: int = 15

    extract_api_key: str = ""

    min_entity_confidence: float = 0.5

    supabase_url: str = ""  # e.g. https://<project-ref>.supabase.co
    supabase_secret_key: str = ""
    supabase_schema: str = "penta_application"


settings = Settings()
