---
phase: 1
plan_number: 06
title: "Anonymization module + RedactionService composition + lifespan warm-up"
wave: 3
depends_on: [01, 02, 03, 04, 05]
requirements: [ANON-01, ANON-02, ANON-03, ANON-04, ANON-05, ANON-06, PERF-01, OBS-01]
files_modified:
  - backend/app/services/redaction/anonymization.py
  - backend/app/services/redaction_service.py
  - backend/app/services/redaction/__init__.py
  - backend/app/main.py
autonomous: true
must_haves:
  - "`get_redaction_service()` returns an `@lru_cache`'d `RedactionService` singleton; `await service.redact_text(text)` returns a `RedactionResult` with fields `anonymized_text`, `entity_map` (real -> surrogate, no hard-redact entries), `hard_redacted_count`, `latency_ms`."
  - "Surrogate-bucket entities replaced with Faker `id_ID` values; PERSON gender-matched via `gender_id.lookup_gender` then `gender-guesser` fallback; ambiguous -> random (D-04, D-05, ANON-04)."
  - "Hard-redact-bucket entities render as `[ENTITY_TYPE]` placeholders verbatim; same placeholder for every instance of a type within one call (D-08, ANON-02)."
  - "Surrogate generation rejects Faker output whose name tokens overlap real first-name/surname tokens; up to 10 retries then fallback `[PERSON_<6-char-blake2b-hex>]` via `hashlib.blake2b(real.encode(), digest_size=3).hexdigest().upper()` (D-06, D-07, ANON-03, ANON-05)."
  - "FastAPI lifespan calls `get_redaction_service()` once after `configure_tracing()` so Presidio + Faker + gender detector load before the first request (PERF-01, D-15)."
  - "Anonymization is purely programmatic find-and-replace - no LLM call (ANON-06)."
  - "`backend/app/services/redaction/__init__.py` exposes ONLY `RedactionError` (imported from `app.services.redaction.errors`); does NOT re-export `RedactionResult` / `RedactionService` / `get_redaction_service` — those are imported from `app.services.redaction_service` directly. This breaks the circular import chain identified by checker B2 (option B)."
  - "`redact_text` calls `detect_entities` exactly once and uses the returned `(masked_text, entities, sentinels)` 3-tuple directly; `apply_uuid_mask` is NOT called from `redaction_service.py` (W10)."
  - "Logger calls in `anonymization.py` and `redaction_service.py` NEVER include real entity values (`entity.text`, `r.entity_text` etc.) — only counts, types, and timings (B4 / D-18 / CLAUDE.md)."
---

<objective>
Compose Wave 1/2 helpers into the public `RedactionService`. Three deliverables:

1. `backend/app/services/redaction/anonymization.py` - pure substitution: takes `(masked_text, entities)` and returns `(anonymized_text, entity_map, hard_redacted_count)`. Handles Faker locale, gender match, surname x-check, 10-retry collision budget with hash fallback, hard-redact `[TYPE]` placeholders.
2. `backend/app/services/redaction_service.py` - public service module with `RedactionResult` Pydantic model, `RedactionService` class (single async public `redact_text`), `@lru_cache`'d `get_redaction_service()` getter.
3. `backend/app/main.py` - extend `lifespan` with `get_redaction_service()` warm-up after `configure_tracing()`.
4. `backend/app/services/redaction/__init__.py` - keep MINIMAL. Re-export ONLY `RedactionError` (sourced from `app.services.redaction.errors`, created in Plan 04). Per checker B2 option B: do NOT re-export `RedactionResult`, `RedactionService`, or `get_redaction_service` — those must be imported from `app.services.redaction_service` directly. This breaks the circular chain `__init__.py → redaction_service.py → anonymization.py → detection.py → uuid_filter.py → __init__.py` that would otherwise raise `ImportError: cannot import name 'RedactionError'`.

Output: a working `await get_redaction_service().redact_text("...")` round-trip that produces a `RedactionResult` for any Indonesian or English chat-message-sized input, satisfying Phase 1 SC#1 / SC#2 / SC#3 / SC#4 / SC#5.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/01-detection-anonymization-foundation/01-CONTEXT.md
@backend/app/main.py
@backend/app/config.py
@backend/app/services/tracing_service.py
@backend/app/services/redaction/__init__.py
@backend/app/services/redaction/gender_id.py
@backend/app/services/redaction/honorifics.py
@backend/app/services/redaction/uuid_filter.py
@backend/app/services/redaction/name_extraction.py
@backend/app/services/redaction/detection.py

CONTEXT.md decisions consumed: D-04 (Faker id_ID), D-05 (Indonesian gender table + gender-guesser fallback), D-06 (10-retry budget + `[TYPE_<hash>]` fallback), D-07 (surname/first-name token x-check), D-08 (same `[TYPE]` for all instances), D-13 (`async def redact_text(text) -> RedactionResult`), D-14 (Phase 1 stateless), D-15 (lru_cache + lifespan warm-up), D-18 (`@traced(name="redaction.redact_text")`).

Faker mapping per surrogate-bucket entity type:
- PERSON: `f.name_male()` / `f.name_female()` / `f.name()` (random)
- EMAIL_ADDRESS: `f.email()`
- PHONE_NUMBER: `f.phone_number()`
- LOCATION: `f.city()`
- DATE_TIME: `f.date()`
- URL: `f.url()`
- IP_ADDRESS: `f.ipv4()`

gender-guesser values: returns one of `"male"`, `"female"`, `"mostly_male"`, `"mostly_female"`, `"andy"`, `"unknown"` (lower-case).

Existing main.py lifespan (post-Plan-01) at lines 10-20:
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_tracing()
    try:
        get_supabase_client().table("documents").update({"status": "pending"}).eq("status", "processing").execute()
    except Exception:
        pass
    yield
```
</context>

<tasks>

<task type="auto" tdd="false">
  <name>Task 1: Create anonymization.py (Faker surrogates, gender match, surname x-check, collision retry, hash fallback, hard-redact placeholders)</name>
  <files>backend/app/services/redaction/anonymization.py</files>
  <read_first>
    - .planning/phases/01-detection-anonymization-foundation/01-CONTEXT.md (D-04..D-08 verbatim contract)
    - backend/app/services/redaction/detection.py (Entity Pydantic model fields: type, start, end, score, text, bucket)
    - backend/app/services/redaction/gender_id.py (lookup_gender signature)
    - backend/app/services/redaction/honorifics.py (strip_honorific / reattach_honorific)
    - backend/app/services/redaction/name_extraction.py (extract_name_tokens)
  </read_first>
  <action>
Create `backend/app/services/redaction/anonymization.py`:

```python
"""Surrogate / hard-redact substitution (D-04..D-08, ANON-01..06)."""

from __future__ import annotations

import hashlib
import logging
from functools import lru_cache
from typing import Literal

import gender_guesser.detector as gg
from faker import Faker

from app.services.redaction.detection import Entity
from app.services.redaction.gender_id import lookup_gender
from app.services.redaction.honorifics import reattach_honorific, strip_honorific
from app.services.redaction.name_extraction import extract_name_tokens

logger = logging.getLogger(__name__)

_COLLISION_RETRIES = 10  # D-06


@lru_cache
def get_faker() -> Faker:
    """D-04: Faker(id_ID) singleton."""
    return Faker("id_ID")


@lru_cache
def get_gender_detector() -> gg.Detector:
    """D-05: gender-guesser fallback singleton."""
    return gg.Detector(case_sensitive=False)


def _resolve_gender(first_name: str) -> Literal["M", "F", "unknown"]:
    """D-05: Indonesian table primary, gender-guesser fallback, else unknown."""
    primary = lookup_gender(first_name)
    if primary in ("M", "F"):
        return primary
    g = get_gender_detector().get_gender(first_name)
    if g in ("male", "mostly_male"):
        return "M"
    if g in ("female", "mostly_female"):
        return "F"
    return "unknown"


def _hash_fallback(entity_type: str, real_value: str) -> str:
    """D-06: deterministic [TYPE_<6-hex>] fallback after collision budget exhausted."""
    short = hashlib.blake2b(real_value.encode("utf-8"), digest_size=3).hexdigest().upper()
    return f"[{entity_type}_{short}]"


def _faker_call(faker: Faker, entity_type: str, gender: Literal["M", "F", "unknown"]) -> str:
    if entity_type == "PERSON":
        if gender == "M":
            return faker.name_male()
        if gender == "F":
            return faker.name_female()
        return faker.name()
    if entity_type == "EMAIL_ADDRESS":
        return faker.email()
    if entity_type == "PHONE_NUMBER":
        return faker.phone_number()
    if entity_type == "LOCATION":
        return faker.city()
    if entity_type == "DATE_TIME":
        return faker.date()
    if entity_type == "URL":
        return faker.url()
    if entity_type == "IP_ADDRESS":
        return faker.ipv4()
    return _hash_fallback(entity_type, "")


def _generate_surrogate(
    entity: Entity,
    faker: Faker,
    forbidden_tokens: set[str],
    used_surrogates: set[str],
) -> str:
    """D-06 budget + D-07 cross-check + ANON-03 dedup."""
    if entity.type == "PERSON":
        honorific, bare = strip_honorific(entity.text)
        first_token = bare.split()[0] if bare.split() else bare
        gender = _resolve_gender(first_token)
    else:
        honorific = None
        gender = "unknown"

    for _ in range(_COLLISION_RETRIES):
        candidate = _faker_call(faker, entity.type, gender)
        if candidate in used_surrogates:
            continue
        if entity.type == "PERSON":
            cand_tokens = {t.lower() for t in candidate.split() if t}
            if cand_tokens & forbidden_tokens:
                continue
            return reattach_honorific(honorific, candidate)
        return candidate

    fallback = _hash_fallback(entity.type, entity.text)
    if entity.type == "PERSON":
        return reattach_honorific(honorific, fallback)
    return fallback


def anonymize(
    masked_text: str,
    entities: list[Entity],
) -> tuple[str, dict[str, str], int]:
    """Substitute entities right-to-left to keep offsets stable.

    Returns (anonymized_text, entity_map, hard_redacted_count).
    entity_map contains ONLY surrogate-bucket pairs (no hard-redact entries).
    """
    faker = get_faker()
    real_persons = [e.text for e in entities if e.type == "PERSON"]
    forbidden_tokens = extract_name_tokens(real_persons)

    entity_map: dict[str, str] = {}
    used_surrogates: set[str] = set()
    hard_redacted_count = 0
    out = masked_text

    for ent in sorted(entities, key=lambda e: e.start, reverse=True):
        if ent.bucket == "redact":
            replacement = f"[{ent.type}]"  # D-08
            hard_redacted_count += 1
        else:
            existing = entity_map.get(ent.text) or next(
                (v for k, v in entity_map.items() if k.lower() == ent.text.lower()),
                None,
            )
            if existing is not None:
                replacement = existing
            else:
                replacement = _generate_surrogate(ent, faker, forbidden_tokens, used_surrogates)
                entity_map[ent.text] = replacement
                used_surrogates.add(replacement)
        out = out[:ent.start] + replacement + out[ent.end:]

    return out, entity_map, hard_redacted_count
```

Notes:
- Right-to-left replacement avoids index drift.
- Hard-redact placeholders never enter `entity_map` (FR-3.5 / D-08).
- gender resolution runs AFTER honorific strip so the first token is the actual name.
- All Faker / detector singletons are `@lru_cache`'d so RedactionService.__init__ can warm them by calling each once.
  </action>
  <verify>
    <automated>cd backend &amp;&amp; source venv/bin/activate &amp;&amp; python -c "from app.services.redaction.anonymization import anonymize, _hash_fallback, get_faker; from app.services.redaction.detection import Entity; out = _hash_fallback('PERSON', 'Bambang'); assert out.startswith('[PERSON_') and out.endswith(']') and len(out) == 15, out; ents = [Entity(type='PERSON', start=0, end=7, score=0.95, text='Bambang', bucket='surrogate')]; t, m, hr = anonymize('Bambang', ents); assert hr == 0; assert len(m) == 1; print('OK')"</automated>
  </verify>
  <acceptance_criteria>
    - `backend/app/services/redaction/anonymization.py` exists.
    - `grep -n "def anonymize" backend/app/services/redaction/anonymization.py` returns 1 match.
    - `grep -n "_COLLISION_RETRIES = 10" backend/app/services/redaction/anonymization.py` returns 1 match.
    - `grep -n "blake2b" backend/app/services/redaction/anonymization.py` returns at least 1 match.
    - `grep -n "Faker(\"id_ID\")" backend/app/services/redaction/anonymization.py` returns 1 match.
    - `grep -n "f\"\\[{ent.type}\\]\"" backend/app/services/redaction/anonymization.py` returns 1 match (D-08 placeholder).
    - `cd backend && source venv/bin/activate && python -c "from app.services.redaction.anonymization import _hash_fallback; out = _hash_fallback('PERSON', 'Bambang'); assert out.startswith('[PERSON_') and len(out) == 15; print('OK')"` exits 0.
    - `cd backend && source venv/bin/activate && python -c "from app.services.redaction.anonymization import get_faker; print(get_faker().name())"` exits 0 and prints a non-empty Indonesian name.
    - **I15 (logger in main.py):** `grep -q "logger = logging.getLogger" backend/app/main.py` returns 0 exit code.
    - **I15 (no print on warm-up):** `grep -nE "print\(.*get_redaction_service.*warm-up" backend/app/main.py` returns 0 matches; instead `grep -n "logger.warning" backend/app/main.py` returns at least 1 match (the warm-up failure handler).
    - **W10 (single apply_uuid_mask call):** `grep -c "apply_uuid_mask" backend/app/services/redaction_service.py` returns 0 (the helper is invoked only inside `detect_entities`, never directly from the service).
    - **W12 (Phase-5 TODO):** `grep -q "TODO(Phase 5)" backend/app/services/redaction_service.py` returns 0 exit code.
    - **B4 (no real PII in logs — anonymization.py):** `grep -nE "logger\.(debug|info|warning|error|exception).*\.text|logger\.(debug|info|warning|error|exception).*r\.entity" backend/app/services/redaction/anonymization.py | grep -v "len("` returns 0 matches.
    - **B4 (no real PII in logs — redaction_service.py):** `grep -nE "logger\.(debug|info|warning|error|exception).*\.text|logger\.(debug|info|warning|error|exception).*r\.entity" backend/app/services/redaction_service.py | grep -v "len("` returns 0 matches.
    - `cd backend && source venv/bin/activate && python -c "from app.main import app; print('OK')"` exits 0.
  </acceptance_criteria>
  <done>anonymization.py implements every substitution rule from D-04..D-08; right-to-left replacement; hash fallback; gender resolver chains Indonesian table then gender-guesser.</done>
</task>

<task type="auto" tdd="false">
  <name>Task 2: Create redaction_service.py + update __init__.py + wire main.py lifespan warm-up</name>
  <files>backend/app/services/redaction_service.py, backend/app/services/redaction/__init__.py, backend/app/main.py</files>
  <read_first>
    - .planning/phases/01-detection-anonymization-foundation/01-CONTEXT.md (D-13 / D-14 / D-15 / D-18)
    - backend/app/services/redaction/detection.py (detect_entities returns (masked_text, entities, sentinels) — W10 3-tuple shape; redact_text uses masked_text directly to avoid double-masking)
    - backend/app/services/redaction/anonymization.py (Task 1 - anonymize returns (text, map, count))
    - backend/app/services/redaction/uuid_filter.py (apply_uuid_mask + restore_uuids)
    - backend/app/main.py (current lifespan - configure_tracing then DB cleanup)
    - backend/app/services/tracing_service.py (Plan 01 - the @traced decorator)
  </read_first>
  <action>
**Step A: Create `backend/app/services/redaction_service.py`**

```python
"""Public RedactionService - composes detection + anonymization (D-13..D-15)."""

from __future__ import annotations

import logging
import time
from functools import lru_cache

from pydantic import BaseModel, ConfigDict

from app.services.redaction.anonymization import (
    anonymize,
    get_faker,
    get_gender_detector,
)
from app.services.redaction.detection import detect_entities, get_analyzer
from app.services.redaction.uuid_filter import restore_uuids  # W10: apply_uuid_mask is called inside detect_entities only.
from app.services.tracing_service import traced

logger = logging.getLogger(__name__)


class RedactionResult(BaseModel):
    """D-13 public output schema."""

    model_config = ConfigDict(frozen=True)

    anonymized_text: str
    entity_map: dict[str, str]
    hard_redacted_count: int
    latency_ms: float


class RedactionService:
    """Phase 1 redaction service - stateless, single async public method (D-14)."""

    def __init__(self) -> None:
        # D-15 eager warm-up.
        get_analyzer()
        get_faker()
        get_gender_detector()
        logger.info("RedactionService initialised (Presidio + Faker + gender detector loaded).")

    @traced(name="redaction.redact_text")
    async def redact_text(self, text: str) -> RedactionResult:
        """D-13: detect + anonymize. Phase 1 stateless."""
        # TODO(Phase 5): gate `if not get_settings().pii_redaction_enabled: return passthrough_result(text)`
        # Phase 1 ships the flag in Settings (Plan 02) for forward-compat with Phase 5 SC#5.
        t0 = time.perf_counter()

        # W10: detect_entities returns the masked text it built so we don't call
        # apply_uuid_mask twice. Entity offsets are relative to masked_text.
        masked_text, entities, sentinels = detect_entities(text)

        anonymized_masked, entity_map, hard_redacted_count = anonymize(masked_text, entities)
        anonymized_text = restore_uuids(anonymized_masked, sentinels)

        latency_ms = (time.perf_counter() - t0) * 1000.0

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


@lru_cache
def get_redaction_service() -> RedactionService:
    """D-15 singleton getter; lifespan calls this once at startup."""
    return RedactionService()
```

**Step B: Update `backend/app/services/redaction/__init__.py`** (B2 — option B)

Replace its content with the MINIMAL form below. Per checker B2, the package
`__init__.py` must NOT re-export `RedactionResult` / `RedactionService` /
`get_redaction_service`. Re-exporting them re-enters the chain
`__init__.py → redaction_service.py → anonymization.py → detection.py →
uuid_filter.py → __init__.py` mid-load and Python raises
`ImportError: cannot import name 'RedactionError'`.

`RedactionError` itself lives in `app.services.redaction.errors` (Plan 04 owns
that file). The `__init__.py` simply re-exports the symbol so existing
consumers (and tests) that write `from app.services.redaction import
RedactionError` keep working.

```python
"""Redaction sub-package — Phase 1 milestone v1.0.

Public surface:
    from app.services.redaction import RedactionError
    from app.services.redaction_service import (
        RedactionResult, RedactionService, get_redaction_service,
    )

NOTE (B2 option B): this `__init__.py` deliberately re-exports ONLY
`RedactionError`. The service classes live in `app.services.redaction_service`
and MUST be imported from that module directly to avoid the circular chain
`__init__ → redaction_service → anonymization → detection → uuid_filter →
__init__`.
"""

from __future__ import annotations

from app.services.redaction.errors import RedactionError

__all__ = ["RedactionError"]
```

Note the `errors.py` file was created by Plan 04 and is the leaf module of the
package's import graph; `uuid_filter.py` already imports `RedactionError` from
`app.services.redaction.errors` directly (NOT via the package). The `__init__`
re-export is only for external convenience.

**Step C: Edit `backend/app/main.py`** (I15 — use `logger.warning` not `print`)

Read `backend/app/main.py` BEFORE editing. The current file has no module-level
logger. As part of this step, also add `import logging` and a module-level
`logger = logging.getLogger(__name__)` if absent. Both insertions must land in
this same task.

Add the imports at the top (alongside the existing
`from app.services.tracing_service import configure_tracing` line that Plan 01
added):

```python
import logging
from app.services.redaction_service import get_redaction_service

logger = logging.getLogger(__name__)
```

Modify `lifespan` to add the warm-up call AFTER `configure_tracing()` and
BEFORE the existing supabase cleanup block. Use `logger.warning(...)` (NOT
`print(...)`) so the failure message routes through the standard logging
config and is structured-log-friendly on Railway:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_tracing()
    try:
        get_redaction_service()  # PERF-01 / D-15 eager warm-up
    except Exception:
        logger.warning("get_redaction_service() warm-up failed", exc_info=True)
    try:
        get_supabase_client().table("documents").update(
            {"status": "pending"}
        ).eq("status", "processing").execute()
    except Exception:
        pass
    yield
```

Behavioural notes:
- `logger.warning(..., exc_info=True)` records the traceback under the
  warm-up failure case without polluting stdout.
- The warm-up failure path remains non-fatal (try/except still swallows the
  exception) so a model-download blip on Railway does not block boot.
  </action>
  <verify>
    <automated>cd backend &amp;&amp; source venv/bin/activate &amp;&amp; python -c "import asyncio; from app.services.redaction_service import get_redaction_service, RedactionResult; svc = get_redaction_service(); res = asyncio.run(svc.redact_text('Pak Bambang Sutrisno tinggal di Jakarta. Doc 6ba7b810-9dad-11d1-80b4-00c04fd430c8.')); assert isinstance(res, RedactionResult); assert '6ba7b810-9dad-11d1-80b4-00c04fd430c8' in res.anonymized_text; print(res.anonymized_text); print(res.entity_map); print(f'latency_ms={res.latency_ms:.1f}')"</automated>
  </verify>
  <acceptance_criteria>
    - `backend/app/services/redaction_service.py` exists.
    - `grep -n "class RedactionResult" backend/app/services/redaction_service.py` returns 1 match.
    - `grep -n "class RedactionService" backend/app/services/redaction_service.py` returns 1 match.
    - `grep -n "@lru_cache" backend/app/services/redaction_service.py` returns at least 1 match.
    - `grep -n "def get_redaction_service" backend/app/services/redaction_service.py` returns 1 match.
    - `grep -n "@traced(name=\"redaction.redact_text\")" backend/app/services/redaction_service.py` returns 1 match.
    - `grep -n "anonymized_text: str" backend/app/services/redaction_service.py` returns 1 match.
    - `grep -n "entity_map: dict\\[str, str\\]" backend/app/services/redaction_service.py` returns 1 match.
    - `grep -n "hard_redacted_count: int" backend/app/services/redaction_service.py` returns 1 match.
    - `grep -n "latency_ms: float" backend/app/services/redaction_service.py` returns 1 match.
    - `grep -n "from app.services.redaction_service import get_redaction_service" backend/app/main.py` returns 1 match.
    - `grep -nE "get_redaction_service\\(\\)" backend/app/main.py` returns at least 1 match (the lifespan call).
    - `grep -n "RedactionError" backend/app/services/redaction/__init__.py` returns at least 1 match (the re-export from `app.services.redaction.errors`).
    - `grep -n "from app.services.redaction.errors import RedactionError" backend/app/services/redaction/__init__.py` returns 1 match.
    - **B2 option B (negative check):** `grep -n "from app.services.redaction_service import" backend/app/services/redaction/__init__.py` returns 0 matches (no re-export of the service classes from `__init__.py`).
    - **B2 option B (positive check):** `cd backend && source venv/bin/activate && python -c "from app.services.redaction import RedactionError; from app.services.redaction_service import RedactionResult, RedactionService, get_redaction_service; print('OK')"` exits 0 (RedactionError from package; service classes from `app.services.redaction_service` directly).
    - `cd backend && source venv/bin/activate && python -c "import asyncio; from app.services.redaction_service import get_redaction_service; r = asyncio.run(get_redaction_service().redact_text('Bambang lives in Jakarta.')); assert 'Bambang' not in r.anonymized_text; print('OK')"` exits 0.
    - `cd backend && source venv/bin/activate && python -c "import asyncio; from app.services.redaction_service import get_redaction_service; r = asyncio.run(get_redaction_service().redact_text('Doc 6ba7b810-9dad-11d1-80b4-00c04fd430c8 ok.')); assert '6ba7b810-9dad-11d1-80b4-00c04fd430c8' in r.anonymized_text; print('OK')"` exits 0.
    - **I15 (logger in main.py):** `grep -q "logger = logging.getLogger" backend/app/main.py` returns 0 exit code.
    - **I15 (no print on warm-up):** `grep -nE "print\(.*get_redaction_service.*warm-up" backend/app/main.py` returns 0 matches; instead `grep -n "logger.warning" backend/app/main.py` returns at least 1 match (the warm-up failure handler).
    - **W10 (single apply_uuid_mask call):** `grep -c "apply_uuid_mask" backend/app/services/redaction_service.py` returns 0 (the helper is invoked only inside `detect_entities`, never directly from the service).
    - **W12 (Phase-5 TODO):** `grep -q "TODO(Phase 5)" backend/app/services/redaction_service.py` returns 0 exit code.
    - **B4 (no real PII in logs — anonymization.py):** `grep -nE "logger\.(debug|info|warning|error|exception).*\.text|logger\.(debug|info|warning|error|exception).*r\.entity" backend/app/services/redaction/anonymization.py | grep -v "len("` returns 0 matches.
    - **B4 (no real PII in logs — redaction_service.py):** `grep -nE "logger\.(debug|info|warning|error|exception).*\.text|logger\.(debug|info|warning|error|exception).*r\.entity" backend/app/services/redaction_service.py | grep -v "len("` returns 0 matches.
    - `cd backend && source venv/bin/activate && python -c "from app.main import app; print('OK')"` exits 0.
  </acceptance_criteria>
  <done>RedactionService + RedactionResult + get_redaction_service shipped; lifespan warms the singleton once at boot; package re-exports the public API; round-trip redaction on Indonesian text passes (UUID preserved, PERSON anonymized, latency_ms reported).</done>
</task>

</tasks>

<verification>
End-to-end smoke after both tasks:
```bash
cd backend && source venv/bin/activate
python -c "
import asyncio
from app.services.redaction_service import get_redaction_service
text = 'Pak Bambang Sutrisno (email: bambang@example.com, phone: +62-812-1234-5678) tinggal di Jakarta. SSN 123-45-6789. Doc 6ba7b810-9dad-11d1-80b4-00c04fd430c8.'
r = asyncio.run(get_redaction_service().redact_text(text))
print('OUT:', r.anonymized_text)
print('MAP:', r.entity_map)
print('hard:', r.hard_redacted_count, 'ms:', round(r.latency_ms, 1))
"
# Expected: anonymized_text contains the literal UUID and the literal `[US_SSN]`; does NOT contain `Bambang`, `bambang@example.com`, or `+62-812-1234-5678`.
```
</verification>

<success_criteria>
1. ANON-01..06 satisfied by the anonymization module + service composition.
2. PERF-01 satisfied: lifespan eager warm-up loads Presidio + Faker + gender detector before first request.
3. OBS-01 satisfied for redaction layer: `redact_text` wrapped in `@traced(name="redaction.redact_text")`; detection layer already wrapped in Plan 05.
4. Phase 1 SC#1 (Indonesian paragraph -> realistic surrogates + `[TYPE]` placeholders), SC#2 (two-pass thresholds applied), SC#3 (UUID survives), SC#4 (gender match + no surname reuse), SC#5 (lazy singleton + tracing) all verifiable end-to-end after this plan.
5. Phase 1 stateless API contract honoured (D-14): `redact_text(text)` only; Phase 2 widens to `(text, registry)`.
</success_criteria>

<output>
After completion, create `.planning/phases/01-detection-anonymization-foundation/01-06-SUMMARY.md` capturing:
- Final `RedactionResult` schema as shipped.
- Lifespan warm-up flow as wired (which singletons load in what order).
- Note that Phase 2 widens `redact_text` to accept `registry`.
- Confirmation that `from app.services.redaction import get_redaction_service, RedactionResult` is the canonical downstream import path.
- Any deviations discovered (Faker locale edge cases, Presidio entity coverage gaps on Indonesian text, etc.).
</output>
