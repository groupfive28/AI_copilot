from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Anchored to this file's location (src/penta/config.py -> project root),
# not the current working directory. pydantic-settings resolves a relative
# env_file against the process's cwd at launch time, which silently finds
# nothing (falling back to blank defaults for everything, no error) if the
# server is ever started from somewhere other than this exact directory —
# e.g. an activated venv in a shell that later cd'd elsewhere. That produced
# a real outage: storage_bucket came through as "", and the empty-string
# Cloud Storage bucket name blew up deep inside the client library with a
# confusing IndexError rather than a clear "config missing" message.
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

    # Below this, a type-specific processor returning no/low-confidence
    # entities is treated as a likely wrong-document-type upload (e.g. a
    # utility bill submitted where a passport was expected) rather than a
    # trustworthy extraction — see penta.ingest.
    min_entity_confidence: float = 0.5

    # Supabase persistence for extracted results (see penta.db). Talks to
    # Supabase's REST API (PostgREST) over HTTPS with the secret
    # (service_role) key — no direct Postgres connection, so no database
    # password needed. The secret key bypasses Row Level Security entirely;
    # it must only ever live server-side, never in client/frontend code.
    #
    # applications/extracted_fields/verification_results/audit_log live in
    # a non-default Postgres schema, not "public" — it must be added to
    # Data API -> Exposed schemas in the Supabase dashboard, or every
    # request 404s with PGRST205 regardless of how correct the code is.
    supabase_url: str = ""  # e.g. https://<project-ref>.supabase.co
    supabase_secret_key: str = ""
    supabase_schema: str = "penta_application"


settings = Settings()
