---
phase: 22-contract-review-harness-docx-deliverable
plan: 08
type: execute
wave: 4
depends_on: ["22-06", "22-07"]
files_modified:
  - backend/app/services/harness_engine.py
  - backend/app/harnesses/contract_review.py
  - backend/app/harnesses/smoke_echo.py
  - backend/tests/harnesses/test_contract_review_cr05.py
  - backend/tests/services/test_harness_engine_programmatic_registry.py
autonomous: true
requirements: [CR-05]
must_haves:
  truths:
    - "REVIEW #4 closed: programmatic executor contract extended to receive `registry` and `system_settings`. CR-05's per-chunk LLM call goes through egress_filter(payload, registry, None) BEFORE the OpenRouterService call — privacy invariant (SEC-04 / B4 single-registry) preserved."
    - "Engine PROGRAMMATIC dispatcher (harness_engine.py:489 area) passes registry + system_settings + user_id + user_email to programmatic executors as kwargs"
    - "smoke_echo's existing programmatic executors are backward-compatible — they accept **kwargs (or are updated to ignore the new kwargs)"
    - "CR-05 (extract-clauses) is a programmatic phase that internally calls an LLM per chunk to extract clauses (each call WRAPPED by egress_filter)"
    - "Output is a JSON array of clauses with fields {category, heading, text, position} — categories restricted to the 13 from CR-04"
    - "Contracts >50k tokens chunk with overlap and dedupe-merge across chunks"
    - "Empty contract or extraction failure returns error dict, not exception"
  artifacts:
    - path: "backend/app/services/harness_engine.py"
      provides: "PROGRAMMATIC dispatcher passes registry + system_settings to executor (REVIEW #4 fix)"
      contains: "registry=registry"
    - path: "backend/app/harnesses/contract_review.py"
      provides: "_phase5_extract_clauses executor + Clause/ClauseExtractionResult schemas + per-chunk egress_filter wrap"
      contains: "egress_filter"
    - path: "backend/tests/harnesses/test_contract_review_cr05.py"
      provides: "Tests for chunking, dedupe, category restriction, empty-contract fallback, egress_filter wrap"
    - path: "backend/tests/services/test_harness_engine_programmatic_registry.py"
      provides: "Test that engine passes registry to programmatic executors (REVIEW #4 contract test)"
  key_links:
    - from: "_phase5_extract_clauses"
      to: "egress_filter(payload, registry, None) BEFORE OpenRouterService.complete"
      via: "SEC-04 / B4 single-registry preserved (REVIEW #4)"
      pattern: "egress_filter"
    - from: "_phase5_extract_clauses output"
      to: "clauses.md + clauses.json"
      via: "CR-05 sibling write (clauses.json for batch dispatcher consumption per ISSUE-04)"
      pattern: "clauses\\.json"
---

<objective>
Replace the CR-05 (extract-clauses) stub. CR-05 is programmatic with an internal per-chunk LLM call. Per **REVIEW #4** ("CR-05's internal LLM calls would BYPASS the SEC-04 egress-filter path"), this plan now:

1. **Extends the programmatic executor contract** so the engine passes `registry` (the conversation `ConversationRegistry`) and `system_settings` to every programmatic executor as kwargs.
2. **CR-05's `_phase5_extract_clauses`** wraps each per-chunk LLM call in `egress_filter(payload, registry, None)` — matching the LLM_SINGLE dispatcher pattern at `harness_engine.py:543-554`. If the filter trips, the chunk is treated as a per-chunk failure (counted, but the phase continues with remaining chunks).

The privacy invariant is now structurally enforced. CR-05's contract LLM payloads CANNOT bypass the egress filter.

Output: 1 engine change + CR-05 implementation + 2 test files.
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
@backend/app/harnesses/contract_review.py
@backend/app/services/harness_engine.py
</context>

<interfaces>
<!-- Existing PROGRAMMATIC dispatcher (harness_engine.py:475-520 area) -->
<!--   Currently calls: result = await phase.executor(inputs=inputs, token=token, thread_id=thread_id, harness_run_id=harness_run_id) -->
<!-- REVIEW #4 fix: extend the kwargs to include registry, system_settings, user_id, user_email. -->

REVIEW #4 fix — extended programmatic executor signature:
```python
async def _phase_executor(
    *,
    inputs: dict[str, str],
    token: str,
    thread_id: str,
    harness_run_id: str,
    # NEW (REVIEW #4) — privacy invariant for any internal LLM calls:
    registry: "ConversationRegistry | None" = None,
    system_settings: dict | None = None,
    user_id: str | None = None,
    user_email: str | None = None,
) -> dict:
    ...
```

CR-05 per-chunk LLM call template (mirrors harness_engine.py:543-554):
```python
from app.services.redaction.egress import egress_filter
from app.services.openrouter_service import OpenRouterService

messages = [{"role": "system", "content": chunk_prompt}]

# REVIEW #4: SEC-04 egress filter pre-call — privacy invariant
if registry is not None:
    payload = json.dumps(messages, ensure_ascii=False)
    er = egress_filter(payload, registry, None)
    if er.tripped:
        chunks_failed += 1
        logger.warning(
            "CR-05 chunk %d/%d egress-blocked harness_run=%s",
            idx, total_chunks, harness_run_id,
        )
        continue   # skip this chunk; don't fail the whole phase

# Safe to call LLM
or_svc = OpenRouterService()
raw = await or_svc.complete_with_tools(
    messages=messages,
    response_format={"type": "json_object"},
    ...
)
```
</interfaces>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Extend PROGRAMMATIC dispatcher to pass registry + system_settings to executor (REVIEW #4)</name>
  <files>backend/app/services/harness_engine.py</files>
  <read_first>
    - backend/app/services/harness_engine.py (lines 475-520 — current PROGRAMMATIC dispatcher; line 487 reads workspace_files, ~line 510 invokes phase.executor)
    - backend/app/services/harness_engine.py (lines 540-554 — LLM_SINGLE egress_filter pattern to mirror)
    - backend/app/harnesses/smoke_echo.py (lines 51-106 — existing _phase1_echo signature; check it accepts **kwargs OR explicit; if explicit, plan 22-08 must keep backward-compat)
    - .planning/phases/22-contract-review-harness-docx-deliverable/22-REVIEWS.md (review finding #4)
  </read_first>
  <behavior>
    - Test 1: PROGRAMMATIC dispatcher passes `registry`, `system_settings`, `user_id`, `user_email` as kwargs to `phase.executor(...)`.
    - Test 2: Existing executor that does NOT accept these kwargs (i.e. uses explicit kwargs only) does NOT crash — engine uses **kwargs spread but tolerates TypeError gracefully OR all existing executors are confirmed to accept **kwargs.
    - Test 3: Backward-compat: smoke_echo's _phase1_echo runs without modification (the engine introspects the signature OR all executors are updated to take `**_` for forward compat).
  </behavior>
  <action>
    In `backend/app/services/harness_engine.py`, find the PROGRAMMATIC dispatcher block (around line 487-520; specifically the `await phase.executor(inputs=...)` call site).

    **Change the executor invocation** to pass the new kwargs:
    ```python
    # REVIEW #4: extend programmatic executor contract to enable in-executor LLM calls
    # to pass through the SEC-04 egress filter. registry + system_settings flow from
    # _gatekeeper_stream_wrapper (B4 single-registry invariant) down to here.
    try:
        result = await phase.executor(
            inputs=inputs,
            token=token,
            thread_id=thread_id,
            harness_run_id=harness_run_id,
            # NEW kwargs — Phase 22 / REVIEW #4 / SEC-04 / B4 single-registry:
            registry=registry,
            system_settings=sys_settings if "sys_settings" in dir() else None,
            user_id=user_id,
            user_email=user_email,
        )
    except TypeError as exc:
        # Backward-compat fallback: pre-Phase-22 executors don't accept the new kwargs.
        # Retry with the old signature so smoke_echo and any external harness keep working.
        if "unexpected keyword argument" in str(exc):
            logger.info(
                "harness_engine: programmatic executor %s does not accept new kwargs (%s); "
                "retrying with legacy signature (no registry — egress wrap is executor's responsibility)",
                phase.name, exc,
            )
            result = await phase.executor(
                inputs=inputs,
                token=token,
                thread_id=thread_id,
                harness_run_id=harness_run_id,
            )
        else:
            raise
    ```

    Verify `registry`, `user_id`, `user_email` are already in scope at this point — they were earlier function parameters of `_dispatch_phase` (line 465 area). `sys_settings` may need to be threaded through or fetched via `get_system_settings()` if not available; check by reading the surrounding code.

    Add a comment at the top of the dispatcher block:
    ```python
    # REVIEW #4 (Phase 22): PROGRAMMATIC executors that perform internal LLM calls
    # (e.g. CR-05's per-chunk extraction) MUST receive the registry to wrap each
    # call in egress_filter(payload, registry, None). The B4 single-registry invariant
    # (chat.py:1851) flows down to here through the engine's `registry` parameter.
    ```

    Also update the `smoke_echo._phase1_echo` signature to accept `**_` for forward compat:
    Inside `backend/app/harnesses/smoke_echo.py`, change:
    ```python
    async def _phase1_echo(
        *, inputs: dict[str, str], token: str, thread_id: str, harness_run_id: str
    ) -> dict:
    ```
    to:
    ```python
    async def _phase1_echo(
        *, inputs: dict[str, str], token: str, thread_id: str, harness_run_id: str,
        **_,  # Phase 22 / REVIEW #4: forward-compat — accepts new engine kwargs (registry, system_settings, etc.) without using them.
    ) -> dict:
    ```
    This is a 1-line addition; preserves identical behavior. Note this means files_modified for plan 22-08 should include `backend/app/harnesses/smoke_echo.py` — UPDATE the frontmatter.
  </action>
  <verify>
    <automated>cd backend && source venv/bin/activate && pytest tests/services/test_harness_engine_programmatic_registry.py -v --tb=short && pytest tests/harnesses/test_smoke_echo.py -v --tb=short && python -c "from app.main import app; print('OK')"</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c "registry=registry" backend/app/services/harness_engine.py` returns `>= 1` (PROGRAMMATIC dispatcher kwarg)
    - `grep -c "REVIEW #4" backend/app/services/harness_engine.py` returns `>= 1`
    - `grep -c "\\*\\*_," backend/app/harnesses/smoke_echo.py` returns `>= 1` (forward-compat sentinel)
    - `pytest backend/tests/harnesses/test_smoke_echo.py -v` exits 0 (regression — smoke_echo still works)
    - `python -c "from app.main import app; print('OK')"` prints `OK`
  </acceptance_criteria>
  <done>Engine passes registry + system_settings to programmatic executors; smoke_echo backward-compat preserved.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: CR-05 executor with per-chunk egress_filter wrap (REVIEW #4)</name>
  <files>backend/app/harnesses/contract_review.py</files>
  <read_first>
    - backend/app/harnesses/contract_review.py (post-Plan-22-07 state — find phases[4] "extract-clauses" stub)
    - backend/app/services/harness_engine.py (post-Task-1 state — confirm dispatcher passes registry)
    - backend/app/services/harness_engine.py (lines 540-554 — egress_filter pattern to mirror)
    - backend/app/services/openrouter_service.py (top 100 lines — confirm `complete_with_tools` signature)
    - .planning/phases/22-contract-review-harness-docx-deliverable/22-REVIEWS.md (review finding #4)
  </read_first>
  <behavior>
    - Test 1: With small (~5k char) contract, returns `{"content": "<JSON markdown>", "clause_count": N, "chunk_count": 1}`.
    - Test 2: With large (~250k char) contract, chunks into >=2 with overlap.
    - Test 3: Dedupe — same clause text in chunks N and N+1 collapsed.
    - Test 4: LLM-returned categories not in CLAUSE_CATEGORIES → coerced to "Other".
    - Test 5: Empty input → error dict `{"error": "contract_text_missing", ...}`.
    - Test 6: Single chunk LLM exception caught; phase continues if other chunks succeed.
    - Test 7: ISSUE-10 — boilerplate header but different bodies (e.g. different dollar amounts) NOT deduped.
    - Test 8 (REVIEW #4 — egress wrap): when `registry` is provided AND egress_filter trips for chunk N, that chunk is skipped (counted as failed) but the phase continues. Returns `{"chunks_failed": >=1}` in the result dict. Mock `egress_filter` to return `tripped=True` on a specific chunk index.
    - Test 9 (REVIEW #4 — registry kwarg accepted): `_phase5_extract_clauses(..., registry=mock_registry)` does not raise TypeError. The signature MUST accept `registry`, `system_settings`, `user_id`, `user_email` (or `**_`).
  </behavior>
  <action>
    Edit `backend/app/harnesses/contract_review.py`:

    **A) Add Clause + ClauseExtractionResult schemas** below PlaybookContext:
    ```python
    class Clause(BaseModel):
        category: str = Field(..., description="One of CLAUSE_CATEGORIES; coerce to 'Other' if unrecognized")
        heading: str = Field(..., min_length=1, max_length=300)
        text: str = Field(..., min_length=1, max_length=10_000)
        position: int = Field(..., ge=0)


    class ClauseExtractionResult(BaseModel):
        clauses: list[Clause] = Field(default_factory=list)
        chunk_index: int = Field(..., ge=0)
        total_chunks: int = Field(..., ge=1)
    ```

    **B) Module-level constants:**
    ```python
    CR05_CHUNK_CHARS = 180_000
    CR05_CHUNK_OVERLAP_CHARS = 5_000
    CR05_DEDUPE_RATIO = 0.85
    ```

    **C) Executor with REVIEW #4 egress wrap** — signature accepts the new kwargs:
    ```python
    async def _phase5_extract_clauses(
        *,
        inputs: dict[str, str],
        token: str,
        thread_id: str,
        harness_run_id: str,
        # REVIEW #4 / SEC-04 / B4 single-registry — engine passes these via plan 22-08 Task 1:
        registry=None,
        system_settings: dict | None = None,
        user_id: str | None = None,
        user_email: str | None = None,
        **_,  # forward-compat for any future engine kwargs
    ) -> dict:
        """CR-05: read contract-text.md; LLM-extract clauses (chunked if needed); dedupe; write clauses.md + clauses.json.

        REVIEW #4 invariant: every per-chunk LLM call is wrapped by egress_filter(payload, registry, None)
        BEFORE OpenRouterService is invoked. If the registry is None (e.g. unit test or harness invoked
        outside chat router), the wrap is skipped — but in production the chat router B4 single-registry
        always provides one.
        """
        contract_text = (inputs or {}).get("contract-text.md", "")
        if not contract_text or not contract_text.strip():
            return {"error": "contract_text_missing", "code": "NO_CONTRACT",
                    "detail": "Phase 5 invoked but inputs['contract-text.md'] is empty"}

        chunks = _chunk_for_clause_extraction(contract_text)
        total_chunks = len(chunks)
        logger.info("CR-05: chunked harness_run=%s chars=%d chunks=%d",
                    harness_run_id, len(contract_text), total_chunks)

        from app.services.openrouter_service import OpenRouterService
        from app.services.redaction.egress import egress_filter
        import json as _j

        all_clauses: list[Clause] = []
        chunks_failed = 0
        chunks_egress_blocked = 0

        for idx, chunk in enumerate(chunks):
            prompt = _build_cr05_chunk_prompt(chunk_text=chunk, chunk_index=idx, total_chunks=total_chunks)
            messages = [{"role": "system", "content": prompt}]

            # REVIEW #4 / SEC-04: egress filter pre-call. Mirrors harness_engine.py:543-554.
            if registry is not None:
                payload = _j.dumps(messages, ensure_ascii=False)
                er = egress_filter(payload, registry, None)
                if er.tripped:
                    chunks_egress_blocked += 1
                    chunks_failed += 1
                    logger.warning(
                        "CR-05 chunk %d/%d egress-blocked harness_run=%s",
                        idx, total_chunks, harness_run_id,
                    )
                    continue

            try:
                or_svc = OpenRouterService()
                llm_result = await or_svc.complete_with_tools(
                    messages=messages,
                    tools=None,
                    model=None,
                    response_format={"type": "json_object"},
                )
                raw = llm_result.get("content", "")
                parsed = ClauseExtractionResult.model_validate(_j.loads(raw))
                for c in parsed.clauses:
                    if c.category not in CLAUSE_CATEGORIES:
                        c.category = "Other"
                all_clauses.extend(parsed.clauses)
            except Exception as exc:
                chunks_failed += 1
                logger.warning(
                    "CR-05 chunk %d/%d failed harness_run=%s: %s",
                    idx, total_chunks, harness_run_id, exc, exc_info=True,
                )

        if chunks_failed == total_chunks:
            return {"error": "all_chunks_failed", "code": "CR05_FAILED",
                    "detail": f"All {total_chunks} chunks failed extraction "
                              f"(egress_blocked={chunks_egress_blocked})"}

        deduped = _dedupe_clauses(all_clauses, ratio=CR05_DEDUPE_RATIO)

        body = _j.dumps([c.model_dump() for c in deduped], ensure_ascii=False, indent=2)
        markdown = (
            f"# Extracted Clauses\n\n"
            f"- **Total clauses:** {len(deduped)} (from {len(all_clauses)} pre-dedupe)\n"
            f"- **Chunks processed:** {total_chunks - chunks_failed}/{total_chunks}\n\n"
            f"```json\n{body}\n```\n"
        )

        # ISSUE-04 / ISSUE-25: also write clauses.json sibling for CR-06 LLM_BATCH_AGENTS consumption
        try:
            ws_inst = WorkspaceService(token=token)
            await ws_inst.write_text_file(
                thread_id, "clauses.json",
                _j.dumps([c.model_dump() for c in deduped], ensure_ascii=False, indent=2),
                source="harness",
            )
        except Exception as exc:
            logger.warning("CR-05 sibling clauses.json write failed: %s", exc)

        return {
            "content": markdown,
            "clause_count": len(deduped),
            "chunk_count": total_chunks,
            "chunks_failed": chunks_failed,
            "chunks_egress_blocked": chunks_egress_blocked,
        }


    def _chunk_for_clause_extraction(text: str) -> list[str]:
        if len(text) <= CR05_CHUNK_CHARS:
            return [text]
        chunks: list[str] = []
        step = CR05_CHUNK_CHARS - CR05_CHUNK_OVERLAP_CHARS
        for start in range(0, len(text), step):
            end = min(start + CR05_CHUNK_CHARS, len(text))
            chunks.append(text[start:end])
            if end == len(text):
                break
        return chunks


    def _dedupe_clauses(clauses: list["Clause"], ratio: float) -> list["Clause"]:
        from difflib import SequenceMatcher
        kept: list[Clause] = []
        for c in clauses:
            is_dup = False
            for k in kept:
                if k.category == c.category and SequenceMatcher(None, k.text, c.text).ratio() > ratio:
                    is_dup = True
                    break
            if not is_dup:
                kept.append(c)
        return kept


    def _build_cr05_chunk_prompt(*, chunk_text: str, chunk_index: int, total_chunks: int) -> str:
        return (
            "You are extracting every distinct legal clause from a contract chunk. "
            f"This is chunk {chunk_index + 1} of {total_chunks}.\n\n"
            "For each clause you find, return a JSON object with fields:\n"
            "  category: one of these strings exactly — "
            f"{', '.join(CLAUSE_CATEGORIES)}\n"
            "  heading: section heading OR the first 80-100 chars of the clause\n"
            "  text: the clause's verbatim text (do not paraphrase)\n"
            "  position: approximate character offset in the chunk (integer)\n\n"
            "Return ONLY a JSON object of shape "
            "{\"clauses\": [...], \"chunk_index\": <int>, \"total_chunks\": <int>}.\n"
            f"Use chunk_index={chunk_index}, total_chunks={total_chunks}.\n"
            "Use 'Other' for clauses that don't fit any of the listed categories.\n\n"
            f"--- CONTRACT CHUNK ---\n{chunk_text}\n--- END CHUNK ---\n"
        )
    ```

    **D) Wire executor on phases[4]** — set `executor=_phase5_extract_clauses` (replace stub).

    **E) ISSUE-25 sibling write is now in the executor body (above), not patched in plan 22-09.** Remove the duplicate-write instruction from plan 22-09 (Task 1 step E) — it's redundant.
  </action>
  <verify>
    <automated>cd backend && source venv/bin/activate && pytest tests/harnesses/test_contract_review_cr05.py -v --tb=short && python -c "from app.harnesses.contract_review import _phase5_extract_clauses, _chunk_for_clause_extraction, _dedupe_clauses; print('OK')"</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c "_phase5_extract_clauses" backend/app/harnesses/contract_review.py` returns `>= 2`
    - `grep -c "egress_filter" backend/app/harnesses/contract_review.py` returns `>= 1` (REVIEW #4 wrap)
    - `grep -c "REVIEW #4" backend/app/harnesses/contract_review.py` returns `>= 1`
    - `grep -c "chunks_egress_blocked" backend/app/harnesses/contract_review.py` returns `>= 2` (counter + return field)
    - `python -c "from app.harnesses.contract_review import CONTRACT_REVIEW; assert CONTRACT_REVIEW.phases[4].executor.__name__ == '_phase5_extract_clauses'; print('OK')"` prints `OK`
    - `python -c "from app.main import app; print('OK')"` prints `OK`
  </acceptance_criteria>
  <done>CR-05 executor wired with egress_filter wrap on every per-chunk LLM call (REVIEW #4 closed); chunking + dedupe + sibling write in place.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: Test that engine passes registry to programmatic executors (REVIEW #4 contract)</name>
  <files>backend/tests/services/test_harness_engine_programmatic_registry.py</files>
  <read_first>
    - backend/app/services/harness_engine.py (post-Task-1)
    - backend/tests/services/test_harness_engine_post_execute.py (analog from plan 22-03)
  </read_first>
  <behavior>
    - Test 1 (REVIEW #4): when engine runs a PROGRAMMATIC phase with a sentinel executor, the executor receives `registry`, `system_settings`, `user_id`, `user_email` kwargs.
    - Test 2 (backward-compat): legacy executor that does NOT accept new kwargs is still invoked successfully (engine catches TypeError and retries with legacy signature).
  </behavior>
  <action>
    Create `backend/tests/services/test_harness_engine_programmatic_registry.py` with 2 tests.

    Concrete test 1:
    ```python
    @pytest.mark.asyncio
    async def test_engine_passes_registry_to_programmatic_executor(monkeypatch):
        """REVIEW #4: privacy invariant — engine MUST pass registry to programmatic
        executors so they can wrap any internal LLM call in egress_filter."""
        captured_kwargs: dict = {}

        async def sentinel_executor(**kwargs):
            captured_kwargs.update(kwargs)
            return {"content": "ok"}

        # Build minimal harness with one PROGRAMMATIC phase using sentinel_executor
        # ... harness setup ...

        mock_registry = MagicMock()
        mock_settings = {"redaction_enabled": True}

        events = [ev async for ev in run_harness_engine(
            harness_run_id="r", registry=mock_registry, ...
        )]

        assert "registry" in captured_kwargs, "REVIEW #4: registry kwarg missing from executor call"
        assert captured_kwargs["registry"] is mock_registry, "must be the same instance"
        assert "user_id" in captured_kwargs
        assert "user_email" in captured_kwargs
    ```
  </action>
  <verify>
    <automated>cd backend && source venv/bin/activate && pytest tests/services/test_harness_engine_programmatic_registry.py -v --tb=short</automated>
  </verify>
  <acceptance_criteria>
    - `pytest backend/tests/services/test_harness_engine_programmatic_registry.py -v` exits 0 with 2 tests
    - `grep -c "REVIEW #4" backend/tests/services/test_harness_engine_programmatic_registry.py` returns `>= 1`
  </acceptance_criteria>
  <done>2 tests pass — registry plumbing verified.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 4: CR-05 unit tests (incl. egress wrap test)</name>
  <files>backend/tests/harnesses/test_contract_review_cr05.py</files>
  <read_first>
    - backend/app/harnesses/contract_review.py (post-Task-2 state)
  </read_first>
  <behavior>
    See behaviors 1-9 in Task 2.
  </behavior>
  <action>
    Create `backend/tests/harnesses/test_contract_review_cr05.py` with 9 tests.

    Concrete test 8 (REVIEW #4 egress wrap):
    ```python
    @pytest.mark.asyncio
    async def test_egress_filter_skips_chunk_when_tripped():
        """REVIEW #4: when registry is provided AND egress_filter trips for a chunk,
        that chunk is counted as failed (egress-blocked) but the phase continues."""
        from app.harnesses.contract_review import _phase5_extract_clauses

        big_text = "x" * 250_000  # forces 2+ chunks
        # Mock egress_filter to trip on chunk index 0 only
        call_count = {"n": 0}
        def fake_egress_filter(payload, registry, _):
            call_count["n"] += 1
            er = MagicMock()
            er.tripped = call_count["n"] == 1  # trip first call
            return er

        mock_registry = MagicMock()
        with patch("app.harnesses.contract_review.egress_filter", side_effect=fake_egress_filter):
            with patch("app.harnesses.contract_review.OpenRouterService") as svc_cls:
                svc_inst = svc_cls.return_value
                svc_inst.complete_with_tools = AsyncMock(return_value={"content": json.dumps({
                    "clauses": [{"category": "Liability", "heading": "h", "text": "t", "position": 0}],
                    "chunk_index": 1, "total_chunks": 2,
                })})
                result = await _phase5_extract_clauses(
                    inputs={"contract-text.md": big_text},
                    token="t", thread_id="thr", harness_run_id="r",
                    registry=mock_registry, system_settings={}, user_id="u", user_email="e@x",
                )

        assert result.get("chunks_egress_blocked") == 1
        assert result.get("chunks_failed") >= 1
        # Phase did not bail entirely — got at least 1 clause from the second chunk
        assert "content" in result
    ```

    Concrete test 9 (REVIEW #4 signature):
    ```python
    @pytest.mark.asyncio
    async def test_executor_accepts_review_4_kwargs():
        """REVIEW #4: executor signature MUST accept registry, system_settings, user_id, user_email."""
        from app.harnesses.contract_review import _phase5_extract_clauses
        # Calling with the new kwargs must not raise TypeError
        result = await _phase5_extract_clauses(
            inputs={"contract-text.md": ""},
            token="t", thread_id="thr", harness_run_id="r",
            registry=None, system_settings=None, user_id=None, user_email=None,
        )
        # Empty contract → error path is fine, signature is what we test here
        assert result.get("error") == "contract_text_missing"
    ```
  </action>
  <verify>
    <automated>cd backend && source venv/bin/activate && pytest tests/harnesses/test_contract_review_cr05.py -v --tb=short</automated>
  </verify>
  <acceptance_criteria>
    - `pytest backend/tests/harnesses/test_contract_review_cr05.py -v` exits 0 with 9 tests passing
    - `grep -c "egress" backend/tests/harnesses/test_contract_review_cr05.py` returns `>= 2`
    - `grep -c "REVIEW #4" backend/tests/harnesses/test_contract_review_cr05.py` returns `>= 1`
  </acceptance_criteria>
  <done>9 tests pass; REVIEW #4 privacy invariant test in place.</done>
</task>

</tasks>

<truths>
- ROADMAP CR-05 spec — JSON array, 13 categories, chunked with overlap and dedupe-merge.
- D-22-15 style fallback — error dict, never raise.
- REVIEW #4 closed: programmatic executor contract extended; CR-05's per-chunk LLM call wrapped in egress_filter.
- B4 single-registry (SEC-04): registry instance flows from chat.py top-level wrap → run_harness_engine → PROGRAMMATIC dispatcher → CR-05 executor.
- The 13 CLAUSE_CATEGORIES shared between CR-04, CR-05, CR-06/07 — defined once at module level in plan 22-07.
- ISSUE-25 sibling clauses.json write moved INTO this plan's executor (was patched in plan 22-09 previously). Plan 22-09's old "patch CR-05 to also write clauses.json" instruction is now redundant — Plan 22-09 should be updated to drop that instruction.
- smoke_echo._phase1_echo updated with `**_` forward-compat in this plan.
</truths>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| contract-text.md (PII) → CR-05 LLM call payload | Real PII; egress_filter wrap MUST run before OpenRouterService — REVIEW #4 enforced |
| LLM JSON output → Pydantic validation | Untrusted JSON; ClauseExtractionResult validates structure |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-22-08-01 | Information Disclosure | Contract PII bypassing egress filter | mitigate | REVIEW #4 fix: every per-chunk call wrapped by `egress_filter(payload, registry, None)`; tripped chunks counted + skipped |
| T-22-08-02 | Tampering | LLM returns malicious JSON to crash json.loads | mitigate | try/except + Pydantic validate; whole-phase fallback if all chunks fail |
| T-22-08-03 | DoS | Pathological 1GB contract input | mitigate | UPL-02 25 MB upload cap; CR05_CHUNK_CHARS=180k bounds per-LLM-call cost |
| T-22-08-04 | Information Disclosure | Engine fails to pass registry → CR-05 falls back to no-wrap mode | mitigate | Test 9 (REVIEW #4 contract test) catches engine kwarg drift; production chat router B4 single-registry always provides registry |
</threat_model>

<verification>
1. `pytest backend/tests/harnesses/test_contract_review_cr05.py -v` exits 0
2. `pytest backend/tests/services/test_harness_engine_programmatic_registry.py -v` exits 0
3. `pytest backend/tests/harnesses/test_smoke_echo.py -v` exits 0 (regression — backward compat)
4. `python -c "from app.main import app; print('OK')"` prints `OK`
</verification>

<success_criteria>
- CR-05 chunks contracts >180k chars with 5k overlap
- Per-chunk LLM extraction returns Pydantic-validated clauses
- Dedupe collapses near-duplicates
- Categories restricted to the 13-element set
- Failure modes return error dicts, never raise
- **REVIEW #4 invariant: every per-chunk LLM payload passes through egress_filter before reaching the cloud LLM**
- Engine passes registry to programmatic executors (verified by separate contract test)
- smoke_echo backward compat preserved
</success_criteria>

<output>
After completion, create `.planning/phases/22-contract-review-harness-docx-deliverable/22-08-SUMMARY.md`.
</output>
