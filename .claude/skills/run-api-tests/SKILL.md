---
name: run-api-tests
description: Run the backend API test suite (41 tests across 5 files) with proper env setup
disable-model-invocation: true
---

# Run API Tests

Run the LexCore backend API test suite against the production backend.

## Prerequisites

- Python venv at `backend/venv/`
- Test credentials configured (test@test.com and test-2@test.com)
- Production backend running at https://api-production-cde1.up.railway.app

## Steps

### 1. Activate venv and run tests

```bash
cd backend && source venv/bin/activate && \
  TEST_EMAIL="test@test.com" \
  TEST_PASSWORD='!*-3-3?3uZ?b$v&' \
  TEST_EMAIL_2="test-2@test.com" \
  TEST_PASSWORD_2='fK4$Wd?HGKmb#A2' \
  API_BASE_URL="https://api-production-cde1.up.railway.app" \
  pytest tests/api/ -v --tb=short
```

### 2. Report results

Print:
- Total tests passed/failed/skipped
- Any failures with short tracebacks
- Test file breakdown (documents, chat, security, settings, agents)

### 3. Run RAG evaluation golden set

After API tests pass, run the RAG retrieval quality evaluation:

```bash
cd backend && source venv/bin/activate && \
  API_BASE_URL="https://api-production-cde1.up.railway.app" \
  TEST_EMAIL="test@test.com" \
  TEST_PASSWORD='!*-3-3?3uZ?b$v&' \
  pytest scripts/eval_rag.py -v --tb=short
```

Report: keyword hit rate, MRR, queries with hits.

### Optional: Run against local backend

If the user says "local" or "localhost", use:
```bash
API_BASE_URL="http://localhost:8000"
```

instead of the production URL for both steps.
