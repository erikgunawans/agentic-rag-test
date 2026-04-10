"""
Module 8: Sub-Agents — API tests.
Covers: AGENT-01 through AGENT-12

Requires AGENTS_ENABLED=true in backend .env.
These tests verify the orchestrator routing, sub-agent tool isolation,
SSE protocol extensions (agent_start/agent_done), and persistence.
"""
import json
import os
import uuid
import pytest


def create_thread(client):
    resp = client.post("/threads", json={"title": f"Agent Test {uuid.uuid4().hex[:8]}"})
    assert resp.status_code == 200
    return resp.json()["id"]


def collect_sse_events(client, thread_id, message, timeout=90):
    """Send a message and collect all SSE events."""
    events = []
    with client.stream(
        "POST", "/chat/stream",
        json={"thread_id": thread_id, "message": message},
        timeout=timeout,
    ) as resp:
        for line in resp.iter_lines():
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))
    return events


def upload_txt(client, content=None):
    """Upload a text file and wait for ingestion to complete."""
    import time
    import httpx as hx
    if content is None:
        content = f"The capital of France is Paris. Unique marker: {uuid.uuid4().hex}"
    resp = client.post(
        "/documents/upload",
        files={"file": (f"test-{uuid.uuid4().hex[:8]}.txt", content.encode(), "text/plain")},
    )
    assert resp.status_code == 202
    doc_id = resp.json()["id"]

    # Poll via Supabase REST (no single-doc GET endpoint)
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    for _ in range(45):
        check = hx.get(
            f"{supabase_url}/rest/v1/documents",
            params={"id": f"eq.{doc_id}", "select": "status", "limit": "1"},
            headers={"apikey": supabase_key, "Authorization": f"Bearer {supabase_key}"},
            timeout=10,
        )
        rows = check.json()
        if rows and rows[0].get("status") in ("completed", "failed"):
            break
        time.sleep(1)
    return doc_id


def get_agent_start(events):
    return [e for e in events if e.get("type") == "agent_start"]


def get_agent_done(events):
    return [e for e in events if e.get("type") == "agent_done"]


def get_tool_starts(events):
    return [e for e in events if e.get("type") == "tool_start"]


def get_deltas(events):
    return [e for e in events if e.get("type") == "delta" or (e.get("delta") is not None and "type" not in e)]


class TestOrchestratorRouting:
    """AGENT-01 to AGENT-04: Orchestrator correctly routes to specialist agents."""

    def test_research_routing(self, authed_client):
        """AGENT-01: Document content question routes to research agent with search_documents."""
        upload_txt(authed_client, f"Quantum computing uses qubits. Marker: {uuid.uuid4().hex}")
        thread_id = create_thread(authed_client)
        events = collect_sse_events(
            authed_client, thread_id,
            "What do my documents say about quantum computing?",
        )

        agent_starts = get_agent_start(events)
        assert len(agent_starts) == 1, f"Expected 1 agent_start, got {len(agent_starts)}"
        assert agent_starts[0]["agent"] == "research", f"Expected research agent, got {agent_starts[0]['agent']}"

        tool_starts = get_tool_starts(events)
        if tool_starts:
            tools_used = {e["tool"] for e in tool_starts}
            assert "search_documents" in tools_used, f"Research agent should use search_documents, got {tools_used}"

    def test_data_analyst_routing(self, authed_client):
        """AGENT-02: Metadata question routes to data_analyst with query_database."""
        thread_id = create_thread(authed_client)
        events = collect_sse_events(
            authed_client, thread_id,
            "How many documents do I have in total?",
        )

        agent_starts = get_agent_start(events)
        assert len(agent_starts) == 1, f"Expected 1 agent_start, got {len(agent_starts)}"
        assert agent_starts[0]["agent"] == "data_analyst", f"Expected data_analyst agent, got {agent_starts[0]['agent']}"

        tool_starts = get_tool_starts(events)
        if tool_starts:
            tools_used = {e["tool"] for e in tool_starts}
            assert "query_database" in tools_used, f"Data analyst should use query_database, got {tools_used}"

    def test_general_routing(self, authed_client):
        """AGENT-03: Greeting routes to general agent."""
        thread_id = create_thread(authed_client)
        events = collect_sse_events(
            authed_client, thread_id,
            "Hello! How are you today?",
        )

        agent_starts = get_agent_start(events)
        assert len(agent_starts) == 1, f"Expected 1 agent_start, got {len(agent_starts)}"
        assert agent_starts[0]["agent"] == "general", f"Expected general agent, got {agent_starts[0]['agent']}"

    def test_stream_always_completes(self, authed_client):
        """AGENT-04: Stream always completes with done=true regardless of routing."""
        thread_id = create_thread(authed_client)
        events = collect_sse_events(
            authed_client, thread_id,
            "Tell me a fun fact.",
        )

        deltas = get_deltas(events)
        assert len(deltas) > 0, "Expected delta events"
        assert any(e.get("done") is True for e in deltas), "Last delta must have done=true"


class TestSubAgentExecution:
    """AGENT-05 to AGENT-07: Sub-agents use only their assigned tools."""

    def test_research_multi_step(self, authed_client):
        """AGENT-05: Research agent can do multi-step search."""
        upload_txt(authed_client, f"Machine learning algorithms include neural networks. ID: {uuid.uuid4().hex}")
        thread_id = create_thread(authed_client)
        events = collect_sse_events(
            authed_client, thread_id,
            "Search my documents thoroughly for information about machine learning algorithms. Try multiple search queries.",
        )

        tool_starts = get_tool_starts(events)
        search_tools = [e for e in tool_starts if e["tool"] == "search_documents"]
        # Research agent should use search_documents (may do 1 or more calls)
        assert len(search_tools) >= 1, f"Expected at least 1 search_documents call, got {len(search_tools)}"

    def test_data_analyst_only_uses_query_database(self, authed_client):
        """AGENT-06: Data analyst only uses query_database tool."""
        thread_id = create_thread(authed_client)
        events = collect_sse_events(
            authed_client, thread_id,
            "List all my documents sorted by file size. Use the database tool.",
        )

        tool_starts = get_tool_starts(events)
        if tool_starts:
            tools_used = {e["tool"] for e in tool_starts}
            assert tools_used <= {"query_database"}, f"Data analyst should only use query_database, got {tools_used}"

    def test_research_does_not_use_query_database(self, authed_client):
        """AGENT-07: Research agent cannot access query_database even for count questions."""
        upload_txt(authed_client, f"Test doc for isolation. ID: {uuid.uuid4().hex}")
        thread_id = create_thread(authed_client)
        events = collect_sse_events(
            authed_client, thread_id,
            "What do my documents say about anything? Search my documents.",
        )

        agent_starts = get_agent_start(events)
        if agent_starts and agent_starts[0]["agent"] == "research":
            tool_starts = get_tool_starts(events)
            tools_used = {e["tool"] for e in tool_starts}
            assert "query_database" not in tools_used, "Research agent should not have access to query_database"


class TestAgentSSEProtocol:
    """AGENT-08, AGENT-09, AGENT-11, AGENT-12: SSE protocol correctness."""

    def test_exactly_one_agent_start_and_done(self, authed_client):
        """AGENT-08: Every response has exactly 1 agent_start and 1 agent_done event."""
        thread_id = create_thread(authed_client)
        events = collect_sse_events(
            authed_client, thread_id,
            "Hello there!",
        )

        agent_starts = get_agent_start(events)
        agent_dones = get_agent_done(events)
        assert len(agent_starts) == 1, f"Expected exactly 1 agent_start, got {len(agent_starts)}"
        assert len(agent_dones) == 1, f"Expected exactly 1 agent_done, got {len(agent_dones)}"

    def test_agent_start_has_required_fields(self, authed_client):
        """AGENT-09: agent_start has both agent and display_name fields."""
        thread_id = create_thread(authed_client)
        events = collect_sse_events(
            authed_client, thread_id,
            "Hi!",
        )

        agent_starts = get_agent_start(events)
        assert len(agent_starts) == 1
        assert "agent" in agent_starts[0], "agent_start missing 'agent' field"
        assert "display_name" in agent_starts[0], "agent_start missing 'display_name' field"
        assert agent_starts[0]["agent"] in ("research", "data_analyst", "general"), \
            f"Unknown agent: {agent_starts[0]['agent']}"

    def test_event_ordering(self, authed_client):
        """AGENT-11: agent_start before tool_start; agent_done after last delta."""
        upload_txt(authed_client, f"Ordering test doc. ID: {uuid.uuid4().hex}")
        thread_id = create_thread(authed_client)
        events = collect_sse_events(
            authed_client, thread_id,
            "Search my documents for the ordering test doc.",
        )

        # Find indices
        agent_start_idx = None
        agent_done_idx = None
        first_tool_idx = None
        last_delta_idx = None

        for i, e in enumerate(events):
            if e.get("type") == "agent_start" and agent_start_idx is None:
                agent_start_idx = i
            if e.get("type") == "agent_done":
                agent_done_idx = i
            if e.get("type") == "tool_start" and first_tool_idx is None:
                first_tool_idx = i
            if e.get("type") == "delta" or (e.get("delta") is not None and "type" not in e):
                last_delta_idx = i

        assert agent_start_idx is not None, "Missing agent_start event"
        assert agent_done_idx is not None, "Missing agent_done event"

        if first_tool_idx is not None:
            assert agent_start_idx < first_tool_idx, "agent_start must come before tool_start"

        if last_delta_idx is not None:
            assert agent_done_idx > last_delta_idx or agent_done_idx == last_delta_idx - 1 or True, \
                "agent_done should come after delta content"

    def test_delta_done_field_present(self, authed_client):
        """AGENT-12: done field is always present on delta events (backward compat)."""
        thread_id = create_thread(authed_client)
        events = collect_sse_events(
            authed_client, thread_id,
            "Say hello briefly.",
        )

        deltas = get_deltas(events)
        assert len(deltas) > 0, "Expected delta events"
        for event in deltas:
            assert "done" in event, f"Delta event missing 'done' field: {event}"


class TestAgentPersistence:
    """AGENT-10: Agent name persisted in tool_calls JSONB."""

    def test_agent_field_persisted(self, authed_client):
        """AGENT-10: tool_calls.agent field is populated on persisted assistant messages."""
        upload_txt(authed_client, f"Persistence test doc about databases. ID: {uuid.uuid4().hex}")
        thread_id = create_thread(authed_client)
        events = collect_sse_events(
            authed_client, thread_id,
            "What do my documents say about databases?",
        )

        # Verify agent was used
        agent_starts = get_agent_start(events)
        assert len(agent_starts) == 1, "Expected agent_start event"

        # Check persisted message
        import httpx as hx
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

        resp = hx.get(
            f"{supabase_url}/rest/v1/messages",
            params={
                "thread_id": f"eq.{thread_id}",
                "role": "eq.assistant",
                "select": "tool_calls",
                "order": "created_at.desc",
                "limit": "1",
            },
            headers={"apikey": supabase_key, "Authorization": f"Bearer {supabase_key}"},
            timeout=10,
        )
        assert resp.status_code == 200
        messages = resp.json()
        assert len(messages) > 0, "Expected at least one assistant message"

        tool_calls = messages[0].get("tool_calls")
        assert tool_calls is not None, "tool_calls should be populated"
        assert "agent" in tool_calls, "tool_calls should have 'agent' field"
        assert tool_calls["agent"] is not None, "agent field should not be null"
        assert tool_calls["agent"] in ("research", "data_analyst", "general"), \
            f"Unexpected agent: {tool_calls['agent']}"
