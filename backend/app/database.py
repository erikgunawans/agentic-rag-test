from supabase import create_client, Client
from app.config import get_settings


def get_supabase_client() -> Client:
    """Service-role client — bypasses RLS for admin operations."""
    settings = get_settings()
    return create_client(settings.supabase_url, settings.supabase_service_role_key)


def get_supabase_authed_client(token: str) -> Client:
    """Anon client with user JWT — queries are scoped by RLS."""
    settings = get_settings()
    client = create_client(settings.supabase_url, settings.supabase_anon_key)
    client.auth.set_session(token, "")
    return client
