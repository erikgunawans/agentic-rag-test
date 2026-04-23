# Progress

PJAA CLM Platform (LexCore) v0.2.0.0. All phases complete (1-3, BJR, RAG 8/8). 2026 UI refresh shipped. LLM auto-naming for chat threads. Global folders with share-with-all and cascading subtree visibility. 28 migrations, 22 routers, 18 services.

## Checkpoint 2026-04-23 (LLM thread auto-naming + global folders)

- **Session:** Added two features: auto-generated chat thread titles via LLM, and global folders with sharing
- **Branch:** master (`21f3382`)
- **Done:**
  - **LLM thread auto-naming** (`c8daaca`): After first assistant response, backend calls LLM to generate ~6-word title. Emits `thread_title` SSE event for instant sidebar update. Language-aware (ID/EN). Non-blocking (try/except).
    - `backend/app/routers/chat.py` — title generation after message persist
    - `frontend/src/hooks/useChatState.ts` — `thread_title` SSE handler
    - `frontend/src/lib/database.types.ts` — `ThreadTitleEvent` type
  - **Global folders** (`21f3382`): Any user can right-click a top-level folder → "Share with All". Entire subtree becomes read-only visible to all users. Globe icon distinguishes shared folders.
    - `supabase/migrations/028_global_folders.sql` — `is_global` column, `is_in_global_subtree()` RPC, updated RLS policies, updated `get_folder_tree` CTE
    - `backend/app/routers/folders.py` — `PATCH /folders/{id}/toggle-global`, updated `GET /folders` for global visibility
    - `frontend/src/components/documents/FolderTree.tsx` — Globe icon, right-click context menu, `(shared)` label, Lock icon for non-owners
    - `frontend/src/pages/DocumentsPage.tsx` — `handleToggleGlobal`, passes `currentUserId` to FolderTree
- **Files changed:** 8 files (3 backend, 4 frontend, 1 migration)
- **Tests:** TypeScript OK, backend import OK, ESLint clean (pre-existing errors only)
- **Pending:** Migration 028 needs to be applied to Supabase; deploy to Railway + Vercel
- **Next:** Apply migration 028, deploy, QA test both features in production

## Checkpoint 2026-04-23 (Knowledge graph rebuild + MCP + CLAUDE.md graphify integration)

- **Session:** Ran full graphify pipeline on entire codebase, rebuilt Obsidian vault, wired graphify MCP server
- **Branch:** master
- **Done:**
  - `graphify .` full run — 237 files, 93% cache hit rate (23 new files extracted via 2 parallel agents)
  - Graph: 1211 nodes, 1655 edges, 192 communities (up from 1229/1729/147 — re-clustering)
  - Obsidian vault: 1403 notes written to `~/claude-code-memory-egs/graphify/claude-code-agentic-rag-masterclass-1/`
  - HTML viz: `graphify-out/graph.html`
  - Token benchmark: **155.9x reduction** per query (510K corpus tokens → ~3,274 per query)
  - `graphify claude install` — added `## graphify` section to `CLAUDE.md`, registered PreToolUse hook in `.claude/settings.json`
  - `.mcp.json` — added `graphify` MCP server (stdio, exposes `query_graph`, `get_node`, `shortest_path`, `god_nodes`)
- **Files changed:** 3 files (`.mcp.json`, `CLAUDE.md`, `.claude/settings.json`) + `graphify-out/`
- **God nodes:** `get_supabase_authed_client` (77 edges), `get_supabase_client` (76), `log_action` (59)
- **Next:** Restart Claude Code to activate graphify MCP; use `/graphify query` to trace architecture questions

## Checkpoint 2026-04-22 (2026 UI design refresh + logo update)

- **Session:** Updated logos (icon rail + thread panel), applied 2026 design trends across CSS and components
- **Branch:** master (`1c733e9`)
- **Done:**
  - Logo swap: IconRail → `lexcore-logo-dark.svg`, ThreadPanel → `lexcore-dark.svg` (from References/)
  - CSS: grain/noise texture overlay (`body::after`, SVG fractalNoise, `mix-blend-mode: overlay`)
  - CSS: multi-tone mesh background — teal second orb (`oklch(0.65 0.15 195)`) alongside purple
  - CSS: new utilities — `.shimmer`, `.card-luminous`, `.interactive-spring`, `--easing-spring` token
  - CSS: `text-wrap: balance` on all headings; `gradient-border-animated:focus-within` rule
  - `SuggestionCards.tsx`: bento redesign — tinted icon backgrounds, per-card ambient colour wash, spring arrow
  - `ThreadList.tsx`: active thread left accent bar (matches IconRail pattern)
  - `WelcomeInput.tsx` + `MessageInput.tsx`: animated gradient border on focus-within
- **Files changed:** 7 files (`index.css`, 4 components, 2 SVGs in public/)
- **Tests:** TypeScript OK, backend import OK
- **Deploy:** Vercel deployed (`frontend-hzhhqwj62-erik-gunawan-s-projects.vercel.app` → production), Railway healthy
- **Next:** Frontend QA pass on production, stakeholder demo prep

## Checkpoint 2026-04-20 (RAG pipeline complete + pre-ship + automations + CLAUDE.md 100)

- **Session:** Completed all 8 RAG pipeline improvements, ran full pre-ship pipeline (simplify + review + codex), implemented Claude Code automations, improved CLAUDE.md to 100/100
- **Branch:** master (`651692c`)
- **Done:**
  - RAG pipeline 8/8: metadata pre-filtering, weighted RRF fusion, Cohere rerank, OCR tracking, graph reindex endpoint, eval golden set, cache key fix, structure-aware chunking (all prior)
  - Migration 027 applied to Supabase (RPCs with filter params + fusion weights + rerank mode columns)
  - Pre-ship pipeline: /simplify fixed O(n²) rerank sort, Literal validation, httpx reuse. /review clean (10/10). /codex caught Cohere client race condition.
  - Claude Code automations: .mcp.json (context7 + Playwright), PostToolUse enhanced (full import check), PreToolUse blocks applied migrations (001-027), /create-migration skill, /run-api-tests enhanced with RAG eval, rag-quality-reviewer subagent
  - CLAUDE.md improved 82→100: condensed design system, fixed stale counts, merged duplicate sections, added skill references
- **Commits:** `53dd0f9` (RAG feat) → `4b6fe28` (simplify) → `0548821` (codex fix) → `36ed096` (automations) → `7ee4afb` + `651692c` (CLAUDE.md)
- **Files changed:** 15 files (10 backend, 2 config, 1 migration, 1 script, 1 docs)
- **Tests:** Backend import OK, health check passed
- **Deploy:** Railway healthy, Vercel auto-deploying from main
- **Next:** Push remaining local commits, stakeholder demo, consider frontend QA pass

## RAG Pipeline Scorecard

| # | Hook | Status | Commit |
|---|------|--------|--------|
| 1 | Structure-aware chunking | ✅ Shipped | `d47df7f` |
| 2 | Multi-modal (vision OCR) | ✅ Shipped | `00d8c2f` |
| 3 | Custom embedding model | ✅ Shipped | `6c9c951` |
| 4 | Metadata pre-filtering | ✅ Shipped | `53dd0f9` |
| 5 | Query expansion (bilingual) | ✅ Shipped | `d47df7f` |
| 6 | Learned fusion weights | ✅ Shipped | `53dd0f9` |
| 7 | Cross-encoder reranking | ✅ Shipped | `53dd0f9` |
| 8 | Graph reindex endpoint | ✅ Shipped | `53dd0f9` |

## Checkpoint 2026-04-19 (RAG Phase 3 embedding infra + Phase 2 plan)

- **Session:** Shipped embedding fine-tuning infrastructure, planned remaining 3 RAG improvements
- **Branch:** master (clean, `6c9c951`)
- **Done:**
  - Committed + deployed `query_logs` table (migration 026) for embedding fine-tuning data collection
  - Fire-and-forget query logging in `tool_service.py` — every search_documents call logs query + retrieved chunk IDs/scores
  - `custom_embedding_model` config in `config.py` + `system_settings` — hot-swappable embedding model
  - `chat.py` prefers custom embedding model over default when set
  - Planned RAG Pipeline Phase 2 (3 remaining improvements): metadata pre-filtering, learned fusion weights, cross-encoder reranking
- **Files changed:** 4 files committed (`config.py`, `chat.py`, `tool_service.py`, `026_embedding_training.sql`)
- **Tests:** Backend import OK, health check passed post-deploy
- **Plan:** `~/.claude/plans/floating-drifting-thimble.md` — RAG Pipeline Phase 2 (3 improvements, 96% confidence)
- **Next:** Execute RAG Pipeline Phase 2 plan (metadata pre-filtering → learned fusion weights → cross-encoder reranking)

## RAG Pipeline Scorecard

| # | Hook | Status | Commit |
|---|------|--------|--------|
| 1 | Structure-aware chunking | ✅ Shipped | `d47df7f` |
| 2 | Multi-modal (vision OCR) | ✅ Shipped | `00d8c2f` |
| 3 | Custom embedding model | ✅ Shipped | `6c9c951` |
| 4 | Metadata pre-filtering | 📋 Planned | — |
| 5 | Query expansion (bilingual) | ✅ Shipped | `d47df7f` |
| 6 | Learned fusion weights | 📋 Planned | — |
| 7 | Cross-encoder reranking | 📋 Planned | — |
| 8 | Query understanding | ⚠️ Partial (intent classification only) | `d47df7f` |

## Checkpoint 2026-04-18 (Knowledge graph updated)

- **Session:** Updated graphify knowledge graph with incremental extraction (3 changed doc files)
- **Branch:** master (clean, no uncommitted changes)
- **Done:**
  - Graphify incremental update: +51 nodes, +55 edges (1091 → 1142 nodes, 1559 → 1614 edges, 125 communities)
  - Traced `get_supabase_authed_client()` god node (77 edges) — confirmed it's the RLS security perimeter bridging all data-access communities
  - Graph outputs refreshed: graph.html, GRAPH_REPORT.md, graph.json
- **Files changed:** 0 committed (graphify-out/ is untracked)
- **Tests:** No code changes — all existing tests still valid
- **Next:** Stakeholder demo prep, then ongoing maintenance

## Checkpoint 2026-04-17 (Phase 3 complete — F13 + F14 shipped)

- **Session:** Implemented Phase 3: F13 (Point-in-Time Compliance Querying) + F14 (UU PDP Compliance Toolkit)
- **Branch:** master (synced with origin + main)
- **Done:**
  - F13: compliance_snapshots table, 4 API endpoints, ComplianceTimelinePage with timeline view + diff comparison, "Save as Snapshot" button on ComplianceCheckPage
  - F14: 3 tables (data_inventory, pdp_compliance_status, data_breach_incidents), 13 API endpoints, PDPDashboardPage (readiness score + DPO appointment), DataInventoryPage (CRUD), DataBreachPage (72-hour countdown + notification template), LLM personal data scanner, require_dpo() dependency
  - Dashboard extended with compliance snapshot count + PDP readiness metrics
  - Migrations 022 + 023 applied to Supabase
  - Deployed to Railway + Vercel
  - Production smoke test: 9/9 passed (snapshots, PDP status, readiness 0→45, inventory CRUD, incident report, notification template, dashboard integration)
- **Commits:** `56ef7d5` (F13) + `05d0a9a` (F14)
- **Files changed:** 21 files (11 new, 10 modified), +1,840 lines
- **Tests:** TypeScript tsc clean, ESLint clean, backend import OK
- **Next:** Stakeholder demo prep, then ongoing maintenance

## Checkpoint 2026-04-17 (BJR pre-ship hardening complete)

- **Session:** Pre-ship pipeline (simplify + review + codex adversarial), security trace Q13/Q14, graph update
- **Branch:** master (synced with origin + main)
- **Done:**
  - Security trace Q13 (admin boundaries): PASS — clean separation
  - Security trace Q14 (RLS cross-references): fixed authed client for evidence reads (`cbb6371`)
  - QA: modal Escape key fix (`adf76fc`), health 100/100
  - /simplify: Literal types on Pydantic models, unused imports removed, selectedPhase dep fix, is_global server filter (`9677dc1`)
  - /review: clean — 0 findings, quality score 10/10
  - /codex adversarial (gpt-5.3-codex): 4 critical/high findings fixed (`3d568e6`):
    1. Evidence auto_approved now requires satisfies_requirement=true
    2. Approval reject/return resets decision from under_review
    3. Completed/cancelled decisions immutable via evidence endpoints
    4. Cancelled decisions blocked from re-entering approval flow
  - Knowledge graph updated (983 nodes, 1311 edges, 120 communities)
  - Graph Question List created (20 questions, 7 categories)
- **Commits:** `c7d2e02` → `adf76fc` → `cbb6371` → `9677dc1` → `3d568e6` (5 commits)
- **Tests:** TypeScript tsc clean, ESLint clean, backend import OK
- **Next:** Deploy final fixes, stakeholder demo, Phase 3 planning

## Checkpoint 2026-04-17 (BJR Decision Governance Module shipped)

- **Session:** Analyzed Ancol GCG/BJR regulatory matrix document, brainstormed integration approach, designed and implemented full BJR module
- **Branch:** master (synced with origin + main)
- **Done:**
  - Deep analysis of `Matriks_Regulasi_GCG_BJR_Ancol_2026.docx` — 28 regulations across 4 layers, 16-item BJR checklist, 11 GCG aspects, 4 strategic risks
  - Design spec: `docs/superpowers/specs/2026-04-17-bjr-governance-module.md`
  - Database: 6 new tables (`bjr_regulatory_items`, `bjr_checklist_templates`, `bjr_decisions`, `bjr_evidence`, `bjr_gcg_aspects`, `bjr_risk_register`) with RLS + seed data
  - Backend: `bjr.py` router (25 endpoints), `bjr_service.py` (LLM evidence assessment + score calculation + phase advance), `models/bjr.py` (12 Pydantic models)
  - Frontend: `BJRDashboardPage.tsx`, `BJRDecisionPage.tsx`, 4 BJR components (PhaseProgress, ChecklistItem, EvidenceAttachModal, RiskCard)
  - Integration: approval workflow hook for phase advancement, dashboard BJR metrics, IconRail standalone nav, 88 i18n keys
  - Migration applied to Supabase, deployed to Railway + Vercel
  - Production smoke test: 8/8 tests passed (regulatory items, checklist, GCG, risks, summary, create decision, get detail, attach evidence)
- **Files changed:** 17 files (10 new, 7 modified), 3,156 insertions
- **Tests:** TypeScript tsc clean, ESLint clean (BJR files)
- **Commit:** `c7d2e02`
- **Next:** QA the BJR module on production UI, Phase 3 planning (F13 + F14), stakeholder demo

## Checkpoint 2026-04-17 (LLM end-to-end test PASSED)

- **Session:** Full AI pipeline validation on production
- **Test document:** `sample_indonesian_nda.txt` — Indonesian NDA between PT Maju Bersama and PT Teknologi Nusantara
- **Results (all PASS):**
  - Document upload + ingestion: status=completed, 3 chunks, embeddings stored, metadata extracted (title, category=legal, summary in Indonesian, tags)
  - Chat with RAG: Multi-agent routing active (Research Agent), search_documents tool called, 4 chunks retrieved, response references specific NDA clauses
  - Follow-up chat: Correctly searched for "force majeure", retrieved relevant chunk
  - SSE streaming: Progressive token-by-token delivery, correct event ordering (agent_start → tool_start → tool_result → delta → done:true)
  - Document creation: Generated 4,801-char NDA, confidence=1.0, auto_approved
  - Compliance check (OJK): overall_status=pass, 2 findings (both pass), 0 missing provisions, confidence=0.95
  - Contract analysis: overall_risk=medium, 3 risks, 2 obligations, 6 critical clauses, 3 missing provisions, confidence=0.85
  - Error handling: 401 (invalid token), 404 (bad thread), 400 (empty file) all correct
  - Tool history: 3 entries recorded with correct tool_type, confidence, review_status
- **What's next:** Stakeholder demo → Phase 3 planning (F13: Point-in-Time Compliance, F14: UU PDP Toolkit)

## Checkpoint 2026-04-16 (Production visual QA passed)

- **Session:** Visual QA of production site (light theme). Logged in, screenshotted 7 key pages, checked console errors, verified backend health.
- **Branch:** master (clean, synced with origin + main)
- **Done:**
  - DocumentsPage fix already committed (`45886d6`)
  - Production QA: Auth, Welcome/Chat, Dashboard, Documents, Create, Settings, Clause Library, Approvals — all pass
  - Zero console errors across all pages
  - Backend health check: `{"status":"ok"}`
  - master synced to main (Vercel production up to date)
- **Files changed:** 0 (working tree clean)
- **Tests:** TypeScript tsc clean
- **Next:** End-to-end LLM test with real Indonesian document → PJAA stakeholder feedback → Phase 3 planning

---

## Checkpoint 2026-04-16 (Session resume — pending QA pass)

- **Session:** Resumed from design refresh + grouped rail checkpoint. Identified uncommitted fix in DocumentsPage.tsx.
- **Branch:** master
- **Done:**
  - Session context restored via /checkpoint resume
  - Identified uncommitted change: DocumentsPage "New Document" button converted from `<button>` to `<Link to="/create">` for correct SPA routing
- **Files changed:** 1 file (frontend/src/pages/DocumentsPage.tsx — staged, not committed)
- **Tests:** TypeScript tsc clean
- **Next:** Commit DocumentsPage fix → Visual QA of light theme on production → End-to-end LLM test with real Indonesian document → PJAA stakeholder feedback

---

## Checkpoint 2026-04-15 (Light theme + design audit)

- **Session:** Full design audit (8 findings, 7 fixed), then light theme implementation (10 steps)
- **Branch:** master
- **Done:**
  - Design audit: removed AI slop (colored left-border cards), added cursor:pointer globally, fixed auth branding ("RAG Chat" to "LexCore"), fixed H1 weight, added color-scheme:dark, increased touch targets
  - Light theme: restructured CSS (`:root` = light, `.dark` = dark), added `@custom-variant dark` for Tailwind v4, created ThemeContext (light/dark/system with localStorage + matchMedia), FOUC prevention script, Settings "Tampilan" section with radio picker, theme-aware Logo component (CSS filter), AuthPage refactored to use Tailwind theme classes, bulk color audit (160 text-*-400 occurrences fixed across 21 files), gradient endpoints moved to CSS vars
  - Vercel env vars cleaned (trailing newlines removed from VITE_API_BASE_URL and VITE_SUPABASE_ANON_KEY)
  - Database cleanup: 21 empty test threads deleted
  - Plan Verification Protocol added to CLAUDE.md
- **Files changed:** 25+ files (index.css, ThemeContext.tsx, App.tsx, index.html, translations.ts, SettingsPage.tsx, AuthPage.tsx, Logo.tsx, IconRail.tsx, ThreadPanel.tsx, AppLayout.tsx, DashboardPage.tsx, DocumentsPage.tsx, MessageView.tsx, + 11 more pages)
- **Tests:** TypeScript tsc clean
- **Next:** Visual QA of light theme on production, tune oklch values if needed, Phase 3 after stakeholder feedback

---

## Checkpoint 2026-04-14 (Unified visual style across all sections)

- **Session:** Applied chat section's atmospheric background (dot-grid + mesh-bg) and minimal layout to all other sections. Removed hard border-b separator bars, added glass sidebars.
- **Branch:** master
- **Done:**
  - dot-grid CSS converted from background-image to ::before pseudo-element overlay (visible above child elements)
  - dot-grid applied to AppLayout `<main>` — every page inherits the dot overlay automatically
  - Removed redundant mesh-bg/dot-grid from WelcomeScreen (inherits from layout)
  - DocumentsPage: removed border-b top bar, merged controls inline with content
  - AuditTrailPage: removed double border-b bars (header + filters), flowed inline
  - Added `glass` (backdrop-blur + semi-transparent bg) to all 10 desktop sidebar panels
  - Extracted InputActionBar component shared by MessageInput + WelcomeInput
  - handleNewChat() for lazy thread creation (no empty threads)
- **Files changed:** 14 files (index.css, AppLayout.tsx, WelcomeScreen.tsx, InputActionBar.tsx, MessageInput.tsx, WelcomeInput.tsx, ThreadPanel.tsx, useChatState.ts, + 10 page files with glass sidebars)
- **Tests:** TypeScript tsc clean
- **Next:** Get PJAA stakeholder feedback, verify visual consistency across all pages, Phase 3 after validation

---

## Checkpoint 2026-04-14 (Chat input UI consistency + new chat flow fix)

- **Session:** Fixed chat MessageInput to match WelcomeInput styling (glass card, action bar icons), fixed "Chat Baru" button to return to welcome screen instead of creating empty thread
- **Branch:** master
- **Done:**
  - MessageInput restyled: glass card, rounded-2xl, gradient send button, Plus/FileText/Mic action bar (matches WelcomeInput)
  - "Chat Baru" button now resets to welcome screen (centered input + suggestion cards) instead of creating an empty thread
  - Added `handleNewChat()` to useChatState — clears activeThreadId without DB call; thread created lazily on first message send
- **Files changed:** 3 files (MessageInput.tsx, ThreadPanel.tsx, useChatState.ts)
- **Tests:** TypeScript tsc clean
- **Next:** Verify chat input transition UX, get PJAA stakeholder feedback, Phase 3 after validation

---

## Checkpoint 2026-04-14 (Phase 1+2 complete, UI polish, chat layout fix)

- **Session:** Built Phase 1 (F3, F5, F6), Phase 2 (F8-F12), code reviews (/simplify x2, /codex, /qa), auth page redesign, LexCore branding, chat layout fix
- **Branch:** master
- **Done:**
  - F3: Clause library + document templates + 9 doc types + per-clause risk scoring
  - F5: Approval workflow engine with admin inbox
  - F6: MFA/security hardening + user management
  - F8: Regulatory intelligence engine with 4 Indonesian sources
  - F9: WhatsApp notification infrastructure
  - F10: Executive dashboard with summary cards + trends
  - F11: Dokmee DMS integration (stubs)
  - F12: Google Workspace export (stubs)
  - Auth page redesign (Apple iCloud style, true black bg, floating card)
  - LexCore branding (logo, icon rail, thread panel, mobile header)
  - Chat layout fix (overflow:clip prevents focus-triggered scroll)
  - Styled glassmorphic tooltips on IconRail
  - Vercel SPA rewrite for client-side routing
  - 3 code reviews: /simplify, /codex (4 findings fixed), /qa (health 100)
- **Files changed:** 40+ files across backend routers, frontend pages, migrations, i18n
- **Tests:** TypeScript tsc -b clean, backend import check clean, QA health 100/100
- **Next:** Get PJAA stakeholder feedback. Phase 3 (F13+F14) only after real user validation.

---

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
- [x] API tests — `TestMultiFormatUpload` class with FMT-01 through FMT-08, all 31 tests passing
- [x] End-to-end validated — all formats ingested to `completed` status with chunks verified

#### Module 5 Architecture Summary

- **New formats**: DOCX (python-docx), CSV (stdlib csv), HTML (beautifulsoup4 + html.parser), JSON (stdlib json)
- **Pattern**: Each format has a `_parse_<format>(file_bytes) -> str` helper; `parse_text()` dispatches by MIME type
- **No schema changes**: Existing `documents` table and ingestion pipeline handle all formats generically
- **Backward compatible**: PDF, TXT, Markdown handling unchanged
- **Accepted MIME types**: `application/pdf`, `text/plain`, `text/markdown`, `application/vnd.openxmlformats-officedocument.wordprocessingml.document`, `text/csv`, `text/html`, `application/json`
- **Test note**: `upload_docx` helper generates DOCX in-memory with a UUID paragraph per call (avoids content-hash dedup collisions); requires `python-docx` in the test runner's Python env (`pip3 install python-docx`)

### Module 6: Hybrid Search & Reranking ✅ COMPLETE

- [x] Migration `supabase/migrations/006_hybrid_search.sql` — add `fts tsvector` column, GIN index, auto-populate trigger, `match_document_chunks_fulltext` RPC
- [x] Config additions — `rag_hybrid_enabled`, `rag_rrf_k`, `rag_rerank_enabled`, `rag_rerank_model` in `backend/app/config.py`
- [x] Rerank model — `backend/app/models/rerank.py` with `RerankScore` and `RerankResponse`
- [x] Hybrid retrieval service — `backend/app/services/hybrid_retrieval_service.py` with vector search, full-text search, RRF fusion, optional LLM reranker
- [x] Chat router updated — `backend/app/routers/chat.py` uses `HybridRetrievalService` instead of `EmbeddingService`
- [x] Search diagnostics endpoint — `POST /documents/search` with `hybrid`, `vector`, `fulltext` modes
- [x] API tests — `TestHybridSearch` class with HYB-01 through HYB-08, all 75 tests passing

#### Module 6 Architecture Summary

- **Hybrid search**: Combines pgvector cosine similarity (semantic) + Postgres `tsvector`/`tsquery` full-text search (lexical)
- **Fusion**: Reciprocal Rank Fusion (RRF) merges rankings from both methods; formula: `score = sum(1 / (k + rank + 1))`, default `k=60`
- **Pipeline**: Over-fetch `top_k * 3` candidates from each method concurrently (`asyncio.gather`), fuse via RRF, return top-k
- **Reranking**: Optional LLM-based reranker via OpenRouter (gated by `RAG_RERANK_ENABLED=true`), uses `json_object` response format, best-effort fallback
- **Full-text search**: `websearch_to_tsquery` for natural query support (quoted phrases, boolean operators)
- **Trigger**: Postgres trigger auto-populates `fts` column on chunk INSERT/UPDATE — no ingestion pipeline changes needed
- **Fallback**: When `RAG_HYBRID_ENABLED=false`, delegates to vector-only search (existing behavior)
- **No new dependencies**: Uses existing OpenAI SDK + Supabase client + Postgres built-in full-text search
- **No frontend changes**: Hybrid search is transparent — same response shape as vector-only

#### Sub-Plan Files

- `.claude/plans/polymorphic-watching-codd.md`

### Module 7: Additional Tools ✅ COMPLETE

- [x] Migration `supabase/migrations/007_tool_calls.sql` — add `tool_calls` JSONB to messages, `execute_user_document_query` RPC
- [x] Config additions — `tavily_api_key`, `tools_enabled`, `tools_max_iterations` in `backend/app/config.py`
- [x] Pydantic models — `ToolCallRecord`, `ToolCallSummary` in `backend/app/models/tools.py`
- [x] Tool service — `backend/app/services/tool_service.py` with `search_documents`, `query_database`, `web_search` tools
- [x] OpenRouter service — `complete_with_tools()` method for non-streaming tool-calling completions
- [x] Chat router refactor — agentic tool-calling loop with extended SSE protocol (`tool_start`, `tool_result`, `delta` events)
- [x] Frontend types — `ToolCallRecord`, `SSEEvent` types in `database.types.ts`
- [x] Frontend SSE parsing — `ChatPage.tsx` handles `tool_start`, `tool_result`, `delta` events
- [x] ToolCallCard component — collapsible tool execution display with icons and attribution
- [x] MessageView updated — renders tool cards inline (streaming and persisted)
- [x] API tests — `TestToolCalling`, `TestSQLSafety`, `TestToolPersistence`, `TestSSECompat`, `TestToolErrorHandling` (TOOL-01 through TOOL-09)

#### Module 7 Architecture Summary

- **Agentic loop**: Chat endpoint now uses a tool-calling loop — LLM decides which tools to invoke, backend executes them, results feed back to LLM, final text response is streamed
- **Three tools**: `search_documents` (hybrid RAG retrieval), `query_database` (text-to-SQL with safety), `web_search` (Tavily API fallback)
- **Non-streaming iterations**: Tool-calling rounds use regular completions (fast); only the final text response is streamed via SSE
- **SQL safety**: Postgres RPC `execute_user_document_query` with `SECURITY DEFINER` + `STABLE`, SELECT-only validation, mandatory user_id scoping, write-keyword rejection
- **Web search**: Tavily API via httpx; optional — gated by `TAVILY_API_KEY` env var; tool hidden if not configured
- **SSE protocol**: Extended with `type` field — `tool_start`, `tool_result`, `delta` events; backward compatible (delta events still have `done` field)
- **Attribution**: Every tool call visible in UI via collapsible ToolCallCard; web search shows source URLs, SQL shows query, doc search shows chunk count
- **Persistence**: Tool execution records stored in `messages.tool_calls` JSONB; rendered on page reload
- **Fallback**: `TOOLS_ENABLED=false` → identical to Module 6 behavior; tool errors caught and reported to LLM gracefully
- **No new dependencies**: Uses existing `httpx` for Tavily; no LangChain/LangGraph
- **New env vars**: `TAVILY_API_KEY` (optional), `TOOLS_ENABLED` (default true), `TOOLS_MAX_ITERATIONS` (default 5)

#### Sub-Plan Files

- `.claude/plans/expressive-tinkering-avalanche.md`

### Module 8: Sub-Agents ✅ COMPLETE

- [x] Config additions — `agents_enabled`, `agents_orchestrator_model` in `backend/app/config.py`
- [x] Pydantic models — `AgentDefinition`, `OrchestratorResult` in `backend/app/models/agents.py`; `agent` field added to `ToolCallSummary`
- [x] OpenRouter service — `complete_with_tools()` updated with optional `tools` and `response_format` params
- [x] Agent service — `backend/app/services/agent_service.py` with registry (research, data_analyst, general), `classify_intent()`, `get_agent_tools()`
- [x] Chat router refactor — conditional orchestrator + sub-agent dispatch when `agents_enabled=true`; Module 7 behavior preserved as default
- [x] Frontend types — `AgentStartEvent`, `AgentDoneEvent` in `database.types.ts`; `agent` field on `tool_calls`
- [x] AgentBadge component — `frontend/src/components/chat/AgentBadge.tsx` with active and badge modes
- [x] ChatPage SSE parsing — `activeAgent` state, handles `agent_start`/`agent_done` events
- [x] MessageView updated — renders AgentBadge during streaming and on persisted messages
- [x] API tests — `TestOrchestratorRouting`, `TestSubAgentExecution`, `TestAgentSSEProtocol`, `TestAgentPersistence` (AGENT-01 through AGENT-12)

#### Module 8 Architecture Summary

- **Multi-agent routing**: Orchestrator classifies intent via single non-streaming LLM call with `json_object` response format, routes to specialist sub-agent
- **Three agents**: Research Agent (search_documents, 5 iterations), Data Analyst (query_database, 5 iterations), General Assistant (web_search, 3 iterations)
- **Tool isolation**: Each sub-agent only sees its assigned tools — LLM can't call tools outside its definition
- **SSE protocol**: Extended with `agent_start` (agent name + display name) and `agent_done` events wrapping the tool loop + delta stream
- **Persistence**: Agent name stored in `tool_calls.agent` JSONB field — no migration needed
- **Backward compatible**: `AGENTS_ENABLED=false` (default) preserves exact Module 7 single-agent behavior
- **Fallback**: Invalid orchestrator response gracefully falls back to general agent
- **No new dependencies**: Reuses existing OpenRouter, tool service, and httpx
- **New env vars**: `AGENTS_ENABLED` (default false), `AGENTS_ORCHESTRATOR_MODEL` (optional, defaults to user's model)
- **PR**: #2 merged to master via squash merge (commit `c1561fe`)

#### Sub-Plan Files

- `.claude/plans/expressive-tinkering-avalanche.md`

### Module 9: RBAC Settings Architecture ✅ COMPLETE

- [x] Migration `backend/migrations/008_rbac_settings.sql` — `system_settings` (single-row, admin-only RLS), `user_preferences` (per-user RLS), `is_super_admin()` SQL helper
- [x] Admin promotion script `backend/scripts/set_admin_role.py` — CLI to set `app_metadata.role = super_admin` via Supabase Admin API
- [x] Backend `dependencies.py` — extract `role` from JWT `app_metadata`, add `require_admin` FastAPI dependency (403 for non-admins)
- [x] System settings service `backend/app/services/system_settings_service.py` — cached reader with 60s TTL, service-role client
- [x] Admin settings router `backend/app/routers/admin_settings.py` — `GET/PATCH /admin/settings` (admin-only)
- [x] User preferences router `backend/app/routers/user_preferences.py` — `GET/PATCH /preferences` (per-user)
- [x] Refactored `chat.py` + `documents.py` — replaced `get_or_create_settings` with `get_system_settings()`
- [x] Removed deprecated `user_settings.py` router and registration
- [x] Frontend `AuthContext` — provides `user`, `role`, `isAdmin` from JWT `app_metadata`
- [x] Frontend `AdminGuard` component — redirects non-admins away from admin routes
- [x] Frontend `AdminSettingsPage` — Global Configuration Dashboard (LLM, embedding, RAG tuning, tools, agents)
- [x] Frontend `SettingsPage` refactored — converted to user preferences (theme picker + notification toggle)
- [x] Frontend routing — `/admin/settings` with `AuthGuard` + `AdminGuard`, `AuthProvider` wrapping all routes
- [x] Frontend `ChatPage` — conditional Shield icon in sidebar nav for admins

#### Module 9 Architecture Summary

- **3-layer enforcement**: Database RLS (`is_super_admin()` checks JWT claim), Backend (`require_admin` dependency), Frontend (`AdminGuard` component)
- **Role storage**: Supabase `auth.users.raw_app_meta_data.role` — embedded in JWT, only writable via service-role key
- **System settings**: Single-row table (`CHECK (id = 1)`), stores LLM model, embedding model, RAG params, tool/agent config
- **User preferences**: Per-user table with theme and notifications_enabled
- **Settings decoupled**: System config (admin-only, DB table) vs user preferences (per-user, personal)
- **Cache**: 60s TTL on system settings to avoid DB hit per request
- **Promotion**: `python -m scripts.set_admin_role <email>` — user must sign out/in for JWT refresh
- **Backward compatible**: `chat.py` and `documents.py` read from `system_settings` instead of per-user `user_settings`
- **PR**: #4 merged to master

### UI Improvements ✅ COMPLETE

- [x] Animated thinking indicator — bouncing dots animation (`ThinkingIndicator.tsx`) while waiting for LLM response, replaces static blinking cursor
- [x] Collapsible thread groups — threads grouped by date (Today, Yesterday, Previous 7 Days, Older) with expand/collapse chevrons and count badges
- **PR**: #5 merged to master

### UI Redesign ✅ COMPLETE

- [x] Dark navy theme — oklch color palette, purple accent, removed light mode
- [x] Layout system — Icon rail (vertical nav) + collapsible ThreadPanel + content area via `AppLayout.tsx`
- [x] ChatPage refactor — 231 → 35 lines, state extracted to `useChatState.ts` hook + `ChatContext.tsx`
- [x] Welcome screen — brand icon, greeting, `MessageInput`, `SuggestionChips` (interactive, pre-fills chat input on click)
- [x] Full i18n — Indonesian (default) + English, `I18nProvider` with localStorage persistence
- [x] i18n coverage — AuthPage, FileUpload, DocumentList all use `useI18n()` translations
- [x] Admin input styling — number inputs use `bg-secondary text-foreground` for dark theme
- [x] Deleted `App.css` — styles consolidated into `index.css` with CSS variables

#### UI Redesign Architecture Summary

- **Layout**: `AppLayout` wraps `<Outlet>` with `IconRail` (60px) + conditional `ThreadPanel` (240px); thread panel shown only on chat routes
- **State**: `useChatState` hook manages threads, messages, streaming, tool/agent events; exposed via `ChatContext`
- **i18n**: `I18nProvider` → `useI18n()` → `t(key, params?)` with `{param}` interpolation; 2 locales (id, en); persisted to localStorage
- **Theme**: Dark-only, oklch color space, custom CSS variables for icon-rail and sidebar colors
- **Components**: `IconRail` (brand + nav + avatar), `ThreadPanel` (new chat + date-grouped threads), `UserAvatar` (initials + sign-out menu), `WelcomeScreen` (greeting + input + chips)

### Admin i18n + Cleanup ✅ COMPLETE

- [x] AdminSettingsPage fully i18n-ized — 30 translation keys (Indonesian + English) for all sections: LLM, embedding, RAG config, tool calling, sub-agents, errors, save actions
- [x] `.gitignore` updated — rules for `*.png`, `*.zip`, `excalidraw.log`, `.playwright-mcp/` to remove design asset clutter
- [x] UI redesign deployed to production (Vercel + Railway)

### Module 10: Conversation Branching ✅ COMPLETE

- [x] Migration `supabase/migrations/009_conversation_branching.sql` — add `parent_message_id` column, index, backfill existing linear chains
- [x] Backend `chat.py` — accept `parent_message_id`, branch-aware history loading (walk ancestor chain), chain user + assistant message inserts
- [x] Frontend `messageTree.ts` — `buildChildrenMap`, `getActivePath`, `getForkPoints` utilities
- [x] Frontend `useChatState.ts` — `allMessages`, `branchSelections`, `forkParentId` state; `handleSwitchBranch`, `handleForkAt`, `handleCancelFork` handlers
- [x] Frontend `MessageView.tsx` — fork button (GitFork icon on hover), `BranchIndicator` (1/3 with arrows) at fork points
- [x] Frontend `MessageInput.tsx` — fork-mode banner with cancel button
- [x] Frontend `ChatPage.tsx` — wire new props from context
- [x] Frontend `database.types.ts` — `parent_message_id` on Message interface
- [x] i18n — `branch.forkMode`, `branch.fork`, `branch.cancel` in Indonesian + English
- [x] End-to-end tested — backward compat (existing threads load), new message chaining, fork creation (two children of same parent), branch-aware LLM history (only ancestor messages sent)

#### Module 10 Architecture Summary

- **Message tree**: `parent_message_id` self-FK on `messages` table; adjacency list pattern
- **Backfill**: Existing linear conversations auto-linked via `LAG()` window function in migration
- **History construction**: When `parent_message_id` provided, backend walks ancestor chain from that message to root; only ancestor messages sent to LLM
- **Frontend tree**: `buildChildrenMap` groups messages by parent; `getActivePath` walks tree following `branchSelections`; only the active branch path is rendered
- **UI**: Fork icon appears on hover; clicking sets `forkParentId` and shows banner in input area; after send, new branch created; fork points show `BranchIndicator` with left/right arrows to switch
- **Backward compatible**: Existing flat threads work unchanged (backfill sets parent chains; `parent_message_id=None` falls back to flat mode)
- **New env vars**: None — uses existing infrastructure
- **New tables**: None — single column addition to `messages`

#### Sub-Plan Files

- `.claude/plans/enumerated-hugging-otter.md`

### Figma UI Migration ✅ COMPLETE

- [x] Shared components — `FeaturePageLayout`, `DropZone`, `HistorySection`, `EmptyState`, `SectionLabel` in `components/shared/`
- [x] IconRail expanded to 6 nav items (Chat, Documents, Create, Compare, Compliance, Analysis) + flyout "More Modules" menu
- [x] `DocumentCreationPage` — doc type selector, form fields, language toggle, reference/template uploads (static UI)
- [x] `DocumentComparisonPage` — dual document upload, swap button, comparison focus selector (static UI)
- [x] `ComplianceCheckPage` — doc upload, framework selector, scope multi-select, context textarea (static UI)
- [x] `ContractAnalysisPage` — doc upload, analysis type multi-select, governing law, depth selector (static UI)
- [x] All 4 pages wired to backend with API calls, loading states, and result display panels
- [x] Full i18n support (Indonesian + English) for all new screens (~80 keys per locale)
- [x] Feature accent colors added (creation/purple, management/cyan, compliance/emerald, analysis/amber)
- [x] shadcn/ui select, textarea, popover components installed
- [x] Routes added to `App.tsx` for `/create`, `/compare`, `/compliance`, `/analysis`

### Document Tool Backend ✅ COMPLETE

- [x] Backend service `document_tool_service.py` — Pydantic response models + LLM prompts for all 4 operations (create, compare, compliance, analyze), reuses `parse_text` from ingestion service, OpenRouter with `json_object` response format
- [x] Backend router `document_tools.py` — 4 FormData endpoints (`POST /document-tools/create`, `/compare`, `/compliance`, `/analyze`), file upload validation, auth required
- [x] Router registered in `main.py`
- [x] Frontend wiring — all 4 pages updated with controlled form state, `apiFetch` calls, loading spinners, error display, structured result rendering in right panel
- [x] Create page: generated document preview (title, summary, content)
- [x] Compare page: differences table with significance badges, risk assessment, recommendation
- [x] Compliance page: overall status badge (pass/review/fail), findings list, missing provisions
- [x] Analysis page: risk cards, obligations table, critical clauses, missing provisions
- [x] QA fix: Generate Draft button disabled until required fields are filled (per doc type validation)
- [x] Backend fix: bilingual document creation handles dict content response from LLM
- [x] Result persistence: `document_tool_results` Supabase table with RLS, history endpoints, frontend history sidebars

#### Document Tool Architecture Summary

- **Pattern**: File upload → parse text (reuse ingestion `parse_text`) → LLM structured output (OpenRouter + `json_object` format) → Pydantic validation → JSON response → persist to `document_tool_results`
- **Persistence**: Results stored in `document_tool_results` table (JSONB), history sidebar shows recent results per tool type, `GET /document-tools/history` endpoint
- **File handling**: FormData with optional files (reference/template for creation, two docs for comparison, single doc for compliance/analysis)
- **Truncation**: Document text capped at ~48k chars (~12k tokens) to stay within LLM context
- **Validation**: Red border + inline error messages on required fields when clicking disabled button; per doc type required field lists
- **No new dependencies**: Reuses existing OpenRouter service, ingestion parser, auth middleware

#### Sub-Plan Files

- `.agent/plans/11.figma-ui-migration.md`

### Welcome Screen Redesign ✅ COMPLETE

- [x] Sparkle icon replaces "K" badge, gradient text for user name
- [x] `WelcomeInput` — large card-style input with action bar (attach, doc icon, "Legal AI v1.0" label, mic, send)
- [x] `SuggestionCards` — Bento grid with left accent borders + inline icons (no icon circles), responsive (stacks on mobile)
- [x] `ThreadPanel` — search bar, "Chat History" subtitle, fully collapsible (340px expanded ↔ hidden), toggle in IconRail

### Page Layout Redesign ✅ COMPLETE

- [x] `DocumentCreationPage` — 3-column layout (Icon Rail | Form 75% + History 25% | Preview empty state), dynamic form fields per doc type (Generic, NDA, Sales, Service), output language radio, reference/template uploads
- [x] `DocumentsPage` — 3-column layout with upload section (dropzone, recent uploads, storage quota), filter section (type filters, status checkboxes), main area (top bar with search + grid/list toggle, responsive document card grid)
- [x] `DocumentComparisonPage` — same 3-column pattern with dual doc upload, swap button, comparison focus, blank results area
- [x] `ComplianceCheckPage` — same 3-column pattern with framework selector, scope multi-select, blank results area
- [x] `ContractAnalysisPage` — same 3-column pattern with analysis type, governing law, depth selector, blank results area
- [x] All column 2 panels standardized to 340px width
- [x] Unified sidebar collapse — shared state via `useSidebar` hook, `PanelLeftClose`/`PanelLeftOpen` icons, panels collapse fully (no 50px strip)
- [x] Settings/Admin pages — 3-column layout with section navigation, centered content with section icons

### Design Quality (A / A+) ✅ COMPLETE

- [x] **Mobile responsive** — hamburger menu header, panel overlays with backdrop, responsive grids, FAB on all feature pages
- [x] **AI slop eliminated** — icon-in-circle cards replaced with accent-border + inline icon, pulse rings removed from EmptyState
- [x] **Touch targets** — all interactive elements 40px+, icon rail 44px, focus-ring on all custom buttons
- [x] **Accessibility** — `prefers-reduced-motion` support for all animations, focus-visible rings on all interactive elements
- [x] **Micro-interactions** — `interactive-lift` hover effect, purposeful active/press states
- [x] **Typography hierarchy** — `font-extrabold tracking-tight` on page headings, 3-tier weight system
- [x] **Document card variety** — category-colored left borders, colored dots, multi-format file type badges (PDF/DOC/MD/CSV/JSON/TXT)
- [x] **Chat layout** — input pinned to bottom, messages scroll above (matches ChatGPT/Claude pattern)
- [x] **Indonesian language** — all panel subtitles translated, consistent language throughout
- [x] **Design Score: A** | **AI Slop Score: A+** (verified by /design-review regression audit)

### 2026 Design System ✅ COMPLETE

- [x] **Font**: Geist Variable (single family, not a default stack)
- [x] **Colors**: oklch/oklab color space, 11 unique colors, coherent dark navy palette
- [x] **Glassmorphism** — `glass` utility on Icon Rail, ThreadPanel, MessageInput, AuthPage, WelcomeInput
- [x] **Layered shadows** — `--shadow-xs/sm/md/lg` CSS variables
- [x] **Gradient accents** — gradient user message bubbles, gradient text for user name
- [x] **Bento grid** — Row 1: equal halves, Row 2: wider left (3fr) + narrower right (2fr)
- [x] **Mesh background** — radial glows, dot grid texture, floating orbs
- [x] **Staggered animations** — `stagger-children` for sequential card entrance
- [x] **Feature accent colors** — per-page left border colors (purple/cyan/emerald/amber)
- [x] **Icon Rail gradient bar** — 3px gradient left accent on active nav items

---

## Deployment Status

### Frontend (Vercel) — ✅ DEPLOYED

- **URL**: https://frontend-one-rho-88.vercel.app
- **Platform**: Vercel (auto-detected Vite)
- **Env vars**: `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`, `VITE_API_BASE_URL` (points to Railway backend)
- **Redeploy**: `cd frontend && npx vercel --prod`

### Backend (Railway) — ✅ DEPLOYED

- **URL**: https://api-production-cde1.up.railway.app
- **Platform**: Railway (Dockerized FastAPI)
- **Health check**: `GET /health` → `{"status": "ok"}`
- **CORS**: Configured via `FRONTEND_URL` env var (comma-separated origins)
- **Redeploy**: `cd backend && railway up`

### Git History

| PR | Branch | Description | Status |
|----|--------|-------------|--------|
| #1 | `feat/module-6-7` | Modules 6+7 — Hybrid Search + Tool Calling | Merged |
| #2 | `feat/module-8-sub-agents` | Module 8 — Sub-Agent Architecture | Merged |
| #3 | `feat/deploy` | Deploy backend (Railway) + frontend (Vercel) | Merged |
| #4 | `feat/rbac-settings` | Module 9 — RBAC Settings Architecture | Merged |
| #5 | `feat/ui-improvements` | Animated thinking indicator + collapsible thread groups | Merged |

---

## PJAA CLM Platform Upgrade

Based on PJAA stakeholder survey (53 questions, 7 findings) — see `References/PJAA-Research-Synthesis-CLM-Compliance.docx.md`.
Full gap analysis and specs: `.agent/plans/15.pjaa-clm-gap-analysis-specs.md`

### Phase 1: Go-Live Foundation (Weeks 1-8)

#### Feature 1: Audit Trail & Activity Logging ✅ COMPLETE

- [x] Migration `supabase/migrations/011_audit_trail.sql` — `audit_logs` table with 4 indexes, RLS enabled (admin-only read)
- [x] Backend `audit_service.py` — fire-and-forget `log_action()` function, service-role client
- [x] Backend `audit_trail.py` router — `GET /admin/audit-logs` (paginated + filtered), CSV export, distinct actions
- [x] Instrumented 4 existing routers (documents, document_tools, admin_settings, threads) with audit log calls
- [x] Frontend `AuditTrailPage.tsx` — admin-only, date/action/resource filters, pagination, CSV export button
- [x] Route at `/admin/audit`, nav link in SettingsPage (mobile + desktop)
- [x] i18n: 17 keys in both Bahasa Indonesia and English
- [x] Security hardening: RLS enabled on audit_logs (caught by adversarial review — was exposed via PostgREST)
- **Commit**: `59a277a`, hardening fix: `ca60078`

#### Feature 7: Bahasa Indonesia Full-Text Search ✅ COMPLETE

- [x] Migration `supabase/migrations/010_bahasa_fts.sql` — FTS trigger + RPC switched from `'english'` to `'simple'` config
- [x] Backfill existing document chunks with new config
- [x] No backend/frontend changes needed — existing search automatically benefits
- **Commit**: `59a277a`

#### Feature 2: AI Confidence Scoring & HITL Gates ✅ COMPLETE

- [x] Migration `supabase/migrations/012_confidence_hitl.sql` — `confidence_score`, `review_status`, `reviewed_by/at/notes` on `document_tool_results`; `confidence_threshold` on `system_settings`; RLS for admin review access
- [x] All 4 Pydantic models updated with `confidence_score: float = 0.0`
- [x] All 4 LLM system prompts request `confidence_score` in JSON response
- [x] `_save_result` computes `review_status` based on configurable threshold (default 0.85)
- [x] Review queue endpoints: `GET /document-tools/review-queue`, `PATCH /document-tools/review/{id}` with `ReviewAction` Pydantic model
- [x] `get_result` endpoint updated — admins can view any user's results (for review)
- [x] `ConfidenceBadge.tsx` component — percentage badge + review status badge
- [x] Badges added to all 4 tool result pages (DocumentCreation, Comparison, Compliance, Analysis)
- [x] `ReviewQueuePage.tsx` — filter by status, approve/reject with notes, audit logged
- [x] `AdminSettingsPage.tsx` — HITL Gates section with threshold input + visual preview
- [x] i18n: 22 keys in both Bahasa Indonesia and English
- [x] Security hardening: `ReviewAction` Pydantic model (validates action, caps notes at 2000 chars), re-review guard (409 if not pending), `confidence_threshold` bounded to 0.0-1.0
- **Commit**: `7c4b20e`, hardening fix: `ca60078`

#### Feature 4: Obligation Lifecycle Tracker ✅ COMPLETE

- [x] Migration `supabase/migrations/013_obligations.sql` — `obligations` table with 15 columns, RLS (4 policies), 3 indexes, `updated_at` trigger, `check_overdue_obligations()` RPC
- [x] Backend `obligations.py` router — 7 endpoints: list (filtered), summary, create, extract from analysis, check-deadlines, update, soft-delete
- [x] Frontend `ObligationsPage.tsx` — summary cards (5 statuses), filter tabs, obligations table with status badges, deadline formatting (relative), "Mark Complete" button
- [x] "Import Obligations" button on `ContractAnalysisPage.tsx` — extracts obligations from analysis results into structured rows
- [x] IconRail nav item (`ClipboardList` icon) + route at `/obligations`
- [x] i18n: 23 keys in both Bahasa Indonesia and English
- **Commit**: `d5ca1be`

#### Feature 3: Enhanced Drafting Workbench ✅ COMPLETE

- [x] Migration `supabase/migrations/014_drafting_workbench.sql` — `clause_library` + `document_templates` tables, RLS (own + global), indexes, triggers, 12 seeded global Indonesian legal clauses
- [x] Backend `clause_library.py` router — 6 endpoints (list with filters, get, create, create global/admin, update, delete)
- [x] Backend `document_templates.py` router — 5 endpoints (list, get with clause resolution, create, update, delete)
- [x] Backend `document_tool_service.py` — `create_document()` accepts `clauses` param, LLM prompt requests `clause_risks`, `GeneratedDocument` model updated
- [x] Backend `document_tools.py` — create endpoint accepts `clause_ids` + `template_id` Form fields, fetches/merges template defaults and clause content
- [x] 9 doc types — added vendor, JV, property lease, employment, SOP/board resolution with per-type form fields and validation
- [x] Frontend clause selector — picker with risk-colored items, selected clause chips, mismatch warnings, clause_ids in submission
- [x] Frontend template selector — dropdown with pre-fill on select, "Save as Template" persists current form state
- [x] Frontend per-clause risk badges — `clause_risks` rendered in results area with risk-colored cards
- [x] `ClauseLibraryPage.tsx` — 2-panel layout (filter/search + clause cards grid), CRUD, global clause badges
- [x] IconRail nav item (`Library` icon), route at `/clause-library`
- [x] i18n: ~45 keys per locale (doc types, clause library, templates, risk levels, categories)

#### Feature 5: Approval Workflow Engine ✅ COMPLETE

- [x] Migration `supabase/migrations/015_approval_workflows.sql` — `approval_workflow_templates`, `approval_requests`, `approval_actions` tables with RLS, indexes, seeded default template
- [x] Backend `approvals.py` router — submit for approval, inbox (admin), my requests, get detail with actions + resource, take action (approve/reject/return), cancel, template CRUD (admin)
- [x] Frontend `ApprovalInboxPage.tsx` — mobile-first 2-panel layout, inbox vs my requests toggle, status filter tabs with count badges, action buttons (approve/reject/return/cancel)
- [x] IconRail nav item (`FileCheck` icon), route at `/approvals`
- [x] i18n: 17 keys per locale for approvals

#### Feature 6: MFA & Security Hardening ✅ COMPLETE

- [x] Migration `supabase/migrations/016_security_hardening.sql` — `user_profiles` table (display_name, department, is_active, deactivated_at/by), `mfa_required` + `session_timeout_minutes` on system_settings, backfill existing users
- [x] Backend `user_management.py` router — list users (admin), deactivate/reactivate (admin), get/update own profile (self-service)
- [x] Frontend `UserManagementPage.tsx` — admin user list with search, status badges, deactivate/reactivate buttons with confirmation
- [x] Frontend `SettingsPage.tsx` — Security section with MFA info panel + session timeout info, User Management admin link
- [x] Route at `/admin/users` (admin-guarded)
- [x] i18n: 20 keys per locale for user management + security

### Phase 1 Summary

| Feature | Status | Commit | Lines |
|---------|--------|--------|-------|
| F1: Audit Trail | ✅ Done | `59a277a` | +1,994 |
| F7: Bahasa FTS | ✅ Done | `59a277a` | (included above) |
| F2: Confidence & HITL | ✅ Done | `7c4b20e` | +553 |
| Hardening (review fixes) | ✅ Done | `ca60078` | +30 |
| F4: Obligation Tracker | ✅ Done | `d5ca1be` | +1,519 |
| F3: Drafting Workbench | ✅ Done | `55f7c05` | +1,200 |
| F5: Approval Workflows | ✅ Done | `55f7c05` | +600 |
| F6: MFA & Security | ✅ Done | `55f7c05` | +400 |

**Phase 1 progress: 7 of 7 features complete** (F1, F2, F3, F4, F5, F6, F7) ✅ PHASE 1 COMPLETE

### Phase 2: Enterprise Capabilities (Weeks 9-16) ✅ COMPLETE

#### Feature 8: Regulatory Intelligence Engine ✅ COMPLETE

- [x] Migration `supabase/migrations/017_regulatory_intelligence.sql` — `regulatory_sources`, `regulatory_updates` (with vector embedding), `regulatory_alerts` tables, RLS, indexes, 4 seeded Indonesian regulatory sources (JDIH, IDX, OJK, Perda DKI)
- [x] Backend `regulatory.py` router — 9 endpoints: source CRUD (admin), update feed with filters, mark read, alerts inbox, dismiss alert
- [x] Frontend `RegulatoryPage.tsx` — 2-panel layout, source type filter, update feed with relevance badges, read/unread state, admin source management
- [x] IconRail nav item (`BookOpen` icon), route at `/regulatory`

#### Feature 9: WhatsApp Notifications ✅ COMPLETE

- [x] Migration `supabase/migrations/018_whatsapp_notifications.sql` — `notification_channels` (per-user, multi-channel), `notification_log` (delivery tracking), WhatsApp settings on `system_settings`
- [x] Backend `notifications.py` router — 6 endpoints: channel CRUD, notification history, admin send (inserts pending record for dispatcher)
- [x] Notification infrastructure ready for WhatsApp Business API integration (requires Meta Business verification)

#### Feature 10: Executive Dashboard ✅ COMPLETE

- [x] Backend `dashboard.py` router — 3 endpoints: aggregate summary (documents/obligations/approvals/compliance/regulatory counts), obligation timeline (next 90 days), compliance trend (last 6 months by month)
- [x] Frontend `DashboardPage.tsx` — responsive grid with 5 summary cards (color-coded), obligation timeline with priority badges, compliance trend with CSS bars
- [x] IconRail nav item (`LayoutDashboard` icon) as first nav item, route at `/dashboard`

#### Feature 11: Dokmee DMS Integration ✅ COMPLETE

- [x] Migration `supabase/migrations/019_dms_integration.sql` — DMS settings on `system_settings`, `external_source` + `external_id` on documents
- [x] Backend `integrations.py` router — 4 endpoints: status check, browse folders, import, export (production-ready stubs pending Dokmee API access)
- [x] Frontend `IntegrationsPage.tsx` — Dokmee card with configured/not-configured status, action buttons

#### Feature 12: Google Workspace Export ✅ COMPLETE

- [x] Migration `supabase/migrations/020_google_integration.sql` — `google_tokens` table (per-user OAuth2), Google OAuth settings on `system_settings`
- [x] Backend `google_export.py` router — 5 endpoints: status, auth URL, OAuth callback, export to Drive, disconnect (production-ready stubs pending Google OAuth setup)
- [x] Frontend `IntegrationsPage.tsx` — Google Drive card with configured + connected status, connect/disconnect buttons

**Phase 2 progress: 5 of 5 features complete** (F8, F9, F10, F11, F12) ✅ PHASE 2 COMPLETE

### BJR Decision Governance Module ✅ COMPLETE

- [x] Design spec (`docs/superpowers/specs/2026-04-17-bjr-governance-module.md`)
- [x] Migration `supabase/migrations/021_bjr_governance.sql` — 6 tables, RLS, indexes, seed data
- [x] Backend `bjr.py` router — 25 endpoints (decisions, evidence, phase progression, risks, admin CRUD, summary)
- [x] Backend `bjr_service.py` — LLM evidence assessment, BJR score calculation, phase advancement
- [x] Backend `models/bjr.py` — 12 Pydantic request/response models
- [x] Approval integration — `approvals.py` handles `resource_type='bjr_phase'`, auto-advances on approval
- [x] Dashboard extension — BJR metrics in `/dashboard/summary`
- [x] Frontend `BJRDashboardPage.tsx` — decision overview, summary cards, create modal, standing risks
- [x] Frontend `BJRDecisionPage.tsx` — decision lifecycle, phase stepper, checklist with evidence, risk register
- [x] 4 BJR components: PhaseProgress, ChecklistItem, EvidenceAttachModal, RiskCard
- [x] IconRail standalone nav item (`Scale` icon → `/bjr`)
- [x] i18n: 88 keys (44 Indonesian + 44 English)
- [x] Seed data: 28 regulations (4 layers), 16 checklist items (3 phases), 11 GCG aspects, 4 standing risks
- [x] Production smoke test: 8/8 passed
- **Commit**: `c7d2e02`

#### BJR Module Architecture Summary

- **Decision lifecycle**: Pre-Decision → Decision → Post-Decision → Completed, with phase-gated approvals
- **Evidence linking**: Polymorphic references to existing LexCore entities (documents, tool results, approvals) via `reference_id` + `reference_table`
- **LLM assessment**: Each evidence attachment can be assessed by LLM against its specific BJR checklist requirement, with confidence scoring and HITL review
- **Configurable framework**: Regulations, checklist items, GCG aspects stored as data (admin-manageable), seeded with Ancol's specific requirements
- **Integration**: Reuses existing approval workflows, audit trail, HITL confidence gating, executive dashboard
- **Source document**: `Matriks_Regulasi_GCG_BJR_Ancol_2026.docx` — Ancol GCG & BJR regulatory matrix

### Phase 3: Advanced Compliance (Months 5-6) ✅ COMPLETE

#### Feature 13: Point-in-Time Compliance Querying ✅ COMPLETE

- [x] Migration `supabase/migrations/022_compliance_snapshots.sql` — `compliance_snapshots` table with RLS
- [x] Backend `compliance_snapshots.py` router — 4 endpoints (create, list, get, diff)
- [x] Snapshot creation reuses existing `check_compliance()` from `document_tool_service.py`
- [x] Diff logic — pure JSON comparison of findings, missing provisions, status changes
- [x] Frontend `ComplianceTimelinePage.tsx` — timeline view with A/B snapshot comparison
- [x] "Save as Snapshot" button added to `ComplianceCheckPage.tsx`
- [x] IconRail: Clock icon in Legal Tools group → `/compliance/timeline`
- **Commit**: `56ef7d5`

#### Feature 14: UU PDP Compliance Toolkit ✅ COMPLETE

- [x] Migration `supabase/migrations/023_uu_pdp_toolkit.sql` — 3 tables (`data_inventory`, `pdp_compliance_status`, `data_breach_incidents`) with DPO-aware RLS
- [x] Backend `pdp.py` router — 13 endpoints (inventory CRUD, compliance status, readiness, incidents, notification template, PII scanner)
- [x] Backend `pdp_service.py` — LLM personal data scanner + readiness score calculator (DPO 20pts + breach plan 20pts + inventory 30pts + DPIA 30pts)
- [x] Backend `models/pdp.py` — Pydantic models with Literal types
- [x] `require_dpo()` dependency in `dependencies.py` for DPO role support
- [x] Frontend `PDPDashboardPage.tsx` — readiness score circle, DPO appointment form, checklist, status cards
- [x] Frontend `DataInventoryPage.tsx` — processing activity table + create modal
- [x] Frontend `DataBreachPage.tsx` — incident list with 72-hour deadline countdown + notification template generator
- [x] IconRail: ShieldAlert standalone item → `/pdp`
- [x] Dashboard: PDP readiness + snapshot count in `/dashboard/summary`
- [x] i18n: ~100 keys (50 ID + 50 EN) for PDP module
- **Commit**: `05d0a9a`

**Phase 3 progress: 2 of 2 features complete** (F13, F14) ✅ PHASE 3 COMPLETE
