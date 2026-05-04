---
phase: 22-contract-review-harness-docx-deliverable
plan: 06
type: execute
wave: 2
depends_on: ["22-01", "22-03"]
files_modified:
  - backend/app/config.py
  - backend/app/services/workspace_service.py
  - backend/app/harnesses/contract_review.py
  - backend/tests/services/test_workspace_read_binary.py
  - backend/tests/harnesses/test_contract_review_skeleton.py
autonomous: true
requirements: [CR-01, CR-02]
must_haves:
  truths:
    - "contract_review.py module exists, registers CONTRACT_REVIEW behind contract_review_enabled flag"
    - "9-phase HarnessDefinition skeleton in place: 8 user-visible CR-XX phases (CR-01..08) + 1 PROGRAMMATIC `filter-redline-candidates` phase inserted between CR-06 and CR-07 per ISSUE-06 (cost optimization, not a user-visible REQ). CR-03..08 + filter are stubs in this plan; populated in plans 22-07..22-10"
    - "CR-01 Document Intake (programmatic) extracts text from uploaded DOCX/PDF via python-docx + PyPDF2 and writes contract-text.md"
    - "CR-02 Contract Classification (llm_single) returns ContractClassification Pydantic model with parties >=2, contract_type non-empty, governing_law, jurisdiction; writes classification.md"
    - "Off-mode (contract_review_enabled=False) does NOT register the harness — gatekeeper system never sees Contract Review"
    - "harness_enabled=True + contract_review_enabled=True is the only path that registers"
    - "ISSUE-09: When contract_review_enabled=True but tool_registry_enabled=False, registration fails fast with a logged error (search_documents_by_doc_ids would not be available — runtime guard)"
    - "ISSUE-14 deploy-order: contract_review_enabled MUST remain False until plans 22-06..22-10 all land in production (CR-03..08 stubs would crash if reached)"
    - "ISSUE-02: WorkspaceService gains read_binary_file(thread_id, file_path) -> bytes (returns content_bytes via signed-URL GET; raises on failure). CR-01 uses it instead of inlining storage logic"
  artifacts:
    - path: "backend/app/config.py"
      provides: "contract_review_enabled flag (default False, dark-launch)"
      contains: "contract_review_enabled"
    - path: "backend/app/harnesses/contract_review.py"
      provides: "CONTRACT_REVIEW HarnessDefinition + CR-01 executor + CR-02 schema/phase + stub phases for CR-03..08 + filter-redline-candidates stub"
      contains: "CONTRACT_REVIEW"
    - path: "backend/tests/harnesses/test_contract_review_skeleton.py"
      provides: "Tests for flag gating, 9-phase shape, CR-01 extraction, CR-02 schema validation"
  key_links:
    - from: "harnesses/__init__.py auto-import"
      to: "contract_review.py registration"
      via: "register(CONTRACT_REVIEW) inside `if get_settings().harness_enabled and get_settings().contract_review_enabled:` guard"
      pattern: "register\\(CONTRACT_REVIEW\\)"
    - from: "_phase1_intake (CR-01 executor)"
      to: "contract-text.md"
      via: "ws.write_text_file or returned content via engine"
      pattern: "contract-text\\.md"
---

<objective>
Create the Contract Review harness module skeleton: feature flag, HarnessDefinition with 8 user-visible phases (CR-01..08) plus a programmatic filter step between CR-06 and CR-07 = 9 phases total, CR-01 (Document Intake — programmatic text extraction), CR-02 (Contract Classification — llm_single with Pydantic schema). Phases CR-03..08 + the filter step are placeholders that the engine never reaches in this plan (engine halts gracefully if a phase has empty system_prompt_template + None executor, OR we register the full skeleton with stub bodies).

The 9-phase HarnessDefinition (8 user-visible CR-XX phases + 1 programmatic filter) is registered in this plan with stub bodies for CR-03..08 + the filter step — subsequent plans (22-07..22-10) replace stubs in-place. This avoids re-registering the harness mid-phase.

Note on phase semantics: the 9th phase (`filter-redline-candidates`) is an internal cost-optimization PROGRAMMATIC step, not a user-visible REQ. CR-01..08 still map 1:1 to the 8 named user phases.

Purpose: Stand up the harness scaffold so plan 22-04's gatekeeper can target it, plan 22-05's eval can reference its display_name, and the smoke run on a synthetic DOCX completes through CR-02.
Output: New module + flag + tests. Stub phases CR-03..08 + filter step fail closed with a clear "not yet implemented" error if reached, so partial-completion is detectable.
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
@backend/app/harnesses/smoke_echo.py
@backend/app/harnesses/types.py
</context>

<interfaces>
<!-- HarnessDefinition + PhaseDefinition shapes (from types.py) — see plan 22-03 interfaces -->

CR-01 programmatic executor signature (mirrors smoke_echo.py:51-66):
```python
async def _phase1_intake(
    *, inputs: dict[str, str], token: str, thread_id: str, harness_run_id: str
) -> dict:
    # Returns:
    #   {"content": "<extracted markdown>", "page_count": N, "char_count": M, "source_file": "<filename>"}
    # OR
    #   {"error": "...", "code": "...", "detail": "<=500 chars"}
```

CR-02 Pydantic schema:
```python
class ContractClassification(BaseModel):
    contract_type: str = Field(..., min_length=1, max_length=200, description="MSA / NDA / SaaS / Employment / Distribution / etc")
    parties: list[str] = Field(..., min_length=2, max_length=20, description="Named entities, e.g. ['Acme Corp', 'Beta Inc']")
    effective_date: str | None = Field(None, description="ISO 8601 if present, else null")
    expiration_date: str | None = Field(None, description="ISO 8601 if present, else null")
    governing_law: str = Field(..., min_length=1, description="Jurisdiction name, e.g. 'Republic of Indonesia', 'New York State'")
    jurisdiction: str = Field(..., min_length=1, description="Forum / venue clause")
    summary: str = Field(..., min_length=20, max_length=1000, description="1-2 sentence description of the contract")
```
</interfaces>

<tasks>

<task type="auto" tdd="true">
  <name>Task 0: Add WorkspaceService.read_binary_file (ISSUE-02 contract pin)</name>
  <files>backend/app/services/workspace_service.py, backend/tests/services/test_workspace_read_binary.py</files>
  <read_first>
    - backend/app/services/workspace_service.py (lines 268-326 — read_file already returns signed_url for binary files; lines 511-572 — write_binary_file analog)
  </read_first>
  <behavior>
    - Test 1: read_binary_file with a valid binary row returns bytes equal to the originally-written content (round-trip via write_binary_file).
    - Test 2: read_binary_file on a missing path returns a structured error dict {"error": "file_not_found", "file_path": ...} — does NOT raise.
    - Test 3: read_binary_file on a TEXT row (no storage_path) returns {"error": "not_a_binary_file", "file_path": ...}.
    - Test 4: read_binary_file rejects invalid paths via validate_workspace_path (raises WorkspaceValidationError → returns dict).
  </behavior>
  <action>
    Add a new public async method to `WorkspaceService` in `backend/app/services/workspace_service.py`, placed AFTER `read_file` (line ~325) and BEFORE `append_line` (line ~328):

    ```python
    async def read_binary_file(self, thread_id: str, file_path: str) -> bytes | dict:
        """Phase 22 / ISSUE-02 — fetch the underlying bytes of a binary workspace file.

        Returns:
            bytes  — file content downloaded from Storage via signed URL
            dict   — structured error: {"error": code, "file_path": ..., "detail": ...}
        """
        # Reuse read_file path validation + DB lookup
        meta = await self.read_file(thread_id, file_path)
        if isinstance(meta, dict) and "error" in meta:
            return meta
        if not meta.get("is_binary"):
            return {"error": "not_a_binary_file", "file_path": file_path,
                    "detail": "read_binary_file called on a text row (no storage_path)"}
        signed_url = meta.get("signed_url") or ""
        if not signed_url:
            return {"error": "no_signed_url", "file_path": file_path}
        try:
            import httpx
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(signed_url)
                resp.raise_for_status()
                return resp.content
        except Exception as exc:
            return {"error": "storage_fetch_failed", "file_path": file_path, "detail": str(exc)[:500]}
    ```

    Create `backend/tests/services/test_workspace_read_binary.py` with the 4 tests in the behavior block. Use `httpx_mock` or patch `httpx.AsyncClient` directly. Mock `WorkspaceService.read_file` to return the meta dicts that drive each branch.
  </action>
  <verify>
    <automated>cd backend && source venv/bin/activate && pytest tests/services/test_workspace_read_binary.py -v --tb=short</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c "async def read_binary_file" backend/app/services/workspace_service.py` returns `1`
    - `pytest backend/tests/services/test_workspace_read_binary.py -v` exits 0 with 4 tests passing
    - `python -c "from app.services.workspace_service import WorkspaceService; assert hasattr(WorkspaceService, 'read_binary_file'); print('OK')"` prints `OK`
  </acceptance_criteria>
  <done>read_binary_file added to WorkspaceService; CR-01 in Task 2 below uses it directly with no conditional fallback.</done>
</task>

<task type="auto">
  <name>Task 1: Add contract_review_enabled flag to config.py</name>
  <files>backend/app/config.py</files>
  <read_first>
    - backend/app/config.py (lines 184-205 — existing `harness_enabled`, `harness_smoke_enabled` flag block)
    - .planning/phases/22-contract-review-harness-docx-deliverable/22-PATTERNS.md (lines 530-540 — flag pattern + comment style)
  </read_first>
  <action>
    Insert this block in `backend/app/config.py` immediately AFTER the `harness_smoke_enabled: bool = False` line (current line 195). Match the comment style of the surrounding flags exactly:

    ```python
        # Phase 22 / v1.3 (CR-*, DOCX-*; D-16): Contract Review harness flag.
        # When False: Contract Review NOT registered in HarnessRegistry, gatekeeper
        # never sees it as a candidate, post_execute DOCX path inert. Codebase
        # byte-identical to pre-Phase-22 (D-16 invariant). Mirrors HARNESS_SMOKE_ENABLED
        # dark-launch precedent.
        contract_review_enabled: bool = False
    ```

    Do NOT modify any other line.
  </action>
  <verify>
    <automated>cd backend && source venv/bin/activate && python -c "from app.config import get_settings; s = get_settings(); assert s.contract_review_enabled is False, f'expected False got {s.contract_review_enabled}'; print('OK')"</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c "contract_review_enabled" backend/app/config.py` returns `1`
    - `grep -B 1 "contract_review_enabled: bool = False" backend/app/config.py | grep -c "Phase 22"` returns `1`
    - `python -c "from app.config import get_settings; print(get_settings().contract_review_enabled)"` prints `False`
    - `python -c "from app.main import app; print('OK')"` prints `OK`
  </acceptance_criteria>
  <done>Flag added with comment block; default False; module imports cleanly.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Author contract_review.py with skeleton + CR-01 + CR-02</name>
  <files>backend/app/harnesses/contract_review.py</files>
  <read_first>
    - backend/app/harnesses/smoke_echo.py (full file — 198 lines — closest analog)
    - backend/app/harnesses/types.py (HarnessDefinition, PhaseDefinition, PhaseType, HarnessPrerequisites)
    - backend/app/services/workspace_service.py (write_text_file, read_file, get_storage_signed_url for binary uploads)
    - .planning/phases/22-contract-review-harness-docx-deliverable/22-PATTERNS.md (lines 33-163 — module structure, Pydantic schema pattern, gated registration, CR-21-01 circular-import guard)
    - .planning/phases/22-contract-review-harness-docx-deliverable/22-CONTEXT.md (D-22-12, D-22-15, intro + display_name conventions)
  </read_first>
  <behavior>
    - Test 1: When `harness_enabled=True` AND `contract_review_enabled=True`, the harness registry contains `"contract-review"`.
    - Test 2: When either flag is False, the registry does NOT contain `"contract-review"` (off-mode invariant).
    - Test 3: `CONTRACT_REVIEW.phases` has exactly 9 entries with names `["intake", "classify", "gather-context", "load-playbook", "extract-clauses", "risk-analysis", "filter-redline-candidates", "redline-generation", "executive-summary"]` (ISSUE-06: filter phase between CR-06 and CR-07).
    - Test 4: `CONTRACT_REVIEW.phases[0].phase_type == PhaseType.PROGRAMMATIC` and `.executor is _phase1_intake`.
    - Test 5: `CONTRACT_REVIEW.phases[1].phase_type == PhaseType.LLM_SINGLE` and `.output_schema is ContractClassification`.
    - Test 6: CR-01 executor with a synthetic 200-byte DOCX upload returns `{"content": "<non-empty>", "page_count": 1, ...}` and writes contract-text.md.
    - Test 7: CR-01 executor with no upload returns error dict `{"error": "no_uploaded_file", "code": "NO_UPLOAD", ...}`.
    - Test 8: ContractClassification schema rejects empty parties list (`parties=[]` raises pydantic.ValidationError).
    - Test 9: ContractClassification schema rejects single party (`parties=["Acme"]` raises) — min_length=2 enforced.
    - Test 10: ContractClassification accepts a fully-populated valid instance.
  </behavior>
  <action>
    Create `backend/app/harnesses/contract_review.py`. Copy structural skeleton from `smoke_echo.py`, then specialize.

    **Header docstring + imports** — follow smoke_echo.py:1-31 shape verbatim, with REQ tags `CR-01..08, DOCX-01..08; D-22-01..15`:

    ```python
    """Phase 22 / v1.3 — Contract Review harness (CR-01..08, DOCX-01..08; D-22-01..15).

    9-phase deterministic Contract Review workflow exercising every phase type
    end-to-end and producing a polished .docx executive report. The 9-phase
    structure = 8 user-visible CR-XX phases + 1 PROGRAMMATIC filter step
    (`filter-redline-candidates`) inserted between CR-06 and CR-07 for cost
    optimization (ISSUE-06; ROADMAP success criterion 4). The filter is NOT a
    user-visible REQ — CR-01..08 still map 1:1 to the 8 named user phases.

      Phase 1 (CR-01) — Document Intake (PROGRAMMATIC): extract text from
        uploaded DOCX/PDF via python-docx + PyPDF2; write contract-text.md.
      Phase 2 (CR-02) — Contract Classification (LLM_SINGLE):
        type/parties/dates/governing_law/jurisdiction; ContractClassification schema.
      Phase 3 (CR-03) — Gather Context (LLM_HUMAN_INPUT)            [stub — plan 22-07]
      Phase 4 (CR-04) — Load Playbook (LLM_AGENT, max 10 rounds)    [stub — plan 22-07]
      Phase 5 (CR-05) — Clause Extraction (PROGRAMMATIC)            [stub — plan 22-08]
      Phase 6 (CR-06) — Risk Analysis (LLM_BATCH_AGENTS, batch=5)   [stub — plan 22-09]
      Phase 7 (filter-redline-candidates) — PROGRAMMATIC YELLOW/RED filter [stub — plan 22-09]
      Phase 8 (CR-07) — Redline Generation (LLM_BATCH_AGENTS, batch=5) [stub — plan 22-09]
      Phase 9 (CR-08) — Executive Summary + DOCX (LLM_SINGLE + post_execute) [stub — plan 22-10]

    Gated behind settings.harness_enabled AND settings.contract_review_enabled
    (D-16 dark-launch invariant). CR-21-01 circular-import lesson preserved via
    `from __future__ import annotations` + lazy-imported services.
    """
    from __future__ import annotations

    import io
    import logging
    from typing import Any

    from pydantic import BaseModel, Field

    from app.config import get_settings
    from app.harnesses.types import (
        HarnessDefinition,
        HarnessPrerequisites,
        PhaseDefinition,
        PhaseType,
    )
    from app.services.harness_registry import register
    from app.services.workspace_service import WorkspaceService

    logger = logging.getLogger(__name__)
    ```

    **Pydantic schemas** (CR-02 + a Phase-3..8 reservation block — keep it explicit):
    ```python
    # ---------------------------------------------------------------------------
    # CR-02 — Contract Classification structured output schema
    # ---------------------------------------------------------------------------

    class ContractClassification(BaseModel):
        """CR-02 LLM output. Enforced via response_format=json_schema (HARN-05).

        ROADMAP success criterion: parties has min_length=2, contract_type non-empty.
        """
        contract_type: str = Field(..., min_length=1, max_length=200,
            description="Type of contract: MSA, NDA, SaaS, Employment, Distribution, etc.")
        parties: list[str] = Field(..., min_length=2, max_length=20,
            description="Named legal entities, e.g. ['Acme Corp', 'Beta Inc']. Min 2.")
        effective_date: str | None = Field(None,
            description="ISO 8601 (YYYY-MM-DD) if present in contract, else null")
        expiration_date: str | None = Field(None,
            description="ISO 8601 (YYYY-MM-DD) if present, else null")
        governing_law: str = Field(..., min_length=1, max_length=200,
            description="Jurisdiction name: 'Republic of Indonesia', 'New York State', etc.")
        jurisdiction: str = Field(..., min_length=1, max_length=200,
            description="Forum / venue: 'courts of Jakarta', 'arbitration in Singapore', etc.")
        summary: str = Field(..., min_length=20, max_length=1000,
            description="1-2 sentence neutral description of contract scope and parties")
    ```

    **CR-01 executor** — programmatic intake. Reads the FIRST upload from the workspace, runs python-docx for DOCX or PyPDF2 for PDF, returns content. Note: `python-docx` and `PyPDF2` are pre-installed in the BACKEND requirements (UPL-03 path) so this runs in the FastAPI process, not the sandbox:

    ```python
    async def _phase1_intake(
        *, inputs: dict[str, str], token: str, thread_id: str, harness_run_id: str
    ) -> dict:
        """CR-01: extract text from the user's uploaded DOCX/PDF; write contract-text.md."""
        ws = WorkspaceService(token=token)
        try:
            files = await ws.list_files(thread_id)
        except Exception as exc:
            logger.error("CR-01 list_files failed harness_run=%s: %s", harness_run_id, exc, exc_info=True)
            return {"error": "list_files_failed", "code": "WS_LIST_ERROR", "detail": str(exc)[:500]}

        # Find the first user-uploaded file (D-22 contract-review supports exactly one contract per run)
        uploads = [f for f in files if f.get("source") == "upload"]
        if not uploads:
            return {"error": "no_uploaded_file", "code": "NO_UPLOAD",
                    "detail": "No source='upload' file found in workspace; user must upload a contract first."}

        target = uploads[0]
        file_path = target.get("file_path", "")
        mime = (target.get("mime_type") or "").lower()

        # Fetch binary content from storage
        try:
            content_bytes = await ws.read_binary_file(thread_id, file_path)
        except Exception as exc:
            logger.error("CR-01 read_binary_file failed: %s", exc, exc_info=True)
            return {"error": "read_failed", "code": "READ_FAILED", "detail": str(exc)[:500]}

        # Extract text by mime type
        try:
            if "wordprocessingml" in mime or file_path.lower().endswith(".docx"):
                from docx import Document  # python-docx
                doc = Document(io.BytesIO(content_bytes))
                paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
                text = "\n\n".join(paragraphs)
                page_count = max(1, len(paragraphs) // 30)  # rough estimate
            elif "pdf" in mime or file_path.lower().endswith(".pdf"):
                from PyPDF2 import PdfReader
                reader = PdfReader(io.BytesIO(content_bytes))
                pages_text = [page.extract_text() or "" for page in reader.pages]
                text = "\n\n".join(pages_text)
                page_count = len(reader.pages)
            else:
                return {"error": "unsupported_mime", "code": "BAD_MIME",
                        "detail": f"Expected DOCX or PDF; got {mime!r} for {file_path!r}"}
        except Exception as exc:
            logger.error("CR-01 extraction failed for %s: %s", file_path, exc, exc_info=True)
            return {"error": "extraction_failed", "code": "EXTRACT_FAILED", "detail": str(exc)[:500]}

        if not text.strip():
            return {"error": "empty_extraction", "code": "EMPTY_TEXT",
                    "detail": f"Extracted text is empty for {file_path!r}; file may be scanned or corrupted."}

        markdown = (
            f"# Contract Source\n\n"
            f"- **File:** `{file_path}`\n"
            f"- **MIME:** `{mime}`\n"
            f"- **Pages:** {page_count}\n"
            f"- **Characters:** {len(text)}\n\n"
            f"---\n\n"
            f"{text}\n"
        )

        return {
            "content": markdown,            # engine writes to contract-text.md per workspace_output
            "page_count": page_count,
            "char_count": len(text),
            "source_file": file_path,
        }
    ```

    **Stub executors for CR-03..08 + filter step** — fail closed so partial completion is detectable. Each stub returns a clear "not implemented" error dict; subsequent plans replace the executor in-place:
    ```python
    async def _phase_stub_not_implemented(*, inputs, token, thread_id, harness_run_id) -> dict:
        return {
            "error": "phase_not_implemented",
            "code": "STUB",
            "detail": "This Contract Review phase is a Phase 22 stub. Subsequent plans 22-07..22-10 fill it in."
        }
    ```

    **HarnessDefinition** — 9-phase scaffold (8 user-visible CR-XX + 1 programmatic filter), gated registration:
    ```python
    CONTRACT_REVIEW = HarnessDefinition(
        name="contract-review",
        display_name="Contract Review",
        prerequisites=HarnessPrerequisites(
            requires_upload=True,
            upload_description="your contract DOCX or PDF (one file)",
            accepted_mime_types=[
                "application/pdf",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ],
            min_files=1,
            max_files=1,
            harness_intro=(
                "Hi! I'm the Contract Review harness. Upload a contract (DOCX or PDF) "
                "and I'll classify it, gather your review context, load the playbook, "
                "extract every clause, grade each one for risk against the playbook, "
                "draft redlines for problematic clauses, and deliver an executive .docx report."
            ),
        ),
        phases=[
            # Phase 1 — CR-01 Document Intake (PROGRAMMATIC)
            PhaseDefinition(
                name="intake",
                description="Extract text from uploaded DOCX/PDF; write contract-text.md.",
                phase_type=PhaseType.PROGRAMMATIC,
                tools=[],
                workspace_inputs=[],
                workspace_output="contract-text.md",
                executor=_phase1_intake,
                timeout_seconds=120,
            ),
            # Phase 2 — CR-02 Contract Classification (LLM_SINGLE)
            PhaseDefinition(
                name="classify",
                description="Classify type/parties/dates/governing_law/jurisdiction (Pydantic-validated).",
                phase_type=PhaseType.LLM_SINGLE,
                system_prompt_template=(
                    "You are classifying a legal contract. Read contract-text.md and produce "
                    "a JSON object matching the ContractClassification schema:\n"
                    "  - contract_type: short string (e.g. 'MSA', 'NDA', 'SaaS Subscription')\n"
                    "  - parties: array of >=2 legal entity names (verbatim if possible)\n"
                    "  - effective_date / expiration_date: ISO 8601 (YYYY-MM-DD) or null\n"
                    "  - governing_law: jurisdiction name (e.g. 'Republic of Indonesia')\n"
                    "  - jurisdiction: forum/venue clause (e.g. 'courts of Jakarta')\n"
                    "  - summary: 1-2 sentence neutral description (20-1000 chars)\n"
                    "Return ONLY the JSON object — no prose."
                ),
                tools=[],
                workspace_inputs=["contract-text.md"],
                workspace_output="classification.md",
                output_schema=ContractClassification,
                timeout_seconds=180,
            ),
            # Phase 3 — CR-03 Gather Context (LLM_HUMAN_INPUT)  [populated in plan 22-07]
            PhaseDefinition(
                name="gather-context",
                description="Stub — Plan 22-07 populates the HIL question prompt.",
                phase_type=PhaseType.LLM_HUMAN_INPUT,
                system_prompt_template="STUB",
                tools=[],
                workspace_inputs=["classification.md"],
                workspace_output="review-context.md",
                timeout_seconds=86_400,
            ),
            # Phase 4 — CR-04 Load Playbook (LLM_AGENT, max 10 rounds)  [populated in plan 22-07]
            PhaseDefinition(
                name="load-playbook",
                description="Stub — Plan 22-07 populates the RAG-agent prompt.",
                phase_type=PhaseType.LLM_AGENT,
                system_prompt_template="STUB",
                tools=["search_documents", "analyze_document"],
                workspace_inputs=["classification.md", "review-context.md"],
                workspace_output="playbook-context.md",
                timeout_seconds=600,
            ),
            # Phase 5 — CR-05 Clause Extraction (PROGRAMMATIC)  [populated in plan 22-08]
            PhaseDefinition(
                name="extract-clauses",
                description="Stub — Plan 22-08 populates the chunk-and-extract executor.",
                phase_type=PhaseType.PROGRAMMATIC,
                tools=[],
                workspace_inputs=["contract-text.md"],
                workspace_output="clauses.md",
                executor=_phase_stub_not_implemented,
                timeout_seconds=600,
            ),
            # Phase 6 — CR-06 Risk Analysis (LLM_BATCH_AGENTS)  [populated in plan 22-09]
            PhaseDefinition(
                name="risk-analysis",
                description="Stub — Plan 22-09 populates the per-clause risk assessment.",
                phase_type=PhaseType.LLM_BATCH_AGENTS,
                system_prompt_template="STUB",
                tools=["search_documents_by_doc_ids", "analyze_document"],
                workspace_inputs=["clauses.json", "playbook-context.md", "review-context.md"],
                workspace_output="risk-analysis.json",
                batch_size=5,
                timeout_seconds=1800,
            ),
            # Phase 7 — Filter Redline Candidates (PROGRAMMATIC — ISSUE-06 cost optimization)  [populated in plan 22-09]
            # Filters risk-analysis.json to YELLOW/RED clauses; writes redline-candidates.json.
            # Stub closes the loop until plan 22-09 wires _phase_filter_redline_candidates.
            # NOTE: this is an internal cost-optimization step, NOT a user-visible REQ.
            # CR-01..08 still map 1:1 to the 8 named user phases.
            PhaseDefinition(
                name="filter-redline-candidates",
                description="Stub — Plan 22-09 populates the YELLOW/RED filter executor.",
                phase_type=PhaseType.PROGRAMMATIC,
                tools=[],
                workspace_inputs=["risk-analysis.json"],
                workspace_output="redline-candidates.json",
                executor=_phase_stub_not_implemented,
                timeout_seconds=30,
            ),
            # Phase 8 — CR-07 Redline Generation (LLM_BATCH_AGENTS)  [populated in plan 22-09]
            PhaseDefinition(
                name="redline-generation",
                description="Stub — Plan 22-09 populates the per-clause redline drafter.",
                phase_type=PhaseType.LLM_BATCH_AGENTS,
                system_prompt_template="STUB",
                tools=["search_documents_by_doc_ids", "analyze_document"],
                workspace_inputs=["redline-candidates.json", "playbook-context.md", "review-context.md"],
                workspace_output="redlines.json",
                batch_size=5,
                timeout_seconds=1800,
            ),
            # Phase 9 — CR-08 Executive Summary + DOCX post_execute  [populated in plan 22-10]
            PhaseDefinition(
                name="executive-summary",
                description="Stub — Plan 22-10 populates the summary prompt + DOCX post_execute.",
                phase_type=PhaseType.LLM_SINGLE,
                system_prompt_template="STUB",
                tools=[],
                workspace_inputs=[
                    "classification.md", "review-context.md", "playbook-context.md",
                    "clauses.md", "risk-analysis.json", "redlines.json",
                ],
                workspace_output="contract-review-report.md",
                output_schema=None,           # Plan 22-10 sets ExecutiveSummary
                post_execute=None,            # Plan 22-10 sets _generate_docx_post_execute
                timeout_seconds=300,
            ),
        ],
    )
    ```

    **Gated registration** at end of file (mirror smoke_echo.py:192-197):
    ```python
    if get_settings().harness_enabled and get_settings().contract_review_enabled:
        register(CONTRACT_REVIEW)
        logger.info("contract_review: registered (HARNESS_ENABLED=True, CONTRACT_REVIEW_ENABLED=True)")
    else:
        logger.info(
            "contract_review: NOT registered (harness_enabled=%s, contract_review_enabled=%s)",
            get_settings().harness_enabled,
            get_settings().contract_review_enabled,
        )
    ```

    Note: `read_binary_file` is added by Task 0 of THIS plan (ISSUE-02 resolution). The `_phase1_intake` executor calls it directly via `await ws.read_binary_file(thread_id, file_path)`. The method returns `bytes` on success or a structured error dict on failure — wrap with isinstance(..., bytes) check and convert error dicts to the executor's error-dict shape. Do NOT in-line storage logic in contract_review.py.

    Add ISSUE-09 runtime guard at the bottom of contract_review.py — replace the simple gated registration block with:
    ```python
    if get_settings().harness_enabled and get_settings().contract_review_enabled:
        if not get_settings().tool_registry_enabled:
            logger.error(
                "contract_review: REFUSING to register — contract_review_enabled=True but "
                "tool_registry_enabled=False. CR-06/07 require search_documents_by_doc_ids "
                "(plan 22-02), which is gated on tool_registry_enabled. Enable both or neither."
            )
            raise RuntimeError(
                "ISSUE-09: contract_review_enabled requires tool_registry_enabled — refusing to register harness"
            )
        register(CONTRACT_REVIEW)
        logger.info("contract_review: registered (HARNESS_ENABLED=True, CONTRACT_REVIEW_ENABLED=True, TOOL_REGISTRY_ENABLED=True)")
    else:
        logger.info(
            "contract_review: NOT registered (harness_enabled=%s, contract_review_enabled=%s)",
            get_settings().harness_enabled,
            get_settings().contract_review_enabled,
        )
    ```
  </action>
  <verify>
    <automated>cd backend && source venv/bin/activate && pytest tests/harnesses/test_contract_review_skeleton.py -v --tb=short && python -c "from app.main import app; print('OK')"</automated>
  </verify>
  <acceptance_criteria>
    - `python -c "from app.harnesses.contract_review import CONTRACT_REVIEW, ContractClassification; print(len(CONTRACT_REVIEW.phases))"` prints `9`
    - `grep -c "register(CONTRACT_REVIEW)" backend/app/harnesses/contract_review.py` returns `1`
    - `grep -c "harness_enabled and get_settings().contract_review_enabled" backend/app/harnesses/contract_review.py` returns `1`
    - `python -c "from app.harnesses.contract_review import CONTRACT_REVIEW; names = [p.name for p in CONTRACT_REVIEW.phases]; assert names == ['intake', 'classify', 'gather-context', 'load-playbook', 'extract-clauses', 'risk-analysis', 'filter-redline-candidates', 'redline-generation', 'executive-summary'], names; print('OK')"` prints `OK`
    - `python -c "from app.main import app; print('OK')"` prints `OK` (no circular imports)
  </acceptance_criteria>
  <done>contract_review.py module exists with 9-phase skeleton (8 user-visible CR-XX + 1 filter), CR-01 executor, CR-02 schema, gated registration; CR-03..08 + filter are explicit stubs.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: Add skeleton tests</name>
  <files>backend/tests/harnesses/test_contract_review_skeleton.py</files>
  <read_first>
    - backend/app/harnesses/contract_review.py (post-Task-2 state)
    - backend/tests/services/test_gatekeeper.py (AsyncMock + pytest.mark.asyncio patterns)
    - backend/app/harnesses/types.py (PhaseType enum values)
  </read_first>
  <behavior>
    See behaviors 1-10 in Task 2 of this plan.
    PLUS:
    - Test 11 (ISSUE-09): with `harness_enabled=True, contract_review_enabled=True, tool_registry_enabled=False`, importing the module raises RuntimeError with "ISSUE-09" in the message.
    - Test 12 (ISSUE-14 deploy-order doc): assert plan-body comment block in contract_review.py mentions the deploy-order constraint (grep for "deploy-order" or "ISSUE-14").
  </behavior>
  <action>
    Create `backend/tests/harnesses/test_contract_review_skeleton.py`. Tests 1-10 from the behavior block. Concrete shapes:

    Test 6 (CR-01 happy path) — generate a synthetic DOCX in-memory:
    ```python
    @pytest.mark.asyncio
    async def test_phase1_intake_extracts_docx_text(monkeypatch):
        from docx import Document
        buf = io.BytesIO()
        d = Document()
        d.add_paragraph("This is a test contract between Acme Corp and Beta Inc.")
        d.add_paragraph("Effective date: 2026-01-01.")
        d.save(buf)
        synthetic = buf.getvalue()

        ws_mock = MagicMock()
        ws_mock.list_files = AsyncMock(return_value=[
            {"file_path": "test.docx", "mime_type":
              "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
             "source": "upload", "size_bytes": len(synthetic)},
        ])
        ws_mock.read_binary_file = AsyncMock(return_value=synthetic)

        with patch("app.harnesses.contract_review.WorkspaceService", return_value=ws_mock):
            from app.harnesses.contract_review import _phase1_intake
            result = await _phase1_intake(inputs={}, token="tok", thread_id="thr", harness_run_id="run")

        assert "content" in result
        assert "Acme Corp" in result["content"]
        assert result.get("source_file") == "test.docx"
    ```

    Test 8/9 (Pydantic validation) — pure schema test, no async:
    ```python
    def test_contract_classification_rejects_single_party():
        from app.harnesses.contract_review import ContractClassification
        with pytest.raises(Exception):
            ContractClassification(
                contract_type="MSA", parties=["Acme"],
                governing_law="Indonesia", jurisdiction="Jakarta",
                summary="Master Services Agreement between one party and...",
            )
    ```

    Tests 1-2 (flag gating) — use `monkeypatch.setattr` on `get_settings` to flip the flags + reload the module.
  </action>
  <verify>
    <automated>cd backend && source venv/bin/activate && pytest tests/harnesses/test_contract_review_skeleton.py -v --tb=short</automated>
  </verify>
  <acceptance_criteria>
    - `pytest backend/tests/harnesses/test_contract_review_skeleton.py -v` exits 0 with 12 tests passing
    - `grep -c "ContractClassification" backend/tests/harnesses/test_contract_review_skeleton.py` returns `>= 3`
    - `grep -c "_phase1_intake" backend/tests/harnesses/test_contract_review_skeleton.py` returns `>= 1`
  </acceptance_criteria>
  <done>12 tests pass — flag gating + 9-phase shape + CR-01 happy/error paths + CR-02 schema validation + ISSUE-09 tool_registry guard + ISSUE-14 deploy-order doc locked in.</done>
</task>

</tasks>

<truths>
- D-16 OFF-mode invariant — Contract Review NOT registered when either flag is False.
- D-22-12 (programmatic python-docx) — CR-01 uses python-docx + PyPDF2 in the BACKEND process (UPL-03 path), not the sandbox. The sandbox is for DOCX **writing** (plan 22-10), not text **extraction**.
- HARN-05 enforcement — CR-02 uses Pydantic + json_schema response_format (engine handles via PhaseDefinition.output_schema).
- ROADMAP success criterion (5.1): "Pydantic schema enforces ≥2 parties, non-empty type" — explicit in ContractClassification.
- CR-21-01 circular-import lesson — preserved via `from __future__ import annotations` + lazy imports (`from docx import Document` inside function).
- The 9-scaffold lets the gatekeeper trigger and the engine reach CR-02 successfully in a smoke run; CR-03's stub fails closed so it's clear which plan is next to land.
</truths>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| User upload (DOCX/PDF) → CR-01 extractor | Untrusted bytes; could be malformed, scanned-only PDF, or zip-bomb DOCX |
| CR-01 extracted text → CR-02 LLM payload | Text is real PII per UU PDP; routes through existing egress filter wrap (B4 single-registry) |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-22-06-01 | Information Disclosure | Contract PII in CR-02 LLM payload | mitigate | Existing SEC-04 egress filter wrap on LLM_SINGLE dispatch (harness_engine.py:543-554) — already covered |
| T-22-06-02 | DoS | Zip-bomb DOCX in CR-01 | mitigate | UPL-02 already enforces 25 MB cap on upload; CR-01 catches any extraction exception via try/except |
| T-22-06-03 | Information Disclosure | Stack trace from extraction failure leaking file paths | mitigate | str(exc)[:500] cap; logger.error not user-facing |
| T-22-06-04 | Spoofing | Malicious user re-uploads contract pretending to be different party | accept | Out of scope; harness uses what's in workspace_files, RLS enforces ownership |
</threat_model>

<verification>
1. `pytest backend/tests/harnesses/test_contract_review_skeleton.py -v` exits 0
2. `python -c "from app.main import app; print('OK')"` prints `OK`
3. `python -c "from app.harnesses.contract_review import CONTRACT_REVIEW; print(len(CONTRACT_REVIEW.phases))"` prints `9`
4. With `HARNESS_ENABLED=False`: `python -c "from app.services.harness_registry import get_harness; print(get_harness('contract-review'))"` prints `None`
</verification>

<success_criteria>
- 9-phase skeleton committed (8 user-visible CR-XX + 1 programmatic filter); CR-01 + CR-02 functional
- Flag-gated, off-mode byte-identical
- CR-03..08 + filter step are explicit stubs failing closed
- Subsequent plans 22-07..22-10 replace stub bodies in-place without restructuring
</success_criteria>

<output>
After completion, create `.planning/phases/22-contract-review-harness-docx-deliverable/22-06-SUMMARY.md`.
</output>
