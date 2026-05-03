# Phase 21: Batched Parallel Sub-Agents + Human-in-the-Loop - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-04
**Phase:** 21-batched-parallel-sub-agents-human-in-the-loop
**Areas discussed:** HIL resume flow, Batch output format, Batch streaming UX, Per-item failure handling

---

## HIL Resume Flow

| Option | Description | Selected |
|--------|-------------|----------|
| Exclude paused from 409 | Change the 409 condition to only block when status IN ('pending','running') — 'paused' falls through to a new HIL resume branch. Mirrors Phase 19 ask_user pattern. Zero new endpoints. | ✓ |
| Dedicated resume endpoint | POST /threads/{id}/harness/resume with {answer}. 409 stays as-is for all active statuses. Frontend detects paused state and routes to the resume endpoint. | |
| You decide | Claude picks the cleanest option. | |

**User's choice:** Exclude paused from 409 (mirrors Phase 19 ask_user pattern)
**Notes:** None — straightforward alignment with the established Phase 19 resume precedent.

---

| Option | Description | Selected |
|--------|-------------|----------|
| New run_harness_engine call with start_from | Pass start_phase_index=N+1 to run_harness_engine. Engine skips phases 0..N (already in phase_results), writes the HIL answer, and runs phases N+1..end in the same new SSE stream. | ✓ |
| HIL-specific resume function | Separate run_harness_resume() function that handles HIL-specific logic then hands off to the existing engine loop. | |
| You decide | Claude picks based on the existing engine architecture. | |

**User's choice:** New run_harness_engine call with start_from
**Notes:** `start_phase_index: int = 0` parameter added to `run_harness_engine` — defaults to 0 for backward compatibility.

---

| Option | Description | Selected |
|--------|-------------|----------|
| delta events + harness_human_input_required + done | Engine streams question as normal delta events, then emits harness_human_input_required with question metadata, then done:true. Status transitions to 'paused' before stream closes. | ✓ |
| harness_human_input_required only (no deltas) | Question delivered only via the event payload — frontend renders it from the event, not from a delta. | |

**User's choice:** delta events + harness_human_input_required + done
**Notes:** Preserves HIL-02 ("normal chat message") contract. Question persists as an assistant message bubble in thread history.

---

## Batch Output Format

| Option | Description | Selected |
|--------|-------------|----------|
| JSONL append-only | Each completed sub-agent appends one line: {"item_index": N, "result": {...}, "status": "ok"\|"failed"}. Resume scans file, collects done indices, runs only missing ones. Atomic per-item writes. | ✓ |
| JSON object keyed by index | Single JSON file {"0": {result}, "1": {result}}. Written atomically on batch completion. Not resumable mid-batch. | |
| Separate per-item workspace files | batch-item-0.json, batch-item-1.json, etc. Trivially resumable but creates many workspace entries. | |

**User's choice:** JSONL append-only
**Notes:** Atomic per-item appends are safe under concurrent asyncio.gather execution.

---

| Option | Description | Selected |
|--------|-------------|----------|
| Phase 21 writes both JSONL + final JSON | After all batches complete, engine does a merge pass and writes a clean risk-analysis.json (array). Phase 22 reads the clean JSON. JSONL stays as resume artifact. | ✓ |
| Phase 22 reads JSONL directly | No merge step — Phase 22 parses JSONL itself. Couples every downstream consumer to the JSONL format. | |
| You decide | Claude picks based on Phase 22 consumption pattern. | |

**User's choice:** Phase 21 writes both JSONL + final JSON
**Notes:** Two files per batch phase: `{name}.jsonl` (internal resume artifact) + `{name}.json` (final clean output for Phase 22).

---

## Batch Streaming UX

| Option | Description | Selected |
|--------|-------------|----------|
| New harness_batch_item_start/complete events | Each sub-agent emits item-level events with item_index and items_total. Frontend adds batchProgress slice to useChatState. HarnessBanner shows "Analyzing clause N/M". | ✓ |
| Extend task_start/task_complete with batch_index | No new event types — add batch_index and batch_total fields to existing task events. Overloads Phase 19's task semantics. | |
| Phase-start event with running_count updates | Engine re-emits harness_phase_start with updated counter fields. Pollutes phase-level event with item-level counters. | |

**User's choice:** New harness_batch_item_start/complete events
**Notes:** Implements the Phase 20 reserved event constants.

---

| Option | Description | Selected |
|--------|-------------|----------|
| Extend existing components only | Add batchProgress slice to useChatState. HarnessBanner reads it for "Analyzing clause N/M". TaskPanel already renders sub-agent cards from Phase 19 — no new component. | ✓ |
| New BatchProgressPanel component | Dedicated panel showing N/M grid of clause items with status badges. More visual but adds another panel to maintain. | |

**User's choice:** Extend existing components only
**Notes:** No new frontend component. Vitest tests for new slice + banner variant.

---

## Per-Item Failure Handling

| Option | Description | Selected |
|--------|-------------|----------|
| Continue with failure marker | Failed item written to JSONL as {status: "failed", error: {...}}. Batch continues. harness_phase_complete emitted with failed_count field. | ✓ |
| Abort entire batch phase | Any sub-agent failure triggers harness_phase_error and engine stops. Impractical for 15+ clause contracts. | |
| Configurable threshold (max_failures field) | Add max_failures: int to PhaseDefinition. Flexible but adds config surface and test matrix complexity. | |

**User's choice:** Continue with failure marker
**Notes:** Consistent with STATUS-03 (no auto-retry). Phase 22 harness definitions handle partial results.

---

| Option | Description | Selected |
|--------|-------------|----------|
| Skip failed items on resume | Resume reads JSONL, skips indices with status='ok' OR status='failed'. No implicit retry. STATUS-03 consistent. | ✓ |
| Retry failed items on resume | Resume only skips status='ok'; failed items re-queued. Inconsistent with STATUS-03 no-retry rule. | |

**User's choice:** Skip failed items on resume
**Notes:** User must cancel + re-trigger for a full fresh run if retries are needed.

---

## Claude's Discretion

- **asyncio.Queue fan-in multiplexer pattern** — standard Python fan-in; mirrors Phase 19's executor SSE queue at `chat.py:455+`.
- **item_index is globally unique across all batches** — not per-batch. Resume re-chunks remaining indices.
- **HIL question generation** — uses existing `phase.system_prompt_template` + `workspace_inputs`; Pydantic output `{question: str}`. No new PhaseDefinition fields.
- **Smoke harness extension** — extends `smoke_echo.py` to 4 phases (adds llm_human_input + llm_batch_agents). Uses existing `HARNESS_SMOKE_ENABLED` flag.
- **No new migration** — `status='paused'` already in migration 042 CHECK constraint.
- **No new feature flag** — `HARNESS_ENABLED` already gates all harness code.

## Deferred Ideas

- Contract Review domain harness + DOCX deliverable — Phase 22
- Configurable max_failures threshold — post-Phase 22 if needed
- Re-run only failed batch items without full restart — deferred
- Per-item progress grid in plan panel — HarnessBanner N/M text sufficient for v1.3
