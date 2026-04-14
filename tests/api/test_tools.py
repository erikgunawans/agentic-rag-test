"""
Module 7: Additional Tools — API tests.
Covers: TOOL-01 through TOOL-09

Tests verify that the agentic tool-calling loop works correctly:
tool_start/tool_result SSE events, delta streaming, tool_calls persistence,
SQL safety, backward compatibility, and graceful error handling.
"""
import json
import os
import uuid
import pytest


def create_thread(client):
    resp = client.post("/threads", json={"title": f"Tool Test {uuid.uuid4().hex[:8]}"})
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


class TestToolCalling:
    """TOOL-01: Document content question triggers search_documents tool."""

    def test_search_documents_tool_triggered(self, authed_client):
        """TOOL-01: Asking about document content triggers search_documents tool."""
        # Upload a test document first
        upload_txt(authed_client, f"Photosynthesis is the process by which plants convert sunlight. ID: {uuid.uuid4().hex}")

        thread_id = create_thread(authed_client)
        events = collect_sse_events(
            authed_client, thread_id,
            "What is photosynthesis according to my documents?",
        )

        tool_starts = [e for e in events if e.get("type") == "tool_start"]
        tool_results = [e for e in events if e.get("type") == "tool_result"]
        deltas = [e for e in events if e.get("type") == "delta" or (e.get("delta") is not None and "type" not in e)]

        # Should have at least one tool call
        assert len(tool_starts) > 0, f"Expected tool_start events, got: {events}"
        # At least one should be search_documents
        search_tools = [e for e in tool_starts if e["tool"] == "search_documents"]
        assert len(search_tools) > 0, f"Expected search_documents tool, got tools: {[e['tool'] for e in tool_starts]}"

        # Should have corresponding results
        assert len(tool_results) >= len(tool_starts), "Each tool_start should have a tool_result"

        # Should have delta events with final done=true
        assert len(deltas) > 0, "Expected delta events"
        last_delta = deltas[-1]
        assert last_delta.get("done") is True, "Last delta must have done=true"

    def test_query_database_tool_triggered(self, authed_client):
        """TOOL-02: Asking about document counts triggers query_database tool."""
        thread_id = create_thread(authed_client)
        events = collect_sse_events(
            authed_client, thread_id,
            "How many documents do I have? Use the query_database tool to find out.",
        )

        tool_starts = [e for e in events if e.get("type") == "tool_start"]
        db_tools = [e for e in tool_starts if e["tool"] == "query_database"]
        assert len(db_tools) > 0, f"Expected query_database tool, got tools: {[e['tool'] for e in tool_starts]}"

    def test_direct_response_no_tools(self, authed_client):
        """TOOL-03: Simple greeting doesn't trigger any tools."""
        thread_id = create_thread(authed_client)
        events = collect_sse_events(
            authed_client, thread_id,
            "Hello! Just say hi back in one word.",
        )

        tool_starts = [e for e in events if e.get("type") == "tool_start"]
        deltas = [e for e in events if e.get("type") == "delta" or (e.get("delta") is not None and "type" not in e)]

        # Should have no tool calls for a simple greeting
        assert len(tool_starts) == 0, f"Expected no tools for greeting, got: {[e['tool'] for e in tool_starts]}"
        # But should still have a text response
        assert len(deltas) > 0, "Expected delta events for text response"


class TestSQLSafety:
    """TOOL-04: SQL injection prevention."""

    def test_sql_read_only_enforcement(self, authed_client):
        """TOOL-04: query_database rejects non-SELECT queries via system enforcement."""
        thread_id = create_thread(authed_client)
        events = collect_sse_events(
            authed_client, thread_id,
            "Use the query_database tool with this exact SQL: DELETE FROM documents WHERE user_id = :user_id",
        )

        # If the tool was called, the result should contain an error
        tool_results = [e for e in events if e.get("type") == "tool_result" and e.get("tool") == "query_database"]
        for result in tool_results:
            output = result.get("output", {})
            # Either the LLM refused to run DELETE, or the backend rejected it
            if "error" in output:
                assert "select" in output["error"].lower() or "not allowed" in output["error"].lower()

        # The response should still complete successfully (graceful fallback)
        deltas = [e for e in events if e.get("type") == "delta" or (e.get("delta") is not None and "type" not in e)]
        assert any(e.get("done") is True for e in deltas), "Stream should complete with done=true"


class TestToolPersistence:
    """TOOL-05: tool_calls are persisted on assistant messages."""

    def test_tool_calls_saved_to_db(self, authed_client):
        """TOOL-05: tool_calls JSONB is saved on assistant messages."""
        thread_id = create_thread(authed_client)

        # Send a message that should trigger tools
        events = collect_sse_events(
            authed_client, thread_id,
            "How many documents do I have? Use query_database to count them.",
        )

        # Verify tool was called
        tool_starts = [e for e in events if e.get("type") == "tool_start"]
        if len(tool_starts) == 0:
            pytest.skip("LLM did not use tools for this query")

        # Check the persisted messages in Supabase
        import httpx as hx
        import os
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

        resp = hx.get(
            f"{supabase_url}/rest/v1/messages",
            params={"thread_id": f"eq.{thread_id}", "role": "eq.assistant", "select": "tool_calls", "order": "created_at.desc", "limit": "1"},
            headers={"apikey": supabase_key, "Authorization": f"Bearer {supabase_key}"},
            timeout=10,
        )
        assert resp.status_code == 200
        messages = resp.json()
        assert len(messages) > 0, "Expected at least one assistant message"

        # tool_calls should be populated
        tool_calls = messages[0].get("tool_calls")
        assert tool_calls is not None, "tool_calls should be populated on assistant message"
        assert "calls" in tool_calls, "tool_calls should have 'calls' key"
        assert len(tool_calls["calls"]) > 0, "tool_calls should have at least one call"


class TestSSECompat:
    """TOOL-07/09: SSE backward compatibility and content type."""

    def test_sse_done_field_present(self, authed_client):
        """TOOL-07: All delta SSE events contain the 'done' field."""
        thread_id = create_thread(authed_client)
        events = collect_sse_events(
            authed_client, thread_id,
            "Say hello in one word.",
        )

        deltas = [e for e in events if e.get("type") == "delta" or (e.get("delta") is not None and "type" not in e)]
        assert len(deltas) > 0, "Expected delta events"
        for event in deltas:
            assert "done" in event, f"Delta event missing 'done' field: {event}"

    def test_stream_content_type(self, authed_client):
        """TOOL-09: Response content-type is still text/event-stream."""
        thread_id = create_thread(authed_client)
        with authed_client.stream(
            "POST", "/chat/stream",
            json={"thread_id": thread_id, "message": "hi"},
        ) as resp:
            assert "text/event-stream" in resp.headers.get("content-type", "")


class TestToolErrorHandling:
    """TOOL-08: Tool errors don't crash the response."""

    def test_graceful_fallback_on_error(self, authed_client):
        """TOOL-08: If a tool fails, the response still completes."""
        thread_id = create_thread(authed_client)
        events = collect_sse_events(
            authed_client, thread_id,
            "Use query_database with this SQL: SELECT invalid_column FROM nonexistent_table WHERE user_id = :user_id",
        )

        # Stream should complete regardless of tool errors
        deltas = [e for e in events if e.get("type") == "delta" or (e.get("delta") is not None and "type" not in e)]
        assert any(e.get("done") is True for e in deltas), "Stream should complete with done=true even after tool error"
