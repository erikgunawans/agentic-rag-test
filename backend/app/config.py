from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


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


@lru_cache
def get_settings() -> Settings:
    return Settings()
