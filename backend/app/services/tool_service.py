import json
import logging
import re
from typing import TYPE_CHECKING, Callable

import httpx

from app.services.tracing_service import traced
from app.config import get_settings
from app.database import get_supabase_authed_client, get_supabase_client
from app.services.audit_service import log_action
from app.services.hybrid_retrieval_service import HybridRetrievalService
from app.services.sandbox_service import get_sandbox_service  # Phase 10 D-P10-05
from postgrest.exceptions import APIError as PostgrestAPIError

if TYPE_CHECKING:
    # Phase 5 D-86 / D-91: ConversationRegistry is referenced ONLY in the
    # `execute_tool` keyword-only annotation as a string forward-ref. The
    # runtime import is gated under TYPE_CHECKING to avoid the circular
    # import chain `tool_service -> redaction -> ... -> tool_service`.
    from app.services.redaction.registry import ConversationRegistry

logger = logging.getLogger(__name__)
settings = get_settings()

# SQL keywords that indicate a write operation
_WRITE_KEYWORDS = re.compile(
    r"\b(insert|update|delete|drop|alter|create|truncate|grant|revoke|execute)\b",
    re.IGNORECASE,
)

# Phase 8: Skill name format (D-P8-09) — must match ^[a-z][a-z0-9]*(-[a-z0-9]+)*$
_SKILL_NAME_REGEX = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")

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
                    },
                    "filter_tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Filter by document tags (e.g., ['kontrak', 'peraturan']). Only return chunks from documents with ANY of these tags.",
                    },
                    "filter_folder_id": {
                        "type": "string",
                        "description": "Filter by folder UUID. Only return chunks from documents in this folder.",
                    },
                    "filter_date_from": {
                        "type": "string",
                        "description": "Filter by document date (ISO 8601). Only return documents created on or after this date.",
                    },
                    "filter_date_to": {
                        "type": "string",
                        "description": "Filter by document date (ISO 8601). Only return documents created on or before this date.",
                    },
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
    # ── Phase 8: Agent Skills tools (D-P8-04 unconditional) ───────────────
    {
        "type": "function",
        "function": {
            "name": "load_skill",
            "description": (
                "Load the full instructions and attached files for an enabled skill by name. "
                "Use this when the user's request clearly matches a skill description shown "
                "in the '## Your Skills' system block. Only call when the match is strong."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Skill name (lowercase-hyphenated identifier, e.g. 'legal-review').",
                    },
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_skill",
            "description": (
                "Persist a new skill to the user's library, or update an existing one when "
                "update=true and skill_id is provided. After collaborating with the user on "
                "name/description/instructions via the skill-creator skill, call save_skill "
                "to commit. On a name_conflict error, resend with update=true + the "
                "existing_skill_id from the error to overwrite."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "lowercase-hyphenated identifier, max 64 chars (regex ^[a-z][a-z0-9]*(-[a-z0-9]+)*$).",
                    },
                    "description": {
                        "type": "string",
                        "description": "20-1024 chars, third-person, what-it-does + when-to-use.",
                    },
                    "instructions": {
                        "type": "string",
                        "description": "Free-form markdown — context the LLM doesn't already know.",
                    },
                    "update": {
                        "type": "boolean",
                        "description": "When true, update the skill identified by skill_id instead of creating new. Default false.",
                    },
                    "skill_id": {
                        "type": "string",
                        "description": "Required when update=true. UUID of the skill to update.",
                    },
                },
                "required": ["name", "description", "instructions"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_skill_file",
            "description": (
                "Read the content of a file attached to a skill. Text files are returned "
                "inline capped at 8000 chars; binary files return metadata only. Use the "
                "skill_id and filename from the load_skill response."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "skill_id": {
                        "type": "string",
                        "description": "UUID of the skill the file belongs to.",
                    },
                    "filename": {
                        "type": "string",
                        "description": "Flat filename as returned by load_skill (e.g. 'legal-clauses.md' or 'scripts__foo.py').",
                    },
                },
                "required": ["skill_id", "filename"],
            },
        },
    },
    # ── Phase 10: Code Execution Sandbox tool (D-P10-05/07; SANDBOX-01/05/06; gated) ──
    {
        "type": "function",
        "function": {
            "name": "execute_code",
            "description": (
                "Execute Python code in a sandboxed Docker container. "
                "Variables persist across calls within the same conversation thread. "
                "Use for data analysis, calculations, file generation (write to /sandbox/output/), "
                "or any task requiring runtime computation. The response includes stdout, stderr, "
                "exit_code, and signed URLs for any files written to /sandbox/output/."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Python code to execute. Use stdout for results.",
                    },
                    "description": {
                        "type": "string",
                        "description": "Brief description of what this code does (for execution log).",
                    },
                },
                "required": ["code"],
            },
        },
    },
]


def _name_conflict_response(client, name: str, user_id: str) -> dict:
    """D-P8-08: return existing_skill_id so the LLM can retry with update=true."""
    existing_id = None
    try:
        existing = (
            client.table("skills")
            .select("id")
            .eq("name", name)
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        if existing.data:
            existing_id = str(existing.data[0]["id"])
    except Exception:
        pass
    return {
        "error": "name_conflict",
        "message": f"Skill '{name}' already exists.",
        "existing_skill_id": existing_id,
        "hint": "Use a different name, or resend with update=true and skill_id=<existing_id> to update.",
    }


class ToolService:
    def __init__(self):
        self.hybrid_service = HybridRetrievalService()

    def get_available_tools(self, *, web_search_enabled: bool = True) -> list[dict]:
        """Return tool definitions visible to the LLM for this request.

        ADR-0008: when web_search_enabled=False, the web_search tool is
        excluded from the catalog so the agent classifier and dispatcher
        never see it. The existing tavily_api_key check is preserved.

        Phase 10 SANDBOX-05: execute_code is excluded when settings.sandbox_enabled
        is False. Default OFF — opt-in per Railway env (config.py D-P10).
        """
        tools = []
        for tool in TOOL_DEFINITIONS:
            name = tool["function"]["name"]
            if name == "web_search":
                if not web_search_enabled:
                    continue
                if not settings.tavily_api_key:
                    continue
            elif name == "execute_code":
                if not settings.sandbox_enabled:
                    continue
            tools.append(tool)
        return tools

    @traced(name="execute_tool")
    async def execute_tool(
        self,
        name: str,
        arguments: dict,
        user_id: str,
        context: dict | None = None,
        *,
        registry: "ConversationRegistry | None" = None,  # Phase 5 D-86 / D-91
        token: str | None = None,                        # Phase 8: RLS-scoped DB access for skill tools
        stream_callback: Callable | None = None,         # Phase 10 D-P10-05 — used ONLY by execute_code branch
    ) -> dict:
        """Dispatch tool execution by name.

        Phase 5 D-86: Accepts an optional ``registry: ConversationRegistry``
        keyword arg from the chat router for symmetry with the centralized
        walker in ``app.services.redaction.tool_redaction`` (D-91). The
        walker invokes ``deanonymize_tool_args`` BEFORE / ``anonymize_tool_output``
        AFTER this method; this method itself is redaction-unaware and the
        dispatch switch body is byte-identical to Phase 4 (the parameter is
        received but NOT used here — that's the whole point of D-91).

        Phase 8: Accepts an optional ``token: str`` keyword arg so skill tools
        (load_skill, save_skill, read_skill_file) can call
        ``get_supabase_authed_client(token)`` for RLS-scoped DB access.
        Other tools ignore this kwarg — they continue to use service-role +
        explicit user_id predicates.

        Phase 10 D-P10-05: Accepts an optional ``stream_callback`` kwarg used
        ONLY by the execute_code branch to emit code_stdout/code_stderr SSE
        events line-by-line during sandbox execution. Other tools accept and
        silently ignore this parameter (parameter received, never invoked).
        """
        if name == "search_documents":
            return await self._execute_search_documents(
                query=arguments.get("query", ""),
                user_id=user_id,
                context=context or {},
                filter_tags=arguments.get("filter_tags"),
                filter_folder_id=arguments.get("filter_folder_id"),
                filter_date_from=arguments.get("filter_date_from"),
                filter_date_to=arguments.get("filter_date_to"),
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
        elif name == "load_skill":
            return await self._execute_load_skill(
                skill_name=arguments.get("name", ""),
                user_id=user_id,
                token=token,
            )
        elif name == "save_skill":
            return await self._execute_save_skill(
                name=arguments.get("name", ""),
                description=arguments.get("description", ""),
                instructions=arguments.get("instructions", ""),
                update=bool(arguments.get("update", False)),
                skill_id=arguments.get("skill_id"),
                user_id=user_id,
                token=token,
            )
        elif name == "read_skill_file":
            return await self._execute_read_skill_file(
                skill_id=arguments.get("skill_id", ""),
                filename=arguments.get("filename", ""),
                user_id=user_id,
                token=token,
            )
        elif name == "execute_code":
            return await self._execute_code(
                code=arguments.get("code", ""),
                description=arguments.get("description"),
                user_id=user_id,
                thread_id=(context or {}).get("thread_id"),
                stream_callback=stream_callback,
            )
        else:
            return {"error": f"Unknown tool: {name}"}

    @traced(name="tool_search_documents")
    async def _execute_search_documents(
        self,
        query: str,
        user_id: str,
        context: dict,
        filter_tags: list[str] | None = None,
        filter_folder_id: str | None = None,
        filter_date_from: str | None = None,
        filter_date_to: str | None = None,
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
                filter_tags=filter_tags,
                filter_folder_id=filter_folder_id,
                filter_date_from=filter_date_from,
                filter_date_to=filter_date_to,
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

    @traced(name="tool_query_database")
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

    @traced(name="tool_web_search")
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

    @traced(name="tool_kb_list_files")
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

    @traced(name="tool_kb_tree")
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

    @traced(name="tool_kb_grep")
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

    @traced(name="tool_kb_glob")
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

    @traced(name="tool_kb_read")
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

    # ── Phase 8: Agent Skills tool handlers ──────────────────────────

    @traced(name="tool_load_skill")
    async def _execute_load_skill(
        self, *, skill_name: str, user_id: str, token: str | None
    ) -> dict:
        """SKILL-08 / SFILE-02: return full skill + attached files table."""
        if not token:
            return {
                "error": "auth_required",
                "message": "Cannot load skill without authenticated session.",
            }
        if not skill_name:
            return {"error": "missing_name", "message": "name is required."}
        client = get_supabase_authed_client(token)
        # RLS auto-filters: own skills + global skills
        try:
            result = (
                client.table("skills")
                .select("id, name, description, instructions, enabled")
                .eq("name", skill_name)
                .eq("enabled", True)
                .limit(1)
                .execute()
            )
        except Exception as e:
            logger.warning("load_skill query failed: %s", e)
            return {"error": "db_error", "message": str(e)}
        rows = result.data or []
        if not rows:
            return {
                "error": "skill_not_found",
                "message": f"Skill '{skill_name}' not found or not enabled.",
                "name": skill_name,
            }
        skill = rows[0]
        try:
            files_result = (
                client.table("skill_files")
                .select("filename, size_bytes, mime_type")
                .eq("skill_id", skill["id"])
                .execute()
            )
            files = [
                {
                    "filename": f["filename"],
                    "size_bytes": f["size_bytes"],
                    "mime_type": f.get("mime_type") or "application/octet-stream",
                }
                for f in (files_result.data or [])
            ]
        except Exception as e:
            logger.warning("load_skill files query failed: %s", e)
            files = []
        return {
            "name": skill["name"],
            "description": skill["description"],
            "instructions": skill["instructions"],
            "files": files,
        }

    @traced(name="tool_save_skill")
    async def _execute_save_skill(
        self,
        *,
        name: str,
        description: str,
        instructions: str,
        update: bool,
        skill_id: str | None,
        user_id: str,
        token: str | None,
    ) -> dict:
        """SKILL-09: persist a new skill or update an existing one (D-P8-08..D-P8-10)."""
        if not token:
            return {
                "error": "auth_required",
                "message": "Cannot save skill without authenticated session.",
            }
        if not _SKILL_NAME_REGEX.match(name or ""):
            return {
                "error": "invalid_name",
                "message": "name must match ^[a-z][a-z0-9]*(-[a-z0-9]+)*$ (max 64 chars).",
            }
        if len(description or "") < 20 or len(description) > 1024:
            return {
                "error": "invalid_description",
                "message": "description must be 20-1024 characters.",
            }
        if not instructions:
            return {
                "error": "invalid_instructions",
                "message": "instructions is required.",
            }

        if update and not skill_id:
            return {
                "error": "missing_skill_id",
                "message": "skill_id is required when update=true.",
            }

        client = get_supabase_authed_client(token)

        if update:
            # RLS gates: UPDATE policy requires user_id = auth.uid() (D-P7-05)
            try:
                upd = (
                    client.table("skills")
                    .update({
                        "name": name,
                        "description": description,
                        "instructions": instructions,
                    })
                    .eq("id", skill_id)
                    .execute()
                )
            except PostgrestAPIError as exc:
                if exc.code == "23505":
                    return _name_conflict_response(client, name, user_id)
                return {"error": "db_error", "message": str(exc.message)}
            if not upd.data:
                return {
                    "error": "skill_not_found",
                    "message": "Skill not found or not editable.",
                    "skill_id": skill_id,
                }
            row = upd.data[0]
            try:
                log_action(
                    user_id=user_id,
                    user_email=None,
                    action="update",
                    resource_type="skill",
                    resource_id=str(row["id"]),
                    details={"via": "llm_tool"},
                )
            except Exception:
                pass
            return {
                "skill_id": str(row["id"]),
                "name": row["name"],
                "description": row["description"],
                "instructions": row["instructions"],
                "enabled": row["enabled"],
                "message": "Skill saved successfully.",
            }

        # Create branch
        try:
            ins = client.table("skills").insert({
                "user_id": user_id,
                "created_by": user_id,
                "name": name,
                "description": description,
                "instructions": instructions,
                "enabled": True,
                "metadata": {},
            }).execute()
        except PostgrestAPIError as exc:
            if exc.code == "23505":
                return _name_conflict_response(client, name, user_id)
            return {"error": "db_error", "message": str(exc.message)}
        if not ins.data:
            return {"error": "db_error", "message": "Insert returned no data."}
        row = ins.data[0]
        try:
            log_action(
                user_id=user_id,
                user_email=None,
                action="create",
                resource_type="skill",
                resource_id=str(row["id"]),
                details={"via": "llm_tool"},
            )
        except Exception:
            pass
        return {
            "skill_id": str(row["id"]),
            "name": row["name"],
            "description": row["description"],
            "instructions": row["instructions"],
            "enabled": row["enabled"],
            "message": "Skill saved successfully.",
        }

    @traced(name="tool_read_skill_file")
    async def _execute_read_skill_file(
        self, *, skill_id: str, filename: str, user_id: str, token: str | None
    ) -> dict:
        """SFILE-03: text inline (≤8000 chars) or binary metadata (D-P8-11/12/13)."""
        if not token:
            return {
                "error": "auth_required",
                "message": "Cannot read skill file without authenticated session.",
            }
        if not skill_id or not filename:
            return {
                "error": "missing_args",
                "message": "skill_id and filename are required.",
            }
        client = get_supabase_authed_client(token)
        try:
            row = (
                client.table("skill_files")
                .select("filename, mime_type, size_bytes, storage_path")
                .eq("skill_id", skill_id)
                .eq("filename", filename)
                .limit(1)
                .execute()
            )
        except Exception as e:
            logger.warning("read_skill_file query failed: %s", e)
            return {"error": "db_error", "message": str(e)}
        if not row.data:
            return {
                "error": "file_not_found",
                "message": f"File '{filename}' not found in skill.",
                "skill_id": skill_id,
                "filename": filename,
            }
        f = row.data[0]
        mime = f.get("mime_type") or "application/octet-stream"
        # D-P8-13: binary → metadata only, no content, no signed URL
        if not mime.startswith("text/"):
            return {
                "filename": f["filename"],
                "mime_type": mime,
                "size_bytes": f["size_bytes"],
                "readable": False,
                "message": "Binary file — cannot display inline. Available as a skill resource.",
            }
        # D-P8-12: text → inline capped at 8000 chars
        # Try RLS-scoped download first; fall back to service-role for globally-shared
        # skill files whose storage path starts with the creator's user_id (D-P7-07).
        try:
            raw = client.storage.from_("skills-files").download(f["storage_path"])
        except Exception:
            # service-role fallback: required for globally-shared skill files per D-P7-07
            try:
                svc = get_supabase_client()
                raw = svc.storage.from_("skills-files").download(f["storage_path"])
            except Exception as e:
                logger.warning("read_skill_file download failed: %s", e)
                return {"error": "download_failed", "message": str(e)}
        text = raw.decode("utf-8", errors="replace")
        truncated = len(text) > 8000
        return {
            "filename": f["filename"],
            "content": text[:8000],
            "truncated": truncated,
            "total_bytes": f["size_bytes"],
            "message": "Content truncated at 8000 chars." if truncated else None,
        }

    # ── Phase 10: Code Execution Sandbox handler ─────────────────────────────

    @traced(name="tool_execute_code")
    async def _execute_code(
        self,
        *,
        code: str,
        description: str | None,
        user_id: str,
        thread_id: str | None,
        stream_callback: Callable | None,
    ) -> dict:
        """SANDBOX-01/02/04/06: dispatch to SandboxService, persist log, emit audit.

        Returns a dict shaped per D-P10-07 — full stdout + stderr + signed URLs +
        exit_code + error_type — so the LLM can reference specific values.

        T-10-25: early-return if thread_id is absent to avoid orphan code_executions
        rows and surface wiring bugs in chat.py (Plan 05 plumbs context['thread_id']).
        """
        if not code:
            return {"error": "missing_code", "message": "code is required."}
        if not thread_id:
            # context.thread_id is plumbed by chat.py in Plan 05; failing fast here
            # surfaces wiring bugs early rather than producing orphan code_executions rows.
            return {
                "error": "missing_thread_id",
                "message": "thread_id is required in context (chat.py must set context['thread_id']).",
            }

        # Phase 14 / BRIDGE-04 (D-P14-04): prepend stub import so LLM-generated code
        # can call platform tools as typed Python functions via the bridge.
        # `from stubs import *` is a no-op if /sandbox/stubs.py doesn't exist (e.g.,
        # bridge is inactive or container restarted), so this is safe to always add
        # when bridge is potentially active.
        _exec_settings = get_settings()
        _bridge_active = _exec_settings.sandbox_enabled and _exec_settings.tool_registry_enabled
        if _bridge_active and not code.startswith("from stubs import"):
            code = "from stubs import *\n" + code

        # Run in sandbox
        try:
            result = await get_sandbox_service().execute(
                code=code,
                thread_id=thread_id,
                user_id=user_id,
                stream_callback=stream_callback,
            )
        except Exception as exc:
            logger.error("execute_code sandbox dispatch failed: %s", exc, exc_info=True)
            return {
                "error": "sandbox_error",
                "message": str(exc),
                "stdout": "",
                "stderr": str(exc),
                "exit_code": -1,
                "files": [],
            }

        # Map sandbox output to status field for code_executions row
        if result.get("error_type") == "timeout":
            status = "timeout"
        elif result.get("exit_code", 0) != 0 or result.get("error_type"):
            status = "error"
        else:
            status = "success"

        execution_id = result.get("execution_id")

        # SANDBOX-06: persist row (service-role; RLS auto-passes own-row INSERT)
        try:
            client = get_supabase_client()
            client.table("code_executions").insert({
                "id": execution_id,
                "user_id": user_id,
                "thread_id": thread_id,
                "code": code,
                "description": description,
                "stdout": result.get("stdout", ""),
                "stderr": result.get("stderr", ""),
                "exit_code": result.get("exit_code", 0),
                "execution_ms": result.get("execution_ms", 0),
                "status": status,
                "files": result.get("files", []),
            }).execute()
        except Exception as exc:
            logger.warning("code_executions insert failed: %s", exc)
            # Continue — don't fail the tool call because logging failed.

        # Audit trail (mirror Phase 8 CR-01 fix at lines 1001–1011)
        try:
            log_action(
                user_id=user_id,
                user_email=None,
                action="execute_code",
                resource_type="code_execution",
                resource_id=str(execution_id) if execution_id else None,
                details={
                    "thread_id": thread_id,
                    "exit_code": result.get("exit_code", 0),
                    "status": status,
                },
            )
        except Exception:
            pass  # audit is fire-and-forget per chat.py line 327 pattern

        # D-P10-07: return full payload to the LLM (stdout + stderr + URLs + exit_code)
        return {
            "execution_id": execution_id,
            "stdout": result.get("stdout", ""),
            "stderr": result.get("stderr", ""),
            "exit_code": result.get("exit_code", 0),
            "error_type": result.get("error_type"),
            "execution_ms": result.get("execution_ms", 0),
            "files": result.get("files", []),
            "status": status,
        }


# ---------------------------------------------------------------------------
# Phase 13 D-P13-01 adapter wrap (TOOL-04, TOOL-05).
#
# Register every native TOOL_DEFINITIONS entry with the unified registry as
# source="native", loading="immediate". The executor is a thin closure that
# delegates back into ToolService.execute_tool — no logic is re-implemented
# here. When settings.tool_registry_enabled is False, this function is a
# no-op AND tool_registry is never imported (TOOL-05 byte-identical fallback).
# ---------------------------------------------------------------------------
def _register_natives_with_registry() -> None:
    """D-P13-01: enumerate TOOL_DEFINITIONS once and register each as a native tool.

    Idempotent on a clean registry. If the registry already has an entry for
    a given name, register() logs a WARNING and skips (first-write-wins).
    Gated by settings.tool_registry_enabled — early return when False so
    neither the registry module nor the closures are instantiated on flag-off
    deployments (TOOL-05 invariant).
    """
    if not settings.tool_registry_enabled:
        return
    # Lazy import: the registry module must NOT be imported when the flag is
    # off (TOOL-05 byte-identical fallback). Verified by test_no_import_when_flag_off.
    from app.services import tool_registry

    # Module-local ToolService instance for executor delegation. chat.py owns
    # its own `tool_service` singleton (chat.py:207); registry executors use a
    # private instance so registration happens at import time without depending
    # on the chat.py instantiation order (Plan 13-05 wiring).
    _svc = ToolService()

    for tool in TOOL_DEFINITIONS:
        fn = tool["function"]
        name = fn["name"]
        description = fn.get("description", "")

        # Closure captures `name` via default-arg binding so each closure
        # holds its own tool name (avoids late-binding bug on the loop var).
        async def _executor(
            arguments: dict,
            user_id: str,
            context: dict | None = None,
            *,
            _name: str = name,
            **kwargs,
        ) -> dict | str:
            return await _svc.execute_tool(
                _name, arguments, user_id, context, **kwargs
            )

        tool_registry.register(
            name=name,
            description=description,
            schema=tool,  # full top-level dict, includes type=function
            source="native",
            loading="immediate",
            executor=_executor,
        )


# Run the adapter wrap at module load. No-op when flag is off.
_register_natives_with_registry()


# ---------------------------------------------------------------------------
# Phase 18 / WS-02, WS-06 — workspace tool registration (D-07, D-08).
#
# Register write_file, read_file, edit_file, list_files as native tools
# through the unified Tool Registry (D-P13-01 pattern).
#
# Gated by settings.workspace_enabled (D-08 kill-switch). When False, none
# of the four tools are registered — they remain unreachable through any
# dispatch path. When True, all four register as source='native',
# loading='immediate'.
#
# Executor signature follows the registry dispatcher shape from chat.py:
#   executor(arguments, user_id, context, *, token=None, ...)
#   - arguments: LLM-supplied tool params dict
#   - user_id: authed user's UUID (from get_current_user)
#   - context: per-request dict with thread_id, user_email, token, etc.
#   - token: JWT passed as kwarg by chat.py's _dispatch_tool
#
# T-18-12: thread_id is read from ctx (server-set), NEVER from LLM params.
# T-18-12: WorkspaceService uses get_supabase_authed_client(token) → RLS.
# ---------------------------------------------------------------------------

async def _workspace_write_file_executor(
    arguments: dict,
    user_id: str,
    context: dict | None = None,
    *,
    token: str | None = None,
    **kwargs,
) -> dict:
    """Executor: write_file → WorkspaceService.write_text_file.

    thread_id is server-set from context (T-18-12). source hardcoded to
    'agent' so the LLM cannot influence the source discriminator (T-18-14).
    """
    from app.services.workspace_service import WorkspaceService  # noqa: PLC0415

    ctx = context or {}
    thread_id = ctx.get("thread_id") or ""
    resolved_token = token or ctx.get("token") or ""
    file_path = arguments.get("file_path", "")
    content = arguments.get("content", "")

    if not thread_id:
        return {
            "error": "missing_thread_id",
            "message": "thread_id is required in context (chat.py must set context['thread_id']).",
        }

    ws = WorkspaceService(token=resolved_token)
    return await ws.write_text_file(thread_id, file_path, content, source="agent")


async def _workspace_read_file_executor(
    arguments: dict,
    user_id: str,
    context: dict | None = None,
    *,
    token: str | None = None,
    **kwargs,
) -> dict:
    """Executor: read_file → WorkspaceService.read_file."""
    from app.services.workspace_service import WorkspaceService  # noqa: PLC0415

    ctx = context or {}
    thread_id = ctx.get("thread_id") or ""
    resolved_token = token or ctx.get("token") or ""
    file_path = arguments.get("file_path", "")

    if not thread_id:
        return {
            "error": "missing_thread_id",
            "message": "thread_id is required in context (chat.py must set context['thread_id']).",
        }

    ws = WorkspaceService(token=resolved_token)
    return await ws.read_file(thread_id, file_path)


async def _workspace_edit_file_executor(
    arguments: dict,
    user_id: str,
    context: dict | None = None,
    *,
    token: str | None = None,
    **kwargs,
) -> dict:
    """Executor: edit_file → WorkspaceService.edit_file."""
    from app.services.workspace_service import WorkspaceService  # noqa: PLC0415

    ctx = context or {}
    thread_id = ctx.get("thread_id") or ""
    resolved_token = token or ctx.get("token") or ""
    file_path = arguments.get("file_path", "")
    old_string = arguments.get("old_string", "")
    new_string = arguments.get("new_string", "")

    if not thread_id:
        return {
            "error": "missing_thread_id",
            "message": "thread_id is required in context (chat.py must set context['thread_id']).",
        }

    ws = WorkspaceService(token=resolved_token)
    return await ws.edit_file(thread_id, file_path, old_string, new_string)


async def _workspace_list_files_executor(
    arguments: dict,
    user_id: str,
    context: dict | None = None,
    *,
    token: str | None = None,
    **kwargs,
) -> dict:
    """Executor: list_files → WorkspaceService.list_files."""
    from app.services.workspace_service import WorkspaceService  # noqa: PLC0415

    ctx = context or {}
    thread_id = ctx.get("thread_id") or ""
    resolved_token = token or ctx.get("token") or ""

    if not thread_id:
        return {
            "error": "missing_thread_id",
            "message": "thread_id is required in context (chat.py must set context['thread_id']).",
        }

    ws = WorkspaceService(token=resolved_token)
    files = await ws.list_files(thread_id)
    return {"ok": True, "files": files, "count": len(files)}


_WORKSPACE_WRITE_FILE_SCHEMA = {
    "type": "function",
    "function": {
        "name": "write_file",
        "description": (
            "Create or overwrite a workspace text file scoped to the current chat thread. "
            "Path is relative (no leading '/', no '\\\\', no '..'), max 500 chars, content max 1 MB. "
            "Recommended directories: notes/, data/, drafts/, deliverables/. "
            "Returns {ok, operation, size_bytes, file_path} or a structured {error: ...}."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Relative path within the thread workspace.",
                },
                "content": {
                    "type": "string",
                    "description": "Full file contents.",
                },
            },
            "required": ["file_path", "content"],
        },
    },
}

_WORKSPACE_READ_FILE_SCHEMA = {
    "type": "function",
    "function": {
        "name": "read_file",
        "description": (
            "Read a workspace file scoped to the current chat thread. Returns text content for text "
            "files. For binary files returns {is_binary: true, signed_url, mime_type, size_bytes} — "
            "the URL is valid for 1 hour. Returns {error: file_not_found} if the path doesn't exist."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Relative path within the thread workspace.",
                },
            },
            "required": ["file_path"],
        },
    },
}

_WORKSPACE_EDIT_FILE_SCHEMA = {
    "type": "function",
    "function": {
        "name": "edit_file",
        "description": (
            "Edit a workspace text file via exact-string replacement. `old_string` MUST appear EXACTLY ONCE; "
            "if absent or ambiguous the call returns a structured error and the file is unchanged. "
            "Cannot edit binary files (returns {error: is_binary_file})."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Relative path within the thread workspace.",
                },
                "old_string": {
                    "type": "string",
                    "description": "Must appear exactly once in the file.",
                },
                "new_string": {
                    "type": "string",
                    "description": "Replacement text.",
                },
            },
            "required": ["file_path", "old_string", "new_string"],
        },
    },
}

_WORKSPACE_LIST_FILES_SCHEMA = {
    "type": "function",
    "function": {
        "name": "list_files",
        "description": (
            "List all workspace files for the current chat thread, ordered by most recently updated. "
            "Returns [{file_path, size_bytes, source, mime_type, updated_at}, ...]."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
}


def _register_workspace_tools() -> None:
    """Register the four workspace tools as native tools (Phase 18 / D-07, D-08).

    Gated by settings.workspace_enabled — early return when False so the
    four tools are completely absent from the registry (D-08 kill-switch).
    Only runs when tool_registry_enabled is also True (registry must exist).
    """
    if not settings.tool_registry_enabled:
        return
    if not settings.workspace_enabled:
        return

    from app.services import tool_registry  # noqa: PLC0415

    tool_registry.register(
        name="edit_file",
        description=_WORKSPACE_EDIT_FILE_SCHEMA["function"]["description"],
        schema=_WORKSPACE_EDIT_FILE_SCHEMA,
        source="native",
        loading="immediate",
        executor=_workspace_edit_file_executor,
    )

    tool_registry.register(
        name="list_files",
        description=_WORKSPACE_LIST_FILES_SCHEMA["function"]["description"],
        schema=_WORKSPACE_LIST_FILES_SCHEMA,
        source="native",
        loading="immediate",
        executor=_workspace_list_files_executor,
    )

    tool_registry.register(
        name="read_file",
        description=_WORKSPACE_READ_FILE_SCHEMA["function"]["description"],
        schema=_WORKSPACE_READ_FILE_SCHEMA,
        source="native",
        loading="immediate",
        executor=_workspace_read_file_executor,
    )

    tool_registry.register(
        name="write_file",
        description=_WORKSPACE_WRITE_FILE_SCHEMA["function"]["description"],
        schema=_WORKSPACE_WRITE_FILE_SCHEMA,
        source="native",
        loading="immediate",
        executor=_workspace_write_file_executor,
    )


# Run at module load. No-op when workspace_enabled or tool_registry_enabled is False.
_register_workspace_tools()
