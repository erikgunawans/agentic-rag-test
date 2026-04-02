import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks
from app.dependencies import get_current_user
from app.database import get_supabase_client
from app.config import get_settings
from app.services.ingestion_service import process_document
from app.routers.user_settings import get_or_create_settings

router = APIRouter(prefix="/documents", tags=["documents"])
settings = get_settings()

ALLOWED_MIME_TYPES = {"application/pdf", "text/plain", "text/markdown"}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB


@router.post("/upload", status_code=202)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
):
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{file.content_type}'. Use PDF, TXT, or Markdown.",
        )

    file_bytes = await file.read()

    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File exceeds 50 MB limit.")
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Empty file.")

    client = get_supabase_client()
    storage_path = f"{user['id']}/{uuid.uuid4()}-{file.filename}"

    # Upload raw file to Supabase Storage
    client.storage.from_(settings.storage_bucket).upload(
        path=storage_path,
        file=file_bytes,
        file_options={"content-type": file.content_type},
    )

    # Create document record
    doc = client.table("documents").insert({
        "user_id": user["id"],
        "filename": file.filename,
        "file_path": storage_path,
        "file_size": len(file_bytes),
        "mime_type": file.content_type,
        "status": "pending",
    }).execute().data[0]

    # Load user's embedding model preference before handing off to background task
    user_settings = get_or_create_settings(client, user["id"])

    # Kick off background ingestion
    background_tasks.add_task(
        process_document,
        doc_id=doc["id"],
        user_id=user["id"],
        file_path=storage_path,
        mime_type=file.content_type,
        embedding_model=user_settings["embedding_model"],
    )

    return {"id": doc["id"], "filename": doc["filename"], "status": "pending"}


@router.get("")
async def list_documents(user: dict = Depends(get_current_user)):
    client = get_supabase_client()
    result = (
        client.table("documents")
        .select("id, filename, file_size, mime_type, status, chunk_count, error_msg, created_at")
        .eq("user_id", user["id"])
        .order("created_at", desc=True)
        .execute()
    )
    return result.data


@router.delete("/{doc_id}", status_code=204)
async def delete_document(doc_id: str, user: dict = Depends(get_current_user)):
    client = get_supabase_client()

    doc = (
        client.table("documents")
        .select("file_path")
        .eq("id", doc_id)
        .eq("user_id", user["id"])
        .single()
        .execute()
    )
    if not doc.data:
        raise HTTPException(status_code=404, detail="Document not found")

    # Remove from Storage (best-effort)
    try:
        client.storage.from_(settings.storage_bucket).remove([doc.data["file_path"]])
    except Exception:
        pass

    # Delete DB record — chunks cascade automatically
    client.table("documents").delete().eq("id", doc_id).eq("user_id", user["id"]).execute()
