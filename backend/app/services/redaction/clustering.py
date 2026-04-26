"""Union-Find clustering + sub-surrogate variant generator (D-45..D-48, RESOLVE-02).

Pre-Faker step (Phase 3 D-45): take the flat list of detected PERSON Entity
spans and produce a list of Cluster objects, where each Cluster carries:
  - canonical: the longest matched real name in the cluster
  - variants: frozenset[str] — first-only / last-only / honorific-prefixed
  - members: tuple[Entity, ...] — every span that belongs to this cluster

Mechanics:
- Union-Find (D-45): runs INSIDE redact_text BEFORE Faker generation (Plan 03-05).
- Indonesian-aware nickname dict (D-46): lookups via nicknames_id.lookup_nickname.
- Strict PRD merge (D-47): a solo first-only or last-only mention merges into
  an existing cluster ONLY when EXACTLY ONE cluster has that token. Ambiguous
  solos → their own cluster (worst case: a duplicate surrogate, never a wrong
  merge). Logs the ambiguity at DEBUG with cluster_count=N (NEVER the value;
  B4 / D-18 invariant).
- Sub-surrogate variant set (D-48): computed once per cluster; honorifics
  sourced from honorifics.strip_honorific; first/last decomposition via
  nameparser (mirroring name_extraction.py's idiom).

Logging invariant (B4 / D-18 / D-55): counts and timings ONLY. NEVER raw values.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from nameparser import HumanName

from app.services.redaction.detection import Entity
from app.services.redaction.honorifics import strip_honorific
from app.services.redaction.nicknames_id import lookup_nickname

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Cluster:
    """A coreference cluster of PERSON entities sharing one canonical surrogate."""
    canonical: str
    variants: frozenset[str]
    members: tuple[Entity, ...]


def _bare_name(text: str) -> str:
    """Strip honorific prefix; return the bare PERSON name component."""
    _h, bare = strip_honorific(text)
    return bare


def _first_token(text: str) -> str:
    """Return the first whitespace-split token of `text` (lower-cased)."""
    bare = _bare_name(text).strip()
    if not bare:
        return ""
    parsed = HumanName(bare)
    if parsed.first:
        return parsed.first.casefold()
    return bare.split()[0].casefold()


def _last_token(text: str) -> str:
    """Return the last token of `text` (lower-cased) only when it differs from first."""
    bare = _bare_name(text).strip()
    if not bare:
        return ""
    parsed = HumanName(bare)
    if parsed.last:
        return parsed.last.casefold()
    parts = bare.split()
    return parts[-1].casefold() if len(parts) > 1 else ""


def _is_solo_token(text: str) -> bool:
    """Single-word PERSON mention (no surname, after honorific strip)."""
    return len(_bare_name(text).strip().split()) == 1


def variants_for(canonical: str) -> frozenset[str]:
    """D-48: derive {canonical, bare, first-only, last-only, honorific-prefixed}.

    Honorific-prefixed variants are added ONLY if Phase 1's strip_honorific
    detected a prefix on the canonical. Returns a frozenset (deduped, hashable).
    """
    if not canonical:
        return frozenset()

    honorific, bare = strip_honorific(canonical)
    variants: set[str] = {canonical, bare}

    parsed = HumanName(bare)
    first = parsed.first or (bare.split()[0] if bare.split() else "")
    last = parsed.last or (bare.split()[-1] if len(bare.split()) > 1 else "")

    if first:
        variants.add(first)
    if last and last != first:
        variants.add(last)

    if honorific:
        prefixed_seeds = {canonical, bare}
        if first:
            prefixed_seeds.add(first)
        if last and last != first:
            prefixed_seeds.add(last)
        for v in prefixed_seeds:
            if not v.startswith(f"{honorific} "):
                variants.add(f"{honorific} {v}")

    return frozenset(v for v in variants if v)


def cluster_persons(person_entities: list[Entity]) -> list[Cluster]:
    """D-45: Union-Find over detected PERSON spans.
    D-46: nickname mentions union with the cluster whose first-name token == nickname's mapped canonical first.
    D-47: ambiguous solo first/last → own cluster (NO wrong merges).
    """
    if not person_entities:
        return []

    parent: list[int] = list(range(len(person_entities)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i: int, j: int) -> None:
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[rj] = ri

    fulls = [e.text.casefold() for e in person_entities]
    firsts = [_first_token(e.text) for e in person_entities]
    lasts = [_last_token(e.text) for e in person_entities]
    is_solo = [_is_solo_token(e.text) for e in person_entities]
    n = len(person_entities)

    # Pass 1: exact-text equality merges (case-insensitive).
    for i in range(n):
        for j in range(i + 1, n):
            if fulls[i] and fulls[i] == fulls[j]:
                union(i, j)

    # Pass 2: shared first AND last token (multi-token mentions).
    for i in range(n):
        if is_solo[i]:
            continue
        for j in range(i + 1, n):
            if is_solo[j]:
                continue
            if firsts[i] and lasts[i] and firsts[i] == firsts[j] and lasts[i] == lasts[j]:
                union(i, j)

    def cluster_first_set(idx: int) -> set[str]:
        root = find(idx)
        return {firsts[k] for k in range(n) if find(k) == root and firsts[k]}

    def cluster_last_set(idx: int) -> set[str]:
        root = find(idx)
        return {lasts[k] for k in range(n) if find(k) == root and lasts[k]}

    # Pass 3: solo-first OR solo-last partial-match merges (D-47 strict).
    for i in range(n):
        if not is_solo[i]:
            continue
        token = firsts[i] or lasts[i]
        if not token:
            continue
        candidate_roots: set[int] = set()
        for j in range(n):
            if i == j:
                continue
            rj = find(j)
            if rj == find(i):
                continue
            if token in cluster_first_set(j) or token in cluster_last_set(j):
                candidate_roots.add(rj)
        if len(candidate_roots) == 1:
            (root,) = candidate_roots
            union(root, i)
        elif len(candidate_roots) > 1:
            logger.debug(
                "clustering.ambiguous_solo entity_index=%d cluster_count=%d",
                i, len(candidate_roots),
            )

    # Pass 4: nickname merges (D-46).
    for i in range(n):
        if not is_solo[i]:
            continue
        canonical_first = lookup_nickname(person_entities[i].text)
        if not canonical_first:
            continue
        candidate_roots = set()
        for j in range(n):
            if i == j:
                continue
            rj = find(j)
            if rj == find(i):
                continue
            if canonical_first.casefold() in cluster_first_set(j):
                candidate_roots.add(rj)
        if len(candidate_roots) == 1:
            (root,) = candidate_roots
            union(root, i)
        elif len(candidate_roots) > 1:
            logger.debug(
                "clustering.ambiguous_nickname entity_index=%d cluster_count=%d",
                i, len(candidate_roots),
            )

    # Build Cluster objects.
    groups: dict[int, list[int]] = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)

    clusters: list[Cluster] = []
    for member_indices in groups.values():
        sorted_for_canonical = sorted(
            member_indices, key=lambda k: (-len(person_entities[k].text), k)
        )
        canonical_idx = sorted_for_canonical[0]
        canonical = person_entities[canonical_idx].text

        members_observed = sorted(
            member_indices, key=lambda k: person_entities[k].start
        )
        members = tuple(person_entities[k] for k in members_observed)

        clusters.append(
            Cluster(
                canonical=canonical,
                variants=variants_for(canonical),
                members=members,
            )
        )

    clusters.sort(key=lambda c: c.members[0].start)

    logger.debug(
        "clustering.complete persons=%d clusters_formed=%d cluster_size_max=%d",
        n, len(clusters),
        max((len(c.members) for c in clusters), default=0),
    )
    return clusters
