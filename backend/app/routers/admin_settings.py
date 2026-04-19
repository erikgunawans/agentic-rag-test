from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from app.dependencies import require_admin
from app.services.audit_service import log_action
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
    confidence_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    rag_vector_weight: float | None = Field(default=None, ge=0.0, le=10.0)
    rag_fulltext_weight: float | None = Field(default=None, ge=0.0, le=10.0)
    rag_rerank_mode: str | None = None


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
    result = update_system_settings(updates)
    log_action(
        user_id=user["id"],
        user_email=user["email"],
        action="update",
        resource_type="system_settings",
        details={"changed_fields": list(updates.keys())},
    )
    return result
