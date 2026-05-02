"""Integration tests for the sandbox HTTP bridge — Phase 14.

These tests require:
  1. A live Docker daemon with the lexcore-sandbox:latest image built.
  2. Settings: SANDBOX_ENABLED=true, TOOL_REGISTRY_ENABLED=true.
  3. The backend running with both flags set (or BRIDGE_PORT configured).

Tests are skipped when Docker is unavailable so CI does not fail.
These tests are run manually as UAT steps.

UAT checklist (maps to BRIDGE-01..07 success criteria):
  [BRIDGE-01] ToolClient is pre-baked in the sandbox image at /sandbox/tool_client.py
  [BRIDGE-02] /bridge/call, /bridge/catalog, /bridge/health endpoints exist and respond
  [BRIDGE-03] /bridge/call rejects invalid session_token with HTTP 401
  [BRIDGE-04] Typed stubs are injected into the container at /sandbox/stubs.py
  [BRIDGE-05] Container env has BRIDGE_URL and BRIDGE_TOKEN set; bridge only active with both flags
  [BRIDGE-06] code_mode_start SSE event emitted with tools list before first execute_code call
  [BRIDGE-07] Dangerous import (subprocess) blocked; ToolClient.call() errors are structured dicts

Build the sandbox image before running:
  docker build -t lexcore-sandbox:latest backend/sandbox/

Run with flags:
  SANDBOX_ENABLED=true TOOL_REGISTRY_ENABLED=true python -m pytest tests/integration/ -v
"""
import os

import pytest


def _docker_available() -> bool:
    """Check if Docker daemon is reachable."""
    try:
        import docker
        client = docker.from_env()
        client.ping()
        return True
    except Exception:
        return False


def _bridge_flags_enabled() -> bool:
    """Check if both bridge feature flags are set in the environment."""
    return (
        os.getenv("SANDBOX_ENABLED", "false").lower() == "true"
        and os.getenv("TOOL_REGISTRY_ENABLED", "false").lower() == "true"
    )


# Skip marker: applied to tests that require Docker + both flags
DOCKER_BRIDGE_SKIP = pytest.mark.skipif(
    not _docker_available() or not _bridge_flags_enabled(),
    reason=(
        "Requires Docker daemon + SANDBOX_ENABLED=true + TOOL_REGISTRY_ENABLED=true. "
        "Build sandbox image first: docker build -t lexcore-sandbox:latest backend/sandbox/"
    ),
)


# ---------------------------------------------------------------------------
# Docker image verification (BRIDGE-01)
# ---------------------------------------------------------------------------

@DOCKER_BRIDGE_SKIP
def test_toolclient_prebaked_in_image():
    """[BRIDGE-01] /sandbox/tool_client.py exists and imports cleanly in the sandbox image."""
    import docker
    client = docker.from_env()
    result = client.containers.run(
        "lexcore-sandbox:latest",
        ["python3", "-c", "import sys; sys.path.insert(0,'/sandbox'); from tool_client import ToolClient; print('OK')"],
        working_dir="/sandbox",
        remove=True,
        stdout=True,
        stderr=True,
    )
    assert b"OK" in result, f"ToolClient not pre-baked in image. Output: {result}"


@DOCKER_BRIDGE_SKIP
def test_sandbox_output_dir_exists_in_image():
    """[BRIDGE-01] /sandbox/output/ directory exists in the sandbox image."""
    import docker
    client = docker.from_env()
    result = client.containers.run(
        "lexcore-sandbox:latest",
        ["python3", "-c", "import os; print('EXISTS' if os.path.isdir('/sandbox/output') else 'MISSING')"],
        working_dir="/sandbox",
        remove=True,
        stdout=True,
    )
    assert b"EXISTS" in result, f"/sandbox/output/ not found in image. Output: {result}"


# ---------------------------------------------------------------------------
# Bridge endpoint tests (BRIDGE-02, BRIDGE-03)
# ---------------------------------------------------------------------------

@DOCKER_BRIDGE_SKIP
def test_bridge_health_endpoint_reachable():
    """[BRIDGE-02] GET /bridge/health returns {'status': 'ok'}."""
    import httpx
    base_url = os.getenv("API_BASE_URL", "http://localhost:8000")
    r = httpx.get(f"{base_url}/bridge/health", timeout=10)
    assert r.status_code == 200, f"Health check failed: {r.status_code} {r.text}"
    assert r.json() == {"status": "ok"}


@DOCKER_BRIDGE_SKIP
def test_bridge_call_rejects_bad_session_token():
    """[BRIDGE-03] /bridge/call rejects invalid session_token with HTTP 401."""
    import httpx
    base_url = os.getenv("API_BASE_URL", "http://localhost:8000")
    jwt = os.getenv("TEST_JWT", "")
    if not jwt:
        pytest.skip("TEST_JWT env var required for authenticated bridge tests")

    r = httpx.post(
        f"{base_url}/bridge/call",
        json={
            "tool_name": "search_documents",
            "arguments": {},
            "session_token": "this-is-not-a-valid-token",
        },
        headers={"Authorization": f"Bearer {jwt}"},
        timeout=10,
    )
    assert r.status_code == 401, f"Expected 401, got {r.status_code}: {r.text}"


@DOCKER_BRIDGE_SKIP
def test_bridge_catalog_returns_tool_list():
    """[BRIDGE-02] GET /bridge/catalog returns a list of available tools."""
    import httpx
    base_url = os.getenv("API_BASE_URL", "http://localhost:8000")
    jwt = os.getenv("TEST_JWT", "")
    session_token = os.getenv("TEST_BRIDGE_SESSION_TOKEN", "")
    if not jwt or not session_token:
        pytest.skip("TEST_JWT and TEST_BRIDGE_SESSION_TOKEN required")

    r = httpx.get(
        f"{base_url}/bridge/catalog",
        params={"session_token": session_token},
        headers={"Authorization": f"Bearer {jwt}"},
        timeout=10,
    )
    assert r.status_code == 200, f"Catalog failed: {r.status_code} {r.text}"
    data = r.json()
    assert "tools" in data
    assert isinstance(data["tools"], list)


# ---------------------------------------------------------------------------
# Security tests (BRIDGE-07)
# ---------------------------------------------------------------------------

@DOCKER_BRIDGE_SKIP
def test_dangerous_import_blocked_at_sandbox_level():
    """[BRIDGE-07] Submitting 'import subprocess' returns security_violation error.

    This test exercises the full chat → execute_code → _check_dangerous_imports path.
    Requires the full backend running.
    """
    pytest.skip(
        "Requires full chat SSE stream — run as UAT: "
        "submit 'import subprocess' code in a sandbox-enabled session and verify "
        "the response contains error='security_violation'"
    )


@DOCKER_BRIDGE_SKIP
def test_toolclient_returns_error_dict_not_exception():
    """[BRIDGE-07] ToolClient.call() returns error dict when BRIDGE_URL unreachable."""
    import docker
    client = docker.from_env()
    # Run with no BRIDGE_URL set — ToolClient should return error dict, not raise
    result = client.containers.run(
        "lexcore-sandbox:latest",
        ["python3", "-c", (
            "import sys; sys.path.insert(0,'/sandbox'); "
            "from tool_client import ToolClient; "
            "tc = ToolClient(); "
            "r = tc.call('test'); "
            "assert isinstance(r, dict), f'Expected dict, got {type(r)}'; "
            "assert r.get('error') == 'bridge_error', f'Expected bridge_error, got {r}'; "
            "print('OK')"
        )],
        working_dir="/sandbox",
        environment={},  # No BRIDGE_URL
        remove=True,
        stdout=True,
        stderr=True,
    )
    assert b"OK" in result, f"ToolClient raised instead of returning error dict: {result}"


# ---------------------------------------------------------------------------
# SSE event tests (BRIDGE-06) — UAT only
# ---------------------------------------------------------------------------

@DOCKER_BRIDGE_SKIP
def test_code_mode_start_event_emitted():
    """[BRIDGE-06] code_mode_start SSE event emitted before first execute_code call.

    UAT step: connect to the chat SSE endpoint, submit a message that triggers
    execute_code, and verify the event stream includes:
      {"type": "code_mode_start", "tools": [...]}
    before any tool_start event for execute_code.
    """
    pytest.skip(
        "UAT step: verify code_mode_start appears in SSE stream before execute_code tool_start. "
        "Run: curl -N -H 'Authorization: Bearer $JWT' "
        "-H 'Content-Type: application/json' "
        "-d '{\"message\": \"run some Python code\", \"thread_id\": \"test\"}' "
        "http://localhost:8000/chat/stream | grep code_mode_start"
    )


@DOCKER_BRIDGE_SKIP
def test_bridge_call_end_to_end():
    """[BRIDGE-01..07] Full E2E: sandbox code calls a platform tool via ToolClient.

    UAT step:
    1. Start a chat session with SANDBOX_ENABLED=true, TOOL_REGISTRY_ENABLED=true
    2. Submit: execute Python code that calls search_documents() from stubs
    3. Verify the tool call succeeds and returns documents from the platform

    Expected flow:
      chat → execute_code → sandbox container → ToolClient.call('search_documents')
      → POST /bridge/call → validate_token → tool_registry.execute → search_documents
      → returns results to container → LLM sees results
    """
    pytest.skip(
        "Full E2E UAT step — requires running backend with both flags enabled, "
        "sandbox image built, and a chat session. See Phase 14 UAT checklist."
    )
