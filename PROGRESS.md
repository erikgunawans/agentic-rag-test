# Progress

Track your progress through the masterclass. Update this file as you complete modules - Claude Code reads this to understand where you are in the project.

## Convention

- `[ ]` = Not started
- `[-]` = In progress
- `[x]` = Completed

## Modules

### Module 1: App Shell + Observability ✅ COMPLETE

- [x] Project setup (Vite frontend, FastAPI backend, venv, env config)
- [x] Supabase schema (threads + messages tables, RLS policies) — migration at `supabase/migrations/001_initial_schema.sql`
- [x] Backend core (FastAPI, Pydantic settings, Supabase client, JWT auth)
- [x] OpenAI Responses API service + LangSmith tracing
- [x] Backend chat API (thread CRUD + SSE streaming endpoint)
- [x] Frontend auth (login/signup, AuthGuard, protected routes)
- [x] Frontend chat UI (ThreadList, MessageView, streaming, MessageInput)
- [x] End-to-end validated — migration applied, env configured, streaming chat confirmed, RLS verified, messages persisted in DB
- [x] Bug fixes — lifespan replaces deprecated on_event, SSE Cache-Control headers added, apiFetch error check simplified

## Notes

- `openai>=2.30.0` required (responses API + `.stream()` context manager not in v1)
- User message is saved to DB before streaming starts; assistant message is only persisted if the stream produces a response (stream errors no longer create orphaned messages)
- `text-embedding-3-small` cosine similarity scores are typically 0.3–0.6 for semantically related text — use `RAG_SIMILARITY_THRESHOLD=0.3` (not 0.7)
- `pymupdf>=1.25.0` and `tiktoken>=0.8.0` required (Python 3.14 compatible versions)

### Module 2: BYO Retrieval + Memory ✅ COMPLETE

- [x] Plan 8: DB schema + ingestion pipeline (`supabase/migrations/002_module2_schema.sql`, `embedding_service.py`, `ingestion_service.py`, `documents.py` router)
- [x] Plan 9: OpenRouter + stateless chat + RAG retrieval (`openrouter_service.py`, refactor `chat.py` with history + context injection)
- [x] Plan 10: Supabase Realtime ingestion status (frontend `useDocumentRealtime.ts` hook)
- [x] Plan 11: Documents UI (`DocumentsPage.tsx`, `FileUpload.tsx`, `DocumentList.tsx`, nav link)
- [x] Settings UI — per-user LLM model + embedding model with lock enforcement (`user_settings` table, `SettingsPage.tsx`)

#### Module 2 Architecture Summary

- **LLM**: OpenRouter Chat Completions, per-user model (default: `openai/gpt-4o-mini`)
- **Retrieval**: pgvector IVFFlat index, cosine similarity, top-5 chunks, similarity ≥ 0.3
- **Memory**: Stateless — load full thread history from DB, send with every request
- **Ingestion**: Upload → Supabase Storage → BackgroundTask → PyMuPDF parse → tiktoken chunk (500t/50 overlap) → OpenAI embed → pgvector store
- **Status**: Supabase Realtime on `documents` table (pending → processing → completed/failed)
- **Settings**: Per-user LLM + embedding model; embedding locked once documents are indexed
- **New env vars**: `OPENROUTER_API_KEY`, `OPENROUTER_MODEL`, `OPENAI_EMBEDDING_MODEL`, `RAG_TOP_K`, `RAG_SIMILARITY_THRESHOLD`, `STORAGE_BUCKET`
- **New tables**: `documents`, `document_chunks`, `user_settings` (all with RLS)
- **Accepted file types**: `.pdf`, `.txt`, `.md`

#### Sub-Plan Files

- `.agent/plans/8.m2-db-ingestion-pipeline.md`
- `.agent/plans/9.m2-openrouter-stateless-chat.md`
- `.agent/plans/10.m2-realtime-status.md`
- `.agent/plans/11.m2-documents-ui.md`

### Module 3: Record Manager ✅ COMPLETE

- [x] Migration `supabase/migrations/004_record_manager.sql` — add `content_hash` column + partial index to `documents` table
- [x] Backend dedup logic — SHA-256 hashing, check for completed/pending/failed duplicates in `documents.py` upload endpoint
- [x] Frontend feedback — `FileUpload.tsx` shows info message for duplicate uploads; `database.types.ts` updated with `content_hash` field
- [x] API tests — `TestDocumentDedup` class with 5 dedup tests in `tests/api/test_documents.py`

#### Module 3 Architecture Summary

- **Hashing**: SHA-256 of raw file bytes, computed before any storage or DB writes
- **Dedup scope**: Per-user — two users uploading the same file each get their own copy
- **On completed duplicate**: Return 200 `{id, filename, status, duplicate: true}` — no storage upload, no DB insert, no background task
- **On pending/processing duplicate**: Return 409
- **On failed duplicate**: Delete failed record + storage file, then proceed with fresh upload
- **Schema**: `content_hash text` column (nullable), partial index on `(user_id, content_hash) WHERE content_hash IS NOT NULL`
- **Legacy docs**: Pre-Module 3 documents have `content_hash = NULL` and are never matched as duplicates

#### Sub-Plan Files

- `.agent/plans/12.m3-record-manager.md`

### Module 4: Metadata Extraction ✅ COMPLETE

- [x] Migration `supabase/migrations/005_document_metadata.sql` — add `metadata` JSONB column + GIN index to `documents`, add `match_document_chunks_with_metadata` RPC
- [x] Pydantic model `backend/app/models/metadata.py` — `DocumentMetadata` with title, author, date_period, category, tags, summary
- [x] Metadata extraction service `backend/app/services/metadata_service.py` — LLM extraction via OpenRouter with `json_object` response format, LangSmith traced
- [x] Ingestion pipeline integration `backend/app/services/ingestion_service.py` — extract metadata after parse, best-effort (failures don't block ingestion)
- [x] Documents router `backend/app/routers/documents.py` — pass `llm_model` to ingestion, include `metadata` in list, add `GET /documents/{id}/metadata` endpoint
- [x] Enhanced retrieval `backend/app/services/embedding_service.py` — `retrieve_chunks_with_metadata()` using new RPC
- [x] Chat enrichment `backend/app/routers/chat.py` — system prompt includes `[Source: "filename" | Category: X | Tags: ...]` per chunk
- [x] Frontend types `frontend/src/lib/database.types.ts` — `DocumentMetadata` interface, `metadata` field on `Document`
- [x] Frontend UI `frontend/src/components/documents/DocumentList.tsx` — show category badge, tags, summary for completed docs
- [x] API tests `tests/api/test_documents.py` — `TestDocumentMetadata` class with META-01 through META-06

#### Module 4 Architecture Summary

- **Extraction**: LLM (user's selected OpenRouter model) extracts structured metadata after text parsing; truncated to 4000 tokens; `json_object` response format; best-effort (extraction failure skips metadata but ingestion succeeds)
- **Schema**: Fixed Pydantic model — `title`, `author`, `date_period`, `category` (enum), `tags` (list), `summary`; stored as JSONB on `documents.metadata`
- **Retrieval**: `match_document_chunks_with_metadata` RPC joins chunks with documents, returns metadata alongside each chunk; optional `filter_category` parameter
- **Chat**: System prompt now includes `[Source: "filename" | Category: X | Tags: y, z]` header before each chunk, giving LLM document-level context
- **Frontend**: Documents page shows category badge (color-coded), keyword tags, and summary for completed documents with metadata; backward compatible with pre-Module 4 docs

#### Sub-Plan Files

- `.agent/plans/13.m4-metadata-extraction.md`

### Module 5: Multi-Format Support ✅ COMPLETE

- [x] Backend dependencies — `python-docx>=1.1.0`, `beautifulsoup4>=4.12.0` added to `requirements.txt`
- [x] Backend MIME whitelist — expanded `ALLOWED_MIME_TYPES` in `documents.py` to include DOCX, CSV, HTML, JSON
- [x] Format parsers — added `_parse_docx`, `_parse_csv`, `_parse_html`, `_parse_json` in `ingestion_service.py`
- [x] Frontend validation — expanded `ACCEPTED_TYPES` and UI text in `FileUpload.tsx`
- [x] Test fixtures — `sample.docx`, `sample.csv`, `sample.html`, `sample.json` in `tests/fixtures/`
- [x] API tests — `TestMultiFormatUpload` class with FMT-01 through FMT-08

#### Module 5 Architecture Summary

- **New formats**: DOCX (python-docx), CSV (stdlib csv), HTML (beautifulsoup4 + html.parser), JSON (stdlib json)
- **Pattern**: Each format has a `_parse_<format>(file_bytes) -> str` helper; `parse_text()` dispatches by MIME type
- **No schema changes**: Existing `documents` table and ingestion pipeline handle all formats generically
- **Backward compatible**: PDF, TXT, Markdown handling unchanged
- **Accepted MIME types**: `application/pdf`, `text/plain`, `text/markdown`, `application/vnd.openxmlformats-officedocument.wordprocessingml.document`, `text/csv`, `text/html`, `application/json`

#### Sub-Plan Files

- `.agent/plans/14.m5-multi-format.md` (plan saved to `.claude/plans/fuzzy-frolicking-flute.md`)

### Module 6: Hybrid Search & Reranking

- [ ] Not started

### Module 7: Additional Tools

- [ ] Not started

### Module 8: Sub-Agents

- [ ] Not started
