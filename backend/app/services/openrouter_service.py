"""OpenRouter / OpenAI-compatible chat completion service.

Phase 12 (D-P12-02 / CTX-01 / CTX-06): single-source-of-truth for usage
capture. Both stream_response and complete_with_tools plumb usage data so
chat.py never has to know about `stream_options`. When the provider does
not emit a usage chunk (older OpenRouter routes, some Ollama builds), the
captured value is None and the chat router silently skips emitting the
SSE `usage` event (CTX-06).
"""
import logging
from typing import Any, AsyncGenerator

from openai import AsyncOpenAI
from app.services.tracing_service import traced
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def _extract_usage(usage_obj: Any) -> dict | None:
    """Convert an OpenAI CompletionUsage object into a plain dict.

    Returns None if any required field is missing or the object is None.
    Tolerant of partial / None fields per CTX-06 graceful no-op.
    """
    if usage_obj is None:
        return None
    try:
        prompt = getattr(usage_obj, "prompt_tokens", None)
        completion = getattr(usage_obj, "completion_tokens", None)
        total = getattr(usage_obj, "total_tokens", None)
    except Exception as exc:
        logger.debug("usage extract failed err=%s — falling back to None", exc)
        return None
    if prompt is None and completion is None and total is None:
        return None
    return {
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "total_tokens": total,
    }


class OpenRouterService:
    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=settings.openrouter_api_key,
            base_url="https://openrouter.ai/api/v1",
        )
        self.model = settings.openrouter_model

    @traced(name="stream_chat_response")
    async def stream_response(
        self, messages: list[dict], model: str | None = None
    ) -> AsyncGenerator[dict, None]:
        """Stream chat deltas; final chunk carries optional usage payload.

        D-P12-02 / CTX-01: stream_options={"include_usage": True} is plumbed
        unconditionally — every caller benefits without per-call wiring.
        D-P12-03 / CTX-06: when no usage chunk arrives, terminal yields
        {"delta":"", "done": True, "usage": None} — chat router skips emit.
        """
        stream = await self.client.chat.completions.create(
            model=model or self.model,
            messages=messages,
            stream=True,
            stream_options={"include_usage": True},
        )
        captured_usage: dict | None = None
        async for chunk in stream:
            # Usage chunks have empty choices; capture and continue.
            if not chunk.choices:
                if getattr(chunk, "usage", None) is not None:
                    captured_usage = _extract_usage(chunk.usage)
                continue
            delta = chunk.choices[0].delta.content or ""
            # Some providers attach usage to the LAST regular chunk too — capture if present.
            if getattr(chunk, "usage", None) is not None and captured_usage is None:
                captured_usage = _extract_usage(chunk.usage)
            if delta:
                yield {"delta": delta, "done": False}
        if captured_usage is None:
            logger.debug("stream_response: provider did not emit usage chunk (CTX-06)")
        yield {"delta": "", "done": True, "usage": captured_usage}

    @traced(name="tool_calling_completion")
    async def complete_with_tools(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        model: str | None = None,
        response_format: dict | None = None,
    ) -> dict:
        """Non-streaming completion that may return tool_calls.

        Phase 12 / CTX-01: returns an additional `usage` key alongside the
        existing role/content/tool_calls/finish_reason. None when provider
        does not emit usage data (CTX-06).
        """
        kwargs: dict = {
            "model": model or self.model,
            "messages": messages,
            "stream": False,
        }
        if tools:
            kwargs["tools"] = tools
        if response_format:
            kwargs["response_format"] = response_format
        response = await self.client.chat.completions.create(**kwargs)
        choice = response.choices[0]
        return {
            "role": choice.message.role,
            "content": choice.message.content,
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in (choice.message.tool_calls or [])
            ] if choice.message.tool_calls else None,
            "finish_reason": choice.finish_reason,
            "usage": _extract_usage(getattr(response, "usage", None)),
        }
