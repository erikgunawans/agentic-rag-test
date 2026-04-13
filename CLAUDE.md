# CLAUDE.md

PJAA CLM (Contract Lifecycle Management) platform. Indonesian legal AI with chat, document tools, clause library, approval workflows, regulatory intelligence, and executive dashboard. RBAC with admin UI.

## Stack
- Frontend: React + Vite + Tailwind + shadcn/ui + base-ui (tooltips)
- Backend: Python + FastAPI (async, `venv`)
- Database: Supabase (Postgres, pgvector, Auth, Storage, Realtime)
- LLM: OpenRouter (chat + document tools), OpenAI (embeddings only)
- Observability: LangSmith

## Quick Start

```bash
# Backend
cd backend && python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend && npm install && npm run dev
```

## Architecture

### Backend (18 routers in `backend/app/routers/`)
- **Core**: `chat.py` (SSE streaming + tool-calling loop), `threads.py`, `documents.py`
- **Document tools**: `document_tools.py` (create/compare/compliance/analyze with LLM)
- **Phase 1**: `clause_library.py`, `document_templates.py`, `approvals.py`, `obligations.py`, `audit_trail.py`, `user_management.py`
- **Phase 2**: `regulatory.py`, `notifications.py`, `dashboard.py`, `integrations.py` (Dokmee), `google_export.py`
- **Settings**: `admin_settings.py` (system-wide), `user_preferences.py` (per-user)

### Frontend (18 pages in `frontend/src/pages/`)
- Layout: `AppLayout` with `IconRail` (60px) + collapsible sidebar (340px) + content
- State: `useChatState` hook + `ChatContext`, `useSidebar` for panel collapse
- i18n: Indonesian (default) + English via `I18nProvider`

### Key patterns
- **Auth**: `get_current_user` dependency returns `{id, email, token, role}`, checks `user_profiles.is_active`
- **Admin**: `require_admin` dependency, checks `role == "super_admin"`
- **DB clients**: `get_supabase_authed_client(token)` for RLS-scoped, `get_supabase_client()` for service-role
- **system_settings**: Single-row table (`id=1`), cached via `get_system_settings()` with 60s TTL. Never query as key-value.
- **Audit**: `log_action(user_id, user_email, action, resource_type, resource_id)` on all mutations
- **Form duplication**: DocumentCreationPage has BOTH mobile and desktop panels. Add new form sections to both.

## Rules
- No LangChain, no LangGraph. Raw SDK calls only.
- Use Pydantic for structured LLM outputs (`json_object` response format)
- All tables need Row-Level Security. Users only see their own data.
- Global/shared data uses `is_global = true` pattern (clauses, templates)
- Stream chat responses via SSE
- Ingestion is manual file upload only

## Admin / RBAC
- test@test.com is `super_admin` (set via `raw_app_meta_data.role`)
- Promote users: `python -m scripts.set_admin_role <email>`
- Admin pages: `/admin/settings`, `/admin/users`, `/admin/audit`, `/admin/reviews`
- RLS admin pattern: `(auth.jwt() -> 'app_metadata' ->> 'role') = 'super_admin'`

## Deployment

```bash
# Frontend (Vercel, auto-deploys from push)
cd frontend && npx vercel --prod

# Backend (Railway)
cd backend && railway up
```

- **Frontend**: https://frontend-one-rho-88.vercel.app
- **Backend**: https://api-production-cde1.up.railway.app
- **Supabase project**: `qedhulpfezucnfadlfiz`

## Planning
- Save plans to `.agent/plans/` folder
- Naming: `{sequence}.{plan-name}.md`
- Complexity indicators: ✅ Simple, ⚠️ Medium, 🔴 Complex

## Testing

User 1 (admin):
- **Email**: `test@test.com`
- **Password**: `!*-3-3?3uZ?b$v&`

User 2:
- **Email**: `test-2@test.com`
- **Password**: `fK4$Wd?HGKmb#A2`

- **Frontend**: `http://localhost:5173`
- **Backend**: `http://localhost:8000`

## Code Quality

```bash
# Frontend lint
cd frontend && npm run lint

# Frontend type check
cd frontend && npx tsc --noEmit

# Backend import check (no pytest suite yet)
cd backend && source venv/bin/activate && python -c "from app.main import app; print('OK')"
```

## Gotchas
- `system_settings` is a single-row table with columns, NOT a key-value store. Use `get_system_settings()` from `system_settings_service.py`.
- base-ui tooltips use `render` prop, not `asChild`. The shim in `tooltip.tsx` translates `asChild` to `render`.
- Python 3.14 shows Pydantic v1 warning from langsmith. Non-blocking.
- Supabase array containment filter: `.filter("col", "cs", "{value}")` not `.contains()`
- Search params in PostgREST filters must sanitize commas and parentheses.
- `get_current_user` makes a `user_profiles` DB call on every request (checks `is_active`, auto-creates for new signups).

## Progress

Check PROGRESS.md for current status. Phase 1 (7/7) and Phase 2 (5/5) complete.
