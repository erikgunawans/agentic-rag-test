"""
User Settings API tests.
Covers: SET-01 through SET-06
"""
import pytest


class TestSettingsGet:
    """SET-01: GET /settings returns defaults on first access."""

    def test_get_returns_200(self, authed_client):
        resp = authed_client.get("/settings")
        assert resp.status_code == 200

    def test_get_returns_required_fields(self, authed_client):
        body = authed_client.get("/settings").json()
        assert "llm_model" in body
        assert "embedding_model" in body
        assert "embedding_locked" in body

    def test_get_embedding_locked_is_bool(self, authed_client):
        body = authed_client.get("/settings").json()
        assert isinstance(body["embedding_locked"], bool)

    def test_get_without_auth_returns_401(self, client):
        resp = client.get("/settings")
        assert resp.status_code in (401, 403)


class TestSettingsPatch:
    """SET-02/04/05: PATCH /settings validation."""

    def test_update_llm_model(self, authed_client):
        """SET-02: LLM model change persists."""
        resp = authed_client.patch("/settings", json={"llm_model": "anthropic/claude-3-haiku"})
        assert resp.status_code == 200
        # Verify persisted
        body = authed_client.get("/settings").json()
        assert body["llm_model"] == "anthropic/claude-3-haiku"
        # Restore default
        authed_client.patch("/settings", json={"llm_model": "openai/gpt-4o-mini"})

    def test_invalid_embedding_model_returns_400(self, authed_client):
        """SET-04: Disallowed embedding model."""
        resp = authed_client.patch("/settings", json={"embedding_model": "text-embedding-3-large"})
        assert resp.status_code == 400

    def test_empty_llm_model_returns_400(self, authed_client):
        """SET-05: Empty llm_model string."""
        resp = authed_client.patch("/settings", json={"llm_model": ""})
        assert resp.status_code == 400

    def test_no_fields_returns_400(self, authed_client):
        resp = authed_client.patch("/settings", json={})
        assert resp.status_code == 400

    def test_patch_without_auth_returns_401(self, client):
        resp = client.patch("/settings", json={"llm_model": "anthropic/claude-3-haiku"})
        assert resp.status_code in (401, 403)
