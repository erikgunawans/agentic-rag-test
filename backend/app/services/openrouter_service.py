from typing import AsyncGenerator
from openai import AsyncOpenAI
from langsmith import traceable
from app.config import get_settings

settings = get_settings()


class OpenRouterService:
    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=settings.openrouter_api_key,
            base_url="https://openrouter.ai/api/v1",
        )
        self.model = settings.openrouter_model

    @traceable(name="stream_chat_response")
    async def stream_response(
        self, messages: list[dict], model: str | None = None
    ) -> AsyncGenerator[dict, None]:
        stream = await self.client.chat.completions.create(
            model=model or self.model,
            messages=messages,
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content or ""
            if delta:
                yield {"delta": delta, "done": False}
        yield {"delta": "", "done": True}

    @traceable(name="tool_calling_completion")
    async def complete_with_tools(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        model: str | None = None,
        response_format: dict | None = None,
    ) -> dict:
        """Non-streaming completion that may return tool_calls."""
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
        }
