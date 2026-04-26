"""Public RedactionService — composes detection + anonymization (D-13..D-15).

This is the single entry point for the v1.0 PII redaction layer. It glues
together the building blocks shipped across Phases 1-3:

- ``uuid_filter`` (Phase 1) — pre-mask UUIDs so Presidio never touches them.
- ``detection`` (Phase 1) — Presidio + spaCy ``xx_ent_wiki_sm`` two-pass
  threshold filter; returns ``(masked_text, entities, sentinels)``.
- ``clustering`` (Phase 3 Wave 3) — Union-Find PERSON cluster builder +
  D-48 sub-surrogate variant set generator.
- ``llm_provider`` (Phase 3 Wave 4) — provider-aware AsyncOpenAI client with
  pre-flight egress filter for cloud calls (D-53..D-56).
- ``anonymization`` (Phase 1 / Phase 3) — cluster-aware Faker dispatch:
  one surrogate per cluster; non-PERSON spans flow through the per-entity
  Phase 1 path (D-62 / RESOLVE-04).
- ``tracing_service`` (Phase 1) — provides the ``@traced`` decorator.

Design invariants:

- W10: ``redact_text`` calls ``detect_entities`` exactly once and uses the
  returned 3-tuple directly. The UUID-masking helper is NOT called from
  here — it lives inside ``detect_entities``. This file imports only
  ``restore_uuids``.
- D-13: public method is ``async def redact_text(text) -> RedactionResult``.
  Phase 2 widened the signature to accept a registry; Phase 3 dispatches on
  ``settings.entity_resolution_mode`` inside the registry-aware path.
- D-14: Phase 1 stateless path remains stateless — no per-conversation
  registry, no thread parameter, no caching of real values across calls.
- D-15: ``get_redaction_service()`` is ``@lru_cache``'d. The FastAPI lifespan
  calls it once at startup so Presidio + Faker + gender detector are loaded
  before the first chat request (PERF-01).
- D-18 / B4: ``redact_text`` is wrapped in ``@traced(name="redaction.redact_text")``
  for OBS-01. Span attributes are counts and timings only — never real
  entity values.
- D-29 / D-30: per-thread asyncio.Lock spans detect → cluster → LLM-call →
  generate-surrogates → upsert-deltas → return. The Phase 3 LLM call
  happens INSIDE the lock; ``LLMProviderClient`` enforces a
  settings-controlled timeout (default 30 s) so the lock is bounded.
- D-52 / D-54 / NFR-3: ``_EgressBlocked`` and any other exception from the
  cloud-LLM path fall back to algorithmic clusters; never re-raised to the
  chat loop.
- D-62 / RESOLVE-04: only PERSON entities are clustered. EMAIL / PHONE /
  URL / LOCATION / DATE_TIME / IP_ADDRESS / hard-redact spans flow through
  the existing Phase 1 + Phase 2 per-entity path — no clustering, no LLM
  contact.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from functools import lru_cache

from pydantic import BaseModel, ConfigDict

from app.config import get_settings
from app.services.llm_provider import LLMProviderClient
from app.services.redaction.anonymization import (
    anonymize,
    get_faker,
    get_gender_detector,
)
from app.services.redaction.clustering import Cluster, cluster_persons, variants_for
from app.services.redaction.detection import Entity, detect_entities, get_analyzer
from app.services.redaction.egress import _EgressBlocked
from app.services.redaction.registry import ConversationRegistry, EntityMapping

# W10: the UUID pre-mask helper is intentionally NOT imported here. It is
# called exactly once per ``redact_text`` invocation, from inside
# ``detect_entities``, and the resulting sentinel map is threaded back
# through this module via the 3-tuple return. We only need ``restore_uuids``
# to put the original UUIDs back after substitution.
from app.services.redaction.uuid_filter import restore_uuids
from app.services.tracing_service import traced

logger = logging.getLogger(__name__)


# D-29 (PERF-03): per-process asyncio.Lock keyed by thread_id.
# NOTE (D-31, FUTURE-WORK Phase 6): UPGRADE PATH for multi-worker / multi-instance
# Railway deploys is `pg_advisory_xact_lock(hashtext(thread_id))` — see
# `.planning/STATE.md` "Pending Items" → "Async-lock cross-process upgrade".
# asyncio.Lock is correct only while Railway runs a single Uvicorn worker.
# The composite UNIQUE constraint `(thread_id, real_value_lower)` on the
# entity_registry table (migration 029) is the cross-process safety net.
_thread_locks: dict[str, asyncio.Lock] = {}
_thread_locks_master: asyncio.Lock = asyncio.Lock()


class RedactionResult(BaseModel):
    """D-13 public output schema.

    Attributes:
        anonymized_text: Input text with surrogate-bucket entities replaced
            by Faker values and hard-redact-bucket entities replaced by
            literal ``[ENTITY_TYPE]`` placeholders. UUIDs are preserved
            exactly.
        entity_map: Mapping of real value -> surrogate. Contains ONLY
            surrogate-bucket pairs; hard-redacted entities are excluded
            per FR-3.5 / D-08. Phase 2's de-anonymization layer consumes
            this same shape from a persisted registry.
        hard_redacted_count: How many hard-redact placeholders were emitted.
            Useful for observability / SLA dashboards.
        latency_ms: Wall-clock duration of the whole redact call, including
            detection, anonymization, and UUID restoration.

    Frozen: callers must not mutate the result; this guards against
    accidental cross-request leaks if the result is ever cached.
    """

    model_config = ConfigDict(frozen=True)

    anonymized_text: str
    entity_map: dict[str, str]
    hard_redacted_count: int
    latency_ms: float


def _split_person_non_person(
    entities: list[Entity],
) -> tuple[list[Entity], list[Entity]]:
    """D-62 / RESOLVE-04: PERSON entities go through clustering; everything
    else (EMAIL / PHONE / URL / LOCATION / DATE_TIME / IP_ADDRESS / hard-redact)
    flows through the existing Phase 1 + Phase 2 per-entity path.

    Returns ``(person_entities, non_person_entities)``.
    """
    person_entities = [e for e in entities if e.type == "PERSON"]
    non_person_entities = [e for e in entities if e.type != "PERSON"]
    return person_entities, non_person_entities


def _clusters_for_mode_none(person_entities: list[Entity]) -> list[Cluster]:
    """D-62 / Claude's Discretion §"none" mode: each PERSON entity becomes
    its own pseudo-cluster (canonical = entity.text, members = (entity,)).

    No merges; no nickname expansion. The variant set is still computed via
    ``variants_for`` so cross-turn de-anonymization still has the variant
    rows in entity_registry to round-trip on. This is explicitly worse for
    coreference quality than algorithmic mode but is the deterministic
    "do nothing" path.
    """
    return [
        Cluster(
            canonical=e.text,
            variants=variants_for(e.text),
            members=(e,),
        )
        for e in person_entities
    ]


async def _resolve_clusters_via_llm(
    person_entities: list[Entity],
    registry: ConversationRegistry,
) -> tuple[list[Cluster], bool, str, bool]:
    """D-49 / D-52 / D-54: try to refine algorithmic clusters via the LLM
    provider; on ANY failure (egress trip, network, schema mismatch) fall
    back to the algorithmic clusters.

    Returns:
        ``(clusters, provider_fallback, fallback_reason, egress_tripped)``.

    Caller holds the per-thread asyncio.Lock; this function MUST NOT raise
    (NFR-3 — never crash, never leak). The cloud LLM call happens inside
    ``LLMProviderClient`` which enforces a settings-controlled timeout
    (D-50, default 30 s) so the lock is bounded.
    """
    # First, always compute the algorithmic clusters — they are the fallback
    # answer if the LLM path errors out OR returns invalid JSON.
    algorithmic_clusters = cluster_persons(person_entities)

    # No PERSON entities → no LLM call needed. Empty cluster list is the
    # correct answer, not an error.
    if not algorithmic_clusters:
        return [], False, "", False

    # Build the provisional surrogate map for the egress filter (D-56).
    # The filter's job is to scan the outbound payload for ANY real value
    # that might be in the registry OR in this turn's in-flight set; using
    # the canonical real values as keys here keeps the filter scope
    # exhaustive without leaking provisional surrogates that don't exist
    # yet (anonymize() hasn't run yet — Faker output not assigned).
    provisional_surrogates: dict[str, str] = {
        c.canonical: c.canonical for c in algorithmic_clusters
    }

    # Compose the resolution prompt. Schema documented in CONTEXT.md D-49.
    # The model's job is to RE-GROUP existing members (no name invention).
    prompt_clusters = [
        {"canonical": c.canonical, "members": [m.text for m in c.members]}
        for c in algorithmic_clusters
    ]
    messages = [
        {
            "role": "system",
            "content": (
                "You are a coreference resolver. The user provides "
                "preliminary PERSON clusters. Return JSON "
                '{"clusters": [{"canonical": str, "members": list[str]}, ...]} '
                "with the same members regrouped if you can identify obvious "
                "mergeable clusters; otherwise return the input unchanged. "
                "Never invent names. Never include any text outside the JSON "
                "object."
            ),
        },
        {
            "role": "user",
            "content": json.dumps({"clusters": prompt_clusters}, ensure_ascii=False),
        },
    ]

    try:
        client = LLMProviderClient()
        result = await client.call(
            feature="entity_resolution",
            messages=messages,
            registry=registry,
            provisional_surrogates=provisional_surrogates,
        )

        # Schema validation. Any mismatch raises ValueError → falls back.
        refined = result.get("clusters") if isinstance(result, dict) else None
        if not isinstance(refined, list):
            raise ValueError("invalid resolution response (clusters not a list)")

        # Re-attach Entity members by looking up each member text in the
        # algorithmic-cluster member pool. Hallucinated names are silently
        # dropped (T-CLUST-02 mitigation) — never invented.
        text_to_entity: dict[str, Entity] = {
            m.text: m for c in algorithmic_clusters for m in c.members
        }
        clusters_built: list[Cluster] = []
        for entry in refined:
            if not isinstance(entry, dict):
                raise ValueError("invalid resolution response entry (not a dict)")
            canonical = entry.get("canonical")
            members_raw = entry.get("members")
            if not isinstance(canonical, str) or not isinstance(members_raw, list):
                raise ValueError("invalid resolution response entry shape")
            members = tuple(
                text_to_entity[m] for m in members_raw if m in text_to_entity
            )
            if not members:
                continue
            clusters_built.append(
                Cluster(
                    canonical=canonical,
                    variants=variants_for(canonical),
                    members=members,
                )
            )
        if not clusters_built:
            raise ValueError("resolution response empty after re-attach")

        # Successful refinement.
        return clusters_built, False, "", False

    except _EgressBlocked as exc:
        # D-54: pre-flight egress trip. Algorithmic fallback (already computed).
        # The egress filter already logged a WARNING with hashes-only.
        # We log the fallback decision at INFO; counts only.
        logger.info(
            "redaction.llm_fallback reason=egress_blocked clusters_formed=%d match_count=%d",
            len(algorithmic_clusters),
            exc.result.match_count,
        )
        return algorithmic_clusters, True, "egress_blocked", True

    except Exception as exc:  # noqa: BLE001
        # D-52: network / 5xx / invalid_response / etc → algorithmic fallback.
        # NEVER re-raise (NFR-3). Type name only; never raw values.
        reason = type(exc).__name__
        logger.info(
            "redaction.llm_fallback reason=%s clusters_formed=%d",
            reason,
            len(algorithmic_clusters),
        )
        return algorithmic_clusters, True, reason, False


class RedactionService:
    """v1.0 redaction service — single async public method (D-14).

    The constructor eagerly warms every ``@lru_cache``'d singleton the
    pipeline depends on so the first real request doesn't pay the
    Presidio + spaCy model load (~1-3 s on a cold start).
    """

    def __init__(self) -> None:
        # D-15 eager warm-up — load Presidio engine, Faker(id_ID), and the
        # gender-guesser detector. Each is @lru_cache'd, so subsequent calls
        # from anywhere in the process are O(1) lookups.
        get_analyzer()
        get_faker()
        get_gender_detector()
        logger.info(
            "RedactionService initialised (Presidio + Faker + gender detector loaded)."
        )

    async def _get_thread_lock(self, thread_id: str) -> asyncio.Lock:
        """D-29 (PERF-03): get-or-create the asyncio.Lock for this thread.

        Held briefly under ``_thread_locks_master`` to make get-or-create
        atomic across coroutines (avoids the dict-mutation race where two
        callers both observe ``_thread_locks.get(thread_id) is None`` and
        each create their own lock — losing one and serialising on the
        other). Returned lock is acquired by the caller.
        """
        async with _thread_locks_master:
            lock = _thread_locks.get(thread_id)
            if lock is None:
                lock = asyncio.Lock()
                _thread_locks[thread_id] = lock
            return lock

    @traced(name="redaction.redact_text")
    async def redact_text(
        self,
        text: str,
        registry: ConversationRegistry | None = None,
    ) -> RedactionResult:
        """D-13 / D-14 / D-39: detect + cluster + anonymize. Stateless or
        registry-aware.

        Args:
            text: Raw input text. May contain UUIDs, Indonesian or English
                names, emails, phone numbers, credit-card-like strings, etc.
            registry: When ``None`` (Phase 1 default — D-39), behaviour is
                identical to the stateless legacy path (mode=algorithmic
                pseudo-clusters; no LLM contact; no upsert). When supplied,
                the call is wrapped in a per-thread ``asyncio.Lock``
                (D-29 / D-30) and:
                  - PERSON entities are clustered per
                    ``settings.entity_resolution_mode`` (algorithmic / llm /
                    none — D-45 / D-49 / D-62)
                  - the cloud-LLM path is gated by the egress filter and
                    falls back to algorithmic on any failure (D-52 / D-54)
                  - existing real values reuse their stored surrogate
                    (REG-04)
                  - Faker generation honours both per-call AND per-thread
                    forbidden tokens (D-37)
                  - newly-introduced mappings (canonical + variants) are
                    upserted to the ``entity_registry`` table inside the
                    critical section (D-32 / D-48)

        Returns:
            ``RedactionResult`` with anonymized text, the real -> surrogate
            map for surrogate-bucket entities, the count of hard-redact
            placeholders emitted, and total latency in milliseconds.

        Raises:
            RedactionError: if the input contains the literal sentinel
                substring ``<<UUID_`` (D-11). Surfaced from the UUID
                pre-mask helper inside ``detect_entities``.
        """
        # TODO(Phase 5): gate `if not get_settings().pii_redaction_enabled:
        # return RedactionResult(anonymized_text=text, entity_map={},
        #                        hard_redacted_count=0, latency_ms=0.0)`
        # Phase 1 ships the flag in Settings (Plan 02) for forward-compat
        # with Phase 5 SC#5; the gate goes here, not in callers, so every
        # downstream consumer benefits automatically.
        if registry is None:
            # D-39: stateless legacy path. Phase 1 body unchanged.
            return await self._redact_text_stateless(text)

        # D-29 / D-30 / D-61: per-thread lock spans detect → cluster → LLM-call
        # → generate-surrogates → upsert-deltas. Phase 3 LLM call lives
        # INSIDE the lock per D-61 step 3.
        lock = await self._get_thread_lock(registry.thread_id)
        t_lock_start = time.perf_counter()
        async with lock:
            lock_wait_ms = (time.perf_counter() - t_lock_start) * 1000.0
            size_before = len(registry.entries())
            result = await self._redact_text_with_registry(text, registry)
            size_after = len(registry.entries())
            # D-41 / B4: counts and timings only — NEVER real values.
            logger.debug(
                "redaction.redact_text(registry): thread_id=%s size_before=%d size_after=%d lock_wait_ms=%.2f writes=%d",
                registry.thread_id,
                size_before,
                size_after,
                lock_wait_ms,
                size_after - size_before,
            )
            return result

    async def _redact_text_stateless(self, text: str) -> RedactionResult:
        """Phase 1 stateless redact path — registry=None ⇒ no clustering, no
        LLM, no upsert. Each PERSON entity gets its own pseudo-cluster so
        the cluster-aware ``anonymize()`` API still works correctly (D-39:
        identical legacy behaviour from the caller's perspective — same
        return shape, same surrogate properties)."""
        t0 = time.perf_counter()

        # W10: detect_entities returns the masked text it built so we don't
        # double-mask. Entity offsets are relative to masked_text, NOT the
        # original input.
        masked_text, entities, sentinels = detect_entities(text)

        person_entities, non_person_entities = _split_person_non_person(entities)
        # Stateless path: each PERSON entity gets its own pseudo-cluster
        # (no merges, no nickname expansion). Behaviour matches the legacy
        # Phase 1 per-entity path because each cluster has a single member
        # whose canonical equals its own text.
        clusters = _clusters_for_mode_none(person_entities)

        anonymized_masked, entity_map, hard_redacted_count = anonymize(
            masked_text=masked_text,
            clusters=clusters,
            non_person_entities=non_person_entities,
            registry=None,
        )
        anonymized_text = restore_uuids(anonymized_masked, sentinels)

        latency_ms = (time.perf_counter() - t0) * 1000.0

        # D-18 / B4: counts and timings only — never real entity values.
        logger.debug(
            "redaction.redact_text: chars=%d entities=%d surrogates=%d hard=%d uuid_drops=%d ms=%.2f",
            len(text),
            len(entities),
            len(entity_map),
            hard_redacted_count,
            len(sentinels),
            latency_ms,
        )

        return RedactionResult(
            anonymized_text=anonymized_text,
            entity_map=entity_map,
            hard_redacted_count=hard_redacted_count,
            latency_ms=latency_ms,
        )

    async def _redact_text_with_registry(
        self,
        text: str,
        registry: ConversationRegistry,
    ) -> RedactionResult:
        """Registry-aware redact path. Caller holds the per-thread lock.

        D-61 8-step flow (verbatim from CONTEXT.md):
            1. (Caller) Acquire per-thread asyncio.Lock.
            2. Detect entities (Presidio two-pass).
            3. Cluster PERSON entities (mode-dispatched: algorithmic / llm /
               none — Phase 3).
            4. Generate Faker surrogates per cluster (Phase 1 collision
               budget preserved by anonymize()).
            5. Compose variant set per cluster (D-48 first-only / last-only /
               honorific-prefixed / nickname).
            6. Compute deltas vs loaded registry; await registry.upsert_delta
               (Phase 2 D-32).
            7. Build entity_map for THIS call's text rewrite using ALL
               variant rows.
            8. (Caller) Release the lock; return RedactionResult.
        """
        t0 = time.perf_counter()

        masked_text, entities, sentinels = detect_entities(text)

        # Step 3: split PERSON / non-PERSON; cluster PERSON by mode.
        person_entities, non_person_entities = _split_person_non_person(entities)

        settings = get_settings()
        mode = settings.entity_resolution_mode  # 'algorithmic' | 'llm' | 'none'

        # D-63 tracing accumulators. NEVER store raw values here.
        provider_fallback = False
        egress_tripped = False
        fallback_reason = ""

        if mode == "algorithmic":
            clusters = cluster_persons(person_entities)
            clusters_merged_via = "algorithmic"
        elif mode == "none":
            clusters = _clusters_for_mode_none(person_entities)
            clusters_merged_via = "none"
        else:
            # mode == "llm" — pre-cluster algorithmically, then ask the LLM
            # to refine. On ANY failure (egress, network, schema mismatch),
            # fall back to algorithmic clusters. Never raises.
            (
                clusters,
                provider_fallback,
                fallback_reason,
                egress_tripped,
            ) = await _resolve_clusters_via_llm(person_entities, registry)
            clusters_merged_via = "llm"

        # Steps 4 + 7: cluster-aware Faker dispatch + entity_map build.
        # anonymize() now allocates ONE surrogate per cluster (D-45) — every
        # variant in cluster.members rewrites to the same canonical surrogate.
        anonymized_masked, entity_map, hard_redacted_count = anonymize(
            masked_text=masked_text,
            clusters=clusters,
            non_person_entities=non_person_entities,
            registry=registry,
        )
        anonymized_text = restore_uuids(anonymized_masked, sentinels)

        # ==============================================================
        # Step 6: delta computation (D-32 / D-48).
        # PERSON deltas: one row per variant in cluster.variants, all sharing
        # the cluster's canonical surrogate (sub-surrogate write-through).
        # Non-PERSON deltas: existing Phase 2 path — one row per real value.
        # All deltas funnel through registry.upsert_delta which is
        # INSERT … ON CONFLICT (thread_id, real_value_lower) DO NOTHING
        # (D-32 — cross-process race-safe).
        # ==============================================================
        deltas: list[EntityMapping] = []
        seen_lower: set[str] = set()  # de-dupe within this call

        # PERSON variant rows (D-48). The canonical's surrogate lives in
        # entity_map under the canonical real value (anonymize() puts it
        # there even when no variant span was detected for the canonical
        # itself — see anonymization.py).
        for cluster in clusters:
            canonical_surrogate = entity_map.get(cluster.canonical)
            if not canonical_surrogate:
                continue  # defensive: empty cluster (shouldn't happen)
            for variant in cluster.variants:
                vlow = variant.casefold()
                if vlow in seen_lower:
                    continue
                seen_lower.add(vlow)
                if vlow in registry._by_lower:
                    continue  # already persisted (cross-turn or earlier in this call)
                deltas.append(
                    EntityMapping(
                        real_value=variant,
                        real_value_lower=vlow,
                        surrogate_value=canonical_surrogate,
                        entity_type="PERSON",
                        source_message_id=None,  # Phase 5 chat router backfills
                    )
                )

        # Non-PERSON deltas. anonymize()'s entity_map keys are real values,
        # but we want a per-Entity walk so we can carry the correct
        # entity_type for each delta (W-2 invariant). Build a text→Entity
        # index ONCE so the loop is O(n) instead of O(n*m).
        non_person_index: dict[str, Entity] = {e.text: e for e in non_person_entities}
        for ent_text, ent in non_person_index.items():
            surrogate = entity_map.get(ent_text)
            if surrogate is None:
                continue  # hard-redact / no surrogate emitted
            elow = ent_text.casefold()
            if elow in seen_lower:
                continue
            seen_lower.add(elow)
            if elow in registry._by_lower:
                continue  # already persisted
            deltas.append(
                EntityMapping(
                    real_value=ent_text,
                    real_value_lower=elow,
                    surrogate_value=surrogate,
                    entity_type=ent.type,
                    source_message_id=None,
                )
            )

        if deltas:
            # D-32: eager upsert inside the critical section. Raises on DB
            # error (REG-04 invariant — losing a write would silently break
            # "same real → same surrogate within thread").
            await registry.upsert_delta(deltas)

        latency_ms = (time.perf_counter() - t0) * 1000.0

        # D-18 / D-41 / B4 / D-63: counts, timings, mode flags ONLY.
        # NEVER real values, NEVER member texts, NEVER cluster canonicals.
        logger.debug(
            "redaction.redact_text(reg): chars=%d entities=%d "
            "clusters=%d cluster_size_max=%d merged_via=%s "
            "surrogates=%d hard=%d uuid_drops=%d deltas=%d "
            "provider_fallback=%s egress_tripped=%s fallback_reason=%s ms=%.2f",
            len(text),
            len(entities),
            len(clusters),
            max((len(c.members) for c in clusters), default=0),
            clusters_merged_via,
            len(entity_map),
            hard_redacted_count,
            len(sentinels),
            len(deltas),
            provider_fallback,
            egress_tripped,
            fallback_reason or "-",
            latency_ms,
        )

        return RedactionResult(
            anonymized_text=anonymized_text,
            entity_map=entity_map,
            hard_redacted_count=hard_redacted_count,
            latency_ms=latency_ms,
        )

    @traced(name="redaction.de_anonymize_text")
    async def de_anonymize_text(
        self,
        text: str,
        registry: ConversationRegistry,
    ) -> str:
        """D-34: 1-phase placeholder-tokenized round-trip (DEANON-01 / DEANON-02).

        Forward-compat with Phase 4's 3-phase fuzzy upgrade (FR-5.4) — Phase 4
        will insert its placeholder-tokenized fuzzy-match pass BETWEEN the
        existing two passes (surrogate→placeholder, placeholder→real) without
        rewriting this call site.

        Algorithm:
          1. Sort registry entries by ``len(surrogate_value)`` DESC — guarantees
             longest match wins, prevents partial-overlap corruption when
             surrogates share token prefixes (e.g. "Bambang Sutrisno" must be
             replaced before "Bambang").
          2. Pass 1: surrogate → placeholder token (case-insensitive per
             DEANON-02 via ``re.IGNORECASE``).
          3. Pass 2: placeholder → real_value (original casing preserved per
             D-36).

        D-35: hard-redact placeholders (``[CREDIT_CARD]``, ``[US_SSN]``, etc.)
        pass through unchanged because they are NEVER in the registry (D-24 /
        REG-05). They are simply not matched by Pass 1.
        """
        t0 = time.perf_counter()
        entries = registry.entries()
        # Sort by len(surrogate_value) DESC — longest surrogate match wins
        # (prevents partial-overlap corruption across DIFFERENT clusters whose
        # surrogates share token prefixes).
        # Tie-break by len(real_value) DESC so canonical real values win over
        # D-48 sub-surrogate variants (first-only / last-only / honorific-
        # prefixed / nickname). All variants in a cluster share ONE
        # surrogate_value (D-45) — without the tie-break, Pass 1 would
        # non-deterministically map the surrogate to a variant's real value
        # like "Maria" instead of the canonical "Maria Santos".
        entries_sorted = sorted(
            entries,
            key=lambda m: (len(m.surrogate_value), len(m.real_value)),
            reverse=True,
        )

        # Pass 1: surrogate -> placeholder token (case-insensitive per DEANON-02).
        out = text
        placeholders: dict[str, str] = {}
        for i, m in enumerate(entries_sorted):
            # Zero-padded width 4 (Claude's Discretion §2 — lexicographic
            # stability in tracing).
            token = f"<<PH_{i:04d}>>"
            out, n = re.subn(
                re.escape(m.surrogate_value),
                token,
                out,
                flags=re.IGNORECASE,
            )
            if n > 0:
                placeholders[token] = m.real_value  # original casing (D-36)

        # Pass 2: placeholder -> real_value.
        resolved = 0
        for token, real in placeholders.items():
            out, n = re.subn(re.escape(token), real, out)
            resolved += n

        latency_ms = (time.perf_counter() - t0) * 1000.0
        # D-41 / B4: counts and timings only — NEVER real values.
        logger.debug(
            "redaction.de_anonymize_text: text_len=%d surrogate_count=%d placeholders_resolved=%d ms=%.2f",
            len(text),
            len(entries),
            resolved,
            latency_ms,
        )
        return out


@lru_cache
def get_redaction_service() -> RedactionService:
    """D-15 singleton getter; lifespan calls this once at startup.

    Returns:
        The process-wide ``RedactionService`` instance. The constructor
        loads Presidio + Faker + the gender detector, so the first call is
        slow (~1-3 s); subsequent calls are O(1).
    """
    return RedactionService()
