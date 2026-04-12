from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from app.dependencies import get_current_user
from app.database import get_supabase_client
from app.services.audit_service import log_action

router = APIRouter(prefix="/integrations", tags=["integrations"])


class DokmeeImport(BaseModel):
    external_id: str
    filename: str
    cabinet: str


class DokmeeExport(BaseModel):
    document_id: str
    cabinet: str
    folder_path: str


def _get_dokmee_config() -> dict:
    """Read Dokmee settings from system_settings. Returns dict with configured flag."""
    client = get_supabase_client()
    rows = (
        client.table("system_settings")
        .select("key, value")
        .in_("key", ["dokmee_api_url", "dokmee_api_key"])
        .execute()
    )
    settings = {r["key"]: r["value"] for r in rows.data}
    api_url = settings.get("dokmee_api_url")
    api_key = settings.get("dokmee_api_key")
    configured = bool(api_url and api_key)
    return {"configured": configured, "api_url": api_url}


@router.get("/dokmee/status")
async def dokmee_status(user: dict = Depends(get_current_user)):
    config = _get_dokmee_config()
    return {"configured": config["configured"], "api_url": config["api_url"]}


@router.get("/dokmee/browse")
async def dokmee_browse(
    path: str = Query("/"),
    limit: int = Query(50, ge=1, le=200),
    user: dict = Depends(get_current_user),
):
    config = _get_dokmee_config()
    if not config["configured"]:
        raise HTTPException(status_code=400, detail="Dokmee integration not configured")
    # Stub: return empty listing until Dokmee API is connected
    return {"folders": [], "documents": [], "path": path}


@router.post("/dokmee/import")
async def dokmee_import(body: DokmeeImport, user: dict = Depends(get_current_user)):
    config = _get_dokmee_config()
    if not config["configured"]:
        log_action(
            user_id=user["id"], user_email=user["email"],
            action="dokmee_import_attempt", resource_type="integration",
            details={"external_id": body.external_id, "status": "not_configured"},
        )
        return {"status": "not_configured", "message": "Dokmee API integration pending configuration"}
    log_action(
        user_id=user["id"], user_email=user["email"],
        action="dokmee_import", resource_type="integration",
        details={"external_id": body.external_id, "filename": body.filename, "cabinet": body.cabinet},
    )
    # Stub: actual import logic when API key is configured
    return {"status": "not_configured", "message": "Dokmee API integration pending configuration"}


@router.post("/dokmee/export")
async def dokmee_export(body: DokmeeExport, user: dict = Depends(get_current_user)):
    config = _get_dokmee_config()
    if not config["configured"]:
        log_action(
            user_id=user["id"], user_email=user["email"],
            action="dokmee_export_attempt", resource_type="integration",
            details={"document_id": body.document_id, "status": "not_configured"},
        )
        return {"status": "not_configured", "message": "Dokmee API integration pending configuration"}
    log_action(
        user_id=user["id"], user_email=user["email"],
        action="dokmee_export", resource_type="integration",
        details={"document_id": body.document_id, "cabinet": body.cabinet, "folder_path": body.folder_path},
    )
    # Stub: actual export logic when API key is configured
    return {"status": "not_configured", "message": "Dokmee API integration pending configuration"}
