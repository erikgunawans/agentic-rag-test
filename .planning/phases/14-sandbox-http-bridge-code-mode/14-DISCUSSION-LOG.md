# Phase 14: Sandbox HTTP Bridge (Code Mode) - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-02
**Phase:** 14-sandbox-http-bridge-code-mode
**Mode:** --auto (fully autonomous; no interactive prompts)
**Areas discussed:** Bridge Port & Networking, Session Token Lifecycle, Stub Injection Strategy, Feature Flag Interaction, Dangerous Import Scanning

---

## Bridge Port & Networking

| Option | Description | Selected |
|--------|-------------|----------|
| Fixed configurable port (`BRIDGE_PORT`, default 8002) | Simple env var; PRD §Infrastructure specifies port 8002; Railway config is straightforward | ✓ |
| Dynamic ephemeral port (OS assigns) | Avoids port conflicts but requires runtime discovery mechanism across process boundary | |

**Auto-selected:** Fixed configurable port via `BRIDGE_PORT` env var (default 8002)
**Notes:** Dynamic ephemeral port is incompatible with the per-thread container model — the container needs to know the port at creation time. PRD §Infrastructure explicitly mentions port 8002. Full Docker network isolation (`--network=none` + iptables allow-only-bridge) is deferred as a hardening step.

---

## Session Token Lifecycle

| Option | Description | Selected |
|--------|-------------|----------|
| Thread-scoped token (same lifetime as 30-min sandbox session TTL) | One UUID per container; revoked when `_cleanup_loop()` evicts the session; in-memory dict | ✓ |
| Request-scoped token (new token per code execution call) | Finer-grained but requires token rotation and more complex lifecycle management | |
| DB-persisted token | Survives process restarts but contradicts D-P10-09 (in-memory sessions) | |

**Auto-selected:** Thread-scoped token, same lifetime as sandbox session
**Notes:** Maps directly to existing per-thread `SandboxSession` model. Consistent with D-P10-09 in-memory-only design. `sandbox_bridge_service.revoke_token(thread_id)` is called from `_cleanup_loop()`.

---

## Stub Injection Strategy

| Option | Description | Selected |
|--------|-------------|----------|
| One-time file write to `/sandbox/stubs.py` via `execute_command` at session creation | ~1 injection per 30-min session; `from stubs import *` prepended to each code block | ✓ |
| Inline prefix on every `container.run()` call | No file write needed; simpler but repeats multi-KB stub text on every execution | |
| Separate "stub loader" tool the LLM must call explicitly | More explicit but adds an extra round-trip and breaks the "transparent" bridge model | |

**Auto-selected:** One-time write to `/sandbox/stubs.py` at session creation
**Notes:** The existing `execute_command` API in llm-sandbox is already used for file listing in Phase 10. One-time injection avoids per-execution overhead. Fallback: if `execute_command` doesn't support stdin, use `container.run(...)` to write the file inline.

---

## Feature Flag Interaction

| Option | Description | Selected |
|--------|-------------|----------|
| Bridge active only when BOTH `SANDBOX_ENABLED` AND `TOOL_REGISTRY_ENABLED` are true | Cleanest separation; `execute_code` with only `SANDBOX_ENABLED=true` remains byte-identical to v1.1 | ✓ |
| Bridge active whenever `SANDBOX_ENABLED=true` (registry optional) | Bridge could work without full registry by falling back to legacy tools | |
| Bridge as a separate third flag (`BRIDGE_ENABLED`) | Maximum granularity but adds another flag to document and test | |

**Auto-selected:** Both flags required for bridge to activate
**Notes:** Consistent with D-P13-01 TOOL-05 invariant (byte-identical fallback when registry disabled). No third flag needed — the dual-flag contract is already established in PROJECT.md.

---

## Dangerous Import Scanning

| Option | Description | Selected |
|--------|-------------|----------|
| Regex in `sandbox_service.py` before `container.run()` | Co-locates security check with execution; consistent with `_WRITE_KEYWORDS` pattern in `tool_service.py` | ✓ |
| Separate `security_service.py` module | Better separation but over-engineered for a one-function concern | |
| Container-level enforcement only (seccomp/AppArmor) | Infrastructure-level but not available in Railway's Docker environment; not addressable in code | |

**Auto-selected:** `_check_dangerous_imports(code: str) -> str | None` in `sandbox_service.py`
**Notes:** PRD §Security mentions "existing security policy" but no such pattern was found in the codebase. Phase 14 introduces it. Must NOT block `urllib.request` or `urllib.parse` (used by the bridge `ToolClient`).

---

## Claude's Discretion

- **Bridge router file size** — ~80-120 LOC; thin router delegating to `sandbox_bridge_service.py`.
- **`sandbox_bridge_service.py` size** — ~150-200 LOC; token store, validation, stub generation, stub injection.
- **Stub generation for complex schemas** — `anyOf`/`oneOf` properties simplified to `Any` type for readability.
- **Token store data structure** — module-level `dict[str, BridgeTokenEntry]`, no separate async lock (token creation is already under `_get_or_create_session` lock).
- **`host.docker.internal` on Linux/Railway** — planner investigates llm-sandbox Docker run API; documents as Railway config step if not natively supported.
- **Bridge route prefix** — `/bridge` (consistent with existing flat router prefixes).

## Deferred Ideas

- Full Docker network isolation (`--network=none` + iptables allow-only-bridge) — deferred as Railway infra hardening.
- Bridge TLS — localhost/Docker-internal only; no TLS needed.
- Token store DB persistence — contradicts D-P10-09; deferred.
- `BRIDGE_TIMEOUT` as admin knob — env var only for v1.2.
- MCP tools via bridge — Phase 15 ships these as `source="mcp"` tools; bridge dispatch is source-agnostic.
- Per-user bridge access control — future RBAC milestone.
