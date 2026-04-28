"""ADR-0008: API integration tests for web search toggle.

Hits the production API per ADR-0005. Follows the pattern in test_chat.py:
- creates a real thread via POST /threads before issuing chat requests
- parses SSE lines prefixed with "data: " and breaks on done=true

Note: we use a dedicated httpx.Client per test with a long read timeout because
the session-scoped fixture client uses a 30s timeout, and a chat turn with
web_search forced off can sometimes exceed that on cold paths.
"""
import json
import os
import httpx
import pytest


API_BASE = os.getenv("TEST_API_BASE", "https://api-production-cde1.up.railway.app")
STREAM_TIMEOUT = httpx.Timeout(connect=15.0, read=120.0, write=15.0, pool=15.0)


def create_thread(client, title: str = "Web Search Toggle Test"):
    resp = client.post("/threads", json={"title": title})
    assert resp.status_code == 200, f"thread create failed: {resp.text}"
    return resp.json()["id"]


def _stream_chat(auth_headers, payload):
    """Drain the SSE stream and return the full list of parsed events.

    Uses a fresh httpx.Client with an extended read timeout so slow turns do
    not get cut off mid-stream by the shared 30s fixture client."""
    events = []
    with httpx.Client(base_url=API_BASE, timeout=STREAM_TIMEOUT, headers=auth_headers) as c:
        with c.stream("POST", "/chat/stream", json=payload) as resp:
            assert resp.status_code == 200, f"chat/stream returned {resp.status_code}"
            for line in resp.iter_lines():
                if not line.startswith("data: "):
                    continue
                event = json.loads(line[6:])
                events.append(event)
                if event.get("done"):
                    break
    return events


def _web_search_dispatched(events) -> bool:
    for event in events:
        tool_start = event.get("tool_start")
        if isinstance(tool_start, dict) and tool_start.get("tool") == "web_search":
            return True
    return False


class TestWebSearchToggle:
    """ADR-0008: per-message web_search toggle behavior."""

    def test_toggle_off_does_not_dispatch_web_search(self, authed_client, auth_headers):
        """When web_search=false, the SSE stream must not emit a tool_start
        event for web_search even on a query that would otherwise trigger it."""
        thread_id = create_thread(authed_client, "toggle off")
        events = _stream_chat(auth_headers, {
            "thread_id": thread_id,
            "message": "What is the latest news on Indonesian contract law in 2026?",
            "web_search": False,
        })
        assert events, "no SSE events received"
        assert events[-1].get("done") is True, "stream did not complete"
        assert not _web_search_dispatched(events), (
            "web_search must not be dispatched when toggle=false"
        )

    def test_toggle_on_allows_dispatch(self, authed_client, auth_headers):
        """When toggle=true and admin web_search_enabled=true, web_search may
        dispatch. We only assert the stream completes cleanly."""
        thread_id = create_thread(authed_client, "toggle on")
        events = _stream_chat(auth_headers, {
            "thread_id": thread_id,
            "message": "Latest 2026 news on Indonesian regulatory updates",
            "web_search": True,
        })
        assert events, "no SSE events received"
        assert events[-1].get("done") is True, "stream must complete cleanly"

    def test_omitted_field_uses_user_default(self, authed_client, auth_headers):
        """When web_search field is omitted, user_preferences.web_search_default
        decides. Default for the test user is False, so web_search must not
        dispatch."""
        thread_id = create_thread(authed_client, "toggle default")
        events = _stream_chat(auth_headers, {
            "thread_id": thread_id,
            "message": "Latest news about Indonesian contract law",
            # web_search field intentionally omitted
        })
        assert events, "no SSE events received"
        assert events[-1].get("done") is True, "stream did not complete"
        assert not _web_search_dispatched(events), (
            "web_search must not dispatch when user default is False"
        )
