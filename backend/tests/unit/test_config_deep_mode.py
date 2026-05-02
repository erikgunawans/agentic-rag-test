"""
Unit tests for Phase 17 / v1.3 Deep Mode Settings fields.

Tests:
- Default values: max_deep_rounds=50, max_tool_rounds=25, max_sub_agent_rounds=15, deep_mode_enabled=False
- Env override: MAX_DEEP_ROUNDS, DEEP_MODE_ENABLED, MAX_TOOL_ROUNDS, MAX_SUB_AGENT_ROUNDS
- Deprecated alias: TOOLS_MAX_ITERATIONS -> max_tool_rounds (with DeprecationWarning)
- Precedence: MAX_TOOL_ROUNDS takes precedence over TOOLS_MAX_ITERATIONS

References: CONF-01..03, DEEP-02, D-14, D-15, D-16
"""

import warnings
import pytest
from app.config import get_settings


@pytest.fixture(autouse=True)
def clear_settings_cache():
    """Clear lru_cache on get_settings before and after each test."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_default_max_deep_rounds_50(monkeypatch):
    """CONF-01: max_deep_rounds defaults to 50 when env is empty."""
    monkeypatch.delenv("MAX_DEEP_ROUNDS", raising=False)
    monkeypatch.delenv("MAX_TOOL_ROUNDS", raising=False)
    monkeypatch.delenv("MAX_SUB_AGENT_ROUNDS", raising=False)
    monkeypatch.delenv("DEEP_MODE_ENABLED", raising=False)
    monkeypatch.delenv("TOOLS_MAX_ITERATIONS", raising=False)
    s = get_settings()
    assert s.max_deep_rounds == 50


def test_default_max_tool_rounds_25(monkeypatch):
    """CONF-02: max_tool_rounds defaults to 25 when env is empty."""
    monkeypatch.delenv("MAX_TOOL_ROUNDS", raising=False)
    monkeypatch.delenv("MAX_DEEP_ROUNDS", raising=False)
    monkeypatch.delenv("MAX_SUB_AGENT_ROUNDS", raising=False)
    monkeypatch.delenv("DEEP_MODE_ENABLED", raising=False)
    monkeypatch.delenv("TOOLS_MAX_ITERATIONS", raising=False)
    s = get_settings()
    assert s.max_tool_rounds == 25


def test_default_max_sub_agent_rounds_15(monkeypatch):
    """CONF-03: max_sub_agent_rounds defaults to 15 when env is empty."""
    monkeypatch.delenv("MAX_SUB_AGENT_ROUNDS", raising=False)
    monkeypatch.delenv("MAX_DEEP_ROUNDS", raising=False)
    monkeypatch.delenv("MAX_TOOL_ROUNDS", raising=False)
    monkeypatch.delenv("DEEP_MODE_ENABLED", raising=False)
    monkeypatch.delenv("TOOLS_MAX_ITERATIONS", raising=False)
    s = get_settings()
    assert s.max_sub_agent_rounds == 15


def test_default_deep_mode_enabled_false(monkeypatch):
    """D-16: deep_mode_enabled defaults to False for dark-launch."""
    monkeypatch.delenv("DEEP_MODE_ENABLED", raising=False)
    monkeypatch.delenv("MAX_DEEP_ROUNDS", raising=False)
    monkeypatch.delenv("MAX_TOOL_ROUNDS", raising=False)
    monkeypatch.delenv("MAX_SUB_AGENT_ROUNDS", raising=False)
    monkeypatch.delenv("TOOLS_MAX_ITERATIONS", raising=False)
    s = get_settings()
    assert s.deep_mode_enabled is False


def test_env_override_max_deep_rounds(monkeypatch):
    """CONF-01: MAX_DEEP_ROUNDS env var overrides default."""
    monkeypatch.setenv("MAX_DEEP_ROUNDS", "10")
    monkeypatch.delenv("MAX_TOOL_ROUNDS", raising=False)
    monkeypatch.delenv("MAX_SUB_AGENT_ROUNDS", raising=False)
    monkeypatch.delenv("DEEP_MODE_ENABLED", raising=False)
    monkeypatch.delenv("TOOLS_MAX_ITERATIONS", raising=False)
    s = get_settings()
    assert s.max_deep_rounds == 10


def test_env_override_deep_mode_enabled(monkeypatch):
    """D-16: DEEP_MODE_ENABLED=true flips flag on."""
    monkeypatch.setenv("DEEP_MODE_ENABLED", "true")
    monkeypatch.delenv("MAX_DEEP_ROUNDS", raising=False)
    monkeypatch.delenv("MAX_TOOL_ROUNDS", raising=False)
    monkeypatch.delenv("MAX_SUB_AGENT_ROUNDS", raising=False)
    monkeypatch.delenv("TOOLS_MAX_ITERATIONS", raising=False)
    s = get_settings()
    assert s.deep_mode_enabled is True


def test_legacy_tools_max_iterations_alias(monkeypatch):
    """D-15: TOOLS_MAX_ITERATIONS alone (no MAX_TOOL_ROUNDS) sets max_tool_rounds + emits DeprecationWarning."""
    monkeypatch.setenv("TOOLS_MAX_ITERATIONS", "7")
    monkeypatch.delenv("MAX_TOOL_ROUNDS", raising=False)
    monkeypatch.delenv("MAX_DEEP_ROUNDS", raising=False)
    monkeypatch.delenv("MAX_SUB_AGENT_ROUNDS", raising=False)
    monkeypatch.delenv("DEEP_MODE_ENABLED", raising=False)

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        s = get_settings()

    assert s.max_tool_rounds == 7

    deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
    assert len(deprecation_warnings) >= 1
    assert "TOOLS_MAX_ITERATIONS" in str(deprecation_warnings[0].message)


def test_max_tool_rounds_takes_precedence(monkeypatch):
    """D-15: When both MAX_TOOL_ROUNDS and TOOLS_MAX_ITERATIONS are set, MAX_TOOL_ROUNDS wins (no warning)."""
    monkeypatch.setenv("MAX_TOOL_ROUNDS", "30")
    monkeypatch.setenv("TOOLS_MAX_ITERATIONS", "7")
    monkeypatch.delenv("MAX_DEEP_ROUNDS", raising=False)
    monkeypatch.delenv("MAX_SUB_AGENT_ROUNDS", raising=False)
    monkeypatch.delenv("DEEP_MODE_ENABLED", raising=False)

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        s = get_settings()

    assert s.max_tool_rounds == 30

    deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)
                            and "TOOLS_MAX_ITERATIONS" in str(x.message)]
    assert len(deprecation_warnings) == 0
