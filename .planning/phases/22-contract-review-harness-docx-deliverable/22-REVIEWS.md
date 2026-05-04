---
phase: 22
reviewers: [codex]
reviewers_skipped:
  - claude (self — review was invoked from Claude Code; skipped for independence)
  - gemini (unauthenticated — GEMINI_API_KEY not set; install/auth gemini-cli to include)
reviewers_unavailable: [coderabbit, opencode, qwen, cursor, ollama, lm_studio, llama_cpp]
reviewed_at: 2026-05-04T14:34:15Z
plans_reviewed:
  - 22-01-sandbox-image-bump-PLAN.md
  - 22-02-search-by-doc-ids-tool-PLAN.md
  - 22-03-engine-post-execute-hook-PLAN.md
  - 22-04-gatekeeper-workspace-prompt-PLAN.md
  - 22-05-gatekeeper-eval-set-PLAN.md
  - 22-06-contract-review-skeleton-CR01-CR02-PLAN.md
  - 22-07-CR03-CR04-context-and-playbook-PLAN.md
  - 22-08-CR05-clause-extraction-PLAN.md
  - 22-09-CR06-CR07-batch-risk-and-redlines-PLAN.md
  - 22-10-CR08-summary-and-DOCX-postexecute-PLAN.md
  - 22-11-frontend-file-card-and-workspace-source-PLAN.md
  - 22-12-end-to-end-pytest-PLAN.md
---

# Cross-AI Plan Review — Phase 22: Contract Review Harness + DOCX Deliverable

> Only one external reviewer (Codex / gpt-5.4, xhigh reasoning) ran successfully. Gemini was skipped because the local `gemini` CLI is unauthenticated; Claude was skipped because this review was invoked from inside Claude Code (independence rule). The "Consensus Summary" section therefore reflects a single-reviewer signal — there is no cross-model agreement axis. Treat findings as a strong adversarial pass, not as cross-validation.

## Codex Review

### Summary

The phase is well-scoped at the product level and the wave sequencing is mostly sensible, but several plans assume capabilities that do not exist in the current checkout. The biggest gaps are in playbook retrieval, batch-agent structured output, privacy enforcement for CR-05's internal LLM calls, and frontend/event correlation for DOCX delivery. As written, the plan set is not yet implementation-safe for CR-04 through CR-07 and the DOCX UX loop.

### Strengths

- The wave structure is disciplined: infrastructure first, harness skeleton next, then phase-by-phase fill-in, then frontend and E2E.
- The plans correctly respect the `tool_service.py` adapter-wrap boundary below line 1283 and avoid in-place edits to the protected native tool block.
- The dark-launch/deploy-order intent is strong: `contract_review_enabled` stays off until the harness is complete.
- Reuse of existing Phase 20/21 machinery is good: gatekeeper, HIL pause/resume, batch dispatcher, workspace files, and post-harness summary are all leveraged instead of reinvented.
- The non-fatal DOCX fallback is well-designed conceptually; degrading to usable analysis instead of failing the run is the right product behavior.
- The review/eval posture is strong: there is unit, integration, live-eval, and E2E thinking throughout the plan set.

### Concerns

- `[HIGH][22-07, 22-09]` CR-04/06/07 depend on capabilities the current tool layer does not expose. `search_documents` returns chunks/filename/category/tags only, not document IDs, and there is no `analyze_document` tool in this checkout. That breaks the whole `playbook_docs -> clause_category_to_playbook -> search_documents_by_doc_ids` chain. See `backend/app/services/tool_service.py:39-71` and `:535-595`.
- `[HIGH][22-09]` The batch path does not produce structured per-item objects the way the plan assumes. `run_sub_agent_loop()` terminates with `{"text": full_response}`, not a parsed `ClauseRisk`/`Redline` dict, while the filter step expects `row["result"]["terminal"]["risk_grade"]`. See `backend/app/services/sub_agent_loop.py:414` and `backend/app/services/harness_engine.py:984-989`.
- `[HIGH][22-09]` CR-07 is missing the original clause text. `ClauseRisk` does not carry `original_text`, and the filter step forwards only risk objects, so the redline phase lacks the verbatim clause body it is supposed to rewrite.
- `[HIGH][22-08]` CR-05's internal LLM calls would bypass the existing SEC-04 egress-filter path. In the current engine, programmatic executors receive `inputs/token/thread_id/harness_run_id`, not the redaction registry, so the privacy invariant is not actually preserved for clause extraction.
- `[HIGH][22-01, 22-06]` The PDF path is incomplete in the backend runtime. `python-docx` is in `backend/requirements.txt`, but `PyPDF2` is not. Plan 22-01 installs it in the sandbox, but CR-01 extraction is planned in the FastAPI process, not the sandbox. PDF uploads would still fail.
- `[HIGH][22-10]` The plan says CR-08 writes `contract-review-report.md`, but `LLM_SINGLE` currently writes raw JSON to `workspace_output`, not markdown. That means the DOCX-08 fallback artifact would be JSON in a `.md` file, not the promised markdown report. See `backend/app/services/harness_engine.py:615-623`.
- `[HIGH][22-10, 22-11]` The "inline chat link + workspace panel listing" loop is incomplete. `post_execute` can write the DOCX via `WorkspaceService.write_binary_file()`, but that code path does not emit `workspace_updated`, so the Workspace Panel will not auto-refresh the way the plans claim.
- `[HIGH][22-11]` The frontend has no reliable correlation anchor for attaching `harness_artifact` to the post-harness assistant message. `Message` lacks `harness_run_id`/`harness_mode`, `summary_complete` is not handled in the frontend, and during summary streaming there is no persisted assistant `Message` object to mutate.
- `[HIGH][22-12]` The E2E happy path ignores the actual HIL architecture. A single `run_harness_engine()` call will stop at CR-03 with `status='paused'`; a real end-to-end test must exercise the chat router's resume branch, not one linear engine invocation.
- `[MEDIUM][22-02]` The plan contradicts itself on doc-id filtering. Parts of it still expect `HybridRetrievalService.retrieve(..., filter_doc_ids=...)`, while the ISSUE-08 resolution correctly says Python-side overfetch-and-filter because that parameter does not exist.
- `[MEDIUM][22-11]` The frontend file targets are off. i18n is in `frontend/src/i18n/translations.ts`, not `frontend/src/i18n/locales/*.json`, and `Message` is defined in `frontend/src/lib/database.types.ts`, not locally in `useChatState.ts`.
- `[MEDIUM][22-01]` The parity test only guards `python-docx`; it does not guard `PyPDF2`, so the PDF intake gap can slip through even if Plan 22-01 passes.

### Suggestions

- `[22-07, 22-09]` Add a real playbook-discovery capability that returns `doc_id/title/summary`, or add a new sibling tool for that purpose. Do not build CR-04/06/07 on top of `search_documents` as it exists today.
- `[22-09]` Add a structured-output layer for `LLM_BATCH_AGENTS`: either teach `sub_agent_loop`/`harness_engine` to parse and validate per-item JSON, or add an explicit post-batch normalization phase before filtering/redlining.
- `[22-09]` Carry `original_text` forward explicitly. Either include it in `ClauseRisk`, or have the filter step join `risk-analysis.json` back to `clauses.json` before producing `redline-candidates.json`.
- `[22-08]` Rework CR-05 so the contract text goes through an engine-managed LLM path that already has the registry/egress filter, or extend the programmatic executor contract before implementing clause extraction.
- `[22-01, 22-06]` Put `PyPDF2` in the backend runtime and add a backend-side import smoke test. Do not rely on the sandbox image for a phase that executes in the app process.
- `[22-10]` Separate "validated JSON summary" from "human-readable markdown report". Keep the `ExecutiveSummary` schema, but add a deterministic markdown render step so `contract-review-report.md` is actually markdown.
- `[22-10, 22-11]` Add deterministic delivery plumbing: emit `workspace_updated` after DOCX write, and carry `assistant_message_id` or equivalent correlation data through SSE so the chip can attach without heuristics.
- `[22-11]` Align the frontend work with the actual repo layout: update `database.types.ts`, `translations.ts`, and decide whether the artifact is attached to streaming state, persisted messages, or both.
- `[22-12]` Rewrite the E2E plan around the real pause/resume flow: gatekeeper -> phases 1-2 -> HIL pause -> resume via `/chat/stream` -> phases 4-9 -> `post_execute`.
- `[22-02]` Clean up the doc-id search plan so all tasks, tests, and acceptance criteria agree on Python-side filtering and never mention nonexistent `filter_doc_ids` support.

### Risk Assessment

**HIGH.** The overall product design is coherent, but the current plans have multiple hard mismatches with the codebase: missing tool/data surfaces for playbook grounding, no structured batch-output path, a privacy gap in CR-05, a backend dependency gap for PDFs, and incomplete frontend delivery wiring for the DOCX artifact. Those are not polish issues; they affect whether CR-04 through CR-07 and DOCX delivery can work at all in this checkout.

---

## Consensus Summary

Single reviewer (Codex). No cross-model triangulation available. The findings below are Codex's, not "consensus" in the multi-reviewer sense — but every concern is anchored to a concrete `file:line` in the live codebase, so they are verifiable.

### Top blockers (must resolve before execution)

1. **Playbook discovery has no tool surface.** `search_documents` returns chunks, not `doc_id`s, and `analyze_document` does not exist. Plans 22-07 / 22-09 build CR-04/06/07 on capabilities that need to be created first. See `backend/app/services/tool_service.py:39-71` and `:535-595`.
2. **Batch agent output is unstructured.** `run_sub_agent_loop()` returns `{"text": full_response}`; the filter step in plan 22-09 expects `row["result"]["terminal"]["risk_grade"]`. A structured-output layer (per-item JSON parse + validate) is missing. See `backend/app/services/sub_agent_loop.py:414` and `backend/app/services/harness_engine.py:984-989`.
3. **CR-07 missing `original_text`.** `ClauseRisk` does not carry the verbatim clause body, but the redline phase needs it. Forward it explicitly.
4. **Privacy invariant gap in CR-05.** Programmatic executors don't receive the redaction registry, so CR-05's internal LLM calls bypass the SEC-04 egress filter. Either route through an engine-managed LLM path or extend the programmatic-executor contract.
5. **PDF support gap.** `PyPDF2` is in the sandbox image (plan 22-01) but missing from `backend/requirements.txt`. CR-01 runs in the FastAPI process, so PDF uploads will fail.
6. **CR-08 fallback artifact is JSON, not markdown.** `LLM_SINGLE` writes raw JSON to `workspace_output`. The plan promises `contract-review-report.md`. Add a deterministic markdown render step.
7. **DOCX delivery loop incomplete.** `post_execute` writes the file but does not emit `workspace_updated`; frontend `Message` lacks `harness_run_id`/`harness_mode` correlation; `summary_complete` is unhandled in the frontend.
8. **E2E test ignores HIL.** A single `run_harness_engine()` call pauses at CR-03; the test must exercise the chat router resume branch.

### Plans that need substantive revision

- **22-09** (highest impact): batch structured output + `original_text` propagation
- **22-07**: playbook discovery capability dependency
- **22-08**: privacy invariant for programmatic LLM calls
- **22-10**: markdown render step + `workspace_updated` emission
- **22-11**: correlation IDs + correct frontend file targets
- **22-12**: rewrite E2E around pause/resume flow
- **22-01 / 22-06**: PyPDF2 in backend runtime + parity test

### Plans that look implementation-safe as written

- **22-03** (engine post_execute hook), **22-04** (gatekeeper system prompt), **22-05** (gatekeeper eval set) — no concerns flagged. (Note: this is absence of evidence, not a positive endorsement; a second reviewer could surface issues here.)

### Divergent views

N/A — only one reviewer. Re-running with `gemini` (after auth) or `claude` (from a non-Claude-Code shell) would surface where adversarial models disagree.

## Next Steps

To incorporate this feedback into planning:

```bash
/gsd-plan-phase 22 --reviews
```

To re-run the review with more CLIs (after configuring auth for gemini):

```bash
/gsd-review --phase 22 --gemini
```
