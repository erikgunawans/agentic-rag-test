from typing import Literal
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
    rag_rerank_mode: Literal["none", "llm", "cohere"] | None = None

    # Phase 3: Entity resolution mode + global LLM provider (D-60)
    entity_resolution_mode: Literal["algorithmic", "llm", "none"] | None = None
    llm_provider: Literal["local", "cloud"] | None = None
    llm_provider_fallback_enabled: bool | None = None

    # Phase 3: Per-feature provider overrides (None = inherit global) (D-51)
    entity_resolution_llm_provider: Literal["local", "cloud"] | None = None
    missed_scan_llm_provider: Literal["local", "cloud"] | None = None
    title_gen_llm_provider: Literal["local", "cloud"] | None = None
    metadata_llm_provider: Literal["local", "cloud"] | None = None
    fuzzy_deanon_llm_provider: Literal["local", "cloud"] | None = None

    # Phase 4 forward-compat (column shipped in Phase 3 to avoid migration churn)
    pii_missed_scan_enabled: bool | None = None

    # Phase 4: Fuzzy de-anonymization (D-67..D-70)
    fuzzy_deanon_mode: Literal["algorithmic", "llm", "none"] | None = None
    fuzzy_deanon_threshold: float | None = Field(default=None, ge=0.50, le=1.00)


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


@router.get("/settings/llm-provider-status")
async def get_llm_provider_status(user: dict = Depends(require_admin)) -> dict:
    """D-58: masked status badge for cloud key + local-endpoint reachability.

    NEVER returns the raw cloud key. Returns booleans only:
      - cloud_key_configured: True iff settings.cloud_llm_api_key has any value.
      - local_endpoint_reachable: True iff GET LOCAL_LLM_BASE_URL/models returns 2xx.
    """
    from app.config import get_settings as _get_app_settings
    import httpx

    app_settings = _get_app_settings()
    cloud_key_configured = bool(app_settings.cloud_llm_api_key)

    local_endpoint_reachable = False
    probe_url = f"{app_settings.local_llm_base_url.rstrip('/')}/models"
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get(probe_url)
            local_endpoint_reachable = 200 <= resp.status_code < 300
    except Exception:
        # Probe failure → reachable=False; never crash the endpoint.
        local_endpoint_reachable = False

    return {
        "cloud_key_configured": cloud_key_configured,
        "local_endpoint_reachable": local_endpoint_reachable,
    }
