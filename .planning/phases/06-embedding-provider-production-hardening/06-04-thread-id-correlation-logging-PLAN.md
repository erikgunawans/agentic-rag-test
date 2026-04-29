---
plan_id: "06-04"
title: "Add thread_id correlation field to redaction-pipeline debug logs (detection, redaction_service, egress, llm_provider, missed_scan)"
phase: "06-embedding-provider-production-hardening"
plan: 4
type: execute
wave: 2
depends_on: []
autonomous: true
files_modified:
  - backend/app/services/redaction/detection.py
  - backend/app/services/redaction_service.py
  - backend/app/services/redaction/egress.py
  - backend/app/services/llm_provider.py
  - backend/app/services/redaction/missed_scan.py
requirements: [OBS-02, OBS-03]
must_haves:
  truths:
    - "detect_entities() accepts a backward-compatible optional thread_id: str | None = None param (D-P6-15) — existing callers that omit it continue to emit the existing log format"
    - "When thread_id is provided to detect_entities(), the redaction.detect debug log includes a thread_id=<value> field"
    - "redaction_service.redact_text / redact_text_batch / de_anonymize_text debug log lines include thread_id=<value> read from registry.thread_id (D-P6-16)"
    - "egress.egress_filter trip log line includes thread_id=<value> read from registry.thread_id (D-P6-16)"
    - "llm_provider.LLMProviderClient.call() resolved-provider audit log INCLUDES thread_id=<value> when registry is supplied (D-P6-17 / OBS-03)"
    - "missed_scan.scan_for_missed_pii's three logger.warning calls (egress-blocked / validation-error / generic-exception soft-fail paths) include thread_id=registry.thread_id (D-P6-11 / D-P6-16) — verifies SC#4 missed-scan-skip-path log carries the new correlation key"
    - "All call sites of detect_entities() pass thread_id=registry.thread_id when a registry is in scope (registry-aware paths only); stateless path (Phase 1 D-39) passes nothing — backward-compat preserved"
    - "Off-mode invariant (SC#5): when pii_redaction_enabled=false redact_text returns identity BEFORE logging — no new log spam introduced"
    - "B4 invariant: log fields remain counts + flags + thread_id only — no raw values, no surrogate values"
  artifacts:
    - path: "backend/app/services/redaction/detection.py"
      provides: "detect_entities(text, thread_id=None) signature; conditional thread_id field in redaction.detect debug log"
      contains: "thread_id"
    - path: "backend/app/services/redaction_service.py"
      provides: "thread_id=registry.thread_id passed to detect_entities() at the 2 call sites in this file (lines 561, 623); thread_id field added to redact_text(reg) / redact_text_batch / de_anonymize_text debug logs (already present in redact_text(registry) line 433 — verify; absent in batch line 518 and de_anon line 925 — add)"
      contains: "thread_id="
    - path: "backend/app/services/redaction/egress.py"
      provides: "thread_id=<value> field in egress_filter_blocked WARNING log line"
      contains: "thread_id"
    - path: "backend/app/services/llm_provider.py"
      provides: "thread_id=<value> field in llm_provider_call INFO audit log (when registry kwarg provided)"
      contains: "thread_id"
    - path: "backend/app/services/redaction/missed_scan.py"
      provides: "thread_id=<value> field in all 3 logger.warning(event=missed_scan_skipped) calls (egress-blocked, validation-error, generic-exception soft-fail paths)"
      contains: "thread_id=%s"
  key_links:
    - from: "backend/app/services/redaction_service.py:_redact_text_with_registry"
      to: "backend/app/services/redaction/detection.py:detect_entities"
      via: "function call passing thread_id=registry.thread_id"
      pattern: "detect_entities\\(.*thread_id=registry\\.thread_id"
    - from: "backend/app/services/redaction/egress.py:egress_filter"
      to: "registry.thread_id"
      via: "logger.warning kwarg"
      pattern: "thread_id=%s"
    - from: "backend/app/services/llm_provider.py:LLMProviderClient.call"
      to: "registry.thread_id"
      via: "logger.info kwarg in resolved-provider audit line"
      pattern: "thread_id="
    - from: "backend/app/services/redaction/missed_scan.py:scan_for_missed_pii"
      to: "registry.thread_id"
      via: "logger.warning kwarg in all 3 soft-fail paths"
      pattern: "thread_id=%s"
threat_model:
  - id: "T-06-04-1"
    description: "T-2 (per CONTEXT planning_context security_considerations): new thread_id=<value> log fields could carry adjacent PII if log-line format inadvertently includes real text. Risk: a UUID-shaped thread_id is non-PII by construction (Supabase row id), but mis-implementation could leak."
    mitigation: "thread_id is sourced ONLY from registry.thread_id (a Supabase UUID — non-PII by construction). All existing log lines already follow the B4 invariant (counts + types + hashes only). Plan 06-04 adds a single key=value field; reviewer's grep gate (acceptance_criteria below) verifies no new f-string or %s carries `text`/`real_value`/`surrogate_value`. Plan 06-08's TestB4LogPrivacyForbiddenTokens test class runs `redact_text_batch + de_anonymize_text` against PII-bearing input and asserts that no real_value or surrogate substring (e.g. 'Bambang Sutrisno', 'ER-PERSON-') leaks into any caplog record across the 4 modified log call sites."
    severity: "low"
  - id: "T-06-04-2"
    description: "Backward-compat regression: existing test_detection_domain_deny_list.py and test_redact_text_batch.py call detect_entities() without thread_id; if signature change is positional-required, all 195+ existing tests crash."
    mitigation: "thread_id is added as an optional keyword arg with default None per D-P6-15 (verbatim). Acceptance criteria includes a grep gate `def detect_entities\\(.*thread_id:\\s*str\\s*\\|\\s*None\\s*=\\s*None` and a regression run of `pytest tests/unit -v` showing 195+ tests still pass."
    severity: "low"
---

<objective>
Add a `thread_id` correlation key to every per-operation debug/warning log line in the redaction pipeline so operators can `grep 'thread_id=<id>'` to extract one chat turn's full log block (OBS-02 verifiable). This plan also closes OBS-03 by extending `LLMProviderClient.call`'s resolved-provider audit line to include `thread_id`, and closes the SC#4 missed-scan log gap by extending `missed_scan.py`'s three soft-fail warnings.

Purpose: Phase 6 deliverable 4. Without the correlation key, debug-block extraction requires log timestamps (unreliable for concurrent threads). The change is mechanical (add an optional param; read `registry.thread_id` inside method bodies) but spans 5 files — keeping it in one plan ensures the "before/after grep deltas" stay visible in one diff. NOTE: this is the largest plan in the phase (5 tasks); the 5 are internally cohesive (all "add thread_id field").

Output: 5 modified files; signature change is backward-compatible (default None); off-mode is byte-identical (no new log lines added inside the off-mode early-return paths); all pre-existing tests still pass.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/06-embedding-provider-production-hardening/06-CONTEXT.md
@.planning/phases/03-entity-resolution-llm-provider-configuration/03-CONTEXT.md
@backend/app/services/redaction/detection.py
@backend/app/services/redaction_service.py
@backend/app/services/redaction/egress.py
@backend/app/services/llm_provider.py
@backend/app/services/redaction/missed_scan.py
@CLAUDE.md

<interfaces>
<!-- Existing log-line formats (B4 invariant — counts + types + hashes only). Phase 6 only ADDS thread_id=<value> field; never removes existing fields. -->

```python
# backend/app/services/redaction/detection.py:213 (current — line 292-303)
@traced(name="redaction.detect")
def detect_entities(text: str) -> tuple[str, list[Entity], dict[str, str]]:
    ...
    logger.debug(
        "redaction.detect: input_chars=%d uuid_drops=%d entities=%d surrogate=%d redact=%d "
        "denied=%d denied_types=%s elapsed_ms=%.2f",
        len(text), len(sentinels), len(entities),
        sum(1 for e in entities if e.bucket == "surrogate"),
        sum(1 for e in entities if e.bucket == "redact"),
        denied_count, sorted(denied_types), elapsed_ms,
    )
```

```python
# backend/app/services/redaction_service.py — three log call sites
# Line 432 (redact_text registry path) — ALREADY has thread_id; verify only
logger.debug(
    "redaction.redact_text(registry): thread_id=%s size_before=%d size_after=%d lock_wait_ms=%.2f writes=%d",
    registry.thread_id, size_before, size_after, lock_wait_ms, size_after - size_before,
)
# Line 517 (redact_text_batch) — ALREADY has thread_id; verify only
logger.debug(
    "redaction.redact_text_batch: thread_id=%s batch_size=%d hard_redacted_total=%d ms=%.2f",
    registry.thread_id, len(texts), hard_redacted_total, elapsed_ms,
)
# Line 923 (de_anonymize_text) — DOES NOT have thread_id; ADD
logger.debug(
    "redaction.de_anonymize_text: text_len=%d surrogate_count=%d "
    "placeholders_resolved=%d fuzzy_deanon_mode=%s "
    "fuzzy_matches_resolved=%d fuzzy_provider_fallback=%s ms=%.2f",
    len(text), len(entries), resolved, mode, fuzzy_matches_resolved, fuzzy_provider_fallback, latency_ms,
)
# Registry-aware result log inside _redact_text_with_registry — ANCHORED BY GREP, NOT LINE NUMBER
# Format string starts with: "redaction.redact_text(reg): chars=%d entities=%d clusters=%d ..."
# Phase 6 ADDS thread_id=%s as the FIRST field after the colon.
# Line 581 (_redact_text_stateless) — INTENTIONALLY no thread_id (registry=None path) — DO NOT ADD
```

```python
# backend/app/services/redaction/egress.py:117 (egress trip log — D-55, hashes only)
logger.warning(
    "egress_filter_blocked event=egress_filter_blocked match_count=%d entity_types=%s match_hashes=%s",
    result.match_count, result.entity_types, result.match_hashes,
)
# Phase 6 ADDS: thread_id=registry.thread_id (read from registry parameter — already in scope)
```

```python
# backend/app/services/llm_provider.py:182-227 (per-call audit log — verified at planning time)
# THREE logger.info call sites:
#   line 192-197: egress-tripped path — current format starts: "feature=%s provider=%s source=%s success=False latency_ms=%d egress_tripped=True"
#   line 210-214: success path        — current format starts: "feature=%s provider=%s source=%s success=True latency_ms=%d"
#   line 221-226: error path          — current format starts: "feature=%s provider=%s source=%s success=False latency_ms=%d error_type=%s"
# Phase 6 ADDS thread_id=<value> as the FIRST field of the format string in ALL THREE call sites.
# Source: registry parameter (already in method signature — line 176). Falls back to "-" sentinel when registry is None.
```

```python
# backend/app/services/redaction/missed_scan.py — three logger.warning soft-fail call sites
# (verified by reading missed_scan.py at planning time)
#
# Site 1 (~line 104, _EgressBlocked path):
#   logger.warning("event=missed_scan_skipped feature=missed_scan error_class=_EgressBlocked")
#
# Site 2 (~line 109, ValidationError path):
#   logger.warning("event=missed_scan_skipped feature=missed_scan error_class=ValidationError")
#
# Site 3 (~line 114-117, generic Exception path):
#   logger.warning("event=missed_scan_skipped feature=missed_scan error_class=%s", type(exc).__name__)
#
# `registry` parameter (ConversationRegistry) is in scope at all three sites
# (passed as the second arg to scan_for_missed_pii) — zero new wiring needed.
# Phase 6 ADDS thread_id=%s as the FIRST field after `event=missed_scan_skipped`.
```

```python
# Stateless detect_entities() callers — DO NOT pass thread_id (Phase 1 D-39 invariant)
# tests/unit/test_detection_domain_deny_list.py — calls detect_entities(text) directly; PRESERVE
# tests/unit/test_redact_text_batch.py — patches detect_entities via mock; PRESERVE
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Add optional thread_id param to detect_entities() and include in redaction.detect debug log</name>
  <read_first>
    - backend/app/services/redaction/detection.py (lines 212-305 — full detect_entities body, log statement at line 292)
    - .planning/phases/06-embedding-provider-production-hardening/06-CONTEXT.md (D-P6-14, D-P6-15 verbatim)
    - backend/tests/unit/test_detection_domain_deny_list.py (line 111, 133, 150 — existing positional call sites; verify NONE break under default=None signature)
  </read_first>
  <files>backend/app/services/redaction/detection.py</files>
  <behavior>
    - Test 1: `detect_entities("hello")` (no thread_id) returns the same 3-tuple as today; debug log line does NOT contain the substring `thread_id=`.
    - Test 2: `detect_entities("hello", thread_id="thread-xyz")` returns the same 3-tuple shape; debug log line DOES contain `thread_id=thread-xyz`.
    - Test 3: `detect_entities("hello", thread_id=None)` is byte-identical to Test 1 (None defaults to omitted field).
  </behavior>
  <action>
Modify the `detect_entities` function signature at line 213 to accept an optional `thread_id` keyword. Specifically:

Change line 213 from:

```python
def detect_entities(text: str) -> tuple[str, list[Entity], dict[str, str]]:
```

to:

```python
def detect_entities(
    text: str,
    thread_id: str | None = None,
) -> tuple[str, list[Entity], dict[str, str]]:
```

Update the docstring (line 214-235) — add this paragraph after the existing "Returns:" block, before the closing `"""`:

```
Args:
    text: Raw input text. May contain UUIDs.
    thread_id: Optional correlation key (Phase 6 OBS-02 / D-P6-14, D-P6-15).
        When supplied, the redaction.detect debug log line gains a
        `thread_id=<value>` field for grep-extractable correlation across
        the full chat turn (detection -> anonymization -> egress -> LLM).
        Stateless callers (Phase 1 D-39 path) MUST omit this — backward-
        compat is preserved by the default of None.
```

Modify the existing `logger.debug(...)` block at line 292-303. Change the format string and arguments to conditionally include `thread_id=<value>`. Use this exact replacement:

```python
    elapsed_ms = (time.perf_counter() - t0) * 1000
    if thread_id is not None:
        logger.debug(
            "redaction.detect: thread_id=%s input_chars=%d uuid_drops=%d entities=%d surrogate=%d redact=%d "
            "denied=%d denied_types=%s elapsed_ms=%.2f",
            thread_id,
            len(text),
            len(sentinels),
            len(entities),
            sum(1 for e in entities if e.bucket == "surrogate"),
            sum(1 for e in entities if e.bucket == "redact"),
            denied_count,
            sorted(denied_types),
            elapsed_ms,
        )
    else:
        logger.debug(
            "redaction.detect: input_chars=%d uuid_drops=%d entities=%d surrogate=%d redact=%d "
            "denied=%d denied_types=%s elapsed_ms=%.2f",
            len(text),
            len(sentinels),
            len(entities),
            sum(1 for e in entities if e.bucket == "surrogate"),
            sum(1 for e in entities if e.bucket == "redact"),
            denied_count,
            sorted(denied_types),
            elapsed_ms,
        )
```

Rationale for the if/else (verbose) instead of a single conditional format string: pre-existing test fixtures (e.g., test_detection_domain_deny_list.py) may caplog-assert against the existing format with no thread_id present. Two literal format strings keep the "no thread_id" path byte-identical to today (B4 invariant + test backward-compat).

Do NOT touch the `@traced(name="redaction.detect")` decorator (line 212) — span attributes are unchanged in this plan.

Do NOT touch the `_is_domain_term`, `_split_csv`, `Entity`, or `_PhoneRecognizerXX` declarations.

Do NOT add `thread_id` to the `Entity` Pydantic model — the field is a logging-only correlation key, not a per-entity attribute.
  </action>
  <verify>
    <automated>cd backend &amp;&amp; source venv/bin/activate &amp;&amp; pytest tests/unit/test_detection_domain_deny_list.py -v --tb=short -q 2>&amp;1 | tail -10</automated>
  </verify>
  <acceptance_criteria>
    - `grep -nE "def detect_entities\(\s*$" backend/app/services/redaction/detection.py` returns at least 1 match (multi-line signature)
    - `grep -nE "thread_id:\s*str\s*\|\s*None\s*=\s*None" backend/app/services/redaction/detection.py` returns at least 1 match (default-None invariant)
    - `grep -c 'redaction.detect: thread_id=' backend/app/services/redaction/detection.py` returns at least 1 (with-thread_id format present)
    - `grep -c 'redaction.detect: input_chars=' backend/app/services/redaction/detection.py` returns at least 1 (without-thread_id format preserved — byte-identical to pre-plan path)
    - `cd backend &amp;&amp; python -c "from app.main import app; print('OK')"` prints `OK`
    - `cd backend &amp;&amp; source venv/bin/activate &amp;&amp; pytest tests/unit/test_detection_domain_deny_list.py -v --tb=short -q 2>&amp;1 | grep -E "passed|failed" | tail -1` shows the same passing-count as pre-plan (no regressions)
  </acceptance_criteria>
  <done>detect_entities() accepts optional thread_id; both log paths exist; existing test_detection_domain_deny_list.py tests pass unchanged; backend imports cleanly.</done>
</task>

<task type="auto">
  <name>Task 2: Pass thread_id=registry.thread_id at the 2 detect_entities() call sites in redaction_service.py and add thread_id to de_anonymize_text + redact_text(reg) result debug logs</name>
  <read_first>
    - backend/app/services/redaction_service.py (lines 558-596 stateless path, 598-812 registry-aware path; line 814-935 de_anonymize_text)
    - .planning/phases/06-embedding-provider-production-hardening/06-CONTEXT.md (D-P6-14: pass `thread_id=registry.thread_id` into detect_entities; D-P6-16: add thread_id field in redact_text_batch and de_anonymize_text debug logs)
    - backend/tests/unit/test_redact_text_batch.py (lines 96-110 verify nothing breaks; line 105 patches detect_entities — verify the mock signature compatibility)
  </read_first>
  <files>backend/app/services/redaction_service.py</files>
  <action>
Make the following 4 edits to `backend/app/services/redaction_service.py`. Use grep anchors (NOT line numbers) — formatter passes drift line numbers between edits.

EDIT 1 — `_redact_text_stateless` body. The stateless path has NO registry, so per D-P6-14 it MUST NOT pass thread_id. Locate it via `grep -n "def _redact_text_stateless" backend/app/services/redaction_service.py` and confirm the `detect_entities(text)` call inside that function body. Leave that line unchanged.

EDIT 2 — `_redact_text_with_registry` body. The registry-aware path MUST pass thread_id. Locate via `grep -n "def _redact_text_with_registry" backend/app/services/redaction_service.py`; inside that function find the line `masked_text, entities, sentinels = detect_entities(text)` and change it to:

```python
        masked_text, entities, sentinels = detect_entities(text, thread_id=registry.thread_id)
```

EDIT 3 — Registry-aware result debug log inside `_redact_text_with_registry`. Locate the `logger.debug(` call whose first format-string token starts with `"redaction.redact_text(reg): chars=%d entities=%d clusters=%d"`. Add `thread_id=%s` as the FIRST field in the format string (right after `(reg): `) and `registry.thread_id` as the FIRST positional arg. Specifically, change the literal:

```python
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
```

to:

```python
        logger.debug(
            "redaction.redact_text(reg): thread_id=%s chars=%d entities=%d "
            "clusters=%d cluster_size_max=%d merged_via=%s "
            "surrogates=%d hard=%d uuid_drops=%d deltas=%d "
            "provider_fallback=%s egress_tripped=%s fallback_reason=%s ms=%.2f",
            registry.thread_id,
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
```

EDIT 4 — `de_anonymize_text` result debug log. Locate via `grep -n 'redaction.de_anonymize_text:' backend/app/services/redaction_service.py`. Add `thread_id=%s` as the FIRST field. Change:

```python
        logger.debug(
            "redaction.de_anonymize_text: text_len=%d surrogate_count=%d "
            "placeholders_resolved=%d fuzzy_deanon_mode=%s "
            "fuzzy_matches_resolved=%d fuzzy_provider_fallback=%s ms=%.2f",
            len(text),
            len(entries),
            resolved,
            mode,
            fuzzy_matches_resolved,
            fuzzy_provider_fallback,
            latency_ms,
        )
```

to:

```python
        logger.debug(
            "redaction.de_anonymize_text: thread_id=%s text_len=%d surrogate_count=%d "
            "placeholders_resolved=%d fuzzy_deanon_mode=%s "
            "fuzzy_matches_resolved=%d fuzzy_provider_fallback=%s ms=%.2f",
            registry.thread_id,
            len(text),
            len(entries),
            resolved,
            mode,
            fuzzy_matches_resolved,
            fuzzy_provider_fallback,
            latency_ms,
        )
```

Do NOT modify the `_redact_text_stateless` debug log — stateless path has no registry, so no thread_id field is appropriate (D-P6-15 backward-compat invariant).

Do NOT touch the `redact_text(registry):` and `redact_text_batch:` lines (they ALREADY include `thread_id=%s`); verify by grep but do not edit.

Do NOT modify any tracing span attribute calls — span attributes are unchanged.
  </action>
  <verify>
    <automated>cd backend &amp;&amp; source venv/bin/activate &amp;&amp; pytest tests/unit/test_redact_text_batch.py -v --tb=short -q 2>&amp;1 | tail -10</automated>
  </verify>
  <acceptance_criteria>
    - `grep -nE "detect_entities\(text, thread_id=registry\.thread_id\)" backend/app/services/redaction_service.py` returns exactly 1 match (registry-aware path only)
    - `grep -cE "detect_entities\(text\)" backend/app/services/redaction_service.py` returns exactly 1 match (stateless path preserved)
    - `grep -n "redaction.redact_text(reg): thread_id=%s" backend/app/services/redaction_service.py` returns at least 1 match
    - `grep -n "redaction.de_anonymize_text: thread_id=%s" backend/app/services/redaction_service.py` returns at least 1 match
    - `grep -nE "redaction\.redact_text\(registry\):\s*thread_id=%s" backend/app/services/redaction_service.py` returns at least 1 match (existing line unchanged — verify present)
    - `grep -nE "redaction\.redact_text_batch:\s*thread_id=%s" backend/app/services/redaction_service.py` returns at least 1 match (existing line unchanged — verify present)
    - `cd backend &amp;&amp; python -c "from app.main import app; print('OK')"` prints `OK`
    - `cd backend &amp;&amp; source venv/bin/activate &amp;&amp; pytest tests/unit -v --tb=short -q 2>&amp;1 | tail -5` shows pre-existing tests still passing (regression unchanged)
  </acceptance_criteria>
  <done>Both registry-aware detect_entities call sites pass thread_id; stateless call site unchanged; both new debug logs (`redact_text(reg)` and `de_anonymize_text`) include thread_id; backend imports cleanly.</done>
</task>

<task type="auto">
  <name>Task 3: Add thread_id field to egress.egress_filter trip log line</name>
  <read_first>
    - backend/app/services/redaction/egress.py (lines 63-122 — full egress_filter body, log statement at line 117)
    - .planning/phases/06-embedding-provider-production-hardening/06-CONTEXT.md (D-P6-16: egress filter trip log gains thread_id field, read from the `registry` parameter already in scope)
    - backend/tests/unit/test_egress_filter.py (any existing caplog assertions that would break; if file exists, verify which fields are asserted)
  </read_first>
  <files>backend/app/services/redaction/egress.py</files>
  <action>
Modify the `egress_filter` function's WARNING log statement (locate via `grep -n "egress_filter_blocked event=" backend/app/services/redaction/egress.py`). The `registry` parameter is already in scope (it is the second function arg). Change:

```python
    if result.tripped:
        # D-55: counts + entity_types + 8-char SHA-256 hashes ONLY. NEVER raw values.
        logger.warning(
            "egress_filter_blocked event=egress_filter_blocked match_count=%d entity_types=%s match_hashes=%s",
            result.match_count, result.entity_types, result.match_hashes,
        )
```

to:

```python
    if result.tripped:
        # D-55 + Phase 6 D-P6-16: counts + entity_types + 8-char SHA-256 hashes
        # ONLY. NEVER raw values. thread_id is the per-thread Supabase UUID
        # (non-PII by construction) — preserves grep-extractable correlation
        # for OBS-02.
        logger.warning(
            "egress_filter_blocked event=egress_filter_blocked thread_id=%s match_count=%d entity_types=%s match_hashes=%s",
            registry.thread_id, result.match_count, result.entity_types, result.match_hashes,
        )
```

Do NOT modify the `EgressResult` dataclass — adding `thread_id` to the dataclass is out of scope; logging-only field.

Do NOT modify `_EgressBlocked` exception class.

Do NOT modify the candidate-building loop — D-48 canonical-only invariant is preserved.

Do NOT change the order of existing fields — `thread_id` is inserted RIGHT AFTER `event=egress_filter_blocked` (the second field) so it groups with the event identifier.
  </action>
  <verify>
    <automated>cd backend &amp;&amp; source venv/bin/activate &amp;&amp; pytest tests/unit -v --tb=short -q -k "egress" 2>&amp;1 | tail -10</automated>
  </verify>
  <acceptance_criteria>
    - `grep -nE "egress_filter_blocked event=egress_filter_blocked thread_id=%s" backend/app/services/redaction/egress.py` returns exactly 1 match
    - `grep -n "registry.thread_id," backend/app/services/redaction/egress.py` returns at least 1 match
    - `grep -nE "egress_filter_blocked event=egress_filter_blocked match_count=%d" backend/app/services/redaction/egress.py` returns 0 matches (old format gone — replaced)
    - `cd backend &amp;&amp; python -c "from app.main import app; print('OK')"` prints `OK`
    - `cd backend &amp;&amp; source venv/bin/activate &amp;&amp; pytest tests/ -v --tb=short -q -k "egress" 2>&amp;1 | tail -5` shows existing egress tests still passing (zero regressions)
  </acceptance_criteria>
  <done>egress_filter trip log includes thread_id; backend imports cleanly; existing egress tests pass unchanged.</done>
</task>

<task type="auto">
  <name>Task 4: Add thread_id field to LLMProviderClient.call() resolved-provider audit log (OBS-03)</name>
  <read_first>
    - backend/app/services/llm_provider.py (lines 171-227 — full LLMProviderClient.call body. Three logger.info call sites verified at planning time: line 192-197 egress-tripped, line 210-214 success, line 221-226 error; format strings begin with `feature=%s provider=%s source=%s`)
    - .planning/phases/06-embedding-provider-production-hardening/06-CONTEXT.md (D-P6-17 verbatim: OBS-03 already implemented; Phase 6 ADDS thread_id field)
    - .planning/phases/03-entity-resolution-llm-provider-configuration/03-CONTEXT.md (D-51 / D-63: provider-resolution audit invariant — counts + provider + source + latency; never raw payload)
  </read_first>
  <files>backend/app/services/llm_provider.py</files>
  <action>
The `call()` method already accepts `registry: ConversationRegistry | None = None`. Read `thread_id` from `registry.thread_id` when registry is supplied; otherwise use the literal string `"-"`.

Add a helper at the top of the `call` method body (RIGHT AFTER `started = time.monotonic()`), insert this single line:

```python
        thread_id = registry.thread_id if registry is not None else "-"
```

Modify all 3 logger.info calls in the method body. Use grep anchors — NOT line numbers — to locate them: `grep -n 'logger.info' backend/app/services/llm_provider.py` returns the 3 sites; each format string begins with `feature=%s provider=%s source=%s`.

EDIT A — Egress-tripped log (the call site whose format string contains `egress_tripped=True`). Change:

```python
                logger.info(
                    "llm_provider_call event=llm_provider_call "
                    "feature=%s provider=%s source=%s success=False "
                    "latency_ms=%d egress_tripped=True",
                    feature, provider, source, latency_ms,
                )
```

to:

```python
                logger.info(
                    "llm_provider_call event=llm_provider_call "
                    "thread_id=%s feature=%s provider=%s source=%s success=False "
                    "latency_ms=%d egress_tripped=True",
                    thread_id, feature, provider, source, latency_ms,
                )
```

EDIT B — Success audit log (the call site whose format string contains `success=True`). Change:

```python
            logger.info(
                "llm_provider_call event=llm_provider_call "
                "feature=%s provider=%s source=%s success=True latency_ms=%d",
                feature, provider, source, latency_ms,
            )
```

to:

```python
            logger.info(
                "llm_provider_call event=llm_provider_call "
                "thread_id=%s feature=%s provider=%s source=%s success=True latency_ms=%d",
                thread_id, feature, provider, source, latency_ms,
            )
```

EDIT C — Error audit log (the call site whose format string contains `error_type=%s`). Change:

```python
            logger.info(
                "llm_provider_call event=llm_provider_call "
                "feature=%s provider=%s source=%s success=False latency_ms=%d "
                "error_type=%s",
                feature, provider, source, latency_ms, type(exc).__name__,
            )
```

to:

```python
            logger.info(
                "llm_provider_call event=llm_provider_call "
                "thread_id=%s feature=%s provider=%s source=%s success=False latency_ms=%d "
                "error_type=%s",
                thread_id, feature, provider, source, latency_ms, type(exc).__name__,
            )
```

Do NOT change the `provider, source = _resolve_provider(feature)` line — provider resolution order (D-51) is unchanged.

Do NOT add `thread_id` to the `egress_filter` call — egress_filter reads it directly from the `registry` parameter (Task 3 already wired this).

Do NOT modify `_get_client`, `_resolve_provider`, `_model_for`, or `_parse_response_content`.

Do NOT change the function signature — the existing `registry: "ConversationRegistry | None" = None` keyword-only kwarg is unchanged. Callers that did not pass registry will see `thread_id=-` in logs (sentinel value, not an error).
  </action>
  <verify>
    <automated>cd backend &amp;&amp; source venv/bin/activate &amp;&amp; pytest tests/unit/test_llm_provider_client.py -v --tb=short -q 2>&amp;1 | tail -10</automated>
  </verify>
  <acceptance_criteria>
    - `grep -nE "thread_id\s*=\s*registry\.thread_id\s+if\s+registry\s+is\s+not\s+None\s+else\s+\"-\"" backend/app/services/llm_provider.py` returns exactly 1 match
    - Positive gate (lockstep update): `grep -cE '"thread_id=%s feature=%s provider=%s source=%s' backend/app/services/llm_provider.py` returns exactly 3 (one per logger.info call site — verified by reading the file at planning time; if executor finds a different count, report and stop)
    - Negative gate (egress-tripped old format gone): `grep -cE '"feature=%s provider=%s source=%s success=False latency_ms=%d egress_tripped=True"' backend/app/services/llm_provider.py` returns 0
    - Negative gate (success old format gone): `grep -cE '"feature=%s provider=%s source=%s success=True latency_ms=%d"' backend/app/services/llm_provider.py` returns 0
    - `cd backend &amp;&amp; python -c "from app.main import app; print('OK')"` prints `OK`
    - `cd backend &amp;&amp; source venv/bin/activate &amp;&amp; pytest tests/unit -v --tb=short -q 2>&amp;1 | grep -E "passed|failed" | tail -1` shows pre-existing tests still passing
  </acceptance_criteria>
  <done>LLMProviderClient.call() audit log includes thread_id (or "-" sentinel) in all 3 paths (success / egress / error); backend imports cleanly; existing tests still pass.</done>
</task>

<task type="auto">
  <name>Task 5: Add thread_id=registry.thread_id to all 3 logger.warning soft-fail calls in missed_scan.py (D-P6-11 SC#4 closure)</name>
  <read_first>
    - backend/app/services/redaction/missed_scan.py (full file — verified at planning time: 3 logger.warning calls at ~lines 104, 109, 114 in the except branches; `registry` is in scope as the second function arg of scan_for_missed_pii)
    - backend/app/services/redaction/detection.py (existing format-string style — counts + thread_id + types only, B4 invariant)
    - .planning/phases/06-embedding-provider-production-hardening/06-CONTEXT.md (D-P6-11: missed-scan skip-path log gains thread_id correlation key; D-P6-14, D-P6-16 thread_id wiring invariants)
    - backend/tests/api/test_phase4_integration.py (any existing caplog assertions on event=missed_scan_skipped — verify additive thread_id field doesn't break them)
  </read_first>
  <files>backend/app/services/redaction/missed_scan.py</files>
  <action>
Locate the 3 `logger.warning` call sites in `scan_for_missed_pii` via `grep -n "logger.warning" backend/app/services/redaction/missed_scan.py` (expect 3 matches inside the three except branches: `_EgressBlocked`, `ValidationError`, generic `Exception`). The `registry` parameter (`ConversationRegistry`) is already in scope at all three sites — it's the second function arg.

EDIT 1 — `except _EgressBlocked:` branch. Change:

```python
    except _EgressBlocked:
        # Defense-in-depth backstop fired (Phase 3 D-53..D-56). Soft-fail.
        logger.warning(
            "event=missed_scan_skipped feature=missed_scan error_class=_EgressBlocked"
        )
        return anonymized_text, 0
```

to:

```python
    except _EgressBlocked:
        # Defense-in-depth backstop fired (Phase 3 D-53..D-56). Soft-fail.
        logger.warning(
            "event=missed_scan_skipped thread_id=%s feature=missed_scan error_class=_EgressBlocked",
            registry.thread_id,
        )
        return anonymized_text, 0
```

EDIT 2 — `except ValidationError:` branch. Change:

```python
    except ValidationError:
        logger.warning(
            "event=missed_scan_skipped feature=missed_scan error_class=ValidationError"
        )
        return anonymized_text, 0
```

to:

```python
    except ValidationError:
        logger.warning(
            "event=missed_scan_skipped thread_id=%s feature=missed_scan error_class=ValidationError",
            registry.thread_id,
        )
        return anonymized_text, 0
```

EDIT 3 — generic `except Exception:` branch. Change:

```python
    except Exception as exc:  # noqa: BLE001 — D-78 catch-all (timeout / 5xx / network)
        logger.warning(
            "event=missed_scan_skipped feature=missed_scan error_class=%s",
            type(exc).__name__,
        )
        return anonymized_text, 0
```

to:

```python
    except Exception as exc:  # noqa: BLE001 — D-78 catch-all (timeout / 5xx / network)
        logger.warning(
            "event=missed_scan_skipped thread_id=%s feature=missed_scan error_class=%s",
            registry.thread_id,
            type(exc).__name__,
        )
        return anonymized_text, 0
```

Do NOT modify the `MissedEntity` / `MissedScanResponse` Pydantic models — out of scope.

Do NOT modify `_valid_hard_redact_types`, the early-return paths, or the substring-replace loop — out of scope.

Do NOT change the `@traced(name="redaction.missed_scan")` decorator — span attributes are unchanged.

Do NOT add `thread_id` as a new function parameter — `registry.thread_id` is already reachable via the existing `registry` arg (zero new wiring).
  </action>
  <verify>
    <automated>cd backend &amp;&amp; source venv/bin/activate &amp;&amp; pytest tests/api/test_phase4_integration.py -v --tb=short -q 2>&amp;1 | tail -10</automated>
  </verify>
  <acceptance_criteria>
    - `grep -cE 'event=missed_scan_skipped.*thread_id=' backend/app/services/redaction/missed_scan.py` returns 3 (one per soft-fail warning call)
    - `grep -cE 'event=missed_scan_skipped feature=missed_scan' backend/app/services/redaction/missed_scan.py` returns 0 (old format gone — replaced in all 3 sites)
    - `grep -c 'registry.thread_id' backend/app/services/redaction/missed_scan.py` returns at least 3 (one positional arg per warning call)
    - `cd backend &amp;&amp; python -c "from app.main import app; print('OK')"` prints `OK`
    - `cd backend &amp;&amp; source venv/bin/activate &amp;&amp; pytest tests/ -v --tb=short -q -k "missed_scan or phase4" 2>&amp;1 | tail -5` shows existing missed-scan / phase 4 tests still passing
  </acceptance_criteria>
  <done>All 3 missed_scan logger.warning calls carry thread_id=registry.thread_id; old format fully replaced; backend imports cleanly; existing tests pass unchanged. SC#4 missed-scan-skip-path log gap closed.</done>
</task>

</tasks>

<verification>
1. `cd backend && source venv/bin/activate && pytest tests/unit -v --tb=short -q 2>&1 | tail -10` — all pre-existing 195+ unit tests continue to pass (signature change is backward-compat).
2. `cd backend && python -c "from app.main import app; print('OK')"` — backend imports cleanly.
3. `grep -rn "thread_id=" backend/app/services/redaction/ backend/app/services/redaction_service.py backend/app/services/llm_provider.py | wc -l` — count shows new fields exist (>= 11 matches across the 5 modified files).
4. `grep -rn 'logger\.\(debug\|info\|warning\)' backend/app/services/redaction/ backend/app/services/redaction_service.py backend/app/services/llm_provider.py | grep -vE "thread_id|stateless|chars=%d entities=%d sur" | wc -l` — sanity check that no log lines accidentally still log raw `text`/`real_value`/`surrogate_value` substrings (B4 invariant).
5. `cd backend && source venv/bin/activate && pytest tests/api -v --tb=short -q -k "phase5" 2>&1 | tail -5` — Phase 5 integration tests still pass (cross-cutting log changes are observable; no behavior changed).
</verification>

<success_criteria>
- detect_entities() accepts optional thread_id keyword (default None) per D-P6-15
- The "with thread_id" and "without thread_id" log paths are both literal format strings (not f-string interpolation) — preserves B4 invariant
- redaction_service passes thread_id=registry.thread_id at the registry-aware detect_entities call site only; stateless call site unchanged
- de_anonymize_text and the registry-aware redact_text result debug log gain thread_id field
- egress.egress_filter trip log gains thread_id field (read from registry param, already in scope)
- LLMProviderClient.call() audit log gains thread_id field at all 3 paths (success / egress trip / exception); falls back to "-" sentinel when registry is None
- missed_scan.py's 3 soft-fail logger.warning calls gain thread_id=registry.thread_id (D-P6-11 SC#4 closure)
- All pre-existing tests still pass
- Backend imports cleanly
- No new migrations
- B4 invariant preserved: log fields are counts + types + thread_id + provider strings only — no raw text, no real values, no surrogate values
</success_criteria>

<output>
After completion, create `.planning/phases/06-embedding-provider-production-hardening/06-04-SUMMARY.md` documenting:
- Diff of detect_entities() signature
- Diff of the 5 modified log statements (verbatim before/after)
- Output of `grep -rn "thread_id=" backend/app/services/redaction/ backend/app/services/redaction_service.py backend/app/services/llm_provider.py` showing the new fields
- Confirmation `pytest tests/unit -v --tb=short -q` pre-existing tests pass count is unchanged from prior plan
- Confirmation no migration files added
</output>
</content>
