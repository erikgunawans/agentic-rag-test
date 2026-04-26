# Phase 3: Entity Resolution & LLM Provider Configuration - Pattern Map

**Mapped:** 2026-04-26
**Files analyzed:** 13 (10 new, 3 modified)
**Analogs found:** 13 / 13

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `backend/app/services/llm_provider.py` (NEW) | service (provider client + egress filter) | request-response (cloud), pass-through (local) | `backend/app/services/embedding_service.py` (`AsyncOpenAI` shape) + `backend/app/services/redaction_service.py` (`@traced` + asyncio scope) | role-match |
| `backend/app/services/redaction/nicknames_id.py` (NEW) | utility (frozen lookup dict) | static lookup | `backend/app/services/redaction/gender_id.py` | exact |
| `backend/app/services/redaction/clustering.py` (NEW, Claude's Discretion to inline) | service (Union-Find + variant generator) | transform | `backend/app/services/redaction/anonymization.py` (sub-package shape) + `backend/app/services/redaction/name_extraction.py` (nameparser wrapper pattern) | role-match |
| `backend/app/services/redaction/anonymization.py` (MODIFIED) | service (surrogate generator) | transform | self (Phase 1+2 baseline) | exact |
| `backend/app/services/redaction_service.py` (MODIFIED) | service (orchestrator) | request-response under asyncio.Lock | self (Phase 2 D-30 critical section) | exact |
| `backend/app/config.py` (MODIFIED) | config (Pydantic Settings) | env-var read | self (Phase 1's `pii_*` block + `tracing_provider`) | exact |
| `supabase/migrations/030_pii_provider_settings.sql` (NEW) | migration (ALTER TABLE) | DDL | `supabase/migrations/029_pii_entity_registry.sql` (Phase 2) + any prior `system_settings` ALTER migration | role-match |
| `backend/app/routers/admin_settings.py` (MODIFIED) | router (admin PATCH + new GET) | request-response | self (existing `SystemSettingsUpdate` + PATCH handler) | exact |
| `frontend/src/pages/AdminSettingsPage.tsx` (MODIFIED) | component (admin section) | UI form → PATCH | self (existing `activeSection`-driven section blocks) | exact |
| `backend/tests/api/test_resolution_and_provider.py` (NEW) | test (API integration) | request-response + live DB | `backend/tests/api/test_redaction_registry.py` (Phase 2) | exact |
| `backend/tests/unit/test_llm_provider_client.py` (NEW) | test (unit, mocked SDK) | mocked async | `backend/tests/unit/test_registry.py` (Phase 2) + any service unit test using `mocker`/`AsyncMock` | role-match |
| `backend/tests/unit/test_egress_filter.py` (NEW) | test (unit, pure function) | pure transform | `backend/tests/unit/test_redaction_anonymization.py` (Phase 1, table-driven) | role-match |
| `backend/app/services/redaction/__init__.py` (MODIFIED, optional) | package init (re-exports) | static | self (Phase 2 re-exports `ConversationRegistry`, `EntityMapping`) | exact |

## Pattern Assignments

### `backend/app/services/llm_provider.py` (service, request-response)

**Analog:** `backend/app/services/embedding_service.py` (for `AsyncOpenAI` instantiation + `@traced`) and `backend/app/services/redaction_service.py` (for asyncio scope, settings consumption, and structured-counts-only logging).

**Imports pattern** (from `embedding_service.py:1-6`):
```python
from openai import AsyncOpenAI
from app.services.tracing_service import traced
from app.config import get_settings
from app.database import get_supabase_client  # not needed here; included for shape
```

**For Phase 3, add:**
```python
from __future__ import annotations
import hashlib
import logging
import re
from dataclasses import dataclass
from typing import Literal, TYPE_CHECKING
from openai import AsyncOpenAI
from app.config import get_settings
from app.services.tracing_service import traced
from app.services.system_settings_service import get_system_settings

if TYPE_CHECKING:
    from app.services.redaction.registry import ConversationRegistry

logger = logging.getLogger(__name__)
```

**Lazy module-level singleton pattern** (mirror `embedding_service.py:6-11` + `anonymization.py:64-74`'s `@lru_cache` form):
```python
# embedding_service.py uses module-level instantiation in __init__:
class EmbeddingService:
    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
```

**For Phase 3 D-50, prefer the module-level cached-dict variant** (matches D-49 "lazily instantiated, cached in module-level dict keyed by provider"):
```python
_clients: dict[Literal["local", "cloud"], AsyncOpenAI] = {}

def _get_client(provider: Literal["local", "cloud"]) -> AsyncOpenAI:
    if provider in _clients:
        return _clients[provider]
    settings = get_settings()
    if provider == "local":
        _clients[provider] = AsyncOpenAI(
            base_url=settings.local_llm_base_url,
            api_key="not-needed",  # LM Studio / Ollama
            timeout=settings.llm_provider_timeout_seconds,
        )
    else:
        _clients[provider] = AsyncOpenAI(
            base_url=settings.cloud_llm_base_url,
            api_key=settings.cloud_llm_api_key,
            timeout=settings.llm_provider_timeout_seconds,
        )
    return _clients[provider]
```

**Tracing pattern** (`embedding_service.py:14`, `tracing_service.py:1-27`):
```python
# Phase 1 D-16: `@traced` supports both bare and parenthesised forms.
# Embedding service uses bare; LLMProviderClient uses parenthesised with `name=`.
@traced(name="llm_provider.entity_resolution")
async def call(self, feature, messages, registry=None, provisional_surrogates=None) -> dict:
    ...
```

**Span-attribute / structured-log pattern** (Phase 1 D-18 / Phase 2 D-41 invariants — counts and timings ONLY, NEVER raw values; mirror `anonymization.py:278-283`):
```python
# anonymization.py:278-283 reference:
logger.debug(
    "redaction.anonymize: entities=%d surrogate_pairs=%d hard_redacted=%d",
    len(entities), len(entity_map), hard_redacted_count,
)

# Phase 3 D-63 INFO-level provider-call audit:
logger.info(
    "llm_provider_call",
    extra={
        "event": "llm_provider_call",
        "feature": feature,
        "provider": resolved_provider,
        "source": resolved_source,
        "success": success,
        "latency_ms": latency_ms,
    },
)

# Phase 3 D-55 WARNING-level egress trip — counts + types + 8-char SHA-256 hashes ONLY:
logger.warning(
    "egress_filter_blocked",
    extra={
        "event": "egress_filter_blocked",
        "match_count": result.match_count,
        "entity_types": result.entity_types,
        "match_hashes": result.match_hashes,  # sha256(value)[:8]
    },
)
```

**Provider-resolution helper** (D-51, single function, source-tagged):
```python
def _resolve_provider(feature: str) -> tuple[Literal["local", "cloud"], str]:
    """D-51: env > db-feature > global-env > db-global > default('local').
    Returns (provider, source) for OBS-03 audit logging."""
    import os
    settings = get_settings()
    feature_env = os.getenv(f"{feature.upper()}_LLM_PROVIDER")
    if feature_env in ("local", "cloud"):
        return feature_env, "feature_env"
    db = get_system_settings()
    feature_db = db.get(f"{feature}_llm_provider")
    if feature_db in ("local", "cloud"):
        return feature_db, "feature_db"
    if settings.llm_provider in ("local", "cloud"):
        # Distinguish env-var-set vs DB-set:
        global_env = os.getenv("LLM_PROVIDER")
        if global_env in ("local", "cloud"):
            return global_env, "global_env"
    global_db = db.get("llm_provider")
    if global_db in ("local", "cloud"):
        return global_db, "global_db"
    return "local", "default"
```

**Egress filter (D-53/D-56) pure-function pattern** (mirror `anonymization.py:_generate_surrogate` shape — pure inputs, named result dataclass):
```python
@dataclass(frozen=True)
class EgressResult:
    tripped: bool
    match_count: int
    entity_types: list[str]
    match_hashes: list[str]  # sha256(value)[:8] only — D-55

def _hash8(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:8]

def egress_filter(
    payload: str,
    registry: "ConversationRegistry",
    provisional: dict[str, str] | None,
) -> EgressResult:
    """D-53: casefold + word-boundary regex match.
    D-56: scope = persisted registry ∪ in-flight provisional surrogates.
    Bail-on-first-match policy with all-matches accounting for the result.
    """
    haystack = payload.casefold()
    matches: list[tuple[str, str]] = []  # (entity_type, value) — never logged raw
    candidates: list[tuple[str, str]] = []
    for ent in registry.entries():
        candidates.append((ent.entity_type, ent.real_value))
    if provisional:
        for real_value in provisional:
            candidates.append(("PERSON", real_value))  # provisional set is PERSON-only
    for entity_type, value in candidates:
        pattern = r"\b" + re.escape(value.casefold()) + r"\b"
        if re.search(pattern, haystack):
            matches.append((entity_type, value))
    return EgressResult(
        tripped=bool(matches),
        match_count=len(matches),
        entity_types=sorted({t for t, _ in matches}),
        match_hashes=sorted({_hash8(v) for _, v in matches}),
    )

class _EgressBlocked(Exception):
    """Internal-only: caught by the fallback wrapper, never raised to chat loop."""
    def __init__(self, result: EgressResult):
        self.result = result
        super().__init__("egress filter blocked cloud call")
```

**Public client surface** (D-49 single class, provider-aware branch, fallback wrapper):
```python
class LLMProviderClient:
    """Single class; all 5 future features dispatch through .call(feature=...)."""

    @traced(name="llm_provider.call")
    async def call(
        self,
        feature: Literal["entity_resolution", "missed_scan", "fuzzy_deanon", "title_gen", "metadata"],
        messages: list[dict],
        registry: "ConversationRegistry | None" = None,
        provisional_surrogates: dict[str, str] | None = None,
    ) -> dict:
        provider, source = _resolve_provider(feature)
        # ... build payload, call, log per D-63, return parsed dict.
        # On cloud + egress trip: raise _EgressBlocked, caught by caller's
        # algorithmic-fallback wrapper (D-52, D-54).
```

**Error-handling pattern** (D-52 / D-54): the `LLMProviderClient` raises `_EgressBlocked` and the call-site (Plan 06 / `redaction_service.py`) catches it and reverts to the already-computed algorithmic clustering result. Network/5xx are caught at the SDK boundary; algorithmic fallback engaged identically. NEVER re-raise to the chat loop (NFR-3 invariant).

---

### `backend/app/services/redaction/nicknames_id.py` (NEW — utility, static lookup)

**Analog:** `backend/app/services/redaction/gender_id.py` — exact match.

**Module shape** (D-46, mirrors `gender_id.py:1-49` exactly):
```python
"""Indonesian-aware nickname → canonical first-name lookup (D-46, RESOLVE-02).

Why this exists:
- PRD FR-4.2 sub-surrogate derivation requires merging "Danny" into the same
  cluster as "Daniel"; an embedded Python dict gives O(1) lookup with zero
  runtime cost beyond the import.
- Indonesian-first coverage; small English block for completeness.

Conventions (mirror gender_id.py):
- Keys are lower-cased, ASCII-folded nicknames (no honorifics).
- Values are the canonical first name (lower-cased).
- Lookup is case-insensitive; callers .casefold() the raw nickname.
- When ambiguous (e.g., "Iwan" → "Suherman" or "Setiawan"), pick the first
  match deterministically and log the ambiguity at DEBUG (OBS-02).
"""
from __future__ import annotations

# fmt: off
_INDONESIAN_NICKNAMES: dict[str, str] = {
    "bambs": "bambang",
    "joko": "joko",            # itself canonical; included for round-trip safety
    "yoyok": "joko",
    "tini": "kartini",
    "wati": "watini",
    # ... add ~30-50 entries
    # English block:
    "danny": "daniel",
    "bob": "robert",
    "rob": "robert",
}
# fmt: on


def lookup_nickname(nickname: str) -> str | None:
    """Return the canonical first name for a nickname, or None if absent."""
    return _INDONESIAN_NICKNAMES.get(nickname.casefold())
```

**Logging-on-ambiguity hook** — caller-side logging at DEBUG (per D-46) is the right home; this module stays pure.

---

### `backend/app/services/redaction/clustering.py` (NEW — service, transform)

**Analog:** `backend/app/services/redaction/anonymization.py` (for module shape and right-to-left transform discipline) + `backend/app/services/redaction/name_extraction.py` (for nameparser wrapper pattern). Claude's Discretion may inline this into `anonymization.py`.

**Imports + module-docstring pattern** (mirror `anonymization.py:1-58`):
```python
"""Union-Find clustering + sub-surrogate variant generator (D-45..D-48, RESOLVE-02).

Pre-Faker step: take the flat list of detected PERSON Entity spans and produce
a list of Cluster objects, where each Cluster carries:
  - canonical: the longest matched real name in the cluster
  - variants: set[str] — first-only / last-only / honorific-prefixed / nickname rows
  - members: list[Entity] — every span that belongs to this cluster

Mechanics:
- Union-Find (D-45): runs INSIDE redact_text BEFORE Faker generation.
- Indonesian-aware nickname dict (D-46): lookups via nicknames_id.lookup_nickname.
- Strict PRD merge (D-47): solo first-or-last partial-match merges only when
  EXACTLY one cluster has it; ambiguity → its own cluster (logs at DEBUG).
- Sub-surrogate variant set (D-48): computed once per cluster; honorifics
  sourced from honorifics.py constant set; first/last decomposition via
  name_extraction.extract_name_tokens.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from app.services.redaction.detection import Entity
from app.services.redaction.honorifics import strip_honorific  # honorific source
from app.services.redaction.name_extraction import extract_name_tokens
from app.services.redaction.nicknames_id import lookup_nickname

logger = logging.getLogger(__name__)
```

**Cluster dataclass** (mirror `EntityMapping` frozen-Pydantic shape from Phase 2 D-22 — use frozen `dataclass` here since Cluster doesn't cross the DB boundary):
```python
@dataclass(frozen=True)
class Cluster:
    canonical: str                     # the longest real name in the cluster
    variants: frozenset[str]           # first-only, last-only, honorific-prefixed, nickname
    members: tuple[Entity, ...]        # all detected spans in this cluster
```

**Union-Find skeleton** (`anonymization.py:172-189` is the closest pattern for "iterate spans, decide per-span, write deterministic output"; for Union-Find use a `parent: dict[str, str]` keyed by `casefold(real_value)`):
```python
def cluster_persons(person_entities: list[Entity]) -> list[Cluster]:
    """D-45: Union-Find over detected PERSON spans.
    D-47: ambiguous solo first/last → its own cluster (no wrong merges).
    D-48: variant set computed eagerly (caller writes one row per variant)."""
    # 1. Initialize parent[v] = v for every distinct casefolded real value.
    # 2. For each pair (a, b) in person_entities:
    #      if shared-last-name AND exactly-one-cluster-has-it: union.
    #      if nickname(a) == canonical-of(b)'s first-name token: union.
    #    Skip union otherwise (D-47 strict refuse-ambiguous).
    # 3. Walk the parent map; for each root, build a Cluster:
    #      - canonical = longest real_value among members
    #      - variants = {first_only, last_only, honorific_prefixed, nickname_form}
    #        (deduped via frozenset)
    # 4. Log: clusters_formed=N, cluster_size_max=M (NEVER values; D-18 / D-55).
    ...
```

**Variant-set generator** (D-48, compose `extract_name_tokens` + `honorifics.strip_honorific` + `nicknames_id.lookup_nickname`):
```python
def variants_for(canonical: str) -> frozenset[str]:
    """D-48: derive {canonical, first-only, last-only, Pak/Bu-prefixed, nickname}."""
    honorific, bare = strip_honorific(canonical)
    tokens = bare.split()
    variants: set[str] = {canonical, bare}
    if len(tokens) >= 1:
        variants.add(tokens[0])             # first-only ("Daniel")
    if len(tokens) >= 2:
        variants.add(tokens[-1])            # last-only ("Walsh")
    # Honorific-prefixed: only if Phase 1 stripped one (else identity).
    if honorific:
        for v in list(variants):
            variants.add(f"{honorific} {v}")
    # Nickname: reverse-lookup the canonical first-name to get any nickname forms.
    # (Forward lookup not needed here — this is for variant ROW WRITES, which
    # happen after the cluster is formed.)
    return frozenset(variants)
```

---

### `backend/app/services/redaction/anonymization.py` (MODIFIED — service, transform)

**Analog:** self (Phase 1 + Phase 2 D-37 baseline; Phase 3 D-45/D-48 changes the input shape).

**Current function signature** (lines 192-218):
```python
def anonymize(
    masked_text: str,
    entities: list[Entity],
    registry: "ConversationRegistry | None" = None,
) -> tuple[str, dict[str, str], int]:
    """Substitute entities right-to-left to keep offsets stable.
    Returns (anonymized_text, entity_map, hard_redacted_count)."""
```

**Faker call site** (lines 271-275, inside `anonymize`):
```python
existing = entity_map.get(ent.text) or next(
    (v for k, v in entity_map.items() if k.lower() == ent.text.lower()),
    None,
)
if existing is not None:
    replacement = existing
else:
    replacement = _generate_surrogate(
        ent, faker, forbidden_tokens, used_surrogates
    )
    entity_map[ent.text] = replacement
    used_surrogates.add(replacement)
```

The actual Faker dispatch is `_generate_surrogate` (lines 148-189) → `_faker_call` (lines 120-145).

**Where Phase 2 D-37 forbidden_tokens is applied** (lines 220-230):
```python
real_persons = [e.text for e in entities if e.type == "PERSON"]
# D-07: build the per-call forbidden-token set from real PERSON names.
bare_persons = [strip_honorific(name)[1] for name in real_persons]
# D-07 / D-37: per-call ∪ per-thread forbidden-token set. Per-PERSON only (D-38).
call_forbidden = extract_name_tokens(bare_persons)
if registry is not None:
    forbidden_tokens = call_forbidden | registry.forbidden_tokens()
else:
    forbidden_tokens = call_forbidden
```

These tokens then flow into `_generate_surrogate(..., forbidden_tokens, ...)` (line 272), which is inside the right-to-left rewrite loop.

**Phase 3 input-shape change (pseudo-diff for D-45/D-48):**
```diff
  def anonymize(
      masked_text: str,
-     entities: list[Entity],
+     clusters: list[Cluster],            # D-45: pre-clustered PERSON groups
+     non_person_entities: list[Entity],  # D-62: emails/phones/URLs flow through unchanged
      registry: "ConversationRegistry | None" = None,
  ) -> tuple[str, dict[str, str], int]:
      faker = get_faker()
-     real_persons = [e.text for e in entities if e.type == "PERSON"]
+     # D-37 still PERSON-only (D-38). With clusters, expand from EVERY member of
+     # every cluster — every variant a real value the cluster represents.
+     real_persons = [m.text for c in clusters for m in c.members]
      bare_persons = [strip_honorific(name)[1] for name in real_persons]
      call_forbidden = extract_name_tokens(bare_persons)
      if registry is not None:
          forbidden_tokens = call_forbidden | registry.forbidden_tokens()
      else:
          forbidden_tokens = call_forbidden

      entity_map: dict[str, str] = {}
      used_surrogates: set[str] = set()
      hard_redacted_count = 0
      out = masked_text

-     for ent in sorted(entities, key=lambda e: e.start, reverse=True):
+     # NEW (D-45 / D-48): one Faker surrogate per CLUSTER, shared by all variants.
+     # Per-cluster surrogate generation runs ONCE; the resulting canonical
+     # surrogate seeds variant rows (D-48: first-only, last-only, honorific-prefixed,
+     # nickname → derived sub-surrogates).
+     cluster_surrogate: dict[str, str] = {}  # casefold(canonical) → surrogate
+     for cluster in clusters:
+         key = cluster.canonical.casefold()
+         if registry is not None:
+             hit = registry.lookup(cluster.canonical)
+             if hit is not None:
+                 cluster_surrogate[key] = hit
+                 continue
+         # Synthesize a single Entity for the canonical to drive _generate_surrogate;
+         # collision-budget + forbidden-token check still apply.
+         pseudo = Entity(text=cluster.canonical, type="PERSON",
+                         start=0, end=len(cluster.canonical),
+                         bucket="surrogate")
+         surrogate = _generate_surrogate(pseudo, faker, forbidden_tokens, used_surrogates)
+         cluster_surrogate[key] = surrogate
+         used_surrogates.add(surrogate)
+
+     # Right-to-left rewrite: every PERSON span (any variant) maps to its
+     # cluster's canonical surrogate; every variant ROW WRITE happens later
+     # in the registry upsert (D-48), keyed off cluster_surrogate.
+     all_spans = [
+         (m, cluster_surrogate[c.canonical.casefold()])
+         for c in clusters for m in c.members
+     ] + [(e, None) for e in non_person_entities]
+     for ent, cluster_replacement in sorted(
+         all_spans, key=lambda pair: pair[0].start, reverse=True,
+     ):
          if ent.bucket == "redact":
              replacement = f"[{ent.type}]"  # D-08
              hard_redacted_count += 1
+         elif cluster_replacement is not None:
+             # PERSON: cluster surrogate already chosen.
+             replacement = cluster_replacement
+             entity_map[ent.text] = replacement
          else:
-             # ... existing per-entity registry lookup + Faker fallback ...
+             # Non-PERSON path unchanged from Phase 1 + Phase 2.
+             ...
          out = out[: ent.start] + replacement + out[ent.end :]

      return out, entity_map, hard_redacted_count
```

**Note for the planner:** D-37 forbidden-token expansion still applies — what changes is the *source* of `real_persons` (now flattened from cluster members) not the algorithm. The Faker collision budget / `used_surrogates` set / forbidden-token check inside `_generate_surrogate` remain untouched.

---

### `backend/app/services/redaction_service.py` (MODIFIED — service, orchestrator)

**Analog:** self (Phase 2 D-30 critical section).

**Pattern to extend** (Phase 2 baseline `_redact_text_with_registry`):
1. Acquire per-thread asyncio.Lock (Phase 2 D-29/D-30 — already present at `redaction_service.py:120-134`).
2. Detect entities (Phase 1 — already present).
3. **NEW Phase 3 (D-45 / D-61):** branch on `entity_resolution_mode`:
   - `algorithmic`: call `clustering.cluster_persons(person_entities)` → `list[Cluster]`.
   - `llm`: pre-cluster algorithmically (provisional surrogates), then call `LLMProviderClient.call("entity_resolution", ...)`; on `_EgressBlocked` or any failure → fall back to algorithmic clusters (D-52 / D-54). Cloud sees only provisional surrogates (D-49); local sees raw real names (FR-9.2).
   - `none`: pass-through — each unique string gets its own pseudo-cluster (Claude's Discretion: explicit pass-through with a `mode="none"` span tag for OBS clarity).
4. Pass clusters + non-person entities to `anonymize(...)` (revised signature per pseudo-diff above).
5. **NEW Phase 3 (D-48):** for each cluster, write ALL variant rows via `registry.upsert_delta(...)` — single batched `INSERT ... ON CONFLICT DO NOTHING` (mirror Phase 2 D-32).
6. Build `entity_map` for de-anon using ALL variant rows (existing call already handles this).
7. Release the lock; return `RedactionResult`.

**Span-attributes pattern to extend** (Phase 2 D-41 + Phase 3 D-63):
```python
# Phase 2 already sets resolution-related counts; Phase 3 ADDS:
span.set_attribute("resolution_mode", mode)                     # algorithmic|llm|none
span.set_attribute("clusters_formed", len(clusters))
span.set_attribute("cluster_size_max", max((len(c.members) for c in clusters), default=0))
span.set_attribute("clusters_merged_via", merge_source)         # algorithmic|llm|none
if mode == "llm":
    span.set_attribute("provider_resolved", provider)           # local|cloud
    span.set_attribute("provider_fallback", fallback_engaged)
    if provider == "cloud":
        span.set_attribute("egress_tripped", egress_tripped)
# NEVER set real-value attributes (B4 / D-18 invariant).
```

---

### `backend/app/config.py` (MODIFIED — config, env-var read)

**Analog:** self (Phase 1's `pii_*` block + `tracing_provider` field).

**Pattern (Phase 1 baseline):**
```python
class Settings(BaseSettings):
    # ...
    pii_redaction_enabled: bool = False
    pii_surrogate_locale: str = "id_ID"
    tracing_provider: str = ""
    # ...
```

**Phase 3 ADDS** (D-50 / D-51 / D-57; ~12 fields total):
```python
    # Phase 3: Entity resolution mode + LLM provider
    entity_resolution_mode: Literal["algorithmic", "llm", "none"] = "algorithmic"
    llm_provider: Literal["local", "cloud"] = "local"
    llm_provider_fallback_enabled: bool = False
    llm_provider_timeout_seconds: int = 30  # D-50

    # Per-feature overrides (None = inherit global)
    entity_resolution_llm_provider: Literal["local", "cloud"] | None = None
    missed_scan_llm_provider: Literal["local", "cloud"] | None = None
    title_gen_llm_provider: Literal["local", "cloud"] | None = None
    metadata_llm_provider: Literal["local", "cloud"] | None = None
    fuzzy_deanon_llm_provider: Literal["local", "cloud"] | None = None

    # Endpoints + creds
    local_llm_base_url: str = "http://localhost:1234/v1"
    local_llm_model: str = "llama-3.1-8b-instruct"
    cloud_llm_base_url: str = "https://api.openai.com/v1"
    cloud_llm_model: str = "gpt-4o-mini"
    cloud_llm_api_key: str = ""  # D-58: env-only

    # Phase 4 forward-compat (ship column + setting now per D-57)
    pii_missed_scan_enabled: bool = True
```

---

### `supabase/migrations/030_pii_provider_settings.sql` (NEW — migration, DDL)

**Analog:** `supabase/migrations/029_pii_entity_registry.sql` (Phase 2; for header/comment style + RLS). For the ALTER TABLE shape on `system_settings`, the planner must `grep` the migrations directory for the most recent `system_settings` ALTER and mirror its column-add idiom (CLAUDE.md gotcha: never edit applied migrations).

**Pattern to follow** (Phase 2 D-60 + D-57; CHECK constraints mirror Pydantic Literals exactly):
```sql
-- 030_pii_provider_settings.sql
-- D-57 / D-60: extend system_settings with mode + provider + per-feature override columns.
-- DB CHECK constraints mirror the Pydantic Literal sets; defense in depth (FR-9, NFR-2).

alter table system_settings
  add column entity_resolution_mode text not null default 'algorithmic'
    check (entity_resolution_mode in ('algorithmic','llm','none')),
  add column llm_provider text not null default 'local'
    check (llm_provider in ('local','cloud')),
  add column llm_provider_fallback_enabled boolean not null default false,
  add column entity_resolution_llm_provider text null
    check (entity_resolution_llm_provider in ('local','cloud')),
  add column missed_scan_llm_provider text null
    check (missed_scan_llm_provider in ('local','cloud')),
  add column title_gen_llm_provider text null
    check (title_gen_llm_provider in ('local','cloud')),
  add column metadata_llm_provider text null
    check (metadata_llm_provider in ('local','cloud')),
  add column fuzzy_deanon_llm_provider text null
    check (fuzzy_deanon_llm_provider in ('local','cloud')),
  add column pii_missed_scan_enabled boolean not null default true;

-- system_settings already has RLS + service-role-only policy from earlier
-- migrations; no policy changes needed here (Phase 2 D-25 invariant carries).
```

**Use `/create-migration`** to generate the file scaffold (CLAUDE.md `/create-migration` skill auto-numbers).

---

### `backend/app/routers/admin_settings.py` (MODIFIED — router, request-response)

**Analog:** self (existing `SystemSettingsUpdate` Pydantic model + PATCH handler at lines 14-53).

**Imports pattern** (lines 1-9 — already correct):
```python
from typing import Literal
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from app.dependencies import require_admin
from app.services.audit_service import log_action
from app.services.system_settings_service import (
    get_system_settings,
    update_system_settings,
)
```

**Auth pattern** (line 33, 40): `Depends(require_admin)` — reused as-is for the new endpoint.

**Existing Literal-typed field** (line 29 — exact pattern Phase 3 D-60 mirrors):
```python
rag_rerank_mode: Literal["none", "llm", "cohere"] | None = None
```

**Phase 3 EXTENDS `SystemSettingsUpdate`** (D-60):
```python
class SystemSettingsUpdate(BaseModel):
    # ... existing fields ...
    rag_rerank_mode: Literal["none", "llm", "cohere"] | None = None

    # Phase 3 ADDS:
    entity_resolution_mode: Literal["algorithmic", "llm", "none"] | None = None
    llm_provider: Literal["local", "cloud"] | None = None
    llm_provider_fallback_enabled: bool | None = None
    entity_resolution_llm_provider: Literal["local", "cloud"] | None = None
    missed_scan_llm_provider: Literal["local", "cloud"] | None = None
    title_gen_llm_provider: Literal["local", "cloud"] | None = None
    metadata_llm_provider: Literal["local", "cloud"] | None = None
    fuzzy_deanon_llm_provider: Literal["local", "cloud"] | None = None
    pii_missed_scan_enabled: bool | None = None
```

**PATCH handler** (lines 37-53 — unchanged; `model_dump(exclude_none=True)` automatically picks up the new fields).

**Audit pattern** (lines 46-52 — unchanged; `details={"changed_fields": list(updates.keys())}` already includes new fields automatically).

**NEW endpoint** (D-58 — masked status badge backing endpoint):
```python
@router.get("/settings/llm-provider-status")
async def get_llm_provider_status(user: dict = Depends(require_admin)):
    """D-58: never returns the raw cloud key — only configured/missing booleans."""
    from app.config import get_settings
    settings = get_settings()
    cloud_key_configured = bool(settings.cloud_llm_api_key)
    # Local-endpoint reachability: probe LOCAL_LLM_BASE_URL/v1/models with a
    # short timeout. Claude's Discretion: sync on this endpoint, async on the
    # frontend; both acceptable per CONTEXT.md.
    local_endpoint_reachable = await _probe_local_endpoint(settings.local_llm_base_url)
    return {
        "cloud_key_configured": cloud_key_configured,
        "local_endpoint_reachable": local_endpoint_reachable,
    }
```

---

### `frontend/src/pages/AdminSettingsPage.tsx` (MODIFIED — component, UI form → PATCH)

**Analog:** self (existing `activeSection` state + side-nav pattern; NOT an accordion).

**Existing section pattern (NOT to be re-architected):**
```tsx
// frontend/src/pages/AdminSettingsPage.tsx

type AdminSection = 'llm' | 'embedding' | 'rag' | 'tools' | 'hitl'

const SECTIONS: { id: AdminSection; icon: typeof Brain; labelKey: string }[] = [
  { id: 'llm', icon: Brain, labelKey: 'admin.llm.title' },
  { id: 'embedding', icon: Database, labelKey: 'admin.embedding.title' },
  { id: 'rag', icon: Settings2, labelKey: 'admin.rag.title' },
  { id: 'tools', icon: Wrench, labelKey: 'admin.tools.title' },
  { id: 'hitl', icon: ShieldCheck, labelKey: 'admin.hitl.title' },
]

const [activeSection, setActiveSection] = useState<AdminSection>('llm')

// Section nav (line 166-180):
{SECTIONS.map(({ id, icon: Icon, labelKey }) => (
  <button
    key={id}
    onClick={() => setActiveSection(id)}
    className={`... ${activeSection === id ? 'bg-primary/10 text-primary' : '...'}`}
  >
    <Icon className="w-4 h-4" />
    {t(labelKey)}
  </button>
))}

// Section bodies (lines 199-433):
{activeSection === 'llm' && (
  <section className="space-y-4">
    {/* Card with Label + Select + Input pattern; uses i18n via t() */}
  </section>
)}

{activeSection === 'rag' && (
  <section className="space-y-4">
    {/* This section already shows the Literal-typed Select pattern for rag_rerank_mode */}
  </section>
)}
```

**For Phase 3** (D-59), add EXACTLY three things:

1. Extend the `AdminSection` union — add `'pii'`:
```tsx
type AdminSection = 'llm' | 'embedding' | 'rag' | 'tools' | 'hitl' | 'pii'
```

2. Append a `SECTIONS` entry (use `Shield` from lucide-react for the icon — fits the security framing):
```tsx
const SECTIONS = [
  // ... existing entries ...
  { id: 'pii', icon: Shield, labelKey: 'admin.pii.title' },
]
```

3. Add a new section block after the existing `{activeSection === 'hitl' && (...)}`:
```tsx
{activeSection === 'pii' && (
  <section className="space-y-4">
    {/* D-59 form fields:
        - Mode radio: algorithmic | llm | none  (entity_resolution_mode)
        - Provider radio: local | cloud         (llm_provider)
        - 5 per-feature override Selects: Inherit | local | cloud
            (entity_resolution_llm_provider, missed_scan_llm_provider,
             title_gen_llm_provider, metadata_llm_provider,
             fuzzy_deanon_llm_provider)
        - Fallback Toggle: llm_provider_fallback_enabled
        - Cloud-key status Badge: from GET /admin/settings/llm-provider-status
        - Local-endpoint status Badge: same endpoint
        - Missed-PII secondary scan Toggle: pii_missed_scan_enabled (Phase 4 consumes)
        Save button → existing PATCH /admin/settings handler.
        i18n via I18nProvider + t(); strings under admin.pii.* */}
  </section>
)}
```

**i18n pattern** (mirror existing `admin.llm.*`, `admin.rag.*` keys): add `admin.pii.title`, `admin.pii.mode.label`, `admin.pii.mode.algorithmic`, `admin.pii.mode.llm`, `admin.pii.mode.none`, `admin.pii.provider.label`, `admin.pii.cloudKey.configured`, `admin.pii.cloudKey.missing`, etc., to BOTH the `id` and `en` translation files referenced by `I18nProvider`.

**Form-element library** — the page already uses shadcn/ui Label + Select + Input + Switch + Badge. Use the same set; do NOT introduce new primitives. The existing `rag` section (lines 199-433 vicinity) is the canonical Literal-typed Select reference.

**No glass on this section.** Persistent admin form panels are not transient overlays (CLAUDE.md design rule).

---

### `backend/tests/api/test_resolution_and_provider.py` (NEW — test, integration)

**Analog:** `backend/tests/api/test_redaction_registry.py` (Phase 2; per-SC test classes, live DB, asyncio race).

**Pattern (mirror Phase 2 verification structure — one test class per SC, SC#5 hits live Supabase):**
```python
import pytest
from unittest.mock import AsyncMock, patch

class TestSC1_AlgorithmicClustering:
    """SC#1: Bambang Sutrisno / Pak Bambang / Sutrisno / Bambang collapse to one cluster."""
    @pytest.mark.asyncio
    async def test_four_variants_one_canonical_surrogate(self, ...):
        # ... assert single canonical surrogate; assert 4 variant rows in entity_registry ...

class TestSC2_CloudEgressFallback:
    """SC#2: cloud LLM mode + payload-with-real-value → trip → algorithmic fallback."""
    @pytest.mark.asyncio
    async def test_egress_trip_falls_back_to_algorithmic(self, monkeypatch):
        # Mock AsyncOpenAI; inject payload containing a registered value;
        # assert _EgressBlocked triggered fallback; assert algorithmic result returned;
        # assert mock recorded ZERO actual cloud invocations after the trip.
        ...

class TestSC3_LocalLLMRawNames:
    """SC#3: local LLM mode sees raw real names, never invokes egress filter."""
    @pytest.mark.asyncio
    async def test_local_mode_bypasses_egress(self, monkeypatch):
        ...

class TestSC4_NonPersonNormalization:
    """SC#4: emails/phones/URLs go through normalize-only path, never reach LLM."""
    @pytest.mark.asyncio
    async def test_resolution_payload_contains_only_person_strings(self):
        ...

class TestSC5_AdminUIPropagatesWithin60s:
    """SC#5: PATCH /admin/settings llm_provider=cloud → cache TTL → next call uses cloud."""
    @pytest.mark.asyncio
    async def test_provider_switch_propagates(self, ...):
        # PATCH; sleep cache TTL; assert _resolve_provider returns 'cloud' WITHOUT redeploy.
        ...
```

---

### `backend/tests/unit/test_llm_provider_client.py` (NEW — test, unit, mocked SDK)

**Analog:** Phase 2 unit tests that mock async clients + any service unit test using `pytest-mock` `mocker.AsyncMock`.

**Pattern (D-65 fixture: in-memory FastAPI mock at `localhost:9999/v1/chat/completions` for the local-LLM path; AsyncOpenAI mock for the cloud path):**
```python
import pytest
from unittest.mock import AsyncMock, patch
from app.services.llm_provider import LLMProviderClient, _resolve_provider, _EgressBlocked

class TestResolveProvider:
    """D-51 resolution order: feature_env > feature_db > global_env > global_db > default."""
    def test_feature_env_wins_over_db(self, monkeypatch): ...
    def test_feature_db_wins_over_global_env(self, monkeypatch): ...
    def test_default_local_when_nothing_set(self, monkeypatch): ...

class TestProviderClientLocalMode:
    """Local mode bypasses egress filter; sees raw real names."""
    @pytest.mark.asyncio
    async def test_local_call_no_egress_invocation(self, mock_local_endpoint): ...

class TestProviderClientCloudMode:
    """Cloud mode wraps payload with egress filter; raises _EgressBlocked on trip."""
    @pytest.mark.asyncio
    async def test_cloud_egress_trip_raises_internal_exception(self, monkeypatch): ...
    @pytest.mark.asyncio
    async def test_cloud_clean_payload_passes_through(self, monkeypatch): ...

class TestProviderClientFallback:
    """D-52: on cloud failure (network/5xx/invalid/egress) → caller sees algorithmic."""
    @pytest.mark.asyncio
    async def test_5xx_triggers_algorithmic_fallback(self, monkeypatch): ...
```

---

### `backend/tests/unit/test_egress_filter.py` (NEW — test, unit, pure function)

**Analog:** `backend/tests/unit/test_redaction_anonymization.py` (Phase 1; table-driven tests over a pure function).

**Pattern (D-66 exhaustive matrix — table-driven, single test class):**
```python
import pytest
from app.services.llm_provider import egress_filter, EgressResult

class TestEgressFilter:
    """D-53/D-56 exhaustive matrix."""
    def test_exact_match_casefold_trips(self): ...
    def test_word_boundary_johnson_does_not_trip_on_john(self): ...
    def test_multi_word_value_trips_on_substring(self): ...
    def test_registry_only_path(self): ...
    def test_provisional_only_path(self): ...
    def test_empty_inputs_no_trip(self): ...
    def test_log_content_invariant_no_raw_values(self, caplog):
        # Parse the captured log line; assert no raw values appear (B4 / D-55).
        ...
```

**Caplog invariant pattern** (mirror Phase 2's `TestSC6_LogPrivacy`): assert against a list of forbidden raw-PII strings; assert each is absent from `caplog.text`.

---

## Shared Patterns

### `@traced` decorator on every new public service method
**Source:** `backend/app/services/tracing_service.py` + every `@traced`-decorated method in `embedding_service.py`, `redaction_service.py`, `anonymization.py`.
**Apply to:** `LLMProviderClient.call`, `egress_filter` (optional — pure functions can be traced when latency matters), every new orchestration entry point in `redaction_service.py`.
**Excerpt** (`embedding_service.py:14`):
```python
@traced
async def embed_text(self, text: str, model: str | None = None) -> list[float]:
    ...
```
**Phase 3 form (parenthesised, with `name=` per D-49):**
```python
@traced(name="llm_provider.entity_resolution")
async def call(self, feature, ...): ...
```

### Service-role DB access for system tables
**Source:** `backend/app/services/system_settings_service.py:16` (`get_supabase_client()`) and `backend/app/services/redaction/registry.py` (Phase 2 D-25).
**Apply to:** Migration 030 needs no new RLS; existing `system_settings` policy carries. Variant-row writes in Plan-06 use `get_supabase_client()` (Phase 2 D-25 invariant).
**Excerpt:**
```python
client = get_supabase_client()  # service-role bypasses RLS
result = client.table("system_settings").select("*").eq("id", 1).single().execute()
```

### Admin-mutation audit log
**Source:** `backend/app/routers/admin_settings.py:46-52`.
**Apply to:** Existing PATCH already audits via `log_action(action="update", resource_type="system_settings", details={"changed_fields": [...]})` — Phase 3 mutation of new fields is automatically audited; no new code needed.
**Excerpt:**
```python
log_action(
    user_id=user["id"],
    user_email=user["email"],
    action="update",
    resource_type="system_settings",
    details={"changed_fields": list(updates.keys())},
)
```

### `require_admin` dependency on every admin endpoint
**Source:** `backend/app/dependencies.py` + `backend/app/routers/admin_settings.py:33,40`.
**Apply to:** New `GET /admin/settings/llm-provider-status` endpoint (D-58).
**Excerpt:**
```python
async def get_llm_provider_status(user: dict = Depends(require_admin)):
    ...
```

### Pydantic `Literal` validation + DB CHECK constraint defense in depth
**Source:** `backend/app/routers/admin_settings.py:29` (`rag_rerank_mode: Literal[...]`) + the matching `CHECK` in the migration that introduced it.
**Apply to:** All 8 new mode/provider columns added in migration 030. Mirror the Literal sets exactly. Tests assert API rejects bad enum (422) AND DB rejects direct SQL with bad enum (23514). (Phase 3 D-60.)

### Counts + 8-char SHA-256 hashes only in PII-adjacent log lines (B4 / D-55)
**Source:** Phase 1 D-18 / Phase 2 D-41 / `anonymization.py:278-283`.
**Apply to:** Every new logger call in `llm_provider.py`, `clustering.py`, `egress_filter`. Egress-filter trip log uses `match_hashes: list[str]` (sha256 first 8 chars), NEVER raw values, NEVER first-N-chars-of-value.

### Lazy module-level singleton with cache key
**Source:** `backend/app/services/redaction/anonymization.py:64-74` (`@lru_cache get_faker()`); embedding service's `__init__`-bound client; `gender_id._INDONESIAN_GENDER`.
**Apply to:** `LLMProviderClient`'s per-provider `AsyncOpenAI` clients cached in module-level `_clients: dict[str, AsyncOpenAI]`; `nicknames_id._INDONESIAN_NICKNAMES` frozen module-level dict.

### asyncio.Lock critical-section composition (Phase 2 D-30 invariant)
**Source:** `backend/app/services/redaction_service.py:68-69, 120-134`.
**Apply to:** Phase 3's clustering + variant-row write step runs INSIDE the existing per-thread asyncio.Lock. No new lock surface; no new lock-master. The `_thread_locks_master` invariant from Phase 2 D-30 is non-negotiable (D-61).

### i18n via `I18nProvider` + `t()` on every admin-page string
**Source:** Existing `frontend/src/pages/AdminSettingsPage.tsx` section bodies.
**Apply to:** All new strings in the `'pii'` section. Add Indonesian (default) + English entries to both translation files referenced by `I18nProvider`. Pattern is `t('admin.pii.<key>')`.

## No Analog Found

(None — every Phase 3 file has a clear codebase analog within the same service tree or sibling redaction module.)

## Metadata

**Analog search scope:**
- `backend/app/services/redaction/` (Phase 1+2 modules)
- `backend/app/services/` (top-level services for client + tracing + audit + system-settings)
- `backend/app/routers/admin_settings.py` (admin PATCH + Literal validation)
- `backend/app/config.py` (Settings class shape)
- `supabase/migrations/029_*.sql` (Phase 2 migration as DDL template)
- `frontend/src/pages/AdminSettingsPage.tsx` (admin UI section pattern)
- `backend/tests/api/test_redaction_registry.py` + `backend/tests/unit/` (Phase 2 test patterns)

**Files scanned:** ~28 (all Phase 1+2 redaction modules, embedding service, tracing service, system-settings service, admin-settings router + dependencies, audit service, AdminSettingsPage, migration 029, Phase 2 verification report for SC↔file mapping).

**Pattern extraction date:** 2026-04-26

## PATTERN MAPPING COMPLETE

**Phase:** 3 - Entity Resolution & LLM Provider Configuration
**Files classified:** 13
**Analogs found:** 13 / 13

### Coverage
- Files with exact analog: 9
- Files with role-match analog: 4
- Files with no analog: 0

### Key Patterns Identified
- All admin-settings flow uses one model (`SystemSettingsUpdate`), one PATCH endpoint, one `log_action` audit row — Phase 3 EXTENDS rather than parallels.
- Lazy module-level singletons (Faker, gender table, settings cache) are the project's idiomatic stateless-service shape — Phase 3 follows for `AsyncOpenAI` clients + `nicknames_id` dict.
- `@traced` decoration + counts-and-timings-only logging (B4 / D-18 / D-55) is non-negotiable for every new service method touching PII-adjacent data.
- The frontend admin page is a section-state machine (`activeSection` + `SECTIONS` array + conditional `<section>` blocks); Phase 3 adds one entry to each of those three structures, never a new page or layout.
- `Literal[...]` Pydantic field + matching `CHECK` constraint is the codebase's defense-in-depth pattern for enum-like settings — Phase 3 D-60 mirrors `rag_rerank_mode` exactly.

### File Created
`.planning/phases/03-entity-resolution-llm-provider-configuration/03-PATTERNS.md`

### Ready for Planning
Pattern mapping complete. Planner can now reference analog patterns in PLAN.md files for each Phase 3 plan (provider client, egress filter, clustering, anonymization revision, redaction-service wiring, migration 030, admin router extension, AdminSettingsPage section, three test files).
