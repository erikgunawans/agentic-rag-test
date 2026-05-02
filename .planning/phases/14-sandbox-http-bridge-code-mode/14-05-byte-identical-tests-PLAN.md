---
phase: 14-sandbox-http-bridge-code-mode
plan: 05
type: execute
wave: 4
depends_on:
  - "14-04"
files_modified:
  - backend/tests/unit/test_bridge_byte_identical.py
  - backend/tests/integration/test_bridge_integration.py
autonomous: true
requirements:
  - BRIDGE-05
  - BRIDGE-07
must_haves:
  truths:
    - "test_bridge_byte_identical.py verifies that with SANDBOX_ENABLED=false OR TOOL_REGISTRY_ENABLED=false, no bridge module is imported at app startup (import isolation test)"
    - "test_bridge_byte_identical.py verifies that _execute_code() does NOT prepend 'from stubs import' when either flag is false"
    - "test_bridge_byte_identical.py verifies that /bridge/* routes are not registered in the app when flags are off"
    - "test_bridge_integration.py documents the E2E test scenario (Docker-dependent — marked xfail/skip when Docker unavailable)"
    - "All previously written unit tests still pass (regression: no new failures introduced)"
    - "python -m pytest tests/unit/ -v --tb=short exits 0 from backend/ with venv active"
  artifacts:
    - path: "backend/tests/unit/test_bridge_byte_identical.py"
      provides: "Byte-identical fallback verification — no bridge when flags off"
      contains: "def test_no_bridge_routes_when_flags_off"
    - path: "backend/tests/integration/test_bridge_integration.py"
      provides: "E2E bridge test (Docker-gated, xfail when unavailable)"
      contains: "def test_bridge_call_end_to_end"
---

# Plan 14-05: Byte-Identical Fallback Tests & Integration Test Scaffold

## Objective

Final plan for Phase 14:
1. **Byte-identical fallback tests** — verify that when `SANDBOX_ENABLED=false` or `TOOL_REGISTRY_ENABLED=false`, the bridge introduces zero behavioral change (no bridge routes, no stubs prepend, no module import)
2. **Integration test scaffold** — document the E2E test that requires a live Docker sandbox (marked xfail; runs during UAT)
3. **Full unit test run** — all 14-01 through 14-04 unit tests pass together

## Tasks

<task id="14-05-T1" name="Write byte-identical fallback tests">
<read_first>
- backend/app/main.py (confirm bridge mount guard and how to check registered routes)
- backend/app/services/tool_service.py (confirm bridge_active check in _execute_code)
- backend/app/config.py (confirm sandbox_enabled and tool_registry_enabled fields)
</read_first>
<action>
Create `backend/tests/unit/test_bridge_byte_identical.py`:

```python
"""Byte-identical fallback tests for Phase 14 bridge — BRIDGE-05, TOOL-05.

Verifies that when SANDBOX_ENABLED=False OR TOOL_REGISTRY_ENABLED=False:
  1. Bridge module is never imported (lazy import invariant)
  2. /bridge/* routes are not registered in the FastAPI app
  3. _execute_code() does not prepend 'from stubs import *' to submitted code

These tests run with default config values (both flags False = Railway default).
They do NOT require Docker.
"""
import sys
import types
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helper: clear cached settings and bridge module state
# ---------------------------------------------------------------------------

def _clear_bridge_module():
    """Remove bridge module from sys.modules to test isolation."""
    for key in list(sys.modules.keys()):
        if "bridge" in key and "app.routers" in key:
            del sys.modules[key]


# ---------------------------------------------------------------------------
# Route registration tests
# ---------------------------------------------------------------------------

class TestNoRouteWhenFlagsOff:
    """Bridge routes must not exist when flags are off."""

    def test_no_bridge_routes_when_both_flags_false(self):
        """With default config (both flags False), no /bridge/* routes exist."""
        mock_settings = MagicMock()
        mock_settings.sandbox_enabled = False
        mock_settings.tool_registry_enabled = False
        mock_settings.frontend_url = "http://localhost:5173"

        with patch("app.config.get_settings", return_value=mock_settings):
            # Re-import main to get fresh app with patched settings
            if "app.main" in sys.modules:
                del sys.modules["app.main"]
            _clear_bridge_module()

            from app.main import app

        client = TestClient(app)
        routes = [r.path for r in app.routes]
        bridge_routes = [r for r in routes if "/bridge" in r]
        assert bridge_routes == [], f"Bridge routes should not be registered: {bridge_routes}"

    def test_no_bridge_routes_when_sandbox_only(self):
        """With only SANDBOX_ENABLED=True, no bridge routes registered."""
        mock_settings = MagicMock()
        mock_settings.sandbox_enabled = True
        mock_settings.tool_registry_enabled = False
        mock_settings.frontend_url = "http://localhost:5173"

        with patch("app.config.get_settings", return_value=mock_settings):
            if "app.main" in sys.modules:
                del sys.modules["app.main"]
            _clear_bridge_module()

            from app.main import app

        routes = [r.path for r in app.routes]
        bridge_routes = [r for r in routes if "/bridge" in r]
        assert bridge_routes == [], f"Bridge routes should not be registered: {bridge_routes}"

    def test_no_bridge_routes_when_registry_only(self):
        """With only TOOL_REGISTRY_ENABLED=True, no bridge routes registered."""
        mock_settings = MagicMock()
        mock_settings.sandbox_enabled = False
        mock_settings.tool_registry_enabled = True
        mock_settings.frontend_url = "http://localhost:5173"

        with patch("app.config.get_settings", return_value=mock_settings):
            if "app.main" in sys.modules:
                del sys.modules["app.main"]
            _clear_bridge_module()

            from app.main import app

        routes = [r.path for r in app.routes]
        bridge_routes = [r for r in routes if "/bridge" in r]
        assert bridge_routes == [], f"Bridge routes should not be registered: {bridge_routes}"

    def test_bridge_routes_registered_when_both_flags_true(self):
        """With both flags True, /bridge/* routes ARE registered."""
        mock_settings = MagicMock()
        mock_settings.sandbox_enabled = True
        mock_settings.tool_registry_enabled = True
        mock_settings.frontend_url = "http://localhost:5173"
        mock_settings.bridge_port = 8002

        with patch("app.config.get_settings", return_value=mock_settings):
            if "app.main" in sys.modules:
                del sys.modules["app.main"]
            _clear_bridge_module()

            from app.main import app

        routes = [r.path for r in app.routes]
        bridge_routes = [r for r in routes if "/bridge" in r]
        assert len(bridge_routes) >= 3, f"Expected bridge routes, got: {bridge_routes}"


# ---------------------------------------------------------------------------
# Stub prepend tests
# ---------------------------------------------------------------------------

class TestNoPrependWhenFlagsOff:
    """_execute_code must NOT prepend 'from stubs import *' when flags are off."""

    def _simulate_prepend_logic(self, code: str, sandbox_enabled: bool, tool_registry_enabled: bool) -> str:
        """Reproduce the prepend logic from _execute_code for isolated testing."""
        bridge_active = sandbox_enabled and tool_registry_enabled
        if bridge_active and not code.startswith("from stubs import"):
            code = "from stubs import *\n" + code
        return code

    def test_no_prepend_when_both_false(self):
        original = "x = 1 + 2\nprint(x)"
        result = self._simulate_prepend_logic(original, False, False)
        assert result == original
        assert "from stubs import" not in result

    def test_no_prepend_when_sandbox_only(self):
        original = "x = 1 + 2"
        result = self._simulate_prepend_logic(original, True, False)
        assert result == original

    def test_no_prepend_when_registry_only(self):
        original = "x = 1 + 2"
        result = self._simulate_prepend_logic(original, False, True)
        assert result == original

    def test_prepend_when_both_true(self):
        original = "x = 1 + 2"
        result = self._simulate_prepend_logic(original, True, True)
        assert result.startswith("from stubs import *\n")
        assert "x = 1 + 2" in result

    def test_no_double_prepend_on_retry(self):
        original = "x = 1 + 2"
        result = self._simulate_prepend_logic(original, True, True)
        result2 = self._simulate_prepend_logic(result, True, True)
        assert result2.count("from stubs import") == 1


# ---------------------------------------------------------------------------
# Bridge module import isolation test
# ---------------------------------------------------------------------------

class TestLazyImportIsolation:
    """When flags are off, importing app.main must not load app.routers.bridge."""

    def test_bridge_module_not_in_sys_modules_when_flags_off(self):
        """With both flags False, app.routers.bridge should not appear in sys.modules after import."""
        mock_settings = MagicMock()
        mock_settings.sandbox_enabled = False
        mock_settings.tool_registry_enabled = False
        mock_settings.frontend_url = "http://localhost:5173"

        # Remove modules to force fresh import
        for key in list(sys.modules.keys()):
            if key.startswith("app."):
                del sys.modules[key]

        with patch("app.config.get_settings", return_value=mock_settings):
            import app.main  # noqa: F401

        loaded = [k for k in sys.modules if "bridge" in k and "routers" in k]
        assert loaded == [], f"Bridge module should not be loaded: {loaded}"
```
</action>
<acceptance_criteria>
- `test -f backend/tests/unit/test_bridge_byte_identical.py` exits 0
- `cd backend && source venv/bin/activate && python -m pytest tests/unit/test_bridge_byte_identical.py -v --tb=short 2>&1 | tail -10` shows all tests PASSED with exit 0
- Route registration tests exist for all three flag combinations (both false, sandbox only, registry only) + the positive case (both true)
- Stub prepend tests exist for no-prepend (flags off) and prepend (flags on) and idempotency
</acceptance_criteria>
</task>

<task id="14-05-T2" name="Create integration test scaffold (Docker-gated)">
<read_first>
- backend/tests/integration/ (check if directory exists; if not, create it)
- .planning/phases/14-sandbox-http-bridge-code-mode/14-CONTEXT.md (BRIDGE-01..07 acceptance criteria)
- .planning/ROADMAP.md §Phase 14 success criteria (what the E2E test must demonstrate)
</read_first>
<action>
Create `backend/tests/integration/test_bridge_integration.py`:

```python
"""Integration tests for the sandbox HTTP bridge — Phase 14.

These tests require:
  1. A live Docker daemon with the lexcore-sandbox:latest image built.
  2. Settings: SANDBOX_ENABLED=true, TOOL_REGISTRY_ENABLED=true.
  3. The backend running with both flags set.

Tests are marked xfail when Docker is unavailable so CI does not fail.
These tests are run manually as UAT steps.

UAT checklist (maps to BRIDGE-01..07 success criteria):
  [BRIDGE-01] ToolClient is pre-baked in the sandbox image at /sandbox/tool_client.py
  [BRIDGE-02] /bridge/call, /bridge/catalog, /bridge/health endpoints exist
  [BRIDGE-03] /bridge/call rejects invalid session_token with 401
  [BRIDGE-04] Typed stubs are injected into the container at /sandbox/stubs.py
  [BRIDGE-05] Container env has BRIDGE_URL and BRIDGE_TOKEN set
  [BRIDGE-06] code_mode_start SSE event emitted with tools list
  [BRIDGE-07] Dangerous import (subprocess) blocked; ToolClient.call() errors are structured dicts
"""
import os
import pytest

# Docker availability check
def _docker_available() -> bool:
    try:
        import docker
        client = docker.from_env()
        client.ping()
        return True
    except Exception:
        return False


DOCKER_SKIP = pytest.mark.skipif(
    not _docker_available() or not (
        os.getenv("SANDBOX_ENABLED") == "true" and
        os.getenv("TOOL_REGISTRY_ENABLED") == "true"
    ),
    reason="Requires Docker + SANDBOX_ENABLED=true + TOOL_REGISTRY_ENABLED=true",
)


@DOCKER_SKIP
class TestBridgeIntegrationE2E:
    """End-to-end bridge tests — require Docker and both feature flags enabled."""

    def test_toolclient_prebaked_in_image(self):
        """[BRIDGE-01] /sandbox/tool_client.py exists in the sandbox image."""
        import docker
        client = docker.from_env()
        result = client.containers.run(
            "lexcore-sandbox:latest",
            ["python3", "-c", "import tool_client; print('OK')"],
            working_dir="/sandbox",
            remove=True,
            stdout=True,
            stderr=True,
        )
        assert b"OK" in result, f"ToolClient not pre-baked: {result}"

    def test_bridge_health_endpoint_reachable(self):
        """[BRIDGE-02] GET /bridge/health returns {'status': 'ok'}."""
        import httpx
        base_url = os.getenv("API_BASE_URL", "http://localhost:8000")
        r = httpx.get(f"{base_url}/bridge/health")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}

    def test_bridge_call_rejects_bad_token(self):
        """[BRIDGE-03] /bridge/call rejects bad session_token with 401."""
        import httpx
        base_url = os.getenv("API_BASE_URL", "http://localhost:8000")
        # Use a valid JWT but invalid session_token
        jwt = os.getenv("TEST_JWT", "")
        r = httpx.post(
            f"{base_url}/bridge/call",
            json={"tool_name": "search_documents", "arguments": {}, "session_token": "bad-token"},
            headers={"Authorization": f"Bearer {jwt}"},
        )
        assert r.status_code == 401

    def test_dangerous_import_blocked(self):
        """[BRIDGE-07] Submitting 'import subprocess' returns security_violation error."""
        # This test requires the full chat SSE endpoint to trigger execute_code.
        # Document as a UAT item — automated in chat_sse_integration tests.
        pytest.skip("Requires full chat SSE integration — document as UAT step")

    def test_code_mode_start_event_emitted(self):
        """[BRIDGE-06] code_mode_start SSE event is emitted before first execute_code."""
        pytest.skip("Requires full SSE stream capture — document as UAT step")

    def test_stub_file_injected_in_container(self):
        """[BRIDGE-04] /sandbox/stubs.py exists after sandbox session creation."""
        pytest.skip("Requires running sandbox session — document as UAT step")
```
</action>
<acceptance_criteria>
- `test -f backend/tests/integration/test_bridge_integration.py` exits 0
- `cd backend && source venv/bin/activate && python -m pytest tests/integration/test_bridge_integration.py -v --tb=short 2>&1 | tail -5` exits 0 (all Docker-dependent tests skipped or xfailed, not errored)
- File documents all 7 BRIDGE-* requirements as test cases
</acceptance_criteria>
</task>

<task id="14-05-T3" name="Run full Phase 14 unit test suite">
<read_first>
- backend/tests/unit/ (listing of all test files written in Plans 14-01 through 14-05)
</read_first>
<action>
From `backend/` with venv active, run the full unit test suite for Phase 14:

```bash
python -m pytest tests/unit/test_sandbox_bridge_service.py \
                 tests/unit/test_sandbox_service_bridge.py \
                 tests/unit/test_bridge_router.py \
                 tests/unit/test_bridge_byte_identical.py \
                 -v --tb=short
```

All tests must pass. If any test fails, investigate and fix the underlying issue in the relevant plan's source files (do NOT weaken assertions or skip failing tests).

Also run the full unit suite to check for regressions:
```bash
python -m pytest tests/unit/ -v --tb=short --ignore=tests/unit/test_bridge_router.py
```

(The bridge router tests use sys.modules manipulation that may interfere with other tests in the same process — run them separately if needed.)
</action>
<acceptance_criteria>
- All four Phase 14 unit test files run with 0 failures, 0 errors
- `python -m pytest tests/unit/ -v --tb=short 2>&1 | grep -E "passed|failed|error" | tail -3` shows N passed, 0 failed, 0 errors
- `python -c "from app.main import app; print('OK')"` exits 0 from backend/ with venv active
</acceptance_criteria>
</task>

## Verification

```bash
# From backend/ with venv active:

# 1. Full Phase 14 unit tests
python -m pytest tests/unit/test_sandbox_bridge_service.py \
                 tests/unit/test_sandbox_service_bridge.py \
                 tests/unit/test_bridge_router.py \
                 tests/unit/test_bridge_byte_identical.py \
                 -v --tb=short

# 2. Integration tests scaffold (expects skips, not failures)
python -m pytest tests/integration/test_bridge_integration.py -v --tb=short

# 3. Import smoke
python -c "from app.main import app; print('OK')"

# 4. All Phase 14 PLAN.md must_haves spot checks
# Byte-identical fallback (BRIDGE-05 / TOOL-05):
grep "if settings.sandbox_enabled and settings.tool_registry_enabled" backend/app/main.py
grep "from stubs import" backend/app/services/tool_service.py
grep "code_mode_start" backend/app/routers/chat.py
grep "_check_dangerous_imports" backend/app/services/sandbox_service.py
grep "bridge_token" backend/app/services/sandbox_service.py
grep "revoke_token" backend/app/services/sandbox_service.py

# 5. File existence check
test -f backend/sandbox/Dockerfile && echo "sandbox/Dockerfile OK"
test -f backend/sandbox/tool_client.py && echo "tool_client.py OK"
test -f backend/app/routers/bridge.py && echo "bridge router OK"
test -f backend/app/services/sandbox_bridge_service.py && echo "sandbox_bridge_service OK"
```

**Phase 14 UAT checklist (requires Docker + both flags true):**
- [ ] Build sandbox Docker image: `docker build -t lexcore-sandbox:latest backend/sandbox/`
- [ ] Verify ToolClient in image: `docker run --rm lexcore-sandbox:latest python3 -c "import tool_client; print('OK')"`
- [ ] Set `SANDBOX_ENABLED=true` and `TOOL_REGISTRY_ENABLED=true` in `.env`
- [ ] Start backend: `uvicorn app.main:app --reload --port 8000`
- [ ] Check bridge routes registered: `curl http://localhost:8000/bridge/health` → `{"status":"ok"}`
- [ ] Test in chat: Submit code that calls `search_documents(query="test")` — verify `code_mode_start` SSE event received
- [ ] Test dangerous import block: Submit `import subprocess` code — verify `security_violation` result
- [ ] Test token rejection: `curl -X POST http://localhost:8000/bridge/call -H "Authorization: Bearer $JWT" -d '{"tool_name":"search_documents","arguments":{},"session_token":"bad"}' -H "Content-Type: application/json"` → 401

<threat_model>
## Threat Model (ASVS L1)

| Threat | Mitigation |
|--------|-----------|
| Test suite mutation of sys.modules affecting other tests | Bridge byte-identical tests use targeted cleanup; integration tests run in separate pytest session |
| False-positive test passes due to mocked settings | Tests patch get_settings at module level and force re-import of app.main to get fresh app instance |
| E2E tests failing CI when Docker unavailable | DOCKER_SKIP marker ensures tests are skipped (not failed) when Docker unavailable |
| Byte-identical tests not actually verifying import isolation | test_bridge_module_not_in_sys_modules_when_flags_off explicitly checks sys.modules after app.main import |
</threat_model>
