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

    @property
    def cors_origin_list(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.cors_origins.split(",")
            if origin.strip()
        ]

settings = Settings()
