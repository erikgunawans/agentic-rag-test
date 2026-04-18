import json
import logging
import re
import httpx
from langsmith import traceable
from app.config import get_settings
from app.database import get_supabase_client
from app.services.hybrid_retrieval_service import HybridRetrievalService

logger = logging.getLogger(__name__)
settings = get_settings()

# SQL keywords that indicate a write operation
_WRITE_KEYWORDS = re.compile(
    r"\b(insert|update|delete|drop|alter|create|truncate|grant|revoke|execute)\b",
    re.IGNORECASE,
)

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "search_documents",
            "description": (
                "Search the user's uploaded documents for relevant information. "
                "Use this when the user asks about content in their documents."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query to find relevant document chunks",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_database",
            "description": (
                "Query structured metadata about the user's documents. Use this to answer "
                "questions like 'how many documents do I have?', 'which documents are about X "
                "category?', 'what are my largest files?', etc. "
                "Schema: documents(id uuid, filename text, file_size int, mime_type text, "
                "status text, chunk_count int, created_at timestamptz, "
                "metadata->>'title' text, metadata->>'author' text, "
                "metadata->>'category' text, metadata->>'tags' text, "
                "metadata->>'summary' text, metadata->>'date_period' text). "
                "Always include WHERE user_id = :user_id in your query."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "sql_query": {
                        "type": "string",
                        "description": (
                            "A read-only SELECT query against the documents table. "
                            "MUST include WHERE user_id = :user_id filter. Only SELECT is allowed."
                        ),
                    }
                },
                "required": ["sql_query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": (
                "Search the web for current information. Use this as a fallback when "
                "the user's documents don't contain the answer, or when the question is "
                "about current events, general knowledge, or topics not covered in their documents."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Web search query",
                    }
                },
                "required": ["query"],
            },
        },
    },
]


class ToolService:
    def __init__(self):
        self.hybrid_service = HybridRetrievalService()

    def get_available_tools(self) -> list[dict]:
        """Return tool definitions, filtering out web_search if no Tavily key."""
        tools = []
        for tool in TOOL_DEFINITIONS:
            if tool["function"]["name"] == "web_search" and not settings.tavily_api_key:
                continue
            tools.append(tool)
        return tools

    @traceable(name="execute_tool")
    async def execute_tool(
        self,
        name: str,
        arguments: dict,
        user_id: str,
        context: dict | None = None,
    ) -> dict:
        """Dispatch tool execution by name."""
        if name == "search_documents":
            return await self._execute_search_documents(
                query=arguments.get("query", ""),
                user_id=user_id,
                context=context or {},
            )
        elif name == "query_database":
            return await self._execute_query_database(
                sql_query=arguments.get("sql_query", ""),
                user_id=user_id,
            )
        elif name == "web_search":
            return await self._execute_web_search(
                query=arguments.get("query", ""),
            )
        else:
            return {"error": f"Unknown tool: {name}"}

    @traceable(name="tool_search_documents")
    async def _execute_search_documents(
        self, query: str, user_id: str, context: dict
    ) -> dict:
        """Search user's documents via hybrid retrieval."""
        try:
            chunks = await self.hybrid_service.retrieve(
                query=query,
                user_id=user_id,
                top_k=context.get("top_k", settings.rag_top_k),
                threshold=context.get("threshold", settings.rag_similarity_threshold),
                embedding_model=context.get("embedding_model"),
                llm_model=context.get("llm_model"),
                category=context.get("category"),
            )
            results = []
            for chunk in chunks:
                meta = chunk.get("doc_metadata") or {}
                item = {
                    "content": chunk["content"],
                    "filename": chunk.get("doc_filename", ""),
                    "category": meta.get("category", ""),
                    "tags": meta.get("tags", []),
                }
                if chunk.get("surrounding_context"):
                    item["surrounding_context"] = chunk["surrounding_context"]
                if chunk.get("graph_context"):
                    item["graph_context"] = chunk["graph_context"]
                results.append(item)
            return {"chunks": results, "count": len(results)}
        except Exception as e:
            logger.error("search_documents failed: %s", e)
            return {"error": str(e), "chunks": [], "count": 0}

    @traceable(name="tool_query_database")
    async def _execute_query_database(self, sql_query: str, user_id: str) -> dict:
        """Execute a read-only SQL query scoped to the user's documents."""
        sql_stripped = sql_query.strip()

        # Validate: must start with SELECT
        if not sql_stripped.lower().startswith("select"):
            return {"error": "Only SELECT queries are allowed"}

        # Validate: reject write keywords
        if _WRITE_KEYWORDS.search(sql_stripped):
            return {"error": "Write operations are not allowed"}

        # Validate: must reference user_id for scoping
        if ":user_id" not in sql_stripped and "user_id" not in sql_stripped.lower():
            return {"error": "Query must include user_id filter for security"}

        try:
            client = get_supabase_client()
            result = client.rpc(
                "execute_user_document_query",
                {"query_text": sql_stripped, "query_user_id": user_id},
            ).execute()
            rows = result.data if result.data else []
            return {"rows": rows, "count": len(rows) if isinstance(rows, list) else 0, "query": sql_stripped}
        except Exception as e:
            logger.error("query_database failed: %s", e)
            return {"error": str(e), "rows": [], "count": 0}

    @traceable(name="tool_web_search")
    async def _execute_web_search(self, query: str) -> dict:
        """Search the web via Tavily API."""
        if not settings.tavily_api_key:
            return {"error": "Web search not configured", "results": [], "count": 0}

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    "https://api.tavily.com/search",
                    json={
                        "api_key": settings.tavily_api_key,
                        "query": query,
                        "max_results": 5,
                    },
                    timeout=15,
                )
                resp.raise_for_status()
                data = resp.json()
                results = [
                    {
                        "title": r.get("title", ""),
                        "url": r.get("url", ""),
                        "content": r.get("content", ""),
                    }
                    for r in data.get("results", [])
                ]
                return {"results": results, "count": len(results)}
        except Exception as e:
            logger.error("web_search failed: %s", e)
            return {"error": str(e), "results": [], "count": 0}
