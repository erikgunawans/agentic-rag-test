import csv
import io

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from app.dependencies import require_admin
from app.database import get_supabase_client

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/audit-logs")
async def get_audit_logs(
    user: dict = Depends(require_admin),
    action: str | None = None,
    resource_type: str | None = None,
    user_id: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
):
    """Paginated audit log query with filters. Admin only."""
    client = get_supabase_client()
    query = client.table("audit_logs").select("*")

    if action:
        query = query.eq("action", action)
    if resource_type:
        query = query.eq("resource_type", resource_type)
    if user_id:
        query = query.eq("user_id", user_id)
    if date_from:
        query = query.gte("created_at", date_from)
    if date_to:
        query = query.lte("created_at", date_to)

    query = query.order("created_at", desc=True).range(offset, offset + limit - 1)
    result = query.execute()
    return {"data": result.data, "count": len(result.data)}


@router.get("/audit-logs/export")
async def export_audit_logs(
    user: dict = Depends(require_admin),
    action: str | None = None,
    resource_type: str | None = None,
    user_id: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
):
    """Export audit logs as CSV. Admin only."""
    client = get_supabase_client()
    query = client.table("audit_logs").select("*")

    if action:
        query = query.eq("action", action)
    if resource_type:
        query = query.eq("resource_type", resource_type)
    if user_id:
        query = query.eq("user_id", user_id)
    if date_from:
        query = query.gte("created_at", date_from)
    if date_to:
        query = query.lte("created_at", date_to)

    query = query.order("created_at", desc=True).limit(10000)
    result = query.execute()

    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=["created_at", "user_email", "action", "resource_type", "resource_id", "details", "ip_address"],
    )
    writer.writeheader()
    for row in result.data:
        writer.writerow({
            "created_at": row.get("created_at", ""),
            "user_email": row.get("user_email", ""),
            "action": row.get("action", ""),
            "resource_type": row.get("resource_type", ""),
            "resource_id": row.get("resource_id", ""),
            "details": str(row.get("details", "")),
            "ip_address": row.get("ip_address", ""),
        })

    output.seek(0)
    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=audit-logs.csv"},
    )


@router.get("/audit-logs/actions")
async def get_audit_actions(user: dict = Depends(require_admin)):
    """Return distinct action types for filter dropdown."""
    client = get_supabase_client()
    # Fetch only action column, deduplicate in Python.
    # For large tables, consider a SQL DISTINCT query via RPC.
    result = client.table("audit_logs").select("action").limit(5000).execute()
    actions = sorted(set(row["action"] for row in result.data))
    return {"actions": actions}
