# Phase 10: Code Execution Sandbox Backend - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-01
**Phase:** 10-code-execution-sandbox-backend
**Areas discussed:** Sandbox runtime backend, Real-time SSE streaming, IPython session model, code_executions table & file storage

---

## Sandbox Runtime Backend

**Q1: How should the sandbox execute Python code?**

| Option | Description | Selected |
|--------|-------------|----------|
| llm-sandbox (Docker backend) | True container isolation; requires Docker-in-Docker on Railway | ✓ |
| llm-sandbox (local/process backend) | Same library API, subprocess instead of Docker; simpler but less isolated | |
| IPython kernel via subprocess | Direct subprocess kernel; no llm-sandbox dependency | |

**User's choice:** llm-sandbox (Docker backend)

**Q2: How to configure Docker access on Railway?**

| Option | Description | Selected |
|--------|-------------|----------|
| Docker socket mount | DOCKER_HOST=unix:///var/run/docker.sock; no privileged mode | ✓ |
| Docker-in-Docker (privileged) | Full DinD with privileged Railway container | |
| You decide | Defer to planner | |

**User's choice:** Docker socket mount

**Q3: Where should the custom Docker image live?**

| Option | Description | Selected |
|--------|-------------|----------|
| Docker Hub public image | lexcore-sandbox:latest; SandboxDockerfile in repo | ✓ |
| Build alongside Railway deploy | Multi-stage Dockerfile; rebuilds on every deploy | |
| GitHub Container Registry | GHCR; requires GITHUB_TOKEN in Railway | |

**User's choice:** Docker Hub public image

**Q4: Container lifecycle — fresh per call or reused per session?**

| Option | Description | Selected |
|--------|-------------|----------|
| One container per thread session | Reused across calls; 30-min TTL; enables variable persistence | ✓ |
| Fresh container per call | Clean isolation but breaks SANDBOX-02 variable persistence | |

**User's choice:** One container per thread session

---

## Real-time SSE Streaming

**Q1: How should streaming output reach the SSE stream during tool execution?**

| Option | Description | Selected |
|--------|-------------|----------|
| Streaming callback on execute_tool | async stream_callback(event_type, data) parameter; minimal blast radius | ✓ |
| Generator-based execute_tool | execute_tool returns async generator; cleaner long-term but requires all tools to adapt | |

**User's choice:** Streaming callback on execute_tool

**Q2: What data should code_stdout/code_stderr events carry?**

| Option | Description | Selected |
|--------|-------------|----------|
| Line + tool_call_id | { type, line, tool_call_id }; associates output with specific invocation | ✓ |
| Line only | { type, line }; simpler but ambiguous with multiple execute_code calls | |

**User's choice:** Line + tool_call_id

**Q3: What should tool_result contain after streaming?**

| Option | Description | Selected |
|--------|-------------|----------|
| Full stdout + file URLs | Complete output text + signed URLs; LLM can reference specific values | ✓ |
| Summary + file URLs only | Short summary + URLs; saves tokens but LLM loses output detail | |

**User's choice:** Full stdout + file URLs

**Q4: How should Python exceptions be surfaced?**

| Option | Description | Selected |
|--------|-------------|----------|
| Unified via code_stderr | Tracebacks stream as code_stderr; tool_result includes exit_code + error_type | ✓ |
| Separate code_error event | Distinct event type for exceptions; more semantic but more event types | |

**User's choice:** Unified via code_stderr

---

## IPython Session Model

**Q1: What happens to sessions on Railway restart?**

| Option | Description | Selected |
|--------|-------------|----------|
| Sessions lost on restart — acceptable | Ephemeral; no persistence layer needed | ✓ |
| Persist session state to Supabase | Serialize namespace to DB; complex, not all objects serializable | |

**User's choice:** Sessions lost on restart — acceptable

**Q2: How should the 30-min TTL cleanup run?**

| Option | Description | Selected |
|--------|-------------|----------|
| asyncio background task every 60s | Matches SANDBOX-02 spec; started on first execute_code call | ✓ |
| Lazy expiry on access | Check TTL on next call; containers linger for idle threads | |

**User's choice:** asyncio background task every 60s

**Q3: Per-user concurrent session limit?**

| Option | Description | Selected |
|--------|-------------|----------|
| One session per thread, no user-level cap | Multiple threads = multiple containers; fine for bounded user base | ✓ |
| One active session per user | Terminates prior session on new thread; surprising UX | |

**User's choice:** One session per thread, no user-level cap

**Q4: Per-call execution timeout?**

| Option | Description | Selected |
|--------|-------------|----------|
| 30s timeout per call | Prevents infinite loops; stream timeout via code_stderr; session stays alive | ✓ |
| No per-call timeout | Rely on 30-min TTL only; a single call could tie up container for full TTL | |
| You decide | Defer to planner | |

**User's choice:** 30s timeout per call

---

## code_executions Table & File Storage

**Q1: Which Supabase Storage bucket for generated files?**

| Option | Description | Selected |
|--------|-------------|----------|
| New sandbox-outputs bucket | Dedicated private bucket; path: {user_id}/{thread_id}/{execution_id}/{filename} | ✓ |
| Reuse skills-files with subfolder | Avoid new bucket; mixes unrelated data types | |

**User's choice:** New sandbox-outputs bucket

**Q2: Signed URL TTL for generated files?**

| Option | Description | Selected |
|--------|-------------|----------|
| 1 hour | Short-lived; legal platform safety; users can re-run to regenerate | ✓ |
| 24 hours | Longer window for sharing; increases risk window | |
| 7 days | Long-lived like skill exports; over-indexed for ephemeral sandbox output | |

**User's choice:** 1 hour

**Q3: code_executions RLS model?**

| Option | Description | Selected |
|--------|-------------|----------|
| Own executions only | user_id = auth.uid(); no UPDATE/DELETE; super_admin sees all | ✓ |
| Own executions + thread-scoped | Extra join; same result in practice for user-scoped threads | |

**User's choice:** Own executions only (immutable audit records)

**Q4: Include GET /code-executions endpoint in Phase 10?**

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — GET /code-executions?thread_id= | Router in Phase 10; Phase 11 panel needs it; migration + router belong together | ✓ |
| No — defer endpoint to Phase 11 | Migration only in Phase 10; Phase 11 adds router | |

**User's choice:** Yes — include in Phase 10

---

## Claude's Discretion

- llm-sandbox internal session management API (`SandboxSession` object shape)
- Migration 036 column definitions (reasonable defaults documented in CONTEXT.md specifics)
- `execute_code` tool input schema: `{ code: str, description: str | None }`
- Service module name: `sandbox_service.py`

## Deferred Ideas

- Code Execution Panel UI (SANDBOX-07) — Phase 11
- Persistent tool memory (MEM-01..03) — Phase 11
- Per-user sandbox resource limits — future milestone
- Sandbox network access for web scraping — explicitly in REQUIREMENTS.md §Future Requirements
