# Changelog

All notable changes to this project will be documented in this file.

## [0.1.0.0] - 2026-04-03

### Added
- **Module 2: BYO Retrieval + Memory** — OpenRouter chat completions with per-user LLM model selection; stateless chat (full thread history loaded from DB and sent with every request); pgvector IVFFlat index for cosine similarity RAG retrieval (top-5 chunks, threshold ≥ 0.3)
- **Document ingestion pipeline** — Upload `.pdf`, `.txt`, `.md` files to Supabase Storage; background task parses (PyMuPDF), chunks (tiktoken, 500t/50 overlap), embeds (OpenAI), and stores vectors in pgvector; Supabase Realtime status updates (pending → processing → completed/failed)
- **Documents UI** — `DocumentsPage`, `FileUpload` (drag-and-drop), `DocumentList` with real-time status badges; nav link in sidebar
- **Settings UI** — Per-user LLM model + embedding model preferences; embedding model locked after documents are indexed; new `user_settings` Supabase table with RLS
- **Module 3: Record Manager** — SHA-256 content hashing for deduplication; completed duplicates return 200 with `duplicate: true`; pending/processing duplicates return 409; failed duplicates are cleaned up and retried; `content_hash` column + partial index on `documents` table
- **API test suite** — `pytest` suite under `tests/api/` covering upload, ingestion polling, list, delete, and all 5 dedup scenarios (DEDUP-01 through DEDUP-05); `conftest.py` with `authed_client` fixture
- **E2E test suite** — Playwright tests under `tests/e2e/` for settings page and document workflow

### Changed
- Chat endpoint switched from OpenAI Responses API to OpenRouter Chat Completions
- Chat history is now stateless — full thread messages fetched from DB and sent each request
- RAG context injected into system prompt when relevant chunks are retrieved

### Fixed
- Document status updates now include `user_id` filter for defense-in-depth (service-role key + explicit filter)
- Storage paths sanitize `file.filename` to prevent path traversal
- Messages history query includes `user_id` guard alongside thread ownership check
- Stream error handling: assistant message only persisted when a response was received; internal errors logged instead of silently dropped
- Error messages shown to users are generic; raw exception details logged server-side only
