# Test Suite Plan — Agentic RAG Masterclass

## Purpose

This test suite validates all built features. An agent can run it after any code change to verify nothing is broken. Tests are deterministic, isolated, and self-documenting.

## Structure

```
tests/
├── e2e/                   # Playwright browser tests (UI flows)
│   ├── playwright.config.ts
│   ├── helpers.ts         # Login helper, shared utilities
│   ├── auth.spec.ts       # Authentication (6 tests)
│   ├── chat.spec.ts       # Chat UI + streaming (6 tests)
│   ├── documents.spec.ts  # Document upload + realtime (7 tests)
│   └── settings.spec.ts   # Model settings (4 tests)
├── api/                   # pytest + httpx (backend API tests)
│   ├── conftest.py        # Fixtures: JWT token, HTTP client
│   ├── test_threads.py    # Thread CRUD (7 tests)
│   ├── test_chat.py       # SSE streaming (4 tests)
│   ├── test_documents.py  # Document upload/list/delete (8 tests)
│   ├── test_settings.py   # Settings CRUD + lock (6 tests)
│   └── test_security.py   # RLS isolation (5 tests)
├── fixtures/
│   ├── sample.txt         # Test document (plain text)
│   └── sample.md          # Test document (markdown)
└── README.md              # How to run
```

## Running the Suite

### Prerequisites
- Backend running: `cd backend && source venv/bin/activate && uvicorn app.main:app --port 8000`
- Frontend running: `cd frontend && npm run dev`
- Test credentials in `.env` / CLAUDE.md (`test@test.com`)

### Run all
```bash
# API tests
cd tests/api && pip install -r requirements.txt && pytest -v

# E2E tests
cd tests/e2e && npx playwright test --reporter=list
```

### Run specific group
```bash
pytest tests/api/test_threads.py -v          # threads only
npx playwright test tests/e2e/auth.spec.ts   # auth only
```

---

## Test Registry with Acceptance Criteria

### GROUP 1: Authentication (E2E)

| ID | Name | Type | Pass Criteria | Fail Signal |
|----|------|------|---------------|-------------|
| AUTH-01 | Unauthenticated redirect | E2E | Navigate to `/` → URL becomes `/auth`, auth form visible | URL stays on `/`, no redirect |
| AUTH-02 | Invalid login shows error | E2E | Submit wrong credentials → red error text "Invalid login credentials" visible, URL stays `/auth` | No error shown, or redirect happens |
| AUTH-03 | Valid login redirects to chat | E2E | Login with test@test.com → URL becomes `/`, sidebar with "RAG Chat" visible | URL stays `/auth`, or error shown |
| AUTH-04 | Session persistence across refresh | E2E | After login, reload page → stays on `/`, still logged in, threads loaded | Redirected to `/auth` after reload |
| AUTH-05 | Sign out redirects to auth | E2E | Click sign-out button → URL becomes `/auth`, auth form visible | URL stays on `/`, session persists |
| AUTH-06 | Protected routes redirect when logged out | E2E | Navigate to `/documents` without auth → URL becomes `/auth` | `/documents` renders without auth |

---

### GROUP 2: Thread Management (API + E2E)

| ID | Name | Type | Pass Criteria | Fail Signal |
|----|------|------|---------------|-------------|
| THR-01 | Create thread via API | API | `POST /threads` with JWT → 200, body has `id` (UUID), `title`, `created_at`; DB row exists | Non-200 status, missing fields |
| THR-02 | List threads returns user's own | API | `GET /threads` → 200, array; all items have `user_id` matching auth user | 401, or items from other users |
| THR-03 | Update thread title | API | `PATCH /threads/{id}` with `{"title":"New Title"}` → 200, returned `title` equals "New Title"; DB reflects change | 404, 401, or title unchanged |
| THR-04 | Delete thread cascades to messages | API | `DELETE /threads/{id}` → 200 `{"ok": true}`; thread no longer in `GET /threads`; all messages with that `thread_id` gone from DB | 404, or thread/messages still exist |
| THR-05 | Can't access another user's thread | API | `GET /threads/{id}` using a thread ID belonging to a different user → 404 or empty | 200 with other user's data |
| THR-06 | Create thread appears in UI sidebar | E2E | Click "New Thread" → new item appears in sidebar list; input area shows with placeholder | Button unresponsive, thread not visible |
| THR-07 | Delete thread removes from sidebar | E2E | Click delete icon on thread → thread disappears from list; message area shows empty state | Thread still in list after click |

---

### GROUP 3: Chat Streaming (API + E2E)

| ID | Name | Type | Pass Criteria | Fail Signal |
|----|------|------|---------------|-------------|
| CHAT-01 | POST /chat/stream returns SSE | API | Response Content-Type is `text/event-stream`; receives at least one `data:` line; last event has `"done":true` | Non-stream response, no events, missing `done` |
| CHAT-02 | Messages persisted after streaming | API | After `POST /chat/stream` completes → `GET /threads/{id}/messages` (or DB query) shows user message + assistant message | Messages not saved, only one role saved |
| CHAT-03 | Stateless history: follow-up uses prior context | E2E | Send "My name is TestUser." → then "What's my name?" → response contains "TestUser" | Second response has no knowledge of first |
| CHAT-04 | Chat stream displays in real time | E2E | Type message, press Enter → user bubble appears immediately; assistant bubble starts filling token-by-token; input disabled during stream | No optimistic message, no streaming display |
| CHAT-05 | Thread 404 on invalid ID | API | `POST /chat/stream` with non-existent `thread_id` → 404 response | 500, 200, or stream starts anyway |
| CHAT-06 | Unauthenticated stream rejected | API | `POST /chat/stream` with no Authorization header → 401 or 403 | 200, or stream starts |

---

### GROUP 4: Document Ingestion (API + E2E)

| ID | Name | Type | Pass Criteria | Fail Signal |
|----|------|------|---------------|-------------|
| DOC-01 | Upload TXT file returns 202 | API | `POST /documents/upload` with .txt file → 202, body has `id`, `filename`, `status: "pending"` | Non-202, missing fields |
| DOC-02 | Ingestion completes: status=completed, chunks>0 | API | After upload, poll `GET /documents` until status=`"completed"` (max 30s) → `chunk_count` ≥ 1 | Status stays pending/processing/failed after 30s |
| DOC-03 | Unsupported file type returns 400 | API | Upload `.docx` file → 400, error body mentions unsupported type | 202 or 500 |
| DOC-04 | Empty file returns 400 | API | Upload file with 0 bytes → 400 | 202 |
| DOC-05 | List documents shows user's own | API | `GET /documents` → 200, array; all items have correct fields | 401, items from other users |
| DOC-06 | Delete document removes chunks | API | `DELETE /documents/{id}` → 204; document gone from `GET /documents`; DB: no `document_chunks` with that `document_id` | 404, or document/chunks remain |
| DOC-07 | Realtime status update in UI | E2E | Upload file in UI → status badge changes from `pending` → `processing` → `completed` without page refresh | Badge stays "pending", requires refresh to see change |
| DOC-08 | Upload and delete via UI | E2E | Upload file → appears in list; click delete → disappears from list | File stays after delete click |

---

### GROUP 5: RAG Retrieval (Integration)

| ID | Name | Type | Pass Criteria | Fail Signal |
|----|------|------|---------------|-------------|
| RAG-01 | Document content retrieved in chat | E2E | Upload `sample.txt` (contains "The capital of France is Paris"), ask "What is the capital of France?" → response mentions "Paris" | Response says "I don't know" or ignores document |
| RAG-02 | No context injection when no docs | API | `POST /chat/stream` with no documents uploaded → system prompt has no "Use the following context" prefix | Context prefix in prompt even with no docs |
| RAG-03 | Irrelevant query gets no context | API | Upload document about France; ask "What is 2+2?" → response is "4" without document context injected (similarity below threshold) | Irrelevant chunks injected into every query |

---

### GROUP 6: Settings (API + E2E)

| ID | Name | Type | Pass Criteria | Fail Signal |
|----|------|------|---------------|-------------|
| SET-01 | Default settings created on first GET | API | `GET /settings` for new user → 200, `llm_model: "openai/gpt-4o-mini"`, `embedding_model: "text-embedding-3-small"`, `embedding_locked: false` | 404, or wrong defaults |
| SET-02 | LLM model change saves | API | `PATCH /settings {"llm_model": "anthropic/claude-3-haiku"}` → 200; subsequent `GET /settings` returns `llm_model: "anthropic/claude-3-haiku"` | 400, or GET returns old value |
| SET-03 | Embedding model locked when docs exist | API | Upload a document (wait for completion); `PATCH /settings {"embedding_model": "text-embedding-ada-002"}` → 409, error message mentions "Delete all documents" | 200 (should be 409) |
| SET-04 | Invalid embedding model rejected | API | `PATCH /settings {"embedding_model": "text-embedding-3-large"}` → 400, error lists allowed models | 200, or 500 |
| SET-05 | Empty LLM model rejected | API | `PATCH /settings {"llm_model": ""}` → 400 | 200 |
| SET-06 | Embedding lock visible in UI | E2E | With documents indexed, navigate to `/settings` → Embedding Model section shows lock badge; radio buttons are disabled | No lock badge, radios are enabled |

---

### GROUP 7: Security / RLS (API)

| ID | Name | Type | Pass Criteria | Fail Signal |
|----|------|------|---------------|-------------|
| SEC-01 | Thread RLS: user sees only own | API | User A creates thread; User B `GET /threads` → User A's thread NOT in list | User A's thread visible to User B |
| SEC-02 | Thread RLS: user can't delete other's | API | User A creates thread; User B `DELETE /threads/{A_thread_id}` → 404 | 200/204 (deletion succeeds) |
| SEC-03 | Document RLS: user sees only own | API | User A uploads document; User B `GET /documents` → User A's document NOT in list | User A's document visible to User B |
| SEC-04 | Messages cascade-delete with thread | API | Delete thread → verify `messages` table has no rows with that `thread_id` | Messages remain after thread deletion |
| SEC-05 | Unauthenticated API requests rejected | API | All endpoints without Authorization header → 401 or 403 for every protected route | Any protected route returns 200 without auth |

---

### GROUP 8: Navigation & Routing (E2E)

| ID | Name | Type | Pass Criteria | Fail Signal |
|----|------|------|---------------|-------------|
| NAV-01 | Documents icon navigates to /documents | E2E | Click folder icon in chat sidebar → URL becomes `/documents`, documents page rendered | URL unchanged, or 404 page |
| NAV-02 | Settings icon navigates to /settings | E2E | Click gear icon → URL becomes `/settings`, settings form rendered | URL unchanged |
| NAV-03 | Back arrow returns to previous page | E2E | From `/documents`, click back arrow → URL becomes `/` | URL unchanged, or goes to `/auth` |
| NAV-04 | Unknown route redirects to / | E2E | Navigate to `/nonexistent` → redirects to `/` | 404 page shown, or stays on `/nonexistent` |

---

## Pass/Fail Scoring

A test **PASSES** if ALL assertions in "Pass Criteria" are satisfied.
A test **FAILS** if ANY assertion in "Fail Criteria" is triggered, OR if it throws an unhandled error.

### Suite Health Thresholds

| Score | Meaning | Recommended Action |
|-------|---------|-------------------|
| 41/41 (100%) | All green | Safe to ship |
| 37–40 (90–99%) | Minor issues | Investigate failures before shipping |
| 30–36 (73–89%) | Degraded | Fix failures before shipping |
| < 30 (< 73%) | Broken | Do not ship, investigate root cause |

---

## Known Limitations

1. **RAG-03**: Hard to assert "no context injected" without log inspection — may verify via LangSmith traces instead
2. **SEC-01/SEC-02/SEC-03**: Requires two test accounts. Use service role key + direct DB query as alternative
3. **CHAT-03**: Relies on model having good instruction-following — may flake if LLM response varies
4. **DOC-07**: Realtime test requires Supabase Realtime to be enabled on `documents` table
