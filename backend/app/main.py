from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_settings
from app.routers import threads, chat, documents, document_tools, admin_settings, user_preferences, audit_trail, obligations, clause_library, document_templates, approvals, user_management, regulatory, notifications, dashboard, integrations, google_export, bjr, compliance_snapshots, pdp
from app.services.langsmith_service import configure_langsmith
from app.database import get_supabase_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_langsmith()
    # Recover any docs stalled in 'processing' from a previous crash
    try:
        get_supabase_client().table("documents").update(
            {"status": "pending"}
        ).eq("status", "processing").execute()
    except Exception:
        pass
    yield


app = FastAPI(title="RAG Masterclass API", lifespan=lifespan)

settings = get_settings()
origins = [o.strip() for o in settings.frontend_url.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(threads.router)
app.include_router(chat.router)
app.include_router(documents.router)
app.include_router(document_tools.router)
app.include_router(admin_settings.router)
app.include_router(user_preferences.router)
app.include_router(audit_trail.router)
app.include_router(obligations.router)
app.include_router(clause_library.router)
app.include_router(document_templates.router)
app.include_router(approvals.router)
app.include_router(user_management.router)
app.include_router(regulatory.router)
app.include_router(notifications.router)
app.include_router(dashboard.router)
app.include_router(integrations.router)
app.include_router(google_export.router)
app.include_router(bjr.router)
app.include_router(compliance_snapshots.router)
app.include_router(pdp.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
