import logging
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from app.dependencies import get_current_user
from app.database import get_supabase_authed_client, get_supabase_client
from app.services.audit_service import log_action
from app.services.document_tool_service import check_compliance, _extract_text

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/compliance/snapshots", tags=["compliance-snapshots"])

ALLOWED_MIME_TYPES = {
    "application/pdf", "text/plain", "text/markdown",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/csv", "text/html", "application/json",
}


@router.post("", status_code=201)
async def create_snapshot(
    framework: str = Form(...),
    scopes: str = Form("legal,risks,missing,regulatory"),
    trigger_type: str = Form("manual"),
    document_id: str | None = Form(None),
    regulatory_context: str | None = Form(None),
    context: str | None = Form(None),
    document: UploadFile | None = File(None),
    user: dict = Depends(get_current_user),
):
    """Create a compliance snapshot — runs compliance check and persists the result."""
    # Get document text from either file upload or existing document
    doc_text = ""
    if document and document.size and document.size > 0:
        file_bytes = await document.read()
        if document.content_type not in ALLOWED_MIME_TYPES:
            raise HTTPException(status_code=400, detail=f"Unsupported file type: {document.content_type}")
        doc_text = _extract_text(file_bytes, document.content_type)
    elif document_id:
        svc_client = get_supabase_client()
        doc_row = svc_client.table("documents").select("filename, metadata").eq("id", document_id).execute()
        if not doc_row.data:
            raise HTTPException(status_code=404, detail="Document not found")
        # Use document chunks as text source
        chunks = svc_client.table("document_chunks").select("content").eq("document_id", document_id).order("chunk_index").execute()
        doc_text = "\n\n".join(c["content"] for c in chunks.data) if chunks.data else ""
    else:
        raise HTTPException(status_code=400, detail="Either document file or document_id is required")

    if not doc_text.strip():
        raise HTTPException(status_code=400, detail="Document has no extractable text")

    # Run compliance check
    scope_list = [s.strip() for s in scopes.split(",") if s.strip()]
    result = await check_compliance(doc_text, framework, scope_list, context)
    result_data = result.model_dump()

    # Persist snapshot
    client = get_supabase_authed_client(user["token"])
    row = client.table("compliance_snapshots").insert({
        "user_id": user["id"],
        "document_id": document_id,
        "trigger_type": trigger_type,
        "framework": framework,
        "scopes": scope_list,
        "overall_status": result.overall_status,
        "result": result_data,
        "confidence_score": result.confidence_score,
        "regulatory_context": regulatory_context,
    }).execute()

    log_action(
        user_id=user["id"], user_email=user["email"],
        action="create_snapshot", resource_type="compliance_snapshot",
        resource_id=str(row.data[0]["id"]),
        details={"framework": framework, "trigger_type": trigger_type, "status": result.overall_status},
    )
    return row.data[0]


@router.get("")
async def list_snapshots(
    framework: str | None = Query(None),
    document_id: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: dict = Depends(get_current_user),
):
    client = get_supabase_authed_client(user["token"])
    query = client.table("compliance_snapshots").select("*")
    if framework:
        query = query.eq("framework", framework)
    if document_id:
        query = query.eq("document_id", document_id)
    if date_from:
        query = query.gte("snapshot_date", date_from)
    if date_to:
        query = query.lte("snapshot_date", date_to)
    query = query.order("snapshot_date", desc=True).range(offset, offset + limit - 1)
    result = query.execute()
    return {"data": result.data}


@router.get("/diff")
async def diff_snapshots(
    a: str = Query(..., description="First snapshot ID"),
    b: str = Query(..., description="Second snapshot ID"),
    user: dict = Depends(get_current_user),
):
    """Compare two compliance snapshots and return the differences."""
    client = get_supabase_authed_client(user["token"])

    snap_a = client.table("compliance_snapshots").select("*").eq("id", a).execute()
    snap_b = client.table("compliance_snapshots").select("*").eq("id", b).execute()

    if not snap_a.data or not snap_b.data:
        raise HTTPException(status_code=404, detail="One or both snapshots not found")

    sa, sb = snap_a.data[0], snap_b.data[0]
    result_a = sa.get("result", {})
    result_b = sb.get("result", {})

    # Compare findings
    findings_a = {f"{f.get('category','')}__{f.get('description','')}" for f in result_a.get("findings", [])}
    findings_b = {f"{f.get('category','')}__{f.get('description','')}" for f in result_b.get("findings", [])}

    added_keys = findings_b - findings_a
    removed_keys = findings_a - findings_b

    added_findings = [f for f in result_b.get("findings", []) if f"{f.get('category','')}__{f.get('description','')}" in added_keys]
    removed_findings = [f for f in result_a.get("findings", []) if f"{f.get('category','')}__{f.get('description','')}" in removed_keys]

    # Compare missing provisions
    missing_a = set(result_a.get("missing_provisions", []))
    missing_b = set(result_b.get("missing_provisions", []))

    return {
        "snapshot_a": {"id": sa["id"], "date": sa["snapshot_date"], "status": sa["overall_status"], "framework": sa["framework"]},
        "snapshot_b": {"id": sb["id"], "date": sb["snapshot_date"], "status": sb["overall_status"], "framework": sb["framework"]},
        "status_change": sa["overall_status"] != sb["overall_status"],
        "status_a": sa["overall_status"],
        "status_b": sb["overall_status"],
        "added_findings": added_findings,
        "removed_findings": removed_findings,
        "new_missing_provisions": list(missing_b - missing_a),
        "resolved_missing_provisions": list(missing_a - missing_b),
    }


@router.get("/{snapshot_id}")
async def get_snapshot(snapshot_id: str, user: dict = Depends(get_current_user)):
    client = get_supabase_authed_client(user["token"])
    result = client.table("compliance_snapshots").select("*").eq("id", snapshot_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    return result.data[0]
