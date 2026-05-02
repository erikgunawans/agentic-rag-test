"""Public (no-auth) settings router — Phase 12 / CTX-03 / D-P12-04..06.

Exposes deployment-time configuration that the frontend needs to render the
context-window indicator. Source of truth: app.config.settings (env-var driven).

Why NOT system_settings? Per D-P12-04, the context window is deployment-time
config (changes only on Railway redeploy), not admin-tunable runtime state. We
explicitly want the "change LLM_CONTEXT_WINDOW env var without a frontend
redeploy" workflow (CTX-03 success criterion #5) — DB writes would force an
admin-UI surface for negligible benefit.

SECURITY NOTE (T-12-02-1): This is the ONLY no-auth router in the backend.
Any future field added to GET /settings/public MUST be non-sensitive — anything
role-gated belongs in admin_settings.py.
"""
from fastapi import APIRouter

from app.config import get_settings

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/public")
async def get_public_settings() -> dict:
    """Return non-sensitive deployment configuration the frontend needs.

    No auth required (D-P12-05). Future fields added here MUST remain
    non-sensitive — anything role-gated belongs in admin_settings.py.

    Currently returns:
        - context_window: total token capacity of the configured LLM, used
          as the denominator in the chat input's context-window indicator.
        - deep_mode_enabled: Phase 17 / DEEP-03 feature flag. When False, the
          Deep Mode toggle is hidden in the UI and the endpoint rejects
          deep_mode=true payloads (server-side gate in Plan 17-04).
    """
    settings = get_settings()
    return {
        "context_window": settings.llm_context_window,
        "deep_mode_enabled": settings.deep_mode_enabled,
    }
