import json
import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from app.dependencies import get_current_user, require_admin
from app.database import get_supabase_authed_client, get_supabase_client
from app.services.audit_service import log_action
from app.services.bjr_service import assess_evidence, calculate_bjr_score
from app.services.system_settings_service import get_system_settings
from app.models.bjr import (
    DecisionCreate, DecisionUpdate,
    EvidenceCreate, RiskCreate, RiskUpdate,
    RegulatoryItemCreate, RegulatoryItemUpdate,
    ChecklistTemplateCreate, ChecklistTemplateUpdate,
    GCGAspectCreate, GCGAspectUpdate,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/bjr", tags=["bjr"])


# ── Decision CRUD ─────────────────────────────────────────────


@router.post("/decisions", status_code=201)
async def create_decision(body: DecisionCreate, user: dict = Depends(get_current_user)):
    client = get_supabase_authed_client(user["token"])
    row = client.table("bjr_decisions").insert({
        "user_id": user["id"],
        "user_email": user["email"],
        "title": body.title,
        "description": body.description,
        "decision_type": body.decision_type,
        "risk_level": body.risk_level,
        "estimated_value": body.estimated_value,
        "gcg_aspect_ids": body.gcg_aspect_ids,
        "metadata": body.metadata,
    }).execute()

    log_action(
        user_id=user["id"], user_email=user["email"],
        action="create_decision", resource_type="bjr_decision",
        resource_id=str(row.data[0]["id"]),
    )
    return row.data[0]


@router.get("/decisions")
async def list_decisions(
    phase: str | None = Query(None),
    status: str | None = Query(None),
    decision_type: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: dict = Depends(get_current_user),
):
    client = get_supabase_authed_client(user["token"])
    query = client.table("bjr_decisions").select("*")
    if phase:
        query = query.eq("current_phase", phase)
    if status:
        query = query.eq("status", status)
    if decision_type:
        query = query.eq("decision_type", decision_type)
    query = query.neq("status", "cancelled").order("created_at", desc=True).range(offset, offset + limit - 1)
    result = query.execute()
    return {"data": result.data}


@router.get("/decisions/{decision_id}")
async def get_decision(decision_id: str, user: dict = Depends(get_current_user)):
    client = get_supabase_authed_client(user["token"])

    decision = client.table("bjr_decisions").select("*").eq("id", decision_id).execute()
    if not decision.data:
        raise HTTPException(status_code=404, detail="Decision not found")

    # Get all checklist items
    checklist = client.table("bjr_checklist_templates").select("*").eq("is_active", True).order("phase").order("item_order").execute()

    # Get all evidence for this decision
    evidence = client.table("bjr_evidence").select("*").eq("decision_id", decision_id).order("created_at").execute()

    # Get risks (decision-specific + global)
    risks = client.table("bjr_risk_register").select("*").or_(
        f"decision_id.eq.{decision_id},is_global.eq.true"
    ).order("risk_level").execute()

    return {
        "decision": decision.data[0],
        "checklist": checklist.data,
        "evidence": evidence.data,
        "risks": risks.data,
    }


@router.patch("/decisions/{decision_id}")
async def update_decision(decision_id: str, body: DecisionUpdate, user: dict = Depends(get_current_user)):
    client = get_supabase_authed_client(user["token"])

    # Verify ownership
    existing = client.table("bjr_decisions").select("user_id, status").eq("id", decision_id).execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail="Decision not found")
    if existing.data[0]["status"] in ("completed", "cancelled"):
        raise HTTPException(status_code=409, detail="Cannot update a completed/cancelled decision")

    update_data = {k: v for k, v in body.model_dump().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")

    result = client.table("bjr_decisions").update(update_data).eq("id", decision_id).execute()

    log_action(
        user_id=user["id"], user_email=user["email"],
        action="update_decision", resource_type="bjr_decision",
        resource_id=decision_id,
    )
    return result.data[0] if result.data else {"status": "updated"}


@router.delete("/decisions/{decision_id}")
async def cancel_decision(decision_id: str, user: dict = Depends(get_current_user)):
    client = get_supabase_authed_client(user["token"])

    existing = client.table("bjr_decisions").select("status").eq("id", decision_id).execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail="Decision not found")
    if existing.data[0]["status"] in ("completed", "cancelled"):
        raise HTTPException(status_code=409, detail="Cannot cancel a completed/cancelled decision")

    client.table("bjr_decisions").update({"status": "cancelled"}).eq("id", decision_id).execute()

    log_action(
        user_id=user["id"], user_email=user["email"],
        action="cancel_decision", resource_type="bjr_decision",
        resource_id=decision_id,
    )
    return {"status": "cancelled"}


# ── Evidence Management ───────────────────────────────────────


@router.post("/decisions/{decision_id}/evidence", status_code=201)
async def attach_evidence(
    decision_id: str,
    body: EvidenceCreate,
    user: dict = Depends(get_current_user),
):
    client = get_supabase_authed_client(user["token"])

    # Verify decision exists and is active
    decision = client.table("bjr_decisions").select("status").eq("id", decision_id).execute()
    if not decision.data:
        raise HTTPException(status_code=404, detail="Decision not found")
    if decision.data[0]["status"] in ("completed", "cancelled"):
        raise HTTPException(status_code=409, detail="Cannot attach evidence to completed/cancelled decision")

    row = client.table("bjr_evidence").insert({
        "decision_id": decision_id,
        "checklist_item_id": body.checklist_item_id,
        "evidence_type": body.evidence_type,
        "reference_id": body.reference_id,
        "reference_table": body.reference_table,
        "title": body.title,
        "notes": body.notes,
        "external_url": body.external_url,
        "attached_by": user["id"],
    }).execute()

    log_action(
        user_id=user["id"], user_email=user["email"],
        action="attach_evidence", resource_type="bjr_decision",
        resource_id=decision_id,
        details={"evidence_id": str(row.data[0]["id"]), "checklist_item_id": body.checklist_item_id},
    )
    return row.data[0]


@router.delete("/evidence/{evidence_id}")
async def remove_evidence(evidence_id: str, user: dict = Depends(get_current_user)):
    client = get_supabase_authed_client(user["token"])
    # Check decision is not completed/cancelled before allowing removal
    ev = client.table("bjr_evidence").select("decision_id").eq("id", evidence_id).execute()
    if ev.data:
        decision = client.table("bjr_decisions").select("status").eq("id", ev.data[0]["decision_id"]).execute()
        if decision.data and decision.data[0]["status"] in ("completed", "cancelled"):
            raise HTTPException(status_code=409, detail="Cannot modify evidence on completed/cancelled decision")
    result = client.table("bjr_evidence").delete().eq("id", evidence_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Evidence not found")
    return {"status": "removed"}


@router.post("/evidence/{evidence_id}/assess")
async def assess_evidence_endpoint(evidence_id: str, user: dict = Depends(get_current_user)):
    """Trigger LLM assessment of evidence against its checklist requirement."""
    client = get_supabase_authed_client(user["token"])

    # Fetch evidence
    ev = client.table("bjr_evidence").select("*").eq("id", evidence_id).execute()
    if not ev.data:
        raise HTTPException(status_code=404, detail="Evidence not found")
    evidence = ev.data[0]

    # Guard: no assessment on completed/cancelled decisions
    decision_status = client.table("bjr_decisions").select("status").eq("id", evidence["decision_id"]).execute()
    if decision_status.data and decision_status.data[0]["status"] in ("completed", "cancelled"):
        raise HTTPException(status_code=409, detail="Cannot assess evidence on completed/cancelled decision")

    # Fetch checklist item
    item = client.table("bjr_checklist_templates").select("*").eq("id", evidence["checklist_item_id"]).execute()
    if not item.data:
        raise HTTPException(status_code=404, detail="Checklist item not found")
    checklist_item = item.data[0]

    # Fetch decision for context
    decision = client.table("bjr_decisions").select("title, description, decision_type").eq("id", evidence["decision_id"]).execute()
    decision_context = ""
    if decision.data:
        d = decision.data[0]
        decision_context = f"Keputusan: {d['title']}\nTipe: {d['decision_type']}\nDeskripsi: {d.get('description', '')}"

    # Get regulatory references
    reg_refs = []
    if checklist_item.get("regulatory_item_ids"):
        regs = client.table("bjr_regulatory_items").select("code, title").in_("id", checklist_item["regulatory_item_ids"]).execute()
        reg_refs = [f"{r['code']} — {r['title']}" for r in regs.data]

    # Get evidence text — use authed client to enforce RLS (user can only read own data)
    evidence_text = ""
    if evidence["evidence_type"] == "manual_note":
        evidence_text = evidence.get("notes", "")
    elif evidence["evidence_type"] == "tool_result" and evidence.get("reference_id"):
        tool_result = client.table("document_tool_results").select("result, title").eq("id", evidence["reference_id"]).execute()
        if tool_result.data:

            evidence_text = f"Tool Result: {tool_result.data[0].get('title', '')}\n{json.dumps(tool_result.data[0].get('result', {}), indent=2, ensure_ascii=False)}"
    elif evidence["evidence_type"] == "document" and evidence.get("reference_id"):
        doc = client.table("documents").select("filename, metadata").eq("id", evidence["reference_id"]).execute()
        if doc.data:

            evidence_text = f"Document: {doc.data[0].get('filename', '')}\nMetadata: {json.dumps(doc.data[0].get('metadata', {}), indent=2, ensure_ascii=False)}"
    elif evidence["evidence_type"] == "external_link":
        evidence_text = f"External link: {evidence.get('external_url', '')}\nNotes: {evidence.get('notes', '')}"

    if not evidence_text:
        evidence_text = evidence.get("notes", "") or evidence.get("title", "No content available")

    # Run LLM assessment
    assessment = await assess_evidence(
        evidence_text=evidence_text,
        checklist_item_title=checklist_item["title"],
        checklist_item_description=checklist_item.get("description", ""),
        regulatory_references=reg_refs,
        decision_context=decision_context,
    )

    # Apply confidence gating — must BOTH meet threshold AND satisfy the requirement
    threshold = get_system_settings().get("confidence_threshold", 0.85)
    if assessment.confidence_score >= threshold and assessment.satisfies_requirement:
        review_status = "auto_approved"
    elif assessment.confidence_score >= threshold and not assessment.satisfies_requirement:
        review_status = "rejected"  # High confidence it does NOT satisfy
    else:
        review_status = "pending_review"

    # Update evidence with assessment
    assessment_data = assessment.model_dump()
    client.table("bjr_evidence").update({
        "llm_assessment": assessment_data,
        "confidence_score": assessment.confidence_score,
        "review_status": review_status,
    }).eq("id", evidence_id).execute()

    # Recalculate decision BJR score
    score = calculate_bjr_score(evidence["decision_id"])
    client.table("bjr_decisions").update({"bjr_score": score}).eq("id", evidence["decision_id"]).execute()

    log_action(
        user_id=user["id"], user_email=user["email"],
        action="assess_evidence", resource_type="bjr_decision",
        resource_id=evidence["decision_id"],
        details={"evidence_id": evidence_id, "confidence": assessment.confidence_score, "satisfies": assessment.satisfies_requirement},
    )

    return {**assessment_data, "review_status": review_status}


# ── Phase Progression ─────────────────────────────────────────


@router.post("/decisions/{decision_id}/submit-phase")
async def submit_phase(decision_id: str, user: dict = Depends(get_current_user)):
    """Submit current phase for approval — creates an approval_request."""
    client = get_supabase_authed_client(user["token"])

    decision = client.table("bjr_decisions").select("*").eq("id", decision_id).execute()
    if not decision.data:
        raise HTTPException(status_code=404, detail="Decision not found")

    d = decision.data[0]
    if d["status"] == "under_review":
        raise HTTPException(status_code=409, detail="Phase already submitted for review")
    if d["status"] == "cancelled":
        raise HTTPException(status_code=409, detail="Cannot submit phase for cancelled decision")
    if d["current_phase"] == "completed":
        raise HTTPException(status_code=409, detail="Decision already completed")

    phase_names = {
        "pre_decision": "Pra-Keputusan",
        "decision": "Keputusan",
        "post_decision": "Pasca-Keputusan",
    }
    phase_label = phase_names.get(d["current_phase"], d["current_phase"])

    # Check for existing pending approval
    existing = client.table("approval_requests").select("id, status").eq("resource_id", decision_id).eq("resource_type", "bjr_phase").in_("status", ["pending", "in_progress"]).execute()
    if existing.data:
        raise HTTPException(status_code=409, detail="Approval request already pending for this phase")

    # Get default approval template
    tpl = client.table("approval_workflow_templates").select("*").eq("is_active", True).order("created_at").limit(1).execute()
    if not tpl.data:
        raise HTTPException(status_code=400, detail="No active approval workflow template found")

    # Create approval request
    approval = client.table("approval_requests").insert({
        "user_id": user["id"],
        "template_id": tpl.data[0]["id"],
        "resource_type": "bjr_phase",
        "resource_id": decision_id,
        "title": f"BJR Phase Review: {d['title']} — {phase_label}",
        "status": "pending",
        "current_step": 1,
    }).execute()

    # Update decision status
    client.table("bjr_decisions").update({"status": "under_review"}).eq("id", decision_id).execute()

    log_action(
        user_id=user["id"], user_email=user["email"],
        action="submit_phase", resource_type="bjr_decision",
        resource_id=decision_id,
        details={"phase": d["current_phase"], "approval_id": str(approval.data[0]["id"])},
    )

    return {"approval_id": approval.data[0]["id"], "phase": d["current_phase"]}


@router.get("/decisions/{decision_id}/phase-status")
async def get_phase_status(decision_id: str, user: dict = Depends(get_current_user)):
    client = get_supabase_authed_client(user["token"])
    approval = client.table("approval_requests").select("*").eq("resource_id", decision_id).eq("resource_type", "bjr_phase").order("submitted_at", desc=True).limit(1).execute()
    return {"approval": approval.data[0] if approval.data else None}


# ── Risk Register ─────────────────────────────────────────────


@router.get("/risks")
async def list_risks(
    decision_id: str | None = Query(None),
    status: str | None = Query(None),
    is_global: bool | None = Query(None),
    user: dict = Depends(get_current_user),
):
    client = get_supabase_authed_client(user["token"])
    query = client.table("bjr_risk_register").select("*")
    if decision_id:
        query = query.or_(f"decision_id.eq.{decision_id},is_global.eq.true")
    if is_global is not None:
        query = query.eq("is_global", is_global)
    if status:
        query = query.eq("status", status)
    query = query.order("risk_level").order("created_at", desc=True)
    result = query.execute()
    return {"data": result.data}


@router.post("/risks", status_code=201)
async def create_risk(body: RiskCreate, user: dict = Depends(get_current_user)):
    client = get_supabase_authed_client(user["token"])

    if body.is_global and user["role"] != "super_admin":
        raise HTTPException(status_code=403, detail="Only admins can create global risks")

    row = client.table("bjr_risk_register").insert({
        "decision_id": body.decision_id,
        "risk_title": body.risk_title,
        "description": body.description,
        "risk_level": body.risk_level,
        "mitigation": body.mitigation,
        "owner_role": body.owner_role,
        "is_global": body.is_global,
        "created_by": user["id"],
    }).execute()

    log_action(
        user_id=user["id"], user_email=user["email"],
        action="create_risk", resource_type="bjr_risk",
        resource_id=str(row.data[0]["id"]),
    )
    return row.data[0]


@router.patch("/risks/{risk_id}")
async def update_risk(risk_id: str, body: RiskUpdate, user: dict = Depends(get_current_user)):
    client = get_supabase_authed_client(user["token"])
    update_data = {k: v for k, v in body.model_dump().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")

    result = client.table("bjr_risk_register").update(update_data).eq("id", risk_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Risk not found")

    log_action(
        user_id=user["id"], user_email=user["email"],
        action="update_risk", resource_type="bjr_risk",
        resource_id=risk_id,
    )
    return result.data[0]


# ── Admin: Regulatory Items ───────────────────────────────────


@router.get("/regulatory-items")
async def list_regulatory_items(
    layer: str | None = Query(None),
    user: dict = Depends(get_current_user),
):
    client = get_supabase_authed_client(user["token"])
    query = client.table("bjr_regulatory_items").select("*").eq("is_active", True)
    if layer:
        query = query.eq("layer", layer)
    query = query.order("layer").order("code")
    result = query.execute()
    return {"data": result.data}


@router.post("/regulatory-items", status_code=201)
async def create_regulatory_item(body: RegulatoryItemCreate, user: dict = Depends(require_admin)):
    client = get_supabase_client()
    row = client.table("bjr_regulatory_items").insert({
        "code": body.code,
        "title": body.title,
        "layer": body.layer,
        "substance": body.substance,
        "url": body.url,
        "critical_notes": body.critical_notes,
        "created_by": user["id"],
    }).execute()

    log_action(
        user_id=user["id"], user_email=user["email"],
        action="create", resource_type="bjr_regulatory_item",
        resource_id=str(row.data[0]["id"]),
    )
    return row.data[0]


@router.patch("/regulatory-items/{item_id}")
async def update_regulatory_item(item_id: str, body: RegulatoryItemUpdate, user: dict = Depends(require_admin)):
    client = get_supabase_client()
    update_data = {k: v for k, v in body.model_dump().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")
    result = client.table("bjr_regulatory_items").update(update_data).eq("id", item_id).execute()
    return result.data[0] if result.data else {"status": "updated"}


# ── Admin: Checklist Templates ────────────────────────────────


@router.get("/checklist-templates")
async def list_checklist_templates(
    phase: str | None = Query(None),
    user: dict = Depends(get_current_user),
):
    client = get_supabase_authed_client(user["token"])
    query = client.table("bjr_checklist_templates").select("*").eq("is_active", True)
    if phase:
        query = query.eq("phase", phase)
    query = query.order("phase").order("item_order")
    result = query.execute()
    return {"data": result.data}


@router.post("/checklist-templates", status_code=201)
async def create_checklist_template(body: ChecklistTemplateCreate, user: dict = Depends(require_admin)):
    client = get_supabase_client()
    row = client.table("bjr_checklist_templates").insert({
        "phase": body.phase,
        "item_order": body.item_order,
        "title": body.title,
        "description": body.description,
        "regulatory_item_ids": body.regulatory_item_ids,
        "is_required": body.is_required,
        "created_by": user["id"],
    }).execute()
    return row.data[0]


@router.patch("/checklist-templates/{template_id}")
async def update_checklist_template(template_id: str, body: ChecklistTemplateUpdate, user: dict = Depends(require_admin)):
    client = get_supabase_client()
    update_data = {k: v for k, v in body.model_dump().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")
    result = client.table("bjr_checklist_templates").update(update_data).eq("id", template_id).execute()
    return result.data[0] if result.data else {"status": "updated"}


# ── Admin: GCG Aspects ────────────────────────────────────────


@router.get("/gcg-aspects")
async def list_gcg_aspects(user: dict = Depends(get_current_user)):
    client = get_supabase_authed_client(user["token"])
    result = client.table("bjr_gcg_aspects").select("*").eq("is_active", True).order("aspect_name").execute()
    return {"data": result.data}


@router.post("/gcg-aspects", status_code=201)
async def create_gcg_aspect(body: GCGAspectCreate, user: dict = Depends(require_admin)):
    client = get_supabase_client()
    row = client.table("bjr_gcg_aspects").insert({
        "aspect_name": body.aspect_name,
        "regulatory_item_ids": body.regulatory_item_ids,
        "indicators": body.indicators,
        "frequency": body.frequency,
        "pic_role": body.pic_role,
        "created_by": user["id"],
    }).execute()
    return row.data[0]


@router.patch("/gcg-aspects/{aspect_id}")
async def update_gcg_aspect(aspect_id: str, body: GCGAspectUpdate, user: dict = Depends(require_admin)):
    client = get_supabase_client()
    update_data = {k: v for k, v in body.model_dump().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")
    result = client.table("bjr_gcg_aspects").update(update_data).eq("id", aspect_id).execute()
    return result.data[0] if result.data else {"status": "updated"}


# ── Summary / Dashboard ───────────────────────────────────────


@router.get("/summary")
async def bjr_summary(user: dict = Depends(get_current_user)):
    client = get_supabase_authed_client(user["token"])

    decisions = client.table("bjr_decisions").select("id, current_phase, status, bjr_score, risk_level").neq("status", "cancelled").execute()

    phase_counts = {"pre_decision": 0, "decision": 0, "post_decision": 0, "completed": 0}
    total_score = 0.0
    risk_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}

    for d in decisions.data:
        phase_counts[d["current_phase"]] = phase_counts.get(d["current_phase"], 0) + 1
        total_score += d.get("bjr_score", 0)
        if d.get("risk_level"):
            risk_counts[d["risk_level"]] = risk_counts.get(d["risk_level"], 0) + 1

    avg_score = round(total_score / len(decisions.data), 1) if decisions.data else 0.0

    # Open risks count
    risks = client.table("bjr_risk_register").select("id", count="exact").eq("status", "open").execute()

    return {
        "total_decisions": len(decisions.data),
        "by_phase": phase_counts,
        "average_bjr_score": avg_score,
        "risk_distribution": risk_counts,
        "open_risks": risks.count or 0,
    }
