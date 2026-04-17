import logging
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from app.dependencies import get_current_user
from app.database import get_supabase_authed_client, get_supabase_client
from app.services.audit_service import log_action
from app.services.pdp_service import scan_for_personal_data, calculate_readiness_score
from app.services.document_tool_service import _extract_text
from app.models.pdp import (
    InventoryCreate, InventoryUpdate,
    ComplianceStatusUpdate,
    IncidentCreate, IncidentUpdate,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pdp", tags=["pdp"])


# ── Data Inventory ────────────────────────────────────────────


@router.post("/inventory", status_code=201)
async def create_inventory_item(body: InventoryCreate, user: dict = Depends(get_current_user)):
    client = get_supabase_authed_client(user["token"])
    row = client.table("data_inventory").insert({
        "user_id": user["id"],
        "processing_activity": body.processing_activity,
        "data_categories": body.data_categories,
        "lawful_basis": body.lawful_basis,
        "purposes": body.purposes,
        "data_subjects": body.data_subjects,
        "processors": body.processors,
        "retention_period": body.retention_period,
        "security_measures": body.security_measures,
        "dpia_required": body.dpia_required,
        "dpia_status": body.dpia_status,
    }).execute()

    log_action(
        user_id=user["id"], user_email=user["email"],
        action="create_inventory", resource_type="data_inventory",
        resource_id=str(row.data[0]["id"]),
    )
    return row.data[0]


@router.get("/inventory")
async def list_inventory(
    status: str | None = Query(None),
    lawful_basis: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    user: dict = Depends(get_current_user),
):
    client = get_supabase_authed_client(user["token"])
    query = client.table("data_inventory").select("*")
    if status:
        query = query.eq("status", status)
    else:
        query = query.eq("status", "active")
    if lawful_basis:
        query = query.eq("lawful_basis", lawful_basis)
    query = query.order("created_at", desc=True).limit(limit)
    result = query.execute()
    return {"data": result.data}


@router.get("/inventory/{item_id}")
async def get_inventory_item(item_id: str, user: dict = Depends(get_current_user)):
    client = get_supabase_authed_client(user["token"])
    result = client.table("data_inventory").select("*").eq("id", item_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    return result.data[0]


@router.patch("/inventory/{item_id}")
async def update_inventory_item(item_id: str, body: InventoryUpdate, user: dict = Depends(get_current_user)):
    client = get_supabase_authed_client(user["token"])
    update_data = {k: v for k, v in body.model_dump().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")
    result = client.table("data_inventory").update(update_data).eq("id", item_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Inventory item not found")

    log_action(
        user_id=user["id"], user_email=user["email"],
        action="update_inventory", resource_type="data_inventory",
        resource_id=item_id,
    )
    return result.data[0]


@router.delete("/inventory/{item_id}")
async def archive_inventory_item(item_id: str, user: dict = Depends(get_current_user)):
    client = get_supabase_authed_client(user["token"])
    result = client.table("data_inventory").update({"status": "archived"}).eq("id", item_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Inventory item not found")

    log_action(
        user_id=user["id"], user_email=user["email"],
        action="archive_inventory", resource_type="data_inventory",
        resource_id=item_id,
    )
    return {"status": "archived"}


# ── PDP Compliance Status ─────────────────────────────────────


@router.get("/compliance-status")
async def get_compliance_status(user: dict = Depends(get_current_user)):
    client = get_supabase_authed_client(user["token"])
    result = client.table("pdp_compliance_status").select("*").eq("id", 1).execute()
    return result.data[0] if result.data else {}


@router.patch("/compliance-status")
async def update_compliance_status(body: ComplianceStatusUpdate, user: dict = Depends(get_current_user)):
    if user["role"] not in ("super_admin", "dpo"):
        raise HTTPException(status_code=403, detail="Only admins and DPO can update compliance status")

    client = get_supabase_client()
    update_data = {k: v for k, v in body.model_dump().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")

    if body.dpo_appointed is True and "dpo_appointed_at" not in update_data:
        update_data["dpo_appointed_at"] = "now()"

    result = client.table("pdp_compliance_status").update(update_data).eq("id", 1).execute()

    log_action(
        user_id=user["id"], user_email=user["email"],
        action="update_pdp_status", resource_type="pdp_compliance_status",
        details=update_data,
    )
    return result.data[0] if result.data else {"status": "updated"}


@router.get("/readiness")
async def get_readiness(user: dict = Depends(get_current_user)):
    score = calculate_readiness_score()

    # Update stored score
    client = get_supabase_client()
    client.table("pdp_compliance_status").update({
        "readiness_score": score,
        "last_assessment_at": "now()",
    }).eq("id", 1).execute()

    # Get inventory stats
    inv = client.table("data_inventory").select("id, dpia_required, dpia_status", count="exact").eq("status", "active").execute()
    inv_count = inv.count if inv.count is not None else len(inv.data)
    dpia_required = sum(1 for i in inv.data if i.get("dpia_required"))
    dpia_completed = sum(1 for i in inv.data if i.get("dpia_required") and i.get("dpia_status") == "completed")

    # Get incident count
    incidents = client.table("data_breach_incidents").select("id", count="exact").execute()
    incident_count = incidents.count if incidents.count is not None else len(incidents.data)

    status = client.table("pdp_compliance_status").select("*").eq("id", 1).execute()

    return {
        "readiness_score": score,
        "status": status.data[0] if status.data else {},
        "inventory_count": inv_count,
        "dpia_required": dpia_required,
        "dpia_completed": dpia_completed,
        "incident_count": incident_count,
    }


# ── Data Breach Incidents ─────────────────────────────────────


@router.post("/incidents", status_code=201)
async def create_incident(body: IncidentCreate, user: dict = Depends(get_current_user)):
    client = get_supabase_authed_client(user["token"])
    row = client.table("data_breach_incidents").insert({
        "user_id": user["id"],
        "incident_date": body.incident_date,
        "incident_type": body.incident_type,
        "description": body.description,
        "affected_data_categories": body.affected_data_categories,
        "estimated_records": body.estimated_records,
    }).execute()

    log_action(
        user_id=user["id"], user_email=user["email"],
        action="report_incident", resource_type="data_breach_incident",
        resource_id=str(row.data[0]["id"]),
        details={"incident_type": body.incident_type},
    )
    return row.data[0]


@router.get("/incidents")
async def list_incidents(
    response_status: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    user: dict = Depends(get_current_user),
):
    client = get_supabase_authed_client(user["token"])
    query = client.table("data_breach_incidents").select("*")
    if response_status:
        query = query.eq("response_status", response_status)
    query = query.order("incident_date", desc=True).limit(limit)
    result = query.execute()
    return {"data": result.data}


@router.patch("/incidents/{incident_id}")
async def update_incident(incident_id: str, body: IncidentUpdate, user: dict = Depends(get_current_user)):
    client = get_supabase_authed_client(user["token"])
    update_data = {k: v for k, v in body.model_dump().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")
    result = client.table("data_breach_incidents").update(update_data).eq("id", incident_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Incident not found")

    log_action(
        user_id=user["id"], user_email=user["email"],
        action="update_incident", resource_type="data_breach_incident",
        resource_id=incident_id,
    )
    return result.data[0]


@router.get("/incidents/{incident_id}/notification")
async def get_notification_template(incident_id: str, user: dict = Depends(get_current_user)):
    """Generate a pre-filled regulator notification template for UU PDP compliance."""
    client = get_supabase_authed_client(user["token"])
    result = client.table("data_breach_incidents").select("*").eq("id", incident_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Incident not found")

    inc = result.data[0]
    categories = ", ".join(inc.get("affected_data_categories", []))

    template = f"""NOTIFIKASI PELANGGARAN DATA PRIBADI
Sesuai UU PDP No. 27 Tahun 2022 Pasal 46

Kepada Yth. Kementerian Komunikasi dan Informatika RI

Dengan ini kami memberitahukan terjadinya pelanggaran data pribadi:

Tanggal Insiden: {inc.get('incident_date', '-')}
Tanggal Ditemukan: {inc.get('discovered_date', '-')}
Jenis Insiden: {inc.get('incident_type', '-')}
Kategori Data Terdampak: {categories}
Estimasi Jumlah Subjek Data: {inc.get('estimated_records', 'Sedang dihitung')}

Deskripsi:
{inc.get('description', '-')}

Penyebab Utama:
{inc.get('root_cause', 'Dalam investigasi')}

Tindakan Remediasi:
{inc.get('remediation_actions', 'Dalam proses')}

Hormat kami,
[Nama DPO / Pejabat Berwenang]
[Nama Perusahaan]"""

    return {"template": template, "incident": inc}


# ── Personal Data Scanner ─────────────────────────────────────


@router.post("/scan-document")
async def scan_document(
    document: UploadFile,
    user: dict = Depends(get_current_user),
):
    """Scan a document for personal data categories per UU PDP."""
    file_bytes = await document.read()
    doc_text = _extract_text(file_bytes, document.content_type or "text/plain")

    if not doc_text.strip():
        raise HTTPException(status_code=400, detail="Document has no extractable text")

    result = await scan_for_personal_data(doc_text)

    log_action(
        user_id=user["id"], user_email=user["email"],
        action="scan_personal_data", resource_type="pdp_scan",
        details={"categories_found": result.data_categories_found, "findings_count": len(result.findings)},
    )
    return result.model_dump()
