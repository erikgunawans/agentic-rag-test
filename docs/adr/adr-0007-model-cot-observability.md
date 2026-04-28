---
title: "ADR-0007: Model Chain-of-Thought / Reasoning Observability"
status: "Proposed"
date: "2026-04-28"
authors: "Erik Gunawan Supriatna (LexCore Engineering)"
tags: ["architecture", "decision", "observability", "llm", "chain-of-thought", "reasoning", "langsmith", "openrouter"]
supersedes: ""
superseded_by: ""
---

# ADR-0007: Model Chain-of-Thought / Reasoning Observability

## Status

**Proposed** — pending implementation. Extends ADR-0001 (raw SDK) and ADR-0003 (SSE) without superseding them. Defines a forward-looking trigger for revisiting LangGraph adoption.

## Context

LexCore users — Indonesian legal practitioners working on contracts and regulatory compliance — increasingly need to **understand how the model arrived at an answer**, not just receive the answer itself. The product question "I want to see the chain of thought when the model is answering" decomposes into two distinct observability needs that must be addressed separately:

| Observability type | Audience | Where it surfaces |
|---|---|---|
| **Developer/admin tracing** | Engineering, debugging poor answers | Backend dashboard (off-platform) |
| **End-user chain-of-thought** | Legal user in chat | Inline in the chat UI, expandable |

Conflating these leads to wrong tooling. Modern reasoning-capable models (Claude 4.x extended thinking, OpenAI o1/o3, DeepSeek R1) emit distinct **reasoning tokens** separate from the final answer. OpenRouter exposes these via a unified `reasoning` parameter, returning a `delta.reasoning` field on stream chunks alongside the existing `delta.content`.

Constraints inherited from prior ADRs:

- **ADR-0001** — raw SDK only, no LangChain or LangGraph framework code.
- **ADR-0003** — SSE is the chat streaming transport; new event types extend the existing contract.
- **ADR-0004** — PII redaction must apply to reasoning tokens with the same rigor as final-answer tokens. Reasoning tokens may surface real entity names from retrieved context.

The team explicitly considered whether ADR-0001 should be partially reconsidered for the chain-of-thought path. After analysis, the conclusion is that **OpenRouter's native `reasoning` parameter delivers the capability without framework adoption** — ADR-0001 stays intact.

## Decision

Implement chain-of-thought observability as **two complementary parts**, both consistent with ADR-0001's raw-SDK envelope:

### Part A — Developer-side tracing via LangSmith (no application code changes)

LangSmith is already configured (`LANGSMITH_API_KEY`, `LANGSMITH_PROJECT` env vars). Activate full tracing by:

1. Setting `LANGCHAIN_TRACING_V2=true` and `LANGCHAIN_PROJECT=lexcore-prod` in Railway env.
2. Wrapping the OpenRouter / OpenAI clients with LangSmith's `wrap_openai()` (or applying the `@traceable` decorator at LLM call sites).
3. No structural code changes; LangSmith observes calls without altering control flow. **Permitted under ADR-0001** because it is observation, not orchestration.

### Part B — End-user CoT via OpenRouter `reasoning` parameter (new SSE event)

For reasoning-capable models, surface the model's reasoning tokens to the chat UI:

1. Add `reasoning` parameter to `openrouter_service.py` LLM call signatures. When the active model supports reasoning, pass `reasoning={"effort": "medium"}` (or per-feature configured level).
2. **Extend the SSE contract** (extends ADR-0003): emit a new `reasoning_delta` event type on the stream, alongside the existing `delta` event.
3. **Persist reasoning** to a new column `messages.reasoning TEXT` (added via migration `033_message_reasoning.sql`). Default `NULL` — only populated when the model produced reasoning tokens.
4. **Frontend UI**: add a collapsible "🧠 Lihat alur pikir AI / View AI reasoning" block in `MessageView.tsx`, collapsed by default. Renders the `messages.reasoning` content under the assistant message.
5. **Admin toggle**: add `chain_of_thought_enabled BOOLEAN DEFAULT false` to `system_settings` (per ADR-0002). Off-mode preserves current behavior.
6. **PII safety (extends ADR-0004)**: reasoning tokens flow through the **same** de-anonymization path as final-answer tokens. The egress guard inspects reasoning chunks identically. Reasoning content persisted to `messages.reasoning` is the de-anonymized form (same as the user-visible answer).

### Future trigger — When to revisit LangGraph (not adopted today)

Document explicit criteria so a future ADR can be raised when warranted. **Do not adopt LangGraph today**; the current chat loop is linear and LangGraph's value emerges only with stateful, cyclic, multi-agent flows. Re-evaluate when any of these become real:

- **Trigger T1 — BJR multi-agent orchestration**: Business Judgment Rule workflows requiring distinct Research / Drafting / Compliance agents with handoffs.
- **Trigger T2 — Cyclic self-correction**: retrieval → reflection → re-retrieval loops where a single pass is insufficient.
- **Trigger T3 — Human-in-the-loop pauses**: agents that pause for approval, persist state, and resume hours later.
- **Trigger T4 — Durable workflow execution**: long-running document workflows that must survive container restarts (Vercel Workflow DevKit, LangGraph durable execution, or Temporal.io are candidates).

When any of T1–T4 ships as a real requirement, raise a follow-up ADR scoping LangGraph adoption *at that boundary only* — not as a wholesale chat-path migration.

## Consequences

### Positive

- **POS-001**: Two observability modes addressed by the right tool — LangSmith for engineers, OpenRouter `reasoning` for end users.
- **POS-002**: ADR-0001 preserved — no framework adoption, no rewrite of working chat code.
- **POS-003**: Trust and explainability for legal users — visible reasoning aligns with UU PDP transparency principles and supports auditability for compliance use cases.
- **POS-004**: Provider-agnostic — OpenRouter abstracts Claude extended thinking, OpenAI o1/o3, DeepSeek R1 behind a single `reasoning` parameter. No lock-in to one provider's SDK.
- **POS-005**: Off-mode invariant preserved — when `chain_of_thought_enabled = false`, the system behaves identically to pre-ADR-0007 state.
- **POS-006**: Forward-looking criteria documented — a future LangGraph adoption decision has clear, pre-agreed triggers; the team won't be debating it from scratch.
- **POS-007**: PII-safe by design — reasoning tokens flow through the same redaction pipeline; no new privacy surface added.

### Negative

- **NEG-001**: Added latency on reasoning-capable model calls — reasoning tokens add wall-clock time before the first content token appears. Mitigated by streaming reasoning to the UI as it arrives.
- **NEG-002**: Token cost — reasoning tokens are billed by providers. Per-feature configurable effort level (`low` / `medium` / `high`) lets the admin tune cost.
- **NEG-003**: Not all OpenRouter models support reasoning — must gracefully degrade when `reasoning` parameter is unsupported. Falls back to standard response (no `reasoning_delta` events emitted).
- **NEG-004**: PII redaction surface area expands — reasoning content may surface real entity names from retrieved chunks that the final answer would have summarized away. Egress guard MUST inspect reasoning chunks identically; this is enforced in the redaction pipeline.
- **NEG-005**: Frontend complexity — new collapsible UI affordance, new SSE event handling, new `messages.reasoning` field in the message tree.
- **NEG-006**: Persistence cost — `messages.reasoning` adds storage. Long reasoning traces from o3 / Claude 4 extended thinking can be tens of KB per turn.

## Alternatives Considered

### LangSmith only (no end-user CoT)

- **ALT-001**: **Description**: Activate LangSmith for backend tracing; do not surface reasoning to the chat UI.
- **ALT-002**: **Rejection Reason**: Solves only the developer-side observability need. End users — the original requesters — would not see CoT in the chat. Half-solution.

### Provider-specific SDK (Anthropic extended thinking only)

- **ALT-003**: **Description**: Bypass OpenRouter for reasoning calls; use Anthropic's `extended_thinking` API directly.
- **ALT-004**: **Rejection Reason**: Couples LexCore to a single provider. Loses the ability to A/B test reasoning quality across Claude / OpenAI / DeepSeek via the existing OpenRouter abstraction. Violates the spirit of ADR-0001's "no version coupling" principle by binding to a provider's proprietary endpoint.

### Prompt-engineered structured reasoning (`<thinking>...</thinking>`)

- **ALT-005**: **Description**: Force any model to emit `<thinking>...</thinking><answer>...</answer>` via system prompt; parse the wrapped sections in post-processing.
- **ALT-006**: **Rejection Reason**: Conflates reasoning with output, requires a brittle parser, breaks structured-output schemas (which expect pure JSON), and is fragile to prompt drift. Provider-native reasoning tokens are first-class; emulating them is regression.

### LangChain (full framework adoption for reasoning paths)

- **ALT-007**: **Description**: Adopt LangChain's `RunnableConfig.callbacks` + streaming for reasoning event emission.
- **ALT-008**: **Rejection Reason**: ADR-0001 forbids framework adoption. LangChain solves chaining, not reasoning observability. The same capability is available via raw OpenRouter without the framework cost.

### LangGraph (stateful agent runtime for reasoning paths)

- **ALT-009**: **Description**: Migrate the chat loop to LangGraph; expose reasoning steps as graph nodes via `astream_events()`.
- **ALT-010**: **Rejection Reason**: LangGraph's value emerges with cyclic loops, multi-agent handoffs, and human-in-the-loop checkpointing — none of which the current linear chat loop has. Migration cost is high; benefit is not yet realized. **Deferred** — see "When to Revisit" triggers T1–T4 above.

### Tool-trace as reasoning proxy

- **ALT-011**: **Description**: Treat existing `tool_start` / `tool_result` SSE events as the observability surface; do not surface model reasoning.
- **ALT-012**: **Rejection Reason**: Tool traces show retrieval steps but not the model's synthesis between/after tool calls. The user wants to see *how the model reasoned*, not just *which tools fired*. Different signal.

## Implementation Notes

- **IMP-001**: Migration `033_message_reasoning.sql` adds `messages.reasoning TEXT NULL` and `system_settings.chain_of_thought_enabled BOOLEAN NOT NULL DEFAULT false`.
- **IMP-002**: `openrouter_service.py` gains a `reasoning_effort` optional parameter on LLM call helpers; when set and the model supports it, pass `reasoning={"effort": <level>}` in the request.
- **IMP-003**: `chat.py` event generator: when `delta.reasoning` is present in a stream chunk, emit `reasoning_delta` SSE event with `{"content": "<token>"}`; when `delta.content` is present, emit existing `delta` event. Mutually exclusive per chunk.
- **IMP-004**: Frontend `useChatState.ts` gains `streamingReasoning: string` state alongside `streamingContent`. On `done`, both are persisted.
- **IMP-005**: `MessageView.tsx` renders the reasoning block as a collapsible `<details>` element, collapsed by default, with an "AI reasoning" label (i18n).
- **IMP-006**: PII redaction integration — `deanonymize_response()` is called on both content AND reasoning streams before they leave the backend. Egress guard scans both. New unit tests verify reasoning redaction.
- **IMP-007**: Per-feature provider override (per ADR-0004 / per `system_settings`) gains `chain_of_thought_provider` and `chain_of_thought_effort` columns to allow A/B testing reasoning across providers.
- **IMP-008**: LangSmith activation: set `LANGCHAIN_TRACING_V2=true`, `LANGCHAIN_PROJECT=lexcore-prod`, then in `openrouter_service.py` wrap the client with `wrap_openai(client)` from `langsmith.wrappers`. Single line of code change.
- **IMP-009**: When the active model does not support reasoning, the OpenRouter response simply omits `delta.reasoning`; no `reasoning_delta` events are emitted; UI falls back to no reasoning block. Graceful degradation.
- **IMP-010**: Cost monitoring — add a new dashboard tile in `dashboard.py` reporting reasoning-token volume per day per model.

## When to Revisit

Re-open this ADR (raise ADR-0008 or supersede this one) when **any** of the following triggers fire:

- **T1**: A BJR or compliance workflow requires multi-agent orchestration (Research → Drafting → Compliance handoffs) with distinct agent state.
- **T2**: A retrieval flow needs cyclic self-correction (search → reflect → re-search) where a single pass is insufficient and the loop must be expressed as graph state.
- **T3**: A workflow requires human-in-the-loop pauses where the *agent itself* awaits approval and resumes with full context.
- **T4**: A long-running workflow must survive container restarts (durable execution); LangGraph, Vercel Workflow DevKit, or Temporal become candidate runtimes.
- **T5**: OpenRouter deprecates the unified `reasoning` parameter or its quality regresses materially.

The first trigger to fire warrants a focused ADR scoping the change at the affected boundary — not a wholesale chat-path rewrite.

## References

- **REF-001**: ADR-0001 — Raw SDK over Framework (this ADR extends without superseding).
- **REF-002**: ADR-0002 — Single-Row System Settings (the `chain_of_thought_enabled` toggle).
- **REF-003**: ADR-0003 — SSE over WebSocket (this ADR adds `reasoning_delta` event to the contract).
- **REF-004**: ADR-0004 — PII Surrogate Architecture (reasoning tokens flow through the same redaction pipeline).
- **REF-005**: OpenRouter `reasoning` parameter — https://openrouter.ai/docs/use-cases/reasoning-tokens
- **REF-006**: Anthropic extended thinking — https://docs.anthropic.com/en/docs/build-with-claude/extended-thinking
- **REF-007**: OpenAI o1/o3 reasoning models — https://platform.openai.com/docs/guides/reasoning
- **REF-008**: LangSmith Python SDK (`wrap_openai`, `@traceable`) — https://docs.smith.langchain.com/observability/how_to_guides/tracing
- **REF-009**: LangGraph documentation (for future-trigger reference) — https://langchain-ai.github.io/langgraph/
- **REF-010**: `Project_Architecture_Blueprint.md` Section 13 — ADR index.
