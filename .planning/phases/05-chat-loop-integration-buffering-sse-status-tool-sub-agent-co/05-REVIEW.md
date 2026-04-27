---
phase: 05-chat-loop-integration-buffering-sse-status-tool-sub-agent-co
reviewed: 2026-04-28T00:00:00Z
depth: standard
files_reviewed: 15
files_reviewed_list:
  - backend/app/services/redaction/registry.py
  - backend/app/services/redaction/egress.py
  - backend/app/services/redaction_service.py
  - backend/app/routers/chat.py
  - backend/app/routers/admin_settings.py
  - backend/app/config.py
  - backend/app/services/agent_service.py
  - backend/tests/unit/test_egress_filter.py
  - backend/tests/unit/test_llm_provider_client.py
  - backend/tests/api/test_phase5_integration.py
  - backend/tests/unit/test_agent_service_classify_intent_egress.py
  - backend/tests/unit/test_chat_router_phase5_wiring.py
  - backend/tests/unit/test_redact_text_batch.py
  - backend/tests/unit/test_redaction_service_d84_gate.py
  - supabase/migrations/032_pii_redaction_enabled_setting.sql
findings:
  critical: 2
  warning: 4
  info: 2
  total: 8
status: issues_found
---

# Phase 05: Code Review Report

**Reviewed:** 2026-04-28T00:00:00Z
**Depth:** standard
**Files Reviewed:** 15
**Status:** issues_found

## Summary

This phase integrates the PII redaction pipeline into the chat loop — the most security-critical wiring in the v1.0 PII milestone. The bulk of the implementation is sound: the `canonicals()` algorithm is correct, the `entries()` → `canonicals()` switch in `egress_filter` correctly addresses the D-48 variant-cascade false-positive, migration 032 is syntactically correct, and the off-mode (D-84) path is properly guarded in both `redact_text` and `redact_text_batch`.

Two critical defects require attention:

1. **Privacy regression in `canonicals()` under surrogate collision**: If two distinct real identities share the same surrogate (a Faker collision that the collision budget can leave undetected across turns), `canonicals()` silently drops one real value from the egress scan. The LLM payload invariant would then be violated for the dropped identity on subsequent turns.

2. **Test stub `_StubRegistry` in `test_agent_service_classify_intent_egress.py` is missing `canonicals()`**: `egress_filter` now calls `registry.canonicals()`, but the stub only implements `entries()`. Tests that pass this stub through to `egress_filter` will raise `AttributeError` at runtime when the egress filter attempts to call `canonicals()`.

Four warnings also identified, primarily around the module-level `_PII_GUIDANCE` baking in `agent_service.py` and a docstring stale reference in `egress.py`.

---

## Critical Issues

### CR-01: `canonicals()` drops real identities when two distinct real values share the same surrogate (Faker collision)

**File:** `backend/app/services/redaction/registry.py:172-177`

**Issue:** `canonicals()` deduplicates by `surrogate_value`, keeping only the *longest* `real_value` per surrogate. This is correct when the D-48 assumption holds — that all rows sharing a surrogate are variants of one canonical. However, Faker's per-thread collision budget operates per-call, not per-persisted-registry-entry. If across two separate turns Faker generates the same surrogate for two unrelated real names (e.g., "Maria Santos" in Turn 1 and "Diego Torres" in Turn 2), both rows land in `entity_registry` with the same `surrogate_value`. On Turn 3, `canonicals()` will return whichever has the longer `real_value` string — the other real identity is silently excluded from the egress scan candidate set.

Verified by tracing `used_surrogates` scope in `anonymization.py` lines 253 and 279: the set is constructed fresh per `anonymize()` call and populated with surrogates from the registry only for cross-turn *reuse* (same canonical), not for cross-cluster collision avoidance. A new cluster in a new turn does not seed `used_surrogates` from all existing `entity_registry` rows.

The correct fix is either:
- (a) Deduplicate by `(surrogate_value, entity_type)` keeping the longest *and also* emit separate entries for each distinct entity_type, to ensure all reals sharing a surrogate are still scanned; OR
- (b) Have `canonicals()` return ALL rows where there are distinct real values sharing a surrogate (not just the longest), accepting the variant-cascade false-positive tradeoff as the lesser evil.

Option (b) is actually correct per the D-48 invariant: if two *different* real identities share a surrogate, that is a bug in the anonymization layer, not in the egress filter. The egress filter should scan all of them. The proper fix is: group by `surrogate_value` and keep all rows whose `real_value` is not a prefix-/suffix-variant of any other row in the same group. As a safe interim fix, revert to `entries()` for non-PERSON entity types (where D-48 variant clustering does not apply), and apply `canonicals()` only to PERSON rows — or, simpler: keep the current longest-wins logic but emit one entry per *distinct* `real_value_lower`, not per surrogate.

```python
# Safe interim fix: deduplicate by real_value_lower (true duplicates only),
# not by surrogate_value. Avoids false-positive suppression without re-introducing
# the D-48 variant cascade.
def canonicals(self) -> list[EntityMapping]:
    seen_lower: set[str] = set()
    result: list[EntityMapping] = []
    # Sort by len(real_value) DESC so canonical (longest) is seen first per cluster.
    for ent in sorted(self._rows, key=lambda m: len(m.real_value), reverse=True):
        if ent.real_value_lower not in seen_lower:
            seen_lower.add(ent.real_value_lower)
            result.append(ent)
    return result
```

This approach deduplicates true exact-casefold duplicates (same real, same surrogate — fine to deduplicate) while preserving all distinct real values even if they share a surrogate.

**Severity: BLOCKER** — Privacy invariant violation: a real identity can reach a cloud LLM payload undetected after a surrogate collision.

---

### CR-02: `_StubRegistry` in `test_agent_service_classify_intent_egress.py` missing `canonicals()` method — tests will fail with `AttributeError` at runtime

**File:** `backend/tests/unit/test_agent_service_classify_intent_egress.py:49-58`

**Issue:** The `_StubRegistry` stub only implements `entries()`. After the Phase 5 D-48 gap-closure, `egress_filter` calls `registry.canonicals()` (line 95 of `egress.py`). The `classify_intent` tests in `TestClassifyIntentEgressTrip` pass a `_StubRegistry` instance, which then flows through `egress_filter`. Any test that does not mock `egress_filter` itself will hit `AttributeError: '_StubRegistry' object has no attribute 'canonicals'` at `egress_filter` line 95.

Currently, `TestClassifyIntentEgressTrip.test_egress_trip_skips_llm_and_returns_fallback` and most other trip tests patch `egress_filter` entirely (`patch.object(agent_service, "egress_filter", ...)`), so those specific tests are safe. However:

- `TestClassifyIntentBackwardCompat.test_no_registry_kwarg_skips_egress_calls_llm` also patches `egress_filter` as a side_effect=AssertionError sentinel (so it must not be called), making it technically safe — but only by design coincidence.
- `TestClassifyIntentEgressTrip.test_egress_no_trip_proceeds_to_llm_call` at line 248 passes `registry = _StubRegistry([])` with `egress_filter` mocked, so it is safe.
- `test_egress_called_with_serialized_messages_and_registry` at line 276 similarly patches egress_filter — safe.

Despite the current tests passing due to blanket mocking, the stub is structurally incorrect: `_StubRegistry` does not satisfy the `ConversationRegistry` duck-type contract used by `egress_filter`. If any future test relaxes the mock or calls `egress_filter` without patching it, the stub will cause an `AttributeError`. The other test files (`test_egress_filter.py`, `test_llm_provider_client.py`) have already been correctly updated to add `canonicals()` to their stubs. This file was not updated.

```python
class _StubRegistry:
    """Minimal duck-typed stand-in for ConversationRegistry."""

    def __init__(self, mappings=(), thread_id="00000000-0000-0000-0000-000000000000"):
        self._mappings = list(mappings)
        self.thread_id = thread_id

    def entries(self):
        return self._mappings

    def canonicals(self):
        # For this stub, all mappings are treated as canonical (no variants).
        return self._mappings
```

**Severity: BLOCKER** — Any test that calls `egress_filter` without patching it, using this stub, will crash. The structural incompatibility should be fixed to prevent silent test rot as the test suite grows.

---

## Warnings

### WR-01: `_PII_GUIDANCE` baked at module import time in `agent_service.py` — admin toggle does not take effect until process restart

**File:** `backend/app/services/agent_service.py:22-24`

**Issue:** `_PII_GUIDANCE` is computed once at module load time by calling `get_system_settings().get("pii_redaction_enabled", True)`. It is then concatenated into four `AgentDefinition.system_prompt` strings, which are also module-level constants (lines 26-97). When an admin toggles `pii_redaction_enabled` via `PATCH /admin/settings`, the DB value changes and `get_system_settings()` will reflect the new value within 60 seconds (TTL cache). However, `_PII_GUIDANCE` and all four `system_prompt` strings remain frozen at their import-time value for the entire lifetime of the process.

This is documented in the inline comment ("changes take effect within the 60s cache TTL on subsequent requests"), but that comment is incorrect: the change does NOT take effect on subsequent requests at all, because the `system_prompt` string is already baked. Only a process restart propagates the change. The per-request branch in chat.py correctly calls `get_pii_guidance_block(redaction_enabled=redaction_on)` at request time (line 386-387), so branch B (single-agent path) is correct. Branch A (multi-agent path) uses `agent_def.system_prompt`, which is the stale baked value.

This means: if an admin disables redaction while the process is running, the multi-agent path will continue instructing the LLM to preserve surrogates in its system prompt — incorrect behavior (though the functional redaction pipeline will correctly skip, so it is only a token waste and mildly misleading, not a security issue).

```python
# Fix: compute pii_guidance dynamically at classify_intent / get_agent call time
# rather than baking it into the AgentDefinition at import time.

# In event_generator, branch A, after classification:
agent_def = agent_service.get_agent(agent_name)
pii_guidance = get_pii_guidance_block(redaction_enabled=redaction_on)
system_prompt_with_guidance = agent_def.system_prompt_base + pii_guidance
messages = [{"role": "system", "content": system_prompt_with_guidance}, ...]
```

Alternatively, store `system_prompt_base` (without guidance) in `AgentDefinition` and compose the full prompt at request time.

**Severity: WARNING** — Functional correctness for admin-toggle propagation in multi-agent path. Not a security issue but a behavioral inconsistency.

---

### WR-02: Stale docstring in `egress.py` still references `entries()` after the `canonicals()` switch

**File:** `backend/app/services/redaction/egress.py:76-78`

**Issue:** The `egress_filter` function's `Args` docstring still says "the per-thread ConversationRegistry whose `entries()` supplies the persisted real values." The implementation was correctly changed to call `registry.canonicals()` at line 95, but the docstring was not updated. This creates misleading documentation for future maintainers who will believe `entries()` is the method contract — which matters because the two methods have different semantics (entries() includes variants; canonicals() excludes them).

```python
# Fix: update the docstring arg description
registry: the per-thread ConversationRegistry whose canonicals() supplies
    the persisted real values (variants are excluded — see D-48 gap-closure).
```

**Severity: WARNING** — Misleading documentation in a security-critical function. Could cause a future maintainer to incorrectly swap `canonicals()` back to `entries()`.

---

### WR-03: `redact_text_batch` off-mode check occurs AFTER the `registry is None` ValueError check would need to fire — order creates a latent logic gap

**File:** `backend/app/services/redaction_service.py:486-497`

**Issue:** In `redact_text_batch`, the off-mode check at line 486 runs first, returning `list(texts)` for any input including `registry=None`. Then the `registry is None` guard fires at line 492. This ordering means: in off-mode, a caller passing `registry=None` with a non-empty `texts` list does NOT get the expected `ValueError` — instead it silently returns the texts unchanged, bypassing the strict primitive contract.

The docstring says "Raises: ValueError if registry is None", but in off-mode that contract is violated. This is a latent bug: if chat.py ever calls `redact_text_batch(texts, None)` while off-mode is active, the call will silently succeed (returning texts unchanged) rather than raising, masking a programming error that should be surfaced during development.

```python
# Fix: check registry=None BEFORE the off-mode gate, or document that
# registry=None is only validated in on-mode.
if registry is None and texts:
    raise ValueError(
        "redact_text_batch requires a loaded ConversationRegistry; "
        "this primitive is the chat-loop chokepoint, not the stateless path."
    )

if not bool(get_system_settings().get("pii_redaction_enabled", True)):
    return list(texts)
```

**Severity: WARNING** — Programming-error masking. In off-mode, a caller bug (passing `registry=None`) is silently accepted rather than caught.

---

### WR-04: `egress_filter` in `_run_tool_loop` passes `provisional=None` — misses in-flight entities from the current turn's tool loop iterations

**File:** `backend/app/routers/chat.py:171`

**Issue:** At D-94 site #1 (the per-iteration egress check inside `_run_tool_loop`), `egress_filter` is called with `provisional=None`. The D-56 design intent is that `provisional` captures entities detected *this turn* but not yet persisted to the registry. By the time `_run_tool_loop` runs, the D-93 batch anonymization has already completed and `upsert_delta` has committed those entities to the registry. So for entities from the user message, `provisional=None` is correct — they are already in `registry.entries()` and will be caught by `canonicals()`.

However, if `anonymize_tool_output` (called at line 219) detects and registers new PII from tool results that were not in the original user message, those new entities are upserted into the registry (via `_redact_text_with_registry` → `upsert_delta`). The next iteration's egress filter call at line 171 will pick them up from the registry. This path appears correct.

The concern is narrower: the egress check at line 171 runs BEFORE the current iteration's `complete_with_tools` call. If the previous iteration's `anonymize_tool_output` introduced new entities (and they were upserted), those entities ARE visible in the registry for the current iteration's check. So the `provisional=None` is defensible for the tool-loop site. However, it diverges from `_resolve_clusters_via_llm` (which builds a proper provisional map at line 220-222 of `redaction_service.py`), making the two egress call sites inconsistent in their provisionality contract.

The discrepancy is low risk in practice but should be documented if not intentional.

```python
# Document the intentionality (or compute a provisional set if a stricter
# safety invariant is needed):
# provisional=None is correct here because D-93's upsert_delta has already
# committed this turn's user-message entities to the registry before _run_tool_loop
# is entered. Tool-output-introduced entities are upserted by anonymize_tool_output
# before the next iteration's egress check.
```

**Severity: WARNING** — Behavioral divergence between egress call sites in the tool loop and the LLM entity-resolution path. Low probability of a real leak, but the inconsistency should be documented.

---

## Info

### IN-01: Migration 032 backfill UPDATE is a no-op when `ADD COLUMN IF NOT EXISTS` already supplied the default — minor SQL redundancy

**File:** `supabase/migrations/032_pii_redaction_enabled_setting.sql:17`

**Issue:** The `ADD COLUMN IF NOT EXISTS pii_redaction_enabled BOOLEAN NOT NULL DEFAULT TRUE` clause sets the column default to `TRUE` for all existing rows at the time of the ALTER. The subsequent `UPDATE system_settings SET pii_redaction_enabled = TRUE WHERE id = 1` is therefore a no-op in all cases (either the column is new and already set to TRUE by the DEFAULT, or the column already existed and the IF NOT EXISTS branch skipped the ALTER entirely). While harmless, the comment "Idempotent backfill" creates the impression the UPDATE is doing something useful.

This is not a bug, but future migration authors reading this as a template may copy the redundant pattern unnecessarily.

**Fix:** Either remove the UPDATE or change the comment to "Explicit confirm for clarity — redundant given DEFAULT TRUE in the ALTER."

---

### IN-02: `test_redaction_service_d84_gate.py:test_on_mode_stateless_path_unchanged` uses the live `get_system_settings()` without patching — will fail if DB returns `pii_redaction_enabled=False`

**File:** `backend/tests/unit/test_redaction_service_d84_gate.py:113-127`

**Issue:** This test calls `svc.redact_text("Bambang Sutrisno called.")` without patching `get_system_settings`. If the test environment's Supabase `system_settings` table has `pii_redaction_enabled=FALSE` (e.g., after a QA session where an admin disabled redaction), the D-84 gate fires and returns `latency_ms=0.0`. The assertion `assert result.latency_ms > 0.0` then fails with a confusing error unrelated to the code under test.

```python
# Fix: patch system_settings explicitly in the on-mode test
async def test_on_mode_stateless_path_unchanged(self):
    from app.services.redaction_service import get_redaction_service
    svc = get_redaction_service()
    with patch("app.services.redaction_service.get_system_settings", return_value=_SYS_ON):
        result = await svc.redact_text("Bambang Sutrisno called.")
    assert result.latency_ms > 0.0
```

---

_Reviewed: 2026-04-28T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
