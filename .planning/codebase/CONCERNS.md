# Codebase Concerns

**Analysis Date:** 2026-04-25
**Project:** LexCore PJAA CLM Platform
**Scope:** Tech debt, bugs, security risks, performance hotspots, fragile areas, lint state, gotchas

---

## Hardcoded Secrets Audit

**Status:** No hardcoded secrets, API keys, or credentials detected in committed source.

- `.env`, `.env.*`: Present but git-ignored. Existence noted only — contents not read.
- API keys for OpenRouter, OpenAI, Cohere, Supabase service role: All sourced from env vars via `app.config.get_settings()`.
- Test credentials for `test@test.com` / `test-2@test.com`: Documented in `CLAUDE.md` (intentional, dev-only) and passed via env vars in `pytest` runs. Acceptable for development; if `CLAUDE.md` is exposed publicly, rotate these accounts.
- PreToolUse hook blocks `.env` edits — no risk of inadvertent commit.

**Recommendation:** Maintain current pattern. Add a CI guard (e.g., `gitleaks` or `trufflehog`) in the pre-push step to harden against future regressions.

---

## Tech Debt

### BLOCKER

**None identified at the BLOCKER tier.** All BLOCKER-class issues from prior phases have been remediated through the migration sequence (001–028) and RBAC hardening (016).

### HIGH

**Dual mobile + desktop form duplication in `DocumentCreationPage`:**
- Files: `frontend/src/pages/DocumentCreationPage.tsx`
- Issue: Both mobile and desktop panels render fully separate copies of the document creation form. Adding a new form field requires editing two parallel JSX blocks; one is regularly missed in feature commits.
- Impact: Drift between mobile and desktop UX, inconsistent validation, double the surface area for layout bugs.
- Fix approach: Extract a shared `<DocumentCreationForm />` subcomponent that both responsive containers render. Keep responsive wrappers for layout (sidebar vs overlay), but move all form state and field markup into one source of truth.

**Pre-existing ESLint errors in `DocumentsPage`:**
- Files: `frontend/src/pages/DocumentsPage.tsx`
- Issue: 6 `react-hooks/set-state-in-effect` errors (confirmed pre-existing as of 2026-04-23). The page's `useEffect` blocks call `loadFolders()` / `loadDocuments()` which `setState`, triggering the rule. The current pattern uses `useCallback` dependencies so the effect re-runs only when `currentFolderId` changes, but ESLint cannot prove the indirection is safe.
- Impact: Lint output is noisy; new regressions can be hidden in the existing error count; CI cannot enforce a clean lint state.
- Fix approach: Either (a) refactor effect bodies into idempotent fetch functions that defer setState behind a `useTransition`, (b) suppress the rule with a `// eslint-disable-next-line` and a comment justifying the pattern, or (c) migrate data loading to TanStack Query / SWR so effects no longer drive state.

**`get_current_user` performs an extra DB roundtrip on every authenticated request:**
- Files: `backend/app/dependencies.py` (lines 8–37)
- Issue: Every request decodes the JWT *and* selects from `user_profiles` to verify `is_active`, plus auto-creates a profile row if missing. That is two RPCs per request to Supabase.
- Impact: Adds 50–150 ms latency to every authenticated endpoint, multiplied across high-volume routes (chat SSE keep-alives, document polling, dashboard widgets). Also a hot path for Supabase quota.
- Fix approach: Cache `(user_id → is_active)` in-memory with a short TTL (e.g., 30 s) keyed by `user_id`, invalidated on user-management mutations. Alternatively, mirror `is_active` into JWT app_metadata at signup/deactivation and trust the JWT.

### MEDIUM

**`system_settings` cache is a module-level global with no invalidation across processes:**
- Files: `backend/app/services/system_settings_service.py`
- Issue: 60-second TTL cache lives in process memory. When admin updates settings via `/admin/settings`, only the worker that handled the PATCH clears its cache; sibling Uvicorn workers (and other Railway replicas) continue serving stale settings until their TTL elapses.
- Impact: Up to 60 s of inconsistent behaviour after admin changes (new RAG weights, model selection, agent toggles). Hard to debug because behaviour depends on which worker handles the next request.
- Fix approach: Either (a) move to Postgres LISTEN/NOTIFY so all workers invalidate on update, (b) use Supabase Realtime on the `system_settings` row, or (c) shorten the TTL to 5 s and accept the extra DB load.

**Semantic retrieval cache TTL invalidation is purely time-based:**
- Files: `backend/app/services/hybrid_retrieval_service.py` (lines 17–34, 71–94)
- Issue: 5-minute TTL with a 1000-entry LRU-ish cap. The cache key includes user_id, query, top_k, category, filter_tags, folder_id, date range — but **not** the embedding model, RAG weights, or document set. If a user uploads a document, deletes one, or admin tweaks `rag_vector_weight` / `rag_fulltext_weight`, cached results stay stale for up to 5 minutes.
- Impact: New documents may not surface in chat results immediately after upload. Confusing UX during demos and admin tuning.
- Fix approach: Add embedding model + a coarse "documents version" counter (bumped on insert/delete) into the cache key. Or expose a manual "Clear retrieval cache" admin button.

**Empty `except Exception: pass` in lifespan and SSE error path:**
- Files: `backend/app/main.py` (lines 13–19), `backend/app/routers/chat.py` (line 277)
- Issue: The startup recovery (`processing → pending`) and the thread-title auto-generation swallow all exceptions silently. If the DB is unreachable at boot or LangSmith blows up, nothing is logged.
- Impact: Failures are invisible until someone notices stuck documents or untitled threads. Hard to diagnose in production.
- Fix approach: Replace bare `pass` with `logger.exception(...)`. Keep the swallow (don't crash startup), but emit a structured log + LangSmith trace.

**Two `024_*.sql` migrations exist with the same numeric prefix:**
- Files: `supabase/migrations/024_knowledge_base_explorer.sql`, `supabase/migrations/024_rag_improvements.sql`
- Issue: Both are applied in production but share prefix `024_`. Some Supabase CLI commands sort lexicographically by full filename — order between them depends on which suffix comes first alphabetically.
- Impact: Fresh environments could replay them in a different order than production if the CLI sort changes. Renumbering is **forbidden** (per CLAUDE.md gotchas) because they are already applied — the PreToolUse hook blocks edits to 001–027.
- Fix approach: Document the canonical apply order in a README inside `supabase/migrations/`. For new migrations, always use `028_`+ and never reuse a prefix.

**`agents_enabled` codepath swallows orchestrator classification errors:**
- Files: `backend/app/routers/chat.py` (lines 172–181)
- Issue: If `agent_service.classify_intent()` raises, the code defaults to `"general"` agent silently. There is no SSE event communicating the fallback.
- Impact: Users receive responses from the wrong agent without indication. Difficult to detect regressions in classification.
- Fix approach: Emit `{"type": "agent_fallback", "reason": str(exc)}` SSE event and log the exception with stack trace.

### LOW

**Mock-up PNG screenshots committed to repo root:**
- Files: 25+ `.png` files in repo root (e.g., `auth-after-fixes.png`, `final-mobile.png`, `home-mobile.png`)
- Issue: Design-review screenshots committed at repo root, bloating clones and crowding `ls`.
- Impact: Slows fresh clones, distracts from actual project files, makes `find` / `git log` noisier.
- Fix approach: Move to `docs/screenshots/` or `.gitignore` them and store in an external artifact store (Vercel preview comments, Linear, Notion).

**Untracked uppercase asset files at root:**
- Files: `L.svg`, `Lex48.svg`, `LexCoreNew.svg`, `LexCoreNewLight.svg`, `axe.svg`, `lexcore-dark.svg`, `graphify-out/`
- Issue: Logo / brand assets and graphify outputs are untracked at repo root. Either they should be committed under `frontend/public/` or `.gitignore`d.
- Impact: Git status is noisy; risk of an asset being accidentally referenced from a relative path that doesn't exist in production.
- Fix approach: Move logos to `frontend/public/` (where Vite serves them) and add `graphify-out/` to `.gitignore`.

**Indonesian-language hardcoded strings in `DocumentsPage` filters:**
- Files: `frontend/src/pages/DocumentsPage.tsx` (lines 19–28)
- Issue: Filter labels (`'Kontrak'`, `'Kepatuhan'`, `'Laporan'`, `'Perjanjian'`) are hardcoded in Indonesian. The page already uses `useI18n()` for other strings.
- Impact: English locale users see Indonesian filter chips. i18n inconsistency.
- Fix approach: Move filter labels through `t()` / `I18nContext` and add corresponding keys to `en.json` and `id.json`.

---

## Known Bugs

### MEDIUM

**Branch-mode chat history can grow unbounded with cycle protection but no depth limit:**
- Files: `backend/app/routers/chat.py` (lines 56–74)
- Symptoms: For a deep conversation branch (hundreds of messages), the ancestor walk loads the entire thread's messages into memory and walks the chain.
- Trigger: Long-lived threads with many branched edits.
- Workaround: None currently. Cycle detection exists (`visited` set), but there is no `max_depth` cap.
- Fix approach: Add a depth limit (e.g., 200) and paginate older context out of the LLM window using sliding-window summarization.

**Vercel deploys from `main` not `master` — easy to forget:**
- Symptoms: Frontend changes pushed to `master` do not deploy. Backend (Railway) deploys from `master`. Drift between FE and BE happens silently.
- Trigger: Any push that omits `git push origin master:main`.
- Workaround: Use `/deploy-lexcore` skill which handles both pushes.
- Fix approach: Either (a) set Vercel to deploy from `master`, (b) add a GitHub Action that auto-mirrors `master` → `main`, or (c) make `master` the default branch and delete `main`.

### LOW

**`PROGRESS.md` shows a single `# Progress` heading but is actively used for state sync:**
- Files: `PROGRESS.md`
- Symptoms: File on disk reads only `# Progress` (line 1) but agent memory/timeline shows extensive checkpoint history.
- Trigger: A previous `/sync` may have truncated the file or memory layer is decoupled from the file.
- Workaround: Treat memory timeline as authoritative; treat file as a stub.
- Fix approach: Investigate the `/sync` skill and decide whether `PROGRESS.md` should be the source of truth or whether the memory timeline is canonical.

---

## Security Considerations

### HIGH

**Service-role client (`get_supabase_client`) bypasses RLS — used in lifespan, system_settings, and chat router:**
- Files: `backend/app/main.py:15`, `backend/app/services/system_settings_service.py:16,26`, `backend/app/routers/chat.py:41`
- Risk: Any future code path that accidentally uses `get_supabase_client()` for user-scoped data instead of `get_supabase_authed_client(token)` silently bypasses RLS.
- Current mitigation: Convention enforced in CLAUDE.md "Key Patterns"; `security-reviewer` agent flags RLS bypasses.
- Recommendations:
  1. Rename `get_supabase_client` → `get_supabase_service_client` to make the privilege escalation explicit at every call site.
  2. Add a pre-commit grep that flags any new use of the service-role client outside an allowlist of files.

**Audit logging is convention-based, not enforced:**
- Files: `backend/app/services/audit_service.py` (assumed location), routers across `backend/app/routers/`
- Risk: `log_action()` is called manually after each mutation. New routers can ship without audit logging and only get caught in code review.
- Current mitigation: `security-reviewer` agent reviews PRs; CLAUDE.md documents the requirement.
- Recommendations: Move audit logging to a FastAPI middleware that inspects the response and logs based on HTTP method (`POST/PATCH/PUT/DELETE`). Alternatively, add a Postgres trigger on each mutating table that writes to `audit_log`.

### MEDIUM

**Custom search-param sanitization for PostgREST filters is fragile:**
- Files: Wherever `.filter("col", "cs", "{...}")` or `.contains()` is used (per CLAUDE.md gotcha)
- Risk: Search params containing `,`, `(`, `)`, `"` must be sanitized before being passed to PostgREST string filters. A missed sanitizer is a SQL/PostgREST injection vector.
- Current mitigation: Documented gotcha; relies on developer awareness.
- Recommendations: Centralize a `safe_postgrest_value(s: str) -> str` helper and enforce its usage via lint rule or codemod.

**`get_current_user` auto-creates `user_profiles` row for unknown JWTs:**
- Files: `backend/app/dependencies.py` (lines 26–31)
- Risk: Any valid Supabase JWT (even from a different project linked to the same auth instance) triggers an INSERT into `user_profiles`. If JWT validation is misconfigured, this could fill the table with attacker-controlled rows.
- Current mitigation: Supabase's `auth.get_user(token)` validates against the project's JWT secret.
- Recommendations: Add an explicit check that `user.aud == "authenticated"` and that `user.id` belongs to the expected auth project. Rate-limit user_profile auto-creation.

### LOW

**`raw_app_meta_data.role = 'super_admin'` is the only RBAC gate:**
- Files: `backend/app/dependencies.py` (lines 40–53), RLS policies referencing `(auth.jwt() -> 'app_metadata' ->> 'role') = 'super_admin'`
- Risk: A single typo in RLS or `require_admin` exposes admin endpoints. No defense-in-depth.
- Current mitigation: `super_admin` role is set via service-role-only script (`scripts.set_admin_role`).
- Recommendations: Add a second factor — e.g., require admin endpoints to also pass an `X-Admin-Confirm` header that the FE only sets after re-auth. Periodic admin-role audit query in `dashboard.py`.

---

## Performance Bottlenecks

### HIGH

**Chat SSE streaming holds Postgres connections for the duration of the stream:**
- Files: `backend/app/routers/chat.py` (lines 36–286)
- Problem: The `event_generator` keeps the request open for the full LLM tool-loop + token stream (5–60 seconds). Postgres clients held by the request are not returned to the pool until the stream ends.
- Cause: Synchronous Supabase client calls inside an `async` generator. Each call may block the event loop.
- Improvement path: Migrate to `asyncpg` directly for hot paths, or wrap Supabase client calls with `asyncio.to_thread`. Also: short-lived connections — release the connection between tool iterations.

**`get_current_user` adds 1 extra DB query per authenticated request:**
- Files: `backend/app/dependencies.py` (line 21)
- Problem: `user_profiles.select("is_active").eq("user_id", ...)` runs on every request.
- Cause: Need to enforce account deactivation in real time.
- Improvement path: Cache `user_id → is_active` for 30 s in-memory; invalidate on user-management endpoints. Alternative: store `is_active` in JWT app_metadata.

### MEDIUM

**Hybrid retrieval cache is keyed on lowercase query but does not normalize whitespace:**
- Files: `backend/app/services/hybrid_retrieval_service.py` (line 33)
- Problem: `"What is X?"` and `"what is X? "` (trailing space) hash differently due to `.strip()` only on the outside; internal whitespace is preserved. Slight typing variations bypass the cache.
- Cause: Minimal normalization (`.lower().strip()`).
- Improvement path: Normalize via `re.sub(r"\s+", " ", q.lower().strip())` in `_cache_key`.

**Retrieval cache has no eviction past `_CACHE_MAX = 1000`:**
- Files: `backend/app/services/hybrid_retrieval_service.py` (lines 19, 71–94)
- Problem: The constant `_CACHE_MAX = 1000` is declared but I see no enforcement in the cache check path. Memory can grow until process restart.
- Cause: LRU eviction not implemented.
- Improvement path: Use `cachetools.TTLCache(maxsize=1000, ttl=300)` instead of a plain dict.

**Document tools call OpenRouter synchronously in series for compare/compliance:**
- Files: `backend/app/services/document_tool_service.py` (assumed), `backend/app/routers/document_tools.py`
- Problem: Multi-document operations (compare, compliance check) appear to run LLM calls one at a time.
- Cause: Sequential `await` patterns.
- Improvement path: Use `asyncio.gather()` for independent document analyses.

### LOW

**Frontend does not memoize `filtered` document list on every render:**
- Files: `frontend/src/pages/DocumentsPage.tsx` (lines 164–169)
- Problem: `documents.filter(...)` runs on every render with no `useMemo`. For 1000+ docs and frequent state changes (search input keystroke), this is O(n) per keystroke.
- Cause: Direct `.filter()` call in render body.
- Improvement path: Wrap in `useMemo` keyed on `[documents, statusFilters, typeFilter, searchQuery]`.

---

## Fragile Areas

### HIGH

**Glass-on-persistent-panel violations are easy to introduce:**
- Files: `frontend/src/components/ui/tooltip.tsx` (uses `backdrop-blur-2xl` — correct, transient), but any `backdrop-blur` on `frontend/src/components/layout/Sidebar.tsx` / chat input cards is forbidden.
- Why fragile: shadcn/ui defaults often include `backdrop-blur`. Copy-pasting from shadcn examples or the design 2026 spec without re-reading the rule introduces violations.
- Safe modification: When adding a new component, grep for `backdrop-blur` first. Add only to overlay components (`Tooltip`, `Popover`, `Dialog`, mobile overlay backdrops).
- Test coverage: Visual only — no automated lint rule. Add an ESLint rule that warns on `backdrop-blur` in files matching `**/layout/**` or `**/sidebar/**`.

**Base-ui tooltip `asChild` shim is non-obvious:**
- Files: `frontend/src/components/ui/tooltip.tsx` (lines 23–28)
- Why fragile: Base-ui's API uses `render` prop. Developers familiar with Radix expect `asChild` to "just work." The shim translates `asChild` → `render={children}`. If a developer writes `<Tooltip.Trigger asChild render={...}>`, both paths fight each other.
- Safe modification: Always use one or the other — `asChild` (forwarded by shim) OR `render` (native base-ui). Never both.
- Test coverage: None. Add a Storybook story exercising both forms.

### MEDIUM

**Form duplication in `DocumentCreationPage.tsx`:**
- Files: `frontend/src/pages/DocumentCreationPage.tsx`
- Why fragile: Mobile and desktop panels render duplicate JSX for the same form. State (`useState` hooks) is single-source, but the markup is forked.
- Safe modification: When adding a form field, search for the existing field in the file and add the new one in BOTH locations. Verify on both viewports before committing.
- Test coverage: No responsive snapshot tests. Add Playwright tests covering both 375px (mobile) and 1280px (desktop).

**`system_settings` is a single-row table, not a key-value store:**
- Files: `backend/app/services/system_settings_service.py`, `supabase/migrations/003_user_settings.sql`
- Why fragile: New developers expect `SELECT value FROM system_settings WHERE key = ?`. The actual schema has one row (`id=1`) with many columns. Misuse leads to subtle bugs (selecting the wrong column, inserting a second row that the cache ignores).
- Safe modification: Always go through `get_system_settings()` / `update_system_settings()`. Never write raw SQL against the table.
- Test coverage: No assertion that only one row exists. Add a CHECK constraint: `CHECK (id = 1)`.

**Pydantic v1 warning under Python 3.14:**
- Files: Triggered by `langsmith` package; visible on backend boot.
- Why fragile: Non-blocking warning today, but Pydantic v1 is deprecated. A future `langsmith` release could drop v1 support and break the import.
- Safe modification: Pin `langsmith==<known-good>` in `requirements.txt`. Watch for upstream migration to v2.
- Test coverage: `python -c "from app.main import app; print('OK')"` smoke test catches import errors but not deprecation regressions.

**Migrations 001–027 are write-locked by PreToolUse hook:**
- Files: `supabase/migrations/001_*.sql` through `027_*.sql`
- Why fragile: Hook blocks edits to applied migrations. If a migration has a typo or bug discovered post-apply, the *only* path is a new compensating migration (`028_*` and onward).
- Safe modification: Never attempt to edit applied migrations. Always create a new numbered migration to fix issues.
- Test coverage: Hook itself is the test.

### LOW

**Indonesian + English bilingual fulltext search uses `tsvector` config switching:**
- Files: `supabase/migrations/010_bahasa_fts.sql`
- Why fragile: PostgreSQL fulltext config selection happens at search time. Wrong config → poor recall in one language.
- Safe modification: Always test new search features against both `id.json` and `en.json` query sets.
- Test coverage: RAG eval golden set (`scripts/eval_rag.py`) — extend with bilingual cases.

---

## Scaling Limits

**Storage quota: hardcoded 50 MB per-user in UI:**
- Files: `frontend/src/pages/DocumentsPage.tsx` (line 204, 209)
- Current capacity: 50 MB per user (display only — not enforced server-side that I observed)
- Limit: Hardcoded constant; backend may not enforce.
- Scaling path: Move to admin-configurable `system_settings.user_storage_quota_mb`. Enforce server-side in `documents.py` upload handler.

**Retrieval cache: 1000-entry in-memory dict per worker:**
- Files: `backend/app/services/hybrid_retrieval_service.py` (line 19)
- Current capacity: 1000 unique queries per Uvicorn worker
- Limit: Memory exhaustion at scale (no eviction enforced); cache hit rate drops with more replicas (each has its own cache).
- Scaling path: Move to Redis with shared TTL once Railway gets a Redis addon.

**Audit log table grows unbounded:**
- Files: `supabase/migrations/011_audit_trail.sql`
- Current capacity: Postgres table with no partitioning or TTL.
- Limit: Performance degrades past ~10M rows for unindexed queries.
- Scaling path: Partition by month; archive to cold storage past 18 months.

---

## Dependencies at Risk

**`langsmith` (Python) — Pydantic v1 dependency on Python 3.14:**
- Risk: Emits Pydantic v1 deprecation warning. If langsmith upgrades and we're stuck on v1 elsewhere, version conflict.
- Impact: Logging/observability could break.
- Migration plan: Pin langsmith version; track upstream Pydantic v2 migration; consider replacing with direct OpenTelemetry instrumentation if migration stalls.

**`base-ui` (frontend) — pre-1.0, API may change:**
- Files: `frontend/src/components/ui/tooltip.tsx`
- Risk: `base-ui` API uses `render` prop; the shim in `tooltip.tsx` translates from `asChild`. Future versions may break.
- Impact: All tooltips break across the app.
- Migration plan: Lock `@base-ui/react` to a known-good version. Subscribe to release notes. Add Storybook visual regression tests.

**`shadcn/ui` — copy-paste model means upgrades are manual:**
- Files: `frontend/src/components/ui/*`
- Risk: shadcn updates require manual port. Components drift from upstream.
- Impact: Can't easily adopt upstream bugfixes.
- Migration plan: Document which shadcn version each component was copied from. Periodic audit to compare against upstream.

---

## Missing Critical Features

**No automated cross-process invalidation for `system_settings` cache:**
- Problem: 60-second window of inconsistent settings across Railway replicas after admin changes.
- Blocks: Confident admin tuning of RAG parameters in production.

**No retry/backoff on OpenRouter / OpenAI / Cohere failures:**
- Problem: Transient 429/500 from upstream LLM providers cause user-visible chat errors.
- Blocks: SLA-grade reliability.

**No request-level timeout on chat SSE streams:**
- Files: `backend/app/routers/chat.py`
- Problem: A stuck OpenRouter response holds the connection indefinitely.
- Blocks: Connection-pool exhaustion under load.

**No regression test for the dual mobile/desktop form pattern in `DocumentCreationPage`:**
- Problem: Form drift between viewports goes undetected.
- Blocks: Mobile parity guarantees.

---

## Test Coverage Gaps

**RBAC negative paths:**
- What's not tested: Non-admin attempts to call admin endpoints; deactivated user attempts to call any endpoint.
- Files: `backend/tests/api/` (8 test files)
- Risk: A future refactor could weaken `require_admin` and not be caught.
- Priority: HIGH

**RLS policy correctness:**
- What's not tested: That user A cannot select user B's documents/threads/messages even with valid JWT.
- Files: `supabase/migrations/*` policies
- Risk: A new migration could relax RLS without notice.
- Priority: HIGH

**SSE event ordering and shape:**
- What's not tested: That `agent_start → tool_start → tool_result → delta → done` order is preserved; that `done:true` is always sent even on error.
- Files: `backend/app/routers/chat.py`
- Risk: Frontend `useChatState` depends on this ordering; subtle backend changes can break the UX with no test alarm.
- Priority: MEDIUM

**Frontend i18n fallback:**
- What's not tested: That switching between `id` and `en` reloads strings everywhere.
- Files: `frontend/src/i18n/I18nContext.tsx`
- Risk: Mixed-language UI for English users (already observed in DocumentsPage filters).
- Priority: LOW

**Bilingual fulltext search recall:**
- What's not tested: Recall of Indonesian-only queries against an English-only document set, and vice versa.
- Files: `scripts/eval_rag.py` golden set
- Risk: Bilingual users get poor results in one language and not the other.
- Priority: MEDIUM

---

## Uncommitted State (As of 2026-04-25)

**Modified, not staged:**
- `PROGRESS.md` (file shows only `# Progress` line — likely truncated or memory-managed)
- `frontend/src/components/chat/SuggestionCards.tsx`

**Untracked (require disposition):**
- `AGENTS.md` (project-level agent registry)
- `L.svg`, `Lex48.svg`, `LexCoreNew.svg`, `LexCoreNewLight.svg`, `axe.svg`, `lexcore-dark.svg` (brand assets — should move to `frontend/public/` or commit at root)
- `docs/PRD-Agent-Harness.md`, `docs/PRD_SPECTRA7_Platform_v1.docx`, `docs/axe.svg` (product docs)
- `frontend/graphify-out/`, `frontend/src/graphify-out/`, `graphify-out/` (graph build outputs — should be `.gitignore`d)

**Recommendation:** Commit `AGENTS.md` + docs; move SVGs into `frontend/public/`; add `graphify-out/` to `.gitignore` at all three levels.

---

## CLAUDE.md Gotchas — Structured Reference

| Gotcha | Severity | Concern Category |
|--------|----------|------------------|
| Vercel deploys from `main`, not `master` | MEDIUM | Known Bugs / Deploy |
| `system_settings` is single-row, not key-value | MEDIUM | Fragile Areas |
| Base-ui tooltip `asChild` → `render` shim | MEDIUM | Fragile Areas |
| Glass forbidden on persistent panels | HIGH | Fragile Areas |
| Pydantic v1 warning on Python 3.14 | LOW | Dependencies at Risk |
| Supabase `cs` filter syntax (not `.contains()`) | MEDIUM | Security (sanitization) |
| PostgREST search-param sanitization (commas, parens) | MEDIUM | Security |
| `get_current_user` extra DB call per request | HIGH | Performance |
| Migrations are sequentially numbered; 001–027 write-locked | HIGH | Fragile Areas |
| Two `024_*.sql` files exist; do not renumber | MEDIUM | Tech Debt |

---

## Pre-Existing Lint State (Baseline)

**Frontend ESLint:** 6 errors in `frontend/src/pages/DocumentsPage.tsx` — all `react-hooks/set-state-in-effect`. Confirmed pre-existing as of 2026-04-23. **Do NOT count these as new regressions** in PR review. New errors introduced after this baseline are real regressions.

**Frontend `tsc --noEmit`:** Clean as of 2026-04-23 baseline.

**Backend `python -c "from app.main import app; print('OK')"`:** Passes with one Pydantic v1 deprecation warning from `langsmith` import. Non-blocking.

---

*Concerns audit: 2026-04-25*
