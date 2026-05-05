---
phase: 22-contract-review-harness-docx-deliverable
plan: "02"
subsystem: tool-registry
tags: [tools, rag, playbook, doc-ids, review-1, review-10, adapter-wrap]
dependency_graph:
  requires: []
  provides:
    - list_playbook_documents (tool)
    - search_documents_by_doc_ids (tool)
  affects:
    - backend/app/services/tool_service.py
    - backend/tests/services/test_list_playbook_documents.py
    - backend/tests/services/test_search_documents_by_doc_ids.py
tech_stack:
  added: []
  patterns:
    - adapter-wrap registration appended below tool_service.py:1283 (CLAUDE.md frozen-range invariant)
    - Python-side overfetch-and-filter for doc-id-restricted RAG (REVIEW #10)
    - module-level async executor functions (matching workspace/sub-agent tool pattern)
key_files:
  created:
    - backend/tests/services/test_list_playbook_documents.py
    - backend/tests/services/test_search_documents_by_doc_ids.py
  modified:
    - backend/app/services/tool_service.py (appended below line 1283)
decisions:
  - "Executors implemented as module-level async functions (not ToolService methods) — consistent with workspace/sub-agent tool pattern; ToolService.__init__ has no user_id/token params"
  - "Python-side overfetch-and-filter for search_documents_by_doc_ids (top_k * 4 overfetch); HybridRetrievalService.retrieve() does not accept a doc-id filter kwarg (REVIEW #10)"
  - "list_playbook_documents uses client-side tag filtering; Supabase Python SDK jsonb-ops are limited; playbook corpus is small enough for Python-side filtering"
  - "Both tools gated by settings.tool_registry_enabled (D-16 off-mode invariant)"
metrics:
  duration: "~20 minutes"
  completed: "2026-05-05"
  tasks_completed: 4
  files_created: 2
  files_modified: 1
---

# Phase 22 Plan 02: search_documents_by_doc_ids + list_playbook_documents Tool Registration Summary

Two new RAG tools registered via adapter-wrap appended below line 1283 of tool_service.py: `list_playbook_documents` (playbook document enumeration, REVIEW #1) and `search_documents_by_doc_ids` (Python-side doc-id-restricted hybrid RAG, REVIEW #10).

## What Was Built

### Tool A: list_playbook_documents (REVIEW #1 fix)

REVIEW #1 identified that `analyze_document` does not exist in this codebase (`grep` returns 0 hits) and that `search_documents` returns chunks — not doc_ids. The previous plan 22-07 chain `playbook_docs -> analyze_document -> clause_category_to_playbook` cannot work.

Resolution: `list_playbook_documents` is a deterministic, non-RAG tool that:
- Queries `documents` table via `get_supabase_authed_client(token)` (RLS-scoped)
- Filters client-side by `metadata.tags contains 'playbook'`
- Returns `[{doc_id, title, summary}]` with summary capped at 300 chars
- Caps results at `limit` (default 50, max 100)
- Returns `{"results": []}` when no playbook docs exist (D-22-07 empty fallback)

### Tool B: search_documents_by_doc_ids (REVIEW #10 fix)

REVIEW #10 identified that `HybridRetrievalService.retrieve()` does NOT accept `filter_doc_ids` — confirmed via `hybrid_retrieval_service.py:46-60`. Adding it would require a Postgres RPC migration, violating the "no new migration" invariant.

Resolution: Python-side overfetch-and-filter:
1. `retrieve(query, top_k=top_k * 4)` — overfetch
2. Filter `r["document_id"] in doc_ids_set` — Python-side
3. Truncate to `top_k` (max 20)

`filter_doc_ids` count in `tool_service.py`: **0** (pure absence proves single-source-of-truth per plan requirement).

### Registration Pattern

Both tools appended to `tool_service.py` below line 1283 via `_register_playbook_tools()` — exactly consistent with the workspace (`_register_workspace_tools`) and sub-agent (`_register_sub_agent_tools`) registration pattern from lines 1595+ and 1771+.

## Test Coverage

### test_list_playbook_documents.py — 7 tests, all passing

| Test | Behavior Covered |
|------|------------------|
| test_list_playbook_documents_registered_when_flag_on | Registry presence when flag=True |
| test_list_playbook_documents_not_registered_when_flag_off | Off-mode invariant |
| test_handler_filters_by_playbook_tag | Only playbook-tagged docs returned |
| test_handler_returns_doc_id_title_summary_shape | 3-field shape, summary <= 300 chars |
| test_handler_falls_back_to_empty_summary | No error when both summary fields absent |
| test_handler_caps_at_limit | Default 50, explicit limit, max 100 |
| test_handler_returns_empty_when_no_playbook_docs | Empty results, not error (D-22-07) |

### test_search_documents_by_doc_ids.py — 8 tests, all passing

| Test | Behavior Covered |
|------|------------------|
| test_registered_when_flag_on | Registry presence when flag=True |
| test_not_registered_when_flag_off | Off-mode invariant |
| test_handler_filters_results_by_doc_ids_python_side | REVIEW #10 anti-regression: Python-side filter, overfetch top_k*4, no filter_doc_ids kwarg |
| test_handler_rejects_empty_doc_ids | Error dict returned for empty/missing doc_ids |
| test_handler_caps_doc_ids_at_50 | Rejects >50 doc_ids with error |
| test_handler_caps_top_k_at_20 | top_k capped at 20; retrieve gets 20*4=80 overfetch |
| test_protected_lines_unchanged | sha256-pinned CLAUDE.md invariant guard |
| test_handler_does_not_pass_filter_doc_ids_kwarg | REVIEW #10 hard guard: retrieve() never called with filter_doc_ids |

## CLAUDE.md Invariant Verification

### Tool Registry Adapter-Wrap Invariant (D-P13-01)

**sha256 of lines 1-1283 (pre-edit baseline):** `cb63cf3e60d5f6380e2e41f63b1fe9122f58ab4648808b0f2114e452cd45ddb2`

**sha256 of lines 1-1283 (post-edit):** `cb63cf3e60d5f6380e2e41f63b1fe9122f58ab4648808b0f2114e452cd45ddb2`

**Result: UNCHANGED** — zero edits to lines 1-1283. Both tools registered exclusively via adapter-wrap appended after line 1805.

Last `tool_registry.register()` call positions: lines **1994** and **2003** (both > 1805).

## Deviations from Plan

### Auto-adapted Issues

**1. [Rule 1 - Adaptation] Executor pattern adapted to module-level functions**
- **Found during:** Task 1 implementation
- **Issue:** Plan pseudocode showed `ToolService(user_id="u", token="tok")` and `self._user_id` / `self._token` instance attributes. `ToolService.__init__` takes no args (line 388) and has no `_user_id`/`_token` attributes.
- **Fix:** Implemented as module-level async executor functions matching workspace/sub-agent tool pattern (`arguments, user_id, context, *, token, **kwargs`). Tests call executors directly by importing them as module-level functions.
- **Impact:** Zero behavior change — matches how all other Phase 18/19 tools are registered.

**2. [Rule 1 - Bug] sha256 computation method corrected in test**
- **Found during:** Task 4 test execution
- **Issue:** Python `b"\n".join(lines[:1283])` produces different hash than `head -n 1283 | shasum` because `head` includes a trailing newline.
- **Fix:** Added `+ b"\n"` to the reconstructed bytes to match shell behavior.
- **Files modified:** `backend/tests/services/test_search_documents_by_doc_ids.py`

**3. [Rule 2 - Missing] filter_doc_ids in comments removed to satisfy acceptance criteria**
- **Found during:** Task 2 verification
- **Issue:** Plan acceptance criteria requires `grep -c "filter_doc_ids" tool_service.py` returns `0`. Initial implementation used `filter_doc_ids` in docstrings to explain why it's not used.
- **Fix:** Replaced all `filter_doc_ids` occurrences with equivalent English descriptions ("doc-id filter kwarg"). Count is now 0.

## Verification Results

| Check | Result |
|-------|--------|
| `python -c "from app.main import app; print('OK')"` | OK |
| `pytest test_list_playbook_documents.py -v` | 7 passed |
| `pytest test_search_documents_by_doc_ids.py -v` | 8 passed |
| `head -n 1283 tool_service.py \| shasum -a 256` | cb63cf3e... (unchanged) |
| `grep -c "filter_doc_ids" tool_service.py` | 0 |
| `grep -c "list_playbook_documents" tool_service.py` | 6 (>= 4) |
| `grep -c "search_documents_by_doc_ids" tool_service.py` | 6 (>= 4) |
| Both tools in registry with TOOL_REGISTRY_ENABLED=true | Verified |

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1, 3 | `402b5b8` | feat(22-02): append list_playbook_documents tool registration (REVIEW #1) |
| 2, 4 | `c651a77` | feat(22-02): append search_documents_by_doc_ids + unit tests for both tools (REVIEW #10) |

## Self-Check: PASSED

- [x] `backend/app/services/tool_service.py` exists and has both tools (lines 1806+)
- [x] `backend/tests/services/test_list_playbook_documents.py` exists — 7 tests
- [x] `backend/tests/services/test_search_documents_by_doc_ids.py` exists — 8 tests
- [x] Commits `402b5b8` and `c651a77` exist in git log
- [x] sha256 of lines 1-1283 unchanged: `cb63cf3e60d5f6380e2e41f63b1fe9122f58ab4648808b0f2114e452cd45ddb2`
- [x] `filter_doc_ids` count in tool_service.py: 0
