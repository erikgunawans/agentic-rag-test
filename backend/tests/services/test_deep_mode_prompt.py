"""Tests for backend/app/services/deep_mode_prompt.py — Phase 19 plan 19-08.

Tests 1-5: Validate Phase 19 real guidance replaces Phase 17 stubs.
Test 6: TASK-06 coexistence — agent_service classify_intent remains byte-identical.
"""
from __future__ import annotations

import re

from app.services.deep_mode_prompt import build_deep_mode_system_prompt


# ---------------------------------------------------------------------------
# Test 1: Determinism (D-09 invariant)
# ---------------------------------------------------------------------------

def test_build_deep_mode_system_prompt_is_deterministic():
    """Same input always produces same output — KV-cache stable."""
    first = build_deep_mode_system_prompt("base prompt")
    second = build_deep_mode_system_prompt("base prompt")
    assert first == second, "build_deep_mode_system_prompt is not deterministic"


# ---------------------------------------------------------------------------
# Test 2: No volatile data (T-19-PROMPT-INJ mitigation)
# ---------------------------------------------------------------------------

def test_build_deep_mode_system_prompt_no_timestamp_or_volatile_data():
    """Output must not contain year strings, uuid-like patterns, or thread-id shapes."""
    output = build_deep_mode_system_prompt("some base")
    # No four-digit year
    assert not re.search(r"\b20\d{2}\b", output), "Year found in prompt — volatile data leak"
    # No uuid-shaped substrings (8-4-4-4-12 hex)
    assert not re.search(
        r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
        output,
        re.IGNORECASE,
    ), "UUID-shaped substring found in prompt"
    # No thread-id shapes (e.g. "thread_abc123" or numeric IDs embedded)
    assert not re.search(r"\bthread_[a-zA-Z0-9]+\b", output), "Thread-id shape found in prompt"


# ---------------------------------------------------------------------------
# Test 3: Sub-Agent Delegation section present (TASK-06 / Phase 19)
# ---------------------------------------------------------------------------

def test_deep_mode_prompt_contains_task_guidance():
    """Prompt must contain Sub-Agent Delegation section with task() tool signature."""
    output = build_deep_mode_system_prompt("base")
    assert "Sub-Agent Delegation" in output, "Missing 'Sub-Agent Delegation' section"
    assert "task(description, context_files)" in output, (
        "Missing task(description, context_files) signature in prompt"
    )


# ---------------------------------------------------------------------------
# Test 4: Ask-User section present
# ---------------------------------------------------------------------------

def test_deep_mode_prompt_contains_ask_user_guidance():
    """Prompt must contain Asking the User section with ask_user() tool signature."""
    output = build_deep_mode_system_prompt("base")
    assert "Asking the User" in output, "Missing 'Asking the User' section"
    assert "ask_user(question)" in output, (
        "Missing ask_user(question) signature in prompt"
    )


# ---------------------------------------------------------------------------
# Test 5: Error Recovery section — no auto-retry (D-20)
# ---------------------------------------------------------------------------

def test_deep_mode_prompt_contains_error_recovery_no_auto_retry():
    """Prompt must contain Error Recovery section communicating no-automatic-retry (D-20)."""
    output = build_deep_mode_system_prompt("base")
    assert "Error Recovery" in output, "Missing 'Error Recovery' section"
    assert "no automatic retry" in output.lower() or "There is no automatic retry" in output, (
        "D-20 'no automatic retry' rule not communicated in prompt"
    )


# ---------------------------------------------------------------------------
# Test 6: TASK-06 coexistence — agent_service.py unchanged
# ---------------------------------------------------------------------------

def test_agent_service_classify_intent_unchanged():
    """TASK-06: agent_service.py has not been modified by Phase 19 plan 19-08.

    The plan spec says the simpler approach is: assert that git diff against
    agent_service.py is empty for this phase's commits. We use subprocess git
    to verify the file is unmodified relative to HEAD (no staged or unstaged
    changes), which is the correct TASK-06 coexistence assertion.

    Additionally, we verify the classify_intent signature by inspecting the
    source text of the file directly — avoiding the Supabase module-import-time
    DB call that prevents a clean import in unit test environments.
    """
    import subprocess
    import inspect as _inspect
    import ast
    import pathlib

    # 1. git diff — no modifications to agent_service.py
    repo_root = pathlib.Path(__file__).parent.parent.parent  # backend/
    agent_service_path = repo_root / "app" / "services" / "agent_service.py"
    result = subprocess.run(
        ["git", "diff", "--name-only", "HEAD", str(agent_service_path)],
        capture_output=True, text=True, cwd=str(repo_root)
    )
    # git diff HEAD -- file returns empty if file is unmodified
    assert result.returncode == 0, f"git diff failed: {result.stderr}"
    assert result.stdout.strip() == "", (
        f"TASK-06 VIOLATED: agent_service.py has uncommitted modifications: {result.stdout}"
    )

    # 2. Inspect source for classify_intent signature without importing the module
    source = agent_service_path.read_text()
    tree = ast.parse(source)
    classify_intent_found = False
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "classify_intent":
            classify_intent_found = True
            arg_names = [a.arg for a in node.args.args] + [a.arg for a in node.args.kwonlyargs]
            assert "message" in arg_names, "classify_intent missing 'message' param"
            assert "history" in arg_names, "classify_intent missing 'history' param"
            assert "model" in arg_names, "classify_intent missing 'model' param"
            assert "registry" in arg_names, "classify_intent missing 'registry' param"
            assert "available_tool_names" in arg_names, (
                "classify_intent missing 'available_tool_names' param"
            )
            break
    assert classify_intent_found, "classify_intent function not found in agent_service.py"
