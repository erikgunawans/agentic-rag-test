from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from typing import Literal


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Supabase
    supabase_url: str
    supabase_anon_key: str
    supabase_service_role_key: str

    # OpenAI (used for embeddings)
    openai_api_key: str
    openai_vector_store_id: str = ""
    openai_embedding_model: str = "text-embedding-3-small"

    # OpenRouter (used for chat completions — Module 2+)
    openrouter_api_key: str = ""
    openrouter_model: str = "openai/gpt-4o-mini"

    # RAG tuning
    rag_top_k: int = 5
    rag_similarity_threshold: float = 0.3
    rag_chunk_size: int = 500
    rag_chunk_overlap: int = 50

    # Hybrid search (Module 6)
    rag_hybrid_enabled: bool = True
    rag_rrf_k: int = 60
    rag_rerank_enabled: bool = False
    rag_rerank_model: str = ""

    # RAG improvements (Phase 1)
    rag_context_enabled: bool = True
    rag_neighbor_window: int = 1
    rag_query_expansion_enabled: bool = False

    # GraphRAG (Phase 2)
    graph_enabled: bool = False
    graph_entity_extraction_model: str = ""

    # Fusion weights (Phase 2)
    rag_vector_weight: float = 1.0
    rag_fulltext_weight: float = 1.0

    # Cohere Rerank (Phase 2)
    cohere_api_key: str = ""

    # Fine-tuned embeddings (Phase 3 — infrastructure ready, model TBD)
    custom_embedding_model: str = ""

    # Tool calling (Module 7)
    tavily_api_key: str = ""
    tools_enabled: bool = True
    tools_max_iterations: int = 5

    # Sub-agents (Module 8)
    agents_enabled: bool = False
    agents_orchestrator_model: str = ""

    # Deployment
    frontend_url: str = "http://localhost:5173"

    # Supabase Storage
    storage_bucket: str = "documents"

    # LangSmith (optional)
    langsmith_api_key: str = ""
    langsmith_project: str = "rag-masterclass"
    langchain_tracing_v2: str = "false"

    # PII Redaction (milestone v1.0 — Phase 1 Detection & Anonymization Foundation)
    # See docs/PRD-PII-Redaction-System-v1.1.md §6 and .planning/phases/01-detection-anonymization-foundation/01-CONTEXT.md D-03/D-04/D-08
    pii_redaction_enabled: bool = True
    pii_surrogate_entities: str = "PERSON,EMAIL_ADDRESS,PHONE_NUMBER,LOCATION,DATE_TIME,URL,IP_ADDRESS"
    pii_redact_entities: str = "CREDIT_CARD,US_SSN,US_ITIN,US_BANK_NUMBER,IBAN_CODE,CRYPTO,US_PASSPORT,US_DRIVER_LICENSE,MEDICAL_LICENSE"
    pii_surrogate_score_threshold: float = 0.7
    pii_redact_score_threshold: float = 0.3

    # Tracing provider switch (OBS-01)
    # "" / "none"  → no-op @traced decorator (zero overhead)
    # "langsmith" → wraps langsmith.traceable
    # "langfuse"  → wraps langfuse.observe
    tracing_provider: str = ""

    # Phase 3: Entity resolution mode + global LLM provider (D-57, D-60)
    entity_resolution_mode: Literal["algorithmic", "llm", "none"] = "algorithmic"
    llm_provider: Literal["local", "cloud"] = "local"
    llm_provider_fallback_enabled: bool = False
    llm_provider_timeout_seconds: int = 30  # D-50

    # Phase 3: Per-feature provider overrides (None = inherit global) (D-51 / PROVIDER-07)
    entity_resolution_llm_provider: Literal["local", "cloud"] | None = None
    missed_scan_llm_provider: Literal["local", "cloud"] | None = None
    title_gen_llm_provider: Literal["local", "cloud"] | None = None
    metadata_llm_provider: Literal["local", "cloud"] | None = None
    fuzzy_deanon_llm_provider: Literal["local", "cloud"] | None = None

    # Phase 3: Endpoints + creds (D-50, D-58)
    local_llm_base_url: str = "http://localhost:1234/v1"
    local_llm_model: str = "llama-3.1-8b-instruct"
    cloud_llm_base_url: str = "https://api.openai.com/v1"
    cloud_llm_model: str = "gpt-4o-mini"
    cloud_llm_api_key: str = ""  # D-58: env-only; admin UI shows masked status badge

    # Phase 4 forward-compat (ship column + setting now per D-57; consumed in Phase 4)
    pii_missed_scan_enabled: bool = True

    # Phase 4: Fuzzy de-anonymization (D-67..D-70 / FR-5.4)
    # Mirrors entity_resolution_mode pattern (Phase 3) — same Literal set.
    fuzzy_deanon_mode: Literal["algorithmic", "llm", "none"] = "none"
    # D-69: PRD-mandated default 0.85; range [0.50, 1.00] (Pydantic + DB CHECK defense in depth).
    fuzzy_deanon_threshold: float = Field(default=0.85, ge=0.50, le=1.00)


@lru_cache
def get_settings() -> Settings:
    return Settings()
