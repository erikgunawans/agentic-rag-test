---
plan_id: "06-05"
phase: "06"
plan: 5
title: "Replace title-gen except-pass with 6-word anonymized-message template fallback"
subsystem: "backend/chat"
tags: [pii-redaction, title-gen, fallback, sse, perf-04]
status: complete
completed_at: "2026-04-29"
duration_minutes: 10

dependency_graph:
  requires: []
  provides:
    - "D-P6-12: 6-word template fallback for title-gen LLM failures"
    - "PERF-04: title/metadata generation never crashes chat loop"
  affects:
    - "backend/app/routers/chat.py (event_generator title-gen except handler)"

tech_stack:
  added: []
  patterns:
    - "nested-try/except fallback: outer except catches LLM failure, inner except prevents fallback-internal errors from crashing chat loop (NFR-3)"
    - "de-anon via mode=none: same chokepoint as LLM-success path — real values in user-facing title, surrogates never leak"

key_files:
  created: []
  modified:
    - backend/app/routers/chat.py

decisions:
  - "Fallback builds template from anonymized_message (surrogate form) and de-anons before persist + emit — mirrors LLM-success path to preserve SC#3 / SC#5 invariants"
  - "Nested try/except ensures NFR-3: if the fallback itself fails (e.g. DB down), the chat loop continues unaffected with 'New Thread' default"
  - "Off-mode (redaction_on=False): template is built from raw message (anonymized_message == real message in off-mode), de-anon skipped — SC#5 preserved"
---

# Phase 06 Plan 05: Replace title-gen except-pass with 6-word template fallback Summary

## One-liner

6-word template fallback for title-gen LLM failures using `anonymized_message.split()[:6]`, de-anonymized via `mode="none"` before DB persist and SSE emit (D-P6-12 / PERF-04).

## What Was Done

Replaced the silent `except Exception: pass` swallow in `chat.py`'s title-gen handler with a deterministic template fallback per D-P6-12. When the title-gen LLM call fails for any reason (timeout, egress block, network error, schema mismatch), the fallback:

1. Builds a 6-word stub from `anonymized_message.split()[:6]`
2. Falls back to `"New Thread"` literal if the stub is empty
3. De-anonymizes via `redaction_service.de_anonymize_text(stub, registry, mode="none")` when redaction is ON (same de-anon path as the LLM-success branch)
4. Persists the title to the DB thread row
5. Emits a `thread_title` SSE event to the frontend (parity with LLM-success path)
6. Wraps the above in a nested try/except that logs a WARNING if the fallback itself fails, but never re-raises (NFR-3 — chat loop never crashes)

### Before / After Diff

```diff
-            except Exception:
-                pass  # Non-blocking — default title stays
+            except Exception as exc:
+                # Phase 6 D-P6-12 / PERF-04: title-gen LLM failed (timeout, egress
+                # block, network, parse error). Fall back to a 6-word template
+                # built from the surrogate-form anonymized_message, de-anonymized
+                # via mode="none" so the user sees the real values.
+                logger.info(
+                    "chat.title_gen_fallback event=title_gen_fallback "
+                    "thread_id=%s error_class=%s",
+                    body.thread_id, type(exc).__name__,
+                )
+                try:
+                    stub = " ".join(anonymized_message.split()[:6])
+                    if not stub:
+                        stub = "New Thread"
+                    if redaction_on and stub != "New Thread":
+                        new_title = await redaction_service.de_anonymize_text(
+                            stub, registry, mode="none",
+                        )
+                    else:
+                        new_title = stub
+                    if new_title:
+                        client.table("threads").update(
+                            {"title": new_title}
+                        ).eq("id", body.thread_id).execute()
+                        yield f"data: {json.dumps({'type': 'thread_title', 'title': new_title, 'thread_id': body.thread_id})}\n\n"
+                except Exception as fallback_exc:
+                    logger.warning(
+                        "chat.title_gen_fallback_failed event=title_gen_fallback_failed "
+                        "thread_id=%s error_class=%s",
+                        body.thread_id, type(fallback_exc).__name__,
+                    )
```

## Acceptance Criteria Verification

| Check | Result |
|-------|--------|
| `split()[:6]` — 1 match | 1 match (line 657) |
| `"New Thread"` — >=2 matches | 4 matches (line 603, 659, 660, 672) |
| `title_gen_fallback event=` INFO log | 1 match (line 652) |
| `title_gen_fallback_failed event=` WARN log | 1 match (line 675) |
| `except Exception: pass` remaining — should be 1 (audit fire-and-forget) | 1 match |
| `mode="none"` — >=2 matches | 4 matches (lines 574, 633, 644, 662) |
| `thread_title` SSE yield — >=2 matches | 2 matches (lines 639, 670) |
| `anonymized_message` count — same or higher | Confirmed (referenced at 391, 395, 616, 657) |
| Backend imports cleanly | OK (py_compile clean + `from app.main import app` OK with .env) |

## `anonymized_message` Outer Scope Confirmation

```
391:            anonymized_message = anonymized_strings[-1]
395:            anonymized_message = body.message
```

Both assignments are in `event_generator`'s outer scope — well before the title-gen try block at line 601. T-06-05-2 threat is mitigated.

## `split()[:6]` and `title_gen_fallback` Pattern Matches

```
652:                    "chat.title_gen_fallback event=title_gen_fallback "
657:                    stub = " ".join(anonymized_message.split()[:6])
675:                        "chat.title_gen_fallback_failed event=title_gen_fallback_failed "
```

## Commits

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Replace title-gen except-pass with 6-word template fallback | 5e7d435 | backend/app/routers/chat.py |

## Deviations from Plan

None — plan executed exactly as written. The single edit target (`except Exception: pass` at original line 640-641) was replaced with the D-P6-12 template fallback block. LLM-success path (lines 600-639) is byte-identical.

## Known Stubs

None.

## Threat Flags

None. No new network endpoints, auth paths, file access patterns, or schema changes introduced. The fallback reuses existing DB update and SSE emit patterns already present in the LLM-success path.

## Self-Check: PASSED

- backend/app/routers/chat.py modified: FOUND
- Commit 5e7d435: verified via git log
- All 9 acceptance criteria: PASSED
- Backend syntax: py_compile OK
- Backend import: OK (with .env)
