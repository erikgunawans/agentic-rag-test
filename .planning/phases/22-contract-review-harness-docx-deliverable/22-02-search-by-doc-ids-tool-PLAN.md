---
phase: 22-contract-review-harness-docx-deliverable
plan: 02
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/app/services/tool_service.py
  - backend/tests/services/test_search_documents_by_doc_ids.py
  - backend/tests/services/test_list_playbook_documents.py
autonomous: true
requirements: [CR-04, CR-06, CR-07]
must_haves:
  truths:
    - "TWO new RAG tools registered AFTER tool_service.py:1283 via tool_registry.register() adapter-wrap (REVIEW #1: playbook discovery has no tool surface — search_documents returns chunks not doc_ids, and analyze_document does NOT exist)"
    - "Tool A: `list_playbook_documents` — returns [{doc_id, title, summary}] for documents tagged `playbook` (replaces the broken `playbook_docs -> analyze_document` chain assumed by previous plan 22-07)"
    - "Tool B: `search_documents_by_doc_ids` — Python-side overfetch-and-filter; HybridRetrievalService.retrieve does NOT accept filter_doc_ids (REVIEW #10: prior plan was self-contradictory — some tasks said yes, ISSUE-08 said no)"
    - "Both tools delegate to existing services; NO edit to tool_service.py:1-1283 protected range"
    - "When TOOL_REGISTRY_ENABLED=False, neither tool is registered (off-mode invariant)"
  artifacts:
    - path: "backend/app/services/tool_service.py"
      provides: "Adapter-wrap registration of list_playbook_documents + search_documents_by_doc_ids appended below line 1283"
      contains: "list_playbook_documents"
    - path: "backend/tests/services/test_list_playbook_documents.py"
      provides: "Unit tests for the playbook-discovery tool"
    - path: "backend/tests/services/test_search_documents_by_doc_ids.py"
      provides: "Unit tests for doc-id restricted search; adapter-wrap invariant guard"
  key_links:
    - from: "CR-04 sub-agent (load-playbook)"
      to: "list_playbook_documents()"
      via: "tool call returns [{doc_id, title, summary}] — sub-agent populates clause_category_to_playbook from this list"
      pattern: "list_playbook_documents"
    - from: "CR-06/CR-07 sub-agents"
      to: "playbook_context.clause_category_to_playbook[category]"
      via: "search_documents_by_doc_ids(query=clause_text, doc_ids=[...])"
      pattern: "search_documents_by_doc_ids"
---

<objective>
Build the missing tool surface for playbook grounding (REVIEW #1) AND the doc-id-restricted RAG tool (REVIEW #10). BOTH tools register via adapter-wrap APPENDED below line 1283 of `tool_service.py` (CLAUDE.md gotcha — protected range frozen).

**REVIEW #1 anchor:** `search_documents` returns chunks (filename/category/tags) but NOT `doc_id`s. There is no `analyze_document` tool in this checkout (`grep -c "analyze_document" backend/app/services/tool_service.py` returns 0). The previous plan 22-07 chain `playbook_docs -> analyze_document -> clause_category_to_playbook` cannot work.

**Resolution:** add `list_playbook_documents` — a deterministic, non-RAG tool that queries `documents` table for rows where `metadata->>'tags'` contains `playbook` (D-22-05) and returns `[{doc_id, title, summary}]`. CR-04 sub-agent calls this ONCE early to enumerate the playbook surface, then optionally calls `search_documents_by_doc_ids` to fetch chunks per doc.

**REVIEW #10 anchor:** `HybridRetrievalService.retrieve()` does NOT accept `filter_doc_ids` (verified `hybrid_retrieval_service.py:46-60`). Adding the kwarg requires a Postgres RPC migration, violating the "no new migration" invariant. Resolution: Python-side overfetch-and-filter in the new tool's handler. Prior plan was self-contradictory — clean up ALL references to ensure single-path implementation.

Output: TWO new tools registered, three test files, invariant-guard test.
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
@.planning/phases/22-contract-review-harness-docx-deliverable/22-REVIEWS.md
@CLAUDE.md
</context>

<interfaces>
<!-- Existing search_documents signature (tool_service.py:39-71, INSIDE protected range) — DO NOT MODIFY -->
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
Returns: chunks (filename/category/tags/snippet) — NOT doc_ids.
There is NO `analyze_document` tool in this checkout. REVIEW #1: the previous CR-04
plan referenced `analyze_document` as if it existed; it does not. CR-04 must instead
use `list_playbook_documents` (this plan) for enumeration.

HybridRetrievalService.retrieve() signature (hybrid_retrieval_service.py:46-60):
```python
async def retrieve(
    self, query, user_id, top_k, threshold,
    embedding_model=None, llm_model=None, category=None,
    filter_tags=None, filter_folder_id=None,
    filter_date_from=None, filter_date_to=None,
) -> list[dict]:
```
`filter_doc_ids` does NOT exist. The underlying RPC functions don't accept it.
Adding it would require a migration — violates CONTEXT.md "no new migration" invariant.

**Resolution path (single-source-of-truth — REVIEW #10):**
Python-side overfetch-and-filter in `_execute_search_documents_by_doc_ids`:
  1. retrieve(query, top_k=top_k * 4, ...)  # overfetch 4×
  2. filter rows by `r["document_id"] in doc_ids_set`
  3. truncate to top_k
NO migration. NO RPC change. NO HybridRetrievalService modification.

**list_playbook_documents query path (D-22-05 — REVIEW #1 fix):**
Direct Supabase query via `get_supabase_authed_client(token).table("documents")`:
```python
.select("id, filename, metadata")
.eq("user_id", user_id)
.execute()
# Then Python-side filter where row.metadata.tags contains "playbook"
# (Supabase Python SDK has limited jsonb operator support; client-side is simpler)
```
Build `{doc_id, title, summary}` per row. `summary` derived from `metadata.summary`
(if present) OR truncated `metadata.first_chunk_text` OR empty string.

**TWO tool definitions plus TWO handlers; TWO tool_registry.register() calls APPENDED below line 1283. Zero edits to lines 1-1283 (CLAUDE.md invariant + sha256 pin test).**
</interfaces>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Append list_playbook_documents tool registration (REVIEW #1 — playbook discovery surface)</name>
  <files>backend/app/services/tool_service.py</files>
  <read_first>
    - backend/app/services/tool_service.py (lines 1280-1300 — confirm the protected boundary line 1283)
    - backend/app/services/tool_service.py (lines 1785-1805 — LAST existing tool_registry.register block, append target)
    - backend/app/routers/documents.py (lines 134-150 — `list_documents` endpoint shape — same `documents` table, RLS-scoped client)
    - backend/app/services/tool_service.py (lines 540-595 — _execute_search_documents pattern for ToolService instance state — `self._user_id`, `self._token`, `self._client`)
    - .planning/phases/22-contract-review-harness-docx-deliverable/22-REVIEWS.md (review finding #1 — verbatim)
    - CLAUDE.md (Tool Registry adapter-wrap invariant)
  </read_first>
  <behavior>
    - Test 1: After import, `tool_registry.get_tool_definition("list_playbook_documents")` returns a non-None OpenAI-shape dict with `parameters.properties.limit` (optional, default 50).
    - Test 2: Calling the registered handler queries `documents` via the authed client, filters by `metadata.tags contains 'playbook'`, returns `{"results": [{"doc_id": ..., "title": ..., "summary": ...}]}`.
    - Test 3: Handler tolerates missing `metadata.summary` field — falls back to empty string.
    - Test 4: Handler caps results at `limit` (default 50, max 100).
    - Test 5: With `TOOL_REGISTRY_ENABLED=False`, the tool is NOT in the registry.
    - Test 6: Handler returns `{"results": []}` (NOT error) when no playbook-tagged docs exist (D-22-07 empty-playbook fallback path — sub-agent gracefully handles empty result).
  </behavior>
  <action>
    Append the following block AFTER the LAST existing `tool_registry.register(...)` call (currently ending around line 1805) in `backend/app/services/tool_service.py`. Do NOT modify any line at index <= 1283.

    Add a code comment block: `# Phase 22 / D-22-05 / REVIEW #1 (CR-04): playbook discovery tool. Returns {doc_id, title, summary} for documents tagged 'playbook'. Adapter-wrap APPENDED below line 1283.`

    Define an OpenAI-shape tool definition for `list_playbook_documents`:
    - `name`: `"list_playbook_documents"`
    - `description`: `"List documents tagged 'playbook' in the user's accessible knowledge base. Returns doc_id + title + short summary per playbook document. Use this ONCE near the start of CR-04 to enumerate the playbook surface; downstream you map clause categories to playbook doc_ids and call search_documents_by_doc_ids for grounded retrieval."`
    - `parameters.properties`:
      - `limit`: `{"type": "integer", "description": "Max docs to return (default 50, max 100)"}`
    - `parameters.required`: `[]` (limit is optional)

    Define an async handler:
    ```python
    async def _execute_list_playbook_documents(
        self, *, limit: int | None = None
    ) -> dict:
        """REVIEW #1 fix: enumerate playbook-tagged documents.

        Mirrors the documents.list_documents endpoint but filters server-side query
        by user_id (RLS) and CLIENT-SIDE filter by metadata.tags contains 'playbook'.
        Supabase Python SDK jsonb-ops are limited; client-side is simpler and the
        playbook corpus is typically small (~10-100 docs).
        """
        cap = max(1, min(int(limit or 50), 100))
        try:
            # Reuse the same authed client pattern as _execute_search_documents
            from app.deps import get_supabase_authed_client
            client = get_supabase_authed_client(self._token)
            rows = (
                client.table("documents")
                .select("id, filename, metadata")
                .eq("user_id", self._user_id)
                .execute()
                .data
                or []
            )
        except Exception as exc:
            return {"error": "documents_query_failed", "code": "DOCS_QUERY", "detail": str(exc)[:500]}

        results: list[dict] = []
        for row in rows:
            meta = row.get("metadata") or {}
            tags = meta.get("tags") or []
            if not isinstance(tags, list):
                continue
            if "playbook" not in tags:
                continue
            summary = (meta.get("summary") or meta.get("first_chunk_text") or "")[:300]
            results.append({
                "doc_id": str(row["id"]),
                "title": row.get("filename") or "",
                "summary": summary,
            })
            if len(results) >= cap:
                break

        return {"results": results}
    ```

    Register via `tool_registry.register(...)` adapter-wrap, gated on `settings.tool_registry_enabled` exactly like the existing 1609/1618/etc. blocks. Bind handler to the ToolService instance.
  </action>
  <verify>
    <automated>cd backend && source venv/bin/activate && pytest tests/services/test_list_playbook_documents.py -v --tb=short && python -c "from app.main import app; print('OK')"</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c "list_playbook_documents" backend/app/services/tool_service.py` returns `>= 4` (tool def name + handler def + register call + comment)
    - `grep -nE "tool_registry.register" backend/app/services/tool_service.py | tail -1 | awk -F: '{print $1}'` returns line `> 1805`
    - `head -n 1283 backend/app/services/tool_service.py | shasum -a 256` unchanged from pre-Phase-22 baseline
    - `python -c "from app.main import app; print('OK')"` prints `OK`
    - `python -c "from app.services.tool_service import tool_registry; print('list_playbook_documents' in {t['function']['name'] for t in tool_registry.get_all_definitions()})"` prints `True` (when TOOL_REGISTRY_ENABLED=True)
  </acceptance_criteria>
  <done>list_playbook_documents tool registered, handler queries documents.metadata.tags, off-mode flag-gated.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Append search_documents_by_doc_ids tool registration (REVIEW #10 — single-source Python-side filter)</name>
  <files>backend/app/services/tool_service.py</files>
  <read_first>
    - backend/app/services/tool_service.py (post-Task-1 state — find the new registration block, append AFTER it)
    - backend/app/services/tool_service.py (lines 534-600 — `_execute_search_documents` analog implementation)
    - backend/app/services/hybrid_retrieval_service.py (lines 46-60 — confirm `filter_doc_ids` does NOT exist on retrieve())
    - .planning/phases/22-contract-review-harness-docx-deliverable/22-REVIEWS.md (review finding #10)
  </read_first>
  <behavior>
    - Test 1: After import, `tool_registry.get_tool_definition("search_documents_by_doc_ids")` returns a non-None OpenAI-shape dict with `parameters.properties.query` and `parameters.properties.doc_ids`.
    - Test 2: Calling the registered handler with `query="warranty"`, `doc_ids=["uuid-a", "uuid-b"]` invokes `HybridRetrievalService.retrieve(query="warranty", top_k=top_k * 4)` (NOT with `filter_doc_ids` kwarg — that does not exist).
    - Test 3: Returned results are filtered by `r["document_id"] in {"uuid-a", "uuid-b"}` — Python-side.
    - Test 4: With `TOOL_REGISTRY_ENABLED=False`, the tool is NOT in the registry.
    - Test 5: pinned-hash check on `head -n 1283 tool_service.py` matches the value before this plan's edits.
    - Test 6: `_execute_search_documents_by_doc_ids` rejects empty `doc_ids` (returns `{"error": "invalid_doc_ids", ...}`).
    - Test 7: `_execute_search_documents_by_doc_ids` caps `doc_ids` at 50 entries.
  </behavior>
  <action>
    Append the following block AFTER the `list_playbook_documents` registration from Task 1. Do NOT modify any line at index <= 1283.

    Add comment: `# Phase 22 / D-22-06 / REVIEW #10 (CR-06, CR-07): doc-id-restricted hybrid RAG via Python-side overfetch-and-filter. HybridRetrievalService.retrieve() does NOT accept filter_doc_ids (would require RPC migration). Adapter-wrap APPENDED below line 1283.`

    Define OpenAI-shape tool definition for `search_documents_by_doc_ids`:
    - `name`: `"search_documents_by_doc_ids"`
    - `description`: `"Hybrid RAG search restricted to a specified list of document IDs. Use when you already know the candidate documents (e.g. playbook docs mapped to a clause category from list_playbook_documents) and want grounded retrieval from those documents only."`
    - `parameters.properties`:
      - `query`: string
      - `doc_ids`: array of strings, max 50
      - `top_k`: integer, default 8, max 20
    - `parameters.required`: `["query", "doc_ids"]`

    Define handler:
    ```python
    async def _execute_search_documents_by_doc_ids(
        self, *, query: str, doc_ids: list[str], top_k: int = 8
    ) -> dict:
        """REVIEW #10: Python-side overfetch-and-filter — HybridRetrievalService.retrieve()
        does NOT accept filter_doc_ids; adding it would require a Postgres RPC migration,
        violating CONTEXT.md 'no new migration' invariant.

        Strategy:
          1. retrieve(query, top_k=top_k * 4, ...)  — overfetch
          2. filter by `chunk["document_id"] in doc_ids_set`
          3. truncate to top_k
        """
        if not isinstance(doc_ids, list) or not doc_ids:
            return {"error": "invalid_doc_ids", "code": "INVALID_DOC_IDS",
                    "detail": "doc_ids must be a non-empty list"}
        if len(doc_ids) > 50:
            return {"error": "invalid_doc_ids", "code": "INVALID_DOC_IDS",
                    "detail": f"doc_ids capped at 50, got {len(doc_ids)}"}

        capped_top_k = min(int(top_k or 8), 20)
        doc_ids_set = set(doc_ids)
        over_fetch = capped_top_k * 4

        try:
            rows = await self.hybrid_retrieval.retrieve(
                query=query,
                user_id=self._user_id,
                top_k=over_fetch,
                threshold=0.5,  # match _execute_search_documents default
            )
        except Exception as exc:
            return {"error": "retrieval_failed", "code": "RETRIEVAL_ERR", "detail": str(exc)[:500]}

        filtered = [r for r in rows if r.get("document_id") in doc_ids_set][:capped_top_k]
        return {"results": filtered}
    ```

    Note: handler MUST NOT pass `filter_doc_ids=` kwarg to `retrieve()`. Test 2 enforces this — any drift back to the nonexistent kwarg will fail the test.

    Register via `tool_registry.register(...)` gated on `settings.tool_registry_enabled`.
  </action>
  <verify>
    <automated>cd backend && source venv/bin/activate && pytest tests/services/test_search_documents_by_doc_ids.py -v --tb=short && python -c "from app.main import app; print('OK')"</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c "search_documents_by_doc_ids" backend/app/services/tool_service.py` returns `>= 4`
    - `grep -c "filter_doc_ids" backend/app/services/tool_service.py` returns `0` (Python-side filter does NOT use that kwarg name; pure absence proves single-source-of-truth)
    - `head -n 1283 backend/app/services/tool_service.py | shasum -a 256` unchanged from pre-Phase-22 baseline
    - `python -c "from app.main import app; print('OK')"` prints `OK`
    - `python -c "from app.services.tool_service import tool_registry; print('search_documents_by_doc_ids' in {t['function']['name'] for t in tool_registry.get_all_definitions()})"` prints `True`
  </acceptance_criteria>
  <done>Tool registered, Python-side filter works, sha256 invariant holds, no `filter_doc_ids` references anywhere.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: Unit tests for list_playbook_documents</name>
  <files>backend/tests/services/test_list_playbook_documents.py</files>
  <read_first>
    - backend/app/services/tool_service.py (post-Task-1 + Task-2 state)
    - backend/tests/services/test_gatekeeper.py (analog for unittest.mock.AsyncMock + pytest patterns)
  </read_first>
  <behavior>
    - Test 1: `test_list_playbook_documents_registered_when_flag_on` — flag True, tool present in registry.
    - Test 2: `test_list_playbook_documents_not_registered_when_flag_off` — flag False, tool absent.
    - Test 3: `test_handler_filters_by_playbook_tag` — mock supabase client returns 5 docs with mixed tags; assert handler returns only docs where `tags` includes `'playbook'`.
    - Test 4: `test_handler_returns_doc_id_title_summary_shape` — every result has the 3 fields, `summary` is `<= 300 chars`.
    - Test 5: `test_handler_falls_back_to_empty_summary` — when `metadata.summary` and `metadata.first_chunk_text` both missing, summary is empty string (not error).
    - Test 6: `test_handler_caps_at_limit` — when 200 docs match, only `limit` (default 50, max 100) returned.
    - Test 7: `test_handler_returns_empty_when_no_playbook_docs` — D-22-07 fallback compatibility — no error, empty results array.
  </behavior>
  <action>
    Create `backend/tests/services/test_list_playbook_documents.py`. Header:
    ```python
    """Phase 22 / Plan 22-02 / REVIEW #1 — list_playbook_documents tool tests.

    7 tests covering registration gating, tag filter, shape, fallbacks, limits.
    """
    from __future__ import annotations
    ```

    Mock `get_supabase_authed_client` to return a chain `.table(...).select(...).eq(...).execute()` whose `.data` is a list of canned doc rows. Use MagicMock for the chain.

    Concrete test 3 body:
    ```python
    @pytest.mark.asyncio
    async def test_handler_filters_by_playbook_tag(monkeypatch):
        from app.services.tool_service import ToolService
        canned_rows = [
            {"id": "uuid-a", "filename": "Master Indemnity Playbook.pdf",
             "metadata": {"tags": ["playbook", "indemnity"], "summary": "Indemnity rules."}},
            {"id": "uuid-b", "filename": "Random Memo.docx",
             "metadata": {"tags": ["memo"], "summary": "Internal memo."}},
            {"id": "uuid-c", "filename": "Liability Playbook.pdf",
             "metadata": {"tags": ["playbook"], "first_chunk_text": "Liability principles..."}},
        ]
        client = MagicMock()
        client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(data=canned_rows)
        monkeypatch.setattr("app.deps.get_supabase_authed_client", lambda token: client)

        ts = ToolService(user_id="u", token="tok")
        result = await ts._execute_list_playbook_documents()
        ids = {r["doc_id"] for r in result["results"]}
        assert ids == {"uuid-a", "uuid-c"}, "must include only playbook-tagged docs"
        assert "uuid-b" not in ids, "memo-tagged doc must be excluded"
    ```
  </action>
  <verify>
    <automated>cd backend && source venv/bin/activate && pytest tests/services/test_list_playbook_documents.py -v --tb=short</automated>
  </verify>
  <acceptance_criteria>
    - `pytest backend/tests/services/test_list_playbook_documents.py -v` exits 0 with 7 tests passing
    - `grep -c "playbook" backend/tests/services/test_list_playbook_documents.py` returns `>= 4`
    - `grep -c "REVIEW #1" backend/tests/services/test_list_playbook_documents.py` returns `>= 1`
  </acceptance_criteria>
  <done>7 tests pass — list_playbook_documents tool locked in.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 4: Unit tests for search_documents_by_doc_ids + adapter-wrap invariant guard</name>
  <files>backend/tests/services/test_search_documents_by_doc_ids.py</files>
  <read_first>
    - backend/app/services/tool_service.py (post-Task-2 state, including lines 1-1283 for hash baseline)
    - backend/tests/services/test_gatekeeper.py (AsyncMock + pytest patterns)
  </read_first>
  <behavior>
    - Test 1: `test_registered_when_flag_on` — flag True, tool present.
    - Test 2: `test_not_registered_when_flag_off` — flag False, tool absent.
    - Test 3: `test_handler_filters_results_by_doc_ids_python_side` (REVIEW #10) — mock `HybridRetrievalService.retrieve` returns chunks with mixed `document_id`s; call handler with `doc_ids=["uuid-a", "uuid-b"]`; assert returned chunks ALL have document_id in that set. Crucially: assert `retrieve` called with `top_k=top_k * 4` (over-fetch) and NOT with `filter_doc_ids=` kwarg (which does not exist).
    - Test 4: `test_handler_rejects_empty_doc_ids` — error dict `{"error": "invalid_doc_ids", ...}` returned (not raised).
    - Test 5: `test_handler_caps_doc_ids_at_50`.
    - Test 6: `test_handler_caps_top_k_at_20` — even if caller passes 99, retrieve gets 20*4=80.
    - Test 7: `test_protected_lines_unchanged` — sha256 baseline of head -n 1283 tool_service.py matches pre-Phase-22 commit hash.
    - Test 8 (REVIEW #10 anti-regression): `test_handler_does_not_pass_filter_doc_ids_kwarg` — explicit assertion that `retrieve` was NOT called with a `filter_doc_ids` kwarg in any signature. Prevents future drift back to the nonexistent kwarg.
  </behavior>
  <action>
    Create `backend/tests/services/test_search_documents_by_doc_ids.py`. Header:
    ```python
    """Phase 22 / Plan 22-02 / REVIEW #10 — search_documents_by_doc_ids tool tests.

    8 tests:
    1.  test_registered_when_flag_on
    2.  test_not_registered_when_flag_off
    3.  test_handler_filters_results_by_doc_ids_python_side
    4.  test_handler_rejects_empty_doc_ids
    5.  test_handler_caps_doc_ids_at_50
    6.  test_handler_caps_top_k_at_20
    7.  test_protected_lines_unchanged  (CLAUDE.md invariant guard — sha256 pin)
    8.  test_handler_does_not_pass_filter_doc_ids_kwarg  (REVIEW #10 anti-drift)
    """
    from __future__ import annotations
    ```

    For Test 7, capture the baseline hash via:
    `git show HEAD~1:backend/app/services/tool_service.py | head -n 1283 | shasum -a 256 | cut -c1-64`
    BEFORE Plan 22-02 lands. Hard-code the result as `PROTECTED_HEAD_SHA256` constant.

    Concrete test 3 body (REVIEW #10 anti-regression):
    ```python
    @pytest.mark.asyncio
    async def test_handler_filters_results_by_doc_ids_python_side(monkeypatch):
        from app.services.tool_service import ToolService

        canned_chunks = [
            {"document_id": "uuid-a", "content": "playbook A chunk 1"},
            {"document_id": "uuid-b", "content": "playbook B chunk 1"},
            {"document_id": "uuid-c", "content": "non-playbook chunk"},  # must be filtered out
            {"document_id": "uuid-a", "content": "playbook A chunk 2"},
        ]
        retrieve_mock = AsyncMock(return_value=canned_chunks)

        ts = ToolService(user_id="u", token="tok")
        ts.hybrid_retrieval = MagicMock()
        ts.hybrid_retrieval.retrieve = retrieve_mock

        result = await ts._execute_search_documents_by_doc_ids(
            query="warranty", doc_ids=["uuid-a", "uuid-b"], top_k=4,
        )
        assert all(r["document_id"] in {"uuid-a", "uuid-b"} for r in result["results"])
        assert "uuid-c" not in [r["document_id"] for r in result["results"]]

        # REVIEW #10 anti-regression: retrieve called with overfetch top_k, NOT filter_doc_ids kwarg
        call = retrieve_mock.call_args
        assert call.kwargs.get("top_k") == 16, "must overfetch 4x (top_k * 4)"
        assert "filter_doc_ids" not in call.kwargs, (
            "REGRESSION: handler is passing filter_doc_ids kwarg, but "
            "HybridRetrievalService.retrieve() does NOT accept it. "
            "See review finding #10."
        )
    ```

    Concrete test 8 body:
    ```python
    @pytest.mark.asyncio
    async def test_handler_does_not_pass_filter_doc_ids_kwarg():
        """REVIEW #10 hard guard: retrieve() does not accept filter_doc_ids; verify
        the handler ALWAYS uses Python-side filtering and never the (nonexistent) kwarg."""
        from app.services.tool_service import ToolService
        retrieve_mock = AsyncMock(return_value=[])
        ts = ToolService(user_id="u", token="tok")
        ts.hybrid_retrieval = MagicMock()
        ts.hybrid_retrieval.retrieve = retrieve_mock

        await ts._execute_search_documents_by_doc_ids(
            query="x", doc_ids=["a"], top_k=8,
        )
        for call in retrieve_mock.call_args_list:
            assert "filter_doc_ids" not in (call.kwargs or {})
    ```
  </action>
  <verify>
    <automated>cd backend && source venv/bin/activate && pytest tests/services/test_search_documents_by_doc_ids.py -v --tb=short</automated>
  </verify>
  <acceptance_criteria>
    - `pytest backend/tests/services/test_search_documents_by_doc_ids.py -v` exits 0 with 8 tests passing
    - `grep -c "filter_doc_ids" backend/tests/services/test_search_documents_by_doc_ids.py` returns `>= 2` (Test 3 + Test 8 anti-regression assertions)
    - `grep -c "PROTECTED_HEAD_SHA256" backend/tests/services/test_search_documents_by_doc_ids.py` returns `>= 2`
    - `grep -c "REVIEW #10" backend/tests/services/test_search_documents_by_doc_ids.py` returns `>= 1`
  </acceptance_criteria>
  <done>8 tests pass; sha256 invariant guard + REVIEW #10 anti-drift guard locked in.</done>
</task>

</tasks>

<truths>
- D-22-05 (filter_tags=['playbook']) preserved — `list_playbook_documents` is the per-doc enumerator, `search_documents` (existing) does the chunk-level RAG.
- D-22-06 (per-clause grounding via doc-id filter) — `search_documents_by_doc_ids` enables CR-06/07 sub-agents to retrieve grounded chunks.
- REVIEW #1 closed: `analyze_document` does NOT exist; CR-04 must use `list_playbook_documents` instead. Plan 22-07 will be updated to remove `analyze_document` references.
- REVIEW #10 closed: prior plan was self-contradictory on `filter_doc_ids`. This plan: Python-side overfetch-and-filter ONLY. Test 8 hard-guards against drift.
- CLAUDE.md Tool Registry adapter-wrap invariant: lines 1-1283 FROZEN; both new tools register APPEND-ONLY.
- D-16 OFF-mode invariant: when `tool_registry_enabled=False`, neither tool is registered.
- B4 single-registry (SEC-04): both new tools' handlers run through the same egress filter as existing `search_documents` because they're invoked from the same sub_agent_loop wrap.
</truths>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| LLM tool call → tool dispatcher | LLM-generated `doc_ids` could include arbitrary UUIDs; bounded to ≤ 50 |
| tool dispatcher → HybridRetrievalService | RPC params validated by Postgres + RLS |
| tool dispatcher → documents table (list_playbook_documents) | RLS enforced by authed client; only user's accessible docs returned |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-22-02-01 | Tampering | LLM-supplied doc_ids list | mitigate | Validate non-empty + ≤ 50 entries; cap top_k at 20 |
| T-22-02-02 | Information Disclosure | Cross-user playbook leakage | mitigate | RLS on `documents` + token-scoped client + `eq("user_id", self._user_id)` filter |
| T-22-02-03 | Tampering | Edits to protected tool_service.py:1-1283 | mitigate | sha256-pinned `test_protected_lines_unchanged` |
| T-22-02-04 | Information Disclosure | summary field leaking sensitive doc content | accept | Capped at 300 chars; user can ONLY see their own docs |
</threat_model>

<verification>
1. `python -c "from app.main import app; print('OK')"` prints `OK`
2. `pytest backend/tests/services/test_list_playbook_documents.py backend/tests/services/test_search_documents_by_doc_ids.py -v` exits 0
3. `head -n 1283 backend/app/services/tool_service.py | shasum -a 256` unchanged from pre-Phase-22 baseline
4. `grep -c "filter_doc_ids" backend/app/services/tool_service.py` returns `0` (REVIEW #10 anti-drift)
5. `python -c "from app.services.tool_service import tool_registry; names = {t['function']['name'] for t in tool_registry.get_all_definitions()}; assert 'list_playbook_documents' in names; assert 'search_documents_by_doc_ids' in names; print('OK')"` prints `OK`
</verification>

<success_criteria>
- Two new tools registered, callable from CR-04/CR-06/CR-07 sub-agents
- `analyze_document` no longer assumed (plan 22-07 must drop references)
- `filter_doc_ids` no longer assumed anywhere (plan 22-09 must align)
- Adapter-wrap invariant preserved (sha256 baseline test passes)
- Off-mode flag-gated identical to peer tools
</success_criteria>

<output>
After completion, create `.planning/phases/22-contract-review-harness-docx-deliverable/22-02-SUMMARY.md`.
</output>
