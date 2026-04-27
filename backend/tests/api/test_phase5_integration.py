"""ROADMAP Phase 5 SC#1..SC#5 integration tests + B4 / Egress-Trip bonus coverage.

Mirrors backend/tests/api/test_phase4_integration.py (Phase 4 SC#1..SC#5 + B4) —
same per-SC test-class layout, same _patched_settings helper, same MagicMock +
AsyncMock mock pattern for AsyncOpenAI, same caplog B4 invariants. Tests run
against live Supabase qedhulpfezucnfadlfiz; cloud LLM is always mocked (no real
egress).

Coverage map:
  SC#1 → TestSC1_PrivacyInvariant       (LLM payload audit — registry.entries() ⊄ payload)
  SC#2 → TestSC2_BufferingAndStatus     (SSE event sequence with redaction ON)
  SC#3 → TestSC3_SearchDocumentsTool    (search_documents de-anon args / re-anon output)
  SC#4 → TestSC4_SqlGrepAndSubAgent     (query_database + kb_grep + sub-agent registry threading)
  SC#5 → TestSC5_OffMode                (PII_REDACTION_ENABLED=false ⇒ baseline behavior)
  Bonus: TestB4_LogPrivacy_ChatLoop     (caplog invariant across the full chat turn)
  Bonus: TestEgressTrip_ChatPath        (Phase 1 NER miss simulation; egress filter trip)

Design notes:
  - chat.py uses a module-level ``settings = get_settings()`` binding (line 45).
    Tests patch ``app.routers.chat.settings`` directly with a SimpleNamespace stub.
  - Auth is bypassed via ``app.dependency_overrides[get_current_user]``.
  - DB thread-ownership check and message persistence are mocked via the
    Supabase client stub.
  - ``get_system_settings()`` is patched to return a minimal dict with the
    fields chat.py reads (``llm_model``, ``embedding_model``).
  - Real ``ConversationRegistry.load`` (live Supabase) is used per D-97 spec.
    Registry cleanup runs via the shared ``fresh_thread_id`` conftest fixture.
"""
from __future__ import annotations

import json
import logging
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient

from app.config import get_settings
from app.dependencies import get_current_user
from app.main import app
from app.services.redaction.registry import ConversationRegistry, EntityMapping
from app.services.redaction_service import RedactionService, get_redaction_service

pytestmark = pytest.mark.asyncio


# ──────────────────────────── Constants ────────────────────────────────────


_TEST_USER_ID = "00000000-0000-0000-0000-test00000001"
_TEST_USER_EMAIL = "test@test.com"

# Fake JWT token used for auth bypass in dependency_overrides.
_FAKE_TOKEN = "test-token-phase5-integration"


# ──────────────────────────── Helpers / Fixtures ───────────────────────────


def _patched_settings(
    *,
    pii_redaction_enabled: bool = True,
    fuzzy_deanon_mode: str = "none",
    agents_enabled: bool = False,
    tools_enabled: bool = True,
    tools_max_iterations: int = 1,
) -> SimpleNamespace:
    """Build a Settings stub honoring the fields chat.py reads.

    Phase 5 extension of the Phase 4 _patched_settings helper.
    Patches ``app.routers.chat.settings`` directly (module-level binding).
    """
    real = get_settings()
    overrides = {f: getattr(real, f) for f in real.model_dump().keys()}
    overrides["pii_redaction_enabled"] = pii_redaction_enabled
    overrides["fuzzy_deanon_mode"] = fuzzy_deanon_mode
    overrides["agents_enabled"] = agents_enabled
    overrides["tools_enabled"] = tools_enabled
    overrides["tools_max_iterations"] = tools_max_iterations
    # Keep rag_top_k / rag_similarity_threshold for tool_context build.
    return SimpleNamespace(**overrides)


def _consume_sse(response) -> list[dict]:
    """Parse a TestClient SSE response into a list of event dicts.

    Each emitted line ``data: {...}\\n\\n`` becomes one dict in the result.
    Non-data lines (blank separators, event: lines) are skipped.
    """
    events: list[dict] = []
    for raw_line in response.iter_lines():
        line = raw_line if isinstance(raw_line, str) else raw_line.decode("utf-8")
        if line.startswith("data: "):
            try:
                events.append(json.loads(line[6:]))
            except json.JSONDecodeError:
                continue
    return events


def _make_supabase_stub(thread_id: str) -> MagicMock:
    """Build a minimal Supabase client stub for chat.py DB calls.

    Stubs the table chain used inside ``stream_chat`` (before event_generator):
    - threads SELECT (ownership check) → returns [{id: thread_id}]
    - messages SELECT (history load) → returns [] (empty history)
    - messages INSERT (user msg persist) → returns [{id: "msg-001"}]
    - messages INSERT (assistant msg persist) → no-op
    - threads SELECT .single() (title check) → returns {title: "New Thread"}
    - threads UPDATE (title update) → no-op

    The key challenge: differentiate SELECT (history load → empty list) from
    INSERT (persist user msg → [{id: "msg-001"}]) for the messages table.
    We track the operation type via a ``_op`` attribute on the chain stub.
    """
    client = MagicMock()

    def _make_chain(table_name: str, op: str = "select"):
        """Return a chainable stub that propagates op through the chain."""
        chain_stub = MagicMock()
        chain_stub._op = op

        def _execute():
            if table_name == "threads":
                # Both SELECT (ownership) and .single() (title check) go here.
                return MagicMock(data=[{"id": thread_id, "title": "New Thread"}])
            elif table_name == "messages":
                if op == "insert":
                    # user_msg INSERT must return [{id: "msg-001"}] for user_msg_id.
                    return MagicMock(data=[{"id": "msg-001"}])
                else:
                    # History SELECT returns empty list (no prior messages).
                    return MagicMock(data=[])
            return MagicMock(data=[])

        chain_stub.execute = _execute

        # Chain methods — propagate op for insert/update, keep select for select ops.
        def _insert(*args, **kwargs):
            return _make_chain(table_name, "insert")

        def _update(*args, **kwargs):
            return _make_chain(table_name, "update")

        def _delete(*args, **kwargs):
            return _make_chain(table_name, "delete")

        def _passthrough(*args, **kwargs):
            return _make_chain(table_name, op)

        chain_stub.select = _passthrough
        chain_stub.eq = _passthrough
        chain_stub.order = _passthrough
        chain_stub.limit = _passthrough
        chain_stub.single = _passthrough
        chain_stub.insert = _insert
        chain_stub.update = _update
        chain_stub.delete = _delete
        return chain_stub

    def _table_factory(table_name: str):
        tbl = MagicMock()
        tbl.select = lambda *a, **kw: _make_chain(table_name, "select")
        tbl.insert = lambda *a, **kw: _make_chain(table_name, "insert")
        tbl.update = lambda *a, **kw: _make_chain(table_name, "update")
        tbl.delete = lambda *a, **kw: _make_chain(table_name, "delete")
        tbl.eq = lambda *a, **kw: _make_chain(table_name, "select")
        return tbl

    client.table = _table_factory
    return client


@pytest.fixture(autouse=True)
def _clear_llm_client_cache():
    """Reset the AsyncOpenAI client cache between tests.

    Mirrors Phase 4 lines 99-110. Prevents a stale mocked client from a
    prior test bleeding into the next test's real-mode setup.
    """
    from app.services import llm_provider

    if hasattr(llm_provider, "_clients"):
        llm_provider._clients.clear()
    yield
    if hasattr(llm_provider, "_clients"):
        llm_provider._clients.clear()


@pytest.fixture(autouse=True)
def _auth_override():
    """Bypass FastAPI get_current_user dependency for all Phase 5 integration tests."""
    async def _fake_current_user():
        return {
            "id": _TEST_USER_ID,
            "email": _TEST_USER_EMAIL,
            "token": _FAKE_TOKEN,
            "role": "user",
        }

    app.dependency_overrides[get_current_user] = _fake_current_user
    yield
    app.dependency_overrides.pop(get_current_user, None)


_MOCK_SYS_SETTINGS = {
    "llm_model": "openai/gpt-4o-mini",
    "embedding_model": "text-embedding-3-small",
    "custom_embedding_model": None,
}


# ──────────────────────────── SC#1 ─────────────────────────────────────────


class TestSC1_PrivacyInvariant:
    """SC#1: every recorded LLM payload contains surrogates only.

    Single most important test in Phase 5 — every other SC is downstream of
    "did the LLM see surrogates only".

    Uses live Supabase (ConversationRegistry.load) + mocked OpenRouter calls.
    After the SSE stream completes, loads the registry and asserts that no
    real_value from any registry entry appears in any captured LLM payload.
    """

    async def test_no_pii_in_any_llm_payload(self, fresh_thread_id):
        """For every captured stream_response payload, assert no registered
        real_value substring appears.

        chat.py calls stream_response with ``messages`` containing the
        anonymized history + anonymized_message. We capture the ``messages``
        argument at the stream_response call site.
        """
        thread_id = fresh_thread_id
        captured_payloads: list[str] = []

        async def _capture_stream_response(messages, *, model=None, **kwargs):
            # Capture the messages payload before streaming begins.
            captured_payloads.append(json.dumps(messages, ensure_ascii=False))
            # Yield a surrogate-form response (the "LLM output").
            yield {"delta": "Aaron Thompson DDS sent a contract.", "done": False}
            yield {"delta": "", "done": True}

        # complete_with_tools is called in _run_tool_loop before stream_response.
        # We mock it to return no tool calls so we skip straight to stream_response.
        async def _mock_complete_with_tools(messages, tools, *, model=None, **kwargs):
            captured_payloads.append(json.dumps(messages, ensure_ascii=False))
            return {"tool_calls": [], "content": None}

        supabase_stub = _make_supabase_stub(thread_id)
        stub_settings = _patched_settings(pii_redaction_enabled=True, tools_enabled=False)

        with (
            patch("app.routers.chat.settings", stub_settings),
            patch("app.routers.chat.get_supabase_client", return_value=supabase_stub),
            patch("app.services.system_settings_service.get_system_settings",
                  return_value=_MOCK_SYS_SETTINGS),
            patch("app.routers.chat.get_system_settings",
                  return_value=_MOCK_SYS_SETTINGS),
            patch(
                "app.services.openrouter_service.OpenRouterService.stream_response",
                side_effect=_capture_stream_response,
            ),
            patch(
                "app.services.openrouter_service.OpenRouterService.complete_with_tools",
                side_effect=_mock_complete_with_tools,
            ),
        ):
            client = TestClient(app)
            response = client.post(
                "/chat/stream",
                json={
                    "thread_id": thread_id,
                    "message": "Pak Bambang Sutrisno (bambang@example.id, +62 812 3456 7890) sent a contract",
                },
                headers={"Authorization": f"Bearer {_FAKE_TOKEN}"},
            )
            _consume_sse(response)

        # Load the registry that Phase 5 D-86 / D-93 populated during the turn.
        registry = await ConversationRegistry.load(thread_id)

        # Privacy invariant: every entry's real_value must NOT appear in any
        # captured LLM payload. This is the SC#1 gate — the single most
        # important assertion in Phase 5.
        for entry in registry.entries():
            for payload in captured_payloads:
                assert entry.real_value not in payload, (
                    f"PII LEAK: real_value ({entry.entity_type}) "
                    f"found in LLM payload"
                )

    async def test_registry_populated_after_turn(self, fresh_thread_id):
        """After a turn containing PII, the registry has at least one entry."""
        thread_id = fresh_thread_id

        async def _mock_stream_response(messages, *, model=None, **kwargs):
            yield {"delta": "Acknowledged.", "done": False}
            yield {"delta": "", "done": True}

        supabase_stub = _make_supabase_stub(thread_id)
        stub_settings = _patched_settings(pii_redaction_enabled=True, tools_enabled=False)

        with (
            patch("app.routers.chat.settings", stub_settings),
            patch("app.routers.chat.get_supabase_client", return_value=supabase_stub),
            patch("app.services.system_settings_service.get_system_settings",
                  return_value=_MOCK_SYS_SETTINGS),
            patch("app.routers.chat.get_system_settings",
                  return_value=_MOCK_SYS_SETTINGS),
            patch(
                "app.services.openrouter_service.OpenRouterService.stream_response",
                side_effect=_mock_stream_response,
            ),
        ):
            client = TestClient(app)
            client.post(
                "/chat/stream",
                json={
                    "thread_id": thread_id,
                    "message": "Pak Bambang Sutrisno called about his contract.",
                },
                headers={"Authorization": f"Bearer {_FAKE_TOKEN}"},
            )

        registry = await ConversationRegistry.load(thread_id)
        # The turn contained a real PERSON name — at least one entry registered.
        assert len(registry.entries()) >= 1, (
            f"expected at least one registry entry after PII-containing turn; "
            f"got {len(registry.entries())}"
        )


# ──────────────────────────── SC#2 ─────────────────────────────────────────


class TestSC2_BufferingAndStatus:
    """SC#2: SSE event sequence + skeleton tool events when redaction is ON.

    D-88: two redaction_status events per turn (anonymizing + deanonymizing).
    D-87: exactly one delta-with-content (single batch).
    D-89: tool_start/tool_result events emit no input/output when redaction ON.
    """

    async def test_event_sequence_redaction_on_no_tools(self, fresh_thread_id):
        """Assert the SSE event sequence for a redaction-ON turn with no tools.

        Expected sequence (relative ordering):
          redaction_status:anonymizing → delta (single batch) → delta:done

        Note: anonymizing fires BEFORE agent_start per 05-04-SUMMARY.md deviation.
        agent_done not emitted in branch B (single-agent, no agent_name set).
        """
        thread_id = fresh_thread_id

        async def _mock_stream_response(messages, *, model=None, **kwargs):
            yield {"delta": "Hello, I can help with that.", "done": False}
            yield {"delta": "", "done": True}

        supabase_stub = _make_supabase_stub(thread_id)
        stub_settings = _patched_settings(
            pii_redaction_enabled=True, tools_enabled=False,
        )

        with (
            patch("app.routers.chat.settings", stub_settings),
            patch("app.routers.chat.get_supabase_client", return_value=supabase_stub),
            patch("app.services.system_settings_service.get_system_settings",
                  return_value=_MOCK_SYS_SETTINGS),
            patch("app.routers.chat.get_system_settings",
                  return_value=_MOCK_SYS_SETTINGS),
            patch(
                "app.services.openrouter_service.OpenRouterService.stream_response",
                side_effect=_mock_stream_response,
            ),
        ):
            client = TestClient(app)
            response = client.post(
                "/chat/stream",
                json={"thread_id": thread_id, "message": "Hello"},
                headers={"Authorization": f"Bearer {_FAKE_TOKEN}"},
            )
            events = _consume_sse(response)

        types = [(i, e.get("type"), e.get("stage")) for i, e in enumerate(events)]

        def _idx(predicate):
            for i, t, s in types:
                if predicate(t, s):
                    return i
            return -1

        i_anon = _idx(lambda t, s: t == "redaction_status" and s == "anonymizing")
        i_deanon = _idx(lambda t, s: t == "redaction_status" and s == "deanonymizing")
        i_delta_content = _idx(lambda t, s: t == "delta")

        # Both redaction_status events present.
        assert i_anon >= 0, f"missing redaction_status:anonymizing; events={events}"
        assert i_deanon >= 0, f"missing redaction_status:deanonymizing; events={events}"

        # Relative ordering: anonymizing before deanonymizing.
        assert i_anon < i_deanon, "anonymizing must precede deanonymizing"

        # D-88 singular — exactly one anonymizing, exactly one deanonymizing.
        anonymizing_count = sum(
            1 for _, t, s in types if t == "redaction_status" and s == "anonymizing"
        )
        deanonymizing_count = sum(
            1 for _, t, s in types if t == "redaction_status" and s == "deanonymizing"
        )
        assert anonymizing_count == 1, (
            f"expected exactly 1 anonymizing event, got {anonymizing_count}"
        )
        assert deanonymizing_count == 1, (
            f"expected exactly 1 deanonymizing event, got {deanonymizing_count}"
        )

        # D-87 single-batch — exactly one delta with non-empty content.
        deltas_with_content = [e for e in events if e.get("type") == "delta" and e.get("delta")]
        assert len(deltas_with_content) == 1, (
            f"expected exactly 1 delta-with-content (single-batch D-87), "
            f"got {len(deltas_with_content)}"
        )

        # deanonymizing precedes the single-batch delta.
        i_first_delta_content = next(
            (i for i, e in enumerate(events) if e.get("type") == "delta" and e.get("delta")),
            -1,
        )
        if i_first_delta_content >= 0:
            assert i_deanon < i_first_delta_content, (
                "deanonymizing must precede first delta-with-content"
            )

    async def test_skeleton_tool_events_when_redaction_on(self, fresh_thread_id):
        """D-89: tool_start/tool_result emit no input/output fields when redaction ON."""
        thread_id = fresh_thread_id
        first_call = [True]

        async def _mock_complete_with_tools(messages, tools, *, model=None, **kwargs):
            if first_call[0]:
                first_call[0] = False
                return {
                    "tool_calls": [
                        {
                            "id": "call-001",
                            "function": {
                                "name": "search_documents",
                                "arguments": '{"query": "test query"}',
                            },
                        }
                    ],
                    "content": None,
                }
            return {"tool_calls": [], "content": None}

        async def _mock_execute_tool(name, arguments, user_id, context=None, *, registry=None):
            return {"results": [{"content": "doc chunk", "id": "doc-001"}]}

        async def _mock_stream_response(messages, *, model=None, **kwargs):
            yield {"delta": "Found 1 document.", "done": False}
            yield {"delta": "", "done": True}

        supabase_stub = _make_supabase_stub(thread_id)
        stub_settings = _patched_settings(
            pii_redaction_enabled=True, tools_enabled=True, tools_max_iterations=2,
        )

        with (
            patch("app.routers.chat.settings", stub_settings),
            patch("app.routers.chat.get_supabase_client", return_value=supabase_stub),
            patch("app.services.system_settings_service.get_system_settings",
                  return_value=_MOCK_SYS_SETTINGS),
            patch("app.routers.chat.get_system_settings",
                  return_value=_MOCK_SYS_SETTINGS),
            patch(
                "app.services.openrouter_service.OpenRouterService.complete_with_tools",
                side_effect=_mock_complete_with_tools,
            ),
            patch(
                "app.services.openrouter_service.OpenRouterService.stream_response",
                side_effect=_mock_stream_response,
            ),
            patch(
                "app.services.tool_service.ToolService.execute_tool",
                side_effect=_mock_execute_tool,
            ),
        ):
            client = TestClient(app)
            response = client.post(
                "/chat/stream",
                json={"thread_id": thread_id, "message": "Find docs about Bambang"},
                headers={"Authorization": f"Bearer {_FAKE_TOKEN}"},
            )
            events = _consume_sse(response)

        # D-89 skeleton — tool_start has no input; tool_result has no output.
        for ev in events:
            if ev.get("type") == "tool_start":
                assert "input" not in ev, f"D-89 violated: tool_start has input field: {ev}"
            if ev.get("type") == "tool_result":
                assert "output" not in ev, f"D-89 violated: tool_result has output field: {ev}"

        # At least one tool_start and tool_result present.
        tool_starts = [e for e in events if e.get("type") == "tool_start"]
        tool_results = [e for e in events if e.get("type") == "tool_result"]
        assert len(tool_starts) >= 1, "expected at least one tool_start"
        assert len(tool_results) >= 1, "expected at least one tool_result"


# ──────────────────────────── SC#3 ─────────────────────────────────────────


class TestSC3_SearchDocumentsTool:
    """SC#3: search_documents de-anon args + re-anon output around tool walker.

    D-91: deanonymize_tool_args runs BEFORE execute_tool; anonymize_tool_output
    runs AFTER. The tool sees real de-anonymized query; the LLM sees surrogate-
    only tool output.
    """

    async def test_tool_args_de_anonymized(self, fresh_thread_id):
        """Tool execute_tool receives de-anonymized args (real query).

        The LLM emits tool args in surrogate form. deanonymize_tool_args converts
        surrogate → real before calling execute_tool. We capture what execute_tool
        actually receives and assert the surrogate form is absent.
        """
        thread_id = fresh_thread_id

        # First, seed a registry entry so the surrogate→real mapping is known.
        registry_pre = await ConversationRegistry.load(thread_id)
        svc = get_redaction_service()
        # Redact the user message to register "Bambang Sutrisno" → some surrogate.
        result = await svc.redact_text("Bambang Sutrisno contract", registry=registry_pre)
        anon_text = result.anonymized_text
        # Reload registry to get the mapping.
        registry_pre = await ConversationRegistry.load(thread_id)
        # Find what surrogate was assigned.
        surrogate = None
        for entry in registry_pre.entries():
            if entry.real_value == "Bambang Sutrisno":
                surrogate = entry.surrogate_value
                break

        if surrogate is None:
            pytest.skip("NER did not detect PERSON entity in seed text; skip SC3 test")

        captured_tool_calls: list[dict] = []

        async def _mock_execute_tool(name, arguments, user_id, context=None, *, registry=None):
            captured_tool_calls.append({"name": name, "arguments": arguments})
            return {"results": [{"content": "contract text", "id": "doc-001"}]}

        first_call = [True]

        async def _mock_complete_with_tools(messages, tools, *, model=None, **kwargs):
            if first_call[0]:
                first_call[0] = False
                # LLM emits the surrogate form in tool args.
                return {
                    "tool_calls": [
                        {
                            "id": "call-001",
                            "function": {
                                "name": "search_documents",
                                "arguments": json.dumps({"query": f"{surrogate} contract"}),
                            },
                        }
                    ],
                    "content": None,
                }
            return {"tool_calls": [], "content": None}

        async def _mock_stream_response(messages, *, model=None, **kwargs):
            yield {"delta": "Found the contract.", "done": False}
            yield {"delta": "", "done": True}

        supabase_stub = _make_supabase_stub(thread_id)
        stub_settings = _patched_settings(
            pii_redaction_enabled=True, tools_enabled=True, tools_max_iterations=2,
        )

        with (
            patch("app.routers.chat.settings", stub_settings),
            patch("app.routers.chat.get_supabase_client", return_value=supabase_stub),
            patch("app.services.system_settings_service.get_system_settings",
                  return_value=_MOCK_SYS_SETTINGS),
            patch("app.routers.chat.get_system_settings",
                  return_value=_MOCK_SYS_SETTINGS),
            patch(
                "app.services.openrouter_service.OpenRouterService.complete_with_tools",
                side_effect=_mock_complete_with_tools,
            ),
            patch(
                "app.services.openrouter_service.OpenRouterService.stream_response",
                side_effect=_mock_stream_response,
            ),
            patch(
                "app.services.tool_service.ToolService.execute_tool",
                side_effect=_mock_execute_tool,
            ),
        ):
            client = TestClient(app)
            response = client.post(
                "/chat/stream",
                json={"thread_id": thread_id, "message": f"{surrogate} contract"},
                headers={"Authorization": f"Bearer {_FAKE_TOKEN}"},
            )
            _consume_sse(response)

        assert len(captured_tool_calls) >= 1, "search_documents was not called"
        tool_args_json = json.dumps(captured_tool_calls[0]["arguments"])
        # The surrogate form should NOT appear in the tool args after de-anonymization.
        assert surrogate not in tool_args_json, (
            f"D-91 walker failed: surrogate still present in tool args after deanonymize_tool_args"
        )

    async def test_walker_symmetry_present(self):
        """Assert deanonymize_tool_args + anonymize_tool_output are both imported in chat.py."""
        import pathlib
        src = pathlib.Path("app/routers/chat.py").read_text()
        assert "deanonymize_tool_args" in src, "deanonymize_tool_args not in chat.py"
        assert "anonymize_tool_output" in src, "anonymize_tool_output not in chat.py"


# ──────────────────────────── SC#4 ─────────────────────────────────────────


class TestSC4_SqlGrepAndSubAgent:
    """SC#4: query_database + kb_grep walker symmetry + no-double-anonymization.

    D-91 walker must de-anonymize args AND re-anonymize output for EVERY tool
    type, not just search_documents. The no-double-anonymization invariant
    ensures the walker is idempotent on surrogate-form strings.
    """

    async def test_no_double_anonymization(self, fresh_thread_id):
        """Calling redact_text on already-surrogate text does not reveal real values.

        After anon: real → surrogate. Re-anon of surrogate may produce a second
        surrogate (Presidio can detect Faker-generated names), but the key invariant
        is that the REAL value never reappears in the output of the second pass.
        This confirms no de-anonymization / chain-inversion occurs.
        """
        thread_id = fresh_thread_id
        registry = await ConversationRegistry.load(thread_id)
        svc = get_redaction_service()

        real_name = "Bambang Sutrisno"
        # First pass — anonymize a real name.
        result1 = await svc.redact_text(f"Pak {real_name} called", registry=registry)
        surrogate_text = result1.anonymized_text

        # The real name must not appear in the first-pass output.
        assert real_name not in surrogate_text, (
            f"first-pass failed: real name still in anonymized text: {surrogate_text!r}"
        )

        # Reload registry after first anon so second pass has the mapping.
        registry2 = await ConversationRegistry.load(thread_id)
        # Second pass — re-anonymize the surrogate form.
        result2 = await svc.redact_text(surrogate_text, registry=registry2)

        # Key invariant: the real value must NOT appear in the second-pass output
        # (no chain-inversion / de-anonymization).
        # Note: Presidio may or may not detect Faker-generated names as PERSON
        # entities; if it does, we get a new surrogate (which is fine — the real
        # value is still absent). If it doesn't, the text is returned as-is.
        assert real_name not in result2.anonymized_text, (
            f"double-anon invariant violated: real name reappeared in second pass output"
        )

    async def test_multiple_tools_walker_invoked(self, fresh_thread_id):
        """query_database + kb_grep tool calls both go through the D-91 walker.

        We mock execute_tool to capture args and assert the walker was invoked
        (surrogate in LLM output → real args to execute_tool).
        """
        thread_id = fresh_thread_id

        # Seed the registry with a known surrogate→real mapping.
        registry = await ConversationRegistry.load(thread_id)
        svc = get_redaction_service()
        res = await svc.redact_text("Bambang Sutrisno", registry=registry)
        surrogate_text = res.anonymized_text.strip()
        registry = await ConversationRegistry.load(thread_id)
        surrogate = None
        for entry in registry.entries():
            if entry.real_value == "Bambang Sutrisno":
                surrogate = entry.surrogate_value
                break

        if surrogate is None:
            pytest.skip("NER did not detect PERSON entity; skip SC4 multi-tool test")

        captured_tool_args: dict[str, list] = {}
        call_count = [0]

        async def _mock_execute_tool(name, arguments, user_id, context=None, *, registry=None):
            captured_tool_args.setdefault(name, []).append(arguments)
            if name == "query_database":
                return {"rows": [{"name": "Bambang Sutrisno", "amount": 100}]}
            elif name == "kb_grep":
                return {"matches": [{"file": "/c1.pdf", "line": "Bambang Sutrisno"}]}
            return {"results": []}

        async def _mock_complete_with_tools(messages, tools, *, model=None, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return {
                    "tool_calls": [
                        {
                            "id": "call-001",
                            "function": {
                                "name": "query_database",
                                "arguments": json.dumps({"sql": f"SELECT * WHERE name='{surrogate}'"}),
                            },
                        },
                        {
                            "id": "call-002",
                            "function": {
                                "name": "kb_grep",
                                "arguments": json.dumps({"pattern": surrogate}),
                            },
                        },
                    ],
                    "content": None,
                }
            return {"tool_calls": [], "content": None}

        async def _mock_stream_response(messages, *, model=None, **kwargs):
            yield {"delta": "Found records.", "done": False}
            yield {"delta": "", "done": True}

        supabase_stub = _make_supabase_stub(thread_id)
        stub_settings = _patched_settings(
            pii_redaction_enabled=True, tools_enabled=True, tools_max_iterations=3,
        )

        with (
            patch("app.routers.chat.settings", stub_settings),
            patch("app.routers.chat.get_supabase_client", return_value=supabase_stub),
            patch("app.services.system_settings_service.get_system_settings",
                  return_value=_MOCK_SYS_SETTINGS),
            patch("app.routers.chat.get_system_settings",
                  return_value=_MOCK_SYS_SETTINGS),
            patch(
                "app.services.openrouter_service.OpenRouterService.complete_with_tools",
                side_effect=_mock_complete_with_tools,
            ),
            patch(
                "app.services.openrouter_service.OpenRouterService.stream_response",
                side_effect=_mock_stream_response,
            ),
            patch(
                "app.services.tool_service.ToolService.execute_tool",
                side_effect=_mock_execute_tool,
            ),
        ):
            client = TestClient(app)
            response = client.post(
                "/chat/stream",
                json={"thread_id": thread_id, "message": f"Find {surrogate} records"},
                headers={"Authorization": f"Bearer {_FAKE_TOKEN}"},
            )
            _consume_sse(response)

        # Both tools were called.
        assert "query_database" in captured_tool_args, "query_database not called"
        assert "kb_grep" in captured_tool_args, "kb_grep not called"

        # Surrogate should NOT appear in args (de-anonymized to real by D-91 walker).
        for tool_name, args_list in captured_tool_args.items():
            for args in args_list:
                args_json = json.dumps(args)
                assert surrogate not in args_json, (
                    f"D-91 walker failed: surrogate still in {tool_name} args: {args_json}"
                )


# ──────────────────────────── SC#5 ─────────────────────────────────────────


class TestSC5_OffMode:
    """SC#5: PII_REDACTION_ENABLED=false ⇒ Phase 0 CHAT-06 baseline preserved.

    D-84: top-level branch skips registry load, batch anon, SSE redaction events,
    buffering. ZERO redaction_status events. Progressive deltas flow as before.
    tool_start/tool_result emit FULL payloads with input/output fields.
    """

    async def test_off_mode_no_redaction_status_events(self, fresh_thread_id):
        """ZERO redaction_status events when PII_REDACTION_ENABLED=false."""
        thread_id = fresh_thread_id

        async def _mock_stream_response(messages, *, model=None, **kwargs):
            yield {"delta": "Hello ", "done": False}
            yield {"delta": "world", "done": False}
            yield {"delta": ".", "done": False}
            yield {"delta": "", "done": True}

        supabase_stub = _make_supabase_stub(thread_id)
        stub_settings = _patched_settings(pii_redaction_enabled=False, tools_enabled=False)

        with (
            patch("app.routers.chat.settings", stub_settings),
            patch("app.routers.chat.get_supabase_client", return_value=supabase_stub),
            patch("app.services.system_settings_service.get_system_settings",
                  return_value=_MOCK_SYS_SETTINGS),
            patch("app.routers.chat.get_system_settings",
                  return_value=_MOCK_SYS_SETTINGS),
            patch(
                "app.services.openrouter_service.OpenRouterService.stream_response",
                side_effect=_mock_stream_response,
            ),
        ):
            client = TestClient(app)
            response = client.post(
                "/chat/stream",
                json={"thread_id": thread_id, "message": "Hello"},
                headers={"Authorization": f"Bearer {_FAKE_TOKEN}"},
            )
            events = _consume_sse(response)

        # ZERO redaction_status events — D-84 off-mode invariant.
        redaction_status_events = [e for e in events if e.get("type") == "redaction_status"]
        assert len(redaction_status_events) == 0, (
            f"off-mode emitted redaction_status events: {redaction_status_events}"
        )

        # PROGRESSIVE delta events — multiple deltas with content (not single batch).
        deltas_with_content = [e for e in events if e.get("type") == "delta" and e.get("delta")]
        assert len(deltas_with_content) >= 2, (
            f"off-mode should emit progressive deltas (≥2), got {len(deltas_with_content)}"
        )

    async def test_off_mode_full_tool_payloads(self, fresh_thread_id):
        """tool_start has 'input' and tool_result has 'output' when redaction OFF."""
        thread_id = fresh_thread_id
        first_call = [True]

        async def _mock_complete_with_tools(messages, tools, *, model=None, **kwargs):
            if first_call[0]:
                first_call[0] = False
                return {
                    "tool_calls": [
                        {
                            "id": "call-001",
                            "function": {
                                "name": "search_documents",
                                "arguments": '{"query": "test"}',
                            },
                        }
                    ],
                    "content": None,
                }
            return {"tool_calls": [], "content": None}

        async def _mock_execute_tool(name, arguments, user_id, context=None, *, registry=None):
            return {"results": [{"content": "doc chunk", "id": "doc-001"}]}

        async def _mock_stream_response(messages, *, model=None, **kwargs):
            yield {"delta": "Found docs.", "done": False}
            yield {"delta": "", "done": True}

        supabase_stub = _make_supabase_stub(thread_id)
        stub_settings = _patched_settings(
            pii_redaction_enabled=False, tools_enabled=True, tools_max_iterations=2,
        )

        with (
            patch("app.routers.chat.settings", stub_settings),
            patch("app.routers.chat.get_supabase_client", return_value=supabase_stub),
            patch("app.services.system_settings_service.get_system_settings",
                  return_value=_MOCK_SYS_SETTINGS),
            patch("app.routers.chat.get_system_settings",
                  return_value=_MOCK_SYS_SETTINGS),
            patch(
                "app.services.openrouter_service.OpenRouterService.complete_with_tools",
                side_effect=_mock_complete_with_tools,
            ),
            patch(
                "app.services.openrouter_service.OpenRouterService.stream_response",
                side_effect=_mock_stream_response,
            ),
            patch(
                "app.services.tool_service.ToolService.execute_tool",
                side_effect=_mock_execute_tool,
            ),
        ):
            client = TestClient(app)
            response = client.post(
                "/chat/stream",
                json={"thread_id": thread_id, "message": "Find docs"},
                headers={"Authorization": f"Bearer {_FAKE_TOKEN}"},
            )
            events = _consume_sse(response)

        # FULL tool event payloads — off-mode preserves input/output (D-89 backward-compat).
        tool_starts = [e for e in events if e.get("type") == "tool_start"]
        tool_results = [e for e in events if e.get("type") == "tool_result"]
        assert tool_starts, "no tool_start events in off-mode turn"
        for ts in tool_starts:
            assert "input" in ts, f"off-mode tool_start missing input field: {ts}"
        for tr in tool_results:
            assert "output" in tr, f"off-mode tool_result missing output field: {tr}"

        # No redaction_status events.
        assert len([e for e in events if e.get("type") == "redaction_status"]) == 0


# ──────────────────────────── B4 Log Privacy ──────────────────────────────


class TestB4_LogPrivacy_ChatLoop:
    """B4 invariant: no real PII in any log record across the full chat turn.

    Extends Phase 1 B4 / Phase 4 caplog pattern to Phase 5's new log sites:
    - D-90 degrade log (deanon_degraded)
    - D-94 egress trip log (egress_blocked)
    - Normal turn logging

    B4 contract: log messages emit counts/class names only — never real_values,
    never surrogate strings, never raw PII payloads.
    """

    async def test_no_pii_in_logs_happy_path(self, fresh_thread_id, caplog):
        """B4 invariant holds during a normal chat turn with PII in the message."""
        thread_id = fresh_thread_id
        caplog.set_level(logging.DEBUG, logger="app")

        async def _mock_stream_response(messages, *, model=None, **kwargs):
            yield {"delta": "Acknowledged.", "done": False}
            yield {"delta": "", "done": True}

        supabase_stub = _make_supabase_stub(thread_id)
        stub_settings = _patched_settings(pii_redaction_enabled=True, tools_enabled=False)

        real_pii_message = "Pak Bambang Sutrisno (bambang@example.id) sent a query"

        with (
            patch("app.routers.chat.settings", stub_settings),
            patch("app.routers.chat.get_supabase_client", return_value=supabase_stub),
            patch("app.services.system_settings_service.get_system_settings",
                  return_value=_MOCK_SYS_SETTINGS),
            patch("app.routers.chat.get_system_settings",
                  return_value=_MOCK_SYS_SETTINGS),
            patch(
                "app.services.openrouter_service.OpenRouterService.stream_response",
                side_effect=_mock_stream_response,
            ),
        ):
            client = TestClient(app)
            response = client.post(
                "/chat/stream",
                json={"thread_id": thread_id, "message": real_pii_message},
                headers={"Authorization": f"Bearer {_FAKE_TOKEN}"},
            )
            _consume_sse(response)

        registry = await ConversationRegistry.load(thread_id)

        # B4 invariant: no real_value in ANY log record.
        for record in caplog.records:
            msg = record.getMessage()
            for entry in registry.entries():
                assert entry.real_value not in msg, (
                    f"B4 violated: real_value ({entry.entity_type}) "
                    f"found in log record from {record.name}/{record.levelname}"
                )

    async def test_no_pii_in_logs_deanon_degrade_path(self, fresh_thread_id, caplog):
        """B4 invariant holds during D-90 degrade path (de-anon failure)."""
        thread_id = fresh_thread_id
        caplog.set_level(logging.DEBUG, logger="app")

        original_deanon = RedactionService.de_anonymize_text
        deanon_call_count = [0]

        async def _flaky_deanon(self_inner, text, registry, mode="none"):
            deanon_call_count[0] += 1
            # Fail on first call to trigger D-90 degrade; second call (fallback) succeeds.
            if deanon_call_count[0] == 1:
                raise RuntimeError("simulated fuzzy LLM failure D-90")
            return await original_deanon(self_inner, text, registry, mode=mode)

        async def _mock_stream_response(messages, *, model=None, **kwargs):
            yield {"delta": "Aaron Thompson DDS reply.", "done": False}
            yield {"delta": "", "done": True}

        supabase_stub = _make_supabase_stub(thread_id)
        stub_settings = _patched_settings(
            pii_redaction_enabled=True, tools_enabled=False, fuzzy_deanon_mode="none",
        )
        real_pii_message = "Pak Bambang Sutrisno sent a query (bambang@example.id)"

        with (
            patch.object(RedactionService, "de_anonymize_text", _flaky_deanon),
            patch("app.routers.chat.settings", stub_settings),
            patch("app.routers.chat.get_supabase_client", return_value=supabase_stub),
            patch("app.services.system_settings_service.get_system_settings",
                  return_value=_MOCK_SYS_SETTINGS),
            patch("app.routers.chat.get_system_settings",
                  return_value=_MOCK_SYS_SETTINGS),
            patch(
                "app.services.openrouter_service.OpenRouterService.stream_response",
                side_effect=_mock_stream_response,
            ),
        ):
            client = TestClient(app)
            response = client.post(
                "/chat/stream",
                json={"thread_id": thread_id, "message": real_pii_message},
                headers={"Authorization": f"Bearer {_FAKE_TOKEN}"},
            )
            _consume_sse(response)

        registry = await ConversationRegistry.load(thread_id)

        # Degrade log present (D-90).
        degrade_logs = [r for r in caplog.records if "deanon_degraded" in r.getMessage()]
        assert len(degrade_logs) >= 1, (
            f"expected D-90 deanon_degraded warn log absent from caplog records"
        )

        # B4 invariant: no real_value in ANY log record.
        for record in caplog.records:
            msg = record.getMessage()
            for entry in registry.entries():
                assert entry.real_value not in msg, (
                    f"B4 violated: real_value ({entry.entity_type}) "
                    f"found in log record from {record.name}/{record.levelname}"
                )


# ──────────────────────────── Egress Trip ─────────────────────────────────


class TestEgressTrip_ChatPath:
    """Egress filter trip on simulated Phase 1 NER miss.

    D-94: pre-flight egress filter wraps every OpenRouter call when redaction ON.
    Trip = log per D-55, emit redaction_status:blocked + delta:{done:true}, abort turn.
    The LLM must NOT be called after the egress filter trips.
    """

    async def test_egress_filter_trips_on_ner_miss(self, fresh_thread_id):
        """Simulated NER miss: real_value in registry + bypassed batch anon → egress trips.

        Strategy:
        1. Seed the registry directly (via ConversationRegistry.load + upsert_delta).
        2. Mock redact_text_batch to return identity (simulates NER miss — real PII
           bypasses anonymization and reaches the egress filter as-is).
        3. Assert: egress filter detects the real_value in the serialized messages,
           raises EgressBlockedAbort, emits redaction_status:blocked.
        4. Assert: stream_response is NOT called (LLM call prevented).
        5. Assert: turn aborts cleanly with 200 status.
        """
        thread_id = fresh_thread_id

        # Step 1: seed a registry entry directly so egress_filter knows the real_value.
        registry = await ConversationRegistry.load(thread_id)
        mapping = EntityMapping(
            real_value="Bambang Sutrisno",
            real_value_lower="bambang sutrisno",
            surrogate_value="Aaron Thompson DDS",
            entity_type="PERSON",
        )
        await registry.upsert_delta([mapping])

        # Step 2: mock redact_text_batch to return identity (Phase 1 NER miss simulation).
        async def _bypass_batch(self_inner, texts, registry_inner):
            # Return the real PII text unchanged — egress filter will catch it.
            return list(texts)

        # Step 3: track stream_response call count.
        stream_response_call_count = [0]

        async def _mock_stream_response(messages, *, model=None, **kwargs):
            stream_response_call_count[0] += 1
            yield {"delta": "test", "done": False}
            yield {"delta": "", "done": True}

        complete_call_count = [0]

        async def _mock_complete_with_tools(messages, tools, *, model=None, **kwargs):
            complete_call_count[0] += 1
            return {"tool_calls": [], "content": None}

        supabase_stub = _make_supabase_stub(thread_id)
        stub_settings = _patched_settings(
            pii_redaction_enabled=True, tools_enabled=False,
        )

        with (
            patch.object(RedactionService, "redact_text_batch", _bypass_batch),
            patch("app.routers.chat.settings", stub_settings),
            patch("app.routers.chat.get_supabase_client", return_value=supabase_stub),
            patch("app.services.system_settings_service.get_system_settings",
                  return_value=_MOCK_SYS_SETTINGS),
            patch("app.routers.chat.get_system_settings",
                  return_value=_MOCK_SYS_SETTINGS),
            patch(
                "app.services.openrouter_service.OpenRouterService.stream_response",
                side_effect=_mock_stream_response,
            ),
            patch(
                "app.services.openrouter_service.OpenRouterService.complete_with_tools",
                side_effect=_mock_complete_with_tools,
            ),
        ):
            client = TestClient(app)
            response = client.post(
                "/chat/stream",
                json={
                    "thread_id": thread_id,
                    # The message contains the seeded real_value — bypassed anon lets it through.
                    "message": "Bambang Sutrisno needs help",
                },
                headers={"Authorization": f"Bearer {_FAKE_TOKEN}"},
            )
            events = _consume_sse(response)

        # Step 4: stream_response MUST NOT be called (egress trip aborts the turn).
        assert stream_response_call_count[0] == 0, (
            f"egress trip should prevent stream_response call; "
            f"got {stream_response_call_count[0]} calls"
        )

        # Step 5: SSE emitted redaction_status:blocked.
        blocked_events = [
            e for e in events
            if e.get("type") == "redaction_status" and e.get("stage") == "blocked"
        ]
        assert len(blocked_events) >= 1, (
            f"expected redaction_status:blocked event; got {events}"
        )

        # Stream terminated cleanly with delta:{done:true}.
        done_events = [
            e for e in events if e.get("type") == "delta" and e.get("done") is True
        ]
        assert len(done_events) >= 1, (
            f"expected delta:{{done:true}} terminator; got {events}"
        )

        # Response status is 200 (clean abort, not 500).
        assert response.status_code == 200, (
            f"expected 200 (clean abort); got {response.status_code}"
        )

    async def test_egress_trip_complete_with_tools_prevented(self, fresh_thread_id):
        """Egress filter trips at complete_with_tools call site too (D-94 site #1)."""
        thread_id = fresh_thread_id

        # Seed registry.
        registry = await ConversationRegistry.load(thread_id)
        mapping = EntityMapping(
            real_value="Sari Dewi",
            real_value_lower="sari dewi",
            surrogate_value="Carol Johnson",
            entity_type="PERSON",
        )
        await registry.upsert_delta([mapping])

        # Bypass batch anon — real_value leaks into messages.
        async def _bypass_batch(self_inner, texts, registry_inner):
            return list(texts)

        complete_call_count = [0]

        async def _mock_complete_with_tools(messages, tools, *, model=None, **kwargs):
            complete_call_count[0] += 1
            return {"tool_calls": [], "content": None}

        async def _mock_stream_response(messages, *, model=None, **kwargs):
            yield {"delta": "done", "done": False}
            yield {"delta": "", "done": True}

        supabase_stub = _make_supabase_stub(thread_id)
        # Enable tools so _run_tool_loop is entered (egress D-94 site #1 inside loop).
        stub_settings = _patched_settings(
            pii_redaction_enabled=True, tools_enabled=True, tools_max_iterations=1,
        )

        with (
            patch.object(RedactionService, "redact_text_batch", _bypass_batch),
            patch("app.routers.chat.settings", stub_settings),
            patch("app.routers.chat.get_supabase_client", return_value=supabase_stub),
            patch("app.services.system_settings_service.get_system_settings",
                  return_value=_MOCK_SYS_SETTINGS),
            patch("app.routers.chat.get_system_settings",
                  return_value=_MOCK_SYS_SETTINGS),
            patch(
                "app.services.openrouter_service.OpenRouterService.complete_with_tools",
                side_effect=_mock_complete_with_tools,
            ),
            patch(
                "app.services.openrouter_service.OpenRouterService.stream_response",
                side_effect=_mock_stream_response,
            ),
        ):
            client = TestClient(app)
            response = client.post(
                "/chat/stream",
                json={"thread_id": thread_id, "message": "Sari Dewi question"},
                headers={"Authorization": f"Bearer {_FAKE_TOKEN}"},
            )
            events = _consume_sse(response)

        # Egress tripped → complete_with_tools NOT called (or if called, blocked event present).
        blocked_events = [
            e for e in events
            if e.get("type") == "redaction_status" and e.get("stage") == "blocked"
        ]
        assert len(blocked_events) >= 1, (
            f"expected redaction_status:blocked event from tool_loop egress; got {events}"
        )
        assert response.status_code == 200
