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
    # ----- Knowledge Base Exploration Tools -----
    {
        "type": "function",
        "function": {
            "name": "kb_list_files",
            "description": (
                "List documents and subfolders in a knowledge base folder (like 'ls'). "
                "Returns filenames, sizes, status, and subfolder names."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "folder_id": {
                        "type": "string",
                        "description": "UUID of the folder to list. Omit to list root-level items.",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "kb_tree",
            "description": (
                "Show the full folder structure as an indented tree with document counts "
                "per folder. Use to understand the knowledge base organization."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "max_depth": {
                        "type": "integer",
                        "description": "Maximum folder depth to display. Default 5.",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "kb_grep",
            "description": (
                "Search all document contents for a text pattern (regex supported). "
                "Returns matching chunks with surrounding context. Like 'grep'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Text or regex pattern to search for in document contents.",
                    },
                    "case_insensitive": {
                        "type": "boolean",
                        "description": "Case-insensitive search. Default true.",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Max matching chunks to return. Default 20.",
                    },
                },
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "kb_glob",
            "description": (
                "Find documents by filename pattern. Supports wildcards: "
                "* matches any characters, ? matches a single character. Like 'glob'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Filename glob pattern, e.g. '*.pdf', 'kontrak-*', 'laporan-??.docx'.",
                    },
                },
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "kb_read",
            "description": (
                "Read a document's content by assembling its stored chunks. "
                "Can read the full document or a specific chunk range for large documents. "
                "Max 20 chunks per call (~10,000 tokens)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "document_id": {
                        "type": "string",
                        "description": "UUID of the document to read.",
                    },
                    "filename": {
                        "type": "string",
                        "description": "Filename to read (alternative to document_id). Uses first match if multiple.",
                    },
                    "start_chunk": {
                        "type": "integer",
                        "description": "Starting chunk index (0-based). Default 0.",
                    },
                    "end_chunk": {
                        "type": "integer",
                        "description": "Ending chunk index (inclusive). Defaults to start_chunk + 19.",
                    },
                },
                "required": [],
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
        elif name == "kb_list_files":
            return await self._execute_kb_list_files(
                folder_id=arguments.get("folder_id"),
                user_id=user_id,
            )
        elif name == "kb_tree":
            return await self._execute_kb_tree(
                max_depth=arguments.get("max_depth", 5),
                user_id=user_id,
            )
        elif name == "kb_grep":
            return await self._execute_kb_grep(
                pattern=arguments.get("pattern", ""),
                case_insensitive=arguments.get("case_insensitive", True),
                max_results=arguments.get("max_results", 20),
                user_id=user_id,
            )
        elif name == "kb_glob":
            return await self._execute_kb_glob(
                pattern=arguments.get("pattern", ""),
                user_id=user_id,
            )
        elif name == "kb_read":
            return await self._execute_kb_read(
                document_id=arguments.get("document_id"),
                filename=arguments.get("filename"),
                start_chunk=arguments.get("start_chunk", 0),
                end_chunk=arguments.get("end_chunk"),
                user_id=user_id,
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

            # Log query + retrieved chunks for embedding fine-tuning data
            try:
                chunk_ids = [c["id"] for c in chunks if c.get("id")]
                chunk_scores = [
                    c.get("similarity") or c.get("rrf_score") or 0.0
                    for c in chunks if c.get("id")
                ]
                get_supabase_client().table("query_logs").insert({
                    "user_id": user_id,
                    "query": query,
                    "retrieved_ids": chunk_ids,
                    "retrieved_scores": chunk_scores,
                    "tool_name": "search_documents",
                }).execute()
            except Exception:
                pass  # fire-and-forget — never block search results

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

    # ── Knowledge Base Exploration Handlers ──────────────────────────

    @traceable(name="tool_kb_list_files")
    async def _execute_kb_list_files(self, folder_id: str | None, user_id: str) -> dict:
        """List subfolders and documents in a folder (like ls)."""
        try:
            client = get_supabase_client()

            # Subfolders
            folder_query = (
                client.table("document_folders")
                .select("id, name, created_at")
                .eq("user_id", user_id)
            )
            if folder_id:
                folder_query = folder_query.eq("parent_folder_id", folder_id)
            else:
                folder_query = folder_query.is_("parent_folder_id", "null")
            folders = folder_query.order("name").execute().data or []

            # Documents
            doc_query = (
                client.table("documents")
                .select("id, filename, file_size, mime_type, status, chunk_count, metadata")
                .eq("user_id", user_id)
            )
            if folder_id:
                doc_query = doc_query.eq("folder_id", folder_id)
            else:
                doc_query = doc_query.is_("folder_id", "null")
            docs = doc_query.order("filename").execute().data or []

            items = []
            for f in folders:
                items.append({"type": "folder", "name": f["name"], "id": f["id"]})
            for d in docs:
                meta = d.get("metadata") or {}
                items.append({
                    "type": "file",
                    "name": d["filename"],
                    "id": d["id"],
                    "size": d["file_size"],
                    "mime_type": d["mime_type"],
                    "status": d["status"],
                    "chunks": d["chunk_count"],
                    "category": meta.get("category", ""),
                })

            return {"items": items, "count": len(items), "folder_id": folder_id or "root"}
        except Exception as e:
            logger.error("kb_list_files failed: %s", e)
            return {"error": str(e), "items": [], "count": 0}

    @traceable(name="tool_kb_tree")
    async def _execute_kb_tree(self, max_depth: int, user_id: str) -> dict:
        """Return the folder tree structure (like tree)."""
        try:
            client = get_supabase_client()
            result = client.rpc(
                "get_folder_tree",
                {"p_user_id": user_id, "p_max_depth": min(max_depth, 10)},
            ).execute()
            tree_data = result.data or []

            # Count root-level documents
            root_docs = (
                client.table("documents")
                .select("id", count="exact")
                .eq("user_id", user_id)
                .is_("folder_id", "null")
                .execute()
            )
            root_doc_count = root_docs.count if root_docs.count is not None else 0

            # Format as indented tree string
            lines = [f"/ (root) [{root_doc_count} files]"]
            for row in tree_data:
                indent = "  " * (row["depth"] + 1)
                doc_count = row["document_count"]
                lines.append(f"{indent}{row['name']}/ [{doc_count} files]")

            # Truncate if too long
            if len(lines) > 100:
                lines = lines[:100]
                lines.append(f"... ({len(tree_data) + 1 - 100} more items truncated)")

            tree_str = "\n".join(lines)
            return {"tree": tree_str, "total_folders": len(tree_data), "root_documents": root_doc_count}
        except Exception as e:
            logger.error("kb_tree failed: %s", e)
            return {"error": str(e), "tree": "", "total_folders": 0}

    @traceable(name="tool_kb_grep")
    async def _execute_kb_grep(
        self, pattern: str, case_insensitive: bool, max_results: int, user_id: str,
    ) -> dict:
        """Search document chunk contents via POSIX regex (like grep)."""
        if not pattern:
            return {"error": "Pattern is required", "matches": [], "count": 0}
        try:
            client = get_supabase_client()
            result = client.rpc(
                "search_chunks_by_pattern",
                {
                    "p_user_id": user_id,
                    "p_pattern": pattern,
                    "p_case_insensitive": case_insensitive,
                    "p_max_results": min(max_results, 50),
                },
            ).execute()
            rows = result.data or []

            matches = []
            for row in rows:
                content = row["content"]
                # Extract a snippet around the match (first 300 chars)
                snippet = content[:300] + ("..." if len(content) > 300 else "")
                matches.append({
                    "filename": row["doc_filename"],
                    "chunk_index": row["chunk_index"],
                    "document_id": row["document_id"],
                    "snippet": snippet,
                })

            return {"matches": matches, "count": len(matches), "pattern": pattern}
        except Exception as e:
            error_msg = str(e)
            if "invalid regular expression" in error_msg.lower():
                return {"error": f"Invalid regex pattern: {pattern}", "matches": [], "count": 0}
            logger.error("kb_grep failed: %s", e)
            return {"error": error_msg, "matches": [], "count": 0}

    @traceable(name="tool_kb_glob")
    async def _execute_kb_glob(self, pattern: str, user_id: str) -> dict:
        """Find documents by filename pattern (like glob)."""
        if not pattern:
            return {"error": "Pattern is required", "files": [], "count": 0}
        try:
            # Convert glob to SQL LIKE: escape existing %, _ then convert * and ?
            sql_pattern = pattern.replace("%", r"\%").replace("_", r"\_")
            sql_pattern = sql_pattern.replace("*", "%").replace("?", "_")

            client = get_supabase_client()
            result = (
                client.table("documents")
                .select("id, filename, file_size, mime_type, status, chunk_count, folder_id, metadata")
                .eq("user_id", user_id)
                .ilike("filename", sql_pattern)
                .order("filename")
                .execute()
            )
            docs = result.data or []

            # Resolve folder paths for context
            folder_ids = {d["folder_id"] for d in docs if d.get("folder_id")}
            folder_paths = {}
            if folder_ids:
                tree = client.rpc(
                    "get_folder_tree",
                    {"p_user_id": user_id, "p_max_depth": 10},
                ).execute()
                for row in (tree.data or []):
                    folder_paths[row["id"]] = row["path"]

            files = []
            for d in docs:
                meta = d.get("metadata") or {}
                path = folder_paths.get(d["folder_id"], "/") if d.get("folder_id") else "/"
                files.append({
                    "filename": d["filename"],
                    "id": d["id"],
                    "path": path,
                    "size": d["file_size"],
                    "mime_type": d["mime_type"],
                    "status": d["status"],
                    "chunks": d["chunk_count"],
                    "category": meta.get("category", ""),
                })

            return {"files": files, "count": len(files), "pattern": pattern}
        except Exception as e:
            logger.error("kb_glob failed: %s", e)
            return {"error": str(e), "files": [], "count": 0}

    @traceable(name="tool_kb_read")
    async def _execute_kb_read(
        self,
        document_id: str | None,
        filename: str | None,
        start_chunk: int,
        end_chunk: int | None,
        user_id: str,
    ) -> dict:
        """Read a document's content from its chunks (like read/cat)."""
        try:
            client = get_supabase_client()

            # Resolve document
            if document_id:
                doc_result = (
                    client.table("documents")
                    .select("id, filename, chunk_count, status")
                    .eq("id", document_id)
                    .eq("user_id", user_id)
                    .limit(1)
                    .execute()
                )
            elif filename:
                doc_result = (
                    client.table("documents")
                    .select("id, filename, chunk_count, status")
                    .eq("user_id", user_id)
                    .ilike("filename", filename)
                    .limit(1)
                    .execute()
                )
            else:
                return {"error": "Provide document_id or filename"}

            if not doc_result.data:
                return {"error": "Document not found"}

            doc = doc_result.data[0]
            if doc["status"] != "completed":
                return {"error": f"Document is not ready (status: {doc['status']})"}

            total_chunks = doc["chunk_count"] or 0
            if total_chunks == 0:
                return {"error": "Document has no chunks", "filename": doc["filename"]}

            # Enforce 20-chunk cap
            max_chunks = 20
            start = max(0, start_chunk)
            end = end_chunk if end_chunk is not None else start + max_chunks - 1
            end = min(end, start + max_chunks - 1, total_chunks - 1)

            # Fetch chunks
            chunks_result = (
                client.table("document_chunks")
                .select("chunk_index, content")
                .eq("document_id", doc["id"])
                .eq("user_id", user_id)
                .gte("chunk_index", start)
                .lte("chunk_index", end)
                .order("chunk_index")
                .execute()
            )
            chunks = chunks_result.data or []

            content_parts = []
            for chunk in chunks:
                content_parts.append(chunk["content"])

            content = "\n".join(content_parts)
            has_more = end < total_chunks - 1

            return {
                "filename": doc["filename"],
                "document_id": doc["id"],
                "content": content,
                "chunk_range": f"{start}-{end}",
                "total_chunks": total_chunks,
                "has_more": has_more,
            }
        except Exception as e:
            logger.error("kb_read failed: %s", e)
            return {"error": str(e)}
