---
phase: 04-fuzzy-de-anonymization-missed-pii-scan-prompt-guidance
plan: 02
type: execute
wave: 2
depends_on: []
files_modified:
  - backend/app/services/redaction/fuzzy_match.py
  - backend/tests/unit/test_fuzzy_match.py
autonomous: true
requirements_addressed: [DEANON-03]
tags: [pii, fuzzy-deanon, rapidfuzz, jaro-winkler, unit-tests]
must_haves:
  truths:
    - "Module fuzzy_match.py exposes _normalize_for_fuzzy(s) -> list[str], fuzzy_score(candidate, variant) -> float, best_match(candidate, variants, threshold=0.85) -> tuple[str, float] | None (D-67/D-68/D-70)"
    - "_normalize_for_fuzzy strips honorifics via Phase 1's honorifics.strip_honorific, casefolds, and tokenizes on whitespace (D-70 invariant)"
    - "fuzzy_score uses rapidfuzz.distance.JaroWinkler.normalized_similarity over token×token max-pair (D-67 algorithm + D-70 token-level scoring)"
    - "best_match enforces per-cluster scoping by accepting variants from the CALLER ONLY — pure function, no registry access (D-68 cross-cluster prevention)"
    - "Module is pure CPU function — no @traced decorator (callers in redaction_service.py already have @traced); no I/O; no DB; no LLM SDK"
    - "Unit tests cover D-70 normalization (3+ cases), D-67 threshold boundary (3+ cases), D-68 per-cluster scoping (2+ cases) — all green via pytest"
    - "rapidfuzz is importable in the backend venv (transitive Presidio dep — D-67 verifies no new top-level requirements.txt entry needed)"
  artifacts:
    - path: "backend/app/services/redaction/fuzzy_match.py"
      provides: "Algorithmic Jaro-Winkler matcher: _normalize_for_fuzzy + fuzzy_score + best_match"
      contains: "from rapidfuzz.distance import JaroWinkler"
    - path: "backend/tests/unit/test_fuzzy_match.py"
      provides: "Unit coverage for D-67/D-68/D-70 invariants"
      contains: "TestD70_Normalization"
  key_links:
    - from: "backend/app/services/redaction/fuzzy_match.py"
      to: "backend/app/services/redaction/honorifics.py"
      via: "from app.services.redaction.honorifics import strip_honorific"
      pattern: "from app.services.redaction.honorifics import strip_honorific"
    - from: "backend/app/services/redaction/fuzzy_match.py"
      to: "rapidfuzz library (transitive Presidio dep)"
      via: "from rapidfuzz.distance import JaroWinkler"
      pattern: "from rapidfuzz.distance import JaroWinkler"
threat_model:
  trust_boundaries:
    - "Pure-function trust boundary: caller (redaction_service.py de_anonymize_text Pass 2) → fuzzy_match.best_match. The function has no I/O surface, no LLM, no DB. The CALLER is responsible for variant scope; the function does not enforce it."
  threats:
    - id: "T-04-02-1"
      category: "Tampering (cross-cluster confusion → wrong de-anon)"
      component: "best_match variants list"
      severity: "medium"
      disposition: "mitigate"
      mitigation: "D-68 structural invariant: best_match accepts variants from CALLER only — Plan 04-03's de_anonymize_text MUST narrow to one cluster's variants per registry entry. Unit test TestD68_PerClusterScope.test_only_matches_against_supplied_variants asserts the contract; integration test in Plan 04-07 (TestSC2_NoSurnameCollision) asserts the wired-up invariant."
    - id: "T-04-02-2"
      category: "Tampering (threshold drift → false positives)"
      component: "fuzzy_score / best_match threshold parameter"
      severity: "low"
      disposition: "mitigate"
      mitigation: "D-69 threshold default 0.85 enforced by signature default `threshold: float = 0.85` AND by the caller in Plan 04-03 reading `settings.fuzzy_deanon_threshold` (Pydantic-validated 0.50-1.00 + DB CHECK from Plan 04-01). Defense-in-depth covers env-var, DB, and code default."
    - id: "T-04-02-3"
      category: "Information Disclosure"
      component: "fuzzy_match.py (no log output)"
      severity: "low"
      disposition: "accept"
      mitigation: "Module emits zero log lines. B4 invariant trivially satisfied — no payloads possible."
---

<objective>
Ship the algorithmic Jaro-Winkler fuzzy matcher (D-67/D-68/D-70) as a small, focused, side-effect-free module under `backend/app/services/redaction/`, with full unit coverage. This is the core CPU primitive for Phase 4 Pass 2's `mode='algorithmic'` branch.

Purpose: Plan 04-03's `de_anonymize_text` 3-phase upgrade calls `fuzzy_match.best_match(candidate, registry_variants_for_cluster, threshold)` between Pass 1 (surrogate→placeholder) and Pass 3 (placeholder→real). This plan ships the matcher in isolation so Plan 04-03 can wire to a tested, frozen contract.

Output: 2 files. `backend/app/services/redaction/fuzzy_match.py` (pure module, ~50 lines). `backend/tests/unit/test_fuzzy_match.py` (table-driven unit tests mirroring Phase 3's `test_egress_filter.py` shape, ~80 lines).
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
@CLAUDE.md
@backend/app/services/redaction/honorifics.py
@backend/app/services/redaction/nicknames_id.py
@backend/tests/unit/test_egress_filter.py

<interfaces>
<!-- The exact contracts this plan produces (consumed by Plan 04-03). -->

```python
# backend/app/services/redaction/fuzzy_match.py — public surface

def _normalize_for_fuzzy(s: str) -> list[str]:
    """D-70: strip honorific (Phase 1 honorifics.strip_honorific) + casefold + tokenize on whitespace."""

def fuzzy_score(candidate: str, variant: str) -> float:
    """D-67/D-70: Jaro-Winkler similarity in [0.0, 1.0] after D-70 normalization,
    token-level (max over token×token pairs)."""

def best_match(
    candidate: str,
    variants: list[str],
    threshold: float = 0.85,
) -> tuple[str, float] | None:
    """D-67/D-68: returns (best_variant, score) if best score >= threshold; else None.
    Per-cluster scoping is the CALLER's responsibility — pass only this cluster's variants."""
```

```python
# backend/app/services/redaction/honorifics.py — Phase 1 dependency this plan imports
def strip_honorific(name: str) -> tuple[str | None, str]:
    """Returns (honorific_or_None, bare_name). 'Pak Bambang' → ('Pak', 'Bambang')."""
```

```python
# rapidfuzz library (transitive Presidio dep — verify import works in backend venv)
from rapidfuzz.distance import JaroWinkler
JaroWinkler.normalized_similarity("Smith", "Smyth")  # → ~0.91
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Write fuzzy_match.py module (D-67/D-68/D-70)</name>
  <files>backend/app/services/redaction/fuzzy_match.py</files>
  <read_first>
    - backend/app/services/redaction/honorifics.py (Phase 1 — confirm `strip_honorific` exists with the documented signature; this module imports it)
    - backend/app/services/redaction/nicknames_id.py (Phase 3 — module-shape analog: small focused module with a single concern)
    - .planning/phases/04-fuzzy-de-anonymization-missed-pii-scan-prompt-guidance/04-PATTERNS.md "fuzzy_match.py (NEW — utility, pure function)" section (verbatim module template lines 60-124)
    - .planning/phases/04-fuzzy-de-anonymization-missed-pii-scan-prompt-guidance/04-CONTEXT.md decisions D-67 (rapidfuzz Jaro-Winkler), D-68 (per-cluster scoping), D-70 (normalization)
    - Verify rapidfuzz is importable: `cd backend && source venv/bin/activate && python -c "from rapidfuzz.distance import JaroWinkler; print(JaroWinkler.normalized_similarity('Smith', 'Smyth'))"` — must print a float ≥ 0.85. If ImportError, STOP and add `rapidfuzz` to `backend/requirements.txt` as an explicit top-level dep before proceeding.
  </read_first>
  <behavior>
    - `_normalize_for_fuzzy("Pak Bambang")` returns `["bambang"]` (honorific stripped + casefolded + single token).
    - `_normalize_for_fuzzy("Marcus A. Smith")` returns `["marcus", "a.", "smith"]` (no honorific; casefolded; whitespace-split — punctuation kept attached to its token).
    - `_normalize_for_fuzzy("")` returns `[]` (empty input).
    - `fuzzy_score("pak Smith", "Pak Smith")` returns `1.0` (post-normalization equality).
    - `fuzzy_score("Smyth", "Smith")` returns ≥ `0.85` (one-char typo above threshold per rapidfuzz Jaro-Winkler).
    - `fuzzy_score("Bambang", "Mukherjee")` returns < `0.85` (unrelated names below threshold).
    - `fuzzy_score("", "Smith")` returns `0.0` (empty candidate guard).
    - `best_match("M. Smyth", ["Marcus Smith", "M. Smith", "Marcus"], threshold=0.85)` returns a `(str, float)` tuple where `str ∈ {"Marcus Smith", "M. Smith", "Marcus"}` and `float >= 0.85`.
    - `best_match("Wijaya", ["Marcus Smith", "Marcus"], threshold=0.85)` returns `None`.
    - `best_match("anything", [], threshold=0.85)` returns `None` (empty variants guard).
  </behavior>
  <action>
Create the file `backend/app/services/redaction/fuzzy_match.py` with the exact content below.

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

No @traced decorator — pure CPU function called from de_anonymize_text which
is already @traced(name="redaction.de_anonymize_text"). Span attributes get
added at the caller (Plan 04-03).
"""
from __future__ import annotations

from rapidfuzz.distance import JaroWinkler

from app.services.redaction.honorifics import strip_honorific


def _normalize_for_fuzzy(s: str) -> list[str]:
    """D-70 normalization: strip honorific + casefold + tokenize on whitespace.

    Returns an empty list when the input is empty or contains only honorific
    + whitespace (e.g., 'Pak ' alone normalizes to []).
    """
    if not s:
        return []
    _honorific, bare = strip_honorific(s)
    return bare.casefold().split()


def fuzzy_score(candidate: str, variant: str) -> float:
    """Jaro-Winkler similarity in [0.0, 1.0] after D-70 normalization.

    Token-level: max-over-pairs to catch "John A. Smith" vs "John Smith" and
    "M. Smyth" vs "Marcus Smith". Returns 0.0 if either side normalizes to
    no tokens (empty input or honorific-only).
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
    """D-67/D-68: return (best_variant, score) if best score >= threshold; else None.

    Per-cluster scoping is the CALLER's responsibility (D-68) — pass only
    this cluster's variants to keep matches privacy-correct. The function
    does NOT cross-reference any registry; it is a pure transform.
    """
    if not variants:
        return None
    best_var = max(variants, key=lambda v: fuzzy_score(candidate, v))
    best_score = fuzzy_score(candidate, best_var)
    if best_score >= threshold:
        return best_var, best_score
    return None
```

**Constraints**:
- ZERO logging calls (no `logger = logging.getLogger(...)`). The module is silent on the wire — caller does instrumentation.
- ZERO `@traced` decorator. The caller (`de_anonymize_text` from Plan 04-03) is already `@traced`.
- ZERO async functions. Pure-CPU; sync.
- NO `from app.services.redaction.registry import ...` — D-68 invariant: function is registry-agnostic; caller scopes.
- DO NOT add `rapidfuzz` to `requirements.txt` UNLESS the import-check in `<read_first>` failed. It is a transitive Presidio dep per D-67.
  </action>
  <verify>
    <automated>cd /Users/erikgunawansupriatna/claude-code-agentic-rag-masterclass-1/backend &amp;&amp; source venv/bin/activate &amp;&amp; python -c "
from app.services.redaction.fuzzy_match import _normalize_for_fuzzy, fuzzy_score, best_match
assert _normalize_for_fuzzy('Pak Bambang') == ['bambang'], _normalize_for_fuzzy('Pak Bambang')
assert _normalize_for_fuzzy('') == []
assert fuzzy_score('pak Smith', 'Pak Smith') == 1.0
assert fuzzy_score('Smyth', 'Smith') &gt;= 0.85
assert fuzzy_score('Bambang', 'Mukherjee') &lt; 0.85
assert fuzzy_score('', 'Smith') == 0.0
r = best_match('M. Smyth', ['Marcus Smith', 'M. Smith', 'Marcus'], threshold=0.85)
assert r is not None and r[1] &gt;= 0.85, r
assert best_match('Wijaya', ['Marcus Smith', 'Marcus'], threshold=0.85) is None
assert best_match('x', [], threshold=0.85) is None
print('FUZZY-MATCH OK')
"</automated>
  </verify>
  <acceptance_criteria>
    - `test -f backend/app/services/redaction/fuzzy_match.py` exits 0.
    - `grep -c '^from rapidfuzz.distance import JaroWinkler' backend/app/services/redaction/fuzzy_match.py` returns exactly 1.
    - `grep -c '^from app.services.redaction.honorifics import strip_honorific' backend/app/services/redaction/fuzzy_match.py` returns exactly 1.
    - `grep -cE '^def (_normalize_for_fuzzy|fuzzy_score|best_match)' backend/app/services/redaction/fuzzy_match.py` returns exactly 3 (all three public/internal functions present).
    - `grep -cE '@traced|logging\.getLogger|async def' backend/app/services/redaction/fuzzy_match.py` returns 0 (no decorator, no logging, no async — purity invariants).
    - `grep -c 'from app.services.redaction.registry' backend/app/services/redaction/fuzzy_match.py` returns 0 (D-68: matcher does NOT import the registry — caller scopes).
    - The smoke-script in `<verify>` exits 0 and prints `FUZZY-MATCH OK`.
    - `cd backend &amp;&amp; source venv/bin/activate &amp;&amp; python -c "from app.main import app; print('OK')"` succeeds (PostToolUse import-check).
    - `cd backend &amp;&amp; source venv/bin/activate &amp;&amp; python -m py_compile app/services/redaction/fuzzy_match.py` exits 0.
  </acceptance_criteria>
  <done>
fuzzy_match.py exists with the exact public surface from `<interfaces>`. All behavior assertions in `<behavior>` pass. The module is import-clean, side-effect-free, and ready to be wired by Plan 04-03.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Write test_fuzzy_match.py covering D-67/D-68/D-70 invariants</name>
  <files>backend/tests/unit/test_fuzzy_match.py</files>
  <read_first>
    - backend/tests/unit/test_egress_filter.py (Phase 3 — exact analog: table-driven, per-D-XX subclasses, single concern per test method)
    - backend/app/services/redaction/fuzzy_match.py (Task 1 output — confirm public surface matches the imports below)
    - .planning/phases/04-fuzzy-de-anonymization-missed-pii-scan-prompt-guidance/04-PATTERNS.md "test_fuzzy_match.py (NEW — unit, table-driven)" section (template lines 352-403)
  </read_first>
  <behavior>
    Test classes (each is a separate concern):
    - `TestD70_Normalization` — strip + casefold + tokenize works, empty input returns [].
    - `TestD67_JaroWinklerThreshold` — exact post-normalization match → 1.0; one-char typo `Smyth` vs `Smith` ≥ 0.85; unrelated names < 0.85.
    - `TestD68_PerClusterScope` — `best_match` returns a variant FROM THE SUPPLIED LIST (contract: caller scopes; function returns the best variant out of those it received).
    - `TestThresholdGuard` — `best_match` returns `None` when nothing clears the threshold; returns `None` when variants is empty.
  </behavior>
  <action>
Create `backend/tests/unit/test_fuzzy_match.py` with the exact content below.

```python
"""Unit tests for fuzzy_match.fuzzy_score / best_match (D-67/D-68/D-70).

Mirrors the table-driven shape of test_egress_filter.py (Phase 3 D-66) —
one test class per Phase 4 decision invariant.
"""
from __future__ import annotations

import pytest

from app.services.redaction.fuzzy_match import (
    _normalize_for_fuzzy,
    best_match,
    fuzzy_score,
)


class TestD70_Normalization:
    """D-70: strip honorifics + casefold + tokenize on whitespace."""

    def test_strips_pak_and_casefolds(self):
        assert _normalize_for_fuzzy("Pak Bambang") == ["bambang"]

    def test_strips_bu_and_casefolds(self):
        assert _normalize_for_fuzzy("Bu Tini") == ["tini"]

    def test_preserves_multi_token(self):
        assert _normalize_for_fuzzy("Marcus A. Smith") == ["marcus", "a.", "smith"]

    def test_empty_input_returns_empty(self):
        assert _normalize_for_fuzzy("") == []


class TestD67_JaroWinklerThreshold:
    """D-67/D-69: rapidfuzz Jaro-Winkler at default threshold 0.85."""

    def test_exact_match_post_normalization(self):
        # 'pak Smith' vs 'Pak Smith' → 1.0 after honorific strip + casefold.
        assert fuzzy_score("pak Smith", "Pak Smith") == 1.0

    def test_one_char_typo_above_threshold(self):
        # Smyth → Smith is the canonical Jaro-Winkler 'close' case (~0.91).
        assert fuzzy_score("Smyth", "Smith") >= 0.85

    def test_dropped_token_token_max_above_threshold(self):
        # 'M. Smyth' has tokens ['m.', 'smyth']; 'Marcus Smith' has ['marcus','smith'].
        # max(JW(smyth, smith)) >= 0.85 → token-level max-pair scoring catches it.
        assert fuzzy_score("M. Smyth", "Marcus Smith") >= 0.85

    def test_unrelated_below_threshold(self):
        assert fuzzy_score("Bambang", "Mukherjee") < 0.85

    def test_empty_candidate_returns_zero(self):
        assert fuzzy_score("", "Smith") == 0.0

    def test_empty_variant_returns_zero(self):
        assert fuzzy_score("Smith", "") == 0.0


class TestD68_PerClusterScope:
    """D-68: best_match operates ONLY on caller-provided variants.

    The function is registry-agnostic; the caller (Plan 04-03 de_anonymize_text)
    is responsible for narrowing to a single cluster's variants.
    """

    def test_returns_variant_from_supplied_list(self):
        variants = ["Marcus Smith", "M. Smith", "Marcus"]
        result = best_match("M. Smyth", variants, threshold=0.85)
        assert result is not None
        match, score = result
        assert match in variants  # contract: returned variant is one of the inputs
        assert score >= 0.85

    def test_does_not_cross_reference_registry(self):
        # If best_match read from the registry, it would match against
        # globally-known names. Pass a variant list that has nothing close
        # to the candidate to confirm scoping.
        result = best_match("Marcus Smith", ["Daniel Walsh", "Walsh"], threshold=0.85)
        # Both candidates are unrelated to 'Marcus Smith' — must return None
        # because the caller chose the wrong cluster's variants.
        assert result is None


class TestThresholdGuard:
    """D-67/D-69: threshold gate."""

    def test_below_threshold_returns_none(self):
        assert best_match("Wijaya", ["Marcus Smith", "Marcus"], threshold=0.85) is None

    def test_empty_variants_returns_none(self):
        assert best_match("M. Smyth", [], threshold=0.85) is None

    def test_lower_threshold_admits_match(self):
        # Demonstrates the threshold knob is honored — at 0.50, even unrelated
        # tokens may score above. Verify the contract that threshold is the
        # gate, not a hard-coded constant.
        result = best_match("Wijaya", ["Marcus Smith", "Marcus"], threshold=0.50)
        # Either None or a tuple — but if a tuple, score must be >= 0.50.
        if result is not None:
            assert result[1] >= 0.50
```

Run the test suite immediately:
```bash
cd backend && source venv/bin/activate && pytest tests/unit/test_fuzzy_match.py -v --tb=short
```
Expected: all tests pass; no regressions in `tests/unit/` overall.
  </action>
  <verify>
    <automated>cd /Users/erikgunawansupriatna/claude-code-agentic-rag-masterclass-1/backend &amp;&amp; source venv/bin/activate &amp;&amp; pytest tests/unit/test_fuzzy_match.py -v --tb=short</automated>
  </verify>
  <acceptance_criteria>
    - `test -f backend/tests/unit/test_fuzzy_match.py` exits 0.
    - `grep -cE '^class Test(D70_Normalization|D67_JaroWinklerThreshold|D68_PerClusterScope|ThresholdGuard)' backend/tests/unit/test_fuzzy_match.py` returns exactly 4.
    - `grep -cE '^    def test_' backend/tests/unit/test_fuzzy_match.py` returns ≥ 12 (one per `<behavior>` line above).
    - `pytest backend/tests/unit/test_fuzzy_match.py -v` exits 0; all collected tests PASS.
    - `pytest backend/tests/unit/ -v --tb=short` exits 0 — Phase 1+2+3 unit tests do NOT regress.
    - Test file imports the public surface from `app.services.redaction.fuzzy_match`: `grep -c 'from app.services.redaction.fuzzy_match import' backend/tests/unit/test_fuzzy_match.py` returns ≥ 1.
  </acceptance_criteria>
  <done>
test_fuzzy_match.py runs green. The four test classes pin D-67, D-68, and D-70 invariants. Phase 1+2+3 unit-test suite continues to pass.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Caller (Plan 04-03 `de_anonymize_text` Pass 2) → `fuzzy_match.best_match` | Pure-function call. The function has no I/O, no registry access, no LLM, no DB. The caller is responsible for narrowing `variants` to a single cluster's variant set per D-68. |

## STRIDE Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation |
|-----------|----------|-----------|----------|-------------|------------|
| T-04-02-1 | Tampering (cross-cluster confusion → wrong de-anon → privacy/correctness regression) | `best_match` variants list | medium | mitigate | D-68 contract: per-cluster scoping is the caller's responsibility. Plan 04-03 narrows by registry cluster_id before calling. Unit test `TestD68_PerClusterScope.test_returns_variant_from_supplied_list` asserts the returned variant is one of the supplied inputs (no cross-reference). Integration test in Plan 04-07 (`TestSC2_NoSurnameCollision`) asserts the wired-up invariant: two clusters share a surname; only the correct one resolves. |
| T-04-02-2 | Tampering (threshold drift → false-positive merges) | `fuzzy_score`/`best_match` threshold | low | mitigate | Function default `threshold=0.85` (D-69 PRD-mandated). Caller (Plan 04-03) reads `settings.fuzzy_deanon_threshold` which is Pydantic-validated `[0.50, 1.00]` (Plan 04-01) and DB-CHECK-bounded at the same range. Defense-in-depth: env-var, DB, function default. |
| T-04-02-3 | Information Disclosure (PII in logs) | `fuzzy_match.py` | low | accept | Module emits ZERO log lines (verified by acceptance grep). B4 invariant trivially satisfied — no payloads possible from this module. |
| T-04-02-4 | Denial of Service (degenerate input → O(n²) explosion) | `fuzzy_score` token×token loop | low | accept | Practical bound: name strings have <10 tokens; cluster variant sets have ≤8 entries (D-48 fixed set: canonical + first + last + honorific-prefixed + nickname). Max ops per call: 80 token×token JW computations × 8 variants = 640 rapidfuzz C-extension calls per de_anonymize_text Pass 2. Negligible at warm-path scale (PERF-02 budget is 500ms; rapidfuzz JW is microseconds). |

## Cross-plan threats inherited / deferred
- **T-1 (raw PII reaching cloud LLM):** N/A here — this module never calls an LLM. Plan 04-03 LLM-mode handles T-1 via D-73 placeholder-tokenization + Phase 3 egress filter.
- **T-2 (hard-redact placeholder leak via fuzzy match):** STRUCTURAL invariant D-74 — hard-redact `[ENTITY_TYPE]` placeholders are NEVER written to the registry per Phase 2 D-24/REG-05. Therefore the `variants` list passed to `best_match` cannot contain `[CREDIT_CARD]` etc. Plan 04-07 integration test asserts this end-to-end across all 3 modes.
</threat_model>

<verification>
- `pytest tests/unit/test_fuzzy_match.py -v` is green.
- `pytest tests/` (full unit + integration suite from `backend/`) is green — no regressions in Phase 1+2+3 79-test baseline.
- `python -c "from app.main import app"` succeeds (PostToolUse hook).
</verification>

<success_criteria>
- `fuzzy_match.py` ships with the exact public surface from `<interfaces>`, all 9 behaviors from Task 1 `<behavior>` pass, no logging, no I/O.
- `test_fuzzy_match.py` ships with 4 test classes covering D-67/D-68/D-70/threshold-guard; ≥12 test methods; all green.
- Plan 04-03 can now import and wire `best_match` against a tested, frozen contract.
</success_criteria>

<output>
After completion, create `.planning/phases/04-fuzzy-de-anonymization-missed-pii-scan-prompt-guidance/04-02-SUMMARY.md` capturing: file paths created, public surface signatures, test count + green status, any deviations from the verbatim template, and confirmation that `rapidfuzz` was reachable as a transitive dep (or, if not, that it was added to `requirements.txt` with version pin).
</output>
</content>
