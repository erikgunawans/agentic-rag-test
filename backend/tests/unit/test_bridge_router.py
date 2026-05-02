"""Unit tests for bridge router — Phase 14 / BRIDGE-02, BRIDGE-03.

Uses FastAPI TestClient with dependency overrides to test auth and routing
without requiring a live Docker sandbox or Supabase connection.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers.bridge import router
from app.dependencies import get_current_user


# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------

def make_user(user_id: str = "user-1") -> dict:
    return {"id": user_id, "email": "test@test.com", "token": "test-jwt", "role": "user"}


def make_app(user_id: str = "user-1") -> FastAPI:
    """Create a minimal FastAPI app with the bridge router and a mocked user dependency."""
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: make_user(user_id)
    return app


# ---------------------------------------------------------------------------
# Health endpoint (no auth)
# ---------------------------------------------------------------------------

class TestBridgeHealth:
    def test_bridge_health_returns_ok(self):
        app = make_app()
        with TestClient(app) as client:
            r = client.get("/bridge/health")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# Auth rejection
# ---------------------------------------------------------------------------

class TestBridgeAuth:
    def test_call_rejects_invalid_token_401(self):
        app = make_app(user_id="user-1")
        with patch("app.services.sandbox_bridge_service.validate_token", return_value=False):
            with TestClient(app) as client:
                r = client.post("/bridge/call", json={
                    "tool_name": "search_documents",
                    "arguments": {"query": "test"},
                    "session_token": "bad-token",
                })
        assert r.status_code == 401

    def test_catalog_rejects_invalid_token_401(self):
        app = make_app(user_id="user-1")
        with patch("app.services.sandbox_bridge_service.validate_token", return_value=False):
            with TestClient(app) as client:
                r = client.get("/bridge/catalog", params={"session_token": "bad-token"})
        assert r.status_code == 401

    def test_call_missing_session_token_returns_422(self):
        """session_token is required in BridgeCallRequest — missing = 422."""
        app = make_app(user_id="user-1")
        with TestClient(app) as client:
            r = client.post("/bridge/call", json={
                "tool_name": "search_documents",
                "arguments": {},
                # session_token omitted
            })
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# Tool dispatch
# ---------------------------------------------------------------------------

class TestBridgeCall:
    def _make_tool_def(self, result):
        executor = AsyncMock(return_value=result)
        tool_def = MagicMock()
        tool_def.executor = executor
        tool_def.source = "native"
        return tool_def, executor

    def test_call_unknown_tool_returns_404(self):
        app = make_app(user_id="user-1")
        mock_registry = MagicMock()
        mock_registry._REGISTRY = {}
        with (
            patch("app.services.sandbox_bridge_service.validate_token", return_value=True),
            patch("app.services.tool_registry._REGISTRY", {}),
            TestClient(app) as client,
        ):
            r = client.post("/bridge/call", json={
                "tool_name": "nonexistent_tool",
                "arguments": {},
                "session_token": "valid-token",
            })
        assert r.status_code == 404

    def test_call_dispatches_to_executor_and_returns_result(self):
        expected_result = {"documents": [{"id": "doc-1", "content": "test"}]}
        tool_def, executor = self._make_tool_def(expected_result)
        registry = {"search_documents": tool_def}
        app = make_app(user_id="user-1")
        with (
            patch("app.services.sandbox_bridge_service.validate_token", return_value=True),
            patch("app.services.tool_registry._REGISTRY", registry),
            TestClient(app) as client,
        ):
            r = client.post("/bridge/call", json={
                "tool_name": "search_documents",
                "arguments": {"query": "revenue"},
                "session_token": "valid-token",
            })
        assert r.status_code == 200
        data = r.json()
        assert "result" in data
        assert data["result"] == expected_result
        executor.assert_called_once()

    def test_call_executor_exception_returns_structured_error(self):
        """BRIDGE-07: executor exceptions return structured dict, not HTTP 500."""
        executor = AsyncMock(side_effect=RuntimeError("tool blew up"))
        tool_def = MagicMock()
        tool_def.executor = executor
        registry = {"search_documents": tool_def}
        app = make_app(user_id="user-1")
        with (
            patch("app.services.sandbox_bridge_service.validate_token", return_value=True),
            patch("app.services.tool_registry._REGISTRY", registry),
            TestClient(app) as client,
        ):
            r = client.post("/bridge/call", json={
                "tool_name": "search_documents",
                "arguments": {},
                "session_token": "valid-token",
            })
        assert r.status_code == 200  # BRIDGE-07: errors as dicts, not HTTP errors
        data = r.json()
        assert data["result"]["error"] == "tool_execution_error"
        assert "tool blew up" in data["result"]["message"]

    def test_catalog_returns_tool_list(self):
        """GET /bridge/catalog returns sorted list of registered tools."""
        mock_tool_b = MagicMock()
        mock_tool_b.source = "native"
        mock_tool_b.description = "Tool B description"
        mock_tool_a = MagicMock()
        mock_tool_a.source = "native"
        mock_tool_a.description = "Tool A description"
        registry = {"tool_b": mock_tool_b, "tool_a": mock_tool_a}
        app = make_app(user_id="user-1")
        with (
            patch("app.services.sandbox_bridge_service.validate_token", return_value=True),
            patch("app.services.tool_registry._REGISTRY", registry),
            TestClient(app) as client,
        ):
            r = client.get("/bridge/catalog", params={"session_token": "valid-token"})
        assert r.status_code == 200
        data = r.json()
        assert "tools" in data
        names = [t["name"] for t in data["tools"]]
        assert "tool_a" in names
        assert "tool_b" in names
        # Should be sorted
        assert names == sorted(names)
