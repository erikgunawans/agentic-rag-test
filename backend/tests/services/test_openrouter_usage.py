"""Unit tests for OpenRouterService usage-capture plumbing (Phase 12 / CTX-01).

Mocked AsyncOpenAI client; verifies stream_options passthrough, terminal-chunk
usage attachment, graceful CTX-06 None fallback, and complete_with_tools
return-dict extension.
"""
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def service():
    """OpenRouterService instance with a mocked AsyncOpenAI client."""
    from app.services.openrouter_service import OpenRouterService
    s = OpenRouterService()
    s.client = MagicMock()
    s.client.chat = MagicMock()
    s.client.chat.completions = MagicMock()
    s.client.chat.completions.create = AsyncMock()
    return s


def _delta_chunk(text: str):
    """Build a mock streaming delta chunk."""
    chunk = MagicMock()
    chunk.choices = [MagicMock()]
    chunk.choices[0].delta = MagicMock()
    chunk.choices[0].delta.content = text
    chunk.usage = None
    return chunk


def _usage_chunk(prompt: int, completion: int, total: int):
    """Build a mock terminal usage chunk (no choices, only `usage`)."""
    chunk = MagicMock()
    chunk.choices = []
    chunk.usage = MagicMock()
    chunk.usage.prompt_tokens = prompt
    chunk.usage.completion_tokens = completion
    chunk.usage.total_tokens = total
    return chunk


def _async_iter(items):
    async def gen():
        for it in items:
            yield it
    return gen()


@pytest.mark.asyncio
async def test_stream_response_passes_stream_options(service):
    service.client.chat.completions.create.return_value = _async_iter([_delta_chunk("hi")])
    out = []
    async for c in service.stream_response(messages=[{"role": "user", "content": "hi"}]):
        out.append(c)
    call_kwargs = service.client.chat.completions.create.call_args.kwargs
    assert call_kwargs.get("stream") is True
    assert call_kwargs.get("stream_options") == {"include_usage": True}


@pytest.mark.asyncio
async def test_stream_response_terminal_chunk_carries_usage(service):
    service.client.chat.completions.create.return_value = _async_iter([
        _delta_chunk("hi"),
        _delta_chunk(" there"),
        _usage_chunk(10, 5, 15),
    ])
    chunks = []
    async for c in service.stream_response(messages=[]):
        chunks.append(c)
    assert chunks[0] == {"delta": "hi", "done": False}
    assert chunks[1] == {"delta": " there", "done": False}
    terminal = chunks[-1]
    assert terminal["done"] is True
    assert terminal["delta"] == ""
    assert terminal["usage"] == {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}


@pytest.mark.asyncio
async def test_stream_response_no_usage_chunk_yields_none(service):
    service.client.chat.completions.create.return_value = _async_iter([
        _delta_chunk("hello"),
    ])
    chunks = []
    async for c in service.stream_response(messages=[]):
        chunks.append(c)
    terminal = chunks[-1]
    assert terminal["done"] is True
    assert terminal["usage"] is None


@pytest.mark.asyncio
async def test_stream_response_partial_usage_object_safe(service):
    bad_chunk = MagicMock()
    bad_chunk.choices = []
    bad_chunk.usage = MagicMock()
    bad_chunk.usage.prompt_tokens = 10
    bad_chunk.usage.completion_tokens = None
    bad_chunk.usage.total_tokens = None
    service.client.chat.completions.create.return_value = _async_iter([
        _delta_chunk("x"),
        bad_chunk,
    ])
    chunks = []
    async for c in service.stream_response(messages=[]):
        chunks.append(c)
    terminal = chunks[-1]
    # Either fully None OR partially populated — but MUST NOT raise and MUST emit terminal.
    assert terminal["done"] is True
    assert "usage" in terminal


@pytest.mark.asyncio
async def test_complete_with_tools_returns_usage(service):
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message = MagicMock()
    response.choices[0].message.role = "assistant"
    response.choices[0].message.content = "ok"
    response.choices[0].message.tool_calls = None
    response.choices[0].finish_reason = "stop"
    response.usage = MagicMock()
    response.usage.prompt_tokens = 20
    response.usage.completion_tokens = 8
    response.usage.total_tokens = 28
    service.client.chat.completions.create.return_value = response

    result = await service.complete_with_tools(messages=[], tools=None)
    assert result["usage"] == {"prompt_tokens": 20, "completion_tokens": 8, "total_tokens": 28}


@pytest.mark.asyncio
async def test_complete_with_tools_no_usage_returns_none(service):
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message = MagicMock()
    response.choices[0].message.role = "assistant"
    response.choices[0].message.content = "ok"
    response.choices[0].message.tool_calls = None
    response.choices[0].finish_reason = "stop"
    response.usage = None
    service.client.chat.completions.create.return_value = response

    result = await service.complete_with_tools(messages=[], tools=None)
    assert result["usage"] is None
    assert result["role"] == "assistant"
    assert result["content"] == "ok"
    assert result["finish_reason"] == "stop"


@pytest.mark.asyncio
async def test_complete_with_tools_preserves_tool_calls_shape(service):
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message = MagicMock()
    response.choices[0].message.role = "assistant"
    response.choices[0].message.content = None
    tc = MagicMock()
    tc.id = "call_xyz"
    tc.function = MagicMock()
    tc.function.name = "search_documents"
    tc.function.arguments = '{"q": "x"}'
    response.choices[0].message.tool_calls = [tc]
    response.choices[0].finish_reason = "tool_calls"
    response.usage = MagicMock(prompt_tokens=1, completion_tokens=1, total_tokens=2)
    service.client.chat.completions.create.return_value = response

    result = await service.complete_with_tools(messages=[], tools=[{"name": "x"}])
    assert result["tool_calls"][0]["id"] == "call_xyz"
    assert result["tool_calls"][0]["function"]["name"] == "search_documents"
    assert result["usage"]["total_tokens"] == 2


@pytest.mark.asyncio
async def test_stream_response_existing_consumer_pattern_works(service):
    """Sanity: a consumer that ignores `usage` keeps working byte-identically."""
    service.client.chat.completions.create.return_value = _async_iter([
        _delta_chunk("a"), _delta_chunk("b"), _usage_chunk(1, 1, 2),
    ])
    text = ""
    done = False
    async for c in service.stream_response(messages=[]):
        text += c["delta"]
        done = c["done"]
    assert text == "ab"
    assert done is True
