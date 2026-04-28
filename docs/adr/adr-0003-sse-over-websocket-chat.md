---
title: "ADR-0003: Server-Sent Events (SSE) over WebSocket for Chat Streaming"
status: "Accepted"
date: "2026-04-28"
authors: "Erik Gunawan Supriatna (LexCore Engineering)"
tags: ["architecture", "decision", "streaming", "sse", "websocket", "chat"]
supersedes: ""
superseded_by: ""
---

# ADR-0003: Server-Sent Events (SSE) over WebSocket for Chat Streaming

## Status

**Accepted** — shipped with v0.1.0 and used as the only streaming transport in the system. Currently emits `agent_start`, `tool_start`, `tool_result`, `delta`, `done`, `error`, and `blocked` event types. ADR-0007 will extend this contract with `reasoning_delta`.

## Context

Chat responses must stream progressively to the user — the model emits hundreds of tokens per response and a buffered round-trip would feel broken. The transport choice was:

- **WebSocket** — bidirectional, persistent, full-duplex.
- **Server-Sent Events (SSE)** — unidirectional (server → client) over a long-lived HTTP connection.

The chat conversation pattern is asymmetric:
- Client → server: send a message, ask for a response.
- Server → client: stream tokens progressively, emit tool events, signal completion.

There is no genuine bidirectional streaming need — the client never sends mid-response data to the server during a single turn.

Other considerations:
- Network proxy compatibility (corporate VPNs, browser extensions)
- Reconnection semantics
- Authentication semantics (HTTP headers vs. WebSocket subprotocols)
- Standard HTTP infrastructure (caching, logging, rate limiting)
- Mobile network resilience

## Decision

Use **Server-Sent Events** for the chat response stream. The endpoint is `POST /chat/stream`, which returns `Content-Type: text/event-stream`. The client opens a single SSE connection per chat turn; multi-turn is handled by sequential POSTs that each open a fresh SSE stream.

## Consequences

### Positive

- **POS-001**: Standard HTTP semantics — the SSE response inherits all auth, caching, and logging conventions from the rest of the API.
- **POS-002**: Authentication via standard `Authorization: Bearer <jwt>` header. WebSocket auth requires either query-string tokens (logged in proxies) or sub-protocol negotiation (custom client code).
- **POS-003**: Proxy / firewall compatibility is excellent — SSE looks like a slow HTTP response.
- **POS-004**: No connection-state management — every chat turn is its own stream; no keepalive ping needed.
- **POS-005**: Browser `EventSource` API is built in; no library dependency on the frontend.
- **POS-006**: Backpressure is implicit — if the browser stalls, TCP backpressure propagates naturally.
- **POS-007**: Clean recovery — if the SSE stream dies mid-response, the next turn is a fresh POST; no reconnect-and-resume protocol needed.

### Negative

- **NEG-001**: Cannot send mid-response data from client to server (e.g., "stop generating now" mid-stream). Cancellation requires a separate POST to a different endpoint.
- **NEG-002**: HTTP/1.1 connection limits apply (browsers cap concurrent connections per origin). Not an issue for chat (one stream at a time per user) but would matter for multiplexed streams.
- **NEG-003**: No standard SSE binary format — JSON-encoded events are the convention. Slightly more bandwidth than a binary WebSocket protocol.
- **NEG-004**: `EventSource` does not support custom auth headers in some older browsers without a polyfill. Modern target browsers all support this; we use the `headers` option in our wrapper.

## Alternatives Considered

### WebSocket

- **ALT-001**: **Description**: A persistent bidirectional connection per user/session, multiplexing chat turns over a single socket.
- **ALT-002**: **Rejection Reason**: True bidirectional streaming is not needed — the client only sends one message per turn. WebSocket adds connection-state management, custom auth wiring, and proxy-compatibility risk for no architectural benefit.

### HTTP Long-Polling

- **ALT-003**: **Description**: Client polls `GET /chat/poll` every N ms; server holds the connection open until tokens are available.
- **ALT-004**: **Rejection Reason**: Higher latency per token, more HTTP overhead, no progressive token delivery semantics. Genuinely worse than SSE on every dimension.

### gRPC Streaming

- **ALT-005**: **Description**: Use gRPC server-streaming over HTTP/2.
- **ALT-006**: **Rejection Reason**: Browser support requires gRPC-Web shim; adds protobuf toolchain to a project that otherwise uses JSON; team familiarity is lower. Cost without commensurate benefit.

## Implementation Notes

- **IMP-001**: Backend uses FastAPI's `StreamingResponse` with an async generator. Each yielded item is `f"data: {json.dumps(event)}\n\n"`.
- **IMP-002**: Frontend uses a custom SSE client (in `useChatState.ts`) that supports the `Authorization: Bearer` header — the native `EventSource` does not, and we need JWT auth.
- **IMP-003**: Event sequence per turn: `agent_start` → `tool_start` → `tool_result` → `delta`* (many) → `done`. Error path: `error` (terminal) or `blocked` (PII egress; terminal). ADR-0007 adds `reasoning_delta` to this contract.
- **IMP-004**: Cancellation is not implemented today. If/when needed, add `POST /chat/cancel/{message_id}` and check a cancellation flag in the streaming generator.
- **IMP-005**: Realtime subscriptions for non-chat data (document processing status) use Supabase Realtime, not SSE. The two patterns are kept separate by purpose.

## References

- **REF-001**: ADR-0007 — Model Chain-of-Thought / Reasoning Observability (extends SSE event contract with `reasoning_delta`).
- **REF-002**: `backend/app/routers/chat.py` — SSE event generator.
- **REF-003**: `frontend/src/hooks/useChatState.ts` — SSE consumer.
- **REF-004**: `Project_Architecture_Blueprint.md` Section 7 — Service Communication Patterns.
- **REF-005**: WHATWG Server-Sent Events specification — https://html.spec.whatwg.org/multipage/server-sent-events.html
