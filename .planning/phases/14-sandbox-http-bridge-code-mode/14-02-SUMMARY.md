---
plan: 14-02
phase: 14-sandbox-http-bridge-code-mode
status: complete
completed: 2026-05-03
commit: b84fa45
requirements_covered:
  - BRIDGE-05
  - BRIDGE-07
---

# Summary: Plan 14-02 — Sandbox Service Patch

## What Was Built

Patched `backend/app/services/sandbox_service.py` with four surgical additions:

1. **`_DANGEROUS_IMPORT_PATTERNS` + `_check_dangerous_imports()`** (BRIDGE-07, D-P14-06) — compiled regex blocking `subprocess`, `socket`, and `__import__` with those names. Called at the top of `execute()` before any `container.run()`. Returns the matched pattern string or None. Does NOT block `urllib.request` or `urllib.parse` (used by bridge ToolClient).

2. **`SandboxSession.bridge_token: str | None = None`** (D-P14-03) — optional field added to the dataclass. Default None ensures backward compatibility with all existing `SandboxSession(...)` constructors.

3. **`_create_container(thread_id, user_id)` bridge env injection** (D-P14-05) — when both `sandbox_enabled` and `tool_registry_enabled` are True, creates a bridge token via lazy import of `sandbox_bridge_service.create_bridge_token()`, injects `BRIDGE_URL=http://host.docker.internal:{bridge_port}` and `BRIDGE_TOKEN=<uuid>` into container environment. When either flag is False: empty env dict, no bridge token (byte-identical fallback).

4. **`_cleanup_loop()` token revocation** (D-P14-03) — after popping each stale session, calls `revoke_token(tid)` via lazy import. No-op when bridge is inactive (empty `_TOKEN_STORE`).

## Key Files Modified

- `backend/app/services/sandbox_service.py` (modified — 4 additions)
- `backend/tests/unit/test_sandbox_service_bridge.py` (new — 22 tests)

## Test Results

```
22 passed in 0.52s
```

## Deviations

`_get_or_create_session` signature changed to `(thread_id, user_id="")` — `user_id` defaults to empty string for backward compatibility. The `execute()` method already received `user_id` and passes it through.

## Self-Check: PASSED

- [x] `SandboxSession.bridge_token` defaults to None
- [x] `_check_dangerous_imports` blocks subprocess/socket, allows urllib
- [x] `bridge_active` dual-flag guard confirmed
- [x] Token revocation in `_cleanup_loop`
- [x] Import smoke test passes
- [x] 22/22 unit tests pass
