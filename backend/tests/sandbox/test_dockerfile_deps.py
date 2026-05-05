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


# Resolve paths relative to this test file.
# backend/tests/sandbox/test_dockerfile_deps.py -> parents[2] == backend/
_BACKEND_ROOT = pathlib.Path(__file__).parents[2]
_SANDBOX_DOCKERFILE = _BACKEND_ROOT / "sandbox" / "Dockerfile"
_BACKEND_REQUIREMENTS = _BACKEND_ROOT / "requirements.txt"
_BACKEND_DOCKERFILE = _BACKEND_ROOT / "Dockerfile"


def test_sandbox_dockerfile_pins_python_docx_1_1_2():
    """DOCX-01: sandbox image must pin python-docx==1.1.2 exactly once."""
    text = _SANDBOX_DOCKERFILE.read_text()
    count = text.count("python-docx==1.1.2")
    assert count == 1, (
        f"Expected exactly 1 occurrence of 'python-docx==1.1.2' in "
        f"backend/sandbox/Dockerfile, found {count}. "
        "Plan 22-01 Task 1 installs this for DOCX report generation (DOCX-01)."
    )


def test_sandbox_dockerfile_pins_pypdf2_3_0_1():
    """REVIEW #12: sandbox image must pin PyPDF2==3.0.1 exactly once."""
    text = _SANDBOX_DOCKERFILE.read_text()
    count = text.count("PyPDF2==3.0.1")
    assert count == 1, (
        f"Expected exactly 1 occurrence of 'PyPDF2==3.0.1' in "
        f"backend/sandbox/Dockerfile, found {count}. "
        "REVIEW #12: prior parity test only guarded python-docx; PyPDF2 gap slipped through."
    )


def test_sandbox_dockerfile_install_layer_before_chmod():
    """Docker layer ordering: RUN pip install must appear BEFORE RUN chmod 777 /sandbox."""
    lines = _SANDBOX_DOCKERFILE.read_text().splitlines()

    pip_install_idx = None
    chmod_idx = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        if pip_install_idx is None and "pip install" in stripped and "python-docx" in stripped:
            pip_install_idx = i
        if chmod_idx is None and "chmod 777" in stripped and "/sandbox" in stripped:
            chmod_idx = i

    assert pip_install_idx is not None, (
        "Could not find 'RUN pip install ... python-docx' in backend/sandbox/Dockerfile."
    )
    assert chmod_idx is not None, (
        "Could not find 'RUN chmod 777 /sandbox' in backend/sandbox/Dockerfile."
    )
    assert pip_install_idx < chmod_idx, (
        f"pip install layer (line {pip_install_idx + 1}) must come BEFORE "
        f"chmod 777 (line {chmod_idx + 1}). The chmod must run last so the "
        "install does not reset /sandbox permissions."
    )


def test_backend_runtime_has_python_docx():
    """REVIEW #12: python-docx must be present in backend/requirements.txt.

    Line check is version-floor agnostic — guards against accidental removal.
    """
    req = _BACKEND_REQUIREMENTS.read_text()
    assert "python-docx" in req, (
        "python-docx missing from backend/requirements.txt. "
        "This dep was present before Phase 22 (line 12); its removal would break "
        "existing DOCX-related backend functionality."
    )


def test_backend_runtime_has_pypdf2():
    """REVIEW #5: CR-01 PDF intake runs in the FastAPI process; PyPDF2 must be in
    backend/requirements.txt (not just the sandbox image).

    REVIEW #12: prior version of this test only guarded python-docx, letting the
    PDF gap slip through.
    """
    req = _BACKEND_REQUIREMENTS.read_text()
    assert "PyPDF2" in req, (
        "PyPDF2 missing from backend/requirements.txt. CR-01 PDF intake runs in the "
        "FastAPI process, not the sandbox — a sandbox-only install crashes PDF uploads. "
        "See review finding #5 in 22-REVIEWS.md."
    )


def test_backend_dockerfile_parity():
    """If a backend Dockerfile exists, it must inherit both deps via requirements.txt.

    We do not require the Dockerfile to RUN pip install python-docx PyPDF2 directly —
    `pip install -r requirements.txt` is the canonical path. Test 4 + Test 5 already
    guard the requirements.txt content, so this test only verifies the Dockerfile
    DOES include `pip install -r requirements.txt` (or equivalent).
    """
    if not _BACKEND_DOCKERFILE.exists():
        return  # no backend Dockerfile in this checkout — N/A
    text = _BACKEND_DOCKERFILE.read_text()
    # Must use requirements.txt as the source of truth (not bare RUN pip installs)
    assert "requirements.txt" in text, (
        "backend/Dockerfile must `pip install -r requirements.txt` so it picks up "
        "the python-docx + PyPDF2 entries guarded by tests 4 + 5."
    )
