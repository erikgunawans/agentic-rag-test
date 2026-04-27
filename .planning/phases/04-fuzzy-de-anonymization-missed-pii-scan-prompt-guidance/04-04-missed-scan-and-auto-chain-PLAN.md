---
phase: 04-fuzzy-de-anonymization-missed-pii-scan-prompt-guidance
plan: 04
type: execute
wave: 4
depends_on: [01, 03]
files_modified:
  - backend/app/services/redaction/missed_scan.py
  - backend/app/services/redaction_service.py
  - backend/tests/unit/test_missed_scan.py
autonomous: true
requirements_addressed: [SCAN-01, SCAN-02, SCAN-03, SCAN-04, SCAN-05]
tags: [pii, missed-scan, llm-provider, soft-fail, re-ner, observability]
must_haves:
  truths:
    - "Module missed_scan.py exposes `async def scan_for_missed_pii(anonymized_text: str, registry: ConversationRegistry) -> tuple[str, int]` (D-75/D-77/D-78)"
    - "scan_for_missed_pii is gated by Settings.pii_missed_scan_enabled (Phase 3 migration 030 D-57); returns (input, 0) immediately when disabled"
    - "LLM call dispatched via LLMProviderClient.call(feature='missed_scan', registry=registry, provisional_surrogates=None) — Phase 3 D-49 _Feature Literal already includes 'missed_scan'"
    - "Response validated via Pydantic MissedScanResponse model: {entities: [{type: str, text: str (1..1000 chars)}]} (D-77)"
    - "Server validates each entity.type ∈ Settings.pii_redact_entities — invalid types silently dropped (FR-8.4 / D-77)"
    - "Server replaces each valid entity.text via re.subn(re.escape(text), f'[{type}]', anonymized_text) — substring match (D-77 forgiving-positions rationale)"
    - "Auto-chained inside RedactionService._redact_text_with_registry AFTER the existing anonymize step (D-75): pipeline becomes detect → anonymize → missed-scan → re-anonymize-if-replaced → return"
    - "When scan replaces ≥1 entities AND scanned_text != anonymized_text: full re-run of redact_text on modified text (D-76 / FR-8.5); guarded by single-re-run cap to prevent unbounded recursion"
    - "Soft-fail per D-78: on TimeoutError / HTTPError / ValidationError / _EgressBlocked: WARNING log with error_class only (B4 — never raw payload), span tag scan_skipped=true, return (input, 0); anonymization continues"
    - "Decorated with @traced(name='redaction.missed_scan') — Phase 1 D-16 pattern"
    - "Unit tests cover D-75 (gated), D-77 (schema validation + invalid-type drop + valid-type replace), D-78 (soft-fail no-PII-in-logs)"
  artifacts:
    - path: "backend/app/services/redaction/missed_scan.py"
      provides: "MissedEntity + MissedScanResponse Pydantic models + async scan_for_missed_pii(anonymized_text, registry) → (text, replacement_count)"
      contains: "async def scan_for_missed_pii"
    - path: "backend/app/services/redaction_service.py"
      provides: "Auto-chain splice in _redact_text_with_registry — calls scan_for_missed_pii after anonymize; full re-run on replacement (D-75/D-76)"
      contains: "scan_for_missed_pii"
    - path: "backend/tests/unit/test_missed_scan.py"
      provides: "Unit coverage for D-75/D-77/D-78"
      contains: "TestD78_SoftFail"
  key_links:
    - from: "backend/app/services/redaction/missed_scan.py"
      to: "backend/app/services/llm_provider.py:LLMProviderClient.call"
      via: "feature='missed_scan'"
      pattern: "feature\\s*=\\s*['\\\"]missed_scan['\\\"]"
    - from: "backend/app/services/redaction_service.py:_redact_text_with_registry"
      to: "backend/app/services/redaction/missed_scan.py:scan_for_missed_pii"
      via: "from app.services.redaction.missed_scan import scan_for_missed_pii"
      pattern: "scan_for_missed_pii"
    - from: "missed_scan.py validation"
      to: "Settings.pii_redact_entities (Phase 1 D-03 / FR-8.4)"
      via: "set(t.strip() for t in settings.pii_redact_entities.split(',') if t.strip())"
      pattern: "pii_redact_entities"
threat_model:
  trust_boundaries:
    - "Caller (RedactionService.redact_text) → scan_for_missed_pii → LLMProviderClient.call (cloud egress when provider='cloud')"
    - "LLM response → server-side type whitelist + re.escape substring replace (untrusted input crossing into anonymized text)"
  threats:
    - id: "T-04-04-1"
      category: "Information Disclosure (anonymized text → cloud LLM)"
      component: "scan_for_missed_pii cloud-mode payload"
      severity: "low"
      disposition: "mitigate"
      mitigation: "D-75 invariant: scan operates on the ALREADY-ANONYMIZED text. The LLM sees only surrogates + [TYPE] placeholders — never raw real values. Defense-in-depth: Phase 3 D-53..D-56 egress filter wraps the call via LLMProviderClient (registry scan). Plan 04-07 TestB4 caplog assertion ensures no raw values appear in logs. (Severity 'low' rather than 'high' because the input is already surrogate-form by construction.)"
    - id: "T-04-04-2"
      category: "Tampering (LLM injects fabricated entity type)"
      component: "MissedScanResponse parse + server-side type whitelist"
      severity: "high"
      disposition: "mitigate"
      mitigation: "D-77 / FR-8.4: server constructs `valid_types = set(...settings.pii_redact_entities split ',')` BEFORE applying any replacement; iterates `parsed.entities` and SKIPS any entity whose `type not in valid_types`. Pydantic enforces schema; server enforces type whitelist. LLM cannot inject `[ARBITRARY_TYPE]` brackets into anonymized text. Plan 04-07 TestSC4 subtests assert this with mocked LLM returning mixed valid + invalid types."
    - id: "T-04-04-3"
      category: "Information Disclosure (PII in soft-fail logs)"
      component: "WARNING log on provider failure"
      severity: "high"
      disposition: "mitigate"
      mitigation: "D-78: log line contains `event=missed_scan_skipped feature=missed_scan error_class=<TypeName>` ONLY. NEVER `text`, `payload`, `messages`, `parsed`, or any other field that could carry surrogates or partial real values. Plan 04-07 TestB4_LogPrivacy_FuzzyAndScan caplog assertion scans every log record for forbidden literals."
    - id: "T-04-04-4"
      category: "DoS (unbounded re-run recursion)"
      component: "Auto-chain re-run on replacement (D-76)"
      severity: "low"
      disposition: "mitigate"
      mitigation: "D-76 single re-run cap: `_redact_text_with_registry` accepts `_scan_rerun_done: bool = False` private kwarg. When set True, the auto-chain block is bypassed. The re-entrant call passes True; the second pass cannot trigger a third. Even pathological cases (LLM keeps flagging entities every pass) terminate in O(2) calls."
    - id: "T-04-04-5"
      category: "DoS (provider failure crashes redact_text)"
      component: "scan_for_missed_pii failure path"
      severity: "low"
      disposition: "mitigate"
      mitigation: "D-78 soft-fail: scan_for_missed_pii NEVER raises; on any exception returns (input, 0) so the caller proceeds with primary-NER results only. PERF-04 contract."
---

<objective>
Ship the optional secondary missed-PII LLM scan (D-75/D-77/D-78, SCAN-01..05). Auto-chain it inside `RedactionService._redact_text_with_registry` so every existing caller — Phase 5 chat-loop, sub-agent paths, tool flows — gets the scan for free without wiring changes. Implement the full re-run-on-replacement guard (D-76 / FR-8.5) so primary-NER positions remain consistent after replacement.

Purpose: This plan covers ROADMAP SC#4 — "with `PII_MISSED_SCAN_ENABLED=true`, secondary LLM scan runs across all 3 resolution modes; entities are validated against the configured hard-redact set (invalid types discarded); on replacement the primary NER engine re-runs." Plan 04-07 then asserts the end-to-end behavior; this plan ships the implementation.

Output: 3 files. New `missed_scan.py` module (~80 lines). New `test_missed_scan.py` (~120 lines). One splice point added to `redaction_service.py:_redact_text_with_registry` (after the existing anonymize step, before the delta computation).
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/04-fuzzy-de-anonymization-missed-pii-scan-prompt-guidance/04-CONTEXT.md
@.planning/phases/04-fuzzy-de-anonymization-missed-pii-scan-prompt-guidance/04-PATTERNS.md
@.planning/phases/04-fuzzy-de-anonymization-missed-pii-scan-prompt-guidance/04-01-config-and-migration-031-PLAN.md
@CLAUDE.md
@backend/app/services/redaction_service.py
@backend/app/services/llm_provider.py
@backend/app/services/redaction/registry.py
@backend/app/config.py
@backend/tests/unit/test_llm_provider_client.py
@backend/tests/unit/test_egress_filter.py

<interfaces>
Phase 1 + Phase 3 baseline:

```
# backend/app/config.py — Phase 1 (entity buckets) + Phase 3 D-57 (scan-enabled toggle)
class Settings(BaseSettings):
    pii_redact_entities: str = "CREDIT_CARD,US_SSN,US_ITIN,US_BANK_NUMBER,IBAN_CODE,CRYPTO,US_PASSPORT,US_DRIVER_LICENSE,MEDICAL_LICENSE,IP_ADDRESS"
    pii_missed_scan_enabled: bool = True   # Phase 3 D-57 column on system_settings (migration 030)

# backend/app/services/llm_provider.py — Phase 3 D-49
class LLMProviderClient:
    async def call(
        self,
        feature: Literal["entity_resolution", "missed_scan", "fuzzy_deanon", "title_gen", "metadata"],
        messages: list[dict],
        registry: ConversationRegistry | None = None,
        provisional_surrogates: dict[str, str] | None = None,
    ) -> dict: ...

class _EgressBlocked(Exception): ...

# backend/app/services/redaction_service.py — Phase 2/3 baseline
class RedactionService:
    @traced(name="redaction.redact_text")
    async def redact_text(self, text: str, registry: ConversationRegistry | None = None) -> RedactionResult: ...

    async def _redact_text_with_registry(self, text: str, registry: ConversationRegistry) -> RedactionResult:
        # Inside the per-thread asyncio.Lock (Phase 2 D-30 critical section).
        # Detect (Phase 1) → anonymize (Phase 1) → restore_uuids (Phase 1) → delta + upsert (Phase 2 D-32) → return.

# backend/app/services/tracing_service.py — Phase 1 D-16
def traced(name: str): ...  # decorator
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Write missed_scan.py module — Pydantic models + scan_for_missed_pii (D-75/D-77/D-78)</name>
  <files>backend/app/services/redaction/missed_scan.py</files>
  <read_first>
    - backend/app/services/redaction_service.py:156-283 (Phase 3 `_resolve_clusters_via_llm` — exact analog for try/_EgressBlocked/Exception triple-catch + WARNING log + soft-fail return shape; mirror this verbatim)
    - backend/app/services/llm_provider.py (confirm `LLMProviderClient.call(feature='missed_scan', ...)` returns a parsed dict; locate `_EgressBlocked` for import)
    - backend/app/services/tracing_service.py (Phase 1 D-16 — confirm `@traced(name=...)` decorator import path)
    - backend/app/config.py (confirm `pii_redact_entities` field shape and `pii_missed_scan_enabled` field exist)
    - .planning/phases/04-fuzzy-de-anonymization-missed-pii-scan-prompt-guidance/04-PATTERNS.md "missed_scan.py (NEW)" section (verbatim module template lines 132-254)
    - .planning/phases/04-fuzzy-de-anonymization-missed-pii-scan-prompt-guidance/04-CONTEXT.md decisions D-75 (auto-chain), D-77 (schema), D-78 (soft-fail)
  </read_first>
  <behavior>
    - When `Settings.pii_missed_scan_enabled=False`: function returns `(input_text, 0)` IMMEDIATELY without making an LLM call.
    - When enabled and LLM returns valid entities of valid types: each text occurrence is replaced with `[<TYPE>]`; counter equals total replacements via `re.subn`.
    - When LLM returns mixed valid + invalid entity types: invalid types are silently DROPPED before replacement; only valid types replace.
    - On `LLMProviderClient.call` raising `_EgressBlocked`: WARNING log `event=missed_scan_skipped feature=missed_scan error_class=_EgressBlocked`; return `(input, 0)`.
    - On `LLMProviderClient.call` raising any other exception (timeout, 5xx, network): WARNING log `event=missed_scan_skipped feature=missed_scan error_class=<exc class name>`; return `(input, 0)`.
    - On `MissedScanResponse.model_validate` raising `ValidationError`: WARNING log `event=missed_scan_skipped feature=missed_scan error_class=ValidationError`; return `(input, 0)`.
    - All log records carry counts/error-class only — NO raw input text, NO `parsed` content, NO entity values.
    - Function is decorated with `@traced(name="redaction.missed_scan")`.
  </behavior>
  <action>
Create the file `backend/app/services/redaction/missed_scan.py` with the exact content below.

```
"""LLM-based missed-PII scan (D-75 / D-77 / D-78, SCAN-01..05, FR-8.1..5).

Auto-chained inside RedactionService.redact_text after primary anonymization:
  detect → anonymize → missed-scan → re-anonymize-if-replaced → return.

D-75: scan operates on the ALREADY-ANONYMIZED text. The cloud LLM only sees
surrogates + [TYPE] placeholders — never raw real values. Privacy-safe by
construction.

D-77: response schema = list[{type, text}]; server uses re.escape(text) +
re.subn to replace ALL occurrences (handles multi-mention). Type validated
against settings.pii_redact_entities; invalid types silently dropped (FR-8.4).

D-78: soft-fail on provider failure. On timeout / 5xx / network / Pydantic
validation error: WARNING-level structured log (counts only — B4 invariant)
+ @traced span tag (scan_skipped=True). Anonymization continues with primary
NER results. PERF-04 mandates this behavior.
"""
from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.config import get_settings
from app.services.llm_provider import LLMProviderClient, _EgressBlocked
from app.services.tracing_service import traced

if TYPE_CHECKING:
    from app.services.redaction.registry import ConversationRegistry

logger = logging.getLogger(__name__)


class MissedEntity(BaseModel):
    """One missed-PII match returned by the scan LLM (D-77)."""

    model_config = ConfigDict(extra="forbid")
    type: str = Field(..., min_length=1, max_length=64)
    text: str = Field(..., min_length=1, max_length=1000)


class MissedScanResponse(BaseModel):
    """Top-level scan response. Pydantic validation = the schema gate."""

    model_config = ConfigDict(extra="forbid")
    entities: list[MissedEntity] = Field(default_factory=list, max_length=100)


def _valid_hard_redact_types() -> set[str]:
    """D-77 / FR-8.4: build the whitelist from Settings.pii_redact_entities."""
    raw = get_settings().pii_redact_entities or ""
    return {t.strip() for t in raw.split(",") if t.strip()}


@traced(name="redaction.missed_scan")
async def scan_for_missed_pii(
    anonymized_text: str,
    registry: "ConversationRegistry",
) -> tuple[str, int]:
    """D-75: run a missed-PII LLM scan over the already-anonymized text.

    Returns (possibly-modified text, replacements_count). On any failure
    returns (anonymized_text, 0) — never raises (D-78 / NFR-3 / PERF-04).
    """
    settings = get_settings()
    if not settings.pii_missed_scan_enabled:
        return anonymized_text, 0

    valid_types = _valid_hard_redact_types()
    if not valid_types:
        # No configured hard-redact types → nothing the scan could legally replace.
        return anonymized_text, 0

    messages = [
        {"role": "system", "content": (
            "Identify any PII the primary NER missed in the text below. "
            'Respond ONLY with JSON: {"entities":[{"type":"<TYPE>","text":"<verbatim substring>"}]}. '
            f"Allowed types: {sorted(valid_types)}. "
            "Return ONLY entities of those types. Do NOT include character offsets — "
            "the server matches by substring. Do NOT return surrogates that are already "
            "anonymized; only NEW PII you spot."
        )},
        {"role": "user", "content": anonymized_text},
    ]

    client = LLMProviderClient()

    try:
        result = await client.call(
            feature="missed_scan",
            messages=messages,
            registry=registry,
            provisional_surrogates=None,  # D-56: no provisional set for this feature
        )
        parsed = MissedScanResponse.model_validate(result)
    except _EgressBlocked:
        # Defense-in-depth backstop fired (Phase 3 D-53..D-56). Soft-fail.
        logger.warning(
            "event=missed_scan_skipped feature=missed_scan error_class=_EgressBlocked"
        )
        return anonymized_text, 0
    except ValidationError as exc:
        logger.warning(
            "event=missed_scan_skipped feature=missed_scan error_class=ValidationError"
        )
        return anonymized_text, 0
    except Exception as exc:  # noqa: BLE001 — D-78 catch-all (timeout / 5xx / network)
        logger.warning(
            "event=missed_scan_skipped feature=missed_scan error_class=%s",
            type(exc).__name__,
        )
        return anonymized_text, 0

    # D-77: substring-replace each valid (type, text) pair. Drop invalid types silently.
    out = anonymized_text
    replacements = 0
    for ent in parsed.entities:
        if ent.type not in valid_types:
            continue  # FR-8.4: invalid types discarded
        placeholder = f"[{ent.type}]"
        new_text, n = re.subn(re.escape(ent.text), placeholder, out)
        out = new_text
        replacements += n
    return out, replacements
```

**Constraints**:
- The except blocks MUST log error_class only — NO `text`, `messages`, `result`, `parsed`, `ent.text`, or any payload-bearing field. Plan 04-07 caplog test will assert this with literal scans.
- The `if not valid_types` short-circuit prevents an LLM call when the configured set is empty (PII_REDACT_ENTITIES env var/column blank).
- The `@traced` decorator MUST come from `app.services.tracing_service` (Phase 1 D-16) — match the import path used by `redaction_service.py`.
- Do NOT cache the `LLMProviderClient` instance at module level — Phase 3 D-50 caches the SDK clients inside `_get_client`; instantiating the wrapper each call is correct (and matches `redaction_service.py:217` pattern).

**Verification**:
```
cd backend && source venv/bin/activate
python -c "from app.services.redaction.missed_scan import scan_for_missed_pii, MissedScanResponse, MissedEntity; print('OK')"
python -c "from app.main import app; print('main OK')"
```
  </action>
  <verify>
    <automated>cd /Users/erikgunawansupriatna/claude-code-agentic-rag-masterclass-1/backend &amp;&amp; source venv/bin/activate &amp;&amp; python -c "from app.services.redaction.missed_scan import scan_for_missed_pii, MissedScanResponse, MissedEntity; import inspect; assert inspect.iscoroutinefunction(scan_for_missed_pii); ok = MissedScanResponse.model_validate({'entities':[{'type':'CREDIT_CARD','text':'4111-1111-1111-1111'}]}); assert ok.entities[0].type == 'CREDIT_CARD'; print('OK')" &amp;&amp; python -c "from app.main import app; print('main OK')"</automated>
  </verify>
  <acceptance_criteria>
    - `test -f backend/app/services/redaction/missed_scan.py` exits 0.
    - `grep -c '^async def scan_for_missed_pii' backend/app/services/redaction/missed_scan.py` returns exactly 1.
    - `grep -c '^class MissedEntity(BaseModel):' backend/app/services/redaction/missed_scan.py` returns exactly 1.
    - `grep -c '^class MissedScanResponse(BaseModel):' backend/app/services/redaction/missed_scan.py` returns exactly 1.
    - `grep -c '@traced(name="redaction.missed_scan")' backend/app/services/redaction/missed_scan.py` returns exactly 1.
    - `grep -c "feature=\"missed_scan\"" backend/app/services/redaction/missed_scan.py` returns exactly 1.
    - `grep -c '_EgressBlocked' backend/app/services/redaction/missed_scan.py` returns ≥ 2 (import + except).
    - `grep -c 'event=missed_scan_skipped' backend/app/services/redaction/missed_scan.py` returns exactly 3 (one per except: _EgressBlocked, ValidationError, generic Exception).
    - `grep -c 'pii_missed_scan_enabled' backend/app/services/redaction/missed_scan.py` returns ≥ 1 (D-75 gating).
    - `grep -c 'pii_redact_entities' backend/app/services/redaction/missed_scan.py` returns ≥ 1 (FR-8.4 whitelist source).
    - `grep -cE 'logger\.(warning|info|debug)\(' backend/app/services/redaction/missed_scan.py | head -1` returns ≥ 3, AND every match string is a counts/error_class log line — `grep -E 'logger\.(warning|info|debug)' backend/app/services/redaction/missed_scan.py | grep -vE 'event=|error_class='` returns 0 (no payload-bearing log lines).
    - `cd backend && source venv/bin/activate && python -m py_compile app/services/redaction/missed_scan.py` exits 0.
    - `cd backend && source venv/bin/activate && python -c "from app.services.redaction.missed_scan import scan_for_missed_pii"` exits 0.
    - `python -c "from app.main import app"` succeeds.
  </acceptance_criteria>
  <done>
missed_scan.py exists with the full module surface from `<interfaces>`. Behavior aligns with all 7 items in `<behavior>`. The module is import-clean, soft-fails on every error class, and emits zero raw-PII log lines.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Auto-chain scan_for_missed_pii inside _redact_text_with_registry with single-re-run cap (D-75/D-76)</name>
  <files>backend/app/services/redaction_service.py</files>
  <read_first>
    - backend/app/services/redaction_service.py (the file being modified — locate `_redact_text_with_registry` near lines 439-602; identify the variable name carrying anonymized text after `restore_uuids` near line 503; identify the existing asyncio.Lock acquire/release pattern lines 373-389)
    - .planning/phases/04-fuzzy-de-anonymization-missed-pii-scan-prompt-guidance/04-PATTERNS.md "Splice point 2 — auto-chain missed-scan inside `redact_text`" section (lines 721-742)
    - .planning/phases/04-fuzzy-de-anonymization-missed-pii-scan-prompt-guidance/04-CONTEXT.md decisions D-75 (auto-chain), D-76 (full re-run on replacement, single-re-run cap)
    - .planning/phases/04-fuzzy-de-anonymization-missed-pii-scan-prompt-guidance/04-04-missed-scan-and-auto-chain-PLAN.md Task 1 above (the `scan_for_missed_pii` contract this task imports)
  </read_first>
  <behavior>
    - `_redact_text_with_registry(text, registry)` (existing public-ish call site signature) continues to work unchanged.
    - New private kwarg added: `_scan_rerun_done: bool = False` — controls whether the auto-chain block runs.
    - On first call (`_scan_rerun_done=False`): after the existing anonymize step completes (just before delta computation / upsert), call `scan_for_missed_pii(anonymized_text, registry)`. If `replacements > 0` AND `scanned_text != anonymized_text`: call `self._redact_text_with_registry(scanned_text, registry, _scan_rerun_done=True)` and return its result directly (the re-entrant call computes a fresh delta + upsert + RedactionResult on the modified text per D-76).
    - If `replacements == 0` OR `scanned_text == anonymized_text`: continue with the existing flow (delta computation on `anonymized_text` — unchanged).
    - On second call (`_scan_rerun_done=True`): the auto-chain block is BYPASSED (D-76 single-re-run cap). The function uses the pre-computed `anonymized_text` (which is the previous call's `scanned_text`) and proceeds to delta computation. The second pass MUST NOT trigger a third.
  </behavior>
  <action>
**Step 1 — Add the import** at the top of `redaction_service.py` (with other Phase 4 imports if Plan 04-03 already added a similar block; otherwise just below the Phase 3 imports):

```
from app.services.redaction.missed_scan import scan_for_missed_pii
```

**Step 2 — Extend the signature** of `_redact_text_with_registry` to add the private kwarg:

```
async def _redact_text_with_registry(
    self,
    text: str,
    registry: ConversationRegistry,
    _scan_rerun_done: bool = False,  # NEW (D-76 single-re-run cap)
) -> RedactionResult:
```

**Step 3 — Splice the auto-chain block** AFTER the existing `restore_uuids` call (line ~503 per PATTERNS.md) and BEFORE the existing delta-computation loop (line ~514). Use the EXACT variable name carrying anonymized text from the existing code (PATTERNS.md uses `anonymized_text`; verify before editing):

```
# Phase 4 D-75: auto-chain missed-PII scan unless this is the re-run pass.
# D-76: single-re-run cap — after one re-run, do NOT scan again.
if not _scan_rerun_done:
    scanned_text, scan_replacements = await scan_for_missed_pii(
        anonymized_text, registry
    )
    if scan_replacements > 0 and scanned_text != anonymized_text:
        # D-76 / FR-8.5: full re-run of redact_text on the modified text.
        # Re-entrant call computes a fresh delta + upsert against the new
        # surrogate positions. The _scan_rerun_done=True kwarg prevents
        # unbounded recursion (single re-run cap).
        return await self._redact_text_with_registry(
            scanned_text, registry, _scan_rerun_done=True
        )
```

**Step 4 — Add span attributes** at the END of the method body (just before the `return RedactionResult(...)` statement). Match the pattern Phase 3 D-63 already uses; PATTERNS.md template at lines 745-754 shows the form. The new attributes:

```
# Phase 4 D-63 / B4: counts only. NEVER real values.
try:
    from app.services.tracing_service import current_span
    span = current_span()
    if span is not None:
        span.set_attribute("missed_scan_enabled", get_settings().pii_missed_scan_enabled)
        span.set_attribute("missed_scan_replacements", scan_replacements if not _scan_rerun_done else 0)
        span.set_attribute("scan_rerun_pass", _scan_rerun_done)
except Exception:
    pass  # tracing must NEVER affect functional behavior
```
(If the existing codebase uses a different span-API surface, match the in-file Phase 3 instrumentation pattern verbatim. Read the file to confirm.)

**Constraints**:
- DO NOT modify the asyncio.Lock acquisition (lines 373-389). The new scan call runs INSIDE the existing critical section per D-75 and Phase 2 D-30.
- DO NOT modify any existing detection / anonymization / delta / upsert logic. The splice is purely additive.
- The re-entrant call path is `await self._redact_text_with_registry(scanned_text, registry, _scan_rerun_done=True)`. The lock is reentrant — wait, asyncio.Lock is NOT reentrant. Confirm by reading the existing lock implementation: if Phase 2 acquired the lock OUTSIDE `_redact_text_with_registry` (e.g., in the public `redact_text` wrapper), then the re-entrant call inside `_redact_text_with_registry` is FINE because the lock is already held by the parent frame (no re-acquisition). If Phase 2 acquired the lock INSIDE `_redact_text_with_registry`, the re-entrant call would deadlock — in that case, restructure: extract the post-lock body into `_redact_body` and have the re-run call `_redact_body` (still inside the same lock). PATTERNS.md note at lines 1073-1078 says "Phase 4's missed-scan + re-run runs INSIDE the existing per-thread asyncio.Lock. NO new lock surface" — confirm by reading the file BEFORE writing the splice. If the read reveals the lock is acquired in `_redact_text_with_registry` itself, document the deviation in 04-04-SUMMARY.md and adjust the splice to avoid re-entry.

**Verification**:
```
cd backend && source venv/bin/activate
python -c "from app.services.redaction_service import RedactionService; import inspect; sig = inspect.signature(RedactionService._redact_text_with_registry); assert '_scan_rerun_done' in sig.parameters; assert sig.parameters['_scan_rerun_done'].default is False; print('OK')"
python -c "from app.main import app; print('main OK')"
pytest tests/ -x --tb=short -q
```
The pytest run should still be green at the Phase 1+2+3 baseline (mock LLM calls in test fixtures will short-circuit; production behavior changes only when `pii_missed_scan_enabled=True` AND the scan returns entities).
  </action>
  <verify>
    <automated>cd /Users/erikgunawansupriatna/claude-code-agentic-rag-masterclass-1/backend &amp;&amp; source venv/bin/activate &amp;&amp; python -c "from app.services.redaction_service import RedactionService; import inspect; sig = inspect.signature(RedactionService._redact_text_with_registry); assert '_scan_rerun_done' in sig.parameters; assert sig.parameters['_scan_rerun_done'].default is False; print('OK')" &amp;&amp; pytest tests/ -x --tb=short -q</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c 'from app.services.redaction.missed_scan import scan_for_missed_pii' backend/app/services/redaction_service.py` returns exactly 1.
    - `grep -cE '_scan_rerun_done:\s*bool\s*=\s*False' backend/app/services/redaction_service.py` returns exactly 1.
    - `grep -c 'await scan_for_missed_pii(' backend/app/services/redaction_service.py` returns exactly 1.
    - `grep -c '_scan_rerun_done=True' backend/app/services/redaction_service.py` returns exactly 1 (re-entrant call passes True).
    - `grep -c 'set_attribute("missed_scan_replacements"' backend/app/services/redaction_service.py` returns ≥ 1.
    - Inspect: `python -c "from app.services.redaction_service import RedactionService; import inspect; sig = inspect.signature(RedactionService._redact_text_with_registry); assert sig.parameters['_scan_rerun_done'].default is False"` exits 0.
    - `pytest tests/ -x --tb=short` exits 0 — Phase 1+2+3 79/79 still green (existing tests use mocked or default-disabled scan paths; baseline preserved).
    - `python -c "from app.main import app"` succeeds.
  </acceptance_criteria>
  <done>
The auto-chain splice is in place. Single-re-run cap prevents recursion. Phase 1+2+3 regression suite still green. The Phase 5 chat-loop integration will get scanning for free.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: Write test_missed_scan.py covering D-75/D-77/D-78 invariants</name>
  <files>backend/tests/unit/test_missed_scan.py</files>
  <read_first>
    - backend/tests/unit/test_llm_provider_client.py (Phase 3 D-65 — exact analog: mock fixtures `_clear_client_cache` autouse + `_StubRegistry` duck-type + `MagicMock + AsyncMock` for AsyncOpenAI; mirror this verbatim)
    - backend/app/services/redaction/missed_scan.py (Task 1 output — confirm imports match the test surface)
    - .planning/phases/04-fuzzy-de-anonymization-missed-pii-scan-prompt-guidance/04-PATTERNS.md "test_missed_scan.py (NEW — unit, mocked SDK)" section (template lines 408-502)
    - .planning/phases/04-fuzzy-de-anonymization-missed-pii-scan-prompt-guidance/04-CONTEXT.md decisions D-75/D-77/D-78
  </read_first>
  <behavior>
    Test classes:
    - `TestD75_FeatureGated` — `pii_missed_scan_enabled=False` → returns `(input, 0)` with no LLM call.
    - `TestD77_SchemaValidation` — invalid types are dropped; valid types replace via `re.subn(re.escape(text), [TYPE], ...)`; multi-mention handling.
    - `TestD78_SoftFail_ProviderError` — generic 5xx-style Exception → returns `(input, 0)`; WARNING log carries error_class only; no raw text in any log record.
    - `TestD78_SoftFail_EgressBlocked` — `_EgressBlocked` → returns `(input, 0)`; specific error_class string in log.
    - `TestD78_SoftFail_ValidationError` — Pydantic ValidationError on malformed LLM JSON → returns `(input, 0)`.
    - `TestSubstringMatch_ReEscape` — entity text containing regex metachars (e.g., `+62-21-555-1234` with `+`) is correctly replaced via `re.escape`.
  </behavior>
  <action>
Create `backend/tests/unit/test_missed_scan.py` with the exact content below.

```
"""Unit tests for missed_scan.scan_for_missed_pii (D-75 / D-77 / D-78).

Mirrors the mock-SDK shape of test_llm_provider_client.py (Phase 3 D-65).
"""
from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.redaction.missed_scan import (
    MissedEntity,
    MissedScanResponse,
    scan_for_missed_pii,
)


# ─────────────────────────── Stubs / fixtures ────────────────────────────


@dataclass(frozen=True)
class _StubMapping:
    real_value: str
    surrogate_value: str
    entity_type: str
    cluster_id: str | None = None


class _StubRegistry:
    def __init__(self, mappings):
        self._mappings = list(mappings)

    def entries(self):
        return self._mappings


@pytest.fixture(autouse=True)
def _clear_client_cache():
    """Phase 3 D-65 fixture pattern — keep llm_provider client cache clean."""
    from app.services import llm_provider
    llm_provider._clients.clear()
    yield
    llm_provider._clients.clear()


def _patched_settings(*, scan_enabled: bool = True, redact_entities: str | None = None) -> SimpleNamespace:
    """Build a Settings stub honoring the fields scan_for_missed_pii reads."""
    from app.config import get_settings as real_settings
    real = real_settings()
    overrides = real.model_dump()
    overrides["pii_missed_scan_enabled"] = scan_enabled
    if redact_entities is not None:
        overrides["pii_redact_entities"] = redact_entities
    return SimpleNamespace(**overrides)


def _mock_llm_response(json_content: str) -> MagicMock:
    """Build a MagicMock chat.completions.create return value (Phase 3 D-65 pattern)."""
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(message=MagicMock(content=json_content))
    ]
    return mock_response


# ─────────────────────────── Tests ───────────────────────────────────────


class TestD75_FeatureGated:
    """D-75: pii_missed_scan_enabled=False → no LLM call, return text unchanged."""

    @pytest.mark.asyncio
    async def test_disabled_returns_input_unchanged(self):
        with patch(
            "app.services.redaction.missed_scan.get_settings",
            return_value=_patched_settings(scan_enabled=False),
        ):
            text, n = await scan_for_missed_pii("foo bar", _StubRegistry([]))
        assert (text, n) == ("foo bar", 0)

    @pytest.mark.asyncio
    async def test_empty_redact_entities_returns_input_unchanged(self):
        # If pii_redact_entities is empty, scan can't legally replace anything.
        with patch(
            "app.services.redaction.missed_scan.get_settings",
            return_value=_patched_settings(scan_enabled=True, redact_entities=""),
        ):
            text, n = await scan_for_missed_pii("hello world", _StubRegistry([]))
        assert (text, n) == ("hello world", 0)


class TestD77_SchemaValidation:
    """D-77 / FR-8.4: invalid types dropped; valid types replace via re.escape substring match."""

    @pytest.mark.asyncio
    async def test_invalid_type_dropped_valid_type_replaced(self):
        json = (
            '{"entities":['
            '{"type":"CREDIT_CARD","text":"4111-1111-1111-1111"},'
            '{"type":"NOT_A_REAL_TYPE","text":"foo"}'
            ']}'
        )
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=_mock_llm_response(json))
        with patch(
            "app.services.redaction.missed_scan.get_settings",
            return_value=_patched_settings(redact_entities="CREDIT_CARD,US_SSN"),
        ), patch("app.services.llm_provider._get_client", return_value=mock_client):
            text, n = await scan_for_missed_pii(
                "card 4111-1111-1111-1111 and foo here",
                _StubRegistry([]),
            )
        assert "[CREDIT_CARD]" in text
        assert "4111-1111-1111-1111" not in text
        assert "foo" in text  # invalid type was discarded
        assert n >= 1

    @pytest.mark.asyncio
    async def test_multi_mention_replaces_all(self):
        json = '{"entities":[{"type":"US_SSN","text":"123-45-6789"}]}'
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=_mock_llm_response(json))
        with patch(
            "app.services.redaction.missed_scan.get_settings",
            return_value=_patched_settings(redact_entities="US_SSN"),
        ), patch("app.services.llm_provider._get_client", return_value=mock_client):
            text, n = await scan_for_missed_pii(
                "first 123-45-6789 second 123-45-6789 third",
                _StubRegistry([]),
            )
        assert text.count("[US_SSN]") == 2
        assert "123-45-6789" not in text
        assert n == 2


class TestSubstringMatch_ReEscape:
    """D-77 substring-match must re.escape regex metachars (phone-number `+`)."""

    @pytest.mark.asyncio
    async def test_phone_number_with_plus_replaced(self):
        json = '{"entities":[{"type":"PHONE_NUMBER","text":"+62-21-555-1234"}]}'
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=_mock_llm_response(json))
        with patch(
            "app.services.redaction.missed_scan.get_settings",
            return_value=_patched_settings(redact_entities="PHONE_NUMBER"),
        ), patch("app.services.llm_provider._get_client", return_value=mock_client):
            text, n = await scan_for_missed_pii(
                "Reach me at +62-21-555-1234 anytime.",
                _StubRegistry([]),
            )
        assert "[PHONE_NUMBER]" in text
        assert "+62-21-555-1234" not in text


class TestD78_SoftFail_ProviderError:
    """D-78: generic Exception → log warn, return (text, 0). NEVER raise."""

    @pytest.mark.asyncio
    async def test_sdk_5xx_returns_input_unchanged(self, caplog):
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(side_effect=RuntimeError("503"))
        with patch(
            "app.services.redaction.missed_scan.get_settings",
            return_value=_patched_settings(redact_entities="CREDIT_CARD"),
        ), patch("app.services.llm_provider._get_client", return_value=mock_client):
            with caplog.at_level("WARNING"):
                text, n = await scan_for_missed_pii(
                    "the secret is hello-world", _StubRegistry([])
                )
        assert (text, n) == ("the secret is hello-world", 0)
        # Soft-fail log present
        assert any("missed_scan_skipped" in r.getMessage() for r in caplog.records)
        # B4 invariant: log line must carry error_class, NOT raw payload.
        for r in caplog.records:
            msg = r.getMessage()
            assert "the secret is hello-world" not in msg
            assert "hello-world" not in msg


class TestD78_SoftFail_EgressBlocked:
    """D-78: _EgressBlocked → log warn with error_class=_EgressBlocked, return (text, 0)."""

    @pytest.mark.asyncio
    async def test_egress_blocked_returns_input_unchanged(self, caplog):
        from app.services.llm_provider import _EgressBlocked

        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(
            side_effect=_EgressBlocked("registry match")
        )
        with patch(
            "app.services.redaction.missed_scan.get_settings",
            return_value=_patched_settings(redact_entities="CREDIT_CARD"),
        ), patch("app.services.llm_provider._get_client", return_value=mock_client):
            with caplog.at_level("WARNING"):
                text, n = await scan_for_missed_pii("hello", _StubRegistry([]))
        assert (text, n) == ("hello", 0)
        assert any("error_class=_EgressBlocked" in r.getMessage() for r in caplog.records)


class TestD78_SoftFail_ValidationError:
    """D-78: malformed JSON → ValidationError caught → return (text, 0)."""

    @pytest.mark.asyncio
    async def test_malformed_response_returns_input_unchanged(self, caplog):
        # Return a non-conforming JSON shape — Pydantic rejects.
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(
            return_value=_mock_llm_response('{"wrong_key": "value"}')
        )
        with patch(
            "app.services.redaction.missed_scan.get_settings",
            return_value=_patched_settings(redact_entities="CREDIT_CARD"),
        ), patch("app.services.llm_provider._get_client", return_value=mock_client):
            with caplog.at_level("WARNING"):
                text, n = await scan_for_missed_pii("hello", _StubRegistry([]))
        assert (text, n) == ("hello", 0)
        assert any("error_class=ValidationError" in r.getMessage() for r in caplog.records)


class TestPydanticSchema:
    """D-77: schema-only sanity checks on MissedEntity / MissedScanResponse."""

    def test_extra_fields_rejected(self):
        from pydantic import ValidationError as VE
        with pytest.raises(VE):
            MissedEntity.model_validate(
                {"type": "CREDIT_CARD", "text": "x", "extra": "nope"}
            )

    def test_empty_text_rejected(self):
        from pydantic import ValidationError as VE
        with pytest.raises(VE):
            MissedEntity.model_validate({"type": "CREDIT_CARD", "text": ""})

    def test_text_max_length_enforced(self):
        from pydantic import ValidationError as VE
        with pytest.raises(VE):
            MissedEntity.model_validate({"type": "CREDIT_CARD", "text": "x" * 1001})
```

**Notes**:
- The `_get_client` patch path matches Phase 3 D-65's pattern: `patch("app.services.llm_provider._get_client", return_value=mock_client)`. If Phase 3's actual patch path differs, mirror that — read `tests/unit/test_llm_provider_client.py` to confirm.
- The `LLMProviderClient.call` internally uses `_get_client` to obtain the cached `AsyncOpenAI`; mocking `_get_client` short-circuits the egress filter properly because the filter runs BEFORE `_get_client` is called (only on `provider='cloud'`). When the test does NOT explicitly set provider, the default falls through to `local` → no egress filter → mock just returns the canned response. For `_EgressBlocked` we directly raise from `chat.completions.create`. If Phase 3 wraps `_EgressBlocked` differently (e.g., raised by the egress filter BEFORE `chat.completions.create`), adjust the side_effect target accordingly — read `llm_provider.py` to confirm.

**Verification**:
```
cd backend && source venv/bin/activate
pytest tests/unit/test_missed_scan.py -v --tb=short
pytest tests/ -x --tb=short -q
```
  </action>
  <verify>
    <automated>cd /Users/erikgunawansupriatna/claude-code-agentic-rag-masterclass-1/backend &amp;&amp; source venv/bin/activate &amp;&amp; pytest tests/unit/test_missed_scan.py -v --tb=short</automated>
  </verify>
  <acceptance_criteria>
    - `test -f backend/tests/unit/test_missed_scan.py` exits 0.
    - `grep -cE '^class Test(D75_FeatureGated|D77_SchemaValidation|SubstringMatch_ReEscape|D78_SoftFail_ProviderError|D78_SoftFail_EgressBlocked|D78_SoftFail_ValidationError|PydanticSchema)' backend/tests/unit/test_missed_scan.py` returns exactly 7.
    - `pytest backend/tests/unit/test_missed_scan.py -v` exits 0; all collected tests PASS.
    - `pytest backend/tests/unit/ -v --tb=short` exits 0 — Phase 1+2+3 unit tests do NOT regress.
    - At least 3 caplog assertions in the file scan log records for forbidden raw-PII strings (B4 invariant): `grep -cE 'assert.*not in.*r\.getMessage|assert.*not in.*msg' backend/tests/unit/test_missed_scan.py` returns ≥ 1.
    - `grep -c 'error_class=_EgressBlocked' backend/tests/unit/test_missed_scan.py` returns ≥ 1.
    - `grep -c 'error_class=ValidationError' backend/tests/unit/test_missed_scan.py` returns ≥ 1.
  </acceptance_criteria>
  <done>
test_missed_scan.py runs green. Coverage spans D-75 (gating), D-77 (schema + whitelist + multi-mention + re.escape), D-78 (3 soft-fail variants + caplog B4 assertion). Phase 1+2+3 unit-test suite continues to pass.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| `RedactionService._redact_text_with_registry` → `scan_for_missed_pii` → `LLMProviderClient.call` | Internal in-process call → cloud egress only when provider='cloud'. |
| `MissedScanResponse` (untrusted LLM JSON) → server-side type whitelist + re.escape replace | Untrusted input crossing into modified text. |

## STRIDE Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation |
|-----------|----------|-----------|----------|-------------|------------|
| T-04-04-1 | Information Disclosure (cloud LLM payload) | `scan_for_missed_pii` request | low | mitigate | D-75 invariant: scan operates on already-anonymized text (surrogates + `[TYPE]` placeholders) — no real values present. Phase 3 D-53..D-56 egress filter wraps as defense-in-depth. |
| T-04-04-2 | Tampering (LLM injects fabricated entity types) | `MissedScanResponse` parse | high | mitigate | D-77 / FR-8.4 server-side whitelist: `valid_types = set(settings.pii_redact_entities.split(','))`; iterate `parsed.entities` and SKIP any `type not in valid_types`. Pydantic validates schema; server enforces type semantics. Plan 04-07 TestSC4 asserts mocked LLM with mixed valid+invalid types only replaces valid ones. |
| T-04-04-3 | Information Disclosure (PII in soft-fail logs) | WARNING log | high | mitigate | D-78: log carries `event=missed_scan_skipped feature=missed_scan error_class=<TypeName>` ONLY. NEVER `text`, `parsed`, `messages`, or any payload-bearing field. Test `TestD78_SoftFail_ProviderError` asserts no raw text in log records (B4 invariant). |
| T-04-04-4 | DoS (unbounded re-run recursion) | `_redact_text_with_registry` re-entry | low | mitigate | D-76 single re-run cap: private `_scan_rerun_done: bool = False` kwarg; second pass sets True; auto-chain block bypassed when True. O(2) call ceiling. |
| T-04-04-5 | DoS (provider failure crashes redact_text) | `scan_for_missed_pii` exception path | low | mitigate | D-78 soft-fail: triple-catch `_EgressBlocked` / `ValidationError` / generic `Exception`. NEVER raises. Caller proceeds with primary-NER results. PERF-04 contract. |
| T-04-04-6 | Tampering (substring-match collateral damage) | `re.subn(re.escape(text), [TYPE], anonymized_text)` | medium | accept | The replace target is server-validated (`text` from LLM, max 1000 chars per Pydantic Field). Worst case: a benign substring matches a longer surrogate and gets partially replaced. Phase 4 accepts this risk because `[TYPE]` is non-PII; the alternative (positional match) is fragile per D-77 rationale (LLMs are unreliable at offsets). PERF-02 in Phase 6 may revisit. |

## Cross-plan threats covered elsewhere
- **T-1 (raw PII to cloud LLM via fuzzy LLM mode):** Plan 04-03 handles via D-73 placeholder-tokenization.
- **T-5 (prompt injection via guidance block):** Plan 04-05.
</threat_model>

<verification>
- `pytest tests/unit/test_missed_scan.py -v` is green.
- `pytest tests/ -x --tb=short` (full suite from `backend/`) is green — 79/79 Phase 1+2+3 baseline preserved (existing tests use mocked or default-disabled scan paths).
- `python -c "from app.main import app"` succeeds (PostToolUse import-check).
- Plan 04-07 integration test `TestSC4_MissedScan` will exercise the auto-chain end-to-end against live registry + mocked LLM — that's where SC#4 is verified holistically.
</verification>

<success_criteria>
- D-75 auto-chain: `_redact_text_with_registry` calls `scan_for_missed_pii` after the existing anonymize step; the splice runs INSIDE the per-thread asyncio.Lock.
- D-76 full re-run: when scan replaces ≥1 entity, the method calls itself with `_scan_rerun_done=True`; primary-NER positions are recomputed on the modified text.
- D-77 schema + whitelist: `MissedScanResponse` Pydantic-validated; server drops invalid types before replacement; substring match via `re.escape`.
- D-78 soft-fail: every error path logs `event=missed_scan_skipped` + `error_class=<TypeName>` (counts only — B4); function NEVER raises.
- 79/79 Phase 1+2+3 regression suite still green.
- Unit test coverage spans 7 test classes pinning D-75/D-77/D-78/Pydantic-schema invariants.
</success_criteria>

<output>
After completion, create `.planning/phases/04-fuzzy-de-anonymization-missed-pii-scan-prompt-guidance/04-04-SUMMARY.md` capturing: missed_scan.py module path + line count, redaction_service.py splice line numbers (added kwarg, scan call, span attrs), test count + green status, the asyncio.Lock re-entry note (whether the lock is acquired in the caller or in `_redact_text_with_registry` itself — informs the re-entrant call shape), and any deviations from the verbatim templates.
</output>
</content>
