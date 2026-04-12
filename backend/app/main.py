from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_settings
from app.routers import threads, chat, documents, document_tools, admin_settings, user_preferences
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


@app.get("/health")
async def health():
    return {"status": "ok"}
