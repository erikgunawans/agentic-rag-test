# Coding Conventions

**Analysis Date:** 2026-04-25

## Naming Patterns

**Files:**
- Backend Python: `snake_case.py` (e.g. `chat.py`, `document_tool_service.py`, `audit_service.py`).
- Backend modules grouped by role: `backend/app/routers/*.py`, `backend/app/services/*.py`, `backend/app/models/*.py`.
- Frontend pages: `PascalCase.tsx` (e.g. `ChatPage.tsx`, `DocumentsPage.tsx`).
- Frontend components: `PascalCase.tsx`, grouped by feature in `frontend/src/components/<feature>/`.
- Frontend hooks: `useCamelCase.ts` (e.g. `useChatState.ts`, `useSidebar.ts`) in `frontend/src/hooks/`.
- Frontend contexts: `PascalCaseContext.tsx` (e.g. `frontend/src/contexts/ChatContext.tsx`).
- Test files: `test_<area>.py` in `tests/api/`, `<area>.spec.ts` in `tests/e2e/`.
- Migrations: `NNN_<description>.sql` (numbered 001-027) in `backend/migrations/`.

**Functions:**
- Python: `snake_case` (`get_current_user`, `require_admin`, `log_action`, `process_document`).
- Python private helpers: leading underscore (`_llm_json`, `_extract_text`, `_run_tool_loop`).
- TypeScript utilities: `camelCase` (`apiFetch`, `buildChildrenMap`, `formatBytes`).
- TypeScript event handlers: `handleX` (`handleSendMessage`, `handleSelectThread`, `handleCreateThread`).
- React components: `PascalCase` named function (`export function ChatPage()`).
- React hooks: `useCamelCase` (`useChatState`, `useChatContext`, `useSidebar`, `useI18n`).

**Variables:**
- Python: `snake_case`. Module-level singletons at the top: `router = APIRouter(...)`, `settings = get_settings()`, `logger = logging.getLogger(__name__)`.
- TypeScript: `camelCase` for state and locals (`activeThreadId`, `currentFolderId`).
- Constants: `UPPER_SNAKE_CASE` (`ALLOWED_MIME_TYPES`, `MAX_FILE_SIZE`, `SYSTEM_PROMPT` in `backend/app/routers/documents.py` and `chat.py`; `TYPE_FILTERS`, `STATUS_BADGE` in `frontend/src/pages/DocumentsPage.tsx`).

**Types:**
- Pydantic models: `PascalCase` request/response classes in same file (`SendMessageRequest`, `ClauseCreate`, `GeneratedDocument`, `ComparisonResult`, `AnalysisResult` in `backend/app/services/document_tool_service.py`).
- TypeScript types: `PascalCase` (`Thread`, `Message`, `Document`, `SSEEvent`) defined in `frontend/src/lib/database.types.ts`.
- Local TypeScript unions: `PascalCase` aliases (`type DocFilter = 'all' | 'nda' | ...`, `type ViewMode = 'grid' | 'list'`).

## Code Style

**Formatting:**
- No Prettier or Black config detected. Style is enforced informally.
- Python: 4-space indent, double quotes, type hints on every function, trailing commas in multi-line collections.
- TypeScript: 2-space indent, single quotes, no semicolons, trailing commas in multi-line collections.
- Frontend uses Tailwind utility classes inline; theme tokens live only in `frontend/src/index.css`.

**Linting:**
- Frontend: ESLint flat config at `frontend/eslint.config.js`. Extends `js.configs.recommended`, `tseslint.configs.recommended`, `reactHooks.configs.flat.recommended`, `reactRefresh.configs.vite`. `dist/` ignored.
- Run: `cd frontend && npm run lint`.
- TypeScript strict in `frontend/tsconfig.app.json` (`strict`, `noUnusedLocals`, `noUnusedParameters`, `noFallthroughCasesInSwitch`, `noUncheckedSideEffectImports`).
- Type check: `cd frontend && npx tsc --noEmit`.
- Backend: no linter configured. PostToolUse hook runs `python -m py_compile` and a full app-import smoke test on every Python edit.

**Type hints (Python):**
- All function signatures use type hints, including return types: `async def get_current_user(...) -> dict`, `def log_action(user_id: str | None, ...) -> None`.
- Modern union syntax: `str | None` over `Optional[str]`. `list[str]` over `List[str]`.
- Pydantic `BaseModel` for all request bodies and structured LLM outputs.

## Import Organization

**Python (backend):**
1. Standard library (`import json`, `import os`, `import uuid`).
2. Third-party (`from fastapi import ...`, `from pydantic import BaseModel`).
3. App-local (`from app.dependencies import get_current_user`, `from app.database import get_supabase_client`, `from app.services.audit_service import log_action`).

**TypeScript (frontend):**
1. React + node-modules (`import { useCallback } from 'react'`, `import { Search } from 'lucide-react'`).
2. Path-aliased internals via `@/` prefix (`@/lib/supabase`, `@/lib/api`, `@/hooks/useChatState`).
3. Type-only imports last and explicit: `import type { Thread, Message } from '@/lib/database.types'`.

**Path Aliases:**
- Frontend: `@/* → ./src/*` (configured in `frontend/tsconfig.app.json`). Use `@/...` consistently — never relative `../../` paths across feature boundaries.
- Backend: no aliases. Use `from app.<module> import ...`.

## Error Handling

**Backend (FastAPI):**
- Raise `HTTPException(status_code=N, detail="...")` for client errors. Examples: `404 "Thread not found"`, `400 "Unsupported file type ..."`, `401 "Invalid token"`, `403 "Account deactivated"`, `403 "Admin access required"`, `409 "This document is already being processed."`.
- `try/except` re-raises `HTTPException` first, then maps any other exception to `HTTPException(401, "Invalid or expired token") from e` to preserve traceback (see `get_current_user` in `backend/app/dependencies.py`).
- Audit logging is fire-and-forget — `log_action` in `backend/app/services/audit_service.py` swallows exceptions and logs a warning. Never let audit failures break a request.
- Lifespan recovery in `backend/app/main.py` resets stalled `processing` documents to `pending` on startup, wrapped in `try/except`.

**Frontend:**
- `apiFetch` in `frontend/src/lib/api.ts` parses the FastAPI `detail` field and throws `Error(detail || 'Request failed')` on non-OK.
- Page components catch and surface errors via toast/inline UI; `useChatContext()` throws if used outside its provider with message `'useChatContext must be used within ChatProvider'`.

## Logging

**Backend:**
- `logger = logging.getLogger(__name__)` at the top of every service module.
- `logger.warning("...: %s", e)` for non-fatal failures, `logger.info(...)` for state transitions.
- LangSmith tracing via `@traceable(name="...")` on LLM-facing functions (`@traceable(name="document_creation")` in `backend/app/services/document_tool_service.py`).

**Frontend:**
- No centralized logger. `console.log/error` used sparingly during development; remove before commit.

## Comments

**When to Comment:**
- Module docstrings on test files explain coverage IDs (`"""Chat Streaming API tests. Covers: CHAT-01, CHAT-02, CHAT-05, CHAT-06"""`).
- Section dividers in long service files use box-drawing characters: `# ── Pydantic response models ──────` (see `backend/app/services/document_tool_service.py`).
- Inline comments call out RLS implications and Supabase quirks (`# Auto-create profile for new signups`, `# Branch mode: walk ancestor chain from the specified parent`).
- Pydantic field comments for enum-like strings: `status: str  # "pass" | "review" | "fail"`.

**Docstrings:**
- Triple-quoted Python docstrings on services and helpers (`def _llm_json(...) -> dict: """Call OpenRouter and parse the JSON response."""`).
- TS files generally do not use JSDoc — types carry the contract.

## Function Design

**Size:** Most service functions are 20-80 lines. Routers favor inline logic in the endpoint and delegate to a service when reused (`process_document`, `log_action`, `_llm_json`). Long endpoints (e.g. `/chat/stream`) define inner async functions (`_run_tool_loop`) for SSE generators.

**Parameters:**
- Backend: dependencies via `Depends(get_current_user)` / `Depends(require_admin)`; request bodies as Pydantic models; query params via `Query(...)` with explicit defaults and bounds (`limit: int = Query(50, ge=1, le=100)`).
- Frontend: handlers receive minimal arguments and read state via `useChatContext()`; props are typed with explicit interfaces.

**Return Values:**
- FastAPI endpoints return dicts or Pydantic models (FastAPI serializes both). Paginated lists return `{"data": [...], "count": N}` (see `list_clauses` in `backend/app/routers/clause_library.py`).
- React components return `JSX.Element` from a single top-level fragment or `<div>`.

## Module Design

**Exports:**
- Python: `router = APIRouter(prefix="/...", tags=["..."])` is the public export, mounted in `backend/app/main.py` via `app.include_router(<module>.router)`.
- TypeScript: prefer named exports (`export function ChatPage()`, `export function useChatState()`, `export const ChatProvider = ...`). No default exports.

**Barrel Files:** No `index.ts` barrels. Import from the concrete file path.

## FastAPI Dependency Patterns

**Auth (`backend/app/dependencies.py`):**
- `get_current_user`: returns `{id, email, token, role}`. Validates Supabase JWT, checks `user_profiles.is_active`, auto-creates a profile on first login. Used on every authenticated endpoint.
- `require_admin`: chains `Depends(get_current_user)`, rejects unless `role == "super_admin"`.
- `require_dpo`: same pattern, allows `super_admin` or `dpo`.

**Database client helpers (`backend/app/database.py`):**
- `get_supabase_client()` — service-role client. Bypasses RLS. Use for trusted server logic, audit writes, system-settings reads.
- `get_supabase_authed_client(token)` — RLS-scoped using the user's JWT. Use whenever the user's data is being read or written. Pass `user["token"]` from the dependency.

**Standard router skeleton:**
```python
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from app.dependencies import get_current_user
from app.database import get_supabase_authed_client
from app.services.audit_service import log_action

router = APIRouter(prefix="/<resource>", tags=["<resource>"])


class ResourceCreate(BaseModel):
    title: str


@router.get("")
async def list_resources(user: dict = Depends(get_current_user)):
    client = get_supabase_authed_client(user["token"])
    result = client.table("...").select("*").execute()
    return {"data": result.data, "count": len(result.data)}
```

## React State Patterns

**Hook + Context pairing:**
- `useChatState` in `frontend/src/hooks/useChatState.ts` owns all chat state (threads, messages, branch selections, streaming flags, tool events). Returns a single object of state and handlers.
- `ChatContext` in `frontend/src/contexts/ChatContext.tsx` types itself as `ReturnType<typeof useChatState>` and exposes `useChatContext()` with a guard error.
- Pages consume context: `const { activeThreadId, messages, handleSendMessage } = useChatContext()` (see `frontend/src/pages/ChatPage.tsx`).

**Other shared hooks:**
- `useSidebar` — panel collapse state (`panelCollapsed`, `togglePanel`).
- `useDocumentRealtime(userId, onUpdate)` — Supabase Realtime subscription for document status updates.
- `useI18n` — Indonesian/English string lookup via `t(key)`.

**Data fetching:**
- All API calls go through `apiFetch` in `frontend/src/lib/api.ts`. It auto-attaches the Supabase JWT, sets JSON `Content-Type` (skipped for `FormData`), throws `Error(detail)` on non-2xx.
- Direct Supabase reads via `supabase.from('table').select(...)` are allowed for realtime/subscription-friendly tables (e.g. `messages` history load in `useChatState.handleSelectThread`). All writes go through the FastAPI backend.

## LLM / Structured Output Pattern

- `_llm_json(system_prompt, user_prompt)` in `backend/app/services/document_tool_service.py` is the canonical helper for structured LLM outputs. Calls OpenRouter with `response_format={"type": "json_object"}` and returns a parsed dict. Pydantic models (`GeneratedDocument`, `ComparisonResult`, `AnalysisResult`) validate the result.
- All LLM-touching functions are wrapped in `@traceable(name="...")` for LangSmith.
- System prompts are module-level `SYSTEM_PROMPT` constants (see `backend/app/routers/chat.py`).
- Confidence gating: results with `confidence_score >= 0.85` are auto-approved; below → `pending_review`.

## How to Add New Code

**New backend router:**
1. Create `backend/app/routers/<name>.py` with `router = APIRouter(prefix="/<name>", tags=["<name>"])`.
2. Define Pydantic request/response models at the top of the file.
3. Add endpoints that depend on `get_current_user` (or `require_admin`/`require_dpo`).
4. Use `get_supabase_authed_client(user["token"])` for user-scoped queries; `get_supabase_client()` only for service-role operations.
5. Call `log_action(...)` from `backend/app/services/audit_service.py` on every mutation.
6. Register in `backend/app/main.py`: import the module and call `app.include_router(<name>.router)`.
7. If new tables, create a numbered migration in `backend/migrations/NNN_<desc>.sql` (use `/create-migration`). Always include RLS policies.

**New backend service:**
1. Create `backend/app/services/<name>_service.py`.
2. Module-level singletons (`logger`, `settings`, `openrouter`) at the top.
3. Public functions are `snake_case`, private helpers prefixed with `_`.
4. Decorate LLM-facing functions with `@traceable(name="...")`.

**New frontend page:**
1. Create `frontend/src/pages/<Name>Page.tsx` exporting `export function <Name>Page()`.
2. Use `useI18n()` for all user-visible strings; add keys under `frontend/src/i18n/`.
3. Wire data through `apiFetch('/path')` from `@/lib/api`.
4. Add the route in `frontend/src/App.tsx`.
5. Reuse `AppLayout` (icon rail + collapsible sidebar + content) — do not roll a custom layout.
6. Run `cd frontend && npx tsc --noEmit && npm run lint` before commit.

**New shared hook:**
1. Create `frontend/src/hooks/use<Name>.ts`. Return a single object with state + handlers.
2. If state is shared across multiple components, pair with a `<Name>Context` in `frontend/src/contexts/`.

## Design System Rules (2026 Calibrated Restraint)

- **Tokens** live in `frontend/src/index.css` `:root` (and dark variant). Zinc-neutral base, purple accent (`--primary: oklch(0.48 0.18 280)`). Full spec at `docs/superpowers/specs/2026-04-14-design-2026-refresh.md`.
- **Glass (`backdrop-blur`):** allowed only on transient overlays — tooltips, popovers, mobile slide-over panels. NEVER on persistent panels (sidebars, input cards, app shell).
- **Buttons:** solid flat colors, no gradients. Use `bg-primary text-primary-foreground` and friends.
- **Gradients:** only on user chat bubbles in `frontend/src/components/chat/MessageView.tsx`. The "New Chat" button has a recently-added modern gradient as an explicit exception.
- **Tooltips:** base-ui tooltips use the `render` prop, not `asChild`. The shim in `frontend/src/components/ui/tooltip.tsx` translates `asChild` to `render`.
- **i18n:** all user-visible strings go through `useI18n()`. Indonesian default; English fallback via `I18nProvider`.
- **DocumentCreationPage caveat:** has BOTH mobile and desktop panels. Add new form sections to both.

## Inconsistencies and Gotchas

- No backend formatter (Black/Ruff) is configured. Style is consistent in practice but not enforced.
- Some pages issue `apiFetch` directly (`DocumentsPage.tsx`) while others go through a hook (`useChatState`). When extending, prefer the hook pattern for state that crosses components.
- `setState` calls inside `useEffect` exist in `DocumentsPage.tsx` (6 ESLint errors flagged Apr 23) — fix by deriving values where possible rather than introducing new derived-state effects.
- Two `024_*.sql` migrations exist (`024_knowledge_base_explorer.sql`, `024_rag_improvements.sql`). Both are applied. Do not renumber.
- `system_settings` is a single-row table with columns, NOT a key-value store. Always read via `get_system_settings()` from `backend/app/services/system_settings_service.py` (60s TTL cache).
- Supabase array containment filter: `.filter("col", "cs", "{value}")` not `.contains()`.
- Search params in PostgREST filters must sanitize commas and parentheses (see `list_clauses` in `backend/app/routers/clause_library.py`).
- `get_current_user` makes a `user_profiles` DB call on every request (checks `is_active`, auto-creates for new signups).
- Vercel deploys from `main`, not `master`. Always `git push origin master:main` after pushing to master.

---

*Convention analysis: 2026-04-25*
