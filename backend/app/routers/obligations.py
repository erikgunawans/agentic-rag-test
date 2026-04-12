from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from app.dependencies import get_current_user
from app.database import get_supabase_authed_client, get_supabase_client
from app.services.audit_service import log_action

router = APIRouter(prefix="/obligations", tags=["obligations"])


class ObligationCreate(BaseModel):
    document_id: str | None = None
    analysis_id: str | None = None
    party: str
    obligation_text: str
    obligation_type: str = "general"
    deadline: str | None = None
    recurrence: str | None = None
    priority: str = "medium"
    reminder_days: int = Field(default=7, ge=1, le=90)
    notes: str | None = None
    contract_title: str | None = None


class ObligationUpdate(BaseModel):
    status: str | None = None
    priority: str | None = None
    deadline: str | None = None
    recurrence: str | None = None
    reminder_days: int | None = Field(default=None, ge=1, le=90)
    notes: str | None = None


@router.get("")
async def list_obligations(
    status: str | None = None,
    priority: str | None = None,
    obligation_type: str | None = None,
    document_id: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: dict = Depends(get_current_user),
):
    """List obligations with optional filters."""
    client = get_supabase_authed_client(user["token"])
    query = client.table("obligations").select("*").eq("user_id", user["id"])

    if status:
        query = query.eq("status", status)
    if priority:
        query = query.eq("priority", priority)
    if obligation_type:
        query = query.eq("obligation_type", obligation_type)
    if document_id:
        query = query.eq("document_id", document_id)

    query = query.order("deadline", desc=False, nulls_last=True).range(offset, offset + limit - 1)
    result = query.execute()
    return {"data": result.data, "count": len(result.data)}


@router.get("/summary")
async def get_summary(user: dict = Depends(get_current_user)):
    """Obligation counts by status for dashboard widgets."""
    client = get_supabase_authed_client(user["token"])
    rows = client.table("obligations").select("status").eq("user_id", user["id"]).execute().data

    counts = {"active": 0, "completed": 0, "overdue": 0, "upcoming": 0, "cancelled": 0, "total": len(rows)}
    for row in rows:
        s = row["status"]
        if s in counts:
            counts[s] += 1
    return counts


@router.post("")
async def create_obligation(
    body: ObligationCreate,
    user: dict = Depends(get_current_user),
):
    """Create a single obligation manually."""
    client = get_supabase_authed_client(user["token"])
    row = client.table("obligations").insert({
        "user_id": user["id"],
        **body.model_dump(exclude_none=True),
    }).execute()

    ob = row.data[0]
    log_action(
        user_id=user["id"],
        user_email=user["email"],
        action="create",
        resource_type="obligation",
        resource_id=str(ob["id"]),
    )
    return ob


@router.post("/extract/{analysis_id}")
async def extract_obligations(
    analysis_id: str,
    user: dict = Depends(get_current_user),
):
    """Extract obligations from an existing contract analysis result into structured rows."""
    client = get_supabase_authed_client(user["token"])

    # Fetch the analysis result
    rows = client.table("document_tool_results").select("result, title").eq(
        "id", analysis_id
    ).eq("user_id", user["id"]).execute().data

    if not rows:
        raise HTTPException(status_code=404, detail="Analysis result not found")

    result_data = rows[0]["result"]
    contract_title = rows[0].get("title", "")
    obligations = result_data.get("obligations", [])

    if not obligations:
        raise HTTPException(status_code=400, detail="No obligations found in this analysis result")

    # Insert each obligation
    inserted = []
    for ob in obligations:
        row = client.table("obligations").insert({
            "user_id": user["id"],
            "analysis_id": analysis_id,
            "party": ob.get("party", "Unknown"),
            "obligation_text": ob.get("obligation", ""),
            "obligation_type": "general",
            "deadline": None,
            "status": "active",
            "priority": "medium",
            "contract_title": contract_title,
        }).execute()
        inserted.append(row.data[0])

    log_action(
        user_id=user["id"],
        user_email=user["email"],
        action="extract_obligations",
        resource_type="obligation",
        details={"analysis_id": analysis_id, "count": len(inserted)},
    )
    return {"extracted": len(inserted), "obligations": inserted}


@router.post("/check-deadlines")
async def check_deadlines(user: dict = Depends(get_current_user)):
    """Update status of obligations based on deadlines (overdue/upcoming)."""
    client = get_supabase_client()
    client.rpc("check_overdue_obligations", {"p_user_id": user["id"]}).execute()
    return {"ok": True}


@router.patch("/{obligation_id}")
async def update_obligation(
    obligation_id: str,
    body: ObligationUpdate,
    user: dict = Depends(get_current_user),
):
    """Update an obligation's status, priority, deadline, or notes."""
    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    client = get_supabase_authed_client(user["token"])
    result = client.table("obligations").update(updates).eq(
        "id", obligation_id
    ).eq("user_id", user["id"]).execute()

    if not result.data:
        raise HTTPException(status_code=404, detail="Obligation not found")

    log_action(
        user_id=user["id"],
        user_email=user["email"],
        action="update",
        resource_type="obligation",
        resource_id=obligation_id,
        details={"changed_fields": list(updates.keys())},
    )
    return result.data[0]


@router.delete("/{obligation_id}", status_code=204)
async def delete_obligation(
    obligation_id: str,
    user: dict = Depends(get_current_user),
):
    """Delete (cancel) an obligation."""
    client = get_supabase_authed_client(user["token"])
    result = client.table("obligations").update(
        {"status": "cancelled"}
    ).eq("id", obligation_id).eq("user_id", user["id"]).execute()

    if not result.data:
        raise HTTPException(status_code=404, detail="Obligation not found")

    log_action(
        user_id=user["id"],
        user_email=user["email"],
        action="cancel",
        resource_type="obligation",
        resource_id=obligation_id,
    )
