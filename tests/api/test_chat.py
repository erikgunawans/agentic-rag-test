"""
Chat Streaming API tests.
Covers: CHAT-01, CHAT-02, CHAT-05, CHAT-06
"""
import json
import pytest


def create_thread(client):
    resp = client.post("/threads", json={"title": "Chat Test Thread"})
    assert resp.status_code == 200
    return resp.json()["id"]


class TestChatStream:
    """CHAT-01: POST /chat/stream returns valid SSE stream."""

    def test_stream_content_type(self, authed_client):
        thread_id = create_thread(authed_client)
        with authed_client.stream(
            "POST", "/chat/stream",
            json={"thread_id": thread_id, "message": "Say exactly: hello"},
        ) as resp:
            assert "text/event-stream" in resp.headers.get("content-type", "")

    def test_stream_contains_done_event(self, authed_client):
        thread_id = create_thread(authed_client)
        events = []
        with authed_client.stream(
            "POST", "/chat/stream",
            json={"thread_id": thread_id, "message": "Say exactly: pong"},
            timeout=60,
        ) as resp:
            for line in resp.iter_lines():
                if line.startswith("data: "):
                    events.append(json.loads(line[6:]))

        assert len(events) > 0, "No SSE events received"
        last = events[-1]
        assert last.get("done") is True, "Last event must have done=true"

    def test_stream_builds_non_empty_response(self, authed_client):
        thread_id = create_thread(authed_client)
        deltas = []
        with authed_client.stream(
            "POST", "/chat/stream",
            json={"thread_id": thread_id, "message": "Reply with a single word: yes"},
            timeout=60,
        ) as resp:
            for line in resp.iter_lines():
                if line.startswith("data: "):
                    event = json.loads(line[6:])
                    if event.get("delta"):
                        deltas.append(event["delta"])

        assert len(deltas) > 0, "No delta chunks received — empty response"


class TestChatEdgeCases:
    """CHAT-05/06: Error handling."""

    def test_nonexistent_thread_returns_404(self, authed_client):
        resp = authed_client.post(
            "/chat/stream",
            json={"thread_id": "00000000-0000-0000-0000-000000000000", "message": "hi"},
        )
        assert resp.status_code == 404

    def test_unauthenticated_returns_401(self, client):
        """CHAT-06 / SEC-05: No auth header."""
        resp = client.post(
            "/chat/stream",
            json={"thread_id": "00000000-0000-0000-0000-000000000000", "message": "hi"},
        )
        assert resp.status_code in (401, 403)
