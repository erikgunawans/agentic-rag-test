# Changelog

All notable changes to this project will be documented in this file.

## [0.2.0.0] - 2026-04-20

### Added
- **RAG pipeline complete (8/8 hooks)**: metadata pre-filtering (tags, folder, date range), weighted RRF fusion, Cohere Rerank v2, OCR metadata tracking, graph re-indexing endpoint, RAG evaluation golden set, bilingual query expansion, structure-aware chunking
- **Metadata pre-filtering**: LLM can now filter document search by tags, folder, and date range directly from chat
- **Weighted fusion**: admin-configurable vector vs fulltext search weights via system settings
- **Cohere Rerank**: fast cross-encoder reranking as alternative to LLM reranking (~200ms vs 2-5s)
- **OCR tracking**: scanned PDF documents now record `ocr_used`, `ocr_pages_processed`, and `ocr_pages_failed` in metadata
- **Graph re-indexing**: `POST /documents/{id}/reindex-graph` backfills graph entities for existing documents
- **RAG evaluation**: 20-query Indonesian legal golden set with keyword hit rate and MRR metrics (`python -m scripts.eval_rag`)
- **Claude Code automations**: context7 + Playwright MCP servers, enhanced PostToolUse (full import check), PreToolUse blocks applied migrations, `/create-migration` skill, `rag-quality-reviewer` agent
- **Vision OCR**: scanned PDFs auto-detected and processed via GPT-4o vision

### Changed
- RRF fusion weights now read from `system_settings` (admin-configurable) instead of hardcoded 1:1
- Rerank dispatch uses tri-state `rag_rerank_mode` (none/llm/cohere) instead of boolean `rag_rerank_enabled`
- `_llm_rerank` sort uses `enumerate()` instead of `list.index()` (O(n log n) vs O(n²))
- httpx client reused across Cohere rerank calls instead of creating per-call
- CLAUDE.md quality improved from 82 to 100/100, condensed from 186 to 167 lines

### Fixed
- Cache key now includes filter params to prevent cross-query collisions
- Cohere client initialized in `__init__` to avoid race condition on concurrent first requests
- `rag_rerank_mode` validated with `Literal["none", "llm", "cohere"]` to prevent silent misconfiguration
- Pre-existing bug: `user_settings` → `sys_settings` in `/documents/search` vector mode (line 244)

## [0.1.1.0] - 2026-04-04

### Added
- Deploy backend to Railway with Dockerized FastAPI container (non-root user, exec-form CMD)
- Deploy frontend to Vercel with auto-detected Vite build
- Configurable CORS origins via `FRONTEND_URL` environment variable (comma-separated, empty-string safe)
- Production Dockerfile for backend (python:3.12-slim, uvicorn)
- `.dockerignore` to exclude dev artifacts, tests, plan files, and git history from container builds

### Fixed
- TypeScript build error in ToolCallCard where `unknown` type wasn't assignable to `ReactNode`
- Unused React import warning in scroll-area component
- CORS empty-string vulnerability when `FRONTEND_URL` has trailing comma
