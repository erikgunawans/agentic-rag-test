"""Phase 20 / v1.3 — Harness Registry (HARN-08, D-06, D-16).

Module-level dict + register() decorator + lookup helpers.
First-write-wins on duplicate name (logged WARNING). Mirrors tool_registry.py.

The registry is auto-populated at import time by app.harnesses.__init__ which
walks every .py file in app/harnesses/ and imports it; each harness module is
expected to call register(definition) at module scope, often gated behind a
feature flag (e.g. settings.harness_smoke_enabled).
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # Importing app.harnesses.types at runtime would trigger
    # app.harnesses/__init__.py during this module's own load and produce
    # a circular import (smoke_echo → harness_registry → app.harnesses
    # → smoke_echo) — see CR-21-01. PEP 563 string annotations + the
    # `from __future__ import annotations` above let us keep the type
    # hints without the runtime import.
    from app.harnesses.types import HarnessDefinition

logger = logging.getLogger(__name__)

_REGISTRY: dict[str, "HarnessDefinition"] = {}


def register(definition: HarnessDefinition) -> None:
    """Register a harness. Duplicate name → WARNING + ignored (first-write-wins)."""
    if definition.name in _REGISTRY:
        logger.warning(
            "harness_registry: duplicate name=%s — ignored (first-write-wins)",
            definition.name,
        )
        return
    _REGISTRY[definition.name] = definition
    logger.info(
        "harness_registry: registered name=%s phases=%d",
        definition.name,
        len(definition.phases),
    )


def get_harness(name: str) -> HarnessDefinition | None:
    """Return a HarnessDefinition by its registry key, or None if not found."""
    return _REGISTRY.get(name)


def list_harnesses() -> list[HarnessDefinition]:
    """Return all registered harness definitions."""
    return list(_REGISTRY.values())


def _reset_for_tests() -> None:
    """Test-only — clear the in-process registry between tests."""
    _REGISTRY.clear()
