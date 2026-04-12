from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.dependencies import get_current_user
from app.database import get_supabase_authed_client, get_supabase_client
from app.services.audit_service import log_action

router = APIRouter(prefix="/google", tags=["google-export"])


class GoogleCallback(BaseModel):
    code: str


class GoogleExport(BaseModel):
    result_id: str
    title: str


def _is_google_configured() -> bool:
    """Check if Google OAuth client ID is set in system_settings (single-row table)."""
    client = get_supabase_client()
    row = client.table("system_settings").select("google_client_id").eq("id", 1).execute()
    return bool(row.data and row.data[0].get("google_client_id"))


def _user_has_token(user: dict) -> bool:
    """Check if the current user has a stored Google token."""
    client = get_supabase_client()
    rows = (
        client.table("google_tokens")
        .select("id")
        .eq("user_id", user["id"])
        .execute()
    )
    return bool(rows.data)


@router.get("/status")
async def google_status(user: dict = Depends(get_current_user)):
    configured = _is_google_configured()
    connected = _user_has_token(user) if configured else False
    return {"configured": configured, "connected": connected}


@router.get("/auth-url")
async def google_auth_url(user: dict = Depends(get_current_user)):
    if not _is_google_configured():
        raise HTTPException(status_code=400, detail="Google OAuth not configured")
    # Stub: generate real OAuth URL when credentials are set
    return {
        "auth_url": None,
        "message": "Google OAuth not configured. Set google_client_id and google_client_secret in admin settings.",
    }


@router.post("/callback")
async def google_callback(body: GoogleCallback, user: dict = Depends(get_current_user)):
    if not _is_google_configured():
        raise HTTPException(status_code=400, detail="Google OAuth not configured")
    # Stub: exchange code for token when credentials are set
    raise HTTPException(status_code=400, detail="Google OAuth not configured")


@router.post("/export")
async def google_export(body: GoogleExport, user: dict = Depends(get_current_user)):
    if not _is_google_configured():
        raise HTTPException(status_code=400, detail="Google OAuth not configured")
    if not _user_has_token(user):
        raise HTTPException(
            status_code=400,
            detail="Connect Google Drive in settings first",
        )
    log_action(
        user_id=user["id"], user_email=user["email"],
        action="google_export", resource_type="google_drive",
        details={"result_id": body.result_id, "title": body.title},
    )
    # Stub: actual export when OAuth is fully wired
    return {"status": "not_configured", "message": "Connect Google Drive in settings first"}


@router.delete("/disconnect", status_code=204)
async def google_disconnect(user: dict = Depends(get_current_user)):
    client = get_supabase_authed_client(user["token"])
    client.table("google_tokens").delete().eq("user_id", user["id"]).execute()
    log_action(
        user_id=user["id"], user_email=user["email"],
        action="google_disconnect", resource_type="google_drive",
    )
