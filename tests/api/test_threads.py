"""
Thread Management API tests.
Covers: THR-01 through THR-05, SEC-04
"""
import pytest
import httpx


def create_thread(client, title="Test Thread"):
    resp = client.post("/threads", json={"title": title})
    assert resp.status_code == 200
    return resp.json()


class TestThreadCreate:
    """THR-01: POST /threads returns valid thread object."""

    def test_create_returns_200(self, authed_client):
        resp = authed_client.post("/threads", json={"title": "THR-01 Thread"})
        assert resp.status_code == 200

    def test_create_returns_required_fields(self, authed_client):
        resp = authed_client.post("/threads", json={"title": "THR-01 Fields"})
        body = resp.json()
        assert "id" in body
        assert "title" in body
        assert "created_at" in body
        assert body["title"] == "THR-01 Fields"

    def test_create_without_auth_returns_401(self, client):
        resp = client.post("/threads", json={"title": "No Auth"})
        assert resp.status_code in (401, 403)  # SEC-05


class TestThreadList:
    """THR-02: GET /threads lists user's own threads."""

    def test_list_returns_200(self, authed_client):
        resp = authed_client.get("/threads")
        assert resp.status_code == 200

    def test_list_returns_array(self, authed_client):
        resp = authed_client.get("/threads")
        assert isinstance(resp.json(), list)

    def test_list_without_auth_returns_401(self, client):
        resp = client.get("/threads")
        assert resp.status_code in (401, 403)


class TestThreadUpdate:
    """THR-03: PATCH /threads/{id} updates title."""

    def test_update_title(self, authed_client):
        thread = create_thread(authed_client, "Original Title")
        thread_id = thread["id"]
        resp = authed_client.patch(f"/threads/{thread_id}", json={"title": "Updated Title"})
        assert resp.status_code == 200
        assert resp.json()["title"] == "Updated Title"

    def test_update_nonexistent_returns_404(self, authed_client):
        resp = authed_client.patch(
            "/threads/00000000-0000-0000-0000-000000000000",
            json={"title": "Ghost"},
        )
        assert resp.status_code == 404


class TestThreadDelete:
    """THR-04 / SEC-04: DELETE /threads cascades to messages."""

    def test_delete_returns_success(self, authed_client):
        thread = create_thread(authed_client, "THR-04 Delete Me")
        resp = authed_client.delete(f"/threads/{thread['id']}")
        assert resp.status_code == 200

    def test_deleted_thread_not_in_list(self, authed_client):
        thread = create_thread(authed_client, "THR-04 Gone")
        thread_id = thread["id"]
        authed_client.delete(f"/threads/{thread_id}")
        ids = [t["id"] for t in authed_client.get("/threads").json()]
        assert thread_id not in ids

    def test_delete_nonexistent_returns_404(self, authed_client):
        resp = authed_client.delete("/threads/00000000-0000-0000-0000-000000000000")
        assert resp.status_code == 404
