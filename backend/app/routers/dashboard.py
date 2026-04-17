from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Query
from app.dependencies import get_current_user
from app.database import get_supabase_authed_client, get_supabase_client

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary")
async def get_summary(user: dict = Depends(get_current_user)):
    """Aggregated counts for the executive dashboard."""
    client = get_supabase_client()

    # Documents
    docs = client.table("documents").select("status").execute().data
    docs_total = len(docs)
    docs_completed = sum(1 for d in docs if d["status"] == "completed")
    docs_processing = sum(1 for d in docs if d["status"] == "processing")

    # Obligations
    obs = client.table("obligations").select("status").execute().data
    obs_total = len(obs)
    obs_active = sum(1 for o in obs if o["status"] == "active")
    obs_overdue = sum(1 for o in obs if o["status"] == "overdue")
    obs_upcoming = sum(1 for o in obs if o["status"] == "upcoming")
    obs_completed = sum(1 for o in obs if o["status"] == "completed")

    # Approvals
    approvals = client.table("approval_requests").select("status").execute().data
    apr_total = len(approvals)
    apr_pending = sum(1 for a in approvals if a["status"] == "pending")
    apr_approved = sum(1 for a in approvals if a["status"] == "approved")
    apr_rejected = sum(1 for a in approvals if a["status"] == "rejected")

    # Compliance
    compliance = client.table("document_tool_results").select(
        "result"
    ).eq("tool_type", "compliance").execute().data
    comp_total = len(compliance)
    comp_pass = 0
    comp_review = 0
    comp_fail = 0
    for c in compliance:
        overall = (c.get("result") or {}).get("overall_status", "")
        if overall == "pass":
            comp_pass += 1
        elif overall == "review":
            comp_review += 1
        elif overall == "fail":
            comp_fail += 1

    # Regulatory
    sources = client.table("regulatory_sources").select("id", count="exact").execute()
    reg_sources = sources.count if sources.count is not None else len(sources.data)

    updates = client.table("regulatory_updates").select("id", count="exact").execute()
    reg_updates = updates.count if updates.count is not None else len(updates.data)

    unread_alerts = client.table("regulatory_alerts").select(
        "id", count="exact"
    ).eq("is_dismissed", False).execute()
    reg_unread = unread_alerts.count if unread_alerts.count is not None else len(unread_alerts.data)

    # BJR Decisions
    bjr_decisions = client.table("bjr_decisions").select("current_phase, bjr_score").neq("status", "cancelled").execute().data
    bjr_total = len(bjr_decisions)
    bjr_active = sum(1 for d in bjr_decisions if d["current_phase"] != "completed")
    bjr_completed = sum(1 for d in bjr_decisions if d["current_phase"] == "completed")
    bjr_avg_score = round(sum(d.get("bjr_score", 0) for d in bjr_decisions) / bjr_total, 1) if bjr_total else 0.0

    bjr_open_risks = client.table("bjr_risk_register").select("id", count="exact").eq("status", "open").execute()
    bjr_risks = bjr_open_risks.count if bjr_open_risks.count is not None else len(bjr_open_risks.data)

    return {
        "documents": {"total": docs_total, "completed": docs_completed, "processing": docs_processing},
        "obligations": {
            "total": obs_total, "active": obs_active, "overdue": obs_overdue,
            "upcoming": obs_upcoming, "completed": obs_completed,
        },
        "approvals": {
            "total": apr_total, "pending": apr_pending,
            "approved": apr_approved, "rejected": apr_rejected,
        },
        "compliance": {
            "total_checks": comp_total, "pass": comp_pass,
            "review": comp_review, "fail": comp_fail,
        },
        "regulatory": {
            "sources": reg_sources, "updates": reg_updates,
            "unread_alerts": reg_unread,
        },
        "bjr": {
            "total": bjr_total, "active": bjr_active,
            "completed": bjr_completed, "avg_score": bjr_avg_score,
            "open_risks": bjr_risks,
        },
    }


@router.get("/obligation-timeline")
async def obligation_timeline(user: dict = Depends(get_current_user)):
    """Upcoming obligations for the next 90 days."""
    client = get_supabase_authed_client(user["token"])

    result = client.table("obligations").select(
        "id, party, obligation_text, deadline, status, priority, contract_title"
    ).eq("user_id", user["id"]).in_(
        "status", ["active", "upcoming"]
    ).not_.is_("deadline", "null").order(
        "deadline", desc=False
    ).limit(20).execute()

    return {"data": result.data}


@router.get("/compliance-trend")
async def compliance_trend(user: dict = Depends(get_current_user)):
    """Compliance check results grouped by month for the last 6 months."""
    client = get_supabase_client()

    six_months_ago = (datetime.utcnow() - timedelta(days=180)).isoformat()

    rows = client.table("document_tool_results").select(
        "created_at, result"
    ).eq("tool_type", "compliance").gte("created_at", six_months_ago).order(
        "created_at", desc=False
    ).execute().data

    # Group by month
    monthly: dict[str, dict[str, int]] = {}
    for row in rows:
        month = row["created_at"][:7]  # "YYYY-MM"
        if month not in monthly:
            monthly[month] = {"pass": 0, "review": 0, "fail": 0}
        overall = (row.get("result") or {}).get("overall_status", "")
        if overall in ("pass", "review", "fail"):
            monthly[month][overall] += 1

    trend = [{"month": m, **counts} for m, counts in sorted(monthly.items())]
    return {"data": trend}
