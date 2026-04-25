"""Conversation-scoped real↔surrogate registry (Phase 2).

Per-thread in-memory wrapper backed by the `entity_registry` Postgres table
(migration 029). The registry guarantees that within a thread, the same real
entity always maps to the same surrogate (REG-04 / FR-3.4) and that mappings
survive a backend restart (REG-02 / FR-3.2).

Lifecycle (D-33):
    1. Chat router calls `await ConversationRegistry.load(thread_id)` once per
       chat turn — issues a single SELECT to populate the in-memory dict.
    2. The instance is passed into every `redact_text(...)` call within that
       turn.
    3. The instance is discarded after the assistant response is committed.

D-31 (FUTURE-WORK Phase 6): the asyncio.Lock-keyed-by-thread_id strategy that
serialises concurrent writers (`redaction_service._thread_locks`) is correct
ONLY while Railway runs a single Uvicorn worker. Under multi-worker or
horizontally-scaled deploys, replace it with `pg_advisory_xact_lock(hashtext(
thread_id))`. The composite UNIQUE constraint `(thread_id, real_value_lower)`
on the table is the cross-process safety net until that upgrade lands.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

# IMPORTANT: strip_honorific lives in honorifics.py, NOT name_extraction.py.
# Phase 1's anonymization.py uses the SAME two-line split (L47 + L48). If you
# accidentally write a single-line import from name_extraction containing
# strip_honorific, Python will raise ImportError at module import time —
# confirm the import comes from honorifics.py before retrying (B-3 diagnostic).
from app.services.redaction.honorifics import strip_honorific
from app.services.redaction.name_extraction import extract_name_tokens

if TYPE_CHECKING:  # avoid runtime cycle if any caller threads this through
    pass

logger = logging.getLogger(__name__)


class EntityMapping(BaseModel):
    """In-memory + row-creation payload for the entity_registry table (D-28).

    Field shapes match migration 029 columns exactly. `real_value_lower` is
    `str.casefold()`'d at construction time (Unicode-correct; D-36).
    `source_message_id` is nullable because `redact_text` runs BEFORE the
    user-message row is committed; the chat router (Phase 5) backfills it.
    """

    model_config = ConfigDict(frozen=True)

    real_value: str
    real_value_lower: str
    surrogate_value: str
    entity_type: str  # PERSON / EMAIL_ADDRESS / PHONE_NUMBER / LOCATION / DATE_TIME / URL / IP_ADDRESS
    source_message_id: str | None = None


class ConversationRegistry:
    """Per-thread in-memory wrapper over `entity_registry` rows (D-27).

    NOT a singleton (D-33: per-turn lifecycle). Do NOT decorate with
    @lru_cache. Constructed by `ConversationRegistry.load(thread_id)`
    (added in Plan 04 once the table is pushed); tests may construct
    directly with `ConversationRegistry(thread_id=..., rows=[...])`
    for unit-mode coverage.
    """

    def __init__(self, thread_id: str, rows: list[EntityMapping] | None = None) -> None:
        self._thread_id: str = thread_id
        self._rows: list[EntityMapping] = list(rows or [])
        # Casefold-keyed dict for O(1) case-insensitive lookup (REG-03 / D-36).
        self._by_lower: dict[str, EntityMapping] = {
            m.real_value_lower: m for m in self._rows
        }

    @property
    def thread_id(self) -> str:
        """Read-only thread_id this registry is bound to."""
        return self._thread_id

    def lookup(self, real_value: str) -> str | None:
        """Case-insensitive lookup of an existing surrogate.

        Returns the existing `surrogate_value` if `real_value` (after
        `str.casefold()`) is already in the registry, else None. This is the
        hot path for "same real → same surrogate within thread" (REG-04 /
        FR-3.4); O(1) dict lookup.
        """
        hit = self._by_lower.get(real_value.casefold())
        return hit.surrogate_value if hit is not None else None

    def entries(self) -> list[EntityMapping]:
        """Read-only iteration of all registry entries.

        Used by `de_anonymize_text` (Phase 2 Plan 05) and by callers
        diffing the registry against new entity_map rows to compute deltas.
        Returns a NEW list each call so callers cannot mutate internal state.
        """
        return list(self._rows)

    def forbidden_tokens(self) -> set[str]:
        """Per-PERSON thread-wide forbidden-token set (D-37 / D-38).

        Returns the union of first-name + surname tokens of every PERSON
        entry currently in the registry. Phase 1 D-07's per-call check
        is expanded with this set so Faker never generates a surrogate
        whose tokens collide with a real PERSON name already mapped in
        this thread (PRD §7.5 cross-turn corruption case).

        D-38: PERSON-only. Email / phone / URL collisions are negligible
        and the cost of building a thread-wide forbidden set across all
        types is wasted.
        """
        person_reals = [m.real_value for m in self._rows if m.entity_type == "PERSON"]
        # Strip honorifics first — same as Phase 1 anonymization.py (L47 honorifics
        # import + the call site near L262) so e.g. "Pak" doesn't accidentally
        # land in the forbidden set.
        bare_names = [strip_honorific(name)[1] for name in person_reals]
        return extract_name_tokens(bare_names)

    def __repr__(self) -> str:  # pragma: no cover — debug aid only; never logs real values
        # B4 / D-18 / D-41: counts only, never real values.
        return f"ConversationRegistry(thread_id={self._thread_id!r}, size={len(self._rows)})"
