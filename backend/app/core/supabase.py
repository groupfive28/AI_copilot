from supabase import Client, create_client

from app.core.config import settings


def get_supabase_client() -> Client:
    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise RuntimeError(
            "Supabase is not configured. Set SUPABASE_URL and "
            "SUPABASE_SERVICE_ROLE_KEY."
        )

    return create_client(
        settings.supabase_url,
        settings.supabase_service_role_key,
    )