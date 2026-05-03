"""Phase 20 / v1.3 — Tests for harness_registry.py.

Tests:
1. test_register_adds_to_registry
2. test_register_duplicate_first_write_wins
3. test_get_harness_unknown_returns_none
4. test_list_harnesses_returns_all_registered
5. test_reset_for_tests_clears_registry
"""
import logging

import pytest

from app.harnesses.types import HarnessDefinition, HarnessPrerequisites
from app.services.harness_registry import (
    _reset_for_tests,
    get_harness,
    list_harnesses,
    register,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_def(name: str = "test-harness") -> HarnessDefinition:
    return HarnessDefinition(
        name=name,
        display_name=name.title(),
        prerequisites=HarnessPrerequisites(harness_intro="test"),
        phases=[],
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clear_registry():
    """Ensure the module-level registry is empty before and after every test."""
    _reset_for_tests()
    yield
    _reset_for_tests()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_register_adds_to_registry():
    """register(definition) makes get_harness(name) return it."""
    defn = _make_def("my-harness")
    register(defn)
    result = get_harness("my-harness")
    assert result is defn


def test_register_duplicate_first_write_wins(caplog):
    """Registering the same name twice keeps the first; second logs WARNING."""
    first = _make_def("dup-harness")
    second = HarnessDefinition(
        name="dup-harness",
        display_name="Different",
        prerequisites=HarnessPrerequisites(harness_intro="other"),
        phases=[],
    )

    register(first)
    with caplog.at_level(logging.WARNING):
        register(second)

    # First-write-wins: original definition is preserved
    assert get_harness("dup-harness") is first
    # A warning was logged
    assert any("duplicate name=dup-harness" in r.message for r in caplog.records)


def test_get_harness_unknown_returns_none():
    """get_harness on an unregistered name returns None."""
    result = get_harness("does-not-exist")
    assert result is None


def test_list_harnesses_returns_all_registered():
    """list_harnesses() returns all registered definitions."""
    d1 = _make_def("alpha")
    d2 = _make_def("beta")
    register(d1)
    register(d2)
    result = list_harnesses()
    names = {h.name for h in result}
    assert names == {"alpha", "beta"}
    assert len(result) == 2


def test_reset_for_tests_clears_registry():
    """_reset_for_tests() empties the registry."""
    register(_make_def("to-clear"))
    assert len(list_harnesses()) == 1
    _reset_for_tests()
    assert list_harnesses() == []
