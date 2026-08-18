from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Document Verification API"

    database_url: str = (
        "postgresql+psycopg2://docverify:docverify@localhost:5432/docverify"
    )

    cors_origins: str = "http://localhost:5173"

    supabase_url: str = ""
    supabase_service_role_key: str = ""

    # The OCR service (ocr/) is a separate FastAPI app - not reachable at
    # all until it's deployed somewhere or run locally, and even then it
    # needs its own GCP credentials to actually start. Empty by default so
    # the post-submission pipeline can skip the call cleanly instead of
    # failing confusingly against an empty URL.
    ocr_service_url: str = ""
    ocr_extract_api_key: str = ""

    # face-verification/ - same reasoning as ocr_service_url above: empty
    # by default so the pipeline can skip it cleanly rather than fail
    # against an unset URL.
    face_verification_service_url: str = ""
    face_verification_api_key: str = ""

    # signature-verification/ - same reasoning as face_verification_service_url
    # above.
    signature_verification_service_url: str = ""
    signature_verification_api_key: str = ""

    # Gates the /api/v1/operations/* endpoints. Tokens are verified against
    # Firebase's public signing keys (no service account needed - see
    # app/core/firebase_auth.py), then the token's email is checked against
    # this allowlist. Comma-separated, case-insensitive.
    firebase_project_id: str = ""
    admin_emails: str = ""

    # Used only by the admin-initiated document re-upload feature
    # (operations/storage.py) - the backend writes directly to the same
    # Firebase Storage bucket the onboarding wizard uploads to, via ADC
    # (see ocr/.env's comment on why no service account key is needed).
    # storage_project_id is the bucket's own owning GCP project, which is a
    # different project from Document AI's - see ocr/.env for that
    # distinction; it's harmless either way since GCS access is
    # IAM-scoped, not tied to this value, but kept correct for clarity.
    storage_bucket: str = ""
    storage_project_id: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.cors_origins.split(",")
            if origin.strip()
        ]

    @property
    def admin_email_list(self) -> list[str]:
        return [
            email.strip().lower()
            for email in self.admin_emails.split(",")
            if email.strip()
        ]

settings = Settings()
