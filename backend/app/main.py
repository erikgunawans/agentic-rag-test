import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_settings
from app.routers import threads, chat, documents, document_tools, admin_settings, user_preferences, audit_trail, obligations, clause_library, document_templates, approvals, user_management, regulatory, notifications, dashboard, integrations, google_export, bjr, compliance_snapshots, pdp, folders, skills, code_execution
from app.routers import settings as public_settings_router  # Phase 12 / CTX-03 — public, no auth
from app.middleware.skills_upload_size import SkillsUploadSizeMiddleware
from app.services.tracing_service import configure_tracing
from app.services.redaction_service import get_redaction_service
from app.services.mcp_client_manager import get_mcp_client_manager
from app.database import get_supabase_client

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_tracing()
    # PERF-01 / D-15: eager warm-up so the first chat request doesn't pay
    # the Presidio + spaCy model load. Wrapped in try/except matching the
    # existing supabase-recovery pattern — if the warm-up trips on Railway
    # (e.g. a model-download blip), we log a warning and let boot continue
    # rather than block the whole API. I15: use logger.warning, not print.
    try:
        get_redaction_service()
    except Exception:
        logger.warning(
            "get_redaction_service() warm-up failed", exc_info=True
        )
    # Phase 15 (MCP-01..06 / D-P15-01): start MCP client manager if configured.
    # Non-critical: failure logs a warning and boot continues (MCP is additive).
    # Gate: only runs when TOOL_REGISTRY_ENABLED=true AND MCP_SERVERS is non-empty.
    if settings.tool_registry_enabled and settings.mcp_servers.strip():
        try:
            await get_mcp_client_manager().startup()
        except Exception:
            logger.warning(
                "MCPClientManager startup failed — MCP tools unavailable", exc_info=True
            )
    # Recover any docs stalled in 'processing' from a previous crash
    try:
        get_supabase_client().table("documents").update(
            {"status": "pending"}
        ).eq("status", "processing").execute()
    except Exception:
        pass
    yield
    # Phase 15 (D-P15-02): clean up MCP connections on shutdown.
    if settings.tool_registry_enabled and settings.mcp_servers.strip():
        try:
            await get_mcp_client_manager().shutdown()
        except Exception:
            logger.warning("MCPClientManager shutdown failed", exc_info=True)


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

# Skills upload size cap (50 MB) — fires before multipart body parsing (cycle-2 H6 fix)
app.add_middleware(SkillsUploadSizeMiddleware)

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
app.include_router(folders.router)
app.include_router(skills.router)
app.include_router(code_execution.router)
app.include_router(public_settings_router.router)  # Phase 12 / CTX-03

# Phase 14 / BRIDGE-02, D-P14-05: bridge router mounted only when BOTH flags are active.
# Lazy import inside the if-block ensures the bridge module is NEVER imported when
# flags are off, preserving the TOOL-05 byte-identical fallback invariant.
if settings.sandbox_enabled and settings.tool_registry_enabled:
    from app.routers import bridge as bridge_router_module
    app.include_router(bridge_router_module.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
