import re
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator
from postgrest.exceptions import APIError as PostgrestAPIError

from app.dependencies import get_current_user
from app.database import get_supabase_authed_client, get_supabase_client
from app.services.audit_service import log_action
from app.services.skill_zip_service import (
    build_skill_zip,
    parse_skill_zip,
    ImportResult,
    SkillImportItem,
)

router = APIRouter(prefix="/skills", tags=["skills"])

NAME_REGEX = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class SkillCreate(BaseModel):
    name: str = Field(..., max_length=64)
    description: str = Field(..., min_length=20, max_length=1024)
    instructions: str = Field(..., min_length=1)
    enabled: bool = True
    metadata: dict = Field(default_factory=dict)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v):
        if not NAME_REGEX.match(v):
            raise ValueError(
                "Invalid name: must match ^[a-z][a-z0-9]*(-[a-z0-9]+)*$"
            )
        return v


class SkillUpdate(BaseModel):
    name: str | None = Field(None, max_length=64)
    description: str | None = Field(None, min_length=20, max_length=1024)
    instructions: str | None = None
    enabled: bool | None = None
    metadata: dict | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v):
        if v is not None and not NAME_REGEX.match(v):
            raise ValueError("Invalid name format")
        return v


class ShareToggle(BaseModel):
    global_: bool = Field(..., alias="global")  # body: {"global": true|false}
    model_config = ConfigDict(populate_by_name=True)


class SkillResponse(BaseModel):
    id: str
    user_id: str | None
    created_by: str | None
    name: str
    description: str
    instructions: str
    enabled: bool
    metadata: dict
    created_at: datetime
    updated_at: datetime

    @computed_field
    @property
    def is_global(self) -> bool:
        return self.user_id is None


# ---------------------------------------------------------------------------
# Endpoint 1: POST /skills — create a private skill
# ---------------------------------------------------------------------------


@router.post("", status_code=201, response_model=SkillResponse)
async def create_skill(body: SkillCreate, user: dict = Depends(get_current_user)):
    client = get_supabase_authed_client(user["token"])
    try:
        result = client.table("skills").insert({
            "user_id": user["id"],
            "created_by": user["id"],
            "name": body.name,
            "description": body.description,
            "instructions": body.instructions,
            "enabled": body.enabled,
            "metadata": body.metadata,
        }).execute()
    except PostgrestAPIError as exc:
        if exc.code == "23505":
            raise HTTPException(status_code=409, detail="Skill name already exists")
        raise
    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to create skill")
    log_action(
        user_id=user["id"],
        user_email=user["email"],
        action="create",
        resource_type="skill",
        resource_id=str(result.data[0]["id"]),
    )
    return SkillResponse(**result.data[0])


# ---------------------------------------------------------------------------
# Endpoint 8: POST /skills/import — MUST be declared before /{id} routes
# so FastAPI matches /skills/import before /skills/{id}
# ---------------------------------------------------------------------------


@router.post("/import", response_model=ImportResult)
async def import_skills(
    request: Request,
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
):
    """Import skills from a ZIP file (Skills Open Standard format).

    The 50 MB body cap is enforced by SkillsUploadSizeMiddleware BEFORE FastAPI
    parses the multipart body (cycle-2 review H6 fix).  The endpoint still
    includes `request: Request` for future per-request checks.

    EXPORT-03 closure: errors are aggregated per-skill; earlier failures do NOT
    block later skills in a bulk import.
    """
    content = await file.read()

    try:
        parsed_skills = parse_skill_zip(content)
    except ValueError:
        raise HTTPException(status_code=413, detail="ZIP exceeds 50 MB limit")

    client = get_supabase_authed_client(user["token"])
    results: list[SkillImportItem] = []
    created_count = 0
    error_count = 0

    for parsed in parsed_skills:
        if parsed.error:
            # Fatal skill-level parse error
            results.append(
                SkillImportItem(
                    name=parsed.frontmatter.name if parsed.frontmatter else "(unknown)",
                    status="error",
                    error=parsed.error,
                    skipped_files=[],
                )
            )
            error_count += 1
            continue

        # parsed.frontmatter is guaranteed non-None here
        fm = parsed.frontmatter  # type: ignore[union-attr]

        # INSERT skill row via RLS-scoped client
        try:
            skill_result = client.table("skills").insert({
                "user_id": user["id"],
                "created_by": user["id"],
                "name": fm.name,
                "description": fm.description,
                "instructions": parsed.instructions_md,
                "enabled": True,
                "metadata": fm.metadata,
            }).execute()
        except PostgrestAPIError as exc:
            error_msg = (
                "Skill name already exists" if exc.code == "23505" else str(exc.message)
            )
            results.append(
                SkillImportItem(
                    name=fm.name,
                    status="error",
                    error=error_msg,
                    skipped_files=parsed.skipped_files,
                )
            )
            error_count += 1
            continue

        if not skill_result.data:
            results.append(
                SkillImportItem(
                    name=fm.name,
                    status="error",
                    error="Database insert returned no data",
                    skipped_files=parsed.skipped_files,
                )
            )
            error_count += 1
            continue

        skill_id = str(skill_result.data[0]["id"])
        file_errors: list[str] = []

        # Upload skill files via RLS-scoped client.
        # Storage path must be three flat segments: {user_id}/{skill_id}/{flat_name}
        # (CHECK constraint: '^[a-zA-Z0-9_-]+/[0-9a-fA-F-]{36}/[^/]+$').
        # Flatten relative_path (e.g. "scripts/foo.py") by replacing '/' with '__'.
        for skill_file in parsed.files:
            flat_name = skill_file.relative_path.replace("/", "__")
            storage_path = f"{user['id']}/{skill_id}/{flat_name}"
            try:
                client.storage.from_("skills-files").upload(
                    storage_path,
                    skill_file.content,
                    {"content-type": "application/octet-stream"},
                )
                # Insert skill_files row — filename stores the original relative path
                client.table("skill_files").insert({
                    "skill_id": skill_id,
                    "filename": flat_name,
                    "size_bytes": skill_file.size_bytes,
                    "storage_path": storage_path,
                    "created_by": user["id"],
                }).execute()
            except Exception as exc:
                file_errors.append(f"{skill_file.relative_path}: {exc}")

        if file_errors:
            # File upload errors are non-fatal for the skill itself
            results.append(
                SkillImportItem(
                    name=fm.name,
                    status="created",
                    skill_id=skill_id,
                    error=f"Partial file errors: {'; '.join(file_errors)}",
                    skipped_files=parsed.skipped_files,
                )
            )
        else:
            results.append(
                SkillImportItem(
                    name=fm.name,
                    status="created",
                    skill_id=skill_id,
                    skipped_files=parsed.skipped_files,
                )
            )
        created_count += 1

    log_action(
        user_id=user["id"],
        user_email=user["email"],
        action="import",
        resource_type="skill",
        resource_id=None,
        details={"created_count": created_count, "error_count": error_count},
    )
    return ImportResult(
        created_count=created_count,
        error_count=error_count,
        results=results,
    )


# ---------------------------------------------------------------------------
# Endpoint 2: GET /skills — list with search/filter
# ---------------------------------------------------------------------------


@router.get("", response_model=dict)
async def list_skills(
    search: str | None = Query(None),
    enabled: bool | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: dict = Depends(get_current_user),
):
    client = get_supabase_authed_client(user["token"])
    query = client.table("skills").select("*")

    if search:
        # Sanitize search — matches clause_library.py:53 pattern
        safe_search = (
            search.replace(",", "")
            .replace("(", "")
            .replace(")", "")
            .replace(".", " ")
        )
        query = query.or_(
            f"name.ilike.%{safe_search}%,description.ilike.%{safe_search}%"
        )

    if enabled is not None:
        query = query.eq("enabled", enabled)

    # Cycle-1 review HIGH #3 fix: order by user_id NULLS FIRST (globals first),
    # then by created_at DESC. No is_global column in DB — computed Pydantic-side only.
    query = (
        query
        .order("user_id", desc=False, nullsfirst=True)
        .order("created_at", desc=True)
        .range(offset, offset + limit - 1)
    )

    result = query.execute()
    skills = [SkillResponse(**row) for row in result.data]
    return {"data": [s.model_dump() for s in skills], "count": len(skills)}


# ---------------------------------------------------------------------------
# Endpoint 3: GET /skills/{id} — fetch single skill
# ---------------------------------------------------------------------------


@router.get("/{skill_id}", response_model=SkillResponse)
async def get_skill(skill_id: str, user: dict = Depends(get_current_user)):
    client = get_supabase_authed_client(user["token"])
    result = client.table("skills").select("*").eq("id", skill_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Skill not found")
    return SkillResponse(**result.data[0])


# ---------------------------------------------------------------------------
# Endpoint 4: PATCH /skills/{id} — update a private skill
# ---------------------------------------------------------------------------


@router.patch("/{skill_id}", response_model=SkillResponse)
async def update_skill(
    skill_id: str,
    body: SkillUpdate,
    user: dict = Depends(get_current_user),
):
    client = get_supabase_authed_client(user["token"])

    # Pre-fetch to check ownership and global status
    existing = client.table("skills").select("*").eq("id", skill_id).execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail="Skill not found")

    row = existing.data[0]
    if row["user_id"] is None:
        # D-P7-03: global skills are read-only via PATCH — creator must unshare first
        raise HTTPException(
            status_code=403,
            detail="Cannot edit a global skill — unshare it first",
        )

    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    try:
        result = client.table("skills").update(updates).eq("id", skill_id).execute()
    except PostgrestAPIError as exc:
        if exc.code == "23505":
            raise HTTPException(status_code=409, detail="Skill name already exists")
        raise

    if not result.data:
        raise HTTPException(status_code=404, detail="Skill not found or not editable")

    log_action(
        user_id=user["id"],
        user_email=user["email"],
        action="update",
        resource_type="skill",
        resource_id=skill_id,
    )
    return SkillResponse(**result.data[0])


# ---------------------------------------------------------------------------
# Endpoint 5: DELETE /skills/{id} — delete a skill
# ---------------------------------------------------------------------------


@router.delete("/{skill_id}", status_code=204)
async def delete_skill(skill_id: str, user: dict = Depends(get_current_user)):
    # D-P7-04: super_admin may delete ANY skill (admin moderation)
    if user.get("role") == "super_admin":
        # service-role: admin moderation per D-P7-04
        admin_client = get_supabase_client()
        existing = admin_client.table("skills").select("id").eq("id", skill_id).execute()
        if not existing.data:
            raise HTTPException(status_code=404, detail="Skill not found")
        admin_client.table("skills").delete().eq("id", skill_id).execute()
        log_action(
            user_id=user["id"],
            user_email=user["email"],
            action="delete",
            resource_type="skill",
            resource_id=skill_id,
        )
        return

    # RLS-scoped DELETE — requires user_id = auth.uid() AND created_by = auth.uid()
    # (private-and-owned only). Creators must unshare before deleting a global skill.
    client = get_supabase_authed_client(user["token"])

    # Pre-fetch to distinguish 404 from 403 (global skill exists but can't delete)
    existing = client.table("skills").select("id,user_id").eq("id", skill_id).execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail="Skill not found")

    row = existing.data[0]
    if row["user_id"] is None:
        # Skill is globally shared — creator must unshare before deleting
        raise HTTPException(
            status_code=403,
            detail="Cannot delete a global skill — unshare it first",
        )

    result = client.table("skills").delete().eq("id", skill_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Skill not found or not deletable")

    log_action(
        user_id=user["id"],
        user_email=user["email"],
        action="delete",
        resource_type="skill",
        resource_id=skill_id,
    )


# ---------------------------------------------------------------------------
# Endpoint 6: PATCH /skills/{id}/share — toggle global/private sharing
# ---------------------------------------------------------------------------


@router.patch("/{skill_id}/share", response_model=SkillResponse)
async def share_skill(
    skill_id: str,
    body: ShareToggle,
    user: dict = Depends(get_current_user),
):
    # Step 1: RLS-scoped pre-fetch to avoid existence disclosure
    client = get_supabase_authed_client(user["token"])
    existing = client.table("skills").select("*").eq("id", skill_id).execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail="Skill not found")

    row = existing.data[0]

    # Step 2: only the creator may change sharing
    if row.get("created_by") != user["id"]:
        raise HTTPException(
            status_code=403, detail="Only the creator can change sharing"
        )

    # Step 3: name-conflict guard (cycle-1 review MEDIUM fix)
    # service-role: global-name uniqueness check per D-P7-06
    svc = get_supabase_client()  # service-role: name conflict check per D-P7-06
    name_lower = row["name"].lower()

    if body.global_:
        # Check for existing global skill with same name (case-insensitive)
        conflict_check = (
            svc.table("skills")
            .select("id")
            .is_("user_id", "null")
            .ilike("name", name_lower)
            .neq("id", skill_id)
            .execute()
        )
        if conflict_check.data:
            raise HTTPException(status_code=409, detail="Skill name already exists")
    else:
        # Check for existing private skill with same owner + same name
        conflict_check = (
            svc.table("skills")
            .select("id")
            .eq("user_id", user["id"])
            .ilike("name", name_lower)
            .neq("id", skill_id)
            .execute()
        )
        if conflict_check.data:
            raise HTTPException(status_code=409, detail="Skill name already exists")

    # Step 4: service-role UPDATE to flip user_id
    # service-role: flipping user_id NULL/non-NULL bypasses general UPDATE RLS per D-P7-06
    new_user_id = None if body.global_ else row["created_by"]
    try:
        result = (
            svc.table("skills")
            .update({"user_id": new_user_id})
            .eq("id", skill_id)
            .execute()
        )
    except PostgrestAPIError as exc:
        # Cycle-2 review MEDIUM fix: translate 23505 race-condition unique violation → 409
        if exc.code == "23505":
            raise HTTPException(status_code=409, detail="Skill name already exists")
        raise

    if not result.data:
        raise HTTPException(status_code=404, detail="Skill not found")

    action = "share" if body.global_ else "unshare"
    log_action(
        user_id=user["id"],
        user_email=user["email"],
        action=action,
        resource_type="skill",
        resource_id=skill_id,
    )
    return SkillResponse(**result.data[0])


# ---------------------------------------------------------------------------
# Endpoint 7: GET /skills/{id}/export — export skill as ZIP
# ---------------------------------------------------------------------------


@router.get("/{skill_id}/export")
async def export_skill(skill_id: str, user: dict = Depends(get_current_user)):
    # RLS-scoped fetch of skill
    client = get_supabase_authed_client(user["token"])
    skill_result = client.table("skills").select("*").eq("id", skill_id).execute()
    if not skill_result.data:
        raise HTTPException(status_code=404, detail="Skill not found")

    skill = skill_result.data[0]

    # RLS-scoped fetch of matching skill_files rows
    files_result = (
        client.table("skill_files")
        .select("*")
        .eq("skill_id", skill_id)
        .execute()
    )
    files = files_result.data or []

    # Cycle-1 review HIGH #2 fix: validate storage_path shape at runtime
    # to make any future RLS regression visible.
    user_id = skill["user_id"]
    for f in files:
        sp = f["storage_path"]
        parts = sp.split("/")
        if len(parts) != 3:
            raise HTTPException(
                status_code=500,
                detail=f"Invalid storage path shape for file {f['id']}",
            )
        if parts[1] != skill_id:
            raise HTTPException(
                status_code=500,
                detail=f"storage_path skill segment mismatch for file {f['id']}",
            )
        if user_id is not None:
            # Private skill: first segment must be owner's user_id
            if parts[0] != str(user_id):
                raise HTTPException(
                    status_code=500,
                    detail=f"storage_path owner segment mismatch for file {f['id']}",
                )

    # service-role: required to download files for globally-shared skills per D-P7-07
    svc_storage = get_supabase_client()

    def bytes_loader(path: str) -> bytes:
        return svc_storage.storage.from_("skills-files").download(path)

    # Convert DB filename format ("scripts__foo.py") back to relative_path ("scripts/foo.py")
    files_for_zip = [{**f, "relative_path": f["filename"].replace("__", "/")} for f in files]
    zip_buf = build_skill_zip(skill, files_for_zip, bytes_loader)

    return StreamingResponse(
        zip_buf,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{skill["name"]}.zip"'
        },
    )
