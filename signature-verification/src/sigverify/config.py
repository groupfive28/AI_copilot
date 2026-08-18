from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="sigverify_", env_file=".env", extra="ignore", protected_namespaces=("settings_",)
    )

    # Same ADC-based credential story as faceverify/config.py - see that
    # module's docstring and ../face-verification/.env for the full
    # explanation. No GOOGLE_APPLICATION_CREDENTIALS needed locally.
    gcp_project_id: str = ""
    storage_bucket: str = ""

    # Direct Postgres, not the Supabase client - same reasoning as
    # faceverify/config.py.
    database_url: str = ""

    extract_api_key: str = ""

    # Where the pretrained SigNet weights live locally. Downloaded lazily on
    # first use (see model.py) rather than shipped in the repo - 63MB is too
    # large to comfortably commit, and this mirrors how insightface caches
    # its own model files outside the repo.
    model_path: str = "models/signet.pth"


settings = Settings()
