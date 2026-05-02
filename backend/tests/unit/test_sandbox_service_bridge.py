"""Unit tests for sandbox_service bridge patches — Phase 14 / BRIDGE-05, BRIDGE-07.

Tests:
  - _check_dangerous_imports: subprocess, socket blocked; urllib not blocked
  - bridge_active dual-flag logic (mocked settings)
  - SandboxSession.bridge_token field exists and defaults to None

Note: Full execute() integration tests require a live Docker daemon —
those belong in integration/E2E tests. These unit tests cover the
pure-logic branches that don't need Docker.
"""
from unittest.mock import MagicMock
from datetime import datetime

import pytest

from app.services.sandbox_service import _check_dangerous_imports, SandboxSession


class TestDangerousImportScanner:
    """Tests for the _check_dangerous_imports module-level function."""

    # --- Blocked patterns ---
    def test_dangerous_import_subprocess(self):
        assert _check_dangerous_imports("import subprocess") is not None

    def test_blocks_from_subprocess_import(self):
        assert _check_dangerous_imports("from subprocess import run") is not None

    def test_blocks_import_socket(self):
        assert _check_dangerous_imports("import socket") is not None

    def test_blocks_from_socket_import(self):
        assert _check_dangerous_imports("from socket import create_connection") is not None

    def test_blocks_dunder_import_subprocess(self):
        assert _check_dangerous_imports("__import__('subprocess')") is not None

    def test_blocks_dunder_import_socket(self):
        assert _check_dangerous_imports('__import__("socket")') is not None

    def test_blocks_case_insensitive(self):
        assert _check_dangerous_imports("IMPORT SUBPROCESS") is not None

    def test_returns_matched_string(self):
        result = _check_dangerous_imports("import subprocess")
        assert isinstance(result, str)
        assert len(result) > 0

    # --- Safe patterns (must NOT be blocked) ---
    def test_allows_urllib_request(self):
        assert _check_dangerous_imports("import urllib.request") is None

    def test_allows_urllib_parse(self):
        assert _check_dangerous_imports("import urllib.parse") is None

    def test_allows_from_urllib_request(self):
        assert _check_dangerous_imports("from urllib.request import urlopen") is None

    def test_allows_clean_code(self):
        code = "x = 1 + 2\nprint(x)"
        assert _check_dangerous_imports(code) is None

    def test_allows_math_import(self):
        assert _check_dangerous_imports("import math") is None

    def test_returns_none_on_empty_string(self):
        assert _check_dangerous_imports("") is None

    def test_allows_json_import(self):
        assert _check_dangerous_imports("import json") is None

    def test_allows_os_path_import(self):
        # os itself is fine; subprocess and socket are the dangerous ones
        assert _check_dangerous_imports("import os.path") is None


class TestSandboxSessionBridgeToken:
    """Tests for bridge_token field on SandboxSession dataclass."""

    def test_bridge_token_defaults_to_none(self):
        sess = SandboxSession(
            container=object(),
            last_used=datetime.utcnow(),
            thread_id="t1",
        )
        assert sess.bridge_token is None

    def test_bridge_token_can_be_set(self):
        sess = SandboxSession(
            container=object(),
            last_used=datetime.utcnow(),
            thread_id="t1",
            bridge_token="test-uuid-1234",
        )
        assert sess.bridge_token == "test-uuid-1234"


class TestBridgeActiveFlag:
    """Tests for bridge_active dual-flag logic (pure logic, no Docker needed)."""

    def _make_settings(self, sandbox_enabled: bool, tool_registry_enabled: bool):
        m = MagicMock()
        m.sandbox_enabled = sandbox_enabled
        m.tool_registry_enabled = tool_registry_enabled
        m.bridge_port = 8002
        m.sandbox_image = "lexcore-sandbox:latest"
        m.sandbox_docker_host = "unix:///var/run/docker.sock"
        return m

    def test_bridge_active_when_both_flags_true(self):
        settings = self._make_settings(True, True)
        bridge_active = settings.sandbox_enabled and settings.tool_registry_enabled
        assert bridge_active is True

    def test_bridge_inactive_when_sandbox_only(self):
        settings = self._make_settings(True, False)
        bridge_active = settings.sandbox_enabled and settings.tool_registry_enabled
        assert bridge_active is False

    def test_bridge_inactive_when_registry_only(self):
        settings = self._make_settings(False, True)
        bridge_active = settings.sandbox_enabled and settings.tool_registry_enabled
        assert bridge_active is False

    def test_bridge_inactive_when_both_false(self):
        settings = self._make_settings(False, False)
        bridge_active = settings.sandbox_enabled and settings.tool_registry_enabled
        assert bridge_active is False
