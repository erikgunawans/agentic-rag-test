---
phase: 04-fuzzy-de-anonymization-missed-pii-scan-prompt-guidance
plan: 03
type: execute
wave: 3
depends_on: [01, 02]
files_modified:
  - backend/app/services/redaction_service.py
autonomous: true
requirements_addressed: [DEANON-03, DEANON-04, DEANON-05]
tags: [pii, de-anonymization, fuzzy-deanon, 3-phase-pipeline, llm-provider, placeholder-tokenization]
must_haves:
  truths:
    - "de_anonymize_text accepts an optional `mode: Literal['algorithmic','llm','none'] | None = None` parameter (D-71); when None, resolves via Settings.fuzzy_deanon_mode; existing Phase 2 callers pass mode=None and continue to work unchanged"
    - "The 3-phase pipeline runs: Pass 1 surrogate→<<PH_xxxx>> (existing Phase 2) → Pass 2 fuzzy/LLM-match remaining text against per-cluster variants (NEW) → Pass 3 <<PH_xxxx>>→real_value (existing Phase 2). Pass 2 is BYPASSED when mode='none'"
    - "Pass 2 algorithmic branch (D-72): per cluster, build the variant set from registry entries grouped by cluster_id; call fuzzy_match.best_match against each cluster's variants; replace matched span with the cluster's <<PH_xxxx>> token; threshold from Settings.fuzzy_deanon_threshold"
    - "Pass 2 LLM branch (D-72/D-73): builds messages with placeholder-tokenized text + JSON variant list; calls LLMProviderClient.call(feature='fuzzy_deanon', registry=registry, provisional_surrogates=None); cloud mode sees ZERO raw real values; egress filter (Phase 3 D-53..D-56) wraps as defense-in-depth"
    - "Pass 2 LLM response is Pydantic-validated via _FuzzyMatchResponse model (D-73): {matches: [{span: str, token: str}]}; server validates that returned token is a member of Pass-1's placeholders dict; server resolves spans via re.escape(span) substring search"
    - "On LLM call failure (timeout, 5xx, ValidationError, _EgressBlocked): soft-fail per D-78 — fall back to algorithmic Pass 2 when settings.llm_provider_fallback_enabled=true (D-52); else skip Pass 2; logs error_class only (B4 invariant)"
    - "Hard-redacted [ENTITY_TYPE] placeholders survive de-anon unchanged in all 3 modes (D-74) — STRUCTURAL invariant inherited from Phase 2 D-24/REG-05: hard-redacts are never in registry, therefore never in placeholder map, therefore never resolved away"
    - "Phase 2 round-trip tests (DEANON-01, DEANON-02) remain green — backward compatibility preserved by mode=None default"
    - "Span attributes added: fuzzy_deanon_mode, fuzzy_matches_resolved (counts only — Phase 1 D-18 + Phase 2 D-41 + B4 invariants honored)"
  artifacts:
    - path: "backend/app/services/redaction_service.py"
      provides: "de_anonymize_text 3-phase upgrade with optional mode param + Pass 2 fuzzy step + LLM mode dispatch + soft-fail fallback"
      contains: "mode: Literal[\"algorithmic\", \"llm\", \"none\"] | None"
  key_links:
    - from: "redaction_service.py:de_anonymize_text Pass 2 (algorithmic)"
      to: "backend/app/services/redaction/fuzzy_match.py:best_match"
      via: "from app.services.redaction.fuzzy_match import best_match"
      pattern: "best_match\\("
    - from: "redaction_service.py:de_anonymize_text Pass 2 (llm)"
      to: "backend/app/services/llm_provider.py:LLMProviderClient.call"
      via: "await client.call(feature='fuzzy_deanon', ...)"
      pattern: "feature\\s*=\\s*['\\\"]fuzzy_deanon['\\\"]"
    - from: "redaction_service.py:de_anonymize_text"
      to: "Settings.fuzzy_deanon_mode + Settings.fuzzy_deanon_threshold (Plan 04-01)"
      via: "get_settings() reads — flows through 60s TTL cache per Phase 2 D-21 / SET-01"
      pattern: "get_settings\\(\\)\\.fuzzy_deanon_(mode|threshold)"
threat_model:
  trust_boundaries:
    - "Caller (Plan 5 SSE de-anon site / Plan 04-07 integration tests) → de_anonymize_text → Pass 2 LLM dispatch → LLMProviderClient.call (cloud egress crossing only when mode='llm' AND provider='cloud')"
    - "registry.entries() (in-memory ConversationRegistry + persisted Supabase rows) → cluster variant lookup (read-only)"
  threats:
    - id: "T-04-03-1"
      category: "Information Disclosure (raw PII reaching cloud LLM via fuzzy LLM mode)"
      component: "Pass 2 LLM branch — cloud-mode call payload"
      severity: "high"
      disposition: "mitigate"
      mitigation: "D-73 invariant: cloud-mode payload = (a) Pass-1-output text where every known surrogate is ALREADY replaced by <<PH_xxxx>> placeholder (no real values present after Pass 1; only mangled-surrogate text + opaque tokens), (b) JSON variant list containing only canonical surrogate names + cluster sub-variants — all surrogate-form per Phase 1+2+3 invariants. Defense-in-depth backstop: Phase 3 D-53..D-56 pre-flight egress filter still runs against the cloud payload via LLMProviderClient.call (registry + provisional set scan). Plan 04-07 TestSC2_NoSurnameCollision + TestB4_LogPrivacy assert no raw values in payload or logs."
    - id: "T-04-03-2"
      category: "Spoofing (LLM fabricates an invalid placeholder token → wrong cluster resolution)"
      component: "_FuzzyMatchResponse parse — token field"
      severity: "medium"
      disposition: "mitigate"
      mitigation: "Two-layer validation: (1) Pydantic Field pattern `^<<PH_[0-9a-f]+>>$` rejects malformed tokens at parse; (2) server checks each returned token is a key in the Pass-1 placeholders dict — tokens not present are silently dropped. LLM cannot inject a token that maps to a foreign cluster because Pass 1's dict is the only source of truth."
    - id: "T-04-03-3"
      category: "Tampering (hard-redact placeholder leak via fuzzy match)"
      component: "Pass 2 (any mode) — hard-redact survival"
      severity: "high"
      disposition: "mitigate"
      mitigation: "D-74 STRUCTURAL invariant: hard-redact [ENTITY_TYPE] placeholders are NEVER in registry per Phase 2 D-24/REG-05. Pass 1 cannot match them (not in registry → no <<PH_xxxx>> minted for them); Pass 2 variants come from registry.entries() filtered by cluster — also cannot contain [TYPE]; Pass 3 only knows <<PH_xxxx>>, not [TYPE]. Hard-redacts pass through unmodified in all 3 modes. Plan 04-07 TestSC3_HardRedactSurvives parametrized test asserts identity preservation across modes."
    - id: "T-04-03-4"
      category: "DoS (LLM provider failure cascading)"
      component: "Pass 2 LLM branch — provider call failure"
      severity: "low"
      disposition: "mitigate"
      mitigation: "Soft-fail per D-78 / NFR-3: on provider failure (TimeoutError, HTTPError, ValidationError, _EgressBlocked) the method falls back to algorithmic Pass 2 (when settings.llm_provider_fallback_enabled=true per D-52) or skips Pass 2 entirely (else); WARNING log carries error_class only (B4 invariant per D-78)."
    - id: "T-04-03-5"
      category: "Information Disclosure (raw value in @traced span attributes)"
      component: "Pass 2 instrumentation"
      severity: "medium"
      disposition: "mitigate"
      mitigation: "D-63 + B4 invariant: span attributes are counts and mode strings ONLY (fuzzy_deanon_mode, fuzzy_matches_resolved, fuzzy_provider_fallback). NEVER set attributes containing real values, surrogate values, candidate strings, or matched text."
---

<objective>
In-place upgrade of `RedactionService.de_anonymize_text` to the production-grade 3-phase placeholder-tokenized pipeline (D-71/D-72/D-73/D-74). Adds the optional `mode` parameter, inserts Pass 2 fuzzy/LLM-match step BETWEEN existing Pass 1 (surrogate→placeholder) and Pass 3 (placeholder→real), and dispatches to the algorithmic matcher (Plan 04-02) or the cloud/local LLM (Phase 3 LLMProviderClient) per mode.

Purpose: This is the load-bearing service-layer change for Phase 4 SC#1 (mangled-surrogate de-anon), SC#2 (no surname-collision corruption), and SC#3 (hard-redact survival). The Phase 2 docstring at `redaction_service.py:612-615` already promised this in-place extension — Plan 04-03 cashes that IOU without rewriting any Phase 2 caller.

Output: Single file modified. New helper methods `_fuzzy_match_algorithmic` and `_fuzzy_match_llm` added on the service class. New private Pydantic models `_FuzzyMatch` + `_FuzzyMatchResponse` (module-scope). Existing Phase 2 callers continue to pass `mode=None` (or omit it) and get identical behavior to today.
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
@.planning/phases/04-fuzzy-de-anonymization-missed-pii-scan-prompt-guidance/04-02-fuzzy-match-algorithmic-PLAN.md
@CLAUDE.md
@backend/app/services/redaction_service.py
@backend/app/services/llm_provider.py
@backend/app/services/redaction/fuzzy_match.py
@backend/app/services/redaction/registry.py

<interfaces>
Phase 2 baseline (this method is upgraded in-place):

```
@traced(name="redaction.de_anonymize_text")
async def de_anonymize_text(self, text: str, registry: ConversationRegistry) -> str:
    # Pass 1 (lines 631-662): surrogate → <<PH_xxxx>> placeholder; build placeholders dict.
    # Pass 2 (lines 664-668): <<PH_xxxx>> → real_value.
```

Plan 04-02 contract (already shipped at this wave):

```
def best_match(candidate: str, variants: list[str], threshold: float = 0.85) -> tuple[str, float] | None
```

Phase 3 LLMProviderClient (already shipped):

```
class LLMProviderClient:
    async def call(
        self,
        feature: Literal["entity_resolution", "missed_scan", "fuzzy_deanon", "title_gen", "metadata"],
        messages: list[dict],
        registry: ConversationRegistry | None = None,
        provisional_surrogates: dict[str, str] | None = None,
    ) -> dict: ...

class _EgressBlocked(Exception): ...
```

Registry contract:

```
class ConversationRegistry:
    def entries(self) -> list[EntityMapping]: ...

@dataclass(frozen=True)
class EntityMapping:
    real_value: str
    surrogate_value: str
    entity_type: str
    cluster_id: str | None  # Phase 3 D-48; nullable for non-PERSON entries
```

Settings (Plan 04-01):

```
fuzzy_deanon_mode: Literal["algorithmic", "llm", "none"] = "none"
fuzzy_deanon_threshold: float = 0.85
llm_provider_fallback_enabled: bool = False  # Phase 3 D-52
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Add Pydantic models + extend de_anonymize_text signature with mode param (D-71/D-73)</name>
  <files>backend/app/services/redaction_service.py</files>
  <read_first>
    - backend/app/services/redaction_service.py (the file being modified — read entirely; locate `de_anonymize_text` near lines 604-679; locate the imports block; locate Pydantic models if any)
    - .planning/phases/04-fuzzy-de-anonymization-missed-pii-scan-prompt-guidance/04-PATTERNS.md "MODIFIED · backend/app/services/redaction_service.py" section (verbatim splice templates)
    - .planning/phases/04-fuzzy-de-anonymization-missed-pii-scan-prompt-guidance/04-CONTEXT.md decisions D-71 (in-place upgrade), D-73 (LLM payload + Pydantic schema)
    - backend/app/services/llm_provider.py (Phase 3 — confirm `LLMProviderClient.call(feature='fuzzy_deanon', ...)` is callable; locate `_EgressBlocked` class)
    - .planning/phases/02-conversation-scoped-registry-and-round-trip/02-CONTEXT.md D-34 (the docstring promise this plan cashes — read the verbatim block)
  </read_first>
  <behavior>
    - `de_anonymize_text(text, registry)` (Phase 2 callers, no mode arg) returns identical output to pre-Phase-4 behavior — backward compatibility holds.
    - `de_anonymize_text(text, registry, mode='none')` returns identical output to Phase 2.
    - `de_anonymize_text(text, registry, mode=None)` resolves effective mode from `get_settings().fuzzy_deanon_mode`; default is `'none'` per Plan 04-01.
    - `_FuzzyMatch` model validates each match has `span: str` (1..500 chars) and `token: str` matching `^<<PH_[0-9a-f]+>>$`. Extra fields rejected.
    - `_FuzzyMatchResponse` model validates `{matches: [...]}` with at most 50 entries; extra fields rejected.
    - Phase 1+2+3 regression: 79/79 tests still pass after this task.
  </behavior>
  <action>
**Step 1 — Module-scope additions** (top of `redaction_service.py`, near other Pydantic models if any, otherwise just below the imports block).

Confirm `Literal` import (Phase 3 likely already imports it; if not, add `from typing import Literal`).

Confirm `BaseModel`, `ConfigDict`, `Field` are imported from `pydantic` (Phase 1 RedactionResult already does this — verify).

Add the import for `best_match` from Plan 04-02:
```
from app.services.redaction.fuzzy_match import best_match
```

Add the private Pydantic response models for D-73 (place near other module-level Pydantic models or just below imports):
```
# Phase 4 D-73: LLM fuzzy-match response schema. Server validates membership
# of `token` against Pass-1 placeholders dict (extra defense beyond Pydantic).
class _FuzzyMatch(BaseModel):
    """One LLM-fuzzy-match candidate (D-73)."""
    model_config = ConfigDict(extra="forbid")
    span: str = Field(..., min_length=1, max_length=500)
    token: str = Field(..., pattern=r"^<<PH_[0-9a-f]+>>$")


class _FuzzyMatchResponse(BaseModel):
    """LLM fuzzy-match response — Pydantic-validated payload (D-73)."""
    model_config = ConfigDict(extra="forbid")
    matches: list[_FuzzyMatch] = Field(default_factory=list, max_length=50)
```

**Step 2 — Extend the `de_anonymize_text` signature.** Replace the existing 1-phase signature:
```
async def de_anonymize_text(self, text: str, registry: ConversationRegistry) -> str:
```
with the verbatim D-71 form:
```
@traced(name="redaction.de_anonymize_text")
async def de_anonymize_text(
    self,
    text: str,
    registry: ConversationRegistry,
    mode: Literal["algorithmic", "llm", "none"] | None = None,  # NEW (D-71)
) -> str:
```
(Preserve the existing `@traced` decorator if it was already there; do NOT duplicate it.)

**Step 3 — Mode-resolution prelude** at the top of the method body (after the docstring, BEFORE the existing Pass 1 loop):
```
# Phase 4 D-71: resolve effective mode (param wins; falls back to settings).
settings = get_settings()
if mode is None:
    mode = settings.fuzzy_deanon_mode  # 'algorithmic' | 'llm' | 'none'
threshold = settings.fuzzy_deanon_threshold
```

**Step 4 — Update the docstring.** Replace the Phase 2 forward-compat block ("Phase 4 will insert...") with the production form:
```
"""3-phase placeholder-tokenized de-anonymization pipeline (Phase 4 D-71..D-74).

Pass 1: replace each known surrogate with an opaque <<PH_xxxx>> token (existing).
Pass 2: when mode='algorithmic' or 'llm', match remaining text against this thread's
        cluster variants and replace mangled forms with the corresponding placeholder.
Pass 3: replace each <<PH_xxxx>> with its real value (existing).

When mode='none' (default per Settings.fuzzy_deanon_mode), Pass 2 is skipped —
behavior is identical to Phase 2.

Args:
    text: surrogate-bearing text from the LLM.
    registry: per-thread ConversationRegistry (already loaded; no DB I/O here).
    mode: optional explicit override; None => Settings.fuzzy_deanon_mode.

Returns:
    Same text with surrogates resolved to real values; hard-redact [ENTITY_TYPE]
    placeholders survive unchanged in all modes (D-74; structural per Phase 2 D-24).
"""
```

**Constraints**:
- DO NOT modify Pass 1 (existing lines 631-662) or Pass 3 (existing lines 664-668) loops in this task. The Pass 2 splice happens in Task 2.
- All Phase 2 call sites must continue to compile — `mode` defaults to `None` so positional/keyword call sites stay valid. Verify via `git grep -n 'de_anonymize_text' backend/` returns the same call sites with the same arity.

**Verification (immediate, before Task 2):**
```
cd backend && source venv/bin/activate
python -c "from app.services.redaction_service import _FuzzyMatchResponse; r = _FuzzyMatchResponse.model_validate({'matches':[{'span':'M. Smyth','token':'<<PH_0001>>'}]}); print('OK')"
python -c "from app.services.redaction_service import _FuzzyMatchResponse
try:
    _FuzzyMatchResponse.model_validate({'matches':[{'span':'x','token':'BOGUS'}]})
    raise SystemExit('pattern should have rejected BOGUS')
except Exception:
    print('PATTERN-OK')"
python -c "from app.main import app; print('main OK')"
pytest tests/ -x --tb=short -q
```
Last command must show 79/79 still green.
  </action>
  <verify>
    <automated>cd /Users/erikgunawansupriatna/claude-code-agentic-rag-masterclass-1/backend &amp;&amp; source venv/bin/activate &amp;&amp; python -c "from app.services.redaction_service import _FuzzyMatchResponse, _FuzzyMatch, RedactionService; import inspect; sig = inspect.signature(RedactionService.de_anonymize_text); assert 'mode' in sig.parameters; assert sig.parameters['mode'].default is None; ok = _FuzzyMatchResponse.model_validate({'matches':[{'span':'M. Smyth','token':'<<PH_0001>>'}]}); assert ok.matches[0].token == '<<PH_0001>>'; print('OK')" &amp;&amp; pytest tests/ -x --tb=short -q</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c '^class _FuzzyMatch(BaseModel):' backend/app/services/redaction_service.py` returns exactly 1.
    - `grep -c '^class _FuzzyMatchResponse(BaseModel):' backend/app/services/redaction_service.py` returns exactly 1.
    - `grep -c 'pattern=r"\^<<PH_\[0-9a-f\]+>>\$"' backend/app/services/redaction_service.py` returns exactly 1.
    - `grep -c 'from app.services.redaction.fuzzy_match import best_match' backend/app/services/redaction_service.py` returns exactly 1.
    - `grep -cE 'mode:\s*Literal\["algorithmic",\s*"llm",\s*"none"\]\s*\|\s*None\s*=\s*None' backend/app/services/redaction_service.py` returns exactly 1.
    - Inspect signature: `python -c "from app.services.redaction_service import RedactionService; import inspect; sig = inspect.signature(RedactionService.de_anonymize_text); assert sig.parameters['mode'].default is None; assert 'text' in sig.parameters and 'registry' in sig.parameters"` exits 0.
    - `pytest tests/ -x --tb=short` exits 0; 79/79 Phase 1+2+3 tests still PASS.
    - `python -c "from app.main import app"` succeeds (PostToolUse import-check).
  </acceptance_criteria>
  <done>
The signature is extended (backward-compatible). Pydantic models for D-73 LLM response are defined. The fuzzy_match import is in place. Phase 1+2+3 baseline still 79/79 green.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Implement Pass 2 dispatch (algorithmic + LLM branches with soft-fail), splice into de_anonymize_text (D-72/D-73/D-74/D-78)</name>
  <files>backend/app/services/redaction_service.py</files>
  <read_first>
    - backend/app/services/redaction_service.py (Task 1 output — locate the existing Pass 1 loop and Pass 3 loop bodies; identify the placeholders dict variable name minted in Pass 1 and the format of <<PH_xxxx>> tokens)
    - .planning/phases/04-fuzzy-de-anonymization-missed-pii-scan-prompt-guidance/04-PATTERNS.md "Splice point 1 — `de_anonymize_text` 3-phase upgrade" + "Tracing-attribute pattern" sections (lines 666-755)
    - .planning/phases/04-fuzzy-de-anonymization-missed-pii-scan-prompt-guidance/04-CONTEXT.md decisions D-72 (mode dispatch in service), D-73 (LLM payload), D-74 (hard-redact survival), D-78 (soft-fail)
    - backend/app/services/redaction_service.py existing _resolve_clusters_via_llm (lines ~156-283) — the soft-fail pattern this task mirrors verbatim (try/_EgressBlocked/Exception triple-catch + WARNING log + fallback)
    - backend/app/services/llm_provider.py — confirm `_EgressBlocked` is importable; confirm `LLMProviderClient.call` returns a dict (not a string) per Phase 3 D-49
  </read_first>
  <behavior>
    - **Pass 2 algorithmic branch** (`mode='algorithmic'`):
      - Group `registry.entries()` by `cluster_id`. Entries with `cluster_id is None` (non-PERSON or unclustered) form their own one-element clusters.
      - For each cluster, build the variant set from `[entry.surrogate_value for entry in cluster_entries]` (NOT real_value; D-68 — fuzzy matching operates on surrogate variants only).
      - Tokenize remaining text into whitespace-separated chunks. For each chunk that is NOT already a placeholder (does not match `<<PH_[0-9a-f]+>>`) AND not a hard-redact `[ENTITY_TYPE]` placeholder: call `best_match(chunk, cluster_variants, threshold)`.
      - On match: find the cluster's canonical placeholder `<<PH_xxxx>>` in the placeholders dict (each cluster's first surrogate added during Pass 1 has a token). Replace the chunk with the placeholder.
      - Returns `(modified_text, count_of_replacements)`.
    - **Pass 2 LLM branch** (`mode='llm'`):
      - Construct messages: system prompt instructing JSON-only response with `{matches: [{span, token}]}`; user message contains Pass-1's placeholder-tokenized text + JSON list of cluster variants `[{token: '<<PH_xxxx>>', canonical: '<surrogate>', variants: [...]}, ...]`.
      - Call `LLMProviderClient().call(feature='fuzzy_deanon', messages=messages, registry=registry, provisional_surrogates=None)`.
      - Parse via `_FuzzyMatchResponse.model_validate(result)`.
      - For each match: validate `match.token` is in Pass-1 placeholders dict; if not, drop (silent — D-77 analog). Replace each `re.escape(match.span)` substring with `match.token` via `re.subn`.
      - Returns `(modified_text, count_of_replacements)`.
    - **Soft-fail in LLM branch** (`mode='llm'`):
      - Catch `_EgressBlocked`: log WARNING `event=fuzzy_deanon_skipped feature=fuzzy_deanon error_class=_EgressBlocked` (NEVER raw payload). If `settings.llm_provider_fallback_enabled=True`: fall back to algorithmic Pass 2. Else: skip Pass 2 (return text unchanged from Pass 1).
      - Catch `(ValidationError, Exception) as exc`: log WARNING `event=fuzzy_deanon_skipped feature=fuzzy_deanon error_class=<type(exc).__name__>`. Same fallback logic.
      - NEVER re-raise to the caller — chat loop must not crash.
    - **Span attributes** added: `fuzzy_deanon_mode` (str), `fuzzy_matches_resolved` (int), `fuzzy_provider_fallback` (bool, only set when LLM branch failed and fell back).
    - **Hard-redact survival** (D-74): the chunk-iteration in algorithmic branch SKIPS chunks matching `^\[[A-Z_]+\]$`. The LLM-mode payload contains Pass-1-output text where hard-redacts are present as `[TYPE]` literals; even if the LLM tries to match them, the server validates `match.token` is in the Pass-1 placeholders dict — `[TYPE]` literals are NOT in that dict (Pass 1 only mints `<<PH_xxxx>>` for registered surrogates), so any LLM attempt to map `[CREDIT_CARD]` to a placeholder is silently dropped.
  </behavior>
  <action>
**Step 1 — Add the algorithmic helper method** on `RedactionService` (place after the existing `de_anonymize_text` body or wherever private helpers cluster):

```
def _fuzzy_match_algorithmic(
    self,
    text: str,
    registry: ConversationRegistry,
    placeholders: dict[str, str],
    threshold: float,
) -> tuple[str, int]:
    """D-72 algorithmic branch: per-cluster Jaro-Winkler match against
    registry surrogate variants. Returns (modified_text, replacement_count)."""
    from collections import defaultdict
    import re as _re

    # Phase 3 D-48: group by cluster_id; None-cluster entries are singletons.
    clusters: dict[str, list[str]] = defaultdict(list)
    surrogate_to_placeholder: dict[str, str] = {}
    for ph_token, real_value in placeholders.items():
        # Reverse-lookup: find the registry entry for this real_value to get
        # its canonical surrogate + cluster_id. registry.lookup_real(real_value)
        # is Phase 2 D-27's case-insensitive helper.
        for ent in registry.entries():
            if ent.real_value.casefold() == real_value.casefold():
                cluster_key = ent.cluster_id or f"_solo_{ent.real_value.casefold()}"
                clusters[cluster_key].append(ent.surrogate_value)
                surrogate_to_placeholder[ent.surrogate_value.casefold()] = ph_token
                break

    if not clusters:
        return text, 0

    # Iterate whitespace tokens. SKIP chunks that are already placeholders or
    # hard-redact bracket forms (D-74 structural survival).
    placeholder_re = _re.compile(r"^<<PH_[0-9a-f]+>>$")
    hard_redact_re = _re.compile(r"^\[[A-Z_]+\]$")

    out = text
    replacements = 0
    # Use a non-greedy whitespace tokenizer that preserves the original
    # text on rebuild (split + rejoin loses double-spaces; instead, find
    # runs of non-whitespace via re.finditer).
    span_replacements: list[tuple[int, int, str]] = []  # (start, end, replacement)
    for m in _re.finditer(r"\S+", text):
        chunk = m.group(0)
        if placeholder_re.match(chunk) or hard_redact_re.match(chunk):
            continue
        # Try each cluster's variants.
        for cluster_key, variants in clusters.items():
            from app.services.redaction.fuzzy_match import best_match as _bm
            result = _bm(chunk, variants, threshold=threshold)
            if result is not None:
                matched_variant, _score = result
                ph_token = surrogate_to_placeholder.get(matched_variant.casefold())
                if ph_token is None:
                    continue
                span_replacements.append((m.start(), m.end(), ph_token))
                replacements += 1
                break  # first matching cluster wins for this chunk

    # Apply replacements right-to-left to preserve offsets.
    for start, end, ph in sorted(span_replacements, key=lambda r: -r[0]):
        out = out[:start] + ph + out[end:]
    return out, replacements
```

**Step 2 — Add the LLM helper method** on `RedactionService`:

```
async def _fuzzy_match_llm(
    self,
    text: str,
    registry: ConversationRegistry,
    placeholders: dict[str, str],
) -> tuple[str, int, bool]:
    """D-72/D-73 LLM branch. Returns (modified_text, replacement_count, fell_back).

    fell_back=True when the LLM call failed AND fallback was attempted.
    On any failure, soft-fails per D-78 — never raises to the caller.
    """
    import re as _re
    from collections import defaultdict
    from pydantic import ValidationError
    from app.services.llm_provider import LLMProviderClient, _EgressBlocked

    # Build cluster variants list (D-73 payload).
    clusters_by_token: dict[str, dict] = {}
    for ph_token, real_value in placeholders.items():
        for ent in registry.entries():
            if ent.real_value.casefold() == real_value.casefold():
                cluster_key = ent.cluster_id or f"_solo_{ent.real_value.casefold()}"
                if ph_token not in clusters_by_token:
                    clusters_by_token[ph_token] = {
                        "token": ph_token,
                        "canonical": ent.surrogate_value,
                        "variants": [],
                    }
                if ent.surrogate_value not in clusters_by_token[ph_token]["variants"]:
                    clusters_by_token[ph_token]["variants"].append(ent.surrogate_value)
                break

    if not clusters_by_token:
        return text, 0, False

    variant_payload = list(clusters_by_token.values())

    messages = [
        {"role": "system", "content": (
            "Identify each instance in the user text where a slightly mangled "
            "form of a known cluster variant appears, and map it to that cluster's "
            "token. Reply ONLY with JSON in the form "
            '{"matches":[{"span":"<exact substring of user text>","token":"<<PH_xxxx>>"}]}.'
            " The placeholders <<PH_xxxx>> in the user text are opaque tokens you must "
            "preserve; map only NEW mangled forms NOT already replaced. Use only tokens "
            "from the provided cluster list. Do not invent tokens."
        )},
        {"role": "user", "content": (
            f"Text:\n{text}\n\nClusters (JSON):\n{variant_payload}"
        )},
    ]

    client = LLMProviderClient()
    settings = get_settings()
    fell_back = False

    try:
        result = await client.call(
            feature="fuzzy_deanon",
            messages=messages,
            registry=registry,
            provisional_surrogates=None,  # D-56: no provisional set for de-anon
        )
        parsed = _FuzzyMatchResponse.model_validate(result)
    except _EgressBlocked as exc:
        logger.warning(
            "event=fuzzy_deanon_skipped feature=fuzzy_deanon error_class=_EgressBlocked"
        )
        if settings.llm_provider_fallback_enabled:
            out, n = self._fuzzy_match_algorithmic(
                text, registry, placeholders, settings.fuzzy_deanon_threshold
            )
            return out, n, True
        return text, 0, True
    except (ValidationError, Exception) as exc:  # noqa: BLE001 — D-78 catch-all
        logger.warning(
            "event=fuzzy_deanon_skipped feature=fuzzy_deanon error_class=%s",
            type(exc).__name__,
        )
        if settings.llm_provider_fallback_enabled:
            out, n = self._fuzzy_match_algorithmic(
                text, registry, placeholders, settings.fuzzy_deanon_threshold
            )
            return out, n, True
        return text, 0, True

    # Apply matches: server validates token membership in placeholders, drops invalid.
    out = text
    replacements = 0
    valid_tokens = set(placeholders.keys())
    for match in parsed.matches:
        if match.token not in valid_tokens:
            continue  # D-73: server-side validation; LLM cannot inject foreign tokens
        # Skip if the span IS a hard-redact bracket form (D-74 belt-and-suspenders).
        if _re.fullmatch(r"\[[A-Z_]+\]", match.span):
            continue
        new_text, n = _re.subn(_re.escape(match.span), match.token, out)
        out = new_text
        replacements += n
    return out, replacements, False
```

**Step 3 — Splice Pass 2 into `de_anonymize_text` body** between the existing Pass 1 (which builds `placeholders` dict and the post-Pass-1 text — call that variable `out` per the existing code — confirm by reading the file) and the existing Pass 3 (which iterates placeholders to substitute back). Insert IMMEDIATELY after the Pass 1 loop completes and BEFORE Pass 3 starts:

```
# Phase 4 D-72: Pass 2 — fuzzy/LLM-match against UNREPLACED variants.
fuzzy_matches_resolved = 0
fuzzy_provider_fallback = False
if mode == "algorithmic":
    out, fuzzy_matches_resolved = self._fuzzy_match_algorithmic(
        out, registry, placeholders, threshold
    )
elif mode == "llm":
    out, fuzzy_matches_resolved, fuzzy_provider_fallback = await self._fuzzy_match_llm(
        out, registry, placeholders
    )
# else mode == "none" → skip Pass 2 entirely (Phase 2 behavior preserved).
```

**Step 4 — Add span attributes** at the END of the method body, just before the return statement (mirror Phase 3 D-63 instrumentation pattern that already exists for `redaction.redact_text`):

```
# Phase 4 D-63 / B4 invariant: counts and mode strings ONLY. NEVER real values.
try:
    from app.services.tracing_service import current_span  # match Phase 3 import
    span = current_span()
    if span is not None:
        span.set_attribute("fuzzy_deanon_mode", mode)
        span.set_attribute("fuzzy_matches_resolved", fuzzy_matches_resolved)
        span.set_attribute("fuzzy_provider_fallback", fuzzy_provider_fallback)
except Exception:  # tracing must NEVER affect functional behavior
    pass
```
(If the existing codebase uses a different tracing API for span-attribute access — e.g., a context manager or a `traced(...)` return value — match that pattern from `redaction_service.py`'s existing `redact_text` instrumentation. Read the surrounding file to confirm before writing.)

**Constraints**:
- DO NOT change Pass 1 or Pass 3 logic. Pass 2 ADDS a step between them.
- DO NOT log raw `text`, `chunk`, `match.span`, `real_value`, or `surrogate_value` anywhere. Caplog assertion in Plan 04-07 will scan for these.
- The LLM helper MUST NOT raise. All exceptions are caught + logged + soft-failed.
- `re.escape` MUST be applied to `match.span` before substitution (handles surrogates with regex metachars like `+62-21-555` containing `+`).

**Verification**:
```
cd backend && source venv/bin/activate
python -c "from app.main import app; print('OK')"
pytest tests/ -x --tb=short -q
```
Phase 1+2+3 baseline must still be 79/79 green (mode defaults to 'none'; existing callers unchanged).
  </action>
  <verify>
    <automated>cd /Users/erikgunawansupriatna/claude-code-agentic-rag-masterclass-1/backend &amp;&amp; source venv/bin/activate &amp;&amp; python -c "from app.services.redaction_service import RedactionService; assert hasattr(RedactionService, '_fuzzy_match_algorithmic'); assert hasattr(RedactionService, '_fuzzy_match_llm'); import inspect; assert inspect.iscoroutinefunction(RedactionService._fuzzy_match_llm); assert not inspect.iscoroutinefunction(RedactionService._fuzzy_match_algorithmic); print('OK')" &amp;&amp; pytest tests/ -x --tb=short -q</automated>
  </verify>
  <acceptance_criteria>
    - `grep -cE 'def _fuzzy_match_algorithmic\(' backend/app/services/redaction_service.py` returns exactly 1.
    - `grep -cE 'async def _fuzzy_match_llm\(' backend/app/services/redaction_service.py` returns exactly 1.
    - `grep -c "feature=\"fuzzy_deanon\"" backend/app/services/redaction_service.py` returns ≥ 1 (LLM branch dispatches with the correct feature string).
    - `grep -c '_EgressBlocked' backend/app/services/redaction_service.py` returns ≥ 2 (import + except clause; Phase 3 may already import, this task adds an except).
    - `grep -c 'event=fuzzy_deanon_skipped' backend/app/services/redaction_service.py` returns ≥ 2 (one per except clause in `_fuzzy_match_llm`).
    - `grep -c 'llm_provider_fallback_enabled' backend/app/services/redaction_service.py` returns ≥ 1 (D-52 fallback gate consulted).
    - `grep -cE 'mode\s*==\s*"algorithmic"' backend/app/services/redaction_service.py` returns ≥ 1; `grep -cE 'mode\s*==\s*"llm"' backend/app/services/redaction_service.py` returns ≥ 1.
    - `grep -c 'set_attribute("fuzzy_deanon_mode"' backend/app/services/redaction_service.py` returns ≥ 1.
    - `grep -c 'set_attribute("fuzzy_matches_resolved"' backend/app/services/redaction_service.py` returns ≥ 1.
    - `grep -c 'hard_redact_re' backend/app/services/redaction_service.py` returns ≥ 1 (D-74 belt-and-suspenders skip pattern in algorithmic branch).
    - `pytest tests/ -x --tb=short` exits 0 — Phase 1+2+3 79/79 still green.
    - Smoke test (manual): `python -c "from app.services.redaction_service import RedactionService; import inspect; assert hasattr(RedactionService, '_fuzzy_match_algorithmic'); assert inspect.iscoroutinefunction(RedactionService._fuzzy_match_llm); print('OK')"` exits 0.
    - `python -c "from app.main import app"` succeeds.
  </acceptance_criteria>
  <done>
de_anonymize_text now runs the full 3-phase pipeline. Pass 2 dispatches to algorithmic or LLM branches per mode. Soft-fail keeps the chat loop alive. Hard-redact survival is structural + belt-and-suspenders. Phase 2 callers unchanged.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Caller (Plan 5 SSE / Plan 04-07 tests) → `de_anonymize_text` | In-process method call; receives surrogate-bearing text from LLM output. |
| `_fuzzy_match_llm` → `LLMProviderClient.call(feature='fuzzy_deanon')` | Crosses cloud egress when provider='cloud'. Phase 3 D-53..D-56 egress filter wraps. |
| `registry.entries()` (in-memory cache; backed by Supabase rows) | Read-only; no write surface. |

## STRIDE Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation |
|-----------|----------|-----------|----------|-------------|------------|
| T-04-03-1 | Information Disclosure (raw PII to cloud LLM) | Pass 2 LLM branch payload | high | mitigate | D-73 placeholder-tokenization invariant: cloud payload contains only post-Pass-1 text (real values already replaced by `<<PH_xxxx>>`) + variant list of surrogate-form strings only. Phase 3 D-53..D-56 egress filter is the runtime backstop. Plan 04-07 TestSC2 + TestB4_LogPrivacy assert no raw values cross the boundary. |
| T-04-03-2 | Spoofing (LLM injects foreign placeholder token) | `_FuzzyMatchResponse` parse | medium | mitigate | Pydantic Field pattern `^<<PH_[0-9a-f]+>>$` rejects malformed tokens; server-side membership check `match.token in valid_tokens` (where valid_tokens=keys of Pass-1 placeholders dict) drops fabricated tokens silently. |
| T-04-03-3 | Tampering (hard-redact `[ENTITY_TYPE]` resolved away) | Pass 2 (any mode) | high | mitigate | D-74 STRUCTURAL: hard-redacts never in registry per Phase 2 D-24/REG-05 → never minted as `<<PH_xxxx>>` placeholders → not resolved by Pass 3. Belt-and-suspenders skip in algorithmic branch (`hard_redact_re`); LLM-mode server validation drops `[TYPE]` spans. Plan 04-07 parametrized `TestSC3_HardRedactSurvives` asserts identity preservation across modes. |
| T-04-03-4 | DoS (provider failure crashes chat) | LLM branch failure | low | mitigate | Triple-catch `_EgressBlocked` / `ValidationError` / generic `Exception` → soft-fail per D-78 → algorithmic fallback (when `llm_provider_fallback_enabled=True` per D-52) or skip Pass 2; WARNING log carries error_class only (B4). Method NEVER raises. |
| T-04-03-5 | Information Disclosure (raw value in span attrs) | Tracing instrumentation | medium | mitigate | D-63 + B4: only `fuzzy_deanon_mode` (str), `fuzzy_matches_resolved` (int), `fuzzy_provider_fallback` (bool) set as attributes. NO real_value / surrogate_value / span text. |

## Cross-plan threats covered elsewhere
- **T-1 (egress filter as primary control):** Phase 3 D-53..D-56 already implemented in `LLMProviderClient.call`. This plan inherits the protection.
- **T-3 (missed-scan injecting fabricated entity types):** N/A — this plan handles fuzzy de-anon only. Plan 04-04 (missed-scan) addresses T-3.
- **T-5 (prompt injection):** N/A — this plan does not mint user-facing prompts. Plan 04-05 (`prompt_guidance.py`) addresses T-5.
</threat_model>

<verification>
- `pytest tests/ -x --tb=short` from `backend/` is green (79/79 Phase 1+2+3 baseline preserved).
- `python -c "from app.main import app"` succeeds (PostToolUse import-check).
- Plan 04-07 integration tests will exercise the new Pass 2 paths against live registry data + mocked LLMProviderClient — that's where SC#1, SC#2, SC#3 are verified end-to-end. This plan ships the hooks; Plan 04-07 ships the assertions.
</verification>

<success_criteria>
- D-71 in-place upgrade: `de_anonymize_text` accepts `mode` kwarg with `None` default; Phase 2 callers unchanged.
- D-72 dispatch: algorithmic branch and LLM branch are wired and selectable via `mode`.
- D-73 LLM payload: placeholder-tokenized text + JSON variant list; `_FuzzyMatchResponse` Pydantic validates response; server checks token membership.
- D-74 hard-redact survival: structural invariant preserved; algorithmic branch belt-and-suspenders skip; LLM-mode server-side filter.
- D-78 soft-fail: triple-catch in LLM branch; WARNING log carries error_class only; method NEVER raises.
- 79/79 Phase 1+2+3 regression suite still green.
</success_criteria>

<output>
After completion, create `.planning/phases/04-fuzzy-de-anonymization-missed-pii-scan-prompt-guidance/04-03-SUMMARY.md` capturing: signature change, lines added/removed, the 2 new helper methods + 2 new Pydantic models, the splice point in `de_anonymize_text`, regression test status, and any deviations.
</output>
</content>
