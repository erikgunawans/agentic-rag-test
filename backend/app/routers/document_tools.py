import json
import logging
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from pydantic import BaseModel, Field
from app.dependencies import get_current_user
from app.database import get_supabase_authed_client, get_supabase_client
from app.services.document_tool_service import (
    create_document,
    compare_documents,
    check_compliance,
    analyze_contract,
    _extract_text,
)
from app.services.audit_service import log_action
from app.services.system_settings_service import get_system_settings
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/document-tools", tags=["document-tools"])


def _save_result(user: dict, tool_type: str, title: str, input_params: dict, result: dict) -> tuple[str, str]:
    """Save a document tool result with confidence gating. Returns (id, review_status)."""
    confidence_score = result.get("confidence_score", 0.0)
    threshold = get_system_settings().get("confidence_threshold", 0.85)
    review_status = "auto_approved" if confidence_score >= threshold else "pending_review"

    client = get_supabase_authed_client(user["token"])
    row = client.table("document_tool_results").insert({
        "user_id": user["id"],
        "tool_type": tool_type,
        "title": title,
        "input_params": input_params,
        "result": result,
        "confidence_score": confidence_score,
        "review_status": review_status,
    }).execute()
    return row.data[0]["id"], review_status

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


def _validate_file(file_bytes: bytes, content_type: str | None) -> None:
    if content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{content_type}'. Use PDF, TXT, Markdown, DOCX, CSV, HTML, or JSON.",
        )
    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File exceeds 50 MB limit.")
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Empty file.")


@router.get("/history")
async def get_history(
    tool_type: str | None = Query(None),
    limit: int = Query(10, ge=1, le=50),
    user: dict = Depends(get_current_user),
):
    """Get recent document tool results for the current user."""
    client = get_supabase_authed_client(user["token"])
    query = client.table("document_tool_results").select(
        "id, tool_type, title, input_params, confidence_score, review_status, created_at"
    ).eq("user_id", user["id"]).order("created_at", desc=True).limit(limit)
    if tool_type:
        query = query.eq("tool_type", tool_type)
    return query.execute().data


@router.get("/history/{result_id}")
async def get_result(result_id: str, user: dict = Depends(get_current_user)):
    """Get a specific document tool result. Admins can view any result."""
    is_admin = user.get("role") == "super_admin"
    if is_admin:
        client = get_supabase_client()
        rows = client.table("document_tool_results").select("*").eq("id", result_id).execute().data
    else:
        client = get_supabase_authed_client(user["token"])
        rows = client.table("document_tool_results").select("*").eq(
            "id", result_id
        ).eq("user_id", user["id"]).execute().data
    if not rows:
        raise HTTPException(status_code=404, detail="Result not found")
    return rows[0]


@router.post("/create")
async def create_document_endpoint(
    doc_type: str = Form(...),
    fields: str = Form(...),  # JSON string of form fields
    output_language: str = Form("both"),
    reference_file: UploadFile | None = File(None),
    template_file: UploadFile | None = File(None),
    user: dict = Depends(get_current_user),
):
    try:
        parsed_fields = json.loads(fields)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid fields JSON.")

    reference_text = None
    if reference_file:
        ref_bytes = await reference_file.read()
        _validate_file(ref_bytes, reference_file.content_type)
        reference_text = _extract_text(ref_bytes, reference_file.content_type)

    template_text = None
    if template_file:
        tpl_bytes = await template_file.read()
        _validate_file(tpl_bytes, template_file.content_type)
        template_text = _extract_text(tpl_bytes, template_file.content_type)

    result = await create_document(
        doc_type=doc_type,
        fields=parsed_fields,
        output_language=output_language,
        reference_text=reference_text,
        template_text=template_text,
    )
    data = result.model_dump()
    result_id, review_status = _save_result(user, "create", data["title"], {"doc_type": doc_type, "output_language": output_language}, data)
    log_action(user_id=user["id"], user_email=user["email"], action="create", resource_type="document_tool_result", resource_id=result_id, details={"tool_type": "create"})
    data["review_status"] = review_status
    return data


@router.post("/compare")
async def compare_documents_endpoint(
    doc_a: UploadFile = File(...),
    doc_b: UploadFile = File(...),
    focus: str = Form("full"),
    context: str = Form(""),
    user: dict = Depends(get_current_user),
):
    a_bytes = await doc_a.read()
    _validate_file(a_bytes, doc_a.content_type)
    b_bytes = await doc_b.read()
    _validate_file(b_bytes, doc_b.content_type)

    doc_a_text = _extract_text(a_bytes, doc_a.content_type)
    doc_b_text = _extract_text(b_bytes, doc_b.content_type)

    result = await compare_documents(
        doc_a_text=doc_a_text,
        doc_b_text=doc_b_text,
        focus=focus,
        context=context or None,
    )
    data = result.model_dump()
    title = f"{doc_a.filename} vs {doc_b.filename}"
    result_id, review_status = _save_result(user, "compare", title, {"focus": focus}, data)
    log_action(user_id=user["id"], user_email=user["email"], action="compare", resource_type="document_tool_result", resource_id=result_id, details={"tool_type": "compare"})
    data["review_status"] = review_status
    return data


@router.post("/compliance")
async def check_compliance_endpoint(
    document: UploadFile = File(...),
    framework: str = Form("ojk"),
    scopes: str = Form("legal"),  # comma-separated
    context: str = Form(""),
    user: dict = Depends(get_current_user),
):
    doc_bytes = await document.read()
    _validate_file(doc_bytes, document.content_type)
    doc_text = _extract_text(doc_bytes, document.content_type)

    scope_list = [s.strip() for s in scopes.split(",") if s.strip()]

    result = await check_compliance(
        doc_text=doc_text,
        framework=framework,
        scopes=scope_list,
        context=context or None,
    )
    data = result.model_dump()
    result_id, review_status = _save_result(user, "compliance", document.filename or "Compliance Check", {"framework": framework, "scopes": scope_list}, data)
    log_action(user_id=user["id"], user_email=user["email"], action="compliance", resource_type="document_tool_result", resource_id=result_id, details={"tool_type": "compliance", "framework": framework})
    data["review_status"] = review_status
    return data


@router.post("/analyze")
async def analyze_contract_endpoint(
    document: UploadFile = File(...),
    analysis_types: str = Form("risk"),  # comma-separated
    law: str = Form("indonesia"),
    depth: str = Form("standard"),
    context: str = Form(""),
    user: dict = Depends(get_current_user),
):
    doc_bytes = await document.read()
    _validate_file(doc_bytes, document.content_type)
    doc_text = _extract_text(doc_bytes, document.content_type)

    type_list = [t.strip() for t in analysis_types.split(",") if t.strip()]

    result = await analyze_contract(
        doc_text=doc_text,
        analysis_types=type_list,
        law=law,
        depth=depth,
        context=context or None,
    )
    data = result.model_dump()
    result_id, review_status = _save_result(user, "analyze", document.filename or "Contract Analysis", {"analysis_types": type_list, "law": law, "depth": depth}, data)
    log_action(user_id=user["id"], user_email=user["email"], action="analyze", resource_type="document_tool_result", resource_id=result_id, details={"tool_type": "analyze", "law": law})
    data["review_status"] = review_status
    return data


@router.get("/review-queue")
async def get_review_queue(
    status: str = Query("pending_review"),
    tool_type: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: dict = Depends(get_current_user),
):
    """Get document tool results by review status. Admin sees all; users see own."""
    is_admin = user.get("role") == "super_admin"
    client = get_supabase_client() if is_admin else get_supabase_authed_client(user["token"])

    query = client.table("document_tool_results").select(
        "id, user_id, tool_type, title, confidence_score, review_status, review_notes, reviewed_by, reviewed_at, created_at"
    ).eq("review_status", status).order("created_at", desc=True)

    if not is_admin:
        query = query.eq("user_id", user["id"])
    if tool_type:
        query = query.eq("tool_type", tool_type)

    query = query.range(offset, offset + limit - 1)
    result = query.execute()
    return {"data": result.data, "count": len(result.data)}


class ReviewAction(BaseModel):
    action: str  # "approve" or "reject"
    notes: str = Field(default="", max_length=2000)


@router.patch("/review/{result_id}")
async def review_result(
    result_id: str,
    body: ReviewAction,
    user: dict = Depends(get_current_user),
):
    """Approve or reject a document tool result. Admin only."""
    if user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    # Guard: only pending_review items can be reviewed
    client = get_supabase_client()
    existing = client.table("document_tool_results").select("review_status").eq("id", result_id).execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail="Result not found")
    if existing.data[0]["review_status"] != "pending_review":
        raise HTTPException(status_code=409, detail=f"Result is already '{existing.data[0]['review_status']}' and cannot be re-reviewed")

    review_status = "approved" if body.action == "approve" else "rejected"
    result = client.table("document_tool_results").update({
        "review_status": review_status,
        "reviewed_by": user["id"],
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
        "review_notes": body.notes,
    }).eq("id", result_id).execute()

    if not result.data:
        raise HTTPException(status_code=404, detail="Result not found")

    log_action(
        user_id=user["id"],
        user_email=user["email"],
        action=f"review_{action}",
        resource_type="document_tool_result",
        resource_id=result_id,
        details={"review_status": review_status, "notes": body.notes},
    )
    return result.data[0]
