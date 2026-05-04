# Phase 22: Contract Review Harness + DOCX Deliverable - Context

**Gathered:** 2026-05-04
**Status:** Ready for planning

<domain>
## Phase Boundary

Build the **first domain-specific harness** on top of the engine + phase-type infrastructure shipped by Phases 20–21. This is an 8-phase deterministic Contract Review workflow that exercises every existing phase type end-to-end and produces a polished `.docx` executive report.

The phase types, batch dispatcher, HIL dispatcher, gatekeeper, post_execute hook, sandbox, and RAG tools are **already built and live in production as of Phase 21 (HEAD `956af2e`)**. Phase 22 is therefore mostly:

1. A new harness module — `backend/app/harnesses/contract_review.py` — that registers the 8-phase HarnessDefinition (CR-01..08).
2. A `post_execute` callback (CR-08 / DOCX-01) that drives DOCX generation in the sandbox (DOCX-02..08).
3. Frontend wiring for DOCX delivery (file link in post-harness chat bubble + workspace panel listing).
4. **One backend fix carried over from Phase 21 UAT (CR-21-08)**: workspace-aware gatekeeper prompt so users can actually trigger Contract Review reliably with natural language.
5. python-docx + dependencies added to the sandbox image.

**No new harness phase types.** All 5 (`programmatic`, `llm_single`, `llm_agent`, `llm_human_input`, `llm_batch_agents`) are already implemented and unit-tested. No new migration. `harness_runs` schema covers everything.

**Strict scope guardrail:**
- Other future domain harnesses (e.g., NDA Quick Review, M&A Due Diligence) are **not** in scope. Phase 22 ships exactly one harness — Contract Review.
- DOCX styling beyond the 8 specified sections (CR-DOCX-02..07) is deferred. No watermarks, custom fonts, or branded title pages beyond the basic CONFIDENTIAL marker + risk badge listed in DOCX-02.
- Multi-contract batch review (uploading 5 contracts at once) is deferred — Phase 22 supports exactly one contract per harness run.
- LangSmith eval dashboards / production telemetry beyond the CI eval set are deferred.

</domain>

<carrying_forward>
## Carrying Forward From Earlier Phases

### From Phase 21 (Batched Parallel Sub-Agents + HIL)

- **D-01..D-04 (HIL pattern)** → directly applies to **CR-03 Gather Context** (`llm_human_input`). The pattern is locked: stream question text as `delta` events → emit `harness_human_input_required` → DB transition to `paused` before SSE close → resume on next user message via the chat router HIL branch. No new code paths needed in the engine.
- **D-05..D-07 (JSONL append-only batch artifact)** → directly applies to **CR-06 Risk Analysis** and **CR-07 Redline Generation** (`llm_batch_agents`, `batch_size=5`). The two-file pattern (`{name}.jsonl` resume artifact + `{name}.json` clean output) is the spec. Mid-batch resume on crash/restart works out of the box.
- **D-08..D-09 (item-level batch SSE + frontend `batchProgress` slice + HarnessBanner suffix)** → already shipped. CR-06/07 will render "Analyzing clause N/M" / "Menganalisis klausula N/M" without any frontend changes.

### From Phase 20 (Harness Engine Core)

- `gatekeeper.py` system prompt builder, sliding-window sentinel detection (window=33), egress filter wrap → reused. The Phase 22 fix to gatekeeper is **additive only** (workspace block injection); does not touch the sentinel logic.
- `post_harness.py` deterministic truncation + inline SSE → reused for the executive summary message (CR-08).
- `messages.harness_mode='contract-review'` on every message persisted by the gatekeeper / engine / post_harness for this run.

### Resolved Phase 21 UAT carryovers

CR-21-01..07 are all fixed and live in production (commits `cb5680e`..`da18f34` + `956af2e`). The only Phase-21-deferred item Phase 22 must address is **CR-21-08 (gatekeeper trigger reliability)** — covered by Decision D-22-01 below.

</carrying_forward>

<decisions>
## Implementation Decisions

### Gatekeeper Trigger Reliability (CR-21-08 fix; gates whether users can reach CR-01)

- **D-22-01 (Workspace-aware gatekeeper system prompt):** Inject the current `workspace_files` list into the gatekeeper system prompt before each turn. The LLM verifies prerequisites programmatically instead of relying on the user's chat assertion. Keeps natural-language UX, fixes gpt-4o-mini's over-cautious refusal observed in Phase 21 UAT (gatekeeper_complete.triggered=false for 3 consecutive turns even with explicit user confirmation).

- **D-22-02 (Workspace block format — filename + size only):** Inject a compact line per file: `Workspace: contract.docx (245 KB), addendum.pdf (89 KB)`. No content, no first-N-chars peek. Rationale: filenames + sizes suffice for "is a contract uploaded?" verification; minimal token cost; no PII leakage path beyond what's already in `workspace_files`. The block is built fresh per turn by querying `workspace_service.list_files(thread_id)` inside `gatekeeper.run_gatekeeper()` before the LLM call. If the list is empty, the block reads `Workspace: (empty — user has not uploaded yet)`.

- **D-22-03 (Match-intent trigger phrase strategy):** Gatekeeper system prompt includes 3–5 few-shot examples covering paraphrases:
  - "Review this contract" → trigger
  - "Check this for risks" → trigger
  - "I uploaded a contract" + workspace non-empty → trigger
  - "Help me with this NDA" + DOCX present → trigger
  - "Hello" / "What's this app do?" → no trigger
  The LLM matches **intent**, not exact phrase. Few-shots live alongside the existing prompt in `build_system_prompt()` and use the harness's `display_name` so the same prompt template works for future domain harnesses.

- **D-22-04 (Trigger reliability eval set + automated CI test):** Build a JSON eval set (~15 phrasings: should-trigger + should-NOT-trigger across smoke-echo, contract-review, neutral chat). New pytest suite `tests/services/test_gatekeeper_eval.py` runs each phrasing through `run_gatekeeper` (with mocked-but-realistic LLM responses for CI cost — the eval against real LLM is a separate manual-run script). Asserts `gatekeeper_complete.triggered` matches the expected label per phrasing. Regressions caught in CI before merge. Smoke-echo phrasings go in the eval set so we can never regress Phase 21 trigger reliability.

### Playbook Discovery (CR-04, llm_agent + RAG, max 10 rounds)

- **D-22-05 (Tag-based filter on `playbook`):** CR-04 sub-agent's `search_documents` calls auto-add `filter_tags=['playbook']` to every RAG query. Admins (super_admin) tag model contracts, internal redline guides, regulatory texts as `playbook` via the existing document tagging UI. Clean separation; predictable; reuses existing `filter_tags` parameter on `search_documents` (no new tool, no new schema).

- **D-22-06 (Playbook output shape — JSON-structured per-category mapping):** CR-04 writes `playbook-context.md` with the following structure (markdown header + JSON code block + plain prose summary for human readers):
  ```json
  {
    "playbook_docs": [
      {"id": "<doc_id>", "title": "<title>", "summary": "<≤200 char summary>"}
    ],
    "clause_category_to_playbook": {
      "Liability": ["<doc_id_1>", "<doc_id_2>"],
      "Indemnification": ["<doc_id_3>"],
      // ... 13 clause categories per CR-05
    }
  }
  ```
  CR-06 (Risk) and CR-07 (Redlines) sub-agents read this file. When grading a clause, they call `search_documents(query=clause_text, filter_doc_ids=clause_category_to_playbook[category])` to retrieve precise grounding from the relevant playbook materials only. This is more authoritative than re-RAG-ing across the whole corpus per clause.

- **D-22-07 (Empty-playbook fallback — generic legal-knowledge with `unfounded` flag):** When CR-04's playbook discovery yields zero documents, CR-06/07 sub-agents proceed using a generic legal-knowledge prompt addendum ("Assess against industry-standard expectations for this contract type"). The engine sets a flag in `phase_results['risk_analysis'].context_quality = 'unfounded'`. CR-08 executive summary calls out: "No playbook materials found — risk grades reflect generic legal standards." Users still get useful output without being blocked by an empty corpus.

- **D-22-08 (Authority hierarchy — user-uploaded > regulatory_intel > 3rd-party):** When the playbook tag has multiple sources, CR-06/07 sub-agent prompts include this fixed ordering. Implementation: `playbook-context.md`'s `playbook_docs` array is sorted by source: user-workspace uploads first, regulatory_intel rows second, general document library third. Sub-agents implicitly weight earlier entries higher when summaries reference multiple sources. Matches typical legal team intuition: "our standards first, then law, then market." No admin authority-score field — keep Phase 22 small.

### CR-03 HIL Question UX

- **D-22-09 (Single combined free-form question):** CR-03's `llm_human_input` phase generates ONE paragraph asking about all 4 topics in plain language ("Which party are you, what's the timeline, anything specific to focus on, and what's the broader deal context?"). User replies with one chat message covering whatever's relevant. Single HIL pause. Matches Phase 21 HIL design and is consistent with smoke-echo's pattern.

- **D-22-10 (Persistence — raw text only, downstream LLMs interpret):** Write the user's answer verbatim to `review-context.md`. CR-04, CR-06, CR-07, CR-08 sub-agents read the file as plain text. LLMs are good at extracting which-side / deadline / focus from natural language; no parser needed. Saves an LLM call (no post-input parse) and avoids parser-drift bugs. If precise structured fields become necessary later, can add an LLM-parse pass without breaking the file shape.

- **D-22-11 (Skip-tolerant — accept any reply, default to neutral):** Even minimal answers like "..." or "just go" are accepted. CR-04..08 sub-agents handle the empty/sparse case by defaulting to "neutral perspective, no deadline pressure, all 13 clause categories equal weight." Don't fight users who want to skip; respect their time. Engine does NOT set a `context_quality` flag for sparse CR-03 answers (only for empty playbook in D-22-07) — sub-agents just operate with less guidance.

### DOCX Template + Delivery (DOCX-01..08)

- **D-22-12 (Pure programmatic python-docx generation, no template file):** All styling, sections, tables, color coding generated in Python code via the `python-docx` library inside the sandbox. No `.dotx` template artifact. Rationale: simplest, version-controlled, deterministic; layout adjustments are normal Python edits; matches REQUIREMENTS.md ("python-docx via sandbox"). The Python script lives in the sandbox at a fixed path (TBD by planner) and is invoked by the `post_execute` callback registered on CR-08's PhaseDefinition.

- **D-22-13 (Pastel risk color scheme):** Risk fills in the redline table (DOCX-05) use:
  - GREEN: `#E6F4EA` fill, dark green text
  - YELLOW: `#FEF7E0` fill, dark amber text
  - RED: `#FCE8E6` fill, dark red text
  Industry-standard for risk tables; readable, professional, prints well without fighting body text. Matches the calibrated-restraint design language used elsewhere in LexCore.

- **D-22-14 (Delivery — inline chat link + workspace panel listing, no auto-download):** Once the post_execute callback finishes generating the DOCX:
  1. The DOCX file is uploaded into `workspace_files` for the active thread (source='harness', filename like `contract-review-{harness_run_id-short}.docx`). The Workspace Panel re-renders automatically via the existing `workspace_updated` SSE event.
  2. The post-harness summary chat bubble (CR-08) includes a clickable file link/card pointing to the workspace file's signed download URL. Frontend renders this as a download chip next to the executive summary text.
  3. **No** browser auto-download. Avoids pop-up blocker / multi-tab annoyances; matches LexCore's restrained interaction style.

- **D-22-15 (DOCX-08 non-fatal fallback — markdown + visible failure note):** If DOCX generation fails (sandbox 5xx, python-docx exception, missing dependency), the post-harness markdown summary is still shown. The chat bubble appends a visible non-fatal note: "DOCX export unavailable right now — the full markdown summary is above. Retry by re-running the harness if needed." User still gets the analysis. Engine logs the failure to LangSmith for ops visibility but does NOT mark `harness_runs.status='failed'` — a missing DOCX is a downgrade, not a harness failure.

</decisions>

<deferred>
## Deferred Ideas

- **Multi-contract batch review (uploading 5 contracts at once)** — would require batching at the harness level (parallel runs of Contract Review). Phase 22 supports one contract per run.
- **Watermarks, custom fonts, branded title pages beyond CONFIDENTIAL + risk badge** — DOCX styling enhancements. The DOCX-02..07 sections are unstyled beyond the pastel risk colors.
- **Admin-editable `authority_score` field on playbook documents** — useful refinement for D-22-08's authority hierarchy, but adds admin UI work outside Phase 22 scope.
- **Two-pass user confirmation on CR-03 parsed fields** — could add accuracy at the cost of an extra HIL pause; deferred unless feedback shows accuracy issues.
- **LangSmith production trigger-rate dashboard for D-22-04** — the eval set covers CI; real-world telemetry can come later if trigger reliability proves operationally sensitive.
- **Curated `/playbooks` folder with folder_id filter** — simpler-to-govern alternative to D-22-05's tag approach; can be added if tag discipline becomes a problem.
- **Retry button on failed DOCX export** — D-22-15's plain text note suffices for v1; a retry endpoint can be added if users hit the failure path often.

</deferred>

<canonical_refs>
## Canonical References (read these for full context)

- `.planning/PROJECT.md` — milestone scope, decisions, current state
- `.planning/REQUIREMENTS.md` — CR-01..08 + DOCX-01..08 (all locked)
- `.planning/ROADMAP.md` (Phase 22 entry) — 8-phase workflow + DOCX deliverable + success criteria
- `.planning/phases/21-batched-parallel-sub-agents-human-in-the-loop/21-CONTEXT.md` — D-01..D-09 (HIL pattern, JSONL artifact, batch SSE) — Phase 22 reuses these verbatim
- `.planning/phases/21-batched-parallel-sub-agents-human-in-the-loop/21-UAT.md` — CR-21-08 root-cause analysis (the gpt-4o-mini gatekeeper failure that motivates D-22-01..04)
- `.planning/phases/20-harness-engine-core-gatekeeper-post-harness-file-upload-lock/20-CONTEXT.md` — engine architecture (`PhaseType` enum, `PhaseDefinition.post_execute` field, gatekeeper sentinel pattern)
- `backend/app/harnesses/types.py` — `PhaseType`, `PhaseDefinition` (line 67: `post_execute: Callable[..., Awaitable[Any]] | None = None` — the hook DOCX uses)
- `backend/app/harnesses/smoke_echo.py` — reference implementation for harness module shape (registration pattern, gating, multi-phase composition)
- `backend/app/services/gatekeeper.py` — current `build_system_prompt()` and `run_gatekeeper()` — D-22-01..03 modify this file
- `backend/app/services/harness_engine.py` — `LLM_BATCH_AGENTS` and `LLM_HUMAN_INPUT` dispatchers (Phase 21 work) — CR-03/06/07 use these
- `backend/sandbox/Dockerfile` + `backend/sandbox/tool_client.py` — sandbox infrastructure that DOCX-01 builds on; Phase 22 must add `python-docx` + `PyPDF2` to this image
- `backend/app/services/tool_service.py` (`search_documents`, `analyze_document`) — RAG tools CR-04 uses with `filter_tags=['playbook']`
- CLAUDE.md — Tool Registry adapter-wrap invariant (line ~178: never edit tool_service.py:1-1283); Railway manual deploy gotcha; Vercel deploy from main; CREATE POLICY DROP-IF-EXISTS pattern (relevant if any new RLS lands)

</canonical_refs>

<code_context>
## Reusable Assets and Patterns

- **`backend/app/harnesses/smoke_echo.py`** — closest analog. Phase 22's `contract_review.py` mirrors its module shape (HarnessDefinition with name, display_name, prerequisites, phases list, gated registration via `register(SMOKE_ECHO)` if flag enabled).
- **`backend/app/services/harness_engine.py` LLM_BATCH_AGENTS dispatcher** (Phase 21) — CR-06/07 batches plug in directly. JSONL append, asyncio.Queue fan-in, mid-batch resume — all already wired.
- **`backend/app/services/harness_engine.py` LLM_HUMAN_INPUT dispatcher** (Phase 21) — CR-03 plugs in directly. Pause/resume across SSE close is already handled.
- **`backend/app/routers/chat.py` HIL resume branch** (Phase 21, line ~365) — handles user's reply to CR-03 without modification.
- **`backend/app/services/post_harness.py`** — Phase 20 module that streams the post-harness summary inline. CR-08's `llm_single` phase is a normal phase; the `post_execute` callback fires after that phase's normal LLM call completes (or in parallel with the summary streaming — planner to decide ordering).
- **`backend/sandbox/tool_client.py`** — sandbox client that the post_execute callback uses to run the DOCX generation Python script.
- **`backend/app/services/workspace_service.py`** — `write_file` (CR phases write artifacts), `append_line` (Phase 21 — used for batch JSONL), `list_files` (D-22-01 needs this for the gatekeeper workspace block), `read_file` (post_execute reads markdown summary to embed in DOCX).
- **`frontend/src/components/chat/HarnessBanner.tsx`** — already shows "Analyzing clause N/M" via Phase 21's `batchProgress` slice. CR-06/07 will populate it without frontend changes.
- **`frontend/src/components/chat/PlanPanel.tsx`** — locked variant from Phase 20-08 already renders the 8 phases as the harness progresses.
- **`frontend/src/components/chat/MessageView.tsx`** — post-harness summary bubble. Phase 22 needs to add a "downloadable file card" rendering when `messages.attachments` (or equivalent) is non-empty. Planner to scope the exact mechanism.
- **`frontend/src/components/chat/WorkspacePanel.tsx`** — already lists workspace files. The DOCX will appear automatically.
- **Existing Phase 13 RAG tools** (`search_documents` with `filter_tags`) — CR-04 uses verbatim.

## Integration Points

- **`harness_smoke_enabled` flag in config.py** — Phase 22 adds parallel `contract_review_enabled` (or reuses a generic `harness_enabled` master). Planner picks; D-16 invariant from Phase 20 says off-mode must be byte-identical.
- **system_settings cache (`get_system_settings()`)** — used by gatekeeper for per-feature LLM provider override; CR sub-agents may use the entity_resolution provider per existing pattern.
- **Egress filter (`SEC-04`, B4 single-registry)** — CR-04, CR-06, CR-07 all make cloud-LLM calls; the existing `_get_or_build_conversation_registry` + `egress_filter` pattern wraps each call site (already covered by Phase 20 B4 work).
- **Tool curation propagation** (Phase 21 `phase_tools` honor hook) — CR-04 (max-10-round agent) and CR-06/07 (batch sub-agents) set `phase_tools=['search_documents', 'analyze_document']` so sub-agents only see RAG tools. Already implemented in `sub_agent_loop.py`.

</code_context>

<open_questions_for_planner>
## Questions Punted to the Planner

1. **Where does the DOCX-generating Python script live?** Inside `backend/app/harnesses/contract_review_docx.py` as a constant string sent to the sandbox? Or a separate `.py` file packaged with the sandbox image? Planner picks based on sandbox tool_client patterns.
2. **Exact ordering of CR-08 LLM summary vs DOCX post_execute:** sequential (LLM completes → DOCX runs reading the markdown) is simpler; parallel is faster. Planner decides based on dependencies.
3. **Frontend file-link rendering inside post-harness chat bubble:** new `attachment` field on the message vs. parse-out-link from markdown vs. dedicated `harness_artifact` SSE event. Planner specs the cleanest path.
4. **Sandbox dependency addition:** Add `python-docx` and `PyPDF2` to `backend/sandbox/Dockerfile`? Or to a layer that only loads on Contract Review runs? Planner decides based on cold-start budget.
5. **Eval set authoring (D-22-04):** the planner specifies the 15 phrasings. Should include at least 5 contract-review-trigger, 5 smoke-echo-trigger, 5 should-not-trigger.
6. **Filename pattern for the generated DOCX** (referenced in D-22-14 as `contract-review-{harness_run_id-short}.docx`) — confirm this matches existing workspace_files naming conventions.

</open_questions_for_planner>

---

**Phase 22 sits on the shoulders of Phases 20–21.** The infrastructure (engine, dispatchers, gatekeeper, sandbox, RAG tools, workspace_files, frontend banner/panel) is built. The core work is composing the 8-phase HarnessDefinition, fixing the gatekeeper trigger reliability gap from CR-21-08, and wiring the DOCX delivery loop. Estimated complexity: comparable to Phase 20 in plan count, but most plans are smaller because the engine already does the heavy lifting.
