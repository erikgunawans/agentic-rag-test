from fastapi import APIRouter, Depends
from pydantic import BaseModel
from app.dependencies import require_admin
from app.services.system_settings_service import (
    get_system_settings,
    update_system_settings,
)

router = APIRouter(prefix="/admin", tags=["admin"])


class SystemSettingsUpdate(BaseModel):
    llm_model: str | None = None
    embedding_model: str | None = None
    rag_top_k: int | None = None
    rag_similarity_threshold: float | None = None
    rag_chunk_size: int | None = None
    rag_chunk_overlap: int | None = None
    rag_hybrid_enabled: bool | None = None
    rag_rrf_k: int | None = None
    tools_enabled: bool | None = None
    tools_max_iterations: int | None = None
    agents_enabled: bool | None = None


@router.get("/settings")
async def get_settings(user: dict = Depends(require_admin)):
    return get_system_settings()


@router.patch("/settings")
async def patch_settings(
    body: SystemSettingsUpdate,
    user: dict = Depends(require_admin),
):
    updates = body.model_dump(exclude_none=True)
    if not updates:
        return get_system_settings()
    return update_system_settings(updates)
