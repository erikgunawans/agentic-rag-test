---
phase: 22-contract-review-harness-docx-deliverable
plan: 08
type: execute
wave: 4
depends_on: ["22-06", "22-07"]
files_modified:
  - backend/app/harnesses/contract_review.py
  - backend/tests/harnesses/test_contract_review_cr05.py
autonomous: true
requirements: [CR-05]
must_haves:
  truths:
    - "CR-05 (extract-clauses) is a programmatic phase that internally calls an LLM per chunk to extract clauses"
    - "Output is a JSON array of clauses with fields {category, heading, text, position} — categories restricted to the 13 from CR-04"
    - "Contracts >50k tokens chunk with overlap and dedupe-merge across chunks"
    - "Empty contract or extraction failure returns error dict, not exception (D-22-15-style fallback)"
    - "ISSUE-10 dedupe ratio rationale: 0.85 SequenceMatcher threshold balances false-positives (different clauses sharing boilerplate header — keep) vs false-negatives (true duplicates with minor whitespace drift — drop). Two clauses sharing identical boilerplate but differing in dollar amounts/dates are kept — covered by Test 7."
    - "Internal LLM calls go through OpenRouterService → existing egress filter wrap (SEC-04)"
  artifacts:
    - path: "backend/app/harnesses/contract_review.py"
      provides: "_phase5_extract_clauses executor + Clause + ClauseExtractionResult schemas"
      contains: "_phase5_extract_clauses"
    - path: "backend/tests/harnesses/test_contract_review_cr05.py"
      provides: "Tests for chunking, dedupe, category restriction, empty-contract fallback"
  key_links:
    - from: "_phase5_extract_clauses"
      to: "OpenRouterService.complete (per chunk LLM call)"
      via: "structured json_object response_format"
      pattern: "json_object\\|json_schema"
    - from: "_phase5_extract_clauses output"
      to: "clauses.md"
      via: "JSON array serialized as markdown code block"
      pattern: "clauses\\.md"
---

<objective>
Replace the CR-05 (extract-clauses) stub in `contract_review.py`. Build a programmatic phase that reads `contract-text.md`, chunks if needed (~50k tokens), runs an LLM per chunk to extract every distinct clause across the 13 categories, then dedupes and merges across chunks.

Per ROADMAP success criterion 3: "writes `clauses.md` (JSON array, 13 categories: ..., contracts >50 k tokens chunk with overlap and dedupe-merge)."

Purpose: CR-06 (risk analysis) reads this clauses array and fan-outs sub-agents one per clause. CR-07 (redlines) processes a subset.
Output: Programmatic phase populated, schema, chunking logic, tests.
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
@backend/app/harnesses/contract_review.py
</context>

<interfaces>
<!-- ISSUE-03 PIN: harness_engine.py PROGRAMMATIC dispatcher (line 487) calls -->
<!--   inputs = await _read_workspace_files(thread_id, phase.workspace_inputs, token) -->
<!-- which loads each file's content into inputs[file_path] = content_string. -->
<!-- The executor receives inputs dict with file CONTENTS pre-loaded — NOT paths. -->
<!-- Pattern (harness_engine.py:1115-1135): -->
<!--   async def _read_workspace_files(thread_id, paths, token) -> dict[str, str]: -->
<!--     for path in paths: read_result = await ws.read_file(thread_id, path) -->
<!--     result[path] = read_result.get("content", "") -->
<!-- So `inputs["contract-text.md"]` IS the file's text content. -->

<!-- CR-05 internal LLM call signature — must use the existing OpenRouterService -->
<!-- Mirrors how harness_engine.py:543-595 does LLM_SINGLE structured output -->

```python
class Clause(BaseModel):
    category: str = Field(..., description="One of the 13 CLAUSE_CATEGORIES")
    heading: str = Field(..., min_length=1, max_length=300, description="Section heading or first ~100 chars")
    text: str = Field(..., min_length=1, max_length=10_000, description="Verbatim clause text")
    position: int = Field(..., ge=0, description="Approximate character offset in source contract")


class ClauseExtractionResult(BaseModel):
    clauses: list[Clause] = Field(..., description="All clauses found in this chunk")
    chunk_index: int = Field(..., ge=0)
    total_chunks: int = Field(..., ge=1)
```
</interfaces>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Populate CR-05 executor + Clause schema + chunking + dedupe</name>
  <files>backend/app/harnesses/contract_review.py</files>
  <read_first>
    - backend/app/harnesses/contract_review.py (post-Plan-22-07 state — find phases[4] "extract-clauses" stub)
    - backend/app/services/harness_engine.py (lines 540-600 — LLM_SINGLE OpenRouter call pattern; reuse the same Settings + json_object approach)
    - backend/app/services/openrouter_service.py (top 100 lines — confirm `complete` or `complete_with_tools` signature)
    - .planning/phases/22-contract-review-harness-docx-deliverable/22-PATTERNS.md (lines 86-87 — programmatic phase invariant: must return dict with `content` field)
  </read_first>
  <behavior>
    - Test 1: With a small (~5k char) contract-text.md, executor returns `{"content": "<JSON markdown>", "clause_count": N, "chunk_count": 1}` with N>=1.
    - Test 2: With a large (~250k char ~ 60k+ tokens) contract-text.md, executor chunks into >=2 chunks (chunk_count >= 2) with overlap.
    - Test 3: Dedupe — same clause text returned by chunks N and N+1 appears ONLY ONCE in the output (similar enough by SequenceMatcher ratio > 0.85).
    - Test 4: Categories restricted — any LLM-returned category not in CLAUSE_CATEGORIES is coerced to "Other".
    - Test 5: Empty input — contract-text.md missing → error dict `{"error": "contract_text_missing", ...}`.
    - Test 6: LLM exception per chunk caught and logged; returns error dict only if ALL chunks fail (single chunk failure with others succeeding still returns content).
    - Test 7 (ISSUE-10): two clauses share a boilerplate header ("Each party agrees that..." 200 chars) but differ in dollar amounts (one $100k, one $5M); assert dedupe KEEPS BOTH (similar boilerplate alone is < 0.85 ratio when the body diverges meaningfully).
  </behavior>
  <action>
    Edit `backend/app/harnesses/contract_review.py`:

    **A) Add Clause + ClauseExtractionResult schemas** below PlaybookContext:
    ```python
    # ---------------------------------------------------------------------------
    # CR-05 — Clause Extraction schemas
    # ---------------------------------------------------------------------------

    class Clause(BaseModel):
        category: str = Field(..., description="One of CLAUSE_CATEGORIES; coerce to 'Other' if unrecognized")
        heading: str = Field(..., min_length=1, max_length=300)
        text: str = Field(..., min_length=1, max_length=10_000)
        position: int = Field(..., ge=0, description="approx character offset in source")


    class ClauseExtractionResult(BaseModel):
        clauses: list[Clause] = Field(default_factory=list)
        chunk_index: int = Field(..., ge=0)
        total_chunks: int = Field(..., ge=1)
    ```

    **B) Add module-level constants** for chunking:
    ```python
    # CR-05 chunking parameters. ~50k tokens ~= 200k chars (rough 4 char/token);
    # we chunk at 180k chars with 5k char overlap to give the LLM headroom for
    # output JSON without crossing model context windows.
    CR05_CHUNK_CHARS = 180_000
    CR05_CHUNK_OVERLAP_CHARS = 5_000
    CR05_DEDUPE_RATIO = 0.85   # SequenceMatcher threshold for cross-chunk dedupe
    ```

    **C) Add the executor function** above the `CONTRACT_REVIEW =` definition:
    ```python
    async def _phase5_extract_clauses(
        *, inputs: dict[str, str], token: str, thread_id: str, harness_run_id: str
    ) -> dict:
        """CR-05: read contract-text.md; LLM-extract clauses (chunked if needed); dedupe; write clauses.md."""
        contract_text = (inputs or {}).get("contract-text.md", "")
        if not contract_text or not contract_text.strip():
            return {"error": "contract_text_missing", "code": "NO_CONTRACT",
                    "detail": "Phase 5 invoked but inputs['contract-text.md'] is empty"}

        # Chunk
        chunks = _chunk_for_clause_extraction(contract_text)
        total_chunks = len(chunks)
        logger.info("CR-05: chunked harness_run=%s chars=%d chunks=%d",
                    harness_run_id, len(contract_text), total_chunks)

        # Per-chunk LLM extraction
        from app.services.openrouter_service import OpenRouterService
        from app.config import get_settings as _gs
        settings = _gs()

        all_clauses: list[Clause] = []
        chunks_failed = 0
        for idx, chunk in enumerate(chunks):
            prompt = _build_cr05_chunk_prompt(chunk_text=chunk, chunk_index=idx, total_chunks=total_chunks)
            try:
                svc = OpenRouterService(settings=settings)
                raw = await svc.complete(
                    messages=[{"role": "system", "content": prompt}],
                    response_format={"type": "json_object"},
                    timeout=120,
                )
                import json as _j
                parsed = ClauseExtractionResult.model_validate(_j.loads(raw))
                # Coerce categories
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
                continue

        if chunks_failed == total_chunks:
            return {"error": "all_chunks_failed", "code": "CR05_FAILED",
                    "detail": f"All {total_chunks} chunks failed extraction"}

        deduped = _dedupe_clauses(all_clauses, ratio=CR05_DEDUPE_RATIO)

        import json as _j
        body = _j.dumps([c.model_dump() for c in deduped], ensure_ascii=False, indent=2)
        markdown = (
            f"# Extracted Clauses\n\n"
            f"- **Total clauses:** {len(deduped)} (from {len(all_clauses)} pre-dedupe)\n"
            f"- **Chunks processed:** {total_chunks - chunks_failed}/{total_chunks}\n\n"
            f"```json\n{body}\n```\n"
        )
        return {
            "content": markdown,
            "clause_count": len(deduped),
            "chunk_count": total_chunks,
            "chunks_failed": chunks_failed,
        }


    def _chunk_for_clause_extraction(text: str) -> list[str]:
        """Split text into overlapping chunks of CR05_CHUNK_CHARS. Returns >=1 chunk."""
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
        """Drop near-duplicate clauses (SequenceMatcher ratio > threshold)."""
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
            "Use 'Other' for clauses that don't fit any of the listed categories.\n"
            "Do NOT skip clauses: every distinct provision should appear once.\n\n"
            f"--- CONTRACT CHUNK ---\n{chunk_text}\n--- END CHUNK ---\n"
        )
    ```

    **D) Replace `phases[4]` (extract-clauses) `executor`** field — change `executor=_phase_stub_not_implemented` to `executor=_phase5_extract_clauses`. Keep all other fields (workspace_inputs=["contract-text.md"], workspace_output="clauses.md", timeout_seconds=600).

    **E) Verify OpenRouterService API** — if it doesn't expose `complete(messages=, response_format=)` use whatever method does (e.g., `chat_completion` or `complete_with_tools`). Grep `backend/app/services/openrouter_service.py` first; the engine's LLM_SINGLE dispatcher already uses this — copy that exact call shape.

    Add an inline comment above `_phase5_extract_clauses`: `# CR-05 (D-22 — programmatic with internal LLM per chunk + dedupe-merge across chunks).`
  </action>
  <verify>
    <automated>cd backend && source venv/bin/activate && pytest tests/harnesses/test_contract_review_cr05.py -v --tb=short && python -c "from app.harnesses.contract_review import _phase5_extract_clauses, _chunk_for_clause_extraction, _dedupe_clauses; print('OK')"</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c "_phase5_extract_clauses" backend/app/harnesses/contract_review.py` returns `>= 2` (def + reference in PhaseDefinition.executor)
    - `grep -c "CR05_CHUNK_CHARS" backend/app/harnesses/contract_review.py` returns `>= 2`
    - `grep -c "_dedupe_clauses" backend/app/harnesses/contract_review.py` returns `>= 2`
    - `python -c "from app.harnesses.contract_review import CONTRACT_REVIEW; assert CONTRACT_REVIEW.phases[4].executor.__name__ == '_phase5_extract_clauses'; print('OK')"` prints `OK`
    - `python -c "from app.harnesses.contract_review import _chunk_for_clause_extraction; chunks = _chunk_for_clause_extraction('a' * 250000); print(len(chunks))"` prints `>= 2`
    - `python -c "from app.main import app; print('OK')"` prints `OK`
    - ISSUE-03 acceptance: `grep -c "_read_workspace_files" backend/app/services/harness_engine.py` returns `>= 2` (declaration + PROGRAMMATIC call site at line 487 confirm pre-load contract)
  </acceptance_criteria>
  <done>CR-05 executor wired, chunking + dedupe helpers implemented, schema added, error fallback in place.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Add CR-05 tests</name>
  <files>backend/tests/harnesses/test_contract_review_cr05.py</files>
  <read_first>
    - backend/app/harnesses/contract_review.py (post-Task-1 state)
    - backend/tests/harnesses/test_contract_review_skeleton.py (analog test patterns)
  </read_first>
  <behavior>
    See behaviors 1-6 in Task 1.
  </behavior>
  <action>
    Create `backend/tests/harnesses/test_contract_review_cr05.py` with the 6 tests. Mock `OpenRouterService.complete` (or whatever method the executor calls) to return canned JSON responses.

    Concrete test 3 (dedupe across chunks):
    ```python
    @pytest.mark.asyncio
    async def test_dedupe_drops_overlap_between_chunks():
        from app.harnesses.contract_review import _phase5_extract_clauses, ClauseExtractionResult, Clause
        # Force >=2 chunks by stubbing _chunk_for_clause_extraction (or use 250k char input)
        big_text = "Liability clause: party shall indemnify against losses. " * 5000
        # Build duplicated LLM responses across chunks: same clause appears in chunks 0 and 1
        dup_clause = {"category": "Liability", "heading": "Liability clause", "text": "party shall indemnify against losses.", "position": 0}
        canned_chunks = [
            ClauseExtractionResult(clauses=[Clause(**dup_clause)], chunk_index=0, total_chunks=2).model_dump_json(),
            ClauseExtractionResult(clauses=[Clause(**dup_clause)], chunk_index=1, total_chunks=2).model_dump_json(),
        ]
        with patch("app.harnesses.contract_review.OpenRouterService") as svc_cls:
            svc_inst = svc_cls.return_value
            svc_inst.complete = AsyncMock(side_effect=canned_chunks)
            result = await _phase5_extract_clauses(
                inputs={"contract-text.md": big_text},
                token="t", thread_id="thr", harness_run_id="run",
            )
        assert "content" in result
        assert result["clause_count"] == 1   # dedupe collapsed identical clauses
    ```

    Concrete test 5 (empty contract):
    ```python
    @pytest.mark.asyncio
    async def test_empty_contract_returns_error_dict():
        from app.harnesses.contract_review import _phase5_extract_clauses
        result = await _phase5_extract_clauses(
            inputs={"contract-text.md": ""},
            token="t", thread_id="thr", harness_run_id="run",
        )
        assert result.get("error") == "contract_text_missing"
        assert result.get("code") == "NO_CONTRACT"
    ```
  </action>
  <verify>
    <automated>cd backend && source venv/bin/activate && pytest tests/harnesses/test_contract_review_cr05.py -v --tb=short</automated>
  </verify>
  <acceptance_criteria>
    - `pytest backend/tests/harnesses/test_contract_review_cr05.py -v` exits 0 with 7 tests passing
    - `grep -c "clause_count" backend/tests/harnesses/test_contract_review_cr05.py` returns `>= 2`
    - `grep -c "_dedupe\|dedupe" backend/tests/harnesses/test_contract_review_cr05.py` returns `>= 1`
  </acceptance_criteria>
  <done>7 tests pass; CR-05 chunking + dedupe + fallback contract + ISSUE-10 boilerplate-but-different test locked in.</done>
</task>

</tasks>

<truths>
- ROADMAP CR-05 spec (success criterion 3) — JSON array, 13 categories, chunked with overlap and dedupe-merge.
- D-22-15 style fallback — error dict, never raise (consistency with smoke_echo + plan 22-03 contract).
- Internal LLM calls go through OpenRouterService → existing egress filter wrap (SEC-04 — already covered by harness_engine's wrap pattern, but CR-05 is programmatic so we instantiate OpenRouterService directly with same settings).
- The 13 CLAUSE_CATEGORIES are shared between CR-04 (plan 22-07), CR-05 (this plan), and CR-06/07 (plan 22-09) — defined once at module level in plan 22-07.
- LLM_SINGLE dispatcher is NOT used here (CR-05 is PROGRAMMATIC) — but the per-chunk LLM call mirrors the same `response_format=json_object` + Pydantic validate pattern.
</truths>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| contract-text.md (PII) → CR-05 LLM call payload | Real PII reaches cloud LLM via this path |
| LLM JSON output → Pydantic validation | Untrusted JSON; ClauseExtractionResult validates structure but not content |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-22-08-01 | Information Disclosure | Contract PII in LLM payload | mitigate | Same egress filter wrap as harness_engine.py:543-554 — instantiate OpenRouterService and route through same code path; B4 single-registry honored at the chat.py top-level wrap |
| T-22-08-02 | Tampering | LLM returns malicious JSON to crash json.loads | mitigate | try/except around json.loads + Pydantic validate; chunks_failed counter; whole-phase fallback if all chunks fail |
| T-22-08-03 | DoS | Pathological 1GB contract input | mitigate | UPL-02 25 MB upload cap upstream; CR05_CHUNK_CHARS=180k bounds per-LLM-call cost |
</threat_model>

<verification>
1. `pytest backend/tests/harnesses/test_contract_review_cr05.py -v` exits 0
2. `pytest backend/tests/harnesses/test_contract_review_skeleton.py -v` exits 0 (regression)
3. `python -c "from app.main import app; print('OK')"` prints `OK`
4. `python -c "from app.harnesses.contract_review import _chunk_for_clause_extraction; chunks = _chunk_for_clause_extraction('a' * 250000); assert len(chunks) >= 2 and len(chunks[0]) == 180000; print('OK')"` prints `OK`
</verification>

<success_criteria>
- CR-05 chunks contracts >180k chars with 5k overlap
- Per-chunk LLM extraction returns Pydantic-validated clauses
- Dedupe collapses near-duplicates (ratio > 0.85)
- Categories restricted to the 13-element set (others coerced to "Other")
- Failure modes return error dicts, never raise
</success_criteria>

<output>
After completion, create `.planning/phases/22-contract-review-harness-docx-deliverable/22-08-SUMMARY.md`.
</output>
