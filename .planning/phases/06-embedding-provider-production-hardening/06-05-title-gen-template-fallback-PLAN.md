---
plan_id: "06-05"
title: "Replace title-gen except-pass with 6-word anonymized-message template fallback (PERF-04 D-P6-12)"
phase: "06-embedding-provider-production-hardening"
plan: 5
type: execute
wave: 2
depends_on: []
autonomous: true
files_modified:
  - backend/app/routers/chat.py
requirements: [PERF-04]
must_haves:
  truths:
    - "When the title-gen LLM call raises ANY exception (timeout, egress block, network, parse error), chat.py persists a templated title built from the first 6 words of the anonymized_message — never crashes the chat loop (NFR-3)"
    - "Template fallback formula is exactly `\" \".join(anonymized_message.split()[:6])` per D-P6-12 (verbatim)"
    - "Empty anonymized_message falls back to the literal string `\"New Thread\"` per D-P6-12"
    - "Templated title is de-anonymized through the registry via mode=\"none\" before persist + SSE emit (same de-anon pattern as the LLM-success path)"
    - "thread_title SSE event is emitted to the frontend with the de-anonymized template title (parity with LLM-success path)"
    - "Off-mode invariant (SC#5): when redaction_on=false the template path uses the raw anonymized_message (which equals the user's real message in off-mode) and skips de-anon — produces a sensible title without registry lookup"
    - "No raw PII leaks (SC#3): the template is built from `anonymized_message` (surrogate form) and then de-anonymized only through registry.lookup — same chokepoint the LLM-success path uses"
    - "Existing LLM-success path (lines 600-639) is unchanged"
  artifacts:
    - path: "backend/app/routers/chat.py"
      provides: "6-word template fallback in the except handler around the title-gen LLMProviderClient.call (replacing line 640-641 `except Exception: pass`)"
      contains: "split()[:6]"
  key_links:
    - from: "backend/app/routers/chat.py:event_generator (title-gen except handler)"
      to: "anonymized_message variable + redaction_service.de_anonymize_text(mode=\"none\")"
      via: "first-6-words template + registry de-anon"
      pattern: "split\\(\\)\\[:6\\]"
    - from: "backend/app/routers/chat.py:event_generator (title-gen except handler)"
      to: "frontend SSE consumer"
      via: "thread_title SSE event"
      pattern: "thread_title"
threat_model:
  - id: "T-06-05-1"
    description: "T-2-adjacent: template fallback string is built from anonymized_message (surrogate form by Phase 5 D-87 invariant). If anonymized_message accidentally still contains real PII (NER miss + missed-scan disabled + empty registry), the template would carry it. Severity: low because Phase 4 D-78 missed-scan + Phase 5 D-93 single-batch chokepoint both keep anonymized_message in surrogate form."
    mitigation: "The template is de-anonymized via registry.de_anonymize_text(mode=\"none\") BEFORE persistence and SSE emit (mirrors line 632-634 LLM-success path) — so the user-facing title carries real values. Cloud-LLM never sees the template (no LLM call in this branch). DB persistence + SSE emit are the only sinks; both go through the same de-anon chokepoint as the LLM-success path."
    severity: "low"
  - id: "T-06-05-2"
    description: "If anonymized_message is None / not in scope at the except site (variable initialised inside the try block), the fallback crashes."
    mitigation: "anonymized_message is bound EARLIER in event_generator (Phase 5 Plan 05-04 — established at the top of the request flow, BEFORE the title-gen try/except). Acceptance criteria includes a grep gate proving anonymized_message is defined in event_generator's outer scope, not inside the try block."
    severity: "low"
  - id: "T-06-05-3"
    description: "Empty thread_id list / empty anonymized_message — `''.split()[:6]` returns `[]` and `' '.join([])` is `''`; persisting empty title would shadow the existing 'New Thread' default."
    mitigation: "D-P6-12 explicit fallback: if the joined string is empty, use literal `\"New Thread\"`. Implementation uses an `if not stub: stub = \"New Thread\"` guard. Acceptance criteria asserts the literal string."
    severity: "low"
---

<objective>
Replace the existing `except Exception: pass` swallow at line 640-641 of `backend/app/routers/chat.py` with the D-P6-12 template-based title fallback: take the first 6 words of `anonymized_message`, de-anonymize via registry mode="none", persist + SSE-emit the result. Empty input → `"New Thread"`.

Purpose: Phase 6 deliverable 3 (PERF-04). Today, when the cloud title-gen LLM call fails (egress block, timeout, network, schema mismatch), the chat loop swallows silently and the thread keeps the default `"New Thread"` title. PERF-04 SC#3 says "title/metadata generation falls back to a templated default — failures are logged but never crash the chat loop and never leak raw PII." The 6-word formula is concrete, deterministic, and re-uses the same de-anon path the LLM-success branch uses.

Output: one block-level edit in chat.py event_generator's title-gen exception handler, plus a single line addition above the exception handler so `anonymized_message` is reachable.
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
@.planning/phases/05-chat-loop-integration-buffering-sse-status-tool-sub-agent-co/05-CONTEXT.md
@backend/app/routers/chat.py
@CLAUDE.md

<interfaces>
<!-- Existing title-gen handler (chat.py lines 599-641). Keep the LLM-success path unchanged; only modify the except handler. -->

```python
        # Auto-generate thread title on first exchange
        if full_response:
            try:
                thread_row = client.table("threads").select("title").eq("id", body.thread_id).single().execute()
                if thread_row.data and thread_row.data["title"] == "New Thread":
                    # Phase 5 D-96: title-gen migrates to LLMProviderClient.
                    # When redaction ON: re-anonymize full_response for title LLM
                    # input (full_response is REAL form here after de-anon in Step 2).
                    if redaction_on:
                        anon_for_title = await redaction_service.redact_text_batch(
                            [full_response], registry,
                        )
                        title_input = anon_for_title[0]
                    else:
                        title_input = full_response
                    title_messages = [
                        {"role": "system", "content": "Generate a short title (max 6 words) for this chat conversation. Respond with ONLY the title text, no quotes, no punctuation at the end. If the message is in Indonesian, generate the title in Indonesian."},
                        {"role": "user", "content": anonymized_message},
                        {"role": "assistant", "content": title_input},
                    ]
                    title_result = await _llm_provider_client.call(
                        feature="title_gen",
                        messages=title_messages,
                        registry=registry,
                    )
                    new_title_raw = (
                        title_result.get("title")
                        or title_result.get("content")
                        or title_result.get("raw")
                        or ""
                    ).strip().strip('"\'')[:80]
                    # D-96: de-anon the LLM-emitted title BEFORE both persist and emit.
                    if redaction_on and new_title_raw:
                        new_title = await redaction_service.de_anonymize_text(
                            new_title_raw, registry, mode="none",
                        )
                    else:
                        new_title = new_title_raw
                    if new_title:
                        client.table("threads").update({"title": new_title}).eq("id", body.thread_id).execute()
                        yield f"data: {json.dumps({'type': 'thread_title', 'title': new_title, 'thread_id': body.thread_id})}\n\n"
            except Exception:
                pass  # Non-blocking — default title stays
```

<!-- Variables already in event_generator outer scope (per Phase 5 Plan 05-04):
     - anonymized_message: str  (anonymized form of body.message)
     - redaction_on: bool
     - registry: ConversationRegistry | None  (None when redaction_on=False)
     - redaction_service: RedactionService
     - client: Supabase client
     - body.thread_id, full_response
     - logger (module-level)
-->
```
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Replace except-pass with 6-word template fallback in chat.py title-gen handler</name>
  <read_first>
    - backend/app/routers/chat.py (lines 1-50 imports + lines 599-641 title-gen block; verify `import logging` is present and a module-level logger exists; if no logger, the new code uses `import logging; logger = logging.getLogger(__name__)` already established)
    - .planning/phases/06-embedding-provider-production-hardening/06-CONTEXT.md (D-P6-12 verbatim — formula is `" ".join(anonymized_message.split()[:6])`; empty fallback is `"New Thread"`)
    - .planning/phases/05-chat-loop-integration-buffering-sse-status-tool-sub-agent-co/05-CONTEXT.md (D-90 graceful-degrade pattern — `mode="none"` for de-anon in degraded paths; D-96 title-gen wiring chokepoint)
    - backend/app/services/redaction_service.py (lines 814-935 — de_anonymize_text signature; verify `mode="none"` is the no-fuzzy default the LLM-success path uses)
    - backend/app/routers/chat.py (search for `anonymized_message =` to confirm it is bound in event_generator outer scope, NOT inside the title-gen try block)
  </read_first>
  <files>backend/app/routers/chat.py</files>
  <action>
Locate the existing block at lines 640-641:

```python
            except Exception:
                pass  # Non-blocking — default title stays
```

Replace those 2 lines with the following block. Indent the new block to match the existing 12-space indent (inside `if full_response:` -> `try:` ... `except Exception as e:`):

```python
            except Exception as exc:
                # Phase 6 D-P6-12 / PERF-04: title-gen LLM failed (timeout, egress
                # block, network, parse error). Fall back to a 6-word template
                # built from the surrogate-form anonymized_message, de-anonymized
                # via mode="none" so the user sees the real values.
                #
                # Why anonymized_message: this branch runs without any cloud-LLM
                # contact, so we still anchor the template on the surrogate-form
                # text and then de-anon through the registry chokepoint — same
                # privacy invariant as the LLM-success path (no raw PII through
                # any LLM; user-facing title carries real values).
                logger.info(
                    "chat.title_gen_fallback event=title_gen_fallback "
                    "thread_id=%s error_class=%s",
                    body.thread_id, type(exc).__name__,
                )
                try:
                    stub = " ".join(anonymized_message.split()[:6])
                    if not stub:
                        stub = "New Thread"
                    if redaction_on and stub != "New Thread":
                        new_title = await redaction_service.de_anonymize_text(
                            stub, registry, mode="none",
                        )
                    else:
                        new_title = stub
                    if new_title:
                        client.table("threads").update(
                            {"title": new_title}
                        ).eq("id", body.thread_id).execute()
                        yield f"data: {json.dumps({'type': 'thread_title', 'title': new_title, 'thread_id': body.thread_id})}\n\n"
                except Exception as fallback_exc:
                    # NFR-3: never re-raise to the chat loop. Default "New Thread"
                    # stays — thread is still functional, just untitled.
                    logger.warning(
                        "chat.title_gen_fallback_failed event=title_gen_fallback_failed "
                        "thread_id=%s error_class=%s",
                        body.thread_id, type(fallback_exc).__name__,
                    )
```

Do NOT touch the LLM-success path (lines 600-639) — leave that block byte-identical.

Do NOT change the outer `try:` at line 601 — only the `except Exception:` at line 640 changes.

Do NOT add `anonymized_message` to function arguments or extract it from the try block — it is already bound in the outer event_generator scope (Phase 5 Plan 05-04 invariant). Verify with grep before editing.

Do NOT introduce a new dependency or import; `logging` and `json` are already imported at the top of chat.py. If a module-level `logger = logging.getLogger(__name__)` does NOT exist, ADD it after the existing import block (single line: `logger = logging.getLogger(__name__)`).
  </action>
  <verify>
    <automated>cd backend &amp;&amp; python -c "from app.main import app; print('OK')" &amp;&amp; cd backend &amp;&amp; source venv/bin/activate &amp;&amp; pytest tests/unit -v --tb=short -q 2>&amp;1 | tail -5</automated>
  </verify>
  <acceptance_criteria>
    - `grep -nE 'split\(\)\[:6\]' backend/app/routers/chat.py` returns exactly 1 match
    - `grep -nE '"New Thread"' backend/app/routers/chat.py` returns at least 2 matches (the existing default check at line 603 + the new fallback literal)
    - `grep -nE "title_gen_fallback event=title_gen_fallback" backend/app/routers/chat.py` returns at least 1 match (new INFO-level log line)
    - `grep -nE "title_gen_fallback_failed event=title_gen_fallback_failed" backend/app/routers/chat.py` returns at least 1 match (nested-failure WARN log line)
    - Pre-edit baseline: `grep -nA1 "except Exception:" backend/app/routers/chat.py | grep -c "^[0-9]*-\s*pass"` returns 2 (line 324 audit fire-and-forget + line 641 title-gen). Post-edit: same gate returns exactly 1 (only the audit fire-and-forget at line 324 remains; title-gen `pass` is replaced). Use this command verbatim — `grep -nA1` annotates the line that follows each match with a `<linenum>-` prefix; the inner grep then counts only `pass`-as-first-non-whitespace lines that immediately follow `except Exception:`.
    - `grep -cE "anonymized_message" backend/app/routers/chat.py` returns the SAME or HIGHER count than before — the variable is referenced more often, never less
    - `grep -nE 'mode="none"' backend/app/routers/chat.py` returns at least 2 matches (existing line 633 LLM-success path + new fallback path)
    - `grep -nE "yield f\"data: \{json\.dumps\(\{'type': 'thread_title'" backend/app/routers/chat.py` returns at least 2 matches (LLM-success path + fallback path emit thread_title)
    - `cd backend &amp;&amp; python -c "from app.main import app; print('OK')"` prints `OK`
    - `cd backend &amp;&amp; source venv/bin/activate &amp;&amp; pytest tests/unit -v --tb=short -q 2>&amp;1 | grep -E "passed|failed" | tail -1` shows pre-existing tests still passing (this plan adds no new tests; PERF-04 tests in Plan 06-07)
  </acceptance_criteria>
  <done>except-pass replaced with template fallback that builds 6-word stub, de-anons via mode="none", persists, and emits SSE thread_title; nested fallback try/except prevents the chat loop from crashing on a fallback-internal error (NFR-3); backend imports cleanly; existing tests pass.</done>
</task>

</tasks>

<verification>
1. `cd backend && python -c "from app.main import app; print('OK')"` — backend imports cleanly (PostToolUse hook also runs this).
2. `grep -nE "split\(\)\[:6\]" backend/app/routers/chat.py` — confirms the 6-word formula is present (D-P6-12 verbatim invariant).
3. `cd backend && source venv/bin/activate && pytest tests/unit -v --tb=short -q 2>&1 | tail -10` — all pre-existing 195+ unit tests still pass (no behavioural change to non-failure paths).
4. `cd backend && source venv/bin/activate && pytest tests/api -v --tb=short -q -k "phase5" 2>&1 | tail -5` — Phase 5 chat integration tests still pass (the LLM-success branch is unchanged).
</verification>

<success_criteria>
- The literal `except Exception: pass` swallow in the title-gen handler is replaced
- New fallback uses `" ".join(anonymized_message.split()[:6])` per D-P6-12 verbatim
- Empty stub falls back to `"New Thread"`
- Fallback de-anons stub via `redaction_service.de_anonymize_text(stub, registry, mode="none")` when redaction_on
- Fallback persists title to DB AND emits `thread_title` SSE event (parity with LLM-success path)
- Nested try/except inside the fallback ensures NFR-3 (chat loop never crashes)
- INFO-level log line emitted with thread_id + error_class on the fallback firing
- WARNING-level log line emitted if the fallback itself fails
- All pre-existing tests still pass
- Backend imports cleanly
</success_criteria>

<output>
After completion, create `.planning/phases/06-embedding-provider-production-hardening/06-05-SUMMARY.md` documenting:
- Verbatim diff of the title-gen except handler (before / after)
- Confirmation that `anonymized_message` is in event_generator outer scope (`grep -nE "^\s+anonymized_message\s*=" backend/app/routers/chat.py`)
- Output of `grep -nE "split\(\)\[:6\]|title_gen_fallback" backend/app/routers/chat.py` showing the 2-3 expected matches
- Confirmation `pytest tests/unit -v` still shows pre-plan passing-count
</output>
</content>
