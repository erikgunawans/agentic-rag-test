"""Regression test for CR-21-01 (Phase 21 UAT finding).

Reproduces the production startup import order that caused the circular import:

    chat router → harness_registry → app.harnesses.types
       → triggers app.harnesses/__init__.py auto-import
          → smoke_echo imports `register` from harness_registry
             → ImportError: harness_registry is partially initialized

When this bug is present, smoke-echo is silently absent from the registry at
runtime (logged at WARN level but not visible to callers), and the gatekeeper
branch in chat.py never fires because `harness_registry.list_harnesses()`
returns an empty list.

The test runs in a fresh subprocess to guarantee a clean module cache (pytest's
own session has app.harnesses pre-loaded by other tests, which masks the bug).
"""
from __future__ import annotations

import os
import subprocess
import sys
import textwrap


def test_smoke_echo_registers_via_production_import_order() -> None:
    """In a fresh interpreter, importing in production order must register smoke-echo."""
    # Production order = chat router imports harness_registry FIRST, then later
    # imports harness_engine which is the first thing to do `from app.harnesses.types`.
    probe = textwrap.dedent(
        """
        import os, sys
        os.environ["HARNESS_ENABLED"] = "true"
        os.environ["HARNESS_SMOKE_ENABLED"] = "true"

        # Clear any cached lru_cache on get_settings — must come BEFORE the imports.
        from app.config import get_settings
        get_settings.cache_clear()

        # Step 1: import harness_registry (matches chat.py:41 order).
        # Bug repro: this transitively triggers app.harnesses/__init__.py to run
        # while harness_registry is still partially initialized.
        from app.services import harness_registry

        # Step 2: import harness_engine (matches chat.py:46). This is the first
        # call site in chat.py to do `from app.harnesses.types`. With the bug it
        # was a no-op (smoke_echo already failed to import); with the fix it
        # triggers app.harnesses/__init__ which auto-imports smoke_echo cleanly.
        from app.services import harness_engine  # noqa: F401

        names = sorted(h.name for h in harness_registry.list_harnesses())
        print("REGISTERED:", ",".join(names))
        """
    )
    env = {**os.environ, "HARNESS_ENABLED": "true", "HARNESS_SMOKE_ENABLED": "true"}
    result = subprocess.run(
        [sys.executable, "-c", probe],
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )
    assert result.returncode == 0, (
        f"subprocess failed:\nstdout={result.stdout}\nstderr={result.stderr}"
    )
    # Parse the REGISTERED: line; ignore Pydantic warnings etc. that may appear above.
    line = next(
        (l for l in result.stdout.splitlines() if l.startswith("REGISTERED:")),
        None,
    )
    assert line is not None, f"no REGISTERED line in stdout:\n{result.stdout}"
    registered = line[len("REGISTERED:"):].strip().split(",") if line[len("REGISTERED:"):].strip() else []
    assert "smoke-echo" in registered, (
        "CR-21-01 regression: smoke-echo not registered in production import order. "
        f"Got registered={registered}.\n"
        f"stderr (look for ImportError on app.services.harness_registry):\n{result.stderr}"
    )
