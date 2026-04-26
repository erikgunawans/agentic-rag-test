---
phase: 03-entity-resolution-llm-provider-configuration
plan: 03
type: execute
wave: 3
depends_on: [01]
files_modified:
  - backend/app/services/redaction/nicknames_id.py
  - backend/app/services/redaction/clustering.py
  - backend/app/services/redaction/egress.py
autonomous: true
requirements_addressed: [RESOLVE-02, RESOLVE-04, PROVIDER-04]
must_haves:
  truths:
    - "nicknames_id.py exposes a frozen module-level dict[str,str] of Indonesian-aware nickname → canonical first-name mappings (D-46)"
    - "clustering.py exposes a Cluster frozen dataclass and cluster_persons(person_entities) -> list[Cluster] implementing Union-Find with the three D-47 merge rules (refuse-ambiguous-solo)"
    - "clustering.py exposes a variants_for(canonical) -> frozenset[str] helper computing {canonical, first-only, last-only, honorific-prefixed} sub-surrogate variants (D-48)"
    - "egress.py exposes a frozen EgressResult dataclass + egress_filter(payload, registry, provisional) pure function performing casefold + word-boundary regex match against registry.entries() ∪ provisional (D-53, D-56)"
    - "egress.py exposes a private _EgressBlocked exception type (D-54) for the LLMProviderClient fallback wrapper to catch"
    - "All three modules log only counts + 8-char SHA-256 hashes — NEVER raw values (B4 / D-18 / D-55 invariant)"
  artifacts:
    - path: "backend/app/services/redaction/nicknames_id.py"
      provides: "Indonesian-aware nickname → canonical lookup"
      exports: ["lookup_nickname"]
      min_lines: 40
    - path: "backend/app/services/redaction/clustering.py"
      provides: "Union-Find PERSON clustering + sub-surrogate variant generator"
      exports: ["Cluster", "cluster_persons", "variants_for"]
      min_lines: 100
    - path: "backend/app/services/redaction/egress.py"
      provides: "Pre-flight egress filter + EgressResult + _EgressBlocked"
      exports: ["egress_filter", "EgressResult", "_EgressBlocked"]
      min_lines: 70
  key_links:
    - from: "backend/app/services/redaction/clustering.py"
      to: "backend/app/services/redaction/nicknames_id.py"
      via: "lookup_nickname() in cluster merge logic"
      pattern: "from app\\.services\\.redaction\\.nicknames_id import lookup_nickname"
    - from: "backend/app/services/redaction/clustering.py"
      to: "backend/app/services/redaction/honorifics.py"
      via: "strip_honorific() in variants_for"
      pattern: "from app\\.services\\.redaction\\.honorifics import"
    - from: "backend/app/services/redaction/egress.py"
      to: "ConversationRegistry.entries()"
      via: "egress_filter scans registry.entries() ∪ provisional"
      pattern: "registry\\.entries\\(\\)"
---

<objective>
Ship three independent leaf modules in the `redaction/` sub-package: `nicknames_id.py`, `clustering.py`, `egress.py`. None depend on each other except `clustering.py` importing `nicknames_id.lookup_nickname` and `honorifics.strip_honorific` (Phase 1).

Purpose: Wave 3 — pure-function leaves that the LLM provider client (Plan 03-04) and the redaction-service wiring (Plan 03-05) compose. Building them as one plan keeps each task small (sibling files, no cross-wiring).

Output: Three new files under `backend/app/services/redaction/`. All modules are stateless / pure-function shape. Total new code: ~250 lines.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/03-entity-resolution-llm-provider-configuration/03-CONTEXT.md
@.planning/phases/03-entity-resolution-llm-provider-configuration/03-PATTERNS.md
@.planning/phases/01-detection-anonymization-foundation/01-CONTEXT.md
@.planning/phases/02-conversation-scoped-registry-and-round-trip/02-CONTEXT.md
@CLAUDE.md
@backend/app/services/redaction/gender_id.py
@backend/app/services/redaction/honorifics.py
@backend/app/services/redaction/name_extraction.py
@backend/app/services/redaction/registry.py

<interfaces>
<!-- Existing primitives this plan calls. Read once; no codebase exploration needed. -->

From backend/app/services/redaction/gender_id.py (analog for nicknames_id.py):
- Module shape: `_INDONESIAN_GENDER: dict[str, str] = {...}` then `def lookup_gender(name) -> str | None: return _INDONESIAN_GENDER.get(name.casefold())`.
- Loaded once at module import; zero runtime cost beyond the import (D-46).

From backend/app/services/redaction/honorifics.py (Phase 1):
- Exposes `strip_honorific(text: str) -> tuple[str, str]` returning `(honorific_or_empty, bare_name)`.
- Phase 3 D-48 reuses this as the source of truth for the honorific-prefixed variant row.

From backend/app/services/redaction/name_extraction.py (Phase 1):
- Phase 1 nameparser wrapper. Phase 3's `_first_token` / `_last_token` mirror its `nameparser.HumanName` idiom.

From backend/app/services/redaction/registry.py (Phase 2 final):
- `class ConversationRegistry`:
  - `def entries(self) -> list[EntityMapping]` — returns ALL persisted real↔surrogate mappings (Phase 2 D-27).
- `class EntityMapping(BaseModel)` frozen — fields used by egress: `entity_type: str`, `real_value: str` (verify the EXACT field name by reading registry.py before iterating; Phase 2 named the original-form column `real_value`).

From .planning/phases/03-entity-resolution-llm-provider-configuration/03-PATTERNS.md §"backend/app/services/llm_provider.py":
- `EgressResult(tripped: bool, match_count: int, entity_types: list[str], match_hashes: list[str])` — frozen dataclass; hashes are sha256(value)[:8] only (D-55).
- `_EgressBlocked(Exception)` — internal-only exception carrying the EgressResult.
- `egress_filter(payload, registry, provisional)` — pure function; pattern is `r'\b' + re.escape(v.casefold()) + r'\b'` against `payload.casefold()`.

The `Entity` Phase 1 type is imported from the same path that `anonymization.py` uses; the executor MUST grep `backend/app/services/redaction/anonymization.py`'s imports to confirm the Entity module path before authoring `clustering.py`. Most likely: `from app.services.redaction.detection import Entity`. Fallbacks: `app.services.redaction.types`, `app.services.redaction.spans`.
</interfaces>
</context>

<tasks>

<task type="auto" tdd="false">
  <name>Task 1: Write backend/app/services/redaction/nicknames_id.py (Indonesian nickname → canonical lookup)</name>
  <files>backend/app/services/redaction/nicknames_id.py</files>
  <read_first>
    - backend/app/services/redaction/gender_id.py (exact analog — read module shape, dict declaration style, lookup function signature)
    - .planning/phases/03-entity-resolution-llm-provider-configuration/03-CONTEXT.md D-46
    - .planning/phases/03-entity-resolution-llm-provider-configuration/03-PATTERNS.md §"backend/app/services/redaction/nicknames_id.py"
  </read_first>
  <action>
Create `backend/app/services/redaction/nicknames_id.py` mirroring `gender_id.py`'s shape exactly. Pure data + one lookup function; loaded once at import.

File content:

```python
"""Indonesian-aware nickname → canonical first-name lookup (D-46, RESOLVE-02).

Why this exists:
- PRD FR-4.2 sub-surrogate derivation requires merging "Danny" into the same
  cluster as "Daniel"; an embedded Python dict gives O(1) lookup with zero
  runtime cost beyond the import.
- Indonesian-first coverage; small English block for completeness.

Conventions (mirror gender_id.py):
- Keys are lower-cased nicknames (no honorifics).
- Values are the canonical first name (lower-cased).
- Lookup is case-insensitive via the lookup_nickname() helper which casefolds.
- When a nickname has multiple plausible canonicals (rare; e.g., "Iwan"),
  the dict picks the FIRST match deterministically (Python dict-insertion order)
  and callers may log the ambiguity at DEBUG (D-46).
"""
from __future__ import annotations

# fmt: off
_INDONESIAN_NICKNAMES: dict[str, str] = {
    # Indonesian nicknames (Indonesian-first coverage per D-46)
    "bambs": "bambang",
    "bams": "bambang",
    "yoyok": "joko",
    "joko": "joko",
    "tini": "kartini",
    "wati": "watini",
    "iwan": "setiawan",
    "ucup": "yusuf",
    "udin": "saifuddin",
    "anto": "haryanto",
    "agus": "agustinus",
    "didi": "didik",
    "eko": "eko",
    "lia": "amalia",
    "rini": "rina",
    "yanti": "yantini",
    "yuli": "yuliana",
    "indra": "indra",
    "ayu": "ayu",
    "hari": "hariyanto",
    "har": "hariyanto",
    "tono": "sutono",
    "dik": "didik",
    "panji": "panji",
    "pandji": "panji",

    # English nicknames (small block for completeness — D-46)
    "danny": "daniel",
    "dan": "daniel",
    "bob": "robert",
    "rob": "robert",
    "robbie": "robert",
    "bill": "william",
    "billy": "william",
    "will": "william",
    "tom": "thomas",
    "tommy": "thomas",
    "mike": "michael",
    "mikey": "michael",
    "jim": "james",
    "jimmy": "james",
    "kate": "katherine",
    "katie": "katherine",
    "liz": "elizabeth",
    "beth": "elizabeth",
    "betty": "elizabeth",
    "jen": "jennifer",
    "jenny": "jennifer",
    "alex": "alexander",
    "andy": "andrew",
    "drew": "andrew",
    "tony": "anthony",
    "chris": "christopher",
    "joe": "joseph",
    "joey": "joseph",
}
# fmt: on


def lookup_nickname(nickname: str) -> str | None:
    """Return the canonical first name for a nickname, or None if absent.

    Lookup is case-insensitive (this function casefolds). On ambiguity the
    dict already encodes a deterministic first-match via insertion order;
    callers may log at DEBUG when a nickname maps multiple plausible canonicals
    (D-46). This module stays pure — no logging here.
    """
    return _INDONESIAN_NICKNAMES.get(nickname.casefold())
```

Hard requirements (verify after writing):
- File path EXACTLY `backend/app/services/redaction/nicknames_id.py`.
- `from __future__ import annotations` at top (matches `gender_id.py`).
- `_INDONESIAN_NICKNAMES` is module-level, typed `dict[str, str]`.
- All keys lower-cased ASCII, all values lower-cased canonical first names.
- `lookup_nickname` is the SOLE public function.
- ≥30 dictionary entries (Indonesian-first majority, English block ≤ 30%).
  </action>
  <verify>
    <automated>cd backend && source venv/bin/activate && python -c "from app.services.redaction.nicknames_id import lookup_nickname, _INDONESIAN_NICKNAMES; assert lookup_nickname('Danny') == 'daniel'; assert lookup_nickname('DANNY') == 'daniel'; assert lookup_nickname('Bambs') == 'bambang'; assert lookup_nickname('not_a_nickname') is None; assert len(_INDONESIAN_NICKNAMES) >= 30; print('NICKNAMES_OK')" 2>&1 | grep -q "NICKNAMES_OK"</automated>
  </verify>
  <acceptance_criteria>
    - File `backend/app/services/redaction/nicknames_id.py` exists.
    - Contains `_INDONESIAN_NICKNAMES: dict[str, str] = {` literal.
    - Contains `def lookup_nickname(nickname: str) -> str | None:` literal.
    - Contains the function body using `.casefold()` on the input.
    - Contains ≥30 entries.
    - `lookup_nickname('Danny')` returns `'daniel'`.
    - `lookup_nickname('Bambs')` returns `'bambang'`.
    - Case-insensitive: `lookup_nickname('DANNY') == 'daniel'`.
    - Missing nicknames return `None` (not KeyError).
  </acceptance_criteria>
  <done>nicknames_id.py written; lookup helper case-insensitive; ≥30 entries.</done>
</task>

<task type="auto" tdd="false">
  <name>Task 2: Write backend/app/services/redaction/clustering.py (Union-Find + sub-surrogate variants)</name>
  <files>backend/app/services/redaction/clustering.py</files>
  <read_first>
    - backend/app/services/redaction/anonymization.py (Phase 1+2 — confirm the EXACT import path for the `Entity` type by reading the module's import block; the path likely is `from app.services.redaction.detection import Entity`. Update the import in clustering.py to match what anonymization.py uses.)
    - backend/app/services/redaction/honorifics.py (strip_honorific signature)
    - backend/app/services/redaction/name_extraction.py (nameparser idiom)
    - backend/app/services/redaction/nicknames_id.py (Plan 03-03 Task 1 — lookup_nickname)
    - .planning/phases/03-entity-resolution-llm-provider-configuration/03-CONTEXT.md D-45, D-46, D-47, D-48
    - .planning/phases/03-entity-resolution-llm-provider-configuration/03-PATTERNS.md §"backend/app/services/redaction/clustering.py"
  </read_first>
  <action>
Create `backend/app/services/redaction/clustering.py`. Module owns:
1. `Cluster` frozen dataclass.
2. `cluster_persons(person_entities)` — Union-Find with the three D-47 strict merge rules.
3. `variants_for(canonical)` — sub-surrogate variant set generator (D-48).

Before writing, grep for the `Entity` import in `anonymization.py`:
```bash
grep -n "from app.services.redaction" backend/app/services/redaction/anonymization.py | grep -i entity
```
Match clustering.py's import to that path verbatim.

File content (full target — adjust only the `Entity` import path if necessary):

```python
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

from app.services.redaction.honorifics import strip_honorific
from app.services.redaction.nicknames_id import lookup_nickname

# Entity import — verify the path matches anonymization.py's import before editing.
from app.services.redaction.detection import Entity  # noqa: E402

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
```

Hard requirements (verify after writing):
- Path EXACTLY `backend/app/services/redaction/clustering.py`.
- `Cluster` is a frozen dataclass with exactly three fields: `canonical: str`, `variants: frozenset[str]`, `members: tuple[Entity, ...]`.
- `cluster_persons(person_entities: list[Entity]) -> list[Cluster]` is the public entry point.
- `variants_for(canonical: str) -> frozenset[str]` is exported.
- D-47 strict-refuse-ambiguous: when more than one existing cluster contains a solo's token, the solo becomes its own cluster (no union); logged at DEBUG with `cluster_count=N`.
- D-46 nickname merge uses `lookup_nickname()`'s output to find the candidate cluster's first-name set.
- All `logger.debug` calls log COUNTS / INDICES only — NEVER `entity.text` or any real-value substring.
- Imports `from app.services.redaction.nicknames_id import lookup_nickname` and `from app.services.redaction.honorifics import strip_honorific`.
  </action>
  <verify>
    <automated>cd backend && source venv/bin/activate && python -c "from app.services.redaction.clustering import Cluster, cluster_persons, variants_for; v = variants_for('Bambang Sutrisno'); assert 'Bambang Sutrisno' in v; v_str = str(sorted(v)).lower(); assert 'bambang' in v_str and 'sutrisno' in v_str; v_pak = variants_for('Pak Bambang Sutrisno'); assert any('Pak ' in vv for vv in v_pak); empty = cluster_persons([]); assert empty == []; print('CLUSTERING_OK')" 2>&1 | grep -q "CLUSTERING_OK"</automated>
  </verify>
  <acceptance_criteria>
    - File `backend/app/services/redaction/clustering.py` exists.
    - Contains `@dataclass(frozen=True)` decorator on `class Cluster`.
    - Contains `def cluster_persons(person_entities: list[Entity]) -> list[Cluster]:`.
    - Contains `def variants_for(canonical: str) -> frozenset[str]:`.
    - Contains `from app.services.redaction.nicknames_id import lookup_nickname`.
    - Contains `from app.services.redaction.honorifics import strip_honorific`.
    - Contains the literal `cluster_count=%d` in logger.debug calls (D-47 ambiguity log).
    - Does NOT contain any logger call with `entity.text`, `person_entities[i].text`, or `%s` formatting on real-value tokens (B4 invariant).
    - `variants_for('Bambang Sutrisno')` returns frozenset containing 'Bambang Sutrisno', 'Bambang', 'Sutrisno' (cased exactly as input).
    - `variants_for('Pak Bambang Sutrisno')` returns variants with 'Pak ' prefix.
    - `cluster_persons([])` returns `[]` (empty).
  </acceptance_criteria>
  <done>clustering.py written; Union-Find + variants_for + Cluster dataclass; D-47 ambiguity refuses merge; logging is counts-only.</done>
</task>

<task type="auto" tdd="false">
  <name>Task 3: Write backend/app/services/redaction/egress.py (pre-flight egress filter + EgressResult + _EgressBlocked)</name>
  <files>backend/app/services/redaction/egress.py</files>
  <read_first>
    - backend/app/services/redaction/registry.py (Phase 2 — confirm EntityMapping field names; the egress filter iterates `registry.entries()` and reads `.entity_type` and `.real_value` per entry)
    - .planning/phases/03-entity-resolution-llm-provider-configuration/03-CONTEXT.md D-53, D-54, D-55, D-56
    - .planning/phases/03-entity-resolution-llm-provider-configuration/03-PATTERNS.md §"backend/app/services/llm_provider.py" (egress filter pattern in the patterns file — full target shape)
  </read_first>
  <action>
Create `backend/app/services/redaction/egress.py`. Module owns:
1. `EgressResult` frozen dataclass.
2. `_EgressBlocked` exception (carries the EgressResult).
3. `egress_filter(payload, registry, provisional)` — pure function.
4. `_hash8(value)` — sha256 hash helper (private; for D-55 log invariant).

Before writing, confirm the `EntityMapping` field name for the original-form value by grepping registry.py:
```bash
grep -n "real_value" backend/app/services/redaction/registry.py
```
Expected: a field named `real_value` (Phase 2 D-22). If Phase 2 named it differently (e.g., `value`), update the egress_filter loop body to match.

File content (full target):

```python
"""Pre-flight egress filter for cloud LLM calls (D-53..D-56, PROVIDER-04, NFR-2).

The egress filter is the security primitive of the v1.0 PII milestone: every
cloud-LLM call passes through this function with its outbound payload BEFORE
any byte leaves the process. It scans for any case-insensitive word-boundary
match against the union of:
  - registry.entries() — all real values from prior turns of this thread
  - the in-flight provisional surrogate map for THIS turn (D-56)

If ANY match is found, the result is `tripped=True` and the LLMProviderClient
raises _EgressBlocked, which the caller's algorithmic-fallback wrapper catches
(D-52 / D-54). The trip log line carries COUNTS + entity_types + 8-char SHA-256
hashes ONLY (D-55). Raw values are NEVER logged (B4 invariant).
"""
from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.redaction.registry import ConversationRegistry

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EgressResult:
    """Outcome of a single egress_filter() call.

    tripped: True if at least one match was found (block the call).
    match_count: number of distinct (entity_type, real_value) matches.
    entity_types: sorted unique entity types matched (e.g. ['EMAIL_ADDRESS', 'PERSON']).
    match_hashes: sorted unique 8-char SHA-256 hashes of matched real values
                  (D-55 — forensic-correlation-friendly without leaking PII).
    """
    tripped: bool
    match_count: int
    entity_types: list[str]
    match_hashes: list[str]


class _EgressBlocked(Exception):
    """Internal-only: caught by LLMProviderClient's fallback wrapper.

    Never raised to the chat loop (NFR-3 'never crash'). Carries the
    EgressResult so the caller can log + decide on algorithmic fallback.
    """
    def __init__(self, result: EgressResult) -> None:
        self.result = result
        super().__init__("egress filter blocked cloud call")


def _hash8(value: str) -> str:
    """8-char SHA-256 hash for forensic logging (D-55). NOT for security."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:8]


def egress_filter(
    payload: str,
    registry: "ConversationRegistry",
    provisional: dict[str, str] | None,
) -> EgressResult:
    """D-53: casefold + word-boundary regex match.
    D-56: scope = persisted registry ∪ in-flight provisional surrogates.
    Bail-on-first-match in the inner loop is acceptable; we accumulate all
    matches for richer telemetry (small registries; n is per-thread).

    Args:
        payload: the outbound LLM request body as a plain string (caller
            pre-serializes messages — usually json.dumps(messages)).
        registry: the per-thread ConversationRegistry whose entries() supplies
            the persisted real values.
        provisional: dict[real_value, provisional_surrogate] for entities
            detected in THIS turn that are not yet persisted (D-56). May be None.

    Returns:
        EgressResult with tripped=True iff any candidate matched.
    """
    haystack = payload.casefold()
    matches: list[tuple[str, str]] = []

    # Build candidate (entity_type, real_value) list.
    candidates: list[tuple[str, str]] = []
    for ent in registry.entries():
        # EntityMapping field name confirmed by grepping registry.py before write.
        candidates.append((ent.entity_type, ent.real_value))
    if provisional:
        for real_value in provisional:
            candidates.append(("PERSON", real_value))  # provisional set is PERSON-only

    for entity_type, value in candidates:
        if not value:
            continue
        pattern = r"\b" + re.escape(value.casefold()) + r"\b"
        if re.search(pattern, haystack):
            matches.append((entity_type, value))

    result = EgressResult(
        tripped=bool(matches),
        match_count=len(matches),
        entity_types=sorted({t for t, _ in matches}),
        match_hashes=sorted({_hash8(v) for _, v in matches}),
    )

    if result.tripped:
        # D-55: counts + entity_types + 8-char SHA-256 hashes ONLY. NEVER raw values.
        logger.warning(
            "egress_filter_blocked event=egress_filter_blocked match_count=%d entity_types=%s match_hashes=%s",
            result.match_count, result.entity_types, result.match_hashes,
        )

    return result
```

Hard requirements (verify after writing):
- Path EXACTLY `backend/app/services/redaction/egress.py`.
- `EgressResult` is a frozen dataclass with exactly four fields: `tripped: bool`, `match_count: int`, `entity_types: list[str]`, `match_hashes: list[str]`.
- `_EgressBlocked` is an `Exception` subclass carrying an `EgressResult` instance.
- `egress_filter(payload, registry, provisional)` is the public entry point.
- The regex pattern is built EXACTLY as `r"\b" + re.escape(value.casefold()) + r"\b"` (D-53 verbatim).
- The haystack is built as `payload.casefold()` (D-53 verbatim).
- The trip log line uses ONLY `match_count`, `entity_types`, `match_hashes` — does NOT log `value`, `payload`, or any first-N-chars of the matched value (D-55 / B4).
- The `_hash8` helper uses sha256, returns first 8 hex chars.
- `TYPE_CHECKING` import block for `ConversationRegistry` to avoid circular import (Phase 2 D-39 / B2 option B posture).
  </action>
  <verify>
    <automated>cd backend && source venv/bin/activate && python -c "
from app.services.redaction.egress import EgressResult, _EgressBlocked, egress_filter, _hash8
import hashlib
# Smoke-test EgressResult
r = EgressResult(tripped=False, match_count=0, entity_types=[], match_hashes=[])
assert r.tripped is False
# Smoke-test _hash8
v = 'Bambang Sutrisno'
assert _hash8(v) == hashlib.sha256(v.encode('utf-8')).hexdigest()[:8]
assert len(_hash8(v)) == 8
# Smoke-test _EgressBlocked carries result
try:
    raise _EgressBlocked(EgressResult(True, 1, ['PERSON'], ['abcd1234']))
except _EgressBlocked as e:
    assert e.result.tripped is True
    assert e.result.match_count == 1
print('EGRESS_OK')
" 2>&1 | grep -q "EGRESS_OK"</automated>
  </verify>
  <acceptance_criteria>
    - File `backend/app/services/redaction/egress.py` exists.
    - Contains `@dataclass(frozen=True)` on `class EgressResult`.
    - EgressResult has fields: `tripped: bool`, `match_count: int`, `entity_types: list[str]`, `match_hashes: list[str]`.
    - Contains `class _EgressBlocked(Exception):` with `__init__(self, result: EgressResult)`.
    - Contains `def egress_filter(payload: str, registry: "ConversationRegistry", provisional: dict[str, str] | None) -> EgressResult:`.
    - Contains the literal regex string fragment `r"\b" + re.escape(value.casefold()) + r"\b"`.
    - Contains the literal `payload.casefold()` for haystack construction.
    - Trip log line (warning level) contains `match_count=%d`, `entity_types=%s`, `match_hashes=%s` — does NOT contain `%s` formatting of `value`, `payload`, or any raw real-value substring.
    - Contains `_hash8(value)` returning `hashlib.sha256(value.encode("utf-8")).hexdigest()[:8]`.
    - Uses `TYPE_CHECKING` for the `ConversationRegistry` import (avoids circular import).
  </acceptance_criteria>
  <done>egress.py written; EgressResult + _EgressBlocked + egress_filter + _hash8; D-53 / D-55 / D-56 invariants met; B4 log invariant preserved.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| in-process: pre-anon → cloud-LLM payload | The egress filter sits at this boundary; everything past it leaves the process |
| application logger → LangSmith / Langfuse / Railway log sink | Trip log lines flow here; B4 invariant must hold across this boundary |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-EGR-01 | Information Disclosure | egress filter bypassed (real PII reaches cloud LLM) | mitigate | D-53 casefold + word-boundary regex against `registry.entries() ∪ provisional`; D-66 unit-test matrix in Plan 03-07 covers exact-match casefold trip, word-boundary preservation, multi-word values, registry-only / provisional-only / empty-empty paths |
| T-EGR-02 | Information Disclosure | trip log leaks raw PII (B4 violation) | mitigate | D-55 — trip log line uses `match_count` (int), `entity_types` (list[str]), `match_hashes` (list[8-char SHA-256]) ONLY; acceptance criterion bans `value` / `payload` / first-N-chars of value in any logger format string. Plan 03-07 caplog test asserts no raw values appear. |
| T-EGR-03 | Information Disclosure | filter scope misses in-flight provisional surrogates from THIS turn (first-turn brand-new entity slips through) | mitigate | D-56 — filter scope is `registry.entries() ∪ in-flight provisional` dict; the helper signature `egress_filter(payload, registry, provisional)` enforces both inputs. Plan 03-07 D-66 test "provisional-only path" exercises this case. |
| T-CLUST-01 | Tampering | wrong cluster merge (false-positive coreference) corrupts the round-trip mapping | mitigate | D-47 strict refuse-ambiguous: solo first/last with multiple candidate clusters → no merge, log ambiguity at DEBUG. Worst case is a duplicate surrogate (UX blemish), never wrong-merge corruption. |
| T-LOG-01 | Information Disclosure | clustering.py logs `entity.text` or member values during cluster formation | mitigate | All `logger.debug` calls in clustering.py use COUNT / INDEX format strings (`%d` only); acceptance criterion bans `%s` formatting on entity.text / person_entities[i].text |
</threat_model>

<verification>
After this plan completes:
- `git status` shows three new files in `backend/app/services/redaction/`.
- Backend imports cleanly: `cd backend && source venv/bin/activate && python -c "from app.main import app; print('OK')"`.
- Phase 1 + Phase 2 regression: `cd backend && source venv/bin/activate && pytest tests/ -x` returns 39/39 pass (no public API changed yet).
- Plan 03-04 (`llm_provider.py`) is unblocked — it imports `egress_filter`, `EgressResult`, `_EgressBlocked` from this plan's `egress.py`.
- Plan 03-05 (redaction_service wiring) is unblocked — it consumes `cluster_persons`, `variants_for` from `clustering.py`.
</verification>

<success_criteria>
- nicknames_id.py: ≥30 entries, case-insensitive lookup, mirrors gender_id.py shape exactly.
- clustering.py: Union-Find with D-47 strict refuse-ambiguous merge; D-46 nickname merges; variants_for produces canonical + bare + first + last + honorific-prefixed; B4 log invariant preserved.
- egress.py: D-53 casefold + word-boundary regex; D-55 hash-only trip log; D-56 filter scope = registry ∪ provisional; _EgressBlocked exception type.
- All three files import cleanly; Phase 1 + Phase 2 tests still pass.
</success_criteria>

<output>
Create `.planning/phases/03-entity-resolution-llm-provider-configuration/03-03-SUMMARY.md` with:
- Three new file paths + line counts
- Public exports per file
- Confirmation that the `Entity` import path was verified against anonymization.py before writing clustering.py
- Confirmation that `EntityMapping.real_value` field name was verified against registry.py before writing egress.py
- Phase 1+2 regression: 39/39 still pass
- Plans 03-04 and 03-05 are now unblocked.
</output>
