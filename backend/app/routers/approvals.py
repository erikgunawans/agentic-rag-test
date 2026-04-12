from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from app.dependencies import get_current_user, require_admin
from app.database import get_supabase_authed_client, get_supabase_client
from app.services.audit_service import log_action

router = APIRouter(prefix="/approvals", tags=["approvals"])


class SubmitApproval(BaseModel):
    resource_type: str = "document_tool_result"
    resource_id: str
    title: str
    template_id: str | None = None


class ApprovalAction(BaseModel):
    action: str  # approve, reject, return
    comments: str = ""


class WorkflowTemplateCreate(BaseModel):
    name: str
    description: str = ""
    steps: list[dict] = [{"step_order": 1, "approver_role": "super_admin", "approver_email": None}]


# --- User endpoints ---

@router.post("/submit", status_code=201)
async def submit_for_approval(body: SubmitApproval, user: dict = Depends(get_current_user)):
    client = get_supabase_authed_client(user["token"])

    # Get template (use provided or default)
    if body.template_id:
        tpl = client.table("approval_workflow_templates").select("*").eq("id", body.template_id).eq("is_active", True).execute()
    else:
        tpl = client.table("approval_workflow_templates").select("*").eq("is_active", True).order("created_at").limit(1).execute()

    if not tpl.data:
        raise HTTPException(status_code=400, detail="No active approval workflow template found")

    template = tpl.data[0]

    # Check for existing pending/in_progress request for same resource
    existing = client.table("approval_requests").select("id, status").eq("resource_id", body.resource_id).in_("status", ["pending", "in_progress"]).execute()
    if existing.data:
        raise HTTPException(status_code=409, detail="An approval request already exists for this resource")

    row = client.table("approval_requests").insert({
        "user_id": user["id"],
        "template_id": template["id"],
        "resource_type": body.resource_type,
        "resource_id": body.resource_id,
        "title": body.title,
        "status": "pending",
        "current_step": 1,
    }).execute()

    log_action(
        user_id=user["id"], user_email=user["email"],
        action="submit_approval", resource_type="approval_request",
        resource_id=str(row.data[0]["id"]),
        details={"resource_type": body.resource_type, "resource_id": body.resource_id},
    )
    return row.data[0]


@router.get("/my-requests")
async def list_my_requests(
    status: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    user: dict = Depends(get_current_user),
):
    client = get_supabase_authed_client(user["token"])
    query = client.table("approval_requests").select("*").eq("user_id", user["id"])
    if status:
        query = query.eq("status", status)
    query = query.order("submitted_at", desc=True).limit(limit)
    result = query.execute()
    return {"data": result.data}


@router.get("/inbox")
async def approval_inbox(
    status: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    user: dict = Depends(get_current_user),
):
    """Get approval requests pending action from the current user (admin inbox)."""
    if user["role"] != "super_admin":
        return {"data": []}

    client = get_supabase_authed_client(user["token"])
    query = client.table("approval_requests").select("*")
    if status:
        query = query.eq("status", status)
    else:
        query = query.in_("status", ["pending", "in_progress"])
    query = query.order("submitted_at", desc=True).limit(limit)
    result = query.execute()
    return {"data": result.data}


@router.get("/{request_id}")
async def get_approval_request(request_id: str, user: dict = Depends(get_current_user)):
    client = get_supabase_authed_client(user["token"])
    req = client.table("approval_requests").select("*").eq("id", request_id).execute()
    if not req.data:
        raise HTTPException(status_code=404, detail="Approval request not found")

    # Get actions history
    actions = client.table("approval_actions").select("*").eq("request_id", request_id).order("acted_at").execute()

    # Get the resource (document tool result)
    resource = None
    request = req.data[0]
    if request["resource_type"] == "document_tool_result":
        res = client.table("document_tool_results").select("*").eq("id", request["resource_id"]).execute()
        if res.data:
            resource = res.data[0]

    return {
        "request": request,
        "actions": actions.data,
        "resource": resource,
    }


@router.post("/{request_id}/action")
async def take_action(request_id: str, body: ApprovalAction, user: dict = Depends(get_current_user)):
    if user["role"] != "super_admin":
        raise HTTPException(status_code=403, detail="Only admins can take approval actions")

    if body.action not in ("approve", "reject", "return"):
        raise HTTPException(status_code=400, detail="Action must be approve, reject, or return")

    client = get_supabase_authed_client(user["token"])

    # Get request
    req = client.table("approval_requests").select("*").eq("id", request_id).execute()
    if not req.data:
        raise HTTPException(status_code=404, detail="Approval request not found")

    request = req.data[0]
    if request["status"] not in ("pending", "in_progress"):
        raise HTTPException(status_code=409, detail=f"Request is already {request['status']}")

    # Record the action
    client.table("approval_actions").insert({
        "request_id": request_id,
        "step_order": request["current_step"],
        "actor_id": user["id"],
        "actor_email": user["email"],
        "action": body.action,
        "comments": body.comments[:2000] if body.comments else "",
    }).execute()

    # Update request status
    if body.action == "approve":
        # Check if there are more steps
        template = client.table("approval_workflow_templates").select("steps").eq("id", request["template_id"]).execute()
        steps = template.data[0]["steps"] if template.data else []
        total_steps = len(steps)

        if request["current_step"] >= total_steps:
            # Final approval
            client.table("approval_requests").update({
                "status": "approved",
                "completed_at": "now()",
            }).eq("id", request_id).execute()
        else:
            # Advance to next step
            client.table("approval_requests").update({
                "status": "in_progress",
                "current_step": request["current_step"] + 1,
            }).eq("id", request_id).execute()
    elif body.action == "reject":
        client.table("approval_requests").update({
            "status": "rejected",
            "completed_at": "now()",
        }).eq("id", request_id).execute()
    elif body.action == "return":
        client.table("approval_requests").update({
            "status": "pending",
            "current_step": 1,
        }).eq("id", request_id).execute()

    log_action(
        user_id=user["id"], user_email=user["email"],
        action=f"approval_{body.action}", resource_type="approval_request",
        resource_id=request_id,
        details={"comments": body.comments[:200] if body.comments else ""},
    )

    return {"status": "ok", "action": body.action}


@router.post("/{request_id}/cancel")
async def cancel_request(request_id: str, user: dict = Depends(get_current_user)):
    client = get_supabase_authed_client(user["token"])
    req = client.table("approval_requests").select("*").eq("id", request_id).eq("user_id", user["id"]).execute()
    if not req.data:
        raise HTTPException(status_code=404, detail="Request not found")
    if req.data[0]["status"] not in ("pending", "in_progress"):
        raise HTTPException(status_code=409, detail="Cannot cancel a completed request")

    client.table("approval_requests").update({
        "status": "cancelled",
        "completed_at": "now()",
    }).eq("id", request_id).execute()

    log_action(
        user_id=user["id"], user_email=user["email"],
        action="cancel_approval", resource_type="approval_request",
        resource_id=request_id,
    )
    return {"status": "cancelled"}


# --- Admin template endpoints ---

@router.get("/templates/list")
async def list_templates(user: dict = Depends(get_current_user)):
    client = get_supabase_authed_client(user["token"])
    result = client.table("approval_workflow_templates").select("*").order("created_at", desc=True).execute()
    return {"data": result.data}


@router.post("/templates", status_code=201)
async def create_template(body: WorkflowTemplateCreate, user: dict = Depends(require_admin)):
    client = get_supabase_client()
    row = client.table("approval_workflow_templates").insert({
        "name": body.name,
        "description": body.description,
        "steps": body.steps,
        "created_by": user["id"],
        "is_active": True,
    }).execute()
    log_action(
        user_id=user["id"], user_email=user["email"],
        action="create", resource_type="approval_workflow_template",
        resource_id=str(row.data[0]["id"]),
    )
    return row.data[0]
