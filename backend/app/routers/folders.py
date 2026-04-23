from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from app.dependencies import get_current_user
from app.database import get_supabase_client
from app.services.audit_service import log_action

router = APIRouter(prefix="/folders", tags=["folders"])


class CreateFolderRequest(BaseModel):
    name: str
    parent_folder_id: str | None = None


class RenameFolderRequest(BaseModel):
    name: str


class MoveFolderRequest(BaseModel):
    parent_folder_id: str | None = None  # null = move to root


@router.post("", status_code=201)
async def create_folder(
    body: CreateFolderRequest,
    user: dict = Depends(get_current_user),
):
    client = get_supabase_client()

    # Validate parent exists and belongs to user
    if body.parent_folder_id:
        parent = (
            client.table("document_folders")
            .select("id")
            .eq("id", body.parent_folder_id)
            .eq("user_id", user["id"])
            .limit(1)
            .execute()
        )
        if not parent.data:
            raise HTTPException(status_code=404, detail="Parent folder not found")

    insert_data = {
        "user_id": user["id"],
        "name": body.name.strip(),
        "parent_folder_id": body.parent_folder_id,
    }

    try:
        result = client.table("document_folders").insert(insert_data).execute()
    except Exception as e:
        if "idx_folders_unique_name" in str(e):
            raise HTTPException(status_code=409, detail="A folder with this name already exists here")
        raise

    folder = result.data[0]

    log_action(
        user_id=user["id"],
        user_email=user["email"],
        action="create",
        resource_type="folder",
        resource_id=str(folder["id"]),
        details={"name": body.name, "parent_folder_id": body.parent_folder_id},
    )

    return folder


@router.get("")
async def list_folders(user: dict = Depends(get_current_user)):
    """List all folders visible to the user (own + global from others)."""
    client = get_supabase_client()
    # RLS handles visibility — own folders + global subtrees
    result = (
        client.table("document_folders")
        .select("id, user_id, name, parent_folder_id, is_global, created_at, updated_at")
        .or_(f"user_id.eq.{user['id']},is_global.eq.true")
        .order("name")
        .execute()
    )
    # For global folders, also include their non-global children (subtree cascade)
    global_ids = {f["id"] for f in result.data if f.get("is_global")}
    if global_ids:
        all_folders = {f["id"]: f for f in result.data}
        # Fetch children of global folders that might not be in the initial set
        children = (
            client.table("document_folders")
            .select("id, user_id, name, parent_folder_id, is_global, created_at, updated_at")
            .in_("parent_folder_id", list(global_ids))
            .execute()
        )
        for child in children.data or []:
            if child["id"] not in all_folders:
                all_folders[child["id"]] = child
        return list(all_folders.values())
    return result.data


@router.get("/tree")
async def get_folder_tree(
    max_depth: int = Query(default=10, ge=1, le=20),
    user: dict = Depends(get_current_user),
):
    """Return the full folder hierarchy via recursive CTE."""
    client = get_supabase_client()
    result = client.rpc(
        "get_folder_tree",
        {"p_user_id": user["id"], "p_max_depth": max_depth},
    ).execute()
    return result.data or []


@router.patch("/{folder_id}")
async def rename_folder(
    folder_id: str,
    body: RenameFolderRequest,
    user: dict = Depends(get_current_user),
):
    client = get_supabase_client()
    result = (
        client.table("document_folders")
        .update({"name": body.name.strip()})
        .eq("id", folder_id)
        .eq("user_id", user["id"])
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Folder not found")
    return result.data[0]


@router.patch("/{folder_id}/move")
async def move_folder(
    folder_id: str,
    body: MoveFolderRequest,
    user: dict = Depends(get_current_user),
):
    # Prevent moving a folder into itself
    if body.parent_folder_id == folder_id:
        raise HTTPException(status_code=400, detail="Cannot move a folder into itself")

    client = get_supabase_client()

    # Validate target parent exists
    if body.parent_folder_id:
        parent = (
            client.table("document_folders")
            .select("id")
            .eq("id", body.parent_folder_id)
            .eq("user_id", user["id"])
            .limit(1)
            .execute()
        )
        if not parent.data:
            raise HTTPException(status_code=404, detail="Target folder not found")

    result = (
        client.table("document_folders")
        .update({"parent_folder_id": body.parent_folder_id})
        .eq("id", folder_id)
        .eq("user_id", user["id"])
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Folder not found")
    return result.data[0]


@router.delete("/{folder_id}", status_code=204)
async def delete_folder(
    folder_id: str,
    user: dict = Depends(get_current_user),
):
    client = get_supabase_client()

    folder = (
        client.table("document_folders")
        .select("id, name")
        .eq("id", folder_id)
        .eq("user_id", user["id"])
        .limit(1)
        .execute()
    )
    if not folder.data:
        raise HTTPException(status_code=404, detail="Folder not found")

    # Documents in this folder get folder_id = NULL (ON DELETE SET NULL)
    # Subfolders cascade-delete (ON DELETE CASCADE)
    client.table("document_folders").delete().eq("id", folder_id).eq("user_id", user["id"]).execute()

    log_action(
        user_id=user["id"],
        user_email=user["email"],
        action="delete",
        resource_type="folder",
        resource_id=folder_id,
        details={"name": folder.data[0]["name"]},
    )


@router.patch("/{folder_id}/toggle-global")
async def toggle_global(
    folder_id: str,
    user: dict = Depends(get_current_user),
):
    """Toggle is_global on a top-level folder the user owns."""
    client = get_supabase_client()

    folder = (
        client.table("document_folders")
        .select("id, name, parent_folder_id, is_global")
        .eq("id", folder_id)
        .eq("user_id", user["id"])
        .limit(1)
        .execute()
    )
    if not folder.data:
        raise HTTPException(status_code=404, detail="Folder not found")

    if folder.data[0]["parent_folder_id"] is not None:
        raise HTTPException(status_code=400, detail="Only top-level folders can be shared globally")

    new_value = not folder.data[0]["is_global"]
    result = (
        client.table("document_folders")
        .update({"is_global": new_value})
        .eq("id", folder_id)
        .eq("user_id", user["id"])
        .execute()
    )

    action = "share_global" if new_value else "unshare_global"
    log_action(
        user_id=user["id"],
        user_email=user["email"],
        action=action,
        resource_type="folder",
        resource_id=folder_id,
        details={"name": folder.data[0]["name"], "is_global": new_value},
    )

    return result.data[0]
