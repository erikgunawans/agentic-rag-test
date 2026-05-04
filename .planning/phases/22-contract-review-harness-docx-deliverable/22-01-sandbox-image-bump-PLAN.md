---
phase: 22-contract-review-harness-docx-deliverable
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/sandbox/Dockerfile
  - backend/tests/sandbox/test_dockerfile_deps.py
autonomous: true
requirements: [DOCX-01]
must_haves:
  truths:
    - "Sandbox image rebuild succeeds with python-docx 1.1.2 + PyPDF2 3.0.1 installed"
    - "A python-docx import + Document() smoke check runs cleanly inside the sandbox container"
    - "Off-mode invariant: when CONTRACT_REVIEW_ENABLED=False the new deps are still present but unused (cold-start budget acceptable)"
  artifacts:
    - path: "backend/sandbox/Dockerfile"
      provides: "python-docx + PyPDF2 RUN layer before chmod 777"
      contains: "RUN pip install --no-cache-dir python-docx==1.1.2 PyPDF2==3.0.1"
    - path: "backend/tests/sandbox/test_dockerfile_deps.py"
      provides: "Pinned-version assertion test (catches accidental version drift)"
  key_links:
    - from: "backend/sandbox/Dockerfile"
      to: "post_execute DOCX generation in plan 22-10"
      via: "python-docx Document API in sandbox python script"
      pattern: "python-docx==1\\.1\\.2"
---

<objective>
Bump the sandbox Docker image to install `python-docx==1.1.2` and `PyPDF2==3.0.1` so that DOCX-01..08 (post_execute callback in plan 22-10) can run a python-docx generation script inside the sandbox.

Purpose: DOCX-01 requires the sandbox to host python-docx. The current `backend/sandbox/Dockerfile` has only stdlib + tool_client.py — no third-party libs.
Output: Updated Dockerfile + assertion test pinning the exact versions.
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
@backend/sandbox/Dockerfile
</context>

<tasks>

<task type="auto">
  <name>Task 1: Add python-docx + PyPDF2 install layer to sandbox Dockerfile</name>
  <files>backend/sandbox/Dockerfile</files>
  <read_first>
    - backend/sandbox/Dockerfile (file being modified — current state ends at WORKDIR /sandbox, line 25)
    - .planning/phases/22-contract-review-harness-docx-deliverable/22-PATTERNS.md (lines 332-360 — exact patch shape and rationale)
  </read_first>
  <action>
    In `backend/sandbox/Dockerfile`, insert exactly this block AFTER the existing `COPY tool_client.py /sandbox/tool_client.py` line and BEFORE the `RUN chmod 777 /sandbox` line:

    ```dockerfile
    # DOCX-01 / Phase 22: python-docx for DOCX report generation,
    # PyPDF2 for any contract-text fallback parsing inside the sandbox.
    RUN pip install --no-cache-dir python-docx==1.1.2 PyPDF2==3.0.1
    ```

    Do not modify any other line. Versions are pinned exactly per CONTEXT.md D-22-12 and PATTERNS.md L355.

    Notes:
    - The base image is `python:3.12-slim` — pip is preinstalled.
    - `--no-cache-dir` keeps the image lean (CONTEXT.md "cold-start budget" guidance — accepting ~5 MB image growth, layer-on-demand was rejected).
    - Do NOT touch `backend/Dockerfile` (the Railway production image) — per Patterns L360, python-docx may already be present there from UPL-03 work; verify in Task 2 but do not modify.
  </action>
  <verify>
    <automated>cd backend/sandbox && docker build -t lexcore-sandbox:phase22-test . && docker run --rm lexcore-sandbox:phase22-test python -c "from docx import Document; from PyPDF2 import PdfReader; print('OK')"</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c "python-docx==1.1.2" backend/sandbox/Dockerfile` returns `1`
    - `grep -c "PyPDF2==3.0.1" backend/sandbox/Dockerfile` returns `1`
    - `docker build -t lexcore-sandbox:phase22-test backend/sandbox/` exits 0
    - `docker run --rm lexcore-sandbox:phase22-test python -c "from docx import Document; from PyPDF2 import PdfReader; print('OK')"` prints `OK`
    - `wc -l backend/sandbox/Dockerfile` is exactly previous-line-count + 3 (one comment + one RUN line + one blank line)
  </acceptance_criteria>
  <done>Dockerfile contains pinned-version RUN layer, builds cleanly, smoke check imports python-docx + PyPDF2 successfully.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Add pinned-version assertion test + verify backend Dockerfile parity</name>
  <files>backend/tests/sandbox/test_dockerfile_deps.py</files>
  <read_first>
    - backend/sandbox/Dockerfile (post-Task-1 state)
    - backend/Dockerfile (verify whether python-docx already present per CONTEXT.md UPL-03 work)
    - backend/tests/services/test_gatekeeper.py (analog for pytest module shape; lines 1-40 for header + import style)
  </read_first>
  <behavior>
    - Test 1: `test_sandbox_dockerfile_pins_python_docx_1_1_2` reads `backend/sandbox/Dockerfile` and asserts the literal string `python-docx==1.1.2` appears exactly once.
    - Test 2: `test_sandbox_dockerfile_pins_pypdf2_3_0_1` reads same file and asserts `PyPDF2==3.0.1` appears exactly once.
    - Test 3: `test_sandbox_dockerfile_install_layer_before_chmod` asserts the `RUN pip install` line index < the `RUN chmod 777` line index (Docker layer ordering).
    - Test 4: `test_backend_dockerfile_has_python_docx_for_upl_03` reads `backend/Dockerfile`; if `python-docx` is missing there, assert it is present in `backend/requirements.txt` (UPL-03 must have a working text-extraction path for DOCX upload).
  </behavior>
  <action>
    Create `backend/tests/sandbox/test_dockerfile_deps.py` with the four assertions described above. Use plain `pathlib.Path(__file__).parents[2] / "sandbox" / "Dockerfile"` (test file at `backend/tests/sandbox/test_dockerfile_deps.py`, so 2 parents up = `backend/`). Read text once at module scope and reuse across tests.

    Header should follow `backend/tests/services/test_gatekeeper.py:1-19` shape — short docstring with REQ tag (`DOCX-01`), `from __future__ import annotations`, `import pathlib`, `import pytest`. NO unittest.mock needed — these are pure file-text assertions.

    Concrete test 1 body:
    ```python
    def test_sandbox_dockerfile_pins_python_docx_1_1_2():
        text = (pathlib.Path(__file__).parents[2] / "sandbox" / "Dockerfile").read_text()
        assert text.count("python-docx==1.1.2") == 1
    ```

    Concrete test 4 body:
    ```python
    def test_backend_dockerfile_has_python_docx_for_upl_03():
        backend_root = pathlib.Path(__file__).parents[2]
        df = (backend_root / "Dockerfile").read_text()
        req = (backend_root / "requirements.txt").read_text()
        assert "python-docx" in df or "python-docx" in req, (
            "UPL-03 (DOCX upload text extraction) requires python-docx in the backend "
            "Railway image — found in neither Dockerfile nor requirements.txt"
        )
    ```

    If Test 4 fails (python-docx missing from backend deps), this is a UPL-03 carryover bug — log it via `pytest.fail` rather than silently skipping. Do NOT fix it in this plan; surface it for plan 22-10 to address if needed.
  </action>
  <verify>
    <automated>cd backend && source venv/bin/activate && pytest tests/sandbox/test_dockerfile_deps.py -v --tb=short</automated>
  </verify>
  <acceptance_criteria>
    - `pytest backend/tests/sandbox/test_dockerfile_deps.py -v` exits 0 with 4 tests passing
    - `grep -c "python-docx==1.1.2" backend/tests/sandbox/test_dockerfile_deps.py` returns `1`
    - `grep -c "PyPDF2==3.0.1" backend/tests/sandbox/test_dockerfile_deps.py` returns `1`
    - File contains `from __future__ import annotations` (project convention, matches gatekeeper test analog)
  </acceptance_criteria>
  <done>Four tests pass, version pin assertions are version-locked (catches accidental drift), and UPL-03 backend Dockerfile parity verified.</done>
</task>

</tasks>

<truths>
- D-22-12 (pure programmatic python-docx generation, no template file) — sandbox needs the library installed.
- DOCX-01 dependency on `python-docx`, also referenced in CR-05 chunking via PyPDF2.
- D-16 OFF-mode invariant: extra deps in sandbox image do NOT change behavior when CONTRACT_REVIEW_ENABLED=False (deps simply unused).
- CLAUDE.md Gotcha #3 (Railway manual deploy): `backend/sandbox/Dockerfile` is the SANDBOX image, NOT `backend/Dockerfile` (Railway production). Bumping the sandbox image requires rebuilding the sandbox container, not redeploying the backend.
- PATTERNS.md L360 cross-check: `backend/Dockerfile` may already have python-docx for UPL-03; do NOT duplicate.
</truths>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Docker image build | external (PyPI) → sandbox image; pinned versions limit supply-chain drift |
| Sandbox runtime → host | Already isolated by sandbox container; new deps run only inside container |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-22-01-01 | Tampering | sandbox Dockerfile dep | mitigate | Exact-version pin (`==1.1.2`, `==3.0.1`) prevents silent supply-chain drift on rebuild |
| T-22-01-02 | Information Disclosure | python-docx parsing untrusted user contracts | accept | Parsing happens INSIDE sandbox container, not on host; no PII reaches LLM payloads (egress filter enforced upstream in plan 22-10) |
| T-22-01-03 | Denial of Service | malformed DOCX crashing sandbox | accept | Sandbox already enforces 30s timeout via BRIDGE_TIMEOUT; D-22-15 non-fatal fallback covers in plan 22-10 |
</threat_model>

<verification>
1. `docker build -t lexcore-sandbox:phase22-test backend/sandbox/` succeeds (REQUIRES Docker daemon — see ISSUE-18 fallback)
2. `docker run --rm lexcore-sandbox:phase22-test python -c "from docx import Document; doc = Document(); doc.add_heading('test'); print('OK')"` prints `OK`
3. `pytest backend/tests/sandbox/test_dockerfile_deps.py` exits 0 (text-only assertions, no Docker required — primary CI gate)
4. `grep -E "python-docx==1.1.2|PyPDF2==3.0.1" backend/sandbox/Dockerfile | wc -l` returns `2`

**ISSUE-18 — Docker requirement in CI:** Steps 1-2 require a running Docker daemon. If Docker is unavailable in the local/CI environment (e.g., GitHub Actions without docker-in-docker), step 3 (the file-content-only pytest) is the SUFFICIENT primary gate — it asserts the version pins are present in the Dockerfile text without building. Docker steps 1-2 are RECOMMENDED for local pre-merge validation but optional in CI. Document this in the plan SUMMARY.md.
</verification>

<success_criteria>
- Sandbox image rebuilds cleanly with new deps
- `python-docx` and `PyPDF2` importable inside the sandbox container
- Pinned-version assertion test passes (regression guard)
- No changes to `backend/Dockerfile` — UPL-03 path unchanged
</success_criteria>

<output>
After completion, create `.planning/phases/22-contract-review-harness-docx-deliverable/22-01-SUMMARY.md`.
</output>
