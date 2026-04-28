---
title: "ADR-0005: Integration Tests Run Against the Production API"
status: "Accepted"
date: "2026-04-28"
authors: "Erik Gunawan Supriatna (LexCore Engineering)"
tags: ["architecture", "decision", "testing", "ci-cd", "integration-tests"]
supersedes: ""
superseded_by: ""
---

# ADR-0005: Integration Tests Run Against the Production API

## Status

**Accepted** — current convention for the 8 API test suites in `tests/api/` and 5 suites in `backend/tests/api/`. Tests target `https://api-production-cde1.up.railway.app` by default.

## Context

LexCore's integration tests need to exercise the full stack (FastAPI router → service → Supabase → external LLM/RAG providers) end-to-end. The strategy choice was:

- **Mock external dependencies** — stub Supabase, OpenRouter, OpenAI in-process; tests run hermetically.
- **Local containerized stack** — spin up local Postgres + Supabase clone via Docker Compose; tests run against that.
- **Run against the live production API** — tests authenticate as real test accounts and hit the deployed Railway backend.

The team has prior burn experience: in earlier projects, **mocked tests passed while production behavior diverged** because mocks drifted from reality. This is an organizational constraint, not just a preference.

Other considerations:

- **Test fidelity** for a compliance-grade legal platform — wrong answers carry liability.
- **Test feedback latency** — devs need fast turnaround.
- **CI cost** — running tests against production has network/API cost per run.
- **Test data isolation** — tests must not corrupt production data.
- **Schema drift** — local schema vs. production schema can diverge silently.
- **Secret management** — test accounts require real credentials.

## Decision

API integration tests run **directly against the production Railway backend** at `https://api-production-cde1.up.railway.app`, using two dedicated test accounts (`test@test.com` and `test-2@test.com`). Database state is read/written through the live system. Only PII unit tests use mocks (via `conftest.py` Supabase stubs).

## Consequences

### Positive

- **POS-001**: Zero mock/prod divergence — tests verify the *actually deployed* system, not a model of it.
- **POS-002**: Catches Railway-specific issues (cold starts, env var misconfigurations, runtime spaCy download failures, container quirks) that local tests miss.
- **POS-003**: No local infra setup required — new contributors clone the repo and run tests immediately.
- **POS-004**: Tests serve as a smoke test for the deployed system — running them post-deploy gives high signal.
- **POS-005**: Schema drift impossible — tests run against the live schema, so any migration mismatch surfaces immediately.
- **POS-006**: Real LLM responses are tested — RAG eval against the golden 20-query set catches regressions in retrieval quality, not just plumbing.

### Negative

- **NEG-001**: Network dependency — tests require internet and a healthy Railway deployment to run.
- **NEG-002**: Slower per-test latency — every test makes real HTTP round-trips; suite time is in seconds-per-test, not milliseconds.
- **NEG-003**: API cost per run — each test exercise consumes real LLM tokens and Supabase quota.
- **NEG-004**: Test-account state hygiene — accumulated threads, documents, and entity-registry entries from test runs require periodic cleanup.
- **NEG-005**: Cannot test pre-deploy code — only what's already on Railway. Local changes need a deploy-and-test cycle, which slows iteration on backend changes.
- **NEG-006**: Test data and production data share the database — RLS enforces user-level isolation, but the tables themselves are shared.

## Alternatives Considered

### Mocked Supabase + Mocked LLM

- **ALT-001**: **Description**: Replace Supabase client and OpenRouter client with in-process stubs returning canned responses.
- **ALT-002**: **Rejection Reason**: This was tried in a prior project and burned the team — mocked tests passed while production migrations and RLS policies were broken. Mock/prod divergence is a structural risk for compliance-grade systems.

### Local Containerized Stack (Docker Compose)

- **ALT-003**: **Description**: Spin up local Postgres + Supabase emulator + LocalStack for storage; tests run hermetically against this.
- **ALT-004**: **Rejection Reason**: Supabase Auth, Realtime, and pgvector behavior is non-trivial to emulate faithfully. Schema drift between local and production is hard to prevent. Maintenance cost is real and ongoing.

### Hybrid (Unit Tests Mocked + Integration Against Production)

- **ALT-005**: **Description**: This is what we actually do — but the *predominant* strategy is production-API.
- **ALT-006**: **Rejection Reason**: Not actually rejected; this is the chosen pattern. PII unit tests use mocks for unit-level isolation; everything else hits production.

### Staging Environment

- **ALT-007**: **Description**: Deploy a parallel staging Railway instance + Supabase project; tests run against staging.
- **ALT-008**: **Rejection Reason**: Doubles infrastructure cost. Staging-vs-production drift is itself a risk. Considered for the future once the team grows beyond a single backend deployment.

## Implementation Notes

- **IMP-001**: Test base URL is configured via `API_BASE_URL` env var, defaulting to the production URL. Tests can be redirected to localhost for development.
- **IMP-002**: Test accounts have credentials in `conftest.py` fixtures, sourced from env vars (`TEST_EMAIL`, `TEST_PASSWORD`, `TEST_EMAIL_2`, `TEST_PASSWORD_2`).
- **IMP-003**: Auth tokens are minted via `get_token()` per fixture, not cached across runs — this exercises the full Supabase auth flow.
- **IMP-004**: Test names follow ticket-ID convention (`CHAT-01`, `HYB-07`, `SC#5`) to link tests to PRD requirements.
- **IMP-005**: PII tests in `backend/tests/api/` use Supabase stubs from `conftest.py` because the redaction pipeline has hot-path tests that should not depend on network.
- **IMP-006**: RAG eval is a separate script (`scripts/eval_rag.py`) that runs the golden 20-query set and reports keyword hit rate + MRR.
- **IMP-007**: When tests fail post-deploy, rollback is via Railway dashboard or `railway redeploy <previous>`.

## References

- **REF-001**: ADR-0006 — Hybrid Vercel/main Deployment (frontend deploy).
- **REF-002**: `backend/tests/api/conftest.py` — auth fixtures and test client.
- **REF-003**: `tests/api/conftest.py` — same pattern at the repo-root level.
- **REF-004**: `scripts/eval_rag.py` — RAG quality eval golden set.
- **REF-005**: `Project_Architecture_Blueprint.md` Section 10 — Testing Architecture.
- **REF-006**: `CLAUDE.md` — Test accounts and credentials.
