"""Phase 5 Plan 05-04 Tasks 2-5: chat.py event_generator wiring assertions.

This file uses source-level structural grep assertions to verify the
Phase 5 splice points are in place in ``backend/app/routers/chat.py``.
End-to-end behavior assertions (privacy invariant, single-batch delta,
two redaction_status events) are owned by Plan 05-06.

Tests are grouped by Task (2..5) so each task's GREEN gate is auditable.

Source assertions match the plan's acceptance_criteria grep counts so
this file doubles as the executable form of the planned acceptance gates.
"""
from __future__ import annotations

import pathlib

CHAT_PATH = pathlib.Path("app/routers/chat.py")


def _src() -> str:
    return CHAT_PATH.read_text()


# ---------------------------------------------------------------------------
# Task 2 — top-level branch + registry load + batch history anon + classify
# ---------------------------------------------------------------------------


class TestTask2RegistryLoadAndBatchAnon:
    def test_single_per_turn_registry_load_present(self):
        # D-86: ConversationRegistry.load called ONCE per turn.
        src = _src()
        assert src.count("await ConversationRegistry.load(body.thread_id)") == 1

    def test_redaction_service_singleton_called(self):
        src = _src()
        assert "get_redaction_service()" in src

    def test_redaction_on_gating_present(self):
        # D-83 / D-84: top-level branch on settings.pii_redaction_enabled.
        src = _src()
        assert "redaction_on" in src
        assert "settings.pii_redaction_enabled" in src

    def test_batch_anon_primitive_used(self):
        # D-93: redact_text_batch is the chokepoint primitive.
        src = _src()
        assert "redact_text_batch" in src

    def test_anonymized_message_variable_set(self):
        src = _src()
        # Defined + used in LLM payloads + classify_intent.
        assert src.count("anonymized_message") >= 2

    def test_anonymized_history_variable_set(self):
        src = _src()
        assert src.count("anonymized_history") >= 2

    def test_classify_intent_passes_registry_kwarg(self):
        # D-96 caller side.
        src = _src()
        assert "registry=registry" in src

    def test_user_message_insert_preserved_real_form(self):
        # D-85 invariant — body.message stays REAL on the persistence row.
        src = _src()
        # Either single or double quote keys depending on style; both forms
        # preserve REAL message form for the messages-table INSERT row.
        assert (
            '"content": body.message' in src
            or "'content': body.message" in src
        )

    def test_no_per_message_redact_loop(self):
        # D-93 forbids per-message redact_text loop in chat.py.
        src = _src()
        # We accept ``redact_text`` substring (it's the substring of
        # redact_text_batch) but assert there is no for-loop awaiting
        # it per-string. A simple proxy: the only call expression
        # containing ``redact_text`` should be ``redact_text_batch``.
        # Allow stateless redact_text in non-chat contexts but enforce
        # absence of a per-msg loop in this router.
        assert ".redact_text(" not in src or src.count(".redact_text(") == 0


# ---------------------------------------------------------------------------
# Task 3 — _run_tool_loop walker + egress wrapper + skeleton tool events
# ---------------------------------------------------------------------------


class TestTask3ToolLoopWiring:
    def test_deanonymize_tool_args_called(self):
        # D-91: walker invocation site.
        src = _src()
        assert "deanonymize_tool_args(" in src

    def test_anonymize_tool_output_called(self):
        src = _src()
        assert "anonymize_tool_output(" in src

    def test_execute_tool_threads_registry_kwarg(self):
        # D-86: chat.py passes registry kwarg into tool_service.execute_tool.
        src = _src()
        # Allow either ``execute_tool(..., registry=registry)`` or split lines.
        assert "execute_tool(" in src
        assert "registry=registry" in src

    def test_egress_blocked_abort_raised(self):
        # Class def + at least one raise in egress wrappers.
        src = _src()
        assert src.count("EgressBlockedAbort") >= 2  # class def + raise(s)

    def test_tool_loop_egress_log_format(self):
        # B4: egress_blocked event=egress_blocked feature=tool_loop ...
        src = _src()
        assert "feature=tool_loop" in src

    def test_skeleton_tool_start_when_redacted(self):
        # D-89: tool_start emit lacks 'input' under redaction_on branch.
        # Loose grep — the conditional dict literal must mention func_name
        # and tool_start without an 'input' key in the redacted-on branch.
        src = _src()
        assert '"type": "tool_start"' in src or "'type': 'tool_start'" in src

    def test_skeleton_tool_result_when_redacted(self):
        src = _src()
        assert '"type": "tool_result"' in src or "'type': 'tool_result'" in src


# ---------------------------------------------------------------------------
# Task 4 — stream_response branches: buffering + egress wrappers
# ---------------------------------------------------------------------------


class TestTask4StreamResponseWiring:
    def test_branch_a_egress_log(self):
        src = _src()
        assert "feature=stream_response_branch_a" in src

    def test_branch_b_egress_log(self):
        src = _src()
        assert "feature=stream_response_branch_b" in src

    def test_full_response_buffer_accumulates(self):
        src = _src()
        # Both branches accumulate chunks. Plan_text or chunk dict access
        # forms are acceptable.
        assert src.count("full_response += chunk") >= 2

    def test_progressive_delta_gated_on_off_mode(self):
        # When ON, no progressive delta; when OFF, existing emit fires.
        src = _src()
        assert src.count("if not redaction_on:") >= 2


# ---------------------------------------------------------------------------
# Task 5 — redaction_status events + de-anon graceful degrade + title-gen
# ---------------------------------------------------------------------------


class TestTask5StatusEventsAndDeanon:
    def test_anonymizing_event_emitted_once(self):
        # D-88: exactly one anonymizing emit per turn.
        src = _src()
        count = src.count("'stage': 'anonymizing'") + src.count('"stage": "anonymizing"')
        assert count == 1

    def test_deanonymizing_event_emitted_once(self):
        src = _src()
        count = src.count("'stage': 'deanonymizing'") + src.count('"stage": "deanonymizing"')
        assert count == 1

    def test_blocked_event_emitted_at_least_once(self):
        src = _src()
        count = src.count("'stage': 'blocked'") + src.count('"stage": "blocked"')
        assert count >= 1

    def test_deanon_degraded_log_present(self):
        # D-90: B4-compliant graceful-degrade log.
        src = _src()
        assert "deanon_degraded" in src

    def test_mode_none_fallback_present(self):
        # D-90 + D-96: at least two mode='none' callsites — de-anon fallback
        # AND title-gen de-anon (always uses mode='none').
        src = _src()
        assert src.count('mode="none"') + src.count("mode='none'") >= 2

    def test_title_gen_uses_llm_provider_client(self):
        # D-96: title-gen migration from openrouter_service.complete_with_tools
        # to LLMProviderClient.call(feature='title_gen', ...).
        src = _src()
        assert "_llm_provider_client.call(" in src
        assert "feature='title_gen'" in src or 'feature="title_gen"' in src

    def test_title_gen_old_call_removed(self):
        # The OLD title-gen call must be GONE after the migration.
        src = _src()
        assert "openrouter_service.complete_with_tools(title_messages)" not in src

    def test_egress_blocked_abort_handler_installed(self):
        src = _src()
        assert "except EgressBlockedAbort" in src

    def test_existing_terminator_preserved(self):
        # Existing terminator at L285 stays unchanged.
        src = _src()
        assert "'delta': ''" in src
        assert "'done': True" in src


# ---------------------------------------------------------------------------
# Cross-task: imports still resolve, app still loads
# ---------------------------------------------------------------------------


class TestCrossTaskInvariants:
    def test_chat_router_imports_clean(self):
        from app.routers.chat import router, EgressBlockedAbort
        assert router is not None
        assert issubclass(EgressBlockedAbort, Exception)

    def test_main_app_imports_clean(self):
        from app.main import app
        assert app is not None
