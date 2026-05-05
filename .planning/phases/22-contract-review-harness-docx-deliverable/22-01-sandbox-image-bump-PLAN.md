---
phase: 22-contract-review-harness-docx-deliverable
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/sandbox/Dockerfile
  - backend/requirements.txt
  - backend/tests/sandbox/test_dockerfile_deps.py
autonomous: true
requirements: [DOCX-01, CR-01]
must_haves:
  truths:
    - "Sandbox image rebuild succeeds with python-docx 1.1.2 + PyPDF2 3.0.1 installed"
    - "Backend runtime requirements.txt has PyPDF2 added (REVIEW #5: CR-01 PDF intake runs in FastAPI process, NOT sandbox — sandbox-only install would crash PDF uploads)"
    - "Backend runtime already has python-docx>=1.1.0 (line 12) — preserved and parity-tested"
    - "A python-docx import + Document() smoke check runs cleanly inside the sandbox container"
    - "A backend-side import smoke check confirms `from PyPDF2 import PdfReader` succeeds in the FastAPI venv"
    - "Off-mode invariant: when CONTRACT_REVIEW_ENABLED=False the new deps are still present but unused"
  artifacts:
    - path: "backend/sandbox/Dockerfile"
      provides: "python-docx + PyPDF2 RUN layer before chmod 777 (sandbox-side; for python-docx generation in plan 22-10 + any in-sandbox PDF parsing)"
      contains: "RUN pip install --no-cache-dir python-docx==1.1.2 PyPDF2==3.0.1"
    - path: "backend/requirements.txt"
      provides: "PyPDF2 added to backend runtime deps (CR-01 PDF intake runs in FastAPI process, not sandbox)"
      contains: "PyPDF2"
    - path: "backend/tests/sandbox/test_dockerfile_deps.py"
      provides: "Pinned-version assertion test + backend runtime parity guards for BOTH python-docx AND PyPDF2"
  key_links:
    - from: "backend/sandbox/Dockerfile"
      to: "post_execute DOCX generation in plan 22-10"
      via: "python-docx Document API in sandbox python script"
      pattern: "python-docx==1\\.1\\.2"
    - from: "backend/requirements.txt PyPDF2"
      to: "CR-01 intake executor in plan 22-06"
      via: "PdfReader().pages text extraction inside FastAPI process"
      pattern: "PyPDF2"
---

<objective>
Bump the sandbox Docker image AND the backend runtime to install `python-docx==1.1.2` + `PyPDF2==3.0.1`. The sandbox install is for DOCX-01..08 (post_execute generation in plan 22-10). The **backend runtime install of PyPDF2 is required by CR-01 (PDF intake) which runs in the FastAPI process, not the sandbox**. REVIEW #5 caught this gap: PyPDF2 was sandbox-only in the prior version of this plan, so PDF uploads would fail in production.

Purpose:
- Sandbox: enables python-docx generation in plan 22-10's post_execute callback.
- Backend runtime: enables PDF text extraction during CR-01 intake (`backend/app/harnesses/contract_review.py::_phase1_intake` to be created in plan 22-06).

Output: Updated Dockerfile + requirements.txt + parity-test that guards BOTH dependencies on BOTH images.
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
@backend/requirements.txt
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
  </action>
  <verify>
    <automated>cd backend/sandbox && docker build -t lexcore-sandbox:phase22-test . && docker run --rm lexcore-sandbox:phase22-test python -c "from docx import Document; from PyPDF2 import PdfReader; print('OK')"</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c "python-docx==1.1.2" backend/sandbox/Dockerfile` returns `1`
    - `grep -c "PyPDF2==3.0.1" backend/sandbox/Dockerfile` returns `1`
    - `docker build -t lexcore-sandbox:phase22-test backend/sandbox/` exits 0
    - `docker run --rm lexcore-sandbox:phase22-test python -c "from docx import Document; from PyPDF2 import PdfReader; print('OK')"` prints `OK`
  </acceptance_criteria>
  <done>Dockerfile contains pinned-version RUN layer, builds cleanly, smoke check imports python-docx + PyPDF2 successfully.</done>
</task>

<task type="auto">
  <name>Task 2: Add PyPDF2 to backend/requirements.txt for CR-01 PDF intake (REVIEW #5)</name>
  <files>backend/requirements.txt</files>
  <read_first>
    - backend/requirements.txt (verify line 12 has `python-docx>=1.1.0` already present — DO NOT duplicate)
    - .planning/phases/22-contract-review-harness-docx-deliverable/22-REVIEWS.md (review finding #5: "PDF path is incomplete in the backend runtime. python-docx is in backend/requirements.txt, but PyPDF2 is not.")
  </read_first>
  <action>
    Add `PyPDF2>=3.0.1` immediately AFTER the existing `python-docx>=1.1.0` line (line 12). Do NOT change any other line. Use a `>=` floor (not `==` pin) to match the project convention for backend deps; the sandbox image uses `==` for hermetic isolation.

    The exact insertion:

    Before (line 12):
    ```
    python-docx>=1.1.0
    ```

    After:
    ```
    python-docx>=1.1.0
    PyPDF2>=3.0.1
    ```

    Add an inline comment IF the surrounding lines have comments — do NOT introduce new comments otherwise (project convention: requirements.txt comments only mark milestone groupings).

    **Why a floor and not exact pin:** the backend image gets re-built more often than the sandbox; pinning exact would conflict with transitive deps as `pymupdf` etc. evolve. Sandbox is hermetic so `==` is fine.

    **Note:** PyPDF2 v3+ is the maintained fork (the original project moved to `pypdf` but PyPDF2 wheels still ship and the import name `PyPDF2` matches the planned `from PyPDF2 import PdfReader` in plan 22-06's CR-01 executor.) Do NOT switch to `pypdf` here — keep import-name parity with the sandbox image.
  </action>
  <verify>
    <automated>cd backend && source venv/bin/activate && pip install -r requirements.txt && python -c "from PyPDF2 import PdfReader; from docx import Document; print('OK')"</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c "PyPDF2" backend/requirements.txt` returns `1`
    - `grep -c "python-docx" backend/requirements.txt` returns `1` (no duplication)
    - The PyPDF2 line appears AFTER the python-docx line: `awk '/PyPDF2/{p=NR} /python-docx/{d=NR} END{exit (d<p)?0:1}' backend/requirements.txt` exits 0
    - `cd backend && source venv/bin/activate && python -c "from PyPDF2 import PdfReader; print('OK')"` prints `OK` after `pip install -r requirements.txt`
    - `cd backend && source venv/bin/activate && python -c "from app.main import app; print('OK')"` still imports cleanly (no transitive dep break)
  </acceptance_criteria>
  <done>PyPDF2 in backend runtime, importable in FastAPI venv, no transitive break.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: Pinned-version assertion test + backend runtime parity for BOTH python-docx AND PyPDF2 (REVIEW #12)</name>
  <files>backend/tests/sandbox/test_dockerfile_deps.py</files>
  <read_first>
    - backend/sandbox/Dockerfile (post-Task-1 state)
    - backend/Dockerfile (Railway production image)
    - backend/requirements.txt (post-Task-2 state)
    - backend/tests/services/test_gatekeeper.py (analog for pytest module shape)
    - .planning/phases/22-contract-review-harness-docx-deliverable/22-REVIEWS.md (review finding #12: parity test must guard PyPDF2 too, not only python-docx)
  </read_first>
  <behavior>
    - Test 1: `test_sandbox_dockerfile_pins_python_docx_1_1_2` — sandbox Dockerfile contains `python-docx==1.1.2` exactly once.
    - Test 2: `test_sandbox_dockerfile_pins_pypdf2_3_0_1` — sandbox Dockerfile contains `PyPDF2==3.0.1` exactly once.
    - Test 3: `test_sandbox_dockerfile_install_layer_before_chmod` — RUN pip install line index < RUN chmod 777 line index.
    - Test 4: `test_backend_runtime_has_python_docx` — REVIEW #12 — `python-docx` is present in `backend/requirements.txt` (line check, version-floor agnostic).
    - Test 5 (NEW per REVIEW #5 + #12): `test_backend_runtime_has_pypdf2` — `PyPDF2` is present in `backend/requirements.txt`. CR-01 PDF intake runs in FastAPI process; sandbox-only install would crash PDF uploads. Failing this test signals plan 22-01 Task 2 was skipped.
    - Test 6 (NEW per REVIEW #12): `test_backend_dockerfile_parity` — if backend/Dockerfile exists and uses pip install, both python-docx AND PyPDF2 must reach the runtime image (either via Dockerfile RUN or via `pip install -r requirements.txt`).
  </behavior>
  <action>
    Create `backend/tests/sandbox/test_dockerfile_deps.py` with the six assertions described above.

    Header (mirror `test_gatekeeper.py:1-19` shape):
    ```python
    """Phase 22 / Plan 22-01 — Dependency parity tests for python-docx + PyPDF2.

    Six tests:
    1. test_sandbox_dockerfile_pins_python_docx_1_1_2  — sandbox image pin (DOCX-01)
    2. test_sandbox_dockerfile_pins_pypdf2_3_0_1       — sandbox image pin (REVIEW #12)
    3. test_sandbox_dockerfile_install_layer_before_chmod — Docker layer ordering
    4. test_backend_runtime_has_python_docx            — backend runtime parity
    5. test_backend_runtime_has_pypdf2                 — REVIEW #5 + #12: CR-01 runs in FastAPI process
    6. test_backend_dockerfile_parity                  — Railway image inherits from requirements.txt

    Why this matters (REVIEW #5 anchor): CR-01 PDF intake runs in the FastAPI process via
    `PyPDF2.PdfReader`, NOT inside the sandbox. A sandbox-only install would still crash the
    PDF upload path. Both images must carry the dep.
    """
    from __future__ import annotations
    import pathlib
    ```

    Concrete test 5 body (REVIEW #5 + #12):
    ```python
    def test_backend_runtime_has_pypdf2():
        """REVIEW #5: CR-01 PDF intake runs in the FastAPI process; PyPDF2 must be in
        backend/requirements.txt (not just the sandbox image).

        REVIEW #12: prior version of this test only guarded python-docx, letting the
        PDF gap slip through.
        """
        backend_root = pathlib.Path(__file__).parents[2]
        req = (backend_root / "requirements.txt").read_text()
        assert "PyPDF2" in req, (
            "PyPDF2 missing from backend/requirements.txt. CR-01 PDF intake runs in the "
            "FastAPI process, not the sandbox — a sandbox-only install crashes PDF uploads. "
            "See review finding #5 in 22-REVIEWS.md."
        )
    ```

    Concrete test 6 body (REVIEW #12 — backend Dockerfile parity):
    ```python
    def test_backend_dockerfile_parity():
        """If a backend Dockerfile exists, it must inherit both deps via requirements.txt.

        We do not require the Dockerfile to RUN pip install python-docx PyPDF2 directly —
        `pip install -r requirements.txt` is the canonical path. Test 4 + Test 5 already
        guard the requirements.txt content, so this test only verifies the Dockerfile
        DOES include `pip install -r requirements.txt` (or equivalent).
        """
        backend_root = pathlib.Path(__file__).parents[2]
        dockerfile_path = backend_root / "Dockerfile"
        if not dockerfile_path.exists():
            return  # no backend Dockerfile in this checkout — N/A
        text = dockerfile_path.read_text()
        # Must use requirements.txt as the source of truth (not bare RUN pip installs)
        assert "requirements.txt" in text, (
            "backend/Dockerfile must `pip install -r requirements.txt` so it picks up "
            "the python-docx + PyPDF2 entries guarded by tests 4 + 5."
        )
    ```

    Use `pathlib.Path(__file__).parents[2]` to reach `backend/` from `backend/tests/sandbox/test_dockerfile_deps.py` (2 parents up).
  </action>
  <verify>
    <automated>cd backend && source venv/bin/activate && pytest tests/sandbox/test_dockerfile_deps.py -v --tb=short</automated>
  </verify>
  <acceptance_criteria>
    - `pytest backend/tests/sandbox/test_dockerfile_deps.py -v` exits 0 with 6 tests passing
    - `grep -c "python-docx==1.1.2" backend/tests/sandbox/test_dockerfile_deps.py` returns `1`
    - `grep -c "PyPDF2==3.0.1" backend/tests/sandbox/test_dockerfile_deps.py` returns `1`
    - `grep -c "test_backend_runtime_has_pypdf2" backend/tests/sandbox/test_dockerfile_deps.py` returns `1` (REVIEW #5 + #12 anchor)
    - `grep -c "REVIEW #5\|REVIEW #12" backend/tests/sandbox/test_dockerfile_deps.py` returns `>= 2` (traceability annotations)
    - File contains `from __future__ import annotations`
  </acceptance_criteria>
  <done>Six tests pass, BOTH dependencies guarded on BOTH images, REVIEW #5 + #12 closed.</done>
</task>

</tasks>

<truths>
- D-22-12 (pure programmatic python-docx generation, no template file) — sandbox needs the library.
- DOCX-01 dependency on `python-docx` (sandbox) + CR-01 PDF intake dep on `PyPDF2` (backend runtime).
- D-16 OFF-mode invariant: extra deps do NOT change behavior when CONTRACT_REVIEW_ENABLED=False (deps simply unused).
- REVIEW #5: prior plan installed PyPDF2 only in sandbox; CR-01 runs in FastAPI process. Without backend-side install, PDF uploads crash with `ModuleNotFoundError: PyPDF2`.
- REVIEW #12: prior parity test only guarded python-docx; the PyPDF2 gap slipped through. Test 5 + 6 explicitly close this.
</truths>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Docker image build | external (PyPI) → sandbox image; pinned versions limit supply-chain drift |
| Backend pip install | external (PyPI) → backend venv; floor versions |
| Sandbox runtime → host | Already isolated by sandbox container |
| Backend PyPDF2 parsing → FastAPI process | Runs in-process; PyPDF2 historically had CVE issues |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-22-01-01 | Tampering | sandbox Dockerfile dep | mitigate | Exact-version pin (`==1.1.2`, `==3.0.1`) in sandbox Dockerfile |
| T-22-01-02 | Tampering | backend requirements.txt PyPDF2 | mitigate | Floor `>=3.0.1` matches project convention; CI runs full pip install on every push |
| T-22-01-03 | Information Disclosure | python-docx parsing untrusted user contracts in sandbox | accept | Parsing happens INSIDE sandbox container; no PII reaches LLM payloads |
| T-22-01-04 | Denial of Service | malformed PDF parsing in FastAPI process via PyPDF2 | mitigate | UPL-02 25 MB upload cap upstream; PyPDF2 3.0+ has malformed-input hardening; CR-01 wraps in try/except returning error dict (D-22-15-style) |
| T-22-01-05 | Denial of Service | malformed DOCX crashing sandbox | accept | Sandbox enforces timeout via service config |
</threat_model>

<verification>
1. `docker build -t lexcore-sandbox:phase22-test backend/sandbox/` succeeds (REQUIRES Docker daemon)
2. `docker run --rm lexcore-sandbox:phase22-test python -c "from docx import Document; from PyPDF2 import PdfReader; print('OK')"` prints `OK`
3. `pytest backend/tests/sandbox/test_dockerfile_deps.py -v` exits 0 with 6 tests (text-only assertions, no Docker required)
4. `cd backend && source venv/bin/activate && pip install -r requirements.txt && python -c "from PyPDF2 import PdfReader; from docx import Document; from app.main import app; print('OK')"` prints `OK`

**ISSUE-18 — Docker requirement in CI:** Steps 1-2 require Docker. If Docker is unavailable, step 3 (pure-text pytest) is the SUFFICIENT primary gate.
</verification>

<success_criteria>
- Sandbox image rebuilds cleanly with pinned deps
- Backend venv has PyPDF2 importable (closes REVIEW #5 PDF intake gap)
- Six-test parity guard catches future drift on EITHER image
- No transitive break in `from app.main import app`
</success_criteria>

<output>
After completion, create `.planning/phases/22-contract-review-harness-docx-deliverable/22-01-SUMMARY.md`.
</output>
