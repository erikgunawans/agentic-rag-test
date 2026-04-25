"""Shared pytest fixtures for the LexCore backend test suite.

Phase 1 (milestone v1.0) adds:
- `seeded_faker`: per-test Faker seed for reproducible surrogate generation
  (D-20: production never sets a seed).
- `redaction_service`: session-scoped to verify @lru_cache singleton behaviour
  (PERF-01 / SC#5).
"""

from __future__ import annotations

import pytest


@pytest.fixture
def seeded_faker():
    """Per-test deterministic seed for the redaction Faker (D-20).

    Returns the seeded Faker instance. Tests that compare exact surrogate
    values request this fixture; tests that only check structural properties
    (gender, presence/absence of tokens) can skip it.
    """
    from app.services.redaction.anonymization import get_faker

    faker = get_faker()
    faker.seed_instance(42)  # arbitrary fixed seed
    yield faker
    # No teardown - the next test that requests seeded_faker re-seeds.


@pytest.fixture(scope="session")
def redaction_service():
    """Session-scoped RedactionService.

    The fixture is session-scoped because get_redaction_service() is itself
    @lru_cache'd; using the same instance across all tests verifies the
    singleton stays intact (PERF-01 / SC#5).
    """
    from app.services.redaction_service import get_redaction_service

    return get_redaction_service()
