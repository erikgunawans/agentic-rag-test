import hashlib
import re
import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from app.dependencies import get_current_user
from app.database import get_supabase_client
from app.config import get_settings
from app.services.ingestion_service import process_document
from app.services.audit_service import log_action
from app.services.embedding_service import EmbeddingService
from app.services.hybrid_retrieval_service import HybridRetrievalService
from app.services.system_settings_service import get_system_settings

router = APIRouter(prefix="/documents", tags=["documents"])
settings = get_settings()
embedding_service = EmbeddingService()
hybrid_service = HybridRetrievalService()

ALLOWED_MIME_TYPES = {
    "application/pdf",
    "text/plain",
    "text/markdown",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/csv",
    "text/html",
    "application/json",
}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB


@router.post("/upload", status_code=202)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    folder_id: str | None = Form(default=None),
    user: dict = Depends(get_current_user),
):
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{file.content_type}'. Use PDF, TXT, Markdown, DOCX, CSV, HTML, or JSON.",
        )

    file_bytes = await file.read()

    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File exceeds 50 MB limit.")
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Empty file.")

    content_hash = hashlib.sha256(file_bytes).hexdigest()

    client = get_supabase_client()

    # Check for existing document with same content hash for this user
    existing = (
        client.table("documents")
        .select("id, filename, status, file_path")
        .eq("user_id", user["id"])
        .eq("content_hash", content_hash)
        .execute()
    ).data

    for doc in existing:
        if doc["status"] == "completed":
            # Already processed — skip storage upload, DB insert, and background task
            return JSONResponse(
                status_code=200,
                content={"id": doc["id"], "filename": doc["filename"], "status": "completed", "duplicate": True},
            )
        if doc["status"] in ("pending", "processing"):
            raise HTTPException(status_code=409, detail="This document is already being processed.")
        if doc["status"] == "failed":
            # Clean up failed record so we can retry with fresh state
            try:
                client.storage.from_(settings.storage_bucket).remove([doc["file_path"]])
            except Exception:
                pass
            client.table("documents").delete().eq("id", doc["id"]).eq("user_id", user["id"]).execute()

    safe_filename = re.sub(r"[^a-zA-Z0-9._-]", "_", file.filename or "upload")
    storage_path = f"{user['id']}/{uuid.uuid4()}-{safe_filename}"

    # Upload raw file to Supabase Storage
    client.storage.from_(settings.storage_bucket).upload(
        path=storage_path,
        file=file_bytes,
        file_options={"content-type": file.content_type},
    )

    # Create document record
    insert_data = {
        "user_id": user["id"],
        "filename": file.filename,
        "file_path": storage_path,
        "file_size": len(file_bytes),
        "mime_type": file.content_type,
        "status": "pending",
        "content_hash": content_hash,
    }
    if folder_id:
        insert_data["folder_id"] = folder_id

    doc = client.table("documents").insert(insert_data).execute().data[0]

    # Load system-level model config
    sys_settings = get_system_settings()

    # Kick off background ingestion
    background_tasks.add_task(
        process_document,
        doc_id=doc["id"],
        user_id=user["id"],
        file_path=storage_path,
        mime_type=file.content_type,
        embedding_model=sys_settings["embedding_model"],
        llm_model=sys_settings["llm_model"],
    )

    log_action(
        user_id=user["id"],
        user_email=user["email"],
        action="upload",
        resource_type="document",
        resource_id=str(doc["id"]),
        details={"filename": file.filename, "mime_type": file.content_type, "file_size": len(file_bytes)},
    )

    return {"id": doc["id"], "filename": doc["filename"], "status": "pending", "duplicate": False}


@router.get("")
async def list_documents(
    folder_id: str | None = Query(default=None),
    user: dict = Depends(get_current_user),
):
    client = get_supabase_client()
    query = (
        client.table("documents")
        .select("id, filename, file_size, mime_type, status, chunk_count, error_msg, content_hash, metadata, folder_id, created_at")
        .eq("user_id", user["id"])
    )
    if folder_id == "root":
        query = query.is_("folder_id", "null")
    elif folder_id:
        query = query.eq("folder_id", folder_id)
    result = query.order("created_at", desc=True).execute()
    return result.data


@router.get("/{doc_id}/metadata")
async def get_document_metadata(doc_id: str, user: dict = Depends(get_current_user)):
    client = get_supabase_client()
    result = (
        client.table("documents")
        .select("metadata")
        .eq("id", doc_id)
        .eq("user_id", user["id"])
        .limit(1)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Document not found")
    return result.data[0]["metadata"]


@router.delete("/{doc_id}", status_code=204)
async def delete_document(doc_id: str, user: dict = Depends(get_current_user)):
    client = get_supabase_client()

    doc = (
        client.table("documents")
        .select("file_path")
        .eq("id", doc_id)
        .eq("user_id", user["id"])
        .limit(1)
        .execute()
    )
    if not doc.data:
        raise HTTPException(status_code=404, detail="Document not found")

    # Remove from Storage (best-effort)
    try:
        client.storage.from_(settings.storage_bucket).remove([doc.data[0]["file_path"]])
    except Exception:
        pass

    # Delete DB record — chunks cascade automatically
    client.table("documents").delete().eq("id", doc_id).eq("user_id", user["id"]).execute()

    log_action(
        user_id=user["id"],
        user_email=user["email"],
        action="delete",
        resource_type="document",
        resource_id=doc_id,
    )


class MoveDocumentRequest(BaseModel):
    folder_id: str | None = None  # null = move to root


@router.patch("/{doc_id}/move")
async def move_document(
    doc_id: str,
    body: MoveDocumentRequest,
    user: dict = Depends(get_current_user),
):
    client = get_supabase_client()
    result = (
        client.table("documents")
        .update({"folder_id": body.folder_id})
        .eq("id", doc_id)
        .eq("user_id", user["id"])
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Document not found")
    return result.data[0]


class SearchRequest(BaseModel):
    query: str
    top_k: int = 5
    mode: str = "hybrid"  # "hybrid", "vector", "fulltext"


@router.post("/search")
async def search_documents(
    body: SearchRequest,
    user: dict = Depends(get_current_user),
):
    sys_settings = get_system_settings()

    if body.mode == "vector":
        results = await embedding_service.retrieve_chunks_with_metadata(
            query=body.query,
            user_id=user["id"],
            top_k=body.top_k,
            threshold=settings.rag_similarity_threshold,
            model=user_settings["embedding_model"],
        )
    elif body.mode == "fulltext":
        try:
            result = get_supabase_client().rpc(
                "match_document_chunks_fulltext",
                {
                    "search_query": body.query,
                    "match_user_id": user["id"],
                    "match_count": body.top_k,
                    "filter_category": None,
                },
            ).execute()
            results = result.data or []
        except Exception:
            results = []
    else:
        results = await hybrid_service.retrieve(
            query=body.query,
            user_id=user["id"],
            top_k=body.top_k,
            threshold=settings.rag_similarity_threshold,
            embedding_model=sys_settings["embedding_model"],
            llm_model=sys_settings["llm_model"],
        )

    return {"results": results, "count": len(results), "mode": body.mode}
