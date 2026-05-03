"""Phase 19 / TASK-* — Sub-agent inner loop.

Mirrors run_deep_mode_loop minus task/write_todos/read_todos. ask_user is
intentionally retained (D-09) — sub-agents may escalate to user. Capped at
MAX_SUB_AGENT_ROUNDS=15 (D-11 forced summary on cap). Yields parent's SSE
events tagged with task_id (D-06).

Privacy invariant: sub-agent reuses the PARENT's ConversationRegistry — egress
filter is applied to every LLM payload so real PII never reaches the cloud
LLM (D-21 / T-19-21).

Security invariant: sub-agent receives parent_token only — RLS scope shared,
no privilege escalation path (D-22 / T-19-22).

Failure isolation: every uncaught exception is converted to a structured
_terminal_result error dict so the parent loop never crashes (D-12 / TASK-05).

D-07: No status broadcast events from inside this module (only outermost loop emits those).
D-23: No action-logging with separate sub-agent identity — parent's user_id used.
"""
from __future__ import annotations

import json
import logging
from typing import AsyncIterator

from app.config import get_settings
from app.database import get_supabase_authed_client
from app.services.redaction.egress import egress_filter
from app.services.workspace_service import WorkspaceService
from app.services import tool_registry as _tr

logger = logging.getLogger(__name__)
settings = get_settings()

# Single-file size limit: 1 MB
_MAX_FILE_BYTES = 1024 * 1024
# Combined context_files size limit: 5 MB
_MAX_TOTAL_BYTES = 5 * 1024 * 1024


# ---------------------------------------------------------------------------
# Helper: first user message builder (D-08)
# ---------------------------------------------------------------------------

def _build_first_user_message(
    description: str,
    context_files_content: dict[str, str],
) -> str:
    """Build the initial user message, wrapping context files in XML tags (D-08).

    Returns a string of the form:
        <task>
        {description}
        </task>

        <context_file path="notes.md">
        {content}
        </context_file>
    """
    parts = [f"<task>\n{description}\n</task>\n"]
    for path, content in context_files_content.items():
        parts.append(f'\n<context_file path="{path}">\n{content}\n</context_file>\n')
    return "".join(parts)


# ---------------------------------------------------------------------------
# Helper: persist one round message with parent_task_id (D-10)
# ---------------------------------------------------------------------------

async def _persist_round_message(
    thread_id: str,
    role: str,
    content: str,
    *,
    user_id: str,
    token: str,
    parent_message_id: str | None = None,
    parent_task_id: str | None = None,
) -> str | None:
    """Persist one message row for a sub-agent round, tagging with parent_task_id (D-10).

    Returns the inserted message ID, or None on error (non-fatal per D-12).
    """
    try:
        db = get_supabase_authed_client(token)
        insert_data: dict = {
            "thread_id": thread_id,
            "user_id": user_id,
            "role": role,
            "content": content,
        }
        if parent_message_id:
            insert_data["parent_message_id"] = parent_message_id
        if parent_task_id:
            insert_data["parent_task_id"] = parent_task_id
        result = db.table("messages").insert(insert_data).execute()
        if result.data:
            return result.data[0]["id"]
    except Exception as exc:
        logger.warning(
            "sub_agent_loop._persist_round_message failed thread_id=%s task_id=%s exc=%s",
            thread_id, parent_task_id, exc,
        )
    return None


# ---------------------------------------------------------------------------
# Helper: execute a single tool call
# ---------------------------------------------------------------------------

async def _execute_tool_call(
    func_name: str,
    func_args: dict,
    user_id: str,
    tool_context: dict,
    token: str,
) -> dict:
    """Dispatch one tool call via the tool registry or a no-op fallback."""
    if settings.tool_registry_enabled:
        if func_name in _tr._REGISTRY:
            tool_def = _tr._REGISTRY[func_name]
            try:
                result = await tool_def.executor(func_args, user_id, tool_context, token=token)
                return result if isinstance(result, dict) else {"result": str(result)}
            except Exception as exc:
                return {"error": str(exc)}
    return {"error": f"Tool '{func_name}' is not available."}


# ---------------------------------------------------------------------------
# Inner loop implementation
# ---------------------------------------------------------------------------

async def _run_sub_agent_loop_inner(
    *,
    description: str,
    context_files: list[str],
    parent_user_id: str,
    parent_user_email: str,
    parent_token: str,
    parent_tool_context: dict,
    parent_thread_id: str,
    parent_user_msg_id: str,
    client,
    sys_settings: dict,
    web_search_effective: bool,
    task_id: str,
    parent_redaction_registry,
) -> AsyncIterator[dict]:
    """Async generator: the actual sub-agent iteration loop."""
    llm_model = sys_settings.get("llm_model", settings.openrouter_model if hasattr(settings, "openrouter_model") else "openai/gpt-4o")
    max_iterations = settings.max_sub_agent_rounds  # 15 per config.py

    # --- Egress / redaction setup ---
    redaction_on = bool(sys_settings.get("pii_redaction_enabled", False))
    registry = parent_redaction_registry  # D-21: reuse parent's registry, NOT a fresh one

    # --- Pre-load context_files (D-08) ---
    context_files_content: dict[str, str] = {}
    if context_files:
        ws = WorkspaceService(parent_token)
        total_bytes = 0
        for path in context_files:
            result = await ws.read_file(parent_thread_id, path)
            if "error" in result:
                yield {"_terminal_result": {
                    "error": result["error"],
                    "code": "WS_READ_ERROR",
                    "detail": result.get("detail", "workspace read failed"),
                    "file_path": path,
                }}
                return

            if result.get("is_binary"):
                yield {"_terminal_result": {
                    "error": "binary_file_not_inlinable",
                    "file_path": path,
                    "code": "WS_BINARY_FILE",
                    "detail": "Binary files cannot be inlined into context_files (D-08).",
                }}
                return

            content = result.get("content") or ""
            size_bytes = len(content.encode("utf-8"))
            if size_bytes > _MAX_FILE_BYTES:
                yield {"_terminal_result": {
                    "error": "text_content_too_large",
                    "code": "WS_LIMIT_EXCEEDED",
                    "limit_bytes": _MAX_FILE_BYTES,
                    "actual_bytes": size_bytes,
                    "file_path": path,
                }}
                return

            total_bytes += size_bytes
            if total_bytes > _MAX_TOTAL_BYTES:
                yield {"_terminal_result": {
                    "error": "context_files_total_too_large",
                    "code": "TASK_LIMIT_EXCEEDED",
                    "limit_bytes": _MAX_TOTAL_BYTES,
                    "detail": "Combined context_files size exceeds 5 MB limit.",
                }}
                return

            context_files_content[path] = content

    # --- Build first user message ---
    first_user_content = _build_first_user_message(description, context_files_content)

    # --- Build tool list — inherit parent minus task/write_todos/read_todos (D-09) ---
    if settings.tools_enabled and settings.tool_registry_enabled:
        active_set = _tr.make_active_set()
        full_tools = _tr.build_llm_tools(
            active_set=active_set,
            web_search_enabled=web_search_effective,
            sandbox_enabled=settings.sandbox_enabled,
            agent_allowed_tools=None,
        )
        # D-09: ask_user is intentionally retained — sub-agents may escalate to user.
        # Only task / write_todos / read_todos are stripped from the parent's full_tools.
        EXCLUDED = {"task", "write_todos", "read_todos"}
        sub_tools = [t for t in full_tools if t["function"]["name"] not in EXCLUDED]
    else:
        sub_tools = []

    available_tool_names = [t["function"]["name"] for t in sub_tools]

    # --- System prompt for sub-agent ---
    system_prompt = (
        "You are a focused sub-agent. Complete the task described by the user precisely. "
        "Use the tools provided to gather information and complete your work. "
        "When you have finished, provide a clear, concise final answer."
    )

    # --- Build initial messages array ---
    loop_messages: list[dict] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": first_user_content},
    ]

    # --- Persist the initial user message with parent_task_id (D-10) ---
    current_parent_id = await _persist_round_message(
        parent_thread_id,
        "user",
        first_user_content,
        user_id=parent_user_id,
        token=parent_token,
        parent_message_id=parent_user_msg_id,
        parent_task_id=task_id,
    )
    if current_parent_id is None:
        current_parent_id = parent_user_msg_id

    # --- Tool context with token wired in ---
    tool_context = {**parent_tool_context, "user_email": parent_user_email, "token": parent_token}

    # --- Per-round state ---
    full_response = ""
    current_tools = list(sub_tools)

    for _iteration in range(max_iterations):
        # D-11: force summarize on final iteration
        if _iteration == max_iterations - 1 and current_tools:
            loop_messages.append({
                "role": "system",
                "content": (
                    "You have reached the iteration limit. "
                    "Please summarize what you have completed and deliver "
                    "a final answer to the parent agent."
                ),
            })
            current_tools = []  # force terminal text round

        # D-21: egress filter — apply to every LLM payload using PARENT's registry.
        # Collapsed to a single guard: registry is only non-None when redaction is on
        # (parent loop sets it that way), so the former elif was unreachable (W-02).
        if registry is not None:
            payload = json.dumps(loop_messages, ensure_ascii=False)
            egress_result = egress_filter(payload, registry, None)
            if egress_result.tripped:
                logger.warning(
                    "egress_blocked event=egress_blocked feature=sub_agent_loop "
                    "task_id=%s iteration=%d match_count=%d",
                    task_id, _iteration, egress_result.match_count,
                )
                yield {"_terminal_result": {
                    "error": "egress_blocked",
                    "code": "PII_EGRESS_BLOCKED",
                    "detail": "PII detected in sub-agent payload — request blocked.",
                }}
                return

        # --- LLM call ---
        call_kwargs: dict = {
            "model": llm_model,
            "messages": loop_messages,
        }
        if current_tools:
            call_kwargs["tools"] = current_tools

        response = await client.chat.completions.create(**call_kwargs)
        choice = response.choices[0]
        message = choice.message
        tool_calls = getattr(message, "tool_calls", None)

        # Terminal: no tool calls → collect text and exit
        if not tool_calls:
            full_response = message.content or ""
            break

        # --- Process each tool call ---
        for tc in tool_calls:
            func_name = tc.function.name
            try:
                func_args = json.loads(tc.function.arguments)
            except (json.JSONDecodeError, AttributeError):
                func_args = {}

            # SSE: tool_start tagged with task_id (D-06)
            yield {
                "type": "tool_start",
                "tool": func_name,
                "task_id": task_id,
            }

            try:
                if func_name not in available_tool_names:
                    tool_output: dict = {
                        "blocked": True,
                        "reason": f"Tool '{func_name}' is not available for sub-agent.",
                    }
                else:
                    tool_output = await _execute_tool_call(
                        func_name, func_args, parent_user_id, tool_context, parent_token
                    )
            except Exception as exc:
                tool_output = {"error": str(exc)}

            # SSE: tool_result tagged with task_id (D-06)
            yield {
                "type": "tool_result",
                "tool": func_name,
                "task_id": task_id,
            }

            # Workspace mutation event
            if (
                func_name in ("write_file", "edit_file")
                and isinstance(tool_output, dict)
                and tool_output.get("ok")
                and settings.workspace_enabled
            ):
                yield {
                    "type": "workspace_updated",
                    "file_path": tool_output.get("file_path"),
                    "operation": tool_output.get("operation"),
                    "size_bytes": tool_output.get("size_bytes"),
                    "source": "sub_agent",
                    "task_id": task_id,
                }

            loop_messages.append({
                "role": "assistant",
                "content": None,
                "tool_calls": [{
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": func_name,
                        "arguments": tc.function.arguments,
                    },
                }],
            })
            loop_messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": json.dumps(tool_output),
            })

        # Persist this round (D-10: parent_task_id set on every row)
        round_content = getattr(message, "content", None) or ""
        current_parent_id = await _persist_round_message(
            parent_thread_id,
            "assistant",
            round_content,
            user_id=parent_user_id,
            token=parent_token,
            parent_message_id=current_parent_id,
            parent_task_id=task_id,
        ) or current_parent_id

    # --- Persist final text row (D-10) ---
    if full_response:
        await _persist_round_message(
            parent_thread_id,
            "assistant",
            full_response,
            user_id=parent_user_id,
            token=parent_token,
            parent_message_id=current_parent_id,
            parent_task_id=task_id,
        )

    yield {"_terminal_result": {"text": full_response}}


# ---------------------------------------------------------------------------
# Public async generator entry point — failure-isolation wrapper (D-12)
# ---------------------------------------------------------------------------

async def run_sub_agent_loop(
    *,
    description: str,
    context_files: list[str],
    parent_user_id: str,
    parent_user_email: str,
    parent_token: str,
    parent_tool_context: dict,
    parent_thread_id: str,
    parent_user_msg_id: str,
    client,
    sys_settings: dict,
    web_search_effective: bool,
    task_id: str,
    parent_redaction_registry,
) -> AsyncIterator[dict]:
    """Phase 19 / TASK-* — Sub-agent inner loop entry point.

    Async generator that yields SSE event dicts. Final yield is always
    {"_terminal_result": {...}} where the value is either {"text": "<response>"}
    or a structured error dict (D-12 — no raw exceptions propagate to parent).

    Args:
        description: Sub-agent's task description (becomes first user message body).
        context_files: List of workspace paths to pre-load as context (D-08).
        parent_user_id: Authenticated user's UUID (inherited from parent — D-22).
        parent_user_email: Authenticated user's email.
        parent_token: JWT access token — SAME JWT as parent (D-22 RLS scope shared).
        parent_tool_context: Tool context dict inherited from parent.
        parent_thread_id: Parent thread UUID.
        parent_user_msg_id: Message ID of parent's user message (chain start).
        client: OpenRouter-compatible async client (chat.completions.create).
        sys_settings: System settings dict (llm_model, pii_redaction_enabled, ...).
        web_search_effective: Web search toggle (inherited from parent).
        task_id: Server-generated UUID for this sub-agent task (D-06 event tagging).
        parent_redaction_registry: Parent's ConversationRegistry (D-21 — NOT a fresh one).

    Yields:
        dict events tagged with task_id. Final event: {"_terminal_result": {...}}
    """
    # W-01: sub_agent_loop requires tool_registry_enabled. When the registry is
    # disabled every _execute_tool_call returns an error dict, making all tool
    # calls silently fail. Catch the invalid flag combination early and return a
    # structured terminal error so the parent loop surfaces a clear message rather
    # than exhausting iteration rounds with no useful output.
    if not settings.tool_registry_enabled:
        logger.error(
            "run_sub_agent_loop called with tool_registry_enabled=False — "
            "sub-agent requires the tool registry; task_id=%s",
            task_id,
        )
        yield {"_terminal_result": {
            "error": "tool_registry_disabled",
            "code": "CONFIG_CONFLICT",
            "detail": (
                "sub_agent_enabled=True requires tool_registry_enabled=True. "
                "Enable the tool registry or disable sub-agents."
            ),
        }}
        return

    try:
        async for event in _run_sub_agent_loop_inner(
            description=description,
            context_files=context_files,
            parent_user_id=parent_user_id,
            parent_user_email=parent_user_email,
            parent_token=parent_token,
            parent_tool_context=parent_tool_context,
            parent_thread_id=parent_thread_id,
            parent_user_msg_id=parent_user_msg_id,
            client=client,
            sys_settings=sys_settings,
            web_search_effective=web_search_effective,
            task_id=task_id,
            parent_redaction_registry=parent_redaction_registry,
        ):
            yield event
    except Exception as exc:
        logger.error(
            "sub_agent_loop failure task_id=%s exc=%s",
            task_id, exc, exc_info=True,
        )
        # D-19: sanitized — no stack trace in detail field
        yield {"_terminal_result": {
            "error": "sub_agent_failed",
            "code": "TASK_LOOP_CRASH",
            "detail": str(exc)[:500],
        }}
