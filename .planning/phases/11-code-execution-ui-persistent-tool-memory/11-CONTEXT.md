# Phase 11: Code Execution UI & Persistent Tool Memory - Context

**Gathered:** 2026-05-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Two surfaces, one phase:

1. **Code Execution Panel (SANDBOX-07)** — Frontend component that consumes the `code_stdout` / `code_stderr` / `tool_result` SSE events Phase 10 emits. Renders inline in chat as a Python-badge header + status indicator + execution time + collapsible code preview + terminal-style stdout/stderr block + file download cards. One panel per `execute_code` call, keyed by `tool_call_id`.

2. **Persistent Tool Memory (MEM-01..03)** — Backend change to (a) extend `ToolCallRecord` (`backend/app/models/tools.py`) with `tool_call_id` and `status`, (b) cap and persist the full result string in `messages.tool_calls.calls[N]`, and (c) rewrite history assembly in `chat.py` so prior tool-call sequences are reconstructed in the OpenAI tool-call format on every new turn — enabling the LLM to reference earlier UUIDs, search results, file listings, and code outputs without re-executing.

**Deliverables:**

1. `frontend/src/components/chat/CodeExecutionPanel.tsx` — NEW component (Python badge, status indicator, execution time, collapsible code preview, terminal-style output, file download cards). Keyed by `tool_call_id`; reads from a new live-stream buffer during streaming, switches to persisted `msg.tool_calls.calls[N]` after refetch.
2. `frontend/src/components/chat/ToolCallCard.tsx` patch — In `ToolCallList`, when `call.tool === "execute_code"` render `CodeExecutionPanel` instead of the generic `ToolCallCard`. Other tools render unchanged.
3. `frontend/src/hooks/useChatState.ts` patch — Add `sandboxStreams: Map<string, {stdout: string[], stderr: string[]}>` keyed by `tool_call_id`. SSE handler appends lines on `code_stdout`/`code_stderr` events; clears the entry after the message is refetched.
4. `frontend/src/lib/database.types.ts` patch — Extend `SSEEvent` union with `CodeStdoutEvent` and `CodeStderrEvent` (`{type, line, tool_call_id}`) — Phase 10 emits these but the frontend type union was never updated.
5. `backend/app/models/tools.py` patch — Extend `ToolCallRecord` with `tool_call_id: str | None`, `status: Literal["success","error","timeout"] | None`, and a Pydantic validator that head-truncates the serialized result/output to 50 KB with a `"\n…[truncated, N more bytes]\n"` marker.
6. `backend/app/routers/chat.py` history-assembly patch — On history load, when an assistant row's `tool_calls.calls[]` carries `tool_call_id` on every call, expand that row into the OpenAI triplet: `{role:"assistant", content, tool_calls:[…]}` → one `{role:"tool", tool_call_id, content: json.dumps(call.output)}` per call → `{role:"assistant", content: textAfterTools}`. Rows whose calls lack `tool_call_id` (legacy pre-Phase-11 messages) keep the current `{role, content}` only path. Reconstruction applies to both the multi-agent and single-agent branches.
7. `backend/app/routers/chat.py` record-construction patch — When building each `ToolCallRecord`, pass `tool_call_id=tc["id"]` and a derived `status` (sandbox: from sandbox output's `error_type`/`exit_code`; non-sandbox: `"error"` if exception caught else `"success"`).
8. `backend/app/routers/chat.py` redaction-aware reconstruction — When `redaction_on=True`, reconstructed tool result message content flows through the same `anonymize_history_text` path that user/assistant history already uses (chat.py ~L485). When `redaction_on=False`, content passes through verbatim.

**Out of scope (deferred):**

- Skill analytics / versioning — future milestone
- Sandbox network access / GPU sandboxes — REQUIREMENTS.md §Future Requirements
- Backfill migration to add `tool_call_id` to legacy rows — explicitly chosen against (D-P11-03)
- Per-tool-type size caps — chosen against in favor of uniform 50 KB (D-P11-04)

</domain>

<decisions>
## Implementation Decisions

### Code Execution Panel — Placement & Rendering

- **D-P11-01:** **Replace `ToolCallCard` for `execute_code` only.** `ToolCallList` keeps rendering all non-sandbox tool calls as today. When `call.tool === "execute_code"`, swap in the dedicated `CodeExecutionPanel` instead. Other tools (`search_documents`, `query_database`, `web_search`, `load_skill`, `save_skill`, `read_skill_file`, `kb_*`) keep `ToolCallCard` unchanged. Smallest blast radius; preserves the established `AgentBadge → ToolCallList → assistant bubble` layout in `MessageView.tsx`.
- **D-P11-05:** **One independent panel per call, stacked vertically.** Each `execute_code` invocation in a single assistant turn renders its own `CodeExecutionPanel`, keyed by `tool_call_id`. Panels stack in call order above the assistant text bubble. Mirrors `ToolCallList`'s existing one-card-per-call pattern and matches the PRD's "inline component" wording literally.
- **D-P11-09:** **Code preview collapsed by default.** Only the header (Python badge, status indicator, execution time) and terminal output are visible on first render. Code preview is hidden behind a `Show code` chevron toggle. Matches PRD's "Collapsible monospace block" wording. Reduces visual noise especially when multiple panels stack in a multi-call turn.
- **D-P11-06:** **File download cards are download-only via signed URL.** Each card shows filename + human-readable size + a Download button. Click triggers a refresh-signed-URL via the existing `GET /code-executions/{id}` endpoint (Phase 10 D-P10-17) and starts a browser download. No click-to-preview drawer for text files (sandbox outputs are mostly binary: matplotlib figs, PowerPoint, Excel; preview path would rarely fire and adds significant frontend complexity).

### Streaming → Persisted Reconciliation

- **D-P11-02:** **Live SSE during stream → persisted message after refetch.** While streaming, `CodeExecutionPanel` reads from a new `useChatState.sandboxStreams: Map<tool_call_id, {stdout: string[], stderr: string[]}>` buffer that accumulates lines as `code_stdout`/`code_stderr` SSE events arrive. After `delta:{done:true}`, `useChatState` refetches `messages` from Supabase (existing post-stream behavior, ~L210); the panel then switches to reading from `msg.tool_calls.calls[N]` (full stdout/stderr/files from the persisted `tool_result`). Matches the existing `tool_start`/`tool_result` UI timing — fully consistent with how `ToolCallList` already handles the live→persisted transition.
- **Status indicator semantics during the lifecycle:**
  - On `tool_start` (execute_code): spinner — "running"
  - On `code_stdout`/`code_stderr`: spinner stays — "streaming"
  - On `tool_result`: switch to ✓ / ✗ / ⏱ based on `tool_result.exit_code` and `tool_result.error_type`
  - After refetch: read from `call.status` field on the persisted record (D-P11-08)
- **Execution time display:** live counter (`(timestamp_now - tool_start_timestamp)`) during streaming; on `tool_result`, freezes at final `execution_ms` value from the result payload. After refetch, reads from `call.output.execution_ms`.

### Persistent Tool Memory — Scope & Shape

- **D-P11-07:** **MEM applies to all tools.** PRD §Feature 5 explicitly mentions referencing UUIDs, search results, and file listings in follow-ups — those come from `search_documents` / `query_database` / `kb_list_files`, not `execute_code`. Single uniform path: every `ToolCallRecord` carries `tool_call_id` + full (size-capped) result + status. History reconstruction expands every assistant row whose `tool_calls.calls[]` carry IDs.
- **D-P11-08:** **Extend `ToolCallRecord` with `tool_call_id: str | None`, `status: Literal["success","error","timeout"] | None`.** Keep the existing `output: dict | str` field (rather than renaming to `result` per literal PRD wording) — preserves backwards compatibility for the existing frontend `ToolCallCard.tsx` reader and any other consumers. New fields are optional, so legacy persisted rows still validate. Sandbox status mapping: success / error / timeout from Phase 10 sandbox output. Non-sandbox status: success / error (no timeout concept).
  ```python
  class ToolCallRecord(BaseModel):
      tool: str
      input: dict
      output: dict | str
      error: str | None = None
      tool_call_id: str | None = None     # Phase 11 — required for new rows
      status: Literal["success", "error", "timeout"] | None = None  # Phase 11
  ```
- **D-P11-04:** **50 KB head-truncate cap, applied at `ToolCallRecord` construction.** When the serialized output exceeds 50 KB (~12.5K tokens), keep the first 50 KB and append `"\n…[truncated, N more bytes]\n"` before persistence. Head (not tail/middle) preserves the start of the data — most useful for follow-up references like "what was the UUID of the first result?" — and is simpler than head+tail elision. Single source of truth: a Pydantic `field_validator` on `output` inside `ToolCallRecord`.
- **D-P11-11:** **Truncation lives inside `ToolCallRecord` at construction (Pydantic validator).** Every code path that builds a record gets truncation for free — `chat.py` (both branches), tests, future tool consumers. Status enum lives next to the validator for symmetry. Avoids a free-floating utility function or a one-off truncate at the persist site.

### History Reconstruction — Legacy & Privacy

- **D-P11-03:** **Skip reconstruction for legacy rows lacking `tool_call_id`.** When loading history, an assistant row qualifies for triplet expansion only if every entry in `tool_calls.calls[]` has a non-null `tool_call_id`. Otherwise the row falls back to the existing `{role:"assistant", content}` shape — old conversations still load and remain answerable; the LLM just can't reference legacy tool data. Zero migration risk; matches PRD's "no schema migration" guidance literally. The cutoff is detectable per-row (no global flag needed).
- **D-P11-10:** **Anonymize reconstructed tool messages through the existing per-history anonymizer.** When the new-turn session has `redaction_on=True`, reconstructed `{role:"tool", content}` messages flow through the same `anonymize_history_text` (or equivalent) path used by user/assistant history at chat.py ~L485. Honors the D-89 privacy invariant: no real PII in cloud-LLM payloads, even from historical tool outputs that were originally redaction-OFF. When `redaction_on=False`, content passes through verbatim. One code path; no skeleton-emit half-measure.

### Claude's Discretion

- Exact CSS class names and Tailwind utilities for `CodeExecutionPanel` — must conform to the 2026 Calibrated Restraint design system: zinc-neutral base, no `backdrop-blur` on persistent panels, no gradients, flat solid buttons. Terminal output uses dark background with green stdout / red stderr — confirmed in PRD.
- Exact wording of the 50 KB truncation marker — "`\n…[truncated, N more bytes]\n`" is a strong default; the planner may polish.
- File download UX: whether to show a small loading spinner during the signed-URL refresh roundtrip (~100ms typical) or fire-and-forget.
- Exact shape of the `useChatState` SSE handler diff for `code_stdout`/`code_stderr` — using `Map<tool_call_id, ...>` vs plain object is a JS-mechanics call; same observable behavior.
- Whether to derive non-sandbox `status` from `try`/`except` outcome alone, or inspect `output.error` for richer signal — both are acceptable.
- Test split: unit tests for `ToolCallRecord` validator (truncation + new fields), integration tests for chat.py history reconstruction (with and without legacy rows, with redaction on/off), component tests for `CodeExecutionPanel` (live-stream buffer + persisted-message branch + collapsed/expanded states).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Primary Specification

- `docs/PRD-skill.md` §Feature 3 §UI — Code Execution Panel UI spec: header (Python badge, status indicator, execution time), collapsible code preview, terminal-style output (dark bg, green stdout, red stderr), file download cards, error state.
- `docs/PRD-skill.md` §Feature 5 — Persistent Tool Memory: full result persisted alongside metadata, reconstruction format (assistant tool_calls → tool result → assistant text), no schema migration, size cap.

### Requirements & Roadmap

- `.planning/REQUIREMENTS.md` §SANDBOX-07 — "Chat shows inline Code Execution Panel with code preview, streaming output, and file downloads."
- `.planning/REQUIREMENTS.md` §MEM-01..03 — Persist full result; reconstruct on load; LLM references prior data without re-execution.
- `.planning/ROADMAP.md` §Phase 11 — 5 success criteria (authoritative scope anchor).

### Prior Phase Decisions (binding)

- `.planning/phases/10-code-execution-sandbox-backend/10-CONTEXT.md` — D-P10-05 (stream_callback parameter), D-P10-06 (SSE event shape `{type, line, tool_call_id}`), D-P10-07 (`tool_result` payload shape: stdout + stderr + signed-URL files + exit_code + error_type), D-P10-08 (errors stream through `code_stderr`; `tool_result` carries `exit_code` + `error_type`).
- `.planning/phases/10-code-execution-sandbox-backend/10-05-SUMMARY.md` — Queue-adapter and per-line PII anonymization implementation (already shipped).
- `.planning/phases/09-skills-frontend/09-CONTEXT.md` — D-P9-07 file preview drawer pattern (NOT reused this phase per D-P11-06; reference for visual consistency only).
- `.planning/phases/08-llm-tool-integration-discovery/08-CONTEXT.md` — D-P8-01..04 tool registration / dispatch pattern (relevant when extending the tool record shape).

### Codebase Conventions

- `.planning/codebase/CONVENTIONS.md` — Component skeleton, Pydantic patterns, audit pattern.
- `.planning/codebase/ARCHITECTURE.md` §Flow 1 — Chat with tool-calling and SSE streaming. Names every integration point this phase touches.

### Code Integration Points (must read)

- `backend/app/routers/chat.py` — History assembly @ L114-129 (currently `{role, content}` only — Phase 11 extends this), `_run_tool_loop` ToolCallRecord construction @ L427-450 and L957-970 (both branches; Phase 11 adds `tool_call_id`+`status`), persistence @ L715 (`ToolCallSummary` insert).
- `backend/app/models/tools.py` — `ToolCallRecord` and `ToolCallSummary` (~17 lines total). Phase 11 extends this file.
- `frontend/src/components/chat/MessageView.tsx` — `tool_calls.calls` render @ L97-101 (`<ToolCallList toolCalls={msg.tool_calls.calls} />`). Phase 11 lets `ToolCallList` route to `CodeExecutionPanel` for execute_code calls.
- `frontend/src/components/chat/ToolCallCard.tsx` — Existing pattern: `interface ToolCallListProps`, `function ToolCallList({ toolCalls })`. Phase 11 extends this — the `.map` switch is where we route to `CodeExecutionPanel`.
- `frontend/src/components/chat/AgentBadge.tsx` — Visual reference for the Python-language badge appearance (small, colored, leading position).
- `frontend/src/hooks/useChatState.ts` — SSE handler @ L172-210. Phase 11 adds `code_stdout`/`code_stderr` cases that append to the new `sandboxStreams` Map.
- `frontend/src/lib/database.types.ts` — `SSEEvent` discriminated union @ L73-79 (currently lacks `code_stdout`/`code_stderr`). Phase 11 adds these variants. `Message` type's `tool_calls` field type currently mirrors `ToolCallSummary` — extend with `tool_call_id` + `status` fields.
- `backend/app/routers/code_execution.py` — Existing Phase 10 router for `GET /code-executions` (signed URL refresh). Phase 11 reuses for file-download click handler.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- **`ToolCallList` / `ToolCallCard`** (`frontend/src/components/chat/ToolCallCard.tsx`) — Existing render path for `msg.tool_calls.calls`. Phase 11 adds a switch on `call.tool === "execute_code"` to route to the new `CodeExecutionPanel`. Untouched for all other tools.
- **`AgentBadge`** (`frontend/src/components/chat/AgentBadge.tsx`) — Visual reference for the Python-language badge. Reuse the styling approach (small chip, colored bg, label).
- **`useChatState`** (`frontend/src/hooks/useChatState.ts`) — Existing SSE event dispatcher (`tool_start`, `tool_result`, `delta`, `agent_start`, `agent_done`, `redaction_status`). Phase 11 extends with `code_stdout`/`code_stderr` cases that mutate a new `sandboxStreams` Map. Existing post-stream refetch (`supabase.from('messages').select(...)` ~L210) clears the Map entries on message reload.
- **`apiFetch`** (`frontend/src/lib/api.ts`) — Used for the file-download signed-URL refresh roundtrip (`GET /code-executions/{id}` → `files[].signed_url`).
- **`anonymize_history_text`** (or whatever the chat.py history-anonymization helper is currently called at ~L485) — Phase 11 reuses this same path for reconstructed tool result messages when `redaction_on=True`. No new anonymization logic.
- **Phase 10 SSE backend pipeline** (`backend/app/routers/chat.py` queue-adapter ~L252-396) — Already emits `code_stdout`/`code_stderr` with `{type, line, tool_call_id}` shape, with PII anonymization applied per-line when redaction is on. Phase 11 only consumes; no backend SSE changes needed.
- **Phase 10 `code_executions` table + `sandbox-outputs` bucket** (migration 036) — `GET /code-executions/{id}` returns refreshed signed URLs (1-hour TTL). Phase 11 calls this for file downloads.

### Established Patterns

- **`tool_calls` JSONB column** — Already exists on `messages` table, stores `ToolCallSummary.model_dump()`. Phase 11 changes the *contents* (extra fields per call) but **NO schema migration** — column is JSONB; new fields are validated by Pydantic on read.
- **History assembly** — `chat.py` L115-129 builds `[{role, content}]` from a `select("id, role, content, parent_message_id")`. Phase 11 changes the SELECT to `"id, role, content, parent_message_id, tool_calls"` and adds an inline expansion loop that emits 1-or-3 messages per row depending on whether `tool_calls.calls[]` is present and carries IDs.
- **Anonymizer integration in history loading** — Existing path at chat.py ~L485 batches user/assistant content for anonymization. Phase 11 hooks reconstructed `{role:"tool", content}` messages into the same batch when `redaction_on=True`.
- **OpenAI tool-call message format** — Already produced and consumed inside `_run_tool_loop` at chat.py L450-460 and L967-973: `{role:"assistant", content:None, tool_calls:[tc]}` followed by `{role:"tool", tool_call_id, content: json.dumps(output)}`. Phase 11's reconstruction emits the *same* shape; only difference is the message comes from DB rather than an in-progress tool loop.
- **Live → persisted UI transition** — `useChatState` already does this for assistant text: streams via `delta` events into `streamingContent`, then refetches messages and clears `streamingContent` (`useChatState.ts` ~L196 + L210). Phase 11 follows the exact same pattern for sandbox streams.
- **Design system** — 2026 Calibrated Restraint: zinc-neutral base, purple accent, NO `backdrop-blur` on persistent panels, NO gradients, flat solid buttons. Terminal block uses dark background per PRD.

### Integration Points

- **`backend/app/models/tools.py`** — Extend `ToolCallRecord` with `tool_call_id` + `status` fields, add Pydantic `field_validator` for 50 KB head-truncate of `output`. Single file ≈ 30 lines after changes.
- **`backend/app/routers/chat.py`** — Three changes: (1) widen the history SELECT to include `tool_calls`; (2) add expansion loop that emits triplets for qualifying rows, plain `{role,content}` for legacy; (3) pass `tool_call_id=tc["id"]` and `status=…` when constructing `ToolCallRecord` in both branches (L427-450, L957-970); (4) ensure reconstructed tool messages flow through the existing redaction-history anonymizer when `redaction_on`.
- **`frontend/src/components/chat/CodeExecutionPanel.tsx`** — NEW component. Props: `{ toolCallId: string, code: string, status: 'running' | 'success' | 'error' | 'timeout', executionMs?: number, stdoutLines: string[], stderrLines: string[], files: { filename, size_bytes, signed_url }[], errorType?: string }`. Internal state: `codeExpanded: boolean` (default false).
- **`frontend/src/components/chat/ToolCallCard.tsx`** — Add the `tool === "execute_code"` switch inside `ToolCallList.map`. Pass live-stream buffer from `useChatState` if present, otherwise hydrate from the persisted record's fields.
- **`frontend/src/hooks/useChatState.ts`** — New state: `sandboxStreams: Map<string, { stdout: string[], stderr: string[] }>`. Cases for `code_stdout` and `code_stderr` push lines onto the entry keyed by `event.tool_call_id`. After post-`done:true` refetch, clear all entries (or clear lazily — entries naturally fall off the next render once `msg.tool_calls.calls[N].output` is the source of truth).
- **`frontend/src/lib/database.types.ts`** — Extend `SSEEvent` with `CodeStdoutEvent` and `CodeStderrEvent` variants. Extend `Message.tool_calls.calls[N]` type with optional `tool_call_id: string | null` and `status: 'success' | 'error' | 'timeout' | null`.

</code_context>

<specifics>
## Specific Ideas

- **Truncation marker text:** `"\n…[truncated, N more bytes]\n"` — N is the byte count beyond the 50 KB cap. Single ellipsis (Unicode U+2026) for visual compactness.
- **Status indicator icons:** spinner (running) / ✓ green (success) / ✗ red (error) / ⏱ amber (timeout). Match Phase 10's status enum exactly.
- **Code preview toggle wording:** `Show code` (collapsed) / `Hide code` (expanded). Lucide chevron icon.
- **Live-stream buffer key:** `tool_call_id` from the SSE event. The same ID appears later on the persisted `call.tool_call_id` field, so reading both sources via the same key is trivial.
- **File card layout:** filename (truncated middle for long names) + size (`pretty-bytes`-style: `1.2 MB`) + Download button (purple accent per design system). Click → `apiFetch('/code-executions/{execution_id}')` → use returned `signed_url`.
- **Multi-call panel keying:** `<CodeExecutionPanel key={call.tool_call_id} … />` — React key from the SSE-provided UUID guarantees stable identity across re-renders.
- **History reconstruction conditional (chat.py pseudo):**
  ```python
  for row in history_rows:
      tc = row.get("tool_calls") or {}
      calls = tc.get("calls") or []
      if calls and all(c.get("tool_call_id") for c in calls):
          # Phase 11 triplet expansion
          history.append({
              "role": "assistant",
              "content": "",
              "tool_calls": [{"id": c["tool_call_id"], "type": "function",
                              "function": {"name": c["tool"],
                                            "arguments": json.dumps(c["input"])}}
                             for c in calls],
          })
          for c in calls:
              history.append({"role": "tool", "tool_call_id": c["tool_call_id"],
                              "content": _serialize(c["output"])})
          if row["content"]:
              history.append({"role": "assistant", "content": row["content"]})
      else:
          # Legacy / no-tool path — unchanged
          history.append({"role": row["role"], "content": row["content"]})
  ```
- **Redaction-history hook:** the reconstructed `{role:"tool", content}` items must be threaded through the same `raw_strings = [m["content"] for m in history] + [body.message]` collection at chat.py ~L485 so the existing batch anonymizer covers them.
- **Frontend type safety:** Mark `tool_call_id` and `status` as nullable (`string | null`) in `database.types.ts` so legacy rows still typecheck. The `ToolCallList` switch only routes to `CodeExecutionPanel` when `tool_call_id` is present (otherwise generic card, treating the legacy execute_code call like any other tool — extremely rare since Phase 10 just shipped).
- **No new env var, no new migration, no new bucket.** Pure code change across 6 files (4 frontend, 2 backend).

</specifics>

<deferred>
## Deferred Ideas

- **Per-tool size caps** (e.g., 30 KB for `search_documents`, 100 KB for `execute_code`) — discarded in favor of uniform 50 KB. Revisit only if MEM column bloat is observed in production.
- **Backfill migration** to add synthetic `tool_call_id` to legacy rows — discarded per D-P11-03; would contradict PRD's "no schema migration" guidance and add risk for marginal benefit.
- **Click-to-preview text files in slide-in drawer** — discarded per D-P11-06; sandbox outputs are mostly binary. Could revisit in a future "skill files richer preview" phase if user demand emerges.
- **Merged terminal across multiple execute_code calls in one turn** — discarded per D-P11-05; per-call panels are clearer and match per-call signed-URL file model.
- **Always-expanded code preview** — discarded per D-P11-09 in favor of collapsed-default to reduce visual noise in stacked-panel turns.
- **Renaming `output` → `result` in `ToolCallRecord`** — discarded per D-P11-08 to preserve backwards compatibility for the existing frontend reader and other consumers.
- **`summary` field** on `ToolCallRecord` (PRD-mentioned) — not added. Output already covers the data; UI status indicator covers human-readable state. Add later if a use case emerges.

</deferred>

---

*Phase: 11 — Code Execution UI & Persistent Tool Memory*
*Context gathered: 2026-05-01*
