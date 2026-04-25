from typing import AsyncGenerator
from openai import AsyncOpenAI
from app.services.tracing_service import traced
from app.config import get_settings


class OpenAIService:
    def __init__(self) -> None:
        settings = get_settings()
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.vector_store_id = settings.openai_vector_store_id

    @traced(name="create_openai_thread")
    async def create_thread(self) -> str:
        """Creates a new OpenAI thread and returns its ID."""
        thread = await self.client.beta.threads.create()
        return thread.id

    @traced(name="stream_chat_response")
    async def stream_response(
        self,
        message: str,
        last_response_id: str | None = None,
    ) -> AsyncGenerator[dict, None]:
        """Streams a response using the OpenAI Responses API.

        Yields dicts: {"delta": str, "done": bool, "response_id": str | None}
        """
        tools = []
        if self.vector_store_id:
            tools = [{"type": "file_search", "vector_store_ids": [self.vector_store_id]}]

        params: dict = {
            "model": "gpt-4o-mini",
            "input": [{"role": "user", "content": message}],
        }
        if last_response_id:
            params["previous_response_id"] = last_response_id
        if tools:
            params["tools"] = tools

        response_id: str | None = None

        async with self.client.responses.stream(**params) as stream:
            async for event in stream:
                if event.type == "response.output_text.delta":
                    yield {"delta": event.delta, "done": False, "response_id": None}
                elif event.type == "response.completed":
                    response_id = event.response.id

        yield {"delta": "", "done": True, "response_id": response_id}
