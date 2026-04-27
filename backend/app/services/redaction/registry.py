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

import asyncio
import logging
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

from app.database import get_supabase_client

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
        self._forbidden_tokens_cache: set[str] | None = None

    @classmethod
    async def load(cls, thread_id: str) -> "ConversationRegistry":
        """Lazy-load the registry for a thread on the first redact call of a turn (D-33).

        One SELECT against `public.entity_registry`. Service-role client per D-25
        (RLS is enabled with no policies — only the service role can read).

        Returns an empty registry (rows=[]) for a brand-new thread; this is
        REG-01-compliant behaviour, not an error.

        The supabase-py client is sync; we wrap in `asyncio.to_thread` because
        `redact_text` (Plan 05) calls this from inside the per-thread asyncio.Lock
        critical section. Blocking the event loop while holding the lock would
        starve other coroutines.
        """
        client = get_supabase_client()

        def _select() -> list[dict]:
            res = (
                client.table("entity_registry")
                .select(
                    "real_value,real_value_lower,surrogate_value,entity_type,source_message_id"
                )
                .eq("thread_id", thread_id)
                .execute()
            )
            return list(res.data or [])

        raw_rows = await asyncio.to_thread(_select)
        rows: list[EntityMapping] = [EntityMapping(**r) for r in raw_rows]

        logger.debug(
            "registry.load: thread_id=%s rows=%d",
            thread_id,
            len(rows),
        )
        return cls(thread_id=thread_id, rows=rows)

    @property
    def thread_id(self) -> str:
        """Read-only thread_id this registry is bound to."""
        return self._thread_id

    def contains_lower(self, real_value_lower: str) -> bool:
        """O(1) check: is a casefold'd real value already in the registry?"""
        return real_value_lower in self._by_lower

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
        if self._forbidden_tokens_cache is not None:
            return self._forbidden_tokens_cache
        person_reals = [m.real_value for m in self._rows if m.entity_type == "PERSON"]
        bare_names = [strip_honorific(name)[1] for name in person_reals]
        self._forbidden_tokens_cache = extract_name_tokens(bare_names)
        return self._forbidden_tokens_cache

    async def upsert_delta(self, deltas: list[EntityMapping]) -> None:
        """Persist newly-introduced mappings to the entity_registry table (D-32).

        Called from inside the asyncio.Lock critical section in
        `redaction_service.redact_text(text, registry)` (Plan 05). Empty list
        = no-op (zero DB hops). Successful inserts also update the in-memory
        state so subsequent `lookup()` calls in this turn see the new entries
        without re-querying the DB.

        Uses INSERT ... ON CONFLICT (thread_id, real_value_lower) DO NOTHING
        — the composite UNIQUE constraint (D-23) is the cross-process
        serialisation safety net; even if two workers race past asyncio.Lock,
        only one row lands.

        Raises any DB error (REG-04 invariant: a lost write would silently
        violate "same real → same surrogate"). Phase 1 audit_service is
        fire-and-forget; registry writes are NOT.
        """
        if not deltas:
            return  # zero-DB-hop fast path

        client = get_supabase_client()
        rows = [
            {
                "thread_id": self._thread_id,
                "real_value": m.real_value,
                "real_value_lower": m.real_value_lower,
                "surrogate_value": m.surrogate_value,
                "entity_type": m.entity_type,
                "source_message_id": m.source_message_id,
            }
            for m in deltas
        ]

        def _upsert() -> None:
            (
                client.table("entity_registry")
                .upsert(
                    rows,
                    on_conflict="thread_id,real_value_lower",
                    ignore_duplicates=True,
                )
                .execute()
            )

        try:
            await asyncio.to_thread(_upsert)
        except Exception as e:
            logger.error(
                "registry.upsert_delta failed: thread_id=%s deltas=%d error_type=%s",
                self._thread_id,
                len(deltas),
                type(e).__name__,
            )
            raise

        # First-write-wins: matches ON CONFLICT DO NOTHING semantics. Don't
        # overwrite existing in-memory entries even if the caller passed a
        # delta whose real_value_lower somehow already exists (shouldn't
        # happen — the caller diffs against registry first — but be safe).
        added_person = False
        for m in deltas:
            if m.real_value_lower not in self._by_lower:
                self._rows.append(m)
                self._by_lower[m.real_value_lower] = m
                if m.entity_type == "PERSON":
                    added_person = True
        if added_person:
            self._forbidden_tokens_cache = None

        logger.debug(
            "registry.upsert_delta: thread_id=%s wrote=%d size_after=%d",
            self._thread_id,
            len(deltas),
            len(self._rows),
        )

    def __repr__(self) -> str:  # pragma: no cover — debug aid only; never logs real values
        # B4 / D-18 / D-41: counts only, never real values.
        return f"ConversationRegistry(thread_id={self._thread_id!r}, size={len(self._rows)})"
