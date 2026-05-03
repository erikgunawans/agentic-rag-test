# Phase 20: Harness Engine Core + Gatekeeper + Post-Harness + File Upload + Locked Plan Panel - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-03
**Phase:** 20-harness-engine-core-gatekeeper-post-harness-file-upload-lock
**Areas discussed:** Harness state machine + migration 042, Gatekeeper LLM contract + harness selection, Post-harness summary + Locked Plan Panel UX, File-upload UX + extraction timing + engine smoke-test strategy
**Mode:** default (interactive, single-question turns)

---

## Harness State Machine + Migration 042

### Q1: How should harness_runs relate to Phase 19's agent_runs table?

| Option | Description | Selected |
|--------|-------------|----------|
| Separate table, mirror schema | New `harness_runs` table with harness-specific columns reusing agent_runs state-machine pattern (status enum, partial unique on active row, RLS thread-scoped). Phase 19 untouched. | ✓ |
| Extend agent_runs with harness columns | Add nullable harness_type/current_phase/phase_results/input_file_ids to agent_runs. Single table for all paused backend execution. | |
| Separate table, separate state machine | harness_runs uses different status enum and separate resume-detection branch in chat.py. Cleanest isolation but two near-identical state machines drift over time. | |

**User's choice:** Separate table, mirror schema (Recommended)
**Notes:** Phase 19 stays untouched, Plan Panel locking + harness-specific fields stay first-class. Two clean tables, one code pattern.

---

### Q2: When a harness_run is active, what should happen if the user sends a normal chat message?

| Option | Description | Selected |
|--------|-------------|----------|
| Reject — 'harness in progress' | Backend returns structured response, frontend shows banner with Cancel button. One workflow per thread at a time. | ✓ |
| Queue — deliver after harness completes | Message persisted but loop holds it until harness reaches terminal state. More complex (queue table, ordering). | |
| Treat as Cancel signal | Any new user message during active harness aborts the run. Destructive — user may lose work. | |
| Route to llm_human_input phase if paused, else reject | Bridges into Phase 21 but adds branching for behavior we don't fully exercise until Phase 21. | |

**User's choice:** Reject — 'harness in progress' (Recommended)

---

### Q3: How should the user cancel an in-flight harness run?

| Option | Description | Selected |
|--------|-------------|----------|
| Cancel button in Plan Panel header | Visible Cancel next to lock icon. Sets status='cancelled', cancellation event checked between rounds/phases. Partial workspace artifacts preserved. | ✓ |
| Slash command /cancel-harness | CLI-friendly but discoverability poor for legal users. | |
| Both: panel button AND /cancel-harness | Belt-and-suspenders. More surface area, more tests. | |

**User's choice:** Cancel button in Plan Panel header (Recommended)

---

### Q4: What does the messages.harness_mode text column carry?

| Option | Description | Selected |
|--------|-------------|----------|
| Harness type only, e.g. 'contract-review' | Simple discriminator on assistant messages produced by harness flow. NULL for normal/deep-mode. | ✓ |
| Harness type + phase index, e.g. 'contract-review:5' | Per-message granularity. Per-phase tag rarely meaningful. | |
| JSONB with type, phase, run_id | Overkill — harness_runs.id provides join path. | |

**User's choice:** Harness type only, e.g. 'contract-review' (Recommended)

---

## Gatekeeper LLM Contract + Harness Selection

### Q5: When should the gatekeeper LLM run?

| Option | Description | Selected |
|--------|-------------|----------|
| Only when harness is registered AND no active/completed run for thread | Per PRD GATE-01. Adds ~one extra small LLM call per pre-harness message. Normal/post-harness chats skip gatekeeper entirely. | ✓ |
| Every user message in every thread | Universal pass. Highest coverage but adds latency + cost to every chat. | |
| Only when user explicitly opts in via 'Start harness' affordance | Most predictable but breaks conversational discoverability the PRD designed for. | |

**User's choice:** Only when a harness is registered AND no active/completed run exists for thread (Recommended)

---

### Q6: How should the gatekeeper know WHICH harness to fire?

| Option | Description | Selected |
|--------|-------------|----------|
| Single registered harness for v1.3, gatekeeper fires it directly | Engine registry holds N; gatekeeper instance built per-harness. v1.3 has only contract-review (Phase 22). | ✓ |
| Multi-harness picker now — gatekeeper classifies intent then routes | Future-proof but premature for one harness. | |
| Per-thread sticky harness binding | Requires UI for binding selection — deferred surface area. | |

**User's choice:** Single registered harness for v1.3, gatekeeper fires it directly (Recommended)

---

### Q7: How should the [TRIGGER_HARNESS] sentinel be detected?

| Option | Description | Selected |
|--------|-------------|----------|
| Buffer and check end-of-stream, suppress sentinel from output | On `done` from LLM, check trailing [TRIGGER_HARNESS]. If yes — strip, flush remaining, emit harness_phase_start. Sentinel never reaches client. | ✓ |
| Stream tokens live, detect+strip sentinel inline | More responsive but tricky tokenization edge cases. | |
| Require sentinel on its own line + JSON envelope | Stricter parse but adds prompt-engineering brittleness. | |

**User's choice:** Buffer and check end-of-stream, suppress sentinel from output (Recommended)

---

### Q8: Should gatekeeper assistant turns be persisted as normal messages?

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — persist with harness_mode='contract-review' | Reload-safe. Backend reconstructs prior gatekeeper turns from messages table when computing prerequisites. | ✓ |
| No — only persist final user trigger message + post-harness summary | Cheaper but user can't see upload-prompting conversation after refresh. | |
| Yes, but with separate gatekeeper_conversations table | Adds a fourth table — marginal benefit. | |

**User's choice:** Yes — persist with harness_mode='contract-review' (Recommended)

---

## Post-Harness Summary + Locked Plan Panel UX

### Q9: How should the post-harness summary be emitted relative to harness_complete?

| Option | Description | Selected |
|--------|-------------|----------|
| Inline stream in SAME SSE response, right after harness_complete | Same SSE generator makes separate LLM call with phase_results in system prompt and streams ~500-token summary as new assistant message. | ✓ |
| Trigger via post_execute callback on the LAST phase | Reuses post_execute hook but tangles two concerns. | |
| Wait for next user message, then prepend summary | Predictable but creates dead air after harness completes. | |

**User's choice:** Inline stream in SAME SSE response, right after harness_complete (Recommended)

---

### Q10: When phase_results exceed 30k chars, how to truncate for the post-harness LLM system prompt?

| Option | Description | Selected |
|--------|-------------|----------|
| Keep last 2 phases full, summarize earlier phases via heading + first 200 chars | Per POST-05. Predictable, deterministic, no extra LLM call. | ✓ |
| Recursive LLM summarization of older phases | Better signal density but adds LLM call to every harness completion. | |
| Hard-truncate the middle | Simple but may chop in middle of clause analysis JSON. | |

**User's choice:** Keep last 2 phases full, summarize earlier phases via heading + first 200 chars (Recommended)

---

### Q11: What's the visual treatment of the 'locked' Plan Panel during a harness run?

| Option | Description | Selected |
|--------|-------------|----------|
| Lock icon + tooltip + Cancel button | Lock icon 🔒 + harness-type label + tooltip + Cancel button. List items render normally; no add/delete affordances. | ✓ |
| Distinct purple banner across panel header + lock icon | Stronger visual but breaks calibrated-restraint design system. | |
| Subtle: lock icon only, no tooltip | Minimal change but discoverability poor. | |

**User's choice:** Lock icon + tooltip + Cancel button (Recommended)

---

### Q12: What does 'locked' enforce technically?

| Option | Description | Selected |
|--------|-------------|----------|
| Both: LLM-side strip of write_todos/read_todos AND UI removes mutation affordances | Defense in depth. Backend rejects PUT/DELETE on agent_todos when active harness_run. | ✓ |
| LLM-side strip only (per PANEL-03 verbatim) | Smaller change but if future UI surface adds 'mark complete' lock breaks silently. | |
| UI-only — backend permits LLM mutations but Plan Panel ignores them visually | Cheapest but breaks PANEL-03 — LLM could overwrite engine's todo writes. | |

**User's choice:** Both: LLM-side strip of write_todos/read_todos AND UI removes mutation affordances (Recommended)

---

## File-Upload UX + Extraction Timing + Engine Smoke-Test Strategy

### Q13: Where should the file-upload affordance live in the chat UI?

| Option | Description | Selected |
|--------|-------------|----------|
| Always visible when WORKSPACE_ENABLED, paperclip icon in chat input toolbar | Intuitive (matches Slack/WhatsApp), works for both harness flows AND general workspace upload. | ✓ |
| Strict UPL-04: only when harness mode active | Stricter to spec but blocks general workspace upload. | |
| Modal triggered by '/upload' slash command | Discoverability poor for legal users. | |

**User's choice:** Always visible when WORKSPACE_ENABLED, paperclip icon in chat input toolbar (Recommended)
**Notes:** Small extension beyond UPL-04 verbatim — captured in CONTEXT.md D-13 so plan-phase doesn't undo it.

---

### Q14: When should DOCX/PDF text extraction happen?

| Option | Description | Selected |
|--------|-------------|----------|
| Lazy at harness-phase runtime | Upload endpoint stores binary + metadata only. Phase 1 (programmatic) runs python-docx/PyPDF2 at harness time. Per CR-01 spec. | ✓ |
| Eager at upload-time, store extracted text alongside binary | Faster harness Phase 1 but couples upload latency to extraction; wastes work if user never triggers harness. | |
| Both — eager extraction with lazy fallback | Most robust but two code paths. | |

**User's choice:** Lazy at harness-phase runtime (Recommended)

---

### Q15: Should scanned-PDF OCR fallback be wired into Phase 20's upload/extraction path, or deferred?

| Option | Description | Selected |
|--------|-------------|----------|
| Defer — Phase 20 extraction is text-layer-only, Phase 22 adds OCR if needed | Phase 1 of consumer harness writes structured error if extraction empty. Avoids re-implementing GPT-4o vision OCR path now. | ✓ |
| Wire RAG-03 vision-OCR fallback into Phase 20 extraction now | More robust upfront but increases Phase 20 scope by integration + tests + cost analysis. | |
| OCR via sandbox python-docx + Tesseract | Self-contained but adds tesseract to Dockerfile, large image. | |

**User's choice:** Defer — Phase 20 extraction is text-layer-only, Phase 22 adds OCR if needed (Recommended)

---

### Q16: Should Phase 20 ship a minimal 'smoke harness' to validate the engine end-to-end before Phase 22?

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — ship a 2-phase echo harness exercising programmatic + llm_single | Adds ~50 LOC: harnesses/smoke_echo.py. Lets us E2E test gatekeeper → harness_runs → phase dispatch → phase_results → post-harness summary → locked Plan Panel without waiting for Phase 22. CRITICAL for verifier. | ✓ |
| No — unit/integration tests only, E2E waits for Phase 22 | Phase 20 verification status will be 'human_needed' for criteria 1–6 until Phase 22. | |
| Yes — ship a 3-phase smoke harness covering programmatic + llm_single + llm_agent | More comprehensive (covers all three phase types). Adds ~100 LOC. | |

**User's choice:** Yes — ship a 2-phase echo harness exercising programmatic + llm_single (Recommended)
**Notes:** Smoke harness stays in registry as developer/admin diagnostic, gated behind HARNESS_SMOKE_ENABLED flag (default False in production).

---

## Claude's Discretion (sensible defaults locked in CONTEXT.md without re-asking)

- **Single feature flag `HARNESS_ENABLED`** (default `False`, Pydantic Settings) mirroring the v1.3 dark-launch precedent. Plus separate `HARNESS_SMOKE_ENABLED` flag controlling smoke harness registration.
- **Phase timeout defaults** from PRD: `llm_single` = 120s, `llm_agent` = 300s, `programmatic` = 60s. Configurable per `PhaseDefinition`.
- **Gatekeeper LLM provider** = same OpenRouter model as deep mode by default; per-feature override via existing admin settings UI.
- **`HarnessPrerequisites` dataclass shape** per PRD §Feature 2.2: `requires_upload`, `upload_description`, `harness_intro`, plus `accepted_mime_types`, `min_files=1`, `max_files=1`.
- **`PhaseDefinition` dataclass shape** per HARN-10 + `timeout_seconds` per-phase override.
- **`HarnessRegistry` directory layout:** `backend/app/harnesses/` with one file per harness; auto-import via `__init__.py`.
- **`progress.md` format (OBS-01):** workspace path `progress.md`, single writer = engine, append-only `## Phase N: <name>` sections with status emoji + 5-10 line intermediate summary per transition.
- **Post-harness summary token cap** = soft enforcement via prompt guidance (no hard token cut); plan-phase may add `max_tokens` kwarg if model overshoots.
- **i18n strings** (banner, tooltip, paperclip aria-label, error messages) — plan-phase / executor finalizes ID + EN; defaults follow Phase 19 D-26 conventions.
- **File upload size cap** = 25 MB.
- **`harness_runs.status='paused'`** reserved in CHECK constraint for Phase 21's `llm_human_input` but unused in Phase 20.

## Deferred Ideas

- `llm_batch_agents` and `llm_human_input` phase types — Phase 21.
- Contract Review domain harness, DOCX deliverable — Phase 22.
- OCR fallback for scanned PDFs (vision via GPT-4o, RAG-03 pattern) — Phase 22+ if UAT shows scanned uploads.
- Multi-harness picker / dispatcher — when 2+ user-facing harnesses exist (future milestone).
- `/cancel-harness` slash command — Cancel button sufficient.
- Per-thread sticky harness binding — gatekeeper-driven selection sufficient.
- Eager extraction at upload — lazy is the chosen pattern; eager could revisit if Phase 22 UAT shows latency.
- Cross-process advisory lock for harness_runs race conditions — async-lock D-31 carryover.
- Admin UI surface for HARNESS_ENABLED / HARNESS_SMOKE_ENABLED — env-var only in v1.3.
- System-settings cache integration for harness flags — alongside admin UI.
- Background / async harness runs (continue server-side after disconnect) — explicit Post-MVP per PRD.
- Auto-resume from `failed` state — out of scope per success criterion #6 + STATUS-03.
- Per-user harness preferences / customization — out of scope (global / system-defined).
- Mid-stream cancellation of `llm_human_input` — Phase 21 territory.
- `harness_runs` history admin UI / cleanup tooling — maintenance phase.
- Workspace garbage-collection for orphaned uploaded files — carried from Phase 18 deferred.
- Filename / document-metadata PII redaction — out of scope (already in PROJECT.md).
- 3-phase smoke harness adding `llm_agent` coverage — D-16 chose 2-phase; can grow during execution if needed.
