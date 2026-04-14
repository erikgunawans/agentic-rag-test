from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from app.dependencies import get_current_user, require_admin
from app.database import get_supabase_authed_client, get_supabase_client
from app.services.audit_service import log_action

router = APIRouter(prefix="/regulatory", tags=["regulatory"])


class SourceCreate(BaseModel):
    name: str
    url: str
    source_type: str
    crawl_schedule: str | None = None
    css_selector: str | None = None
    metadata: dict | None = None


class SourceUpdate(BaseModel):
    name: str | None = None
    url: str | None = None
    source_type: str | None = None
    crawl_schedule: str | None = None
    css_selector: str | None = None
    metadata: dict | None = None


# --- Sources ---

@router.get("/sources")
async def list_sources(user: dict = Depends(get_current_user)):
    """List all regulatory sources."""
    client = get_supabase_authed_client(user["token"])
    result = client.table("regulatory_sources").select("*").order("created_at", desc=True).execute()
    return {"data": result.data}


@router.post("/sources", status_code=201)
async def create_source(body: SourceCreate, user: dict = Depends(require_admin)):
    """Create a regulatory source (admin only)."""
    client = get_supabase_client()
    row = client.table("regulatory_sources").insert({
        "created_by": user["id"],
        **body.model_dump(exclude_none=True),
    }).execute()

    source = row.data[0]
    log_action(
        user_id=user["id"],
        user_email=user["email"],
        action="create",
        resource_type="regulatory_source",
        resource_id=str(source["id"]),
    )
    return source


@router.patch("/sources/{source_id}")
async def update_source(source_id: str, body: SourceUpdate, user: dict = Depends(require_admin)):
    """Update a regulatory source (admin only)."""
    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    client = get_supabase_client()
    result = client.table("regulatory_sources").update(updates).eq("id", source_id).execute()

    if not result.data:
        raise HTTPException(status_code=404, detail="Source not found")

    log_action(
        user_id=user["id"],
        user_email=user["email"],
        action="update",
        resource_type="regulatory_source",
        resource_id=source_id,
        details={"changed_fields": list(updates.keys())},
    )
    return result.data[0]


@router.delete("/sources/{source_id}", status_code=204)
async def delete_source(source_id: str, user: dict = Depends(require_admin)):
    """Delete a regulatory source (admin only)."""
    client = get_supabase_client()
    result = client.table("regulatory_sources").delete().eq("id", source_id).execute()

    if not result.data:
        raise HTTPException(status_code=404, detail="Source not found")

    log_action(
        user_id=user["id"],
        user_email=user["email"],
        action="delete",
        resource_type="regulatory_source",
        resource_id=source_id,
    )


# --- Updates ---

@router.get("/updates")
async def list_updates(
    source_id: str | None = None,
    is_read: bool | None = None,
    limit: int = Query(30, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: dict = Depends(get_current_user),
):
    """List regulatory updates with optional filters."""
    client = get_supabase_authed_client(user["token"])
    query = client.table("regulatory_updates").select("*")

    if source_id:
        query = query.eq("source_id", source_id)
    if is_read is not None:
        query = query.eq("is_read", is_read)

    query = query.order("crawled_at", desc=True).range(offset, offset + limit - 1)
    result = query.execute()
    return {"data": result.data, "count": len(result.data)}


@router.get("/updates/{update_id}")
async def get_update(update_id: str, user: dict = Depends(get_current_user)):
    """Get a single regulatory update."""
    client = get_supabase_authed_client(user["token"])
    result = client.table("regulatory_updates").select("*").eq("id", update_id).execute()

    if not result.data:
        raise HTTPException(status_code=404, detail="Update not found")

    return result.data[0]


@router.patch("/updates/{update_id}/read")
async def mark_update_read(update_id: str, user: dict = Depends(get_current_user)):
    """Mark a regulatory update as read."""
    client = get_supabase_authed_client(user["token"])
    result = client.table("regulatory_updates").update(
        {"is_read": True}
    ).eq("id", update_id).execute()

    if not result.data:
        raise HTTPException(status_code=404, detail="Update not found")

    return result.data[0]


# --- Alerts ---

@router.get("/alerts")
async def list_alerts(user: dict = Depends(get_current_user)):
    """List user's unread alerts with update title."""
    client = get_supabase_authed_client(user["token"])
    result = client.table("regulatory_alerts").select(
        "*, regulatory_updates(title)"
    ).eq("user_id", user["id"]).eq("is_dismissed", False).order(
        "created_at", desc=True
    ).execute()

    return {"data": result.data}


@router.patch("/alerts/{alert_id}/dismiss")
async def dismiss_alert(alert_id: str, user: dict = Depends(get_current_user)):
    """Dismiss an alert."""
    client = get_supabase_authed_client(user["token"])
    result = client.table("regulatory_alerts").update(
        {"is_dismissed": True}
    ).eq("id", alert_id).eq("user_id", user["id"]).execute()

    if not result.data:
        raise HTTPException(status_code=404, detail="Alert not found")

    return result.data[0]
