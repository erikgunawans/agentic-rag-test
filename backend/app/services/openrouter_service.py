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
