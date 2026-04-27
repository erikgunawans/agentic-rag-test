# Phase 4: Fuzzy De-anonymization, Missed-PII Scan & Prompt Guidance — Pattern Map

**Mapped:** 2026-04-27
**Files analyzed:** 14 (8 new, 6 modified)
**Analogs found:** 14 / 14

Phase 4 is heavily continuation-of-Phase-3. Most analogs live in
`backend/app/services/redaction/` (Phase 1+2+3 modules) and the Phase 3 LLM
provider client. Reuse is the rule; new abstractions are the exception.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `backend/app/services/redaction/fuzzy_match.py` (NEW) | utility (pure function) | transform | `backend/app/services/redaction/honorifics.py` (module shape) + `backend/app/services/redaction/nicknames_id.py` (small focused module) + `backend/app/services/redaction/clustering.py:variants_for` (token-level transform) | role-match |
| `backend/app/services/redaction/missed_scan.py` (NEW) | service (LLM call wrapper + Pydantic model) | request-response (LLM) | `backend/app/services/redaction_service.py:_resolve_clusters_via_llm` (lines 156–283; LLMProviderClient call + soft-fail) + `backend/app/services/llm_provider.py` | role-match |
| `backend/app/services/redaction/prompt_guidance.py` (NEW) | utility (frozen string constant + helper) | static lookup | `backend/app/services/redaction/honorifics.py` (small focused module pattern) + `backend/app/services/agent_service.py:8-79` (system_prompt as string constant) | role-match |
| `supabase/migrations/031_pii_fuzzy_settings.sql` (NEW) | migration (ALTER TABLE) | DDL | `supabase/migrations/030_pii_provider_settings.sql` | exact |
| `backend/tests/unit/test_fuzzy_match.py` (NEW) | test (unit, pure function, table-driven) | pure transform | `backend/tests/unit/test_egress_filter.py` (per Phase 3 D-66) | exact |
| `backend/tests/unit/test_missed_scan.py` (NEW) | test (unit, mocked LLM SDK) | mocked async | `backend/tests/unit/test_llm_provider_client.py` (Phase 3 D-65 mock fixtures) | exact |
| `backend/tests/unit/test_prompt_guidance.py` (NEW) | test (unit, pure function) | pure | `backend/tests/unit/test_egress_filter.py` (table-driven invariants) | role-match |
| `backend/tests/api/test_phase4_integration.py` (NEW) | test (API integration) | request-response + live DB | `backend/tests/api/test_resolution_and_provider.py` (per-SC test classes; mocked AsyncOpenAI; live Supabase) | exact |
| `backend/app/services/redaction_service.py` (MODIFIED) | service (orchestrator) | request-response under asyncio.Lock | self (Phase 3 lines 285–679; `redact_text` + `de_anonymize_text` + `_resolve_clusters_via_llm`) | exact |
| `backend/app/config.py` (MODIFIED) | config (Pydantic Settings) | env-var read | self (Phase 3 lines 88–109 — same `Literal[...]` + range validator pattern) | exact |
| `backend/app/routers/admin_settings.py` (MODIFIED) | router (admin PATCH + GET) | request-response | self (Phase 3 lines 31–44 — Literal-typed mode/provider fields) | exact |
| `backend/app/routers/chat.py` (MODIFIED) | router (chat completions / SSE) | streaming, system-prompt assembly | self (lines 19–27 SYSTEM_PROMPT + lines 187–219 message-building site) | exact |
| `backend/app/services/agent_service.py` (MODIFIED) | service (agent registry) | static configuration | self (lines 8–79 — 4 `AgentDefinition.system_prompt` blocks) | exact |
| `frontend/src/pages/AdminSettingsPage.tsx` (MODIFIED) | component (admin section) | UI form → PATCH | self (lines 466–584 — existing `'pii'` section block; `entity_resolution_mode` <select>) | exact |

---

## Pattern Assignments

### NEW · Submodule: `backend/app/services/redaction/`

#### 1. `backend/app/services/redaction/fuzzy_match.py` (NEW — utility, pure function)

**Analog:** `honorifics.py` (module shape: small focused module with frozen
constant + 1–2 pure helpers + `from __future__ import annotations`) +
`clustering.py:variants_for` (token-level transform discipline) +
`nicknames_id.py:lookup_nickname` (casefold-on-input invariant from Phase 2 D-36).

**Module-shape pattern** (`honorifics.py:1-22`):
```python
"""Indonesian honorific strip-and-reattach (D-02 / PII-04).
... 5–10 line module docstring with examples ...
"""

from __future__ import annotations

import re

# D-02 verbatim list. ... (frozen constants here) ...
_HONORIFICS = ("Bapak", "Pak", "Ibu", "Bu", "Sdri.", "Sdr.")
```

**Phase 4 module skeleton** (compose `rapidfuzz` + Phase 1's `strip_honorific`
+ Phase 2 D-36 casefold invariant):
```python
"""Algorithmic Jaro-Winkler fuzzy matching for de-anonymization (D-67/D-68/D-70).

Why this exists:
- Phase 4 Pass 2 of the placeholder-tokenized de-anon pipeline scans the
  remaining (post-Pass 1) text for slightly-mangled surrogate forms ("M. Smyth"
  for canonical "Marcus Smith"). Pure-Python Jaro-Winkler is ~50x slower
  at warm-path scale, so we use rapidfuzz's C-extension implementation
  (already a transitive Presidio dep — no new top-level dependency).
- Per-cluster scoping (D-68): we ONLY score against variants in this thread's
  registry. Cross-cluster scoring would risk merging two distinct people
  whose surrogate names happen to be similar.

Pre-fuzzy normalization (D-70):
    1. Strip honorifics via Phase 1's honorifics.strip_honorific (Pak / Bu / etc.).
    2. casefold both strings (Phase 2 D-36 invariant; Phase 3 D-53 egress filter consistency).
    3. Token-level scoring: split into whitespace tokens; score each (a, b)
       pair; take max.
"""
from __future__ import annotations

from rapidfuzz.distance import JaroWinkler

from app.services.redaction.honorifics import strip_honorific


def _normalize_for_fuzzy(s: str) -> list[str]:
    """D-70 normalization: strip honorific + casefold + tokenize."""
    _honorific, bare = strip_honorific(s)
    return bare.casefold().split()


def fuzzy_score(candidate: str, variant: str) -> float:
    """Jaro-Winkler similarity in [0.0, 1.0] after D-70 normalization.

    Token-level: max-over-pairs to catch "John A. Smith" vs "John Smith".
    """
    cand_tokens = _normalize_for_fuzzy(candidate)
    var_tokens = _normalize_for_fuzzy(variant)
    if not cand_tokens or not var_tokens:
        return 0.0
    return max(
        JaroWinkler.normalized_similarity(c, v)
        for c in cand_tokens
        for v in var_tokens
    )


def best_match(
    candidate: str,
    variants: list[str],
    threshold: float = 0.85,
) -> tuple[str, float] | None:
    """D-67/D-68: return (best_variant, score) if best score ≥ threshold; else None.

    Per-cluster scoping is the CALLER's responsibility — pass only this
    cluster's variants to keep matches privacy-correct (D-68).
    """
    if not variants:
        return None
    best_var = max(variants, key=lambda v: fuzzy_score(candidate, v))
    best_score = fuzzy_score(candidate, best_var)
    if best_score >= threshold:
        return best_var, best_score
    return None
```

**No tracing decorator on this module** — it's a pure CPU function, called
from `de_anonymize_text` which is already `@traced(name="redaction.de_anonymize_text")`
(Phase 2 / `redaction_service.py:604`). Span attributes get added at the caller.

---

#### 2. `backend/app/services/redaction/missed_scan.py` (NEW — service, request-response LLM)

**Analog:** `redaction_service.py:_resolve_clusters_via_llm` (lines 156–283 —
build messages → call `LLMProviderClient` → schema-validate → soft-fail with
algorithmic fallback) and `llm_provider.py` (Phase 3 client surface).

**Imports + module-docstring pattern** (mirror `redaction_service.py:1-77` —
multi-section docstring with composition map + design invariants):
```python
"""LLM-based missed-PII scan (D-75 / D-77 / D-78, SCAN-01..05, FR-8.1..5).

Auto-chained inside RedactionService.redact_text after primary anonymization:
  detect → anonymize → missed-scan → re-anonymize-if-replaced → return.

D-75: scan operates on the ALREADY-ANONYMIZED text. The cloud LLM only sees
surrogates + [TYPE] placeholders — never raw real values. Privacy-safe by
construction.

D-77: response schema = list[{type, text}]; server uses re.escape(text) +
re.finditer to find ALL occurrences (handles multi-mention). Type validated
against settings.PII_HARD_REDACT_ENTITIES; invalid types silently dropped.

D-78: soft-fail on provider failure. On timeout / 5xx / network / Pydantic
validation error: WARNING-level structured log (counts only — B4 invariant)
+ @traced span tag (scan_skipped=True) + counter metric. Anonymization
continues with primary NER results. PERF-04 mandates this behavior.
"""
from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field, ValidationError

from app.config import get_settings
from app.services.llm_provider import LLMProviderClient
from app.services.tracing_service import traced

if TYPE_CHECKING:
    from app.services.redaction.registry import ConversationRegistry

logger = logging.getLogger(__name__)
```

**Pydantic schema pattern** (mirror Phase 1 `RedactionResult` `BaseModel +
ConfigDict(frozen=True)` shape from `redaction_service.py:93-119`):
```python
class MissedEntity(BaseModel):
    """One missed-PII match returned by the scan LLM (D-77)."""

    type: str = Field(..., description="Hard-redact entity type (validated).")
    text: str = Field(..., min_length=1, max_length=1000)


class MissedScanResponse(BaseModel):
    """Top-level scan response. Pydantic validation = the only gate."""

    entities: list[MissedEntity] = Field(default_factory=list)
```

**LLM-call + soft-fail pattern** (mirror `redaction_service.py:216-283`
verbatim — try/except `LLMProviderClient.call`, log type-name only, never
re-raise to the chat loop):
```python
@traced(name="redaction.missed_scan")
async def scan_for_missed_pii(
    anonymized_text: str,
    registry: "ConversationRegistry",
) -> tuple[str, int]:
    """D-75: run a missed-PII LLM scan over the already-anonymized text.

    Returns (possibly-modified text, replacements_count). On any failure
    returns (anonymized_text, 0) — never raises (D-78 / NFR-3).
    """
    settings = get_settings()
    if not settings.pii_missed_scan_enabled:
        return anonymized_text, 0

    valid_types = set(
        t.strip() for t in settings.pii_redact_entities.split(",") if t.strip()
    )

    messages = [
        {"role": "system", "content": (
            "Identify any PII the primary NER missed in the text below. "
            'Respond with JSON {"entities":[{"type":"<TYPE>","text":"..."}]}. '
            f"Allowed types: {sorted(valid_types)}. Text only — no offsets."
        )},
        {"role": "user", "content": anonymized_text},
    ]

    try:
        client = LLMProviderClient()
        result = await client.call(
            feature="missed_scan",
            messages=messages,
            registry=registry,
            provisional_surrogates=None,  # D-56 — no provisional set for this feature
        )
        parsed = MissedScanResponse.model_validate(result)
    except (ValidationError, Exception) as exc:  # noqa: BLE001 — D-78 catch-all
        # D-78 soft-fail. Counts + error class only — NEVER raw payloads or PII.
        logger.warning(
            'event=missed_scan_skipped feature=missed_scan error_class=%s scan_skipped_reason=%s',
            type(exc).__name__, type(exc).__name__,
        )
        return anonymized_text, 0

    # D-77: substring-replace each valid (type, text) pair. Drop invalid types silently.
    out = anonymized_text
    replacements = 0
    for ent in parsed.entities:
        if ent.type not in valid_types:
            continue  # FR-8.4: invalid types discarded
        placeholder = f"[{ent.type}]"
        # re.escape the text to handle phone-number punctuation, etc.
        new_text, n = re.subn(re.escape(ent.text), placeholder, out)
        out = new_text
        replacements += n

    return out, replacements
```

**Splice point in `redaction_service.py`** — see modified-files section.

---

#### 3. `backend/app/services/redaction/prompt_guidance.py` (NEW — utility, static lookup)

**Analog:** `honorifics.py` for module shape; `agent_service.py:8-79` for the
system-prompt-as-constant idiom. The module is a frozen string + a 6-line helper.

**Module skeleton** (D-79/D-80/D-81/D-82):
```python
"""System-prompt PII guidance helper (D-79..D-82, PROMPT-01, FR-7).

Single source of truth for the surrogate-preservation block. Appended to
chat.py's SYSTEM_PROMPT (line 19) and to each of the 4 AgentDefinition
.system_prompt blocks in agent_service.py.

Conditional injection (D-80): returns "" when redaction is disabled — saves
~150 tokens per non-redacted turn.

English-only (D-81): system instructions are most reliable in English across
OpenRouter / OpenAI / LM Studio / Ollama. Indonesian user content + English
system prompt is the standard LexCore stack pattern.
"""
from __future__ import annotations


# D-82: imperative rules + explicit type list + [TYPE] warning + 2 examples.
# ~150 tokens. Examples are load-bearing (RLHF compliance). Do NOT soften
# imperatives ("MUST" / "NEVER") into "please" — invariant violation risk.
_GUIDANCE_BLOCK = """

CRITICAL: Some text in this conversation may contain placeholder values that look like real names, emails, phones, locations, dates, URLs, or IP addresses. You MUST reproduce these EXACTLY as written, with NO abbreviation, NO reformatting, and NO substitution. Treat them as opaque tokens.

Specifically: when you see text like "John Smith", "user@example.com", "+62-21-555-1234", "Jl. Sudirman 1", "2024-01-15", "https://example.com/x", or "192.168.1.1" in the input, output it character-for-character identical. Do NOT shorten "John Smith" to "J. Smith" or "Smith". Do NOT reformat "+62-21-555-1234" to "+622155512345".

Additionally, ANY text wrapped in square brackets like [CREDIT_CARD], [US_SSN], or [PHONE_NUMBER] is a literal placeholder — preserve it exactly, do not replace it with a fabricated value.

Examples:
- Input contains "Marcus Smith" → output "Marcus Smith" (NOT "Marcus" or "M. Smith" or "Mark Smith")
- Input contains "[CREDIT_CARD]" → output "[CREDIT_CARD]" (NOT "credit card number" or a fabricated number)
"""


def get_pii_guidance_block(*, redaction_enabled: bool) -> str:
    """D-79/D-80: return the guidance block (or empty string when redaction off)."""
    return _GUIDANCE_BLOCK if redaction_enabled else ""
```

---

#### 4. `supabase/migrations/031_pii_fuzzy_settings.sql` (NEW — migration, DDL)

**Analog:** `supabase/migrations/030_pii_provider_settings.sql` — exact match
(same single-row `system_settings` ALTER pattern, same Pydantic-Literal /
DB-CHECK defense-in-depth, same comment style, no RLS changes).

**Full template** (mirror `030_*.sql:1-36` verbatim with new column set):
```sql
-- 031: PII Fuzzy De-Anonymization Settings — fuzzy_deanon_mode + threshold (Phase 4)
-- Extends the single-row system_settings table with 2 new columns per D-69 / D-70.
-- DB CHECK constraints mirror the Pydantic Literal sets in app.config.Settings
-- and the SystemSettingsUpdate model (defense in depth — D-60 / FR-5.4 / NFR-2).
-- See PRD-PII-Redaction-System-v1.1.md §4.FR-5.4 and 04-CONTEXT.md D-67..D-70.

alter table system_settings
  add column fuzzy_deanon_mode text not null default 'none'
    check (fuzzy_deanon_mode in ('algorithmic','llm','none')),
  add column fuzzy_deanon_threshold numeric(3,2) not null default 0.85
    check (fuzzy_deanon_threshold >= 0.50 and fuzzy_deanon_threshold <= 1.00);

-- system_settings already has RLS + service-role-only policy from earlier
-- migrations; no policy changes needed here. Per Phase 2 D-25 invariant the
-- registry/system_settings tables are service-role-only — no end-user PostgREST
-- access path. The PATCH route at /admin/settings is gated by require_admin.

comment on column system_settings.fuzzy_deanon_mode is
  'Phase 4 fuzzy de-anon mode: algorithmic (Jaro-Winkler) | llm | none. PRD §4.FR-5.4.';
comment on column system_settings.fuzzy_deanon_threshold is
  'D-69: Jaro-Winkler match threshold; PRD-mandated default 0.85. Range [0.50, 1.00].';
```

**Use `/create-migration`** (CLAUDE.md gotcha: never edit applied migrations
001–030; the hook blocks it).

---

### NEW · Submodule: `backend/tests/`

#### 5. `backend/tests/unit/test_fuzzy_match.py` (NEW — unit, table-driven)

**Analog:** `backend/tests/unit/test_egress_filter.py` (Phase 3 D-66 — pure
function, exhaustive matrix, single test class with named cases).

**Pattern** (mirror Phase 3 D-66 exhaustive matrix; per-class subgrouping for
threshold / honorific / casefold / per-cluster-scope — one case per D-67/D-68/D-70 invariant):
```python
"""Unit tests for fuzzy_match.fuzzy_score / best_match (D-67/D-68/D-70)."""
from __future__ import annotations

import pytest

from app.services.redaction.fuzzy_match import (
    _normalize_for_fuzzy, best_match, fuzzy_score,
)


class TestD70_Normalization:
    """D-70: strip honorifics + casefold + tokenize."""

    def test_strips_pak_and_casefolds(self):
        assert _normalize_for_fuzzy("Pak Bambang") == ["bambang"]

    def test_preserves_multi_token(self):
        assert _normalize_for_fuzzy("Marcus A. Smith") == ["marcus", "a.", "smith"]


class TestD67_JaroWinklerThreshold:
    """D-67/D-69: rapidfuzz Jaro-Winkler at threshold 0.85."""

    def test_exact_match_post_normalization(self):
        # "pak Smith" vs "Pak Smith" → 1.0 after honorific strip + casefold.
        assert fuzzy_score("pak Smith", "Pak Smith") == 1.0

    def test_one_char_typo_above_threshold(self):
        assert fuzzy_score("Smyth", "Smith") >= 0.85

    def test_unrelated_below_threshold(self):
        assert fuzzy_score("Bambang", "Mukherjee") < 0.85


class TestD68_PerClusterScope:
    """D-68: best_match operates ONLY on caller-provided variants."""

    def test_only_matches_against_supplied_variants(self):
        # Caller MUST narrow to one cluster's variants. We don't enforce in
        # the function; we test that the contract is honoured.
        variants = ["Marcus Smith", "M. Smith", "Marcus"]
        result = best_match("M. Smyth", variants, threshold=0.85)
        assert result is not None
        match, score = result
        assert match in variants
        assert score >= 0.85

    def test_below_threshold_returns_none(self):
        assert best_match("Wijaya", ["Marcus Smith", "Marcus"], threshold=0.85) is None
```

---

#### 6. `backend/tests/unit/test_missed_scan.py` (NEW — unit, mocked SDK)

**Analog:** `backend/tests/unit/test_llm_provider_client.py` lines 23–47
(`_clear_client_cache` autouse fixture + `_StubRegistry`/`_StubMapping`
duck-types) and lines 175–260 (mock `AsyncOpenAI` with `MagicMock` +
`AsyncMock(return_value=mock_response)` for `chat.completions.create`).

**Pattern** (mirror `test_llm_provider_client.py:32-47` stubs and the cloud
clean-payload flow at lines 209–233):
```python
"""Unit tests for missed_scan.scan_for_missed_pii (D-75/D-77/D-78)."""
from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.redaction.missed_scan import (
    MissedEntity, MissedScanResponse, scan_for_missed_pii,
)


@dataclass(frozen=True)
class _StubMapping:
    entity_type: str
    real_value: str


class _StubRegistry:
    def __init__(self, mappings):
        self._mappings = list(mappings)

    def entries(self):
        return self._mappings


@pytest.fixture(autouse=True)
def _clear_client_cache():
    from app.services import llm_provider
    llm_provider._clients.clear()
    yield
    llm_provider._clients.clear()


class TestD75_FeatureGated:
    """D-75: pii_missed_scan_enabled=False → no LLM call, return text unchanged."""

    @pytest.mark.asyncio
    async def test_disabled_returns_input_unchanged(self, monkeypatch):
        # Patch settings.pii_missed_scan_enabled=False via the get_settings
        # module-level call inside missed_scan.py.
        from app.config import get_settings as real_settings
        from types import SimpleNamespace
        real = real_settings()
        fake = SimpleNamespace(**{**real.model_dump(), "pii_missed_scan_enabled": False})
        with patch("app.services.redaction.missed_scan.get_settings", return_value=fake):
            text, n = await scan_for_missed_pii("foo bar", _StubRegistry([]))
        assert (text, n) == ("foo bar", 0)


class TestD77_SchemaValidation:
    """D-77: invalid types dropped; valid types replace via re.escape substring match."""

    @pytest.mark.asyncio
    async def test_invalid_type_dropped(self, monkeypatch):
        # Mock the LLM SDK to return a mix of valid + invalid types.
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content=
            '{"entities":[{"type":"CREDIT_CARD","text":"4111-1111-1111-1111"},'
            '{"type":"NOT_A_REAL_TYPE","text":"foo"}]}'
        ))]
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        with patch("app.services.llm_provider._get_client", return_value=mock_client):
            text, n = await scan_for_missed_pii(
                "card 4111-1111-1111-1111 and foo here",
                _StubRegistry([]),
            )
        assert "[CREDIT_CARD]" in text
        assert "foo" in text  # invalid type was discarded


class TestD78_SoftFail:
    """D-78: provider failure → log warn, return (text, 0). NEVER raise."""

    @pytest.mark.asyncio
    async def test_sdk_5xx_returns_input_unchanged(self, caplog):
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(side_effect=Exception("503"))
        with patch("app.services.llm_provider._get_client", return_value=mock_client):
            text, n = await scan_for_missed_pii("hello", _StubRegistry([]))
        assert (text, n) == ("hello", 0)
        # B4 invariant: log line carries error_class, NOT raw payloads.
        assert any("missed_scan_skipped" in r.getMessage() for r in caplog.records)
        assert all("hello" not in r.getMessage() for r in caplog.records)
```

---

#### 7. `backend/tests/unit/test_prompt_guidance.py` (NEW — unit, pure function)

**Analog:** `test_egress_filter.py` (Phase 3 D-66) for the table-driven shape;
this is a 30-line file because the helper has 2 branches.

**Pattern**:
```python
"""Unit tests for prompt_guidance.get_pii_guidance_block (D-79/D-80/D-82)."""
from __future__ import annotations

from app.services.redaction.prompt_guidance import (
    _GUIDANCE_BLOCK, get_pii_guidance_block,
)


class TestD80_ConditionalInjection:
    def test_disabled_returns_empty(self):
        assert get_pii_guidance_block(redaction_enabled=False) == ""

    def test_enabled_returns_block(self):
        result = get_pii_guidance_block(redaction_enabled=True)
        assert result == _GUIDANCE_BLOCK
        assert result != ""


class TestD82_BlockContent:
    def test_contains_imperative_rules(self):
        block = get_pii_guidance_block(redaction_enabled=True)
        assert "MUST reproduce these EXACTLY" in block
        assert "NO abbreviation" in block

    def test_contains_explicit_type_list(self):
        block = get_pii_guidance_block(redaction_enabled=True)
        for sample in ["John Smith", "user@example.com", "+62-21-555-1234"]:
            assert sample in block

    def test_contains_bracket_warning(self):
        block = get_pii_guidance_block(redaction_enabled=True)
        assert "[CREDIT_CARD]" in block
        assert "literal placeholder" in block

    def test_contains_concrete_examples(self):
        block = get_pii_guidance_block(redaction_enabled=True)
        assert "Marcus Smith" in block
        assert "→" in block  # examples use the arrow form per D-82
```

---

#### 8. `backend/tests/api/test_phase4_integration.py` (NEW — API integration, live DB)

**Analog:** `backend/tests/api/test_resolution_and_provider.py` — exact match.
Mirror its structure 1:1 (per-SC test class, `_patched_settings(mode)` helper,
`fresh_thread_id` + `seeded_faker` fixtures from `backend/tests/conftest.py`,
`MagicMock + AsyncMock` for AsyncOpenAI; `caplog` for B4 invariants).

**Helper pattern** (Phase 3 lines 44–56 verbatim — adapt the override key):
```python
def _patched_settings(
    *,
    fuzzy_mode: str = "none",
    fuzzy_threshold: float = 0.85,
    missed_scan_enabled: bool = True,
) -> SimpleNamespace:
    real = get_settings()
    overrides = {f: getattr(real, f) for f in real.model_dump().keys()}
    overrides["fuzzy_deanon_mode"] = fuzzy_mode
    overrides["fuzzy_deanon_threshold"] = fuzzy_threshold
    overrides["pii_missed_scan_enabled"] = missed_scan_enabled
    return SimpleNamespace(**overrides)
```

**Per-SC test-class pattern** (mirror `test_resolution_and_provider.py:62-145`
— class per SC, async methods, `fresh_thread_id` fixture, live Supabase):
```python
class TestSC1_FuzzyDeanon:
    """Mangled-surrogate de-anon resolves under algorithmic/llm; passthrough under none."""

    async def test_surname_dropped_algorithmic(self, fresh_thread_id, seeded_faker):
        # Pre-seed registry with a cluster: canonical "Marcus Smith" + variants
        # ("M. Smith", "Marcus", "Smith"). De-anonymize "M. Smyth" — fuzzy match
        # ≥ threshold → resolves to "Marcus Smith".
        ...

    async def test_passthrough_in_none_mode(self, fresh_thread_id, seeded_faker):
        # mode='none' — "M. Smyth" left unchanged (no fuzzy step).
        ...


class TestSC2_NoSurnameCollision:
    """3-phase pipeline prevents surname-collision corruption (D-71/D-68)."""

    async def test_two_clusters_share_surname(self, fresh_thread_id, seeded_faker):
        # Two clusters: "Marcus Smith" / "Sarah Smith". A "Smith" mention must
        # NOT cross-resolve. Per-cluster scoping (D-68) is the protective invariant.
        ...


class TestSC3_HardRedactSurvives:
    """[CREDIT_CARD] / [US_SSN] survive de-anon in all 3 modes (D-74)."""

    @pytest.mark.parametrize("mode", ["algorithmic", "llm", "none"])
    async def test_hard_redact_identity(self, mode, fresh_thread_id, seeded_faker):
        ...


class TestSC4_MissedScan:
    """Auto-chained scan replaces missed types; invalid types discarded; re-NER on replacement."""

    async def test_scan_replaces_and_re_runs(self, fresh_thread_id, seeded_faker):
        # Mock LLMProviderClient to return a CREDIT_CARD missed entity.
        # Assert post-scan text contains [CREDIT_CARD].
        # Assert primary NER re-ran (D-76 — full re_run on modified text).
        ...

    async def test_invalid_types_dropped(self, fresh_thread_id, seeded_faker):
        # Mock returns mixed valid + invalid types; only valid types replaced.
        ...


class TestSC5_VerbatimEmission:
    """Main-agent system prompt instructs LLM to emit surrogates verbatim (D-79..D-82)."""

    async def test_chat_completion_preserves_surrogate(self, fresh_thread_id):
        # Mock OpenRouter; pass a surrogate-bearing message; assert response
        # contains exact surrogate format (RLHF compliance test).
        ...


class TestB4_LogPrivacy_FuzzyAndScan:
    """Phase 1 B4 invariant extends to D-78 missed-scan soft-fail logs."""

    async def test_no_real_pii_in_scan_skip_log(self, fresh_thread_id, caplog):
        # Mirror test_resolution_and_provider.py::TestSC6_LogPrivacy.
        # Force scan failure; assert no real value in any log line.
        ...
```

**Cloud-mocking pattern** (mirror `test_resolution_and_provider.py:163-201`
— `MagicMock + AsyncMock` for `chat.completions.create`; `_patched_settings`
+ `patch("app.services.llm_provider._get_client")` + env override):
```python
mock_client = MagicMock()
mock_client.chat.completions.create = AsyncMock()  # never-called assert downstream

with patch(
    "app.services.redaction_service.get_settings",
    return_value=_patched_settings(fuzzy_mode="llm"),
), patch(
    "app.services.llm_provider._get_client", return_value=mock_client
), patch.dict(
    "os.environ", {"FUZZY_DEANON_LLM_PROVIDER": "cloud"}, clear=False,
):
    ...
```

---

### MODIFIED · `backend/app/services/redaction_service.py` (service, orchestrator)

**Analog:** self (Phase 2 + Phase 3 — lines 285–679 already contain the
`redact_text` orchestrator + `de_anonymize_text` 1-phase round-trip).

**Splice point 1 — `de_anonymize_text` 3-phase upgrade** (D-71/D-72).
Current signature at `redaction_service.py:604-679`:
```python
@traced(name="redaction.de_anonymize_text")
async def de_anonymize_text(
    self,
    text: str,
    registry: ConversationRegistry,
) -> str:
```
The Phase 2 docstring at lines 612–615 already promises Phase 4's insertion
between the two existing passes:
> Forward-compat with Phase 4's 3-phase fuzzy upgrade (FR-5.4) — Phase 4
> will insert its placeholder-tokenized fuzzy-match pass BETWEEN the
> existing two passes (surrogate→placeholder, placeholder→real) without
> rewriting this call site.

**Phase 4 in-place extension** (D-71 — append `mode` param; D-72 — insert
Pass 2 fuzzy step between current Pass 1 (line 648) and Pass 2 (line 664)):
```python
@traced(name="redaction.de_anonymize_text")
async def de_anonymize_text(
    self,
    text: str,
    registry: ConversationRegistry,
    mode: Literal["algorithmic", "llm", "none"] | None = None,  # NEW (D-71)
) -> str:
    # NEW (D-71): resolve effective mode: param → env → DB → default 'none'.
    if mode is None:
        mode = get_settings().fuzzy_deanon_mode  # 'none' | 'algorithmic' | 'llm'
    threshold = get_settings().fuzzy_deanon_threshold

    # ─── EXISTING (lines 631-662): Pass 1 — surrogate → placeholder ───
    # (unchanged: sort by len(surrogate_value) DESC; re.subn with re.IGNORECASE;
    # populate placeholders dict from successful subs.)

    # ─── NEW (D-72): Pass 2 — fuzzy/LLM-match against UNREPLACED variants ───
    if mode == "algorithmic":
        out, additional = self._fuzzy_match_algorithmic(
            out, registry, placeholders, threshold,
        )
    elif mode == "llm":
        out, additional = await self._fuzzy_match_llm(
            out, registry, placeholders,
        )
    else:  # mode == "none"
        additional = 0

    # ─── EXISTING (lines 664-668): Pass 3 — placeholder → real_value ───
    # (unchanged.)
```

**Splice point 2 — auto-chain missed-scan inside `redact_text`** (D-75).
Current `_redact_text_with_registry` at `redaction_service.py:439-602`. After
`anonymize(...)` returns at line 497–502 and `restore_uuids` at line 503,
insert the scan + re-run:
```python
# ─── EXISTING line 503 ───
anonymized_text = restore_uuids(anonymized_masked, sentinels)

# ─── NEW (D-75/D-76): auto-chain missed-scan + re-run on replacement ───
from app.services.redaction.missed_scan import scan_for_missed_pii
scanned_text, replacements = await scan_for_missed_pii(anonymized_text, registry)
if replacements > 0 and scanned_text != anonymized_text:
    # D-76: full re-run of redact_text on modified text. Single re-run cap —
    # do NOT loop a third time. Pass scanned_text back through the same
    # entry point with a guard flag to prevent recursion.
    # (Implementation: a private kwarg or thread-local — planner picks.)
    return await self._redact_text_with_registry(
        scanned_text, registry, _scan_rerun_done=True,  # guard
    )

# ─── EXISTING (line 506+): delta computation, upsert, RedactionResult ───
```

**Tracing-attribute pattern** (Phase 3 D-63 lines 575–595 already wired —
extend with Phase 4 attrs):
```python
# Phase 4 ADDS to the existing logger.debug block:
span.set_attribute("fuzzy_deanon_mode", mode)              # algorithmic|llm|none
span.set_attribute("fuzzy_matches_resolved", additional)
span.set_attribute("missed_scan_enabled", settings.pii_missed_scan_enabled)
span.set_attribute("missed_scan_replacements", replacements)
span.set_attribute("scan_skipped", scan_skipped)           # D-78 soft-fail tag
# NEVER set real-value attributes (B4 / D-18 invariant).
```

---

### MODIFIED · `backend/app/config.py` (config, env-var)

**Analog:** self — Phase 3's lines 88–109 are the exact pattern to mirror
(`Literal[...]` + `| None` + comment block referencing the decision IDs +
forward-compat field already shipped at line 109).

**Splice point** — append after Phase 3's `pii_missed_scan_enabled` (line 109):
```python
    # Phase 4 forward-compat (column shipped in Phase 3 to avoid migration churn)
    pii_missed_scan_enabled: bool = True   # ← line 109 (existing)

    # Phase 4: Fuzzy de-anonymization (D-67..D-70 / FR-5.4)
    # Mirrors entity_resolution_mode pattern (line 89) — same Literal set.
    fuzzy_deanon_mode: Literal["algorithmic", "llm", "none"] = "none"
    # D-69: PRD-mandated default 0.85; range [0.50, 1.00] (Pydantic + DB CHECK).
    fuzzy_deanon_threshold: float = Field(default=0.85, ge=0.50, le=1.00)
```

**Add `Field` import** (line 1 already imports `BaseSettings, SettingsConfigDict`;
need to add `Field` from pydantic — confirm Phase 3 may already do this via
pydantic_settings). Safe import line:
```python
from pydantic import Field   # NEW; pydantic v2 — Field is re-exported here
```

---

### MODIFIED · `backend/app/routers/admin_settings.py` (router, request-response)

**Analog:** self — Phase 3 lines 31–44 (PII Phase 3 mode/provider Literal block).

**Splice point** — append after Phase 3 `pii_missed_scan_enabled` field at
line 44 inside `SystemSettingsUpdate`:
```python
class SystemSettingsUpdate(BaseModel):
    # ... existing Phase 3 fields ...
    pii_missed_scan_enabled: bool | None = None   # ← line 44 (existing)

    # Phase 4: Fuzzy de-anonymization (D-67..D-70)
    fuzzy_deanon_mode: Literal["algorithmic", "llm", "none"] | None = None
    fuzzy_deanon_threshold: float | None = Field(default=None, ge=0.50, le=1.00)
```

**No PATCH-handler change** — `model_dump(exclude_none=True)` (line 57)
auto-picks new fields; `log_action(details={"changed_fields": ...})` (line 61)
auto-audits.

**No new GET endpoint needed** — the existing `GET /admin/settings` (line 47)
returns `system_settings` row in full, including the new columns added by
migration 031.

---

### MODIFIED · `backend/app/routers/chat.py` (router, system-prompt assembly)

**Analog:** self — lines 19–27 (`SYSTEM_PROMPT` constant) and lines 187–219
(message-building site in `event_generator`).

**Splice point — line 215–219** (single-agent path message construction):
```python
# Existing (line 215):
            else:
                # --- Single-agent path (Module 7 behavior) ---
                messages = (
                    [{"role": "system", "content": SYSTEM_PROMPT}]
                    + [{"role": m["role"], "content": m["content"]} for m in history]
                    + [{"role": "user", "content": body.message}]
                )
```

**Phase 4 splice** (D-79 — append guidance to system prompt at build time):
```python
# Top of file (after line 9 `from app.services import agent_service`):
from app.services.redaction.prompt_guidance import get_pii_guidance_block

# Inside event_generator() — replace the single-agent system message:
            else:
                # --- Single-agent path (Module 7 behavior) ---
                # D-79/D-80: append PII guidance when redaction is enabled
                # for this thread. thread.redaction_enabled may be a column
                # on threads (Phase 5 wiring) or fall back to global
                # settings.pii_redaction_enabled. Phase 4 ships the call
                # site; Phase 5 wires the per-thread flag.
                pii_guidance = get_pii_guidance_block(
                    redaction_enabled=settings.pii_redaction_enabled,
                )
                messages = (
                    [{"role": "system", "content": SYSTEM_PROMPT + pii_guidance}]
                    + [{"role": m["role"], "content": m["content"]} for m in history]
                    + [{"role": "user", "content": body.message}]
                )
```

**Splice point — line 187–191** (multi-agent path):
```python
# Existing (line 187):
                # 3. Build messages with agent's system prompt
                messages = (
                    [{"role": "system", "content": agent_def.system_prompt}]
                    + [{"role": m["role"], "content": m["content"]} for m in history]
                    + [{"role": "user", "content": body.message}]
                )
```

**Phase 4 splice** — `agent_def.system_prompt` already includes the guidance
because `agent_service.py` appends it at agent-construction time (see next
modified file). The chat.py multi-agent path needs NO additional change.

---

### MODIFIED · `backend/app/services/agent_service.py` (service, agent registry)

**Analog:** self — lines 8–79 contain 4 `AgentDefinition.system_prompt`
blocks (Research, Data Analyst, General, Explorer).

**Splice points — 4 sites** (lines 11, 29, 49, 64 per CONTEXT.md):
- `RESEARCH_AGENT.system_prompt` (line 11) — ends at line 21
- `DATA_ANALYST_AGENT.system_prompt` (line 29) — ends at line 41
- `GENERAL_AGENT.system_prompt` (line 49) — ends at line 56
- `EXPLORER_AGENT.system_prompt` (line 64) — ends at line 76

**Phase 4 splice** — append helper output to each system_prompt at module
import time (D-79). Single-source-of-truth via the helper:
```python
# Top of file (after line 4 `from app.models.agents import ...`):
from app.config import get_settings
from app.services.redaction.prompt_guidance import get_pii_guidance_block

# At module-import time, compute the guidance once.
# Phase 4 uses global settings.pii_redaction_enabled; Phase 5 may switch
# to per-thread flag at chat-completion-build time. Module-import binding
# is acceptable for v1.0 since redaction-on/off is a deploy-time toggle.
_PII_GUIDANCE = get_pii_guidance_block(
    redaction_enabled=get_settings().pii_redaction_enabled,
)

RESEARCH_AGENT = AgentDefinition(
    name="research",
    display_name="Research Agent",
    system_prompt=(
        "You are a thorough document research specialist. ... "
        "Be precise and cite your sources."
    ) + _PII_GUIDANCE,        # ← NEW
    tool_names=["search_documents"],
    max_iterations=5,
)

# Apply the same `+ _PII_GUIDANCE` suffix to:
#   DATA_ANALYST_AGENT.system_prompt (line 29)
#   GENERAL_AGENT.system_prompt      (line 49)
#   EXPLORER_AGENT.system_prompt     (line 64)
```

**Why module-import binding is correct here**: every other agent definition
field (tool_names, max_iterations) is also bound at import time. The
redaction-enabled flag is a global Settings value; Phase 5 may later move
this to a per-call computation if per-thread overrides ship.

---

### MODIFIED · `frontend/src/pages/AdminSettingsPage.tsx` (component, UI form)

**Analog:** self — lines 466–584 already contain the `'pii'` section block
(Phase 3 D-59). Phase 4 adds two NEW form fields to the existing section.

**Splice point — line 513** (after the existing `entity_resolution_mode`
<select> closes, before the `Global provider` block at line 515):

The existing pattern at `AdminSettingsPage.tsx:499-513`:
```tsx
              {/* Mode (entity_resolution_mode) */}
              <div className="space-y-1">
                <label className="text-xs font-medium">{t('admin.pii.mode.label')}</label>
                <select
                  value={form.entity_resolution_mode ?? 'algorithmic'}
                  onChange={(e) =>
                    updateField('entity_resolution_mode', e.target.value as 'algorithmic' | 'llm' | 'none')
                  }
                  className={inputClass}
                >
                  <option value="algorithmic">{t('admin.pii.mode.algorithmic')}</option>
                  <option value="llm">{t('admin.pii.mode.llm')}</option>
                  <option value="none">{t('admin.pii.mode.none')}</option>
                </select>
              </div>
```

**Phase 4 splice** — add 2 fields mirroring this pattern; place between the
mode/provider blocks and the existing `Separator` at line 530:

1. Extend the `SystemSettings` interface (line 32 — after `pii_missed_scan_enabled`):
```tsx
  pii_missed_scan_enabled?: boolean
  // Phase 4: Fuzzy de-anonymization (D-67..D-70)
  fuzzy_deanon_mode?: 'algorithmic' | 'llm' | 'none'
  fuzzy_deanon_threshold?: number
```

2. Add the new fields inside the `'pii'` section block (D-69 / D-70 / D-82):
```tsx
              {/* Phase 4: Fuzzy de-anon mode (D-67) */}
              <div className="space-y-1">
                <label className="text-xs font-medium">{t('admin.pii.fuzzy.mode.label')}</label>
                <select
                  value={form.fuzzy_deanon_mode ?? 'none'}
                  onChange={(e) =>
                    updateField('fuzzy_deanon_mode', e.target.value as 'algorithmic' | 'llm' | 'none')
                  }
                  className={inputClass}
                >
                  <option value="none">{t('admin.pii.fuzzy.mode.none')}</option>
                  <option value="algorithmic">{t('admin.pii.fuzzy.mode.algorithmic')}</option>
                  <option value="llm">{t('admin.pii.fuzzy.mode.llm')}</option>
                </select>
              </div>

              {/* Phase 4: Fuzzy threshold slider (D-69) */}
              <div className="space-y-1">
                <label className="text-xs font-medium">
                  {t('admin.pii.fuzzy.threshold.label')}: {(form.fuzzy_deanon_threshold ?? 0.85).toFixed(2)}
                </label>
                <input
                  type="range"
                  min={0.50}
                  max={1.00}
                  step={0.05}
                  value={form.fuzzy_deanon_threshold ?? 0.85}
                  onChange={(e) =>
                    updateField('fuzzy_deanon_threshold', parseFloat(e.target.value))
                  }
                  className="w-full"
                />
              </div>
```

3. Add i18n strings to BOTH translation files (`id` + `en` referenced by
`I18nProvider`):
- `admin.pii.fuzzy.mode.label` / `.none` / `.algorithmic` / `.llm`
- `admin.pii.fuzzy.threshold.label`

**No new state variable** — the existing `form` state covers the two new
fields automatically; existing `handleSave` (lines 104–122) already PATCHes
`form` as-is. Existing `isDirty` check (line 124) auto-tracks changes.

---

## Shared Patterns

### `@traced` decorator on every new public service method
**Source:** Phase 1 D-16 / `tracing_service.py` + every `@traced`-decorated
method in `redaction_service.py` (lines 320, 604) and `llm_provider.py` (line 171).
**Apply to:** `redaction.missed_scan` (Phase 4 D-78 — `@traced(name="redaction.missed_scan")`).
**Excerpt** (`redaction_service.py:320`):
```python
@traced(name="redaction.redact_text")
async def redact_text(self, text: str, registry: ConversationRegistry | None = None) -> RedactionResult:
    ...
```

### LLMProviderClient call + soft-fail wrapper (D-78 / NFR-3)
**Source:** `redaction_service.py:_resolve_clusters_via_llm` (lines 156–283).
**Apply to:** `missed_scan.scan_for_missed_pii` — same try/`_EgressBlocked`/
`Exception` triple-catch shape; same WARNING-level structured-log policy
(counts + error-class only — B4 / D-55); same algorithmic-fallback or
return-input behavior.
**Excerpt** (`redaction_service.py:262-282`):
```python
except _EgressBlocked as exc:
    logger.info(
        "redaction.llm_fallback reason=egress_blocked clusters_formed=%d match_count=%d",
        len(algorithmic_clusters),
        exc.result.match_count,
    )
    return algorithmic_clusters, True, "egress_blocked", True
except Exception as exc:  # noqa: BLE001
    reason = type(exc).__name__
    logger.info("redaction.llm_fallback reason=%s clusters_formed=%d", reason, len(algorithmic_clusters))
    return algorithmic_clusters, True, reason, False
```

### Counts + 8-char SHA-256 hashes only in PII-adjacent log lines (B4 / D-55 / D-78)
**Source:** Phase 1 D-18 / Phase 2 D-41 / `egress.py:108-113` (the canonical
`event=egress_filter_blocked` log line).
**Apply to:** Every new logger call in `missed_scan.py`, `fuzzy_match.py`
(if any), and the redaction_service span attributes for D-78. NEVER log
raw payloads or matched text. Mirror the integration test invariant in
`test_resolution_and_provider.py:436-443` (B4 caplog scan).

### Pydantic `Literal` validation + DB CHECK constraint defense in depth (D-60)
**Source:** `admin_settings.py:29-44` (`rag_rerank_mode`, `entity_resolution_mode`)
+ `030_pii_provider_settings.sql:7-23` matching CHECKs.
**Apply to:** `fuzzy_deanon_mode` Literal in `config.py` + `admin_settings.py`
+ `031_pii_fuzzy_settings.sql` CHECK clause; numeric range enforced at API
layer via Pydantic `Field(ge=0.50, le=1.00)` AND at DB layer via CHECK.

### Service-internal call from `redact_text` orchestrator (D-75 auto-chain)
**Source:** `redaction_service.py:497-502` — pattern of inserting a step
between detection (line 463) and delta-computation (line 514) inside the
asyncio.Lock critical section.
**Apply to:** `scan_for_missed_pii` call site (Phase 4 D-75) — slot it
between `restore_uuids` (line 503) and the delta loop (line 514). The
asyncio.Lock from line 375 is already held; no new lock surface.

### Lazy module-level singleton (no new client surface needed)
**Source:** `llm_provider.py:_clients` dict + `_get_client` lazy init
(lines 100–121).
**Apply to:** `missed_scan.py` does NOT need a new client — it instantiates
`LLMProviderClient()` per-call, which is correct (the underlying SDK clients
ARE cached at the `_get_client` layer). Mirror the pattern at
`redaction_service.py:217`:
```python
client = LLMProviderClient()  # lightweight; SDK cache lives in _get_client
result = await client.call(feature="missed_scan", ...)
```

### asyncio.Lock critical-section composition (Phase 2 D-30 invariant)
**Source:** `redaction_service.py:373-389` (lock acquisition + size_before /
size_after / lock_wait_ms instrumentation).
**Apply to:** Phase 4's missed-scan + re-run runs INSIDE the existing
per-thread asyncio.Lock. NO new lock surface. The re-run guard flag (D-76:
single re-run cap) prevents recursion within the same lock-held call.

### `fresh_thread_id` + `seeded_faker` test fixtures (Phase 2 D-44 / Phase 3 D-65)
**Source:** `backend/tests/conftest.py:33` (`seeded_faker`) and `:94`
(`fresh_thread_id` — yields a UUID after creating a fresh threads row).
**Apply to:** Every per-test isolation in `test_phase4_integration.py`.
Pattern:
```python
async def test_xxx(self, fresh_thread_id, seeded_faker, caplog):
    registry = await ConversationRegistry.load(fresh_thread_id)
    ...
```

### i18n via `I18nProvider` + `t()` on every admin-page string
**Source:** `AdminSettingsPage.tsx` — every `t('admin.pii.<key>')` call.
**Apply to:** New `admin.pii.fuzzy.mode.*` and `admin.pii.fuzzy.threshold.*`
strings — add Indonesian (default) + English entries to BOTH translation
files referenced by `I18nProvider`.

### Phase-3-shipped `feature` Literal already includes Phase 4 strings
**Source:** `llm_provider.py:53-59` — `_Feature` Literal already enumerates
`"fuzzy_deanon"` and `"missed_scan"`. No type extension needed in Phase 4.
```python
_Feature = Literal[
    "entity_resolution",
    "missed_scan",     # ← Phase 4 consumes
    "fuzzy_deanon",    # ← Phase 4 consumes
    "title_gen",
    "metadata",
]
```

---

## No Analog Found

(None — every Phase 4 file has a clear codebase analog within the same
service tree. Phase 4 is heavily continuation-of-Phase-3, so reuse is
exhaustive.)

---

## Metadata

**Analog search scope:**
- `backend/app/services/redaction/` (Phase 1+2+3 modules — full submodule)
- `backend/app/services/redaction_service.py` (Phase 2+3 orchestrator)
- `backend/app/services/llm_provider.py` (Phase 3 client)
- `backend/app/config.py` (Settings — Phase 1+2+3 PII fields)
- `backend/app/routers/admin_settings.py` (PATCH + GET schema)
- `backend/app/routers/chat.py` (SYSTEM_PROMPT site, message assembly)
- `backend/app/services/agent_service.py` (4 AgentDefinition system_prompts)
- `supabase/migrations/030_pii_provider_settings.sql` (Phase 3 migration template)
- `frontend/src/pages/AdminSettingsPage.tsx` ('pii' section)
- `backend/tests/api/test_resolution_and_provider.py` (per-SC integration suite)
- `backend/tests/unit/test_llm_provider_client.py` + `test_egress_filter.py`
  (mocked-SDK + table-driven unit patterns)
- `backend/tests/conftest.py` (`fresh_thread_id`, `seeded_faker` fixtures)

**Files scanned:** ~16 (full Phase 3 surface + Phase 1/2 redaction modules
that Phase 4 imports from + the chat router + agent service + Phase 3
integration test for SC↔file mapping).

**Pattern extraction date:** 2026-04-27

---

## PATTERN MAPPING COMPLETE

**Phase:** 4 — Fuzzy De-anonymization, Missed-PII Scan & Prompt Guidance
**Files classified:** 14
**Analogs found:** 14 / 14

### Coverage
- Files with exact analog: 11
- Files with role-match analog: 3
- Files with no analog: 0

### Key Patterns Identified
- All Phase 4 LLM calls dispatch through Phase 3's `LLMProviderClient.call(feature=...)`. The `feature` Literal already includes `missed_scan` and `fuzzy_deanon` (Phase 3 D-49 forward-compat shipped); no client-surface change.
- Soft-fail wrapper for missed-scan (D-78) mirrors `_resolve_clusters_via_llm` exactly — `try LLMProviderClient.call → except _EgressBlocked → except Exception → return input unchanged with WARNING log carrying error_class only`.
- All Phase 4 service code reuses the existing per-thread asyncio.Lock from `redaction_service.py:373-389`. NO new lock surface, NO new singleton, NO new client. Variant rows already exist in `entity_registry` from Phase 3 D-48 — fuzzy matching reads them via `registry.entries()`.
- The 3-phase de-anon upgrade is an in-place extension of `de_anonymize_text` (Phase 2 D-34 docstring promised this — lines 612–615). Adding the `mode` parameter with `None` default is backward-compatible — Phase 2 callers and tests stay green.
- Migration 031 mirrors migration 030 line-for-line: same single-row ALTER TABLE, same DB CHECK / Pydantic Literal defense in depth, same comment style. No RLS changes.
- The admin UI already has a `'pii'` section block (Phase 3 D-59 lines 466–584); Phase 4 adds 2 form fields inside it — no new section, no new state variable, no new endpoint.
- `agent_service.py`'s 4 `system_prompt` blocks all close as multi-line strings (lines 21, 41, 56, 76); appending `+ _PII_GUIDANCE` to each is mechanical and uniform.
- B4 / D-55 caplog invariants are reused verbatim from Phase 3 (`test_resolution_and_provider.py:436-443`) — every Phase 4 caplog assertion lists the same `forbidden = ["Bambang Sutrisno", "Bambang", "Sutrisno"]` style of literal scan.

### File Created
`.planning/phases/04-fuzzy-de-anonymization-missed-pii-scan-prompt-guidance/04-PATTERNS.md`

### Ready for Planning
Pattern mapping complete. Planner can now reference exact line numbers and
function signatures for each Phase 4 plan (fuzzy_match algorithmic, missed_scan
LLM, prompt_guidance helper, redaction_service splices, config + admin router
+ migration 031, agent_service + chat.py wiring, admin UI extension, full
test suite mirroring Phase 3 D-64..D-66).
