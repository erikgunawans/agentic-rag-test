# Test Suite

Automated validation for the Agentic RAG Masterclass app. Run after any code change to verify nothing is broken.

## Prerequisites

Services must be running before any tests:

```bash
# Terminal 1 — Backend
cd backend && source venv/bin/activate && uvicorn app.main:app --host 0.0.0.0 --port 8000

# Terminal 2 — Frontend
cd frontend && npm run dev
```

Test credentials are stored in `CLAUDE.md` (Testing section). Tests read from `backend/.env` automatically.

---

## API Tests (pytest)

Tests every backend endpoint directly with HTTP calls.

### Setup (once)

```bash
cd tests/api
pip install -r requirements.txt
```

### Run

```bash
# All API tests
cd tests/api && pytest -v

# Specific group
pytest test_threads.py -v
pytest test_chat.py -v
pytest test_documents.py -v
pytest test_settings.py -v
pytest test_security.py -v

# With summary
pytest -v --tb=short
```

### What's tested

| File | Tests | Description |
|------|-------|-------------|
| `test_threads.py` | 10 | Thread CRUD, auth enforcement |
| `test_chat.py` | 5 | SSE streaming, error handling |
| `test_documents.py` | 10 | Upload, ingestion, list, delete |
| `test_settings.py` | 7 | Settings CRUD, validation, lock |
| `test_security.py` | 9 | RLS, unauthenticated rejection |

---

## E2E Tests (Playwright)

Tests the browser UI end-to-end.

### Setup (once)

```bash
cd tests/e2e
npm init -y
npm install --save-dev @playwright/test
npx playwright install chromium
```

### Run

```bash
# All E2E tests
cd tests/e2e && npx playwright test

# Specific spec
npx playwright test auth.spec.ts
npx playwright test chat.spec.ts
npx playwright test documents.spec.ts
npx playwright test settings.spec.ts

# With UI (headed mode for debugging)
npx playwright test --headed

# With HTML report
npx playwright test --reporter=html && npx playwright show-report
```

### What's tested

| File | Tests | Description |
|------|-------|-------------|
| `auth.spec.ts` | 8 | Auth redirect, login, session, logout |
| `chat.spec.ts` | 6 | Thread UI, streaming, history, navigation |
| `documents.spec.ts` | 4 | Upload, delete, realtime status, RAG |
| `settings.spec.ts` | 3 | Settings UI, save, embedding lock |

---

## Test IDs & Acceptance Criteria

See `.agent/plans/test-suite.md` for the full test registry with acceptance criteria for each test.

### Pass/Fail Thresholds

| Score | Status |
|-------|--------|
| 41/41 (100%) | ✅ All green — safe to ship |
| 37–40 (90–99%) | ⚠️ Minor issues — investigate before shipping |
| 30–36 (73–89%) | ❌ Degraded — fix before shipping |
| < 30 (< 73%) | 🚨 Broken — do not ship |

---

## For Agents

To run the full suite autonomously:

```bash
# Step 1: Verify services are running
curl http://localhost:8000/health   # should return {"status":"ok"}
curl http://localhost:5173          # should return HTML

# Step 2: Run API tests
cd /path/to/project/tests/api
pytest -v --tb=short 2>&1 | tee api-results.txt
echo "API tests: $(grep -c PASSED api-results.txt) passed, $(grep -c FAILED api-results.txt) failed"

# Step 3: Run E2E tests
cd /path/to/project/tests/e2e
npx playwright test --reporter=list 2>&1 | tee e2e-results.txt
echo "E2E: $(grep -c '✓' e2e-results.txt) passed, $(grep -c '✗' e2e-results.txt) failed"
```

If any tests fail, check `.agent/plans/test-suite.md` for the acceptance criteria of that test ID to understand what the expected behavior is.
