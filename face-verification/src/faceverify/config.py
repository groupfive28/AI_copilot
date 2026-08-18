from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="faceverify_", env_file=".env", extra="ignore")

    # Same credential shape as ocr/ (google-cloud-storage + a GCP service
    # account, via GOOGLE_APPLICATION_CREDENTIALS) rather than
    # firebase-admin - a Firebase Storage bucket is a regular GCS bucket
    # underneath, so the same service account (or one scoped the same way)
    # that unblocks the OCR service can unblock this one too, instead of
    # asking for a third distinct credential type.
    gcp_project_id: str = ""
    storage_bucket: str = ""

    # Direct Postgres, not the Supabase client - see
    # backend/app/onboarding/service.py's receive_wizard_application for
    # why: penta_application isn't exposed for writes the way this needs,
    # and this way there's one fewer credential/schema-exposure dependency.
    database_url: str = ""

    extract_api_key: str = ""


settings = Settings()
