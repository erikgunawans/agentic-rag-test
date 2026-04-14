from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from app.dependencies import get_current_user
from app.database import get_supabase_authed_client
from app.services.audit_service import log_action

router = APIRouter(prefix="/document-templates", tags=["document-templates"])


class TemplateCreate(BaseModel):
    name: str
    doc_type: str
    default_values: dict = {}
    default_clauses: list[str] = []


class TemplateUpdate(BaseModel):
    name: str | None = None
    doc_type: str | None = None
    default_values: dict | None = None
    default_clauses: list[str] | None = None


@router.get("")
async def list_templates(
    doc_type: str | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: dict = Depends(get_current_user),
):
    client = get_supabase_authed_client(user["token"])
    query = client.table("document_templates").select("*")
    if doc_type:
        query = query.eq("doc_type", doc_type)
    query = query.order("is_global", desc=True).order("created_at", desc=True)
    query = query.range(offset, offset + limit - 1)
    result = query.execute()
    return {"data": result.data, "count": len(result.data)}


@router.get("/{template_id}")
async def get_template(template_id: str, user: dict = Depends(get_current_user)):
    client = get_supabase_authed_client(user["token"])
    result = client.table("document_templates").select("*").eq("id", template_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Template not found")
    template = result.data[0]

    # Resolve default_clauses to full clause objects
    clauses = []
    clause_ids = template.get("default_clauses", [])
    if clause_ids:
        clause_result = client.table("clause_library").select("*").in_("id", clause_ids).execute()
        clauses = clause_result.data

    return {"template": template, "clauses": clauses}


@router.post("", status_code=201)
async def create_template(body: TemplateCreate, user: dict = Depends(get_current_user)):
    client = get_supabase_authed_client(user["token"])
    row = client.table("document_templates").insert({
        "user_id": user["id"],
        "name": body.name,
        "doc_type": body.doc_type,
        "default_values": body.default_values,
        "default_clauses": body.default_clauses,
        "is_global": False,
    }).execute()
    log_action(
        user_id=user["id"], user_email=user["email"],
        action="create", resource_type="document_template",
        resource_id=str(row.data[0]["id"]),
    )
    return row.data[0]


@router.patch("/{template_id}")
async def update_template(template_id: str, body: TemplateUpdate, user: dict = Depends(get_current_user)):
    client = get_supabase_authed_client(user["token"])
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    result = client.table("document_templates").update(updates).eq("id", template_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Template not found or not editable")
    log_action(
        user_id=user["id"], user_email=user["email"],
        action="update", resource_type="document_template",
        resource_id=template_id,
    )
    return result.data[0]


@router.delete("/{template_id}", status_code=204)
async def delete_template(template_id: str, user: dict = Depends(get_current_user)):
    client = get_supabase_authed_client(user["token"])
    result = client.table("document_templates").delete().eq("id", template_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Template not found or not deletable")
    log_action(
        user_id=user["id"], user_email=user["email"],
        action="delete", resource_type="document_template",
        resource_id=template_id,
    )
