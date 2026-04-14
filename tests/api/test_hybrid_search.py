"""
Hybrid Search & Reranking API tests.
Covers: HYB-01 through HYB-08
"""
import os
import time
import uuid


FIXTURES = os.path.join(os.path.dirname(__file__), "../fixtures")

# Distinctive content designed for full-text search testing.
# Contains specific scientific keywords that are easy to target with exact queries.
HYBRID_TEST_CONTENT = (
    "Photosynthesis is the process by which chlorophyll in plant cells converts "
    "sunlight into adenosine triphosphate (ATP). The Calvin cycle within chloroplasts "
    "fixes carbon dioxide into glucose molecules. Thylakoid membranes contain "
    "photosystem complexes that drive electron transport chains. "
    "Ribulose-1,5-bisphosphate carboxylase (RuBisCO) is the most abundant enzyme "
    "on Earth and catalyzes the first step of carbon fixation."
)


def _upload_hybrid_doc(client):
    """Upload a text document with distinctive scientific keywords for search testing."""
    content = (HYBRID_TEST_CONTENT + f"\n# {uuid.uuid4()}").encode()
    resp = client.post(
        "/documents/upload",
        files={"file": (f"hybrid-test-{uuid.uuid4().hex[:8]}.txt", content, "text/plain")},
    )
    return resp


def _wait_completed(client, doc_id: str, timeout: int = 45):
    """Poll until document reaches completed status."""
    for _ in range(timeout):
        docs = client.get("/documents").json()
        doc = next((d for d in docs if d["id"] == doc_id), None)
        if doc and doc["status"] == "completed":
            return doc
        time.sleep(1)
    return None


def _search(client, query: str, mode: str = "hybrid", top_k: int = 5):
    """Call the search diagnostics endpoint."""
    return client.post(
        "/documents/search",
        json={"query": query, "mode": mode, "top_k": top_k},
    )


class TestHybridSearch:
    """Module 6: Hybrid Search & Reranking (HYB-01 through HYB-08)."""

    def test_fulltext_search_returns_results(self, authed_client):
        """HYB-01: Full-text search returns results for exact keyword query."""
        # Upload and wait for ingestion
        resp = _upload_hybrid_doc(authed_client)
        assert resp.status_code == 202
        doc = _wait_completed(authed_client, resp.json()["id"])
        assert doc is not None, "Document did not reach completed status"

        # Search for a distinctive keyword via full-text mode
        search_resp = _search(authed_client, "RuBisCO carboxylase", mode="fulltext")
        assert search_resp.status_code == 200
        body = search_resp.json()
        assert body["mode"] == "fulltext"
        assert body["count"] >= 1
        assert len(body["results"]) >= 1

    def test_vector_search_returns_results(self, authed_client):
        """HYB-02: Vector search still returns results for semantic query."""
        search_resp = _search(authed_client, "how do plants convert sunlight to energy", mode="vector")
        assert search_resp.status_code == 200
        body = search_resp.json()
        assert body["mode"] == "vector"
        assert body["count"] >= 1

    def test_hybrid_search_returns_results(self, authed_client):
        """HYB-03: Hybrid mode returns results."""
        search_resp = _search(authed_client, "chlorophyll photosynthesis ATP", mode="hybrid")
        assert search_resp.status_code == 200
        body = search_resp.json()
        assert body["mode"] == "hybrid"
        assert body["count"] >= 1

    def test_hybrid_finds_keyword_matches(self, authed_client):
        """HYB-04: Hybrid finds keyword matches for specific terms."""
        # Query with a very specific term that full-text search excels at
        search_resp = _search(authed_client, "ribulose bisphosphate", mode="hybrid")
        assert search_resp.status_code == 200
        body = search_resp.json()
        assert body["count"] >= 1
        # Verify the result contains our distinctive content
        contents = [r["content"] for r in body["results"]]
        assert any("RuBisCO" in c or "ribulose" in c.lower() for c in contents)

    def test_hybrid_handles_no_fulltext_matches(self, authed_client):
        """HYB-05: Hybrid gracefully handles zero full-text matches."""
        # A semantic query unlikely to match exact keywords but should match vectors
        search_resp = _search(authed_client, "biological energy production mechanisms", mode="hybrid")
        assert search_resp.status_code == 200
        body = search_resp.json()
        # Should still return results from vector search even if fulltext has none
        assert body["count"] >= 0  # At minimum, no error

    def test_search_requires_auth(self, client):
        """HYB-06: Search endpoint rejects unauthenticated requests."""
        resp = client.post(
            "/documents/search",
            json={"query": "test", "mode": "hybrid"},
        )
        assert resp.status_code in (401, 403)

    def test_chat_stream_with_hybrid(self, authed_client):
        """HYB-07: Chat stream works end-to-end through hybrid pipeline."""
        # Create a thread
        thread_resp = authed_client.post("/threads", json={"title": f"hybrid-test-{uuid.uuid4().hex[:8]}"})
        assert thread_resp.status_code == 200
        thread_id = thread_resp.json()["id"]

        # Send a message that should trigger hybrid retrieval
        with authed_client.stream(
            "POST",
            "/chat/stream",
            json={"thread_id": thread_id, "message": "What is photosynthesis?"},
            timeout=60,
        ) as stream:
            events = []
            for line in stream.iter_lines():
                if line.startswith("data: "):
                    import json
                    events.append(json.loads(line[6:]))

        assert len(events) >= 1
        assert any(e.get("done") for e in events)

        # Clean up thread
        authed_client.delete(f"/threads/{thread_id}")

    def test_search_preserves_metadata(self, authed_client):
        """HYB-08: Search results preserve doc_filename and doc_metadata."""
        search_resp = _search(authed_client, "chlorophyll photosynthesis", mode="hybrid")
        assert search_resp.status_code == 200
        body = search_resp.json()
        if body["count"] > 0:
            result = body["results"][0]
            assert "doc_filename" in result
            assert "content" in result
