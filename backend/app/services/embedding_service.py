from openai import AsyncOpenAI
from langsmith import traceable
from app.config import get_settings
from app.database import get_supabase_client

settings = get_settings()


class EmbeddingService:
    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_embedding_model

    @traceable
    async def embed_text(self, text: str, model: str | None = None) -> list[float]:
        response = await self.client.embeddings.create(
            model=model or self.model,
            input=text,
        )
        return response.data[0].embedding

    @traceable
    async def embed_batch(self, texts: list[str], model: str | None = None) -> list[list[float]]:
        response = await self.client.embeddings.create(
            model=model or self.model,
            input=texts,
        )
        # Sort by index to preserve order
        return [item.embedding for item in sorted(response.data, key=lambda x: x.index)]

    @traceable
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
