from pydantic import Field, model_validator
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

    # CTX-03 / D-P12-04: deployment-time config for the chat context-window bar.
    # Pydantic Settings reads LLM_CONTEXT_WINDOW env var; default sized to GPT-4o.
    # Surfaced via GET /settings/public (no auth) — see backend/app/routers/settings.py.
    # NOT routed through system_settings: changing LLM_CONTEXT_WINDOW only requires a
    # backend Railway redeploy, not a frontend redeploy (CTX-03 success criterion #5).
    llm_context_window: int = 128_000

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

    # Phase 6: Embedding provider switch (EMBED-01, EMBED-02; D-P6-01..D-P6-03)
    # `cloud` (default) preserves the existing OpenAI-embeddings flow (RAG-02 unchanged).
    # `local` uses an OpenAI-API-compatible local endpoint (Ollama bge-m3, nomic-embed-text, LM Studio).
    # NOTE: Switching providers does NOT trigger automatic re-embedding of existing documents
    # (D-P6-04 / EMBED-02 — deployer-managed migration; document only, no code).
    embedding_provider: Literal["local", "cloud"] = "cloud"
    local_embedding_base_url: str = ""  # e.g. "http://localhost:11434/v1" for Ollama

    # Tool calling (Module 7)
    tavily_api_key: str = ""
    tools_enabled: bool = True
    tools_max_iterations: int = 5

    # Sub-agents (Module 8)
    agents_enabled: bool = False
    agents_orchestrator_model: str = ""

    # Phase 10: Code Execution Sandbox (SANDBOX-01..06, 08; D-P10-01..D-P10-17)
    # SANDBOX-05 / D-P10: gate the execute_code tool. Default OFF — opt-in per Railway env.
    sandbox_enabled: bool = False
    # Phase 13 (TOOL-01..06; D-P13-01..D-P13-06): Unified Tool Registry & tool_search.
    # Default OFF — when False, chat.py + tool_service.py skip importing the registry
    # entirely (TOOL-05 byte-identical fallback). Env var: TOOL_REGISTRY_ENABLED.
    tool_registry_enabled: bool = False
    # Phase 15 (MCP-01): MCP server connection config.
    # Format: 'name:command:args' (split on first 2 colons; args is shlex-split).
    # Multiple servers: comma-separated. Empty = no MCP servers, zero startup cost (MCP-05).
    # Example: 'github:npx:-y @modelcontextprotocol/server-github'
    # Example (multi): 'github:npx:-y @modelcontextprotocol/server-github,postgres:python:server.py'
    mcp_servers: str = ""
    # D-P10-03: Docker Hub image (rebuild + push when packages change).
    sandbox_image: str = "lexcore-sandbox:latest"
    # D-P10-02: Railway socket-mount pattern. Override per-env if running rootless / DinD.
    sandbox_docker_host: str = "unix:///var/run/docker.sock"
    # D-P10-12: per-call execution timeout (seconds). Distinct from 30-min session TTL.
    sandbox_max_exec_seconds: int = 30
    # Phase 14 (BRIDGE-01, D-P14-01): host port the bridge FastAPI app listens on.
    # Sandbox containers connect to host.docker.internal:{bridge_port}.
    # Env var: BRIDGE_PORT. Default matches PRD §Infrastructure.
    bridge_port: int = 8002

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
    # NOTE: pii_redaction_enabled was removed (Plan 05-08). It now lives in system_settings
    # (migration 032) as a DB-backed admin-toggleable column. PII_REDACTION_ENABLED env var
    # is silently ignored (extra='ignore' in model_config). Clean it up from Railway env.
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
    llm_provider_fallback_enabled: bool = True  # Phase 6 D-P6-09: PERF-04 ships fallback ON by default
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

    # Phase 17 / v1.3 (DEEP-02, CONF-01..03; D-14 / D-15 / D-16):
    # Loop iteration caps for the Deep Mode branch + standard tool loop + sub-agent loop.
    # Env-driven (NOT system_settings) — these are deployment knobs, not user-runtime settings.
    max_deep_rounds: int = 50
    max_tool_rounds: int = 25
    max_sub_agent_rounds: int = 15

    # Phase 17 / v1.3 (DEEP-03; D-16):
    # Dark-launch feature flag. When False, the Deep Mode toggle is hidden in the UI,
    # the /chat endpoint rejects deep_mode=true payloads, and the codebase is byte-identical
    # to pre-Phase-17 (CONF-01 / DEEP-03 invariant). Mirrors TOOL_REGISTRY_ENABLED /
    # SANDBOX_ENABLED dark-launch precedent.
    deep_mode_enabled: bool = False

    # Phase 18 (WS-02, WS-06, WS-09; D-08, D-09): Workspace Virtual Filesystem feature flag.
    # When False: workspace tools NOT registered in tool registry, REST endpoints return 404,
    # SSE workspace_updated events not emitted. Default OFF — opt-in via WORKSPACE_ENABLED env var.
    workspace_enabled: bool = False

    # Phase 19 / v1.3 (TASK-*, ASK-*, STATUS-*; D-17): Sub-Agent Delegation feature flag.
    # When False: task and ask_user tools NOT registered, agent_runs unused, resume-detection
    # branch in /chat short-circuits, no task_*/agent_status SSE events emitted. Default OFF —
    # opt-in via SUB_AGENT_ENABLED env var. Mirrors WORKSPACE_ENABLED dark-launch precedent.
    sub_agent_enabled: bool = False

    @model_validator(mode="after")
    def _validate_local_embedding(self) -> "Settings":
        # CR-02 fix: catch EMBEDDING_PROVIDER=local + empty LOCAL_EMBEDDING_BASE_URL at startup.
        if self.embedding_provider == "local" and not self.local_embedding_base_url.strip():
            raise ValueError(
                "LOCAL_EMBEDDING_BASE_URL must be set when EMBEDDING_PROVIDER=local "
                "(e.g. 'http://localhost:11434/v1' for Ollama)"
            )
        return self

    @model_validator(mode="after")
    def _migrate_tools_max_iterations_alias(self) -> "Settings":
        # D-15 deprecation: TOOLS_MAX_ITERATIONS env still readable for one milestone.
        # If MAX_TOOL_ROUNDS not explicitly set (still equals default 25) BUT
        # TOOLS_MAX_ITERATIONS env was provided (and != legacy default 5),
        # back-fill max_tool_rounds and emit a deprecation warning.
        import os
        import warnings
        env_legacy = os.environ.get("TOOLS_MAX_ITERATIONS")
        env_new = os.environ.get("MAX_TOOL_ROUNDS")
        if env_legacy is not None and env_new is None:
            warnings.warn(
                "TOOLS_MAX_ITERATIONS is deprecated; set MAX_TOOL_ROUNDS instead. "
                "Falling back to TOOLS_MAX_ITERATIONS for this run (Phase 17 / D-15).",
                DeprecationWarning,
                stacklevel=2,
            )
            try:
                self.max_tool_rounds = int(env_legacy)
            except ValueError:
                pass
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
