from openai import AsyncOpenAI
from app.services.tracing_service import traced
from app.config import get_settings
from app.database import get_supabase_client

settings = get_settings()


class EmbeddingService:
    def __init__(self):
        # Phase 6 D-P6-02 / EMBED-01 / EMBED-02: provider branch.
        # cloud (default) preserves the existing OpenAI flow exactly (RAG-02 unchanged).
        # local uses an OpenAI-API-compatible endpoint (Ollama bge-m3 / LM Studio) — no third-party egress.
        # Pattern mirrors LLMProviderClient._get_client (Phase 3 D-50): same AsyncOpenAI library,
        # same chat-completions-style API surface, deployer-supplied base_url for local.
        if settings.embedding_provider == "local":
            self.client = AsyncOpenAI(
                base_url=settings.local_embedding_base_url,
                api_key="not-needed",  # Ollama / LM Studio require no key
            )
        else:
            # cloud (default) — RAG-02 preserved byte-identically
            self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_embedding_model

    @traced
    async def embed_text(self, text: str, model: str | None = None) -> list[float]:
        response = await self.client.embeddings.create(
            model=model or self.model,
            input=text,
        )
        return response.data[0].embedding

    @traced
    async def embed_batch(self, texts: list[str], model: str | None = None) -> list[list[float]]:
        response = await self.client.embeddings.create(
            model=model or self.model,
            input=texts,
        )
        # Sort by index to preserve order
        return [item.embedding for item in sorted(response.data, key=lambda x: x.index)]

    @traced
    async def retrieve_chunks(
        self,
        query: str,
        user_id: str,
        top_k: int,
        threshold: float,
        model: str | None = None,
    ) -> list[str]:
        """Embed query and return top-k similar chunk contents via pgvector RPC."""
        embedding = await self.embed_text(query, model=model)
        result = get_supabase_client().rpc(
            "match_document_chunks",
            {
                "query_embedding": embedding,
                "match_user_id": user_id,
                "match_count": top_k,
                "match_threshold": threshold,
            },
        ).execute()
        return [row["content"] for row in (result.data or [])]

    @traced
    async def retrieve_chunks_with_metadata(
        self,
        query: str,
        user_id: str,
        top_k: int,
        threshold: float,
        model: str | None = None,
        category: str | None = None,
        filter_tags: list[str] | None = None,
        filter_folder_id: str | None = None,
        filter_date_from: str | None = None,
        filter_date_to: str | None = None,
    ) -> list[dict]:
        """Embed query and return top-k chunks with document metadata via pgvector RPC."""
        embedding = await self.embed_text(query, model=model)
        params: dict = {
            "query_embedding": embedding,
            "match_user_id": user_id,
            "match_count": top_k,
            "match_threshold": threshold,
            "filter_category": category,
        }
        if filter_tags:
            params["filter_tags"] = filter_tags
        if filter_folder_id:
            params["filter_folder_id"] = filter_folder_id
        if filter_date_from:
            params["filter_date_from"] = filter_date_from
        if filter_date_to:
            params["filter_date_to"] = filter_date_to
        result = get_supabase_client().rpc(
            "match_document_chunks_with_metadata", params,
        ).execute()
        return result.data or []
