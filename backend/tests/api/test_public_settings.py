"""API tests for GET /settings/public (Phase 12 / CTX-03).

Uses FastAPI TestClient (in-process) so the tests run without a live backend
or Supabase connection. Verifies:
- No-auth call returns 200 (D-P12-05)
- Response shape: {"context_window": int}
- Value is env-var-driven via Pydantic Settings.llm_context_window
- Endpoint mounted at exact path /settings/public (no double-prefix)
"""
from fastapi.testclient import TestClient

from app.main import app


def test_public_settings_no_auth_returns_200():
    """No Authorization header — must return 200 (D-P12-05)."""
    client = TestClient(app)
    resp = client.get("/settings/public")
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"


def test_public_settings_response_shape():
    """Body must be {\"context_window\": int}."""
    client = TestClient(app)
    resp = client.get("/settings/public")
    body = resp.json()
    assert "context_window" in body
    assert isinstance(body["context_window"], int)
    assert body["context_window"] > 0


def test_public_settings_returns_env_driven_value():
    """Default is 128_000; value must reflect Settings.llm_context_window."""
    from app.config import get_settings

    expected = get_settings().llm_context_window
    client = TestClient(app)
    resp = client.get("/settings/public")
    body = resp.json()
    assert body["context_window"] == expected
    # Smallest sane context window for any production LLM
    assert body["context_window"] >= 1024


def test_public_settings_no_double_prefix():
    """Endpoint must be at /settings/public, NOT /settings/settings/public."""
    client = TestClient(app)
    bad = client.get("/settings/settings/public")
    assert bad.status_code == 404, "Double-prefix path should not resolve"
    good = client.get("/settings/public")
    assert good.status_code == 200


def test_public_settings_value_matches_default_when_env_unset():
    """When LLM_CONTEXT_WINDOW env var is unset, value defaults to 128_000."""
    import os

    if os.environ.get("LLM_CONTEXT_WINDOW"):
        # Skip when running with explicit env override
        return
    client = TestClient(app)
    resp = client.get("/settings/public")
    assert resp.json()["context_window"] == 128_000
