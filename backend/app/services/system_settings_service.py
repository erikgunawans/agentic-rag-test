import time
from app.database import get_supabase_client

_cache: dict | None = None
_cache_ts: float = 0.0
_TTL = 60  # seconds


def get_system_settings() -> dict:
    """Read the single system_settings row. Cached for 60s."""
    global _cache, _cache_ts
    now = time.time()
    if _cache is not None and (now - _cache_ts) < _TTL:
        return _cache

    client = get_supabase_client()  # service-role bypasses RLS
    result = client.table("system_settings").select("*").eq("id", 1).single().execute()
    _cache = result.data
    _cache_ts = now
    return _cache


def update_system_settings(data: dict) -> dict:
    """Update system_settings and clear cache."""
    global _cache, _cache_ts
    client = get_supabase_client()
    result = (
        client.table("system_settings")
        .update(data)
        .eq("id", 1)
        .execute()
    )
    _cache = None
    _cache_ts = 0.0
    return result.data[0] if result.data else {}
