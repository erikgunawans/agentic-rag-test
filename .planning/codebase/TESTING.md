# Testing Patterns

**Analysis Date:** 2026-04-25

## Test Framework

**Backend (API tests):**
- pytest 8.3.2 with pytest-asyncio 0.24.0 (`tests/api/requirements.txt`).
- httpx 0.27.2 for HTTP requests against a running FastAPI server.
- python-dotenv 1.0.1 to load `backend/.env` for credentials.
- No `pytest.ini` or `pyproject.toml` config — pytest discovers tests from `tests/api/`.

**Frontend (E2E):**
- Playwright (`tests/e2e/playwright.config.ts`).
- TypeScript specs (`auth.spec.ts`, `chat.spec.ts`, `documents.spec.ts`, `settings.spec.ts`).
- No frontend unit tests detected — no `vitest.config.*`, no `jest.config.*`, no `*.test.ts(x)` or `*.spec.ts(x)` files inside `frontend/src/`.

**RAG Evaluation:**
- `backend/scripts/eval_rag.py` runs as a standalone script or pytest module.
- 20-query Indonesian legal "golden set" — measures keyword hit rate and MRR.

**Assertion Library:** Built-in `assert` for pytest. Playwright `expect()` for E2E.

## Run Commands

```bash
# Setup (once)
cd tests/api && pip install -r requirements.txt

# All API tests against local backend
cd tests/api && pytest -v

# Specific groups
pytest test_threads.py -v
pytest test_chat.py -v
pytest test_documents.py -v
pytest test_settings.py -v
pytest test_security.py -v
pytest test_agents.py -v
pytest test_hybrid_search.py -v
pytest test_tools.py -v

# All API tests against deployed backend (CI-style)
cd backend && source venv/bin/activate && \
  TEST_EMAIL="test@test.com" TEST_PASSWORD='!*-3-3?3uZ?b$v&' \
  TEST_EMAIL_2="test-2@test.com" TEST_PASSWORD_2='fK4$Wd?HGKmb#A2' \
  API_BASE_URL="https://api-production-cde1.up.railway.app" \
  pytest tests/api/ -v --tb=short

# Skill: runs the above + the RAG eval golden set
/run-api-tests

# E2E (Playwright)
cd tests/e2e && npx playwright test
npx playwright test auth.spec.ts
npx playwright test --headed
npx playwright test --reporter=html && npx playwright show-report

# RAG eval golden set
cd backend && python -m scripts.eval_rag --base-url http://localhost:8000 --token <JWT>
cd backend && pytest scripts/eval_rag.py -v
```

## Test File Organization

**Location:**
- API tests live at the **repo root** under `tests/api/`, NOT under `backend/tests/`. Intentional — the test suite is a top-level concern, not bundled with the backend package.
- Test fixtures (sample docs) at `tests/fixtures/`.
- E2E specs at `tests/e2e/` with `helpers.ts` and `playwright.config.ts`.

**Naming:**
- Python: `test_<area>.py` mirroring the router (`test_chat.py` ↔ `backend/app/routers/chat.py`).
- E2E: `<area>.spec.ts`.

**Structure:**
```
tests/
├── api/
│   ├── conftest.py                # jwt_token, auth_headers, client, authed_client
│   ├── requirements.txt           # pytest, httpx, python-dotenv
│   ├── test_threads.py            # 10 tests
│   ├── test_chat.py               # 5 tests — SSE streaming
│   ├── test_documents.py          # 10 tests — upload/ingestion/dedup
│   ├── test_settings.py           # 7 tests
│   ├── test_security.py           # 9 tests — RLS, unauth rejection
│   ├── test_agents.py             # multi-agent classification
│   ├── test_hybrid_search.py      # vector + fulltext + RRF fusion
│   └── test_tools.py              # tool dispatch
├── e2e/
│   ├── playwright.config.ts
│   ├── helpers.ts
│   ├── auth.spec.ts               # 8 tests
│   ├── chat.spec.ts               # 6 tests
│   ├── documents.spec.ts          # 4 tests
│   └── settings.spec.ts           # 3 tests
└── fixtures/
    ├── sample.csv
    ├── sample.docx
    ├── sample.html
    ├── sample.json
    ├── sample.txt
    └── sample_indonesian_nda.txt
```

## Test Structure (pytest)

```python
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


class TestChatEdgeCases:
    """CHAT-05/06: Error handling."""

    def test_unauthenticated_returns_401(self, client):
        resp = client.post("/chat/stream", json={"thread_id": "...", "message": "hi"})
        assert resp.status_code in (401, 403)
```

**Patterns:**
- Group related tests under a `TestX` class with a docstring naming the test ID range (`CHAT-01`, `SEC-05`, `DOC-02`).
- Module docstring at the top lists coverage IDs for the file.
- Helper functions defined at module scope above the classes (`create_thread`, `upload_txt`).
- One assertion concept per test; multiple `assert` lines fine when verifying related fields.
- Parametrize tabular cases with `@pytest.mark.parametrize("method,path", PROTECTED_ROUTES)` — see `TestUnauthenticatedRejection` in `tests/api/test_security.py`.

## Fixtures

**Shared fixtures (`tests/api/conftest.py`):**

```python
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "../../backend/.env"))

API_BASE = os.getenv("TEST_API_BASE", "http://localhost:8000")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
TEST_EMAIL = os.getenv("TEST_EMAIL", "test@test.com")
TEST_PASSWORD = os.getenv("TEST_PASSWORD", "!*-3-3?3uZ?b$v&")


@pytest.fixture(scope="session")
def jwt_token():
    """Session-scoped JWT — authenticates once per test run."""
    return get_jwt(TEST_EMAIL, TEST_PASSWORD)


@pytest.fixture(scope="session")
def auth_headers(jwt_token):
    return {"Authorization": f"Bearer {jwt_token}"}


@pytest.fixture(scope="session")
def client():
    """Shared httpx client."""
    with httpx.Client(base_url=API_BASE, timeout=30) as c:
        yield c


@pytest.fixture()
def authed_client(client, auth_headers):
    """Client with auth headers pre-set."""
    client.headers.update(auth_headers)
    yield client
    client.headers.pop("Authorization", None)
```

**Setup pattern:**
- `client` and `jwt_token` are session-scoped — auth happens once per pytest invocation, not per test.
- `authed_client` is function-scoped and resets `Authorization` after each test, so an "unauthenticated" test (using bare `client`) doesn't pick up a stale token.
- The dotenv path resolves up two levels to `backend/.env`. Tests fail fast if `SUPABASE_URL` / `SUPABASE_ANON_KEY` are missing.

**Test data fixtures:**
- Static fixture files in `tests/fixtures/` (sample documents).
- Dynamic uniqueness: `test_documents.py` appends a UUID comment to each upload to dodge content-hash dedup (`upload_txt` helper).
- Parametrized routes for blanket auth tests:
  ```python
  PROTECTED_ROUTES = [
      ("GET",   "/threads"),
      ("POST",  "/threads"),
      ("GET",   "/documents"),
      ("POST",  "/documents/upload"),
      ("GET",   "/settings"),
      ("PATCH", "/settings"),
      ("POST",  "/chat/stream"),
  ]
  ```

## Mocking

**Approach: NO MOCKING.** Tests run against real services.

- The pytest suite hits a **live FastAPI backend** (local `http://localhost:8000` or deployed `https://api-production-cde1.up.railway.app`).
- That backend talks to the **real Supabase project** (`qedhulpfezucnfadlfiz`), the **real OpenRouter API** (chat + tool calling), and the **real OpenAI API** (embeddings).
- Chat tests issue actual model prompts ("Say exactly: hello", "Reply with a single word: yes") and assert on observable side effects — content-type header, presence of `delta` events, presence of a final `done: true` SSE event.
- Document tests poll real ingestion (`for _ in range(45): time.sleep(1)`) waiting for `status` to flip to `completed`.
- Test users (`test@test.com`, `test-2@test.com`) are real Supabase Auth accounts; their data persists in production-grade tables.

**Implications:**
- Tests cost real LLM tokens and embedding calls. Don't run the full suite in tight loops.
- Tests can fail for **infrastructure** reasons (Supabase outage, OpenRouter rate limit) unrelated to the code under change. Read failures carefully before "fixing" them.
- Cleanup is partial — `test_security.py` deletes the threads it creates, `test_documents.py` mostly does not. Shared test accounts accumulate test data over time.

**What is NOT mocked:**
- Supabase Auth, RLS, Postgres, Storage, Realtime.
- OpenRouter (chat completions, tool-calling).
- OpenAI embeddings.
- LangSmith (writes traces during test runs).

**What COULD be mocked but isn't:** anything. There are no `unittest.mock`, `monkeypatch`, or fixture overrides anywhere in the suite.

## Coverage

**Requirements:** No coverage tool configured (`tests/api/requirements.txt` lacks `coverage` / `pytest-cov`). No coverage gates enforced.

**Test count by area (per `tests/README.md`):**

| File | Tests | Description |
|------|-------|-------------|
| `tests/api/test_threads.py` | 10 | Thread CRUD, auth enforcement |
| `tests/api/test_chat.py` | 5 | SSE streaming, error handling |
| `tests/api/test_documents.py` | 10 | Upload, ingestion, list, delete |
| `tests/api/test_settings.py` | 7 | Settings CRUD, validation, lock |
| `tests/api/test_security.py` | 9 | RLS, unauthenticated rejection |
| `tests/api/test_agents.py` | (?) | Multi-agent classification |
| `tests/api/test_hybrid_search.py` | (?) | Hybrid retrieval pipeline |
| `tests/api/test_tools.py` | (?) | Tool dispatch |
| `tests/e2e/auth.spec.ts` | 8 | Auth redirect, login, session, logout |
| `tests/e2e/chat.spec.ts` | 6 | Thread UI, streaming, history, navigation |
| `tests/e2e/documents.spec.ts` | 4 | Upload, delete, realtime status, RAG |
| `tests/e2e/settings.spec.ts` | 3 | Settings UI, save, embedding lock |

**Pass/fail thresholds (from `tests/README.md`):**

| Score | Status |
|-------|--------|
| 41/41 (100%) | All green — safe to ship |
| 37–40 (90–99%) | Minor issues — investigate before shipping |
| 30–36 (73–89%) | Degraded — fix before shipping |
| < 30 (< 73%) | Broken — do not ship |

## Test Types

**Unit tests:** None at the unit level. Closest analogues are `test_hybrid_search.py` and `test_tools.py`, which exercise individual services through HTTP endpoints.

**Integration / API tests (pytest):** All 8 files in `tests/api/` are integration by nature — real HTTP, real DB, real LLM. Coverage spans: thread CRUD, SSE chat streaming, document upload/ingestion/dedup, settings, RLS isolation, multi-agent routing, hybrid retrieval, tool execution.

**E2E tests (Playwright):** 4 spec files in `tests/e2e/` covering auth, chat, documents, settings. Run against the live frontend (default `http://localhost:5173`).

**RAG evaluation:**
- `backend/scripts/eval_rag.py` — 20-query golden set in Indonesian. Categories: regulation lookup (UU PDP, OJK, pengadaan, ketenagakerjaan), contract clause search (force majeure, kerahasiaan, sengketa, ganti rugi), compliance obligations (LHKPN, laporan tahunan, anti pencucian uang, kebocoran data), BJR/risk, semantic recall.
- Each entry: `{query, expected_keywords, category}`.
- Metrics: keyword hit rate (% of expected keywords present in retrieved chunks) and MRR (mean reciprocal rank).
- Runs both as a CLI (`python -m scripts.eval_rag --base-url ... --token ...`) and as pytest tests (`pytest scripts/eval_rag.py -v`).

## Common Patterns

**SSE / async testing:**
```python
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
```

**Polling for async ingestion:**
```python
for _ in range(45):
    docs = authed_client.get("/documents").json()
    doc = next((d for d in docs if d["id"] == doc_id), None)
    if doc["status"] in ("completed", "failed"):
        break
    time.sleep(1)
assert doc["status"] == "completed"
```

**Auth rejection (parametrized):**
```python
@pytest.mark.parametrize("method,path", PROTECTED_ROUTES)
def test_no_auth_rejected(self, client, method, path):
    resp = client.request(method, path)
    assert resp.status_code in (401, 403)
```

**Unique upload (avoid dedup collision):**
```python
def upload_txt(client, filename="sample.txt"):
    path = os.path.join(FIXTURES, filename)
    with open(path, "rb") as f:
        content = f.read() + f"\n# {uuid.uuid4()}".encode()
    return client.post("/documents/upload", files={"file": (filename, content, "text/plain")})
```

**RLS isolation:**
- Tests verify that another user's UUID returns 404, not data leak (`test_cannot_access_nonexistent_thread`, `test_cannot_delete_nonexistent_document` in `tests/api/test_security.py`).
- For two-user scenarios, the suite has `TEST_EMAIL_2`/`TEST_PASSWORD_2` env vars but a second-user fixture is not yet implemented — extend `conftest.py` to add a `jwt_token_2` / `authed_client_2` pair when needed.

## Coverage Gaps and Risks

**No frontend unit tests:** Vitest/Jest is not configured in `frontend/`. The only frontend coverage is via Playwright E2E. Component logic (e.g. `useChatState` branch selection in `frontend/src/hooks/useChatState.ts`, `buildChildrenMap` / `getActivePath` in `frontend/src/lib/messageTree.ts`, `useDocumentRealtime`) is not unit-tested.

**No backend unit tests:** All "tests" hit a live server. Pure-function services like `backend/app/services/document_tool_service.py` (`_extract_text`, Pydantic model validation) are exercised only through the HTTP boundary. A pure-function test layer would speed up the feedback loop and reduce LLM-token cost during dev.

**Limited cross-user RLS testing:** `TEST_EMAIL_2` is plumbed in but the suite mostly relies on "nonexistent UUID returns 404" as the RLS proxy. Real cross-user isolation tests (User A creates → User B reads → expect empty/forbidden) are absent.

**No CI configuration detected:** No `.github/workflows/`, no CircleCI, no GitLab CI. Tests are run manually via `/run-api-tests`. Test failures don't gate PRs.

**No mutation/regression test for migrations:** Numbered migrations 001-027 are blocked from edits via PreToolUse hook, but there's no automated test that re-applies them on a clean database.

**Eval data is small:** 20 queries in `backend/scripts/eval_rag.py`. Adequate for smoke detection, insufficient for tracking subtle retrieval regressions across the 8 RAG hooks (structure-aware chunking, vision OCR, custom embeddings, metadata pre-filtering, bilingual query expansion, weighted fusion, cross-encoder reranking, graph reindex).

**Audit trail not verified:** `log_action` failures are silently swallowed (see `backend/app/services/audit_service.py`) — there's no test that confirms audit rows are written for every mutation. A regression here would never be caught by the suite.

**RAG configuration drift:** Tests use whatever `system_settings` row is currently in the DB (`get_system_settings()` 60s TTL). Tests can pass or fail depending on the admin's last UI change. Pin a known-good config for deterministic RAG tests.

**Test data accumulation:** Most tests don't clean up. The shared `test@test.com` account accumulates threads and documents across runs. Periodically prune via the admin UI or a dedicated cleanup script.

**Pre-push gap:** PostToolUse hook lints frontend (`tsc + eslint`) and backend (`py_compile`) on each file edit, but there's no `pre-push` hook running the full pytest suite. A broken endpoint can land on `master` if the agent forgets to run `/run-api-tests`.

---

*Testing analysis: 2026-04-25*
