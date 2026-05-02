---
phase: 12-chat-ux-context-window-indicator-interleaved-history
plan: 02
status: complete
requirements: [CTX-03]
tests_added: 5
tests_passing: 5
---

# Plan 12-02 Summary: LLM_CONTEXT_WINDOW + Public Settings Endpoint

## What Was Built

1. **Pydantic Settings field**: Added `llm_context_window: int = 128_000` to `Settings` in `backend/app/config.py`. Reads `LLM_CONTEXT_WINDOW` env var; default sized to GPT-4o.

2. **New no-auth router**: Created `backend/app/routers/settings.py` exposing `GET /settings/public` with NO `Depends(get_current_user)`. Returns `{"context_window": <int>}` from `get_settings().llm_context_window`.

3. **Mounted in main.py**: Added `from app.routers import settings as public_settings_router` import, and `app.include_router(public_settings_router.router)` mount line. No double-prefix (router defines its own `/settings` prefix).

4. **API tests**: Created `backend/tests/api/test_public_settings.py` with 5 tests using FastAPI TestClient (in-process, no live backend needed):
   - No-auth call returns 200
   - Response shape validates as `{"context_window": int}`
   - Value matches `Settings.llm_context_window`
   - No-double-prefix check (404 on `/settings/settings/public`)
   - Default 128_000 when env unset

## Key Decisions Honored

- **D-P12-04**: Endpoint reads from `app.config.settings.llm_context_window` (env-var driven), NOT from system_settings table.
- **D-P12-05**: First public no-auth endpoint in backend. Security comment in router file reinforces "any future field MUST be non-sensitive."
- **D-P12-06**: CTX-03 success criterion #5 — env var change on Railway updates frontend bar denominator without frontend redeploy.

## Files Changed

- `backend/app/config.py` — added `llm_context_window` field with comment block (~6 lines)
- `backend/app/routers/settings.py` — NEW (~30 lines)
- `backend/app/main.py` — added 2 lines (import + mount)
- `backend/tests/api/test_public_settings.py` — NEW; 5 tests

## Verification

```
pytest tests/api/test_public_settings.py -v   → 5 passed
python -c "from app.main import app; print(get_settings().llm_context_window)"  → 128000
```

## Self-Check: PASSED

All 5 must_haves truths satisfied:
- llm_context_window field on Settings (default 128_000)
- GET /settings/public no auth, returns dict
- Endpoint reads from app.config.settings (not system_settings)
- Router mounted in main.py
- Env-var-driven (no frontend redeploy needed for changes)
