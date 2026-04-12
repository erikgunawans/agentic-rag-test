from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from app.dependencies import require_admin, get_current_user
from app.database import get_supabase_client, get_supabase_authed_client
from app.services.audit_service import log_action

router = APIRouter(prefix="/admin/users", tags=["user-management"])


class ProfileUpdate(BaseModel):
    display_name: str | None = None
    department: str | None = None


# --- Admin endpoints ---

@router.get("")
async def list_users(
    is_active: bool | None = Query(None),
    search: str | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
    user: dict = Depends(require_admin),
):
    """List all user profiles (admin only)."""
    client = get_supabase_client()
    query = client.table("user_profiles").select("*")
    if is_active is not None:
        query = query.eq("is_active", is_active)
    if search:
        query = query.or_(f"display_name.ilike.%{search}%,department.ilike.%{search}%")
    query = query.order("created_at", desc=True).limit(limit)
    result = query.execute()
    return {"data": result.data}


@router.patch("/{profile_id}/deactivate")
async def deactivate_user(profile_id: str, user: dict = Depends(require_admin)):
    """Deactivate a user account (admin only)."""
    client = get_supabase_client()
    profile = client.table("user_profiles").select("*").eq("id", profile_id).execute()
    if not profile.data:
        raise HTTPException(status_code=404, detail="User profile not found")
    if not profile.data[0]["is_active"]:
        raise HTTPException(status_code=409, detail="User is already deactivated")

    # Don't allow deactivating yourself
    if profile.data[0]["user_id"] == user["id"]:
        raise HTTPException(status_code=400, detail="Cannot deactivate your own account")

    result = client.table("user_profiles").update({
        "is_active": False,
        "deactivated_at": "now()",
        "deactivated_by": user["id"],
    }).eq("id", profile_id).execute()

    log_action(
        user_id=user["id"], user_email=user["email"],
        action="deactivate_user", resource_type="user_profile",
        resource_id=profile_id,
        details={"target_user_id": profile.data[0]["user_id"]},
    )
    return result.data[0]


@router.patch("/{profile_id}/reactivate")
async def reactivate_user(profile_id: str, user: dict = Depends(require_admin)):
    """Reactivate a deactivated user account (admin only)."""
    client = get_supabase_client()
    profile = client.table("user_profiles").select("*").eq("id", profile_id).execute()
    if not profile.data:
        raise HTTPException(status_code=404, detail="User profile not found")
    if profile.data[0]["is_active"]:
        raise HTTPException(status_code=409, detail="User is already active")

    result = client.table("user_profiles").update({
        "is_active": True,
        "deactivated_at": None,
        "deactivated_by": None,
    }).eq("id", profile_id).execute()

    log_action(
        user_id=user["id"], user_email=user["email"],
        action="reactivate_user", resource_type="user_profile",
        resource_id=profile_id,
        details={"target_user_id": profile.data[0]["user_id"]},
    )
    return result.data[0]


# --- User self-service endpoints ---

@router.get("/me")
async def get_my_profile(user: dict = Depends(get_current_user)):
    """Get current user's profile, auto-create if missing."""
    client = get_supabase_authed_client(user["token"])
    result = client.table("user_profiles").select("*").eq("user_id", user["id"]).execute()
    if result.data:
        return result.data[0]

    # Auto-create profile
    row = client.table("user_profiles").insert({
        "user_id": user["id"],
        "display_name": user["email"],
        "is_active": True,
    }).execute()
    return row.data[0]


@router.patch("/me")
async def update_my_profile(body: ProfileUpdate, user: dict = Depends(get_current_user)):
    """Update current user's profile."""
    client = get_supabase_authed_client(user["token"])
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    result = client.table("user_profiles").update(updates).eq("user_id", user["id"]).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Profile not found")
    return result.data[0]
