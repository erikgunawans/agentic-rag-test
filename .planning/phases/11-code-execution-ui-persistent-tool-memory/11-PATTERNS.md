# Phase 11: Code Execution UI & Persistent Tool Memory — Pattern Map

**Mapped:** 2026-05-01
**Files analyzed:** 6 (4 frontend, 2 backend — chat.py spans 3 logical change sites)
**Analogs found:** 6 / 6 (all integration points have in-repo analogs)

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `frontend/src/components/chat/CodeExecutionPanel.tsx` (NEW) | component | streaming → render | `frontend/src/components/chat/ToolCallCard.tsx` (one-card-per-call render + collapsible chevron) + `frontend/src/components/chat/AgentBadge.tsx` (chip badge) | role-match (streaming UX is novel) |
| `frontend/src/components/chat/ToolCallCard.tsx` (MODIFY — `ToolCallList` switch) | component | render-route | self (`ToolCallList` map) | exact |
| `frontend/src/hooks/useChatState.ts` (MODIFY — SSE cases) | hook | event-driven | self (existing `event.type === 'tool_start'/'tool_result'/'redaction_status'` switch @ L170-204) | exact |
| `frontend/src/lib/database.types.ts` (MODIFY — SSEEvent union) | types | type-only | self (`RedactionStatusEvent` @ L68-71 added in Phase 5) | exact |
| `backend/app/models/tools.py` (MODIFY — add fields + validator) | model | Pydantic schema | self (`ToolCallRecord` @ L4-9) + `backend/app/routers/skills.py` `field_validator` style @ L37-44 | exact |
| `backend/app/routers/chat.py` (MODIFY — 3 sites: history SELECT, ToolCallRecord ctor ×2, redaction batch) | router | request-response + history-rebuild | self — all three sites already exist (L114-129, L427-429+436-438, L956-959, L485) | exact |

All six change sites have a literal in-repo analog. No external/RESEARCH.md fallback needed.

---

## Pattern Assignments

### 1. `frontend/src/components/chat/CodeExecutionPanel.tsx` (NEW component, streaming → render)

**Analog A:** `frontend/src/components/chat/ToolCallCard.tsx` — one-card-per-call wrapper, collapsible body, lucide icon header, `border rounded-md` container.

**Analog B:** `frontend/src/components/chat/AgentBadge.tsx` — small chip badge with lucide icon + label.

**Analog C (state lifecycle):** `useChatState.ts` `streamingContent` → post-stream refetch pattern (see file 3 below).

**Imports pattern** (from `ToolCallCard.tsx` L1-4):
```typescript
import { useState } from 'react'
import { Database, Search, Globe, FileText, ChevronDown, ChevronRight, Loader2 } from 'lucide-react'
import type { ToolCallRecord } from '@/lib/database.types'
import { useI18n } from '@/i18n/I18nContext'
```
For `CodeExecutionPanel.tsx` swap the icons for `Terminal`, `Copy`, `Download`, `FileDown`, `CheckCircle2`, `XCircle`, `Clock`, `AlertCircle`, `ChevronRight`, `Loader2` per UI-SPEC §Component Inventory. `useI18n` is mandatory — UI-SPEC defines i18n keys `sandbox.status.*`, `sandbox.showCode`, `sandbox.hideCode`, `sandbox.filesGenerated`, `sandbox.download`, `sandbox.truncated`, `sandbox.error.*`, `sandbox.copyCode`.

**Container shell pattern** (from `ToolCallCard.tsx` L52, structurally analogous):
```tsx
<div className="border rounded-md text-xs my-1">
  {/* Header: button (always visible) */}
  <button
    onClick={() => setExpanded(!expanded)}
    className="flex items-center gap-2 w-full px-3 py-2 text-left hover:bg-muted/50 transition-colors"
  >
    {/* Icon, badge, summary, chevron */}
  </button>
  {expanded && output && (
    <div className="px-3 pb-2 space-y-1.5 border-t">
      {/* Body */}
    </div>
  )}
</div>
```
For `CodeExecutionPanel`: replicate the outer `border rounded-md text-xs` shell. Replace the single header `<button>` with the two-cluster header from UI-SPEC §1 Panel Header (`flex items-center gap-2 px-3 py-2 border-b border-border`), where only the right-side chevron is the toggle (Python badge / status / timer are non-interactive). Code preview (UI-SPEC §2) and terminal (§3) and file cards (§4) become three sibling sections separated by `border-b border-border`, replacing the single `expanded && ...` block.

**Status icon pattern** (from `ToolCallCard.tsx` L57-61, the `isLoading ? Loader2 : Icon` shape):
```tsx
{isLoading ? (
  <Loader2 className="h-3.5 w-3.5 text-muted-foreground animate-spin shrink-0" />
) : (
  <Icon className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
)}
```
For `CodeExecutionPanel`: extend to a 5-state switch driven by the `status` prop using exact icons from UI-SPEC §Status Indicator States. Keep the `h-3.5 w-3.5 shrink-0` sizing — it matches `ToolCallCard` and the Dimension 5 spacing FLAG was non-blocking precisely because this size is project-canon.

**Chip badge pattern** (from `ToolCallCard.tsx` L17-28, `SourceBadge`):
```tsx
<span
  className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] shrink-0 ${
    isWeb
      ? 'bg-blue-500/10 text-blue-600 dark:text-blue-400'
      : 'bg-zinc-500/10 text-zinc-600 dark:text-zinc-400'
  }`}
>
  <Icon className="h-3 w-3" />
  {label}
</span>
```
For the Python badge: same shape — `inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] shrink-0` — with `bg-primary/15 text-primary` (UI-SPEC §Component Inventory) and `<Terminal className="h-3 w-3" />` + literal `"Python"` (NOT i18n'd, see UI-SPEC §Copywriting "Python Badge Label").

**Active-spinner pattern** (from `AgentBadge.tsx` L21-26 for the running state's mood):
```tsx
<div className="flex items-center gap-2 text-sm text-muted-foreground mb-2">
  <Loader2 className="h-3.5 w-3.5 animate-spin" />
  <span>{label} is working...</span>
</div>
```
For `CodeExecutionPanel`: same `Loader2 className="h-3.5 w-3.5 animate-spin"` for `running`/`pending` states. `text-primary` for `running` (active accent), `text-muted-foreground` for `pending` (UI-SPEC §Status Indicator States).

**Live → persisted prop resolution (component-internal logic):**
```typescript
// Pseudocode the planner must spec out:
// Caller (ToolCallList) passes both:
//   - persisted record (call.tool_call_id, call.input.code, call.output, call.status)
//   - live buffer entry from useChatState.sandboxStreams.get(toolCallId)
// Inside CodeExecutionPanel:
const live = sandboxStreams.get(toolCallId)
const stdoutLines = live?.stdout ?? persistedOutput?.stdout_lines ?? []
const stderrLines = live?.stderr ?? persistedOutput?.stderr_lines ?? []
const status: 'pending' | 'running' | 'success' | 'error' | 'timeout' =
  live ? 'running' : (persistedStatus ?? 'success')
```

**Key conventions to replicate:**
- `useState` for `codeExpanded` (default `false` per D-P11-09).
- `useI18n()` for every user-visible string (matches `ToolCallCard`'s `t('chat.source.web')` pattern at L14-16).
- `border rounded-md` outer shell; `border-b border-border` between internal sections.
- Solid `bg-card` / `bg-muted/50` / `bg-zinc-900` surfaces only — NEVER `backdrop-blur` (CLAUDE.md design rule, UI-SPEC §Glass Rule).
- Lucide icons sized `h-3 w-3` (badges) / `h-3.5 w-3.5` (status) / `h-4 w-4` (file icon) per UI-SPEC §Spacing Scale exceptions.
- Tabular-nums for the timer (`text-xs text-muted-foreground tabular-nums`).
- For the Download button reuse `<Button size="sm" variant="default" />` from `frontend/src/components/ui/button.tsx` (already in the project — see `frontend/src/components/ui/` listing).

---

### 2. `frontend/src/components/chat/ToolCallCard.tsx` (MODIFY — switch in `ToolCallList`)

**Analog:** self — the existing `ToolCallList.map` block.

**Existing JSX excerpt** (lines 119-136, exact text — splice site):
```tsx
interface ToolCallListProps {
  toolCalls: ToolCallRecord[]
}

export function ToolCallList({ toolCalls }: ToolCallListProps) {
  return (
    <div className="space-y-0.5">
      {toolCalls.map((tc, i) => (
        <ToolCallCard
          key={i}
          tool={tc.tool}
          input={tc.input}
          output={tc.output as Record<string, unknown>}
        />
      ))}
    </div>
  )
}
```

**Existing TOOL_CONFIG excerpt** (lines 6-10, the planner must add a `'execute_code'` entry per UI-SPEC §"MODIFIED: ToolCallCard.tsx"):
```typescript
const TOOL_CONFIG: Record<string, { icon: typeof Database; label: string }> = {
  search_documents: { icon: Search, label: 'Document Search' },
  query_database: { icon: Database, label: 'Database Query' },
  web_search: { icon: Globe, label: 'Web Search' },
}
```

**Key conventions to replicate:**
- `toolCalls.map((tc, i) => ...)` index-based key is preserved for legacy non-`execute_code` tools.
- For `execute_code` panels, switch the key to `tc.tool_call_id ?? i` (UI-SPEC §Multi-Call: "React key from the SSE-provided UUID guarantees stable identity").
- Per UI-SPEC §Vertical Stack Layout: render two segregated lists rather than mixing gap values. The existing `space-y-0.5` is preserved for the generic-card list; sandbox panels get their own `flex flex-col gap-6` wrapper.
- The legacy fallback for `execute_code` calls without `tool_call_id` (D-P11-03) drops through to a generic `ToolCallCard` using a new `TOOL_CONFIG.execute_code = { icon: Terminal, label: 'Code Execution' }` entry.
- The new optional `status?: 'success' | 'error' | null` prop on `ToolCallCard` (UI-SPEC §"MODIFIED: ToolCallCard.tsx") is a progressive enhancement — existing callers compile unchanged.

**Live-buffer prop wiring:** `ToolCallList` accepts a new optional `sandboxStreams?: Map<string, {stdout: string[], stderr: string[]}>` prop. `MessageView.tsx` L100-101 currently calls `<ToolCallList toolCalls={msg.tool_calls.calls} />` — it must pass `sandboxStreams` from `useChatState` for the actively-streaming message only.

---

### 3. `frontend/src/hooks/useChatState.ts` (MODIFY — add SSE cases + `sandboxStreams` state)

**Analog:** self — the existing event-dispatch switch at L161-205.

**Existing SSE switch excerpt** (lines 161-205, exact splice site):
```typescript
for (const line of lines) {
  if (!line.startsWith('data: ')) continue
  let event: SSEEvent
  try {
    event = JSON.parse(line.slice(6)) as SSEEvent
  } catch {
    continue
  }

  if (event.type === 'thread_title') {
    setThreads((prev) =>
      prev.map((t) =>
        t.id === event.thread_id ? { ...t, title: event.title } : t
      )
    )
  } else if (event.type === 'agent_start') {
    setActiveAgent({ agent: event.agent, display_name: event.display_name })
  } else if (event.type === 'agent_done') {
    setActiveAgent(null)
  } else if (event.type === 'tool_start') {
    setActiveTools((prev) => [...prev, event])
  } else if (event.type === 'tool_result') {
    setActiveTools((prev) => {
      const idx = prev.findIndex((t) => t.tool === event.tool)
      if (idx >= 0) return [...prev.slice(0, idx), ...prev.slice(idx + 1)]
      return prev
    })
    setToolResults((prev) => [...prev, event])
  } else if (event.type === 'redaction_status') {
    // Phase 5 D-88: status spinner state during the buffer window.
    setRedactionStage(event.stage)
    if (event.stage === 'blocked') {
      setStreamingContent('')
      assistantContent = ''
    }
  } else {
    const delta = 'delta' in event ? event.delta : ''
    const isDone = 'done' in event ? event.done : false
    if (!isDone && delta) {
      assistantContent += delta
      setStreamingContent(assistantContent)
    }
  }
}
```

**State declaration analog** (lines 18-19, the splice site for new `sandboxStreams`):
```typescript
const [activeTools, setActiveTools] = useState<ToolStartEvent[]>([])
const [toolResults, setToolResults] = useState<ToolResultEvent[]>([])
```

**Post-stream refetch + cleanup analog** (lines 209-228, where new `setSandboxStreams(new Map())` clear belongs):
```typescript
// Refetch all messages and rebuild tree
const { data } = await supabase
  .from('messages')
  .select('*')
  .eq('thread_id', threadId)
  .order('created_at', { ascending: true })

const all = (data as Message[]) ?? []
setAllMessages(all)
rebuildVisibleMessages(all, branchSelectionsRef.current)
loadThreads()
} finally {
  setIsStreaming(false)
  setStreamingContent('')
  setActiveTools([])
  setToolResults([])
  setActiveAgent(null)
  // ...
}
```

**Hook return-shape analog** (lines 252-276, where `sandboxStreams` must be exposed to consumers):
```typescript
return {
  threads,
  activeThreadId,
  // ...
  activeTools,
  toolResults,
  activeAgent,
  redactionStage,
  // ...
}
```

**Key conventions to replicate:**
- New cases follow `else if (event.type === 'code_stdout') { ... } else if (event.type === 'code_stderr') { ... }` form — match existing `else-if` chain style exactly (do NOT introduce a `switch` statement; the file uses `if/else if`).
- Append-immutable update: `setSandboxStreams((prev) => { const next = new Map(prev); const cur = next.get(event.tool_call_id) ?? { stdout: [], stderr: [] }; next.set(event.tool_call_id, { ...cur, stdout: [...cur.stdout, event.line] }); return next })` — mirrors `setActiveTools((prev) => [...prev, event])` immutability style at L181.
- Cleanup happens in the `finally` block at L219-228: add `setSandboxStreams(new Map())` alongside the existing `setActiveTools([])` / `setToolResults([])` resets.
- `setRedactionStage(null)` reset at L86 (`handleSelectThread`) and L134 (`sendMessageToThread`) must include `setSandboxStreams(new Map())` reset for thread-switch correctness.
- Expose `sandboxStreams` in the hook's return object alongside `activeTools` (L260) so `MessageView` / `ToolCallList` can read it.

---

### 4. `frontend/src/lib/database.types.ts` (MODIFY — add union variants)

**Analog:** self — the existing `RedactionStatusEvent` and `SSEEvent` union at L68-80.

**Existing union excerpt** (lines 68-80, exact splice site):
```typescript
// Phase 5 D-88 + D-94: redaction status events.
// 'anonymizing' fires once per turn after agent_start (covers history anon + tool-loop iterations).
// 'deanonymizing' fires once per turn after the buffer completes (before de-anon runs).
// 'blocked' fires on egress filter trip (D-94) — turn aborts cleanly.
export interface RedactionStatusEvent {
  type: 'redaction_status'
  stage: 'anonymizing' | 'deanonymizing' | 'blocked'
}

export type SSEEvent =
  | DeltaEvent
  | ToolStartEvent
  | ToolResultEvent
  | AgentStartEvent
  | AgentDoneEvent
  | ThreadTitleEvent
  | RedactionStatusEvent  // Phase 5 D-88
```

**Existing `ToolCallRecord` excerpt** (lines 11-16, the splice site for new fields per D-P11-08):
```typescript
export interface ToolCallRecord {
  tool: string
  input: Record<string, unknown>
  output: Record<string, unknown> | string
  error?: string | null
}
```

**Existing `Message.tool_calls` excerpt** (line 24):
```typescript
tool_calls?: { agent?: string | null; calls: ToolCallRecord[] } | null
```

**Key conventions to replicate:**
- Each new variant is a top-level `export interface` with discriminated `type` literal (matches `ToolStartEvent` / `RedactionStatusEvent` exactly).
- Phase comment block above the new variants — mirror the `// Phase 5 D-88 + D-94: ...` block style.
- Add `| CodeStdoutEvent | CodeStderrEvent` to the `SSEEvent` union with `// Phase 11 SANDBOX-07` end-of-line comment, matching the `// Phase 5 D-88` annotation style.
- Extend `ToolCallRecord` with `tool_call_id?: string | null` and `status?: 'success' | 'error' | 'timeout' | null` — both nullable so legacy persisted rows still typecheck (CONTEXT.md §Specifics: "Mark `tool_call_id` and `status` as nullable").
- The new variant payload shape is `{ type: 'code_stdout' | 'code_stderr', line: string, tool_call_id: string }` per Phase 10 D-P10-06 and CONTEXT.md.

---

### 5. `backend/app/models/tools.py` (MODIFY — add fields + Pydantic field_validator)

**Analog A (self):** existing `ToolCallRecord` and `ToolCallSummary` definitions.

**Analog B (validator style):** `backend/app/routers/skills.py` `field_validator` usage @ L37-44.

**Existing model excerpt** (full file, lines 1-15):
```python
from pydantic import BaseModel


class ToolCallRecord(BaseModel):
    """Persisted record of a single tool execution."""
    tool: str
    input: dict
    output: dict | str
    error: str | None = None


class ToolCallSummary(BaseModel):
    """Stored in messages.tool_calls JSONB."""
    agent: str | None = None
    calls: list[ToolCallRecord]
```

**Validator pattern excerpt** (from `skills.py` L37-44):
```python
    @field_validator("name")
    @classmethod
    def validate_name(cls, v):
        if not NAME_REGEX.match(v):
            raise ValueError(
                "Invalid name: must match ^[a-z][a-z0-9]*(-[a-z0-9]+)*$"
            )
        return v
```

**Key conventions to replicate:**
- Import-additions order: `from pydantic import BaseModel, field_validator` and `from typing import Literal` (project uses 3.10+ pipe syntax `str | None`; `Literal` lives in `typing`).
- Add new fields AFTER the existing `error: str | None = None` line per D-P11-08 to preserve positional order for any callers using positional construction (chat.py uses keyword construction at L427-428 and L437 — both are safe but field order is still meaningful for serialization stability).
- `tool_call_id: str | None = None` — nullable default for legacy rows (D-P11-03).
- `status: Literal["success", "error", "timeout"] | None = None` — exactly the three Phase-10 sandbox states; non-sandbox calls use `success`/`error` only (CONTEXT.md D-P11-08).
- Truncation `field_validator` lives on `output` and head-truncates serialized result to 50 KB with marker `"\n…[truncated, N more bytes]\n"` (D-P11-04, D-P11-11). Constants:
  - `MAX_OUTPUT_BYTES = 50_000`  (50 KB literal — CONTEXT.md §Decisions D-P11-04)
  - Single ellipsis is U+2026 (`…`) per CONTEXT.md §Specifics.
- The validator must serialize `dict` values via `json.dumps(v, ensure_ascii=False)` before measuring length, then re-parse if input was a dict; or operate string-only and let the caller pass already-serialized output. Recommend string-only path: validator runs on the serialized form by accepting `dict | str` and converting internally.
- Use `@field_validator("output")` + `@classmethod` exactly as `skills.py` L37-39 shows.
- Do NOT add a `summary` field (deferred per CONTEXT.md §Deferred).
- `ToolCallSummary` is NOT modified — the new fields are inside each `ToolCallRecord` element of `calls: list[ToolCallRecord]`.

---

### 6. `backend/app/routers/chat.py` (MODIFY — 4 sub-edits in one file)

#### 6a. History SELECT widening (lines 110-139)

**Existing branch-aware excerpt** (lines 110-129):
```python
    # Load chat history — branch-aware when parent_message_id is provided
    if body.parent_message_id:
        # Branch mode: walk ancestor chain from the specified parent
        all_messages = (
            client.table("messages")
            .select("id, role, content, parent_message_id")
            .eq("thread_id", body.thread_id)
            .eq("user_id", user["id"])
            .execute()
        ).data or []
        msg_map = {m["id"]: m for m in all_messages}
        chain = []
        visited: set[str] = set()
        current_id = body.parent_message_id
        while current_id and current_id in msg_map and current_id not in visited:
            visited.add(current_id)
            chain.append(msg_map[current_id])
            current_id = msg_map[current_id].get("parent_message_id")
        chain.reverse()
        history = [{"role": m["role"], "content": m["content"]} for m in chain]
```

**Existing flat-mode excerpt** (lines 130-139):
```python
    else:
        # Flat mode: all messages in order (existing behavior)
        history = (
            client.table("messages")
            .select("role, content")
            .eq("thread_id", body.thread_id)
            .eq("user_id", user["id"])
            .order("created_at")
            .execute()
        ).data or []
```

**Key conventions for the patch:**
- BOTH SELECT calls widen to include `tool_calls`: `.select("id, role, content, parent_message_id, tool_calls")` (branch mode) and `.select("role, content, tool_calls")` (flat mode).
- Replace the final list comprehension at L129 (`history = [{"role": m["role"], "content": m["content"]} for m in chain]`) with the triplet-expansion loop from CONTEXT.md §Specifics:
  ```python
  history = []
  for row in chain:  # or for m in flat_data
      tc = row.get("tool_calls") or {}
      calls = tc.get("calls") or []
      if calls and all(c.get("tool_call_id") for c in calls):
          history.append({
              "role": "assistant",
              "content": "",
              "tool_calls": [
                  {"id": c["tool_call_id"], "type": "function",
                   "function": {"name": c["tool"],
                                "arguments": json.dumps(c["input"])}}
                  for c in calls
              ],
          })
          for c in calls:
              history.append({"role": "tool",
                              "tool_call_id": c["tool_call_id"],
                              "content": json.dumps(c["output"]) if not isinstance(c["output"], str) else c["output"]})
          if row["content"]:
              history.append({"role": "assistant", "content": row["content"]})
      else:
          history.append({"role": row["role"], "content": row["content"]})
  ```
- Apply the SAME loop to BOTH branches (branch mode L129 and flat mode L139) per D-P11-07. Extract into a local helper function `_expand_history_row(row)` to avoid duplication.

#### 6b. ToolCallRecord construction — single-agent branch (lines 427-438)

**Existing excerpt** (lines 427-438):
```python
                    tool_records.append(ToolCallRecord(
                        tool=func_name, input=func_args, output=tool_output
                    ))
                except EgressBlockedAbort:
                    # Bubble up to event_generator's outer handler — DO NOT
                    # swallow here (D-94: trip aborts the entire turn).
                    raise
                except Exception as e:
                    tool_output = {"error": str(e)}
                    tool_records.append(ToolCallRecord(
                        tool=func_name, input=func_args, output={}, error=str(e)
                    ))
```

**Key conventions for the patch:**
- Both `ToolCallRecord(...)` constructors gain `tool_call_id=tc["id"]` and `status=...` kwargs (CONTEXT.md §Integration Points #2).
- Status derivation per CONTEXT.md D-P11-08:
  - For `func_name == "execute_code"`: derive from `tool_output.get("error_type")` and `tool_output.get("exit_code")` — `"timeout"` if `error_type == "timeout"`, `"error"` if `exit_code != 0` or `error_type` truthy, else `"success"`.
  - For non-sandbox tools (success path): `status="success"`.
  - For exception-caught path (L434-438): `status="error"`.
- `tc["id"]` is already in scope — it's the `tool_call_id` from the OpenAI tool-call dict, used at L458 (`messages.append({"role": "tool", "tool_call_id": tc["id"], ...})`) and L974.

#### 6c. ToolCallRecord construction — multi-agent branch (lines 956-960)

**Existing excerpt** (lines 953-960):
```python
            except EgressBlockedAbort:
                raise
            except Exception as e:
                tool_output = {"error": str(e)}
                from app.models.tools import ToolCallRecord
                tool_records.append(ToolCallRecord(
                    tool=func_name, input=func_args, output={}, error=str(e)
                ))
```

**Key conventions for the patch:**
- Mirror the same `tool_call_id=tc["id"]` and `status=...` kwargs additions made in 6b. There's only the one constructor in this branch's exception handler (the success-path constructor for the multi-agent branch lives elsewhere — search for it during planning; based on the structural symmetry it must also exist around L900-940 paired with the `messages.append({"role": "tool", ...})` at L972-976).
- The inline `from app.models.tools import ToolCallRecord` import on L957 is preserved as-is (no change needed since the model is the same).

#### 6d. Redaction batch — reconstructed tool messages flow through anonymizer (lines 477-497)

**Existing excerpt** (lines 477-497):
```python
        redaction_on = bool(sys_settings.get("pii_redaction_enabled", True))
        redaction_service = get_redaction_service()
        if redaction_on:
            # D-86: ConversationRegistry.load called ONCE per turn (chokepoint).
            registry = await ConversationRegistry.load(body.thread_id)
            # D-93: single batched history anon under one asyncio.Lock.
            # Order is preserved by redact_text_batch (T-05-01-2 mitigation),
            # so we rebuild history items by index.
            raw_strings = [m["content"] for m in history] + [body.message]
            anonymized_strings = await redaction_service.redact_text_batch(
                raw_strings, registry
            )
            anonymized_history = [
                {**h, "content": a}
                for h, a in zip(history, anonymized_strings[:-1])
            ]
            anonymized_message = anonymized_strings[-1]
        else:
            registry = None
            anonymized_history = history
            anonymized_message = body.message
```

**Key conventions for the patch (D-P11-10):**
- Because the history-expansion in 6a now produces messages with `role: "tool"` and `content: json.dumps(...)`, the existing line 485 `raw_strings = [m["content"] for m in history] + [body.message]` ALREADY captures them — `m["content"]` is present on tool messages (it's the JSON-stringified output).
- The `zip(history, anonymized_strings[:-1])` rebuild at L489-492 ALREADY works because the expansion produces 1 dict per output position. **Verify in the plan:** every reconstructed message must have a `content` key (assistant rows with `tool_calls` MUST set `"content": ""` not omit it — see the recommended expansion code in 6a — to keep the index alignment safe).
- Assistant tool-call rows have empty `content`; redact_text_batch on `""` returns `""` — no behavior change.
- Tool messages with `"content": json.dumps(c["output"])` flow through Presidio just like user/assistant content. This is the desired D-89 invariant: real PII never reaches the cloud LLM, even from historical tool outputs that were originally stored when redaction was OFF.
- No new code path required at L485 itself — only the precondition that 6a's expansion always emits a `content` key.

---

## Shared Patterns

### 2026 Calibrated Restraint design system (frontend, all new components)

**Source:** `CLAUDE.md` (project root) §"Design System (2026 Calibrated Restraint)" + `frontend/src/index.css` `:root` token block + UI-SPEC §Color, §Glass Rule.

**Apply to:** `CodeExecutionPanel.tsx`, the `ToolCallCard.tsx` switch, any new visual surface this phase.

**Hard rules:**
- NO `backdrop-blur` on persistent panels (`CodeExecutionPanel` is persistent — solid `bg-card` / `bg-muted/50` / `bg-zinc-900` only).
- NO gradients on buttons/panels (gradients are reserved exclusively for user chat bubbles per `CLAUDE.md`).
- Flat solid buttons via the existing `frontend/src/components/ui/button.tsx` shadcn primitive — `<Button size="sm" variant="default" />`.
- Zinc-neutral base + purple accent (`--primary`) — UI-SPEC §Color section codifies the exact tokens.
- Status icon size canonical: `h-3.5 w-3.5` (matches `ToolCallCard.tsx` L58 / L60).

### Auth — `get_current_user` dependency (backend, both `chat.py` edits)

**Source:** `backend/app/routers/code_execution.py` L115, `backend/app/routers/chat.py` L73 (existing).

**Apply to:** All chat.py changes — already present (`user: dict = Depends(get_current_user)`). No new auth code required this phase.

### Audit — `log_action` (backend)

**Source:** `backend/app/routers/chat.py` L411-426 (existing pattern).

**Apply to:** No new audit calls needed this phase. The existing `web_search_dispatch` audit is unchanged. CodeExecutionPanel renders persisted data only; no new mutation surface.

### Pydantic validator style

**Source:** `backend/app/routers/skills.py` L37-44.

**Apply to:** `backend/app/models/tools.py` 50 KB head-truncate `field_validator` on `output`.

```python
    @field_validator("output")
    @classmethod
    def truncate_output(cls, v):
        # implementation per D-P11-04 / D-P11-11
        return v
```

### i18n integration

**Source:** `frontend/src/i18n/I18nContext.tsx` (already present), `ToolCallCard.tsx` L4 + L13-16 usage pattern.

**Apply to:** `CodeExecutionPanel.tsx`. Every user-visible string uses `const { t } = useI18n()` then `t('sandbox.status.running')` etc. The keys are enumerated in UI-SPEC §Copywriting Contract — they must be added to `frontend/src/i18n/translations.ts` under both `id` and `en` locales.

### `apiFetch` for backend calls

**Source:** `frontend/src/lib/api.ts` L5-28 (existing).

**Apply to:** `CodeExecutionPanel.tsx` file-download click handler:
```typescript
const res = await apiFetch(`/code-executions?thread_id=${threadId}`)
const json = await res.json()
const fresh = json.data.find(...).files.find(f => f.filename === filename).signed_url
window.open(fresh, '_blank')
```
NOTE: the existing `code_execution.py` router exposes `GET /code-executions?thread_id=` (a LIST endpoint, not `GET /{id}` per UI-SPEC §"File Download Click"). The planner should specify the actual call signature against the real router contract: `GET /code-executions?thread_id=<thread>` returns `{data: [CodeExecutionResponse, ...], count: N}`. To resolve a fresh signed_url for a specific execution, call this endpoint and find the row by `id` (which is `tool_call_id`'s parent execution) — the planner needs to verify whether `code_executions.id` ≡ `tool_call_id` or whether a separate id is on the `ToolCallRecord` payload. If a per-execution `GET /code-executions/{id}` is needed, the planner may add it (small router patch, RLS-aligned).

---

## No Analog Found

None. All six change sites have direct in-repo analogs.

---

## Metadata

**Analog search scope:**
- `frontend/src/components/chat/` (ToolCallCard, AgentBadge, MessageView)
- `frontend/src/hooks/useChatState.ts`
- `frontend/src/lib/database.types.ts`, `frontend/src/lib/api.ts`
- `frontend/src/components/ui/` (button.tsx confirmed present)
- `frontend/src/i18n/` (I18nContext, translations)
- `backend/app/models/tools.py`
- `backend/app/routers/chat.py` (lines 100-140, 410-500, 700-720, 940-980)
- `backend/app/routers/code_execution.py` (full file — 145 lines)
- `backend/app/routers/skills.py` (lines 30-65 — Pydantic validator reference)

**Files scanned:** 9
**Pattern extraction date:** 2026-05-01
**Project skills referenced:** None invoked this phase. (No new migration, no new test infra invocation; the planner may reference `/run-api-tests` in plan acceptance steps if backend tests are added.)

---

*Phase 11 — Code Execution UI & Persistent Tool Memory*
*Pattern map authored: 2026-05-01*
