---
phase: 06-embedding-provider-production-hardening
reviewed: 2026-04-29T07:51:00Z
depth: standard
files_reviewed: 16
files_reviewed_list:
  - CLAUDE.md
  - backend/app/config.py
  - backend/app/services/embedding_service.py
  - backend/app/services/llm_provider.py
  - backend/app/services/redaction/detection.py
  - backend/app/services/redaction/egress.py
  - backend/app/services/redaction/missed_scan.py
  - backend/app/services/redaction_service.py
  - backend/pyproject.toml
  - backend/tests/services/redaction/test_perf04_degradation.py
  - backend/tests/services/redaction/test_perf_latency.py
  - backend/tests/services/redaction/test_thread_id_logging.py
  - backend/tests/unit/test_detect_entities_thread_id.py
  - backend/tests/unit/test_egress_filter.py
  - backend/tests/unit/test_embedding_provider_branch.py
  - backend/tests/unit/test_llm_provider_client.py
findings:
  critical: 2
  warning: 6
  info: 3
  total: 11
status: issues_found
---

# Phase 06: Code Review Report

**Reviewed:** 2026-04-29T07:51:00Z
**Depth:** standard
**Files Reviewed:** 16
**Status:** issues_found

## Summary

Phase 6 delivers three distinct deliverables: (1) embedding provider switch (`EMBEDDING_PROVIDER=local/cloud`) in `embedding_service.py`, (2) `thread_id` correlation logging wired through the entire redaction pipeline (detection → egress → missed_scan → llm_provider → redaction_service), and (3) a suite of regression tests covering PERF-04 graceful degradation, PERF-02 latency, OBS-02/03 log format, and B4 privacy invariant.

The embedding provider branch itself is clean. The thread_id propagation is correctly wired in every production file reviewed. The test suite is well-structured and the B4 / OBS invariant tests are sound.

**Two blockers were found:**

1. **chat.py title-gen fallback was NOT shipped.** Plan 06-05 was declared complete in a SUMMARY, but `chat.py` line 640 still reads `except Exception: pass`. The 6-word stub formula and `logger.info("chat.title_gen_fallback ...")` described in the plan and tested in `test_perf04_degradation.py::TestTitleGenFallback` do not exist in the production file. The test for log-line emission manufactures the log line itself rather than calling the real code path — it is a false-green test that can never catch a regression.

2. **`embedding_provider=local` with an empty `local_embedding_base_url` silently misbehaves.** `config.py` sets `local_embedding_base_url: str = ""` as the default, and `embedding_service.py` passes that empty string directly as `base_url` to `AsyncOpenAI`. The OpenAI SDK does not raise at construction time on an empty `base_url`; the error surfaces only at the first API call with an unhelpful URL-related exception. An operator who sets `EMBEDDING_PROVIDER=local` but forgets to set `LOCAL_EMBEDDING_BASE_URL` gets a confusing runtime failure instead of a startup-time configuration error.

Six warnings and three informational items follow.

---

## Critical Issues

### CR-01: Plan 06-05 title-gen fallback not present in `chat.py` — test is a false-green

**File:** `backend/app/routers/chat.py:640`
**Issue:** The submitted `chat.py` still has the original `except Exception: pass` at line 640 (the title-gen exception handler). The Plan 06-05 SUMMARY declared the work complete, and `test_perf04_degradation.py::TestTitleGenFallback::test_title_gen_fallback_emits_log_line` (lines 260-289) was written to guard this change. However, that test does NOT call `chat.py` — it constructs the fallback log line itself inside the test body (lines 274-282), then asserts the log line it just emitted is present. It passes whether or not `chat.py` has been changed. The plan's promised deliverables (6-word stub, `logger.info("chat.title_gen_fallback ...")`, `thread_id` in the fallback log) are absent from production code.

**Fix:** Wire the Plan 06-05 fallback block into `chat.py` at the title-gen exception site:

```python
except Exception as exc:
    # Plan 06-05 / D-P6-12: 6-word template fallback.
    stub = " ".join(anonymized_message.split()[:6])
    if not stub:
        stub = "New Thread"
    logger.info(
        "chat.title_gen_fallback event=title_gen_fallback "
        "thread_id=%s error_class=%s",
        body.thread_id, type(exc).__name__,
    )
    # De-anon the stub title before emit (surrogates must not persist as title).
    if redaction_on and registry is not None:
        stub = await redaction_service.de_anonymize_text(stub, registry, mode="none")
    if stub:
        client.table("threads").update({"title": stub}).eq("id", body.thread_id).execute()
        yield f"data: {json.dumps({'type': 'thread_title', 'title': stub, 'thread_id': body.thread_id})}\n\n"
```

Additionally, `test_title_gen_fallback_emits_log_line` must be rewritten to call the real `event_generator` path rather than emitting the log line inline.

---

### CR-02: `embedding_provider=local` with empty `local_embedding_base_url` silently passes construction, fails at first API call

**File:** `backend/app/services/embedding_service.py:17-19`
**Issue:** When `EMBEDDING_PROVIDER=local` is set and `LOCAL_EMBEDDING_BASE_URL` is not set (or left at the default `""`), `AsyncOpenAI(base_url="", api_key="not-needed")` is constructed without error. The OpenAI Python SDK silently accepts an empty string as `base_url` at `__init__` time. The failure surface is the first `embed_text` or `embed_batch` call, which produces an unhelpful URL-parsing or connection-refused error with no indication that a misconfiguration is the root cause. In production on Railway, this would cause all document ingestion to fail after deployment without any startup-time signal.

```python
# config.py line 61
local_embedding_base_url: str = ""  # empty default — no validation
```

```python
# embedding_service.py line 17-19
if settings.embedding_provider == "local":
    self.client = AsyncOpenAI(
        base_url=settings.local_embedding_base_url,   # can be "" — accepted silently
        api_key="not-needed",
    )
```

**Fix:** Add a startup guard in `EmbeddingService.__init__`:

```python
if settings.embedding_provider == "local":
    if not settings.local_embedding_base_url:
        raise ValueError(
            "EMBEDDING_PROVIDER=local requires LOCAL_EMBEDDING_BASE_URL to be set "
            "(e.g. 'http://localhost:11434/v1' for Ollama). "
            "Current value is empty."
        )
    self.client = AsyncOpenAI(
        base_url=settings.local_embedding_base_url,
        api_key="not-needed",
    )
```

Alternatively, add a Pydantic `@model_validator` to `Settings`:

```python
from pydantic import model_validator

@model_validator(mode="after")
def _validate_local_embedding(self) -> "Settings":
    if self.embedding_provider == "local" and not self.local_embedding_base_url:
        raise ValueError(
            "LOCAL_EMBEDDING_BASE_URL must be set when EMBEDDING_PROVIDER=local"
        )
    return self
```

---

## Warnings

### WR-01: `_fuzzy_match_llm` and `_EgressBlocked` soft-fail log lines missing `thread_id`

**File:** `backend/app/services/redaction_service.py:1134-1136, 1146-1148`
**Issue:** Plan 06-04 added `thread_id` to all soft-fail WARNING log lines across the redaction pipeline. The `missed_scan.py` soft-fail logs correctly include `thread_id=%s`. However, the two equivalent soft-fail WARNING log lines in `_fuzzy_match_llm` do not include `thread_id`:

```python
# line 1134-1136 (_EgressBlocked branch)
logger.warning(
    "event=fuzzy_deanon_skipped feature=fuzzy_deanon "
    "error_class=_EgressBlocked"          # ← no thread_id field
)

# line 1146-1148 (catch-all branch)
logger.warning(
    "event=fuzzy_deanon_skipped feature=fuzzy_deanon "
    "error_class=%s",                      # ← no thread_id field
    type(exc).__name__,
)
```

`_fuzzy_match_llm` receives `registry` (which carries `registry.thread_id`) as a parameter, so the field is available.

**Fix:**
```python
# _EgressBlocked branch
logger.warning(
    "event=fuzzy_deanon_skipped feature=fuzzy_deanon "
    "thread_id=%s error_class=_EgressBlocked",
    registry.thread_id,
)

# catch-all branch
logger.warning(
    "event=fuzzy_deanon_skipped feature=fuzzy_deanon "
    "thread_id=%s error_class=%s",
    registry.thread_id, type(exc).__name__,
)
```

---

### WR-02: `missed_scan.py` substring replacement is case-sensitive — will miss uppercase/mixed-case PII occurrences

**File:** `backend/app/services/redaction/missed_scan.py:130`
**Issue:** The missed-PII replacement loop uses `re.subn(re.escape(ent.text), placeholder, out)` without the `re.IGNORECASE` flag. If the LLM returns `"john.doe@example.com"` as the `text` field but the actual occurrence in the already-anonymized text happens to be in a slightly different case (e.g., from a quoted block that preserved original casing), the substitution silently misses it and the PII passes through unreplaced. The D-77 spec says "server uses re.escape(text) + re.subn to replace ALL occurrences" — case-insensitive matching is the safer default for an entity the scan LLM identified.

**Fix:**
```python
new_text, n = re.subn(re.escape(ent.text), placeholder, out, flags=re.IGNORECASE)
```

---

### WR-03: `egress_filter` called positionally in `llm_provider.py` with argument name mismatch

**File:** `backend/app/services/llm_provider.py:188`
**Issue:** `egress_filter` is defined with the third parameter named `provisional` (`def egress_filter(payload, registry, provisional)`), but `LLMProviderClient.call` passes it under the name `provisional_surrogates` in the public call signature and docstring (line 160, 177). The actual invocation at line 188 passes the argument positionally, which works, but the keyword name `provisional_surrogates` in `LLMProviderClient.call`'s signature creates a misleading asymmetry: callers of `.call()` pass `provisional_surrogates=` while the underlying filter uses `provisional=`. If a future maintainer switches line 188 to a keyword call (`egress_filter(payload_str, registry, provisional=provisional_surrogates)` or mistakenly `provisional_surrogates=provisional_surrogates`), they will get a `TypeError`. This was flagged in a prior observation (obs 3712) as already known but never resolved.

**Fix:** Align the parameter name in `egress_filter` to `provisional_surrogates`, or add a comment at line 188 flagging the positional-only intent:
```python
# positional: egress_filter(payload, registry, provisional) — 3rd arg name differs from .call() kwarg
result = egress_filter(payload_str, registry, provisional_surrogates)
```

---

### WR-04: `test_title_gen_fallback_emits_log_line` is a vacuous test — it cannot detect missing production code

**File:** `backend/tests/services/redaction/test_perf04_degradation.py:260-289`
**Issue:** (Elaboration of CR-01.) This test is not just untested production code — it actively provides false confidence. The test body raises an exception, then emits the expected log line directly (`logger.info("chat.title_gen_fallback ...")`) inside the `except` block, and asserts that the log line appeared. It will always pass regardless of whether `chat.py` was changed. The docstring says "Re-create the relevant fallback block … this test guards its log-emission invariant in isolation" but "guarding in isolation" here means the test cannot catch the regression it was designed to catch.

**Fix:** Replace the test body with a mock-patched call through the real `chat.py` `event_generator` path (or at minimum document clearly that this is a formula-only unit test and a separate integration test is required for the wiring). The test as written should not be treated as green for the D-P6-12 acceptance criterion.

---

### WR-05: `EmbeddingService` reads `settings` from a module-level singleton at import time — provider branch is fixed for the process lifetime

**File:** `backend/app/services/embedding_service.py:6`
**Issue:** `settings = get_settings()` is evaluated once at module import time (line 6), and `EmbeddingService.__init__` branches on `settings.embedding_provider` from that singleton. `get_settings()` is `@lru_cache`'d so the value is frozen after first call. This means: (a) if the embedding provider is changed in the environment after process start, it is never picked up without a restart — which is expected and documented; (b) more critically, every `EmbeddingService()` instance (if multiple are constructed) will use the same module-level `settings` snapshot. This is fine in the current single-instance pattern but is a subtle trap: `monkeypatch.setattr("app.services.embedding_service.settings", fake)` in tests works precisely because it replaces the module attribute, but test isolation relies on the import cache not being reset between tests. The existing tests (`test_embedding_provider_branch.py`) handle this correctly with `monkeypatch`, but the pattern is fragile.

The real concern: `EmbeddingService.__init__` should call `get_settings()` rather than relying on the module-level `settings` to ensure it always reflects the cache state at instantiation time, which is the pattern used in `llm_provider.py`'s `_get_client`.

**Fix:** Remove the module-level `settings = get_settings()` and call `get_settings()` inside `__init__`:
```python
def __init__(self):
    settings = get_settings()  # reads from lru_cache — same singleton, but explicit
    if settings.embedding_provider == "local":
        ...
    self.model = settings.openai_embedding_model
```

---

### WR-06: `_FuzzyMatch.token` Pydantic regex pattern uses `[0-9a-f]` (hex) but `de_anonymize_text` generates tokens with `%04d` (decimal, including digits 0-9 only)

**File:** `backend/app/services/redaction_service.py:140, 889`
**Issue:** The `_FuzzyMatch` Pydantic model validates LLM-returned token strings against the pattern `r"^<<PH_[0-9a-f]+>>$"` (line 140), which accepts hex digits (0–9, a–f). However, tokens are generated at line 889 with `f"<<PH_{i:04d}>>"` which uses zero-padded decimal formatting. For i < 10000 the digits are 0–9 only, which are valid hex. But the pattern **also permits** LLM-fabricated tokens like `<<PH_dead>>` or `<<PH_cafe1>>` which are valid per the regex but will NEVER match a real generated token (since `%04d` only produces numeric strings). This means: a misbehaving LLM that returns `{"span": "foo", "token": "<<PH_dead>>"}` passes Pydantic validation, then gets rejected by the `if match.token not in valid_tokens` check at line 1165 — so the D-73 server-side guard does catch it. However, the Pydantic validation layer provides weaker protection than it appears to, and the regex documents a contract (`[0-9a-f]`) that does not match the actual generation format (`%04d`).

**Fix:** Align the Pydantic regex with the actual generation format:
```python
token: str = Field(..., pattern=r"^<<PH_[0-9]+>>$")
```
This is strictly tighter (only decimal digits allowed) and matches what `de_anonymize_text` actually produces.

---

## Info

### IN-01: `config.py` has no startup validation for `local_llm_base_url` consistency with `llm_provider`

**File:** `backend/app/config.py:113`
**Issue:** Unlike the embedding provider, `local_llm_base_url` defaults to `"http://localhost:1234/v1"` (a non-empty, non-trivially-wrong value), and `llm_provider` defaults to `"local"`. This means local-LLM features work silently against the default LM Studio port without any explicit operator configuration. This is an acceptable design choice but the default endpoint may surprise operators who intend cloud-only mode but forget to set `LLM_PROVIDER=cloud`. No code change required, but a CLAUDE.md gotcha entry would help.

---

### IN-02: `missed_scan.py` passes `provisional_surrogates=None` to `LLMProviderClient.call` — this means cloud mode egress filter receives `None` provisional set for a feature that runs POST-anonymization

**File:** `backend/app/services/redaction/missed_scan.py:99`
**Issue:** The comment "D-56: no provisional set for this feature" is architecturally correct — by the time the missed-scan call runs, the primary anonymization has already completed and all real values from this turn have been committed to the registry. There are no in-flight provisional surrogates. This is not a bug. However, the comment could mislead a future maintainer into thinking the provisional set is irrelevant for this call. In reality, if the missed scan is somehow called BEFORE `registry.upsert_delta` (e.g., under a future refactor), PII would not be guarded. The design is safe now but fragile to ordering changes.

---

### IN-03: `test_perf_latency.py` asserts `result[0] != _INDONESIAN_LEGAL_FIXTURE` as a proxy for "redaction ran" but the assertion is too weak for the actual regression gate

**File:** `backend/tests/services/redaction/test_perf_latency.py:312-318`
**Issue:** The assertion `assert result[0] != _INDONESIAN_LEGAL_FIXTURE` (line 312) only proves the output differs from the input — it could pass if even one whitespace character changed due to UUID masking or any other text transformation, even if zero PII was redacted. The subsequent `names_anonymized >= 1` check (line 336) tightens this but only checks three PERSON entities. If spaCy degrades and stops detecting all three names but still changes something else (e.g., normalizes Unicode), the primary PERF-02 assertion would pass while the PII coverage assertion would fail with the right message. The test logic is correct overall, but the ordering (inequality check before the entity check) could produce a confusing failure message. Not a blocker.

---

_Reviewed: 2026-04-29T07:51:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
