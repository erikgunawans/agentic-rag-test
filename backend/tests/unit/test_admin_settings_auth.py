"""HTTP-level auth tests for admin settings endpoints (Phase 3/4/5 admin UI).

The Phase 3 SC#5 test (test_resolution_and_provider.py) calls
``update_system_settings()`` directly and never exercises the HTTP layer,
so a misconfigured ``require_admin`` dependency would go undetected. These
tests assert that non-admin tokens get 403 from every admin endpoint added
during the PII redaction milestone.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.dependencies import get_current_user
from app.main import app


_FAKE_TOKEN = "test-token-admin-auth"


def _override_user(role: str) -> dict:
    return {
        "id": "00000000-0000-0000-0000-test00000099",
        "email": "regular@test.com",
        "token": _FAKE_TOKEN,
        "role": role,
    }


class TestAdminSettingsRequireAdmin:
    """Every admin endpoint must reject non-super_admin tokens with 403."""

    def setup_method(self):
        self._original_overrides = dict(app.dependency_overrides)

    def teardown_method(self):
        app.dependency_overrides = self._original_overrides

    def test_get_settings_403_for_regular_user(self):
        app.dependency_overrides[get_current_user] = lambda: _override_user("user")
        client = TestClient(app)
        r = client.get(
            "/admin/settings",
            headers={"Authorization": f"Bearer {_FAKE_TOKEN}"},
        )
        assert r.status_code == 403, r.text

    def test_patch_settings_403_for_regular_user(self):
        app.dependency_overrides[get_current_user] = lambda: _override_user("user")
        client = TestClient(app)
        r = client.patch(
            "/admin/settings",
            headers={"Authorization": f"Bearer {_FAKE_TOKEN}"},
            json={"llm_provider": "cloud"},
        )
        assert r.status_code == 403, r.text

    def test_get_llm_provider_status_403_for_regular_user(self):
        app.dependency_overrides[get_current_user] = lambda: _override_user("user")
        client = TestClient(app)
        r = client.get(
            "/admin/settings/llm-provider-status",
            headers={"Authorization": f"Bearer {_FAKE_TOKEN}"},
        )
        assert r.status_code == 403, r.text

    def test_patch_settings_403_for_dpo_role(self):
        """DPO role can access PDP endpoints but NOT admin/settings."""
        app.dependency_overrides[get_current_user] = lambda: _override_user("dpo")
        client = TestClient(app)
        r = client.patch(
            "/admin/settings",
            headers={"Authorization": f"Bearer {_FAKE_TOKEN}"},
            json={"llm_provider": "cloud"},
        )
        assert r.status_code == 403, r.text
