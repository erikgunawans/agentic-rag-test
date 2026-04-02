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
- User message is saved to DB before streaming starts — if stream fails, message is orphaned (known limitation, addressed in Module 2 refactor)
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

### Module 4: Metadata Extraction

- [ ] Not started

### Module 5: Multi-Format Support

- [ ] Not started

### Module 6: Hybrid Search & Reranking

- [ ] Not started

### Module 7: Additional Tools

- [ ] Not started

### Module 8: Sub-Agents

- [ ] Not started
