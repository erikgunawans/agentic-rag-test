---
phase: 22-contract-review-harness-docx-deliverable
plan: 02
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/app/services/tool_service.py
  - backend/tests/services/test_search_documents_by_doc_ids.py
autonomous: true
requirements: [CR-06, CR-07]
must_haves:
  truths:
    - "A new RAG tool `search_documents_by_doc_ids` is registered AFTER tool_service.py:1283 via tool_registry.register() adapter-wrap"
    - "The new tool delegates to HybridRetrievalService with a doc-id allowlist filter, no edit to the protected lines 1-1283"
    - "The Tool Registry adapter-wrap invariant pinned-hash check on tool_service.py lines 1-1283 still passes"
    - "When TOOL_REGISTRY_ENABLED=False, the new tool is NOT registered (off-mode invariant)"
  artifacts:
    - path: "backend/app/services/tool_service.py"
      provides: "Adapter-wrap registration of search_documents_by_doc_ids appended below line 1283"
      contains: "search_documents_by_doc_ids"
    - path: "backend/tests/services/test_search_documents_by_doc_ids.py"
      provides: "Unit tests for the new tool — registration, doc-id filter, adapter-wrap invariant guard"
  key_links:
    - from: "CR-06/CR-07 sub-agents"
      to: "playbook-context.md clause_category_to_playbook[category]"
      via: "search_documents_by_doc_ids(query=clause_text, doc_ids=[...])"
      pattern: "search_documents_by_doc_ids"
    - from: "tool_registry.register at end of tool_service.py"
      to: "HybridRetrievalService.retrieve()"
      via: "doc_ids parameter forwarded as filter_doc_ids RPC param"
      pattern: "filter_doc_ids"
---

<objective>
Resolve the Tool Registry adapter-wrap invariant by registering a NEW tool `search_documents_by_doc_ids` APPENDED below line 1283 of `tool_service.py` (per CLAUDE.md gotcha). This unblocks CR-06 and CR-07 sub-agents (per D-22-06) which need to call `search_documents` constrained to a specific list of document IDs (the playbook docs mapped to the clause's category).

Purpose: D-22-06 says "CR-06 and CR-07 sub-agents call `search_documents(query=clause_text, filter_doc_ids=clause_category_to_playbook[category])`." The existing `search_documents` tool lives in the protected `tool_service.py:1-1283` block (CLAUDE.md line ~178) so we cannot extend its signature in place. Resolution: ship a new sibling tool that adapter-wraps `HybridRetrievalService` and accepts a `doc_ids` parameter directly.
Output: New tool registered, unit tests, invariant-guard test.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/ROADMAP.md
@.planning/REQUIREMENTS.md
@.planning/phases/22-contract-review-harness-docx-deliverable/22-CONTEXT.md
@.planning/phases/22-contract-review-harness-docx-deliverable/22-PATTERNS.md
@CLAUDE.md
</context>

<interfaces>
<!-- Existing search_documents signature (tool_service.py:39-71, INSIDE protected range) — DO NOT MODIFY -->
<!-- Reference for parameter shapes the new tool mirrors -->

From backend/app/services/tool_service.py:39-71:
```python
{
    "name": "search_documents",
    "parameters": {
        "properties": {
            "query": {"type": "string"},
            "filter_tags": {"type": "array", "items": {"type": "string"}},
            "filter_folder_id": {"type": "string"},
            "filter_date_from": {"type": "string"},
            "filter_date_to": {"type": "string"},
        },
    },
}
```

From backend/app/services/tool_service.py:534-558 (the existing implementation we mirror):
```python
async def _execute_search_documents(self, *, query, filter_tags=None, ...) -> dict:
    # Calls HybridRetrievalService.retrieve(query, top_k=..., filter_tags=..., ...)
```

The existing adapter-wrap registration block starts at `tool_service.py:1352` (`tool_registry.register(...)`) and continues through line 1805. Plan 22-02 appends a new `tool_registry.register(...)` call AFTER the last existing one (line 1794), still APPENDED below the protected boundary (line 1283).

ISSUE-08 PIN: HybridRetrievalService.retrieve() signature (hybrid_retrieval_service.py:46-60):
```python
async def retrieve(
    self,
    query: str,
    user_id: str,
    top_k: int,
    threshold: float,
    embedding_model: str | None = None,
    llm_model: str | None = None,
    category: str | None = None,
    filter_tags: list[str] | None = None,
    filter_folder_id: str | None = None,
    filter_date_from: str | None = None,
    filter_date_to: str | None = None,
) -> list[dict]:
```

`filter_doc_ids` does NOT exist as a kwarg, and the underlying RPC functions
(`match_document_chunks_fulltext`, vector search RPC) do not accept a doc-id allowlist.

CONTEXT.md Phase 22 invariant: "No new migration. harness_runs schema covers everything."
Adding `filter_doc_ids` to the RPC SQL function would require a migration —
violating that invariant.

**Resolution (ISSUE-08 chosen path: option 2 — Python-side post-retrieval filter):**

Plan 22-02 implements doc-id restriction in the NEW tool's handler, NOT inside
HybridRetrievalService. The handler:
  1. Calls `hybrid_retrieval.retrieve(query=query, top_k=top_k * 4, ...)` — over-fetch 4×
  2. Filters returned chunks by `chunk["document_id"] in doc_ids_set`
  3. Truncates to `top_k`

Cost: one extra retrieval round-trip's worth of candidates fetched (4× normal).
For the playbook scope (typically 1-10 docs per category) this is a non-issue.
NO migration. NO change to HybridRetrievalService. NO RPC schema change.

Pseudo-code:
```python
async def _execute_search_documents_by_doc_ids(self, *, query, doc_ids, top_k=8) -> dict:
    if not isinstance(doc_ids, list) or not doc_ids:
        return {"error": "invalid_doc_ids", "code": "INVALID_DOC_IDS",
                "detail": "doc_ids must be a non-empty list"}
    if len(doc_ids) > 50:
        return {"error": "invalid_doc_ids", "code": "INVALID_DOC_IDS",
                "detail": f"doc_ids capped at 50, got {len(doc_ids)}"}
    top_k = min(int(top_k or 8), 20)
    doc_ids_set = set(doc_ids)
    over_fetch = top_k * 4
    rows = await self.hybrid_retrieval.retrieve(
        query=query, user_id=self._user_id, top_k=over_fetch,
        threshold=0.5,  # match _execute_search_documents default
    )
    filtered = [r for r in rows if r.get("document_id") in doc_ids_set][:top_k]
    return {"results": filtered}
```
</interfaces>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Append search_documents_by_doc_ids tool registration with adapter wrap</name>
  <files>backend/app/services/tool_service.py</files>
  <read_first>
    - backend/app/services/tool_service.py (lines 1280-1300 — verify the protected boundary line 1283)
    - backend/app/services/tool_service.py (lines 1785-1805 — the LAST existing tool_registry.register block, our append target)
    - backend/app/services/tool_service.py (lines 534-600 — `_execute_search_documents` analog implementation we mirror)
    - backend/app/services/tool_service.py (lines 39-71 — existing search_documents OpenAI tool definition)
    - .planning/phases/22-contract-review-harness-docx-deliverable/22-PATTERNS.md (lines 558-594 — gating decision rationale)
    - CLAUDE.md (Tool Registry adapter-wrap invariant — search for "Tool Registry adapter-wrap")
  </read_first>
  <behavior>
    - Test 1: After import, `tool_registry.get_tool_definition("search_documents_by_doc_ids")` returns a non-None OpenAI-shape dict with `parameters.properties.query`, `parameters.properties.doc_ids`.
    - Test 2: Calling the registered handler with `query="warranty"`, `doc_ids=["uuid-a", "uuid-b"]` invokes `HybridRetrievalService.retrieve(query="warranty", filter_doc_ids=["uuid-a", "uuid-b"], top_k=8)`.
    - Test 3: With `TOOL_REGISTRY_ENABLED=False`, the tool is NOT in the registry (off-mode invariant).
    - Test 4: pinned-hash check on `head -n 1283 tool_service.py` matches the value before this plan's edits (proves we did NOT touch the protected range).
  </behavior>
  <action>
    Append the following block AFTER the LAST existing `tool_registry.register(...)` call (currently ending at line ~1805) in `backend/app/services/tool_service.py`. Do NOT modify any line at index <= 1283.

    The block must:
    1. Define an OpenAI-shape tool definition for `search_documents_by_doc_ids` mirroring the existing `search_documents` schema (line 39-71) but with:
       - `name`: `"search_documents_by_doc_ids"`
       - Description: `"Hybrid RAG search restricted to a specified list of document IDs. Use when you already know the candidate documents (e.g. playbook docs mapped to a clause category) and want precise grounding from those documents only."`
       - `parameters.properties`: `{"query": {"type": "string", "description": "..."}, "doc_ids": {"type": "array", "items": {"type": "string"}, "description": "List of document UUIDs to restrict search to (max 50)"}, "top_k": {"type": "integer", "description": "Top results count, default 8, max 20"}}`
       - `parameters.required`: `["query", "doc_ids"]`
    2. Define an async handler `_execute_search_documents_by_doc_ids(self, *, query: str, doc_ids: list[str], top_k: int = 8) -> dict` that:
       - Validates `doc_ids` is non-empty list of strings (≤ 50 entries) — return `{"error": "invalid_doc_ids", "code": "INVALID_DOC_IDS", "detail": "..."}` on failure
       - Caps `top_k` at 20
       - Delegates to `self.hybrid_retrieval.retrieve(query=query, top_k=top_k, filter_doc_ids=doc_ids, ...)` reusing the same kwargs the existing `_execute_search_documents` passes for `cache_key_namespace`, `user_id`, `token`, `system_settings` — see lines 534-600 for the parameter set
       - Returns the same shape as `_execute_search_documents` (an array of result objects)
    3. Register via `tool_registry.register(...)` adapter-wrap — name must match the OpenAI schema, handler bound to the ToolService instance, gated on `settings.tool_registry_enabled` exactly like the existing 1609/1618/1627/1636 blocks above.
    4. Add a code comment block above the registration: `# Phase 22 / D-22-06 (CR-06, CR-07): doc-id-restricted hybrid RAG. Adapter-wrap APPENDED below line 1283 per CLAUDE.md Tool Registry invariant.`

    **ISSUE-08 PINNED — implementation:** `HybridRetrievalService.retrieve()` does NOT accept `filter_doc_ids` (verified in hybrid_retrieval_service.py:46-60). Adding the kwarg would require a Postgres migration to the RPC function (`match_document_chunks_fulltext`) — violating CONTEXT.md "no new migration" invariant.

    Use option 2 (Python-side post-retrieval filter): over-fetch by 4× then filter by `chunk["document_id"] in doc_ids_set`. See `<interfaces>` block above for pseudo-code. NO modification to `hybrid_retrieval_service.py`. NO RPC change. NO migration.

    Files modified by this approach: ONLY `backend/app/services/tool_service.py` (the handler, appended below line 1283).

    Update `<files_modified>` frontmatter (already only includes tool_service.py + test file — no change needed).
  </action>
  <verify>
    <automated>cd backend && source venv/bin/activate && pytest tests/services/test_search_documents_by_doc_ids.py -v --tb=short && python -c "from app.main import app; print('OK')"</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c "search_documents_by_doc_ids" backend/app/services/tool_service.py` returns `>= 4` (tool def name + handler def + registry register call + comment)
    - `grep -nE "tool_registry.register" backend/app/services/tool_service.py | tail -1 | awk -F: '{print $1}'` returns a line number `> 1805` (the new register call appended below all prior ones)
    - `head -n 1283 backend/app/services/tool_service.py | shasum -a 256` matches the value BEFORE the edit (capture the hash via `git show HEAD:backend/app/services/tool_service.py | head -n 1283 | shasum -a 256` then compare)
    - `python -c "from app.main import app; print('OK')"` prints `OK`
  </acceptance_criteria>
  <done>New tool registered, all four behavior tests pass, the pinned-hash invariant on lines 1-1283 holds, app imports cleanly.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Add unit tests including adapter-wrap invariant guard</name>
  <files>backend/tests/services/test_search_documents_by_doc_ids.py</files>
  <read_first>
    - backend/app/services/tool_service.py (post-Task-1 state, including lines 1-1283 for hash baseline)
    - backend/tests/services/test_gatekeeper.py (analog for unittest.mock.AsyncMock + pytest patterns)
    - .planning/phases/22-contract-review-harness-docx-deliverable/22-PATTERNS.md (lines 583-594 — invariant resolution rationale)
  </read_first>
  <behavior>
    - Test 1: `test_search_documents_by_doc_ids_registered_when_flag_on` — patches `settings.tool_registry_enabled=True`, re-imports, asserts `tool_registry.get_tool_definition("search_documents_by_doc_ids")` is non-None.
    - Test 2: `test_search_documents_by_doc_ids_not_registered_when_flag_off` — same but flag False, asserts None.
    - Test 3: `test_handler_filters_results_by_doc_ids_python_side` (ISSUE-08) — mock `HybridRetrievalService.retrieve` to return chunks with mixed `document_id` values; call handler with `doc_ids=["uuid-a", "uuid-b"]`; assert returned results contain ONLY chunks where `document_id in ["uuid-a", "uuid-b"]`. Assert `retrieve` was called with `top_k=top_k * 4` (over-fetch) — NOT `filter_doc_ids` kwarg.
    - Test 4: `test_handler_rejects_empty_doc_ids` — handler returns `{"error": "invalid_doc_ids", ...}` (NOT raises).
    - Test 5: `test_handler_caps_doc_ids_at_50` — handler returns invalid_doc_ids when `len(doc_ids) > 50`.
    - Test 6: `test_handler_caps_top_k_at_20` — even if caller passes `top_k=99`, the underlying retrieve call gets `top_k=20`.
    - Test 7: `test_protected_lines_unchanged` — read `backend/app/services/tool_service.py`, take first 1283 lines, hash with sha256, compare to a baseline hash committed in this test file as a constant (capture via `git show HEAD:backend/app/services/tool_service.py | head -n 1283 | shasum -a 256` from the pre-Phase-22 commit). If hash drifts, this test fails LOUDLY.
  </behavior>
  <action>
    Create `backend/tests/services/test_search_documents_by_doc_ids.py` with the seven tests above.

    Header (mirror `test_gatekeeper.py:1-19` shape):
    ```python
    """Phase 22 / Plan 22-02 — search_documents_by_doc_ids tool registration tests
    (CR-06, CR-07; D-22-06; CLAUDE.md Tool Registry adapter-wrap invariant).

    7 tests:
    1.  test_search_documents_by_doc_ids_registered_when_flag_on
    2.  test_search_documents_by_doc_ids_not_registered_when_flag_off
    3.  test_handler_forwards_doc_ids_to_hybrid_retrieval
    4.  test_handler_rejects_empty_doc_ids
    5.  test_handler_caps_doc_ids_at_50
    6.  test_handler_caps_top_k_at_20
    7.  test_protected_lines_unchanged  (CLAUDE.md invariant guard — pinned sha256)
    """
    from __future__ import annotations
    ```

    For Test 7, capture the baseline hash:
    ```python
    # Pinned sha256 of head -n 1283 tool_service.py from pre-Phase-22 (commit da18f34).
    # If this test fails, you edited the protected range — REVERT and use adapter-wrap APPEND.
    PROTECTED_HEAD_SHA256 = "<RUN: git show da18f34:backend/app/services/tool_service.py | head -n 1283 | shasum -a 256 | cut -c1-64>"

    def test_protected_lines_unchanged():
        import hashlib, pathlib
        text = pathlib.Path("backend/app/services/tool_service.py").read_text()
        head = "".join(text.splitlines(keepends=True)[:1283])
        actual = hashlib.sha256(head.encode("utf-8")).hexdigest()
        assert actual == PROTECTED_HEAD_SHA256, (
            f"Tool Registry adapter-wrap invariant VIOLATED — "
            f"tool_service.py lines 1-1283 mutated. Expected {PROTECTED_HEAD_SHA256}, got {actual}"
        )
    ```

    Compute the actual baseline hash with this command BEFORE filling in PROTECTED_HEAD_SHA256:
    `git show da18f34:backend/app/services/tool_service.py | head -n 1283 | shasum -a 256`

    Use `unittest.mock.AsyncMock` for `HybridRetrievalService.retrieve` and `MagicMock` for `Settings`.
  </action>
  <verify>
    <automated>cd backend && source venv/bin/activate && pytest tests/services/test_search_documents_by_doc_ids.py -v --tb=short</automated>
  </verify>
  <acceptance_criteria>
    - `pytest backend/tests/services/test_search_documents_by_doc_ids.py -v` exits 0 with 7 tests passing
    - `grep -c "PROTECTED_HEAD_SHA256" backend/tests/services/test_search_documents_by_doc_ids.py` returns `>= 2` (constant + test usage)
    - `grep -c "filter_doc_ids" backend/tests/services/test_search_documents_by_doc_ids.py` returns `>= 1`
  </acceptance_criteria>
  <done>All 7 tests pass; the pinned-hash invariant test is the regression guard for the protected range.</done>
</task>

</tasks>

<truths>
- D-22-06 (per-clause grounding via doc-id filter) drives this plan.
- CLAUDE.md Tool Registry adapter-wrap invariant: `tool_service.py` lines 1-1283 are FROZEN. PATTERNS.md L585-594 confirms resolution: register a NEW tool below line 1283 (option b), NOT amend the existing `search_documents` (option a).
- D-16 OFF-mode invariant: when `tool_registry_enabled=False`, new tool is NOT registered. Plan 22-04 + 22-08 add `contract_review_enabled` flag separately; this tool is gated only by the existing `tool_registry_enabled` master.
- B4 single-registry (SEC-04): the new tool's handler runs through the same egress filter as the existing `search_documents` because it's invoked from the same sub_agent_loop wrap.
</truths>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| LLM tool call → tool dispatcher | LLM-generated `doc_ids` could include arbitrary UUIDs; bounded to ≤ 50 |
| tool dispatcher → HybridRetrievalService | RPC params validated by Postgres + RLS — users only see their own + global docs |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-22-02-01 | Tampering | LLM-supplied doc_ids list | mitigate | Validate non-empty + ≤ 50 entries; cap top_k at 20 to bound cost |
| T-22-02-02 | Information Disclosure | Sub-agent searching across user_id | mitigate | Existing RLS on documents + token-scoped client (matches `_execute_search_documents` pattern) |
| T-22-02-03 | Tampering | Edits to protected tool_service.py:1-1283 | mitigate | sha256-pinned `test_protected_lines_unchanged` regression guard |
</threat_model>

<verification>
1. `python -c "from app.main import app; print('OK')"` prints `OK`
2. `pytest backend/tests/services/test_search_documents_by_doc_ids.py -v` exits 0
3. `head -n 1283 backend/app/services/tool_service.py | shasum -a 256` unchanged from pre-Phase-22 baseline
4. `python -c "from app.services.tool_service import tool_registry; print('search_documents_by_doc_ids' in {t['function']['name'] for t in tool_registry.get_all_definitions()})"` prints `True` (when TOOL_REGISTRY_ENABLED=True)
</verification>

<success_criteria>
- `search_documents_by_doc_ids` tool registered, callable from sub-agents
- Adapter-wrap invariant preserved (sha256 baseline test passes)
- CR-06 and CR-07 (plan 22-09) can call this tool with `doc_ids=playbook_context.clause_category_to_playbook[category]`
- Off-mode flag-gated identical to peer tools
</success_criteria>

<output>
After completion, create `.planning/phases/22-contract-review-harness-docx-deliverable/22-02-SUMMARY.md`.
</output>
