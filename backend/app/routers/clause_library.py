from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from app.dependencies import get_current_user, require_admin
from app.database import get_supabase_authed_client, get_supabase_client
from app.services.audit_service import log_action

router = APIRouter(prefix="/clause-library", tags=["clause-library"])


class ClauseCreate(BaseModel):
    title: str
    content: str
    category: str = "general"
    applicable_doc_types: list[str] = []
    risk_level: str = "low"
    language: str = "id"
    tags: list[str] = []


class ClauseUpdate(BaseModel):
    title: str | None = None
    content: str | None = None
    category: str | None = None
    applicable_doc_types: list[str] | None = None
    risk_level: str | None = None
    language: str | None = None
    tags: list[str] | None = None


@router.get("")
async def list_clauses(
    category: str | None = Query(None),
    doc_type: str | None = Query(None),
    risk_level: str | None = Query(None),
    search: str | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: dict = Depends(get_current_user),
):
    client = get_supabase_authed_client(user["token"])
    query = client.table("clause_library").select("*")

    if category:
        query = query.eq("category", category)
    if risk_level:
        query = query.eq("risk_level", risk_level)
    if doc_type:
        # Match clauses containing this doc_type OR universal clauses (empty array)
        query = query.or_(f"applicable_doc_types.cs.{{{doc_type}}},applicable_doc_types.eq.{'{}'}")
    if search:
        query = query.or_(f"title.ilike.%{search}%,content.ilike.%{search}%")

    query = query.order("is_global", desc=True).order("created_at", desc=True)
    query = query.range(offset, offset + limit - 1)
    result = query.execute()
    return {"data": result.data, "count": len(result.data)}


@router.get("/{clause_id}")
async def get_clause(clause_id: str, user: dict = Depends(get_current_user)):
    client = get_supabase_authed_client(user["token"])
    result = client.table("clause_library").select("*").eq("id", clause_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Clause not found")
    return result.data[0]


@router.post("", status_code=201)
async def create_clause(body: ClauseCreate, user: dict = Depends(get_current_user)):
    client = get_supabase_authed_client(user["token"])
    row = client.table("clause_library").insert({
        "user_id": user["id"],
        "title": body.title,
        "content": body.content,
        "category": body.category,
        "applicable_doc_types": body.applicable_doc_types,
        "risk_level": body.risk_level,
        "language": body.language,
        "tags": body.tags,
        "is_global": False,
    }).execute()
    log_action(
        user_id=user["id"], user_email=user["email"],
        action="create", resource_type="clause",
        resource_id=str(row.data[0]["id"]),
    )
    return row.data[0]


@router.post("/global", status_code=201)
async def create_global_clause(body: ClauseCreate, user: dict = Depends(require_admin)):
    client = get_supabase_client()
    row = client.table("clause_library").insert({
        "user_id": None,
        "title": body.title,
        "content": body.content,
        "category": body.category,
        "applicable_doc_types": body.applicable_doc_types,
        "risk_level": body.risk_level,
        "language": body.language,
        "tags": body.tags,
        "is_global": True,
    }).execute()
    log_action(
        user_id=user["id"], user_email=user["email"],
        action="create_global", resource_type="clause",
        resource_id=str(row.data[0]["id"]),
    )
    return row.data[0]


@router.patch("/{clause_id}")
async def update_clause(clause_id: str, body: ClauseUpdate, user: dict = Depends(get_current_user)):
    client = get_supabase_authed_client(user["token"])
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    result = client.table("clause_library").update(updates).eq("id", clause_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Clause not found or not editable")
    log_action(
        user_id=user["id"], user_email=user["email"],
        action="update", resource_type="clause",
        resource_id=clause_id,
    )
    return result.data[0]


@router.delete("/{clause_id}", status_code=204)
async def delete_clause(clause_id: str, user: dict = Depends(get_current_user)):
    client = get_supabase_authed_client(user["token"])
    result = client.table("clause_library").delete().eq("id", clause_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Clause not found or not deletable")
    log_action(
        user_id=user["id"], user_email=user["email"],
        action="delete", resource_type="clause",
        resource_id=clause_id,
    )
