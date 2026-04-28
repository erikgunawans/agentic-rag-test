---
title: "ADR-0001: Raw SDK over Framework (No LangChain)"
status: "Accepted"
date: "2026-04-28"
authors: "Erik Gunawan Supriatna (LexCore Engineering)"
tags: ["architecture", "decision", "llm", "framework", "sdk"]
supersedes: ""
superseded_by: ""
---

# ADR-0001: Raw SDK over Framework (No LangChain)

## Status

**Accepted** — shipped with v0.1.0 and load-bearing in the chat path.

## Context

LexCore is a Contract Lifecycle Management (CLM) platform with AI-powered chat, document tools, and a hybrid retrieval pipeline. At project inception we had to choose between:

- **A framework approach** — adopt LangChain (and later LangGraph) to compose chains, agents, vector stores, retrievers, and output parsers via pre-built abstractions.
- **A raw SDK approach** — call OpenRouter, OpenAI, and Cohere SDKs directly and build domain-specific service classes (`HybridRetrievalService`, `ToolService`, `EmbeddingService`, `_llm_json()` helper).

The deciding factors were:

- **Predictability matters more than velocity.** The platform handles Indonesian regulatory and contract content where wrong answers carry compliance risk. Hidden behavior in framework abstractions is a liability.
- **Token accounting must be visible.** Cost-sensitive deployment on Railway requires per-call token transparency, which framework call-stacks obscure.
- **Streaming behavior must be controlled end-to-end.** SSE token streaming, tool dispatch interleaving, and the PII redaction pipeline (ADR-0004) need bytes-precise control over what enters and leaves the LLM payload.
- **Version coupling is expensive.** LangChain's release cadence has historically introduced breaking changes; pinning the framework introduces upgrade churn unrelated to our domain.

Counter-considerations that we weighed:

- LangChain provides excellent pre-built integrations (vector stores, document loaders, tools, retrievers).
- LangChain Expression Language (LCEL) offers declarative composition.
- LangGraph provides stateful agent orchestration with checkpointing.

## Decision

Use raw SDK calls (OpenRouter, OpenAI, Cohere) directly and build domain services in plain Python. Do not adopt LangChain or LangGraph. Observability tooling that wraps SDK calls without altering control flow (e.g., LangSmith via `wrap_openai()` or `@traceable`) is **explicitly permitted** under this ADR — it is observation, not orchestration.

## Consequences

### Positive

- **POS-001**: Full visibility into prompts, model parameters, token counts, and streaming chunks at every call site.
- **POS-002**: Zero framework upgrade exposure; SDK upgrades are surgical and scoped.
- **POS-003**: PII redaction (ADR-0004) can wrap OpenRouter calls without fighting framework conventions.
- **POS-004**: Per-feature LLM provider override (entity resolution, missed-scan, fuzzy de-anon, title-gen, metadata) is straightforward — `llm_provider.py` routes by feature without framework callbacks.
- **POS-005**: New developers can read a service file top-to-bottom without learning a DSL.

### Negative

- **NEG-001**: We re-implement primitives (retrievers, output parsers, tool dispatchers) that LangChain provides for free. Initial development cost is higher.
- **NEG-002**: No declarative chain composition; logic is procedural and lives in service classes.
- **NEG-003**: When a new LLM capability ships (e.g., reasoning tokens), we wire it into our SDK code rather than getting it via a framework upgrade. See ADR-0007 for how we handled OpenRouter's `reasoning` parameter.
- **NEG-004**: Multi-agent orchestration with cyclic loops (search → reflect → re-search) becomes laborious. If/when BJR or contract-review workflows demand this, LangGraph at that boundary will need re-evaluation (see "When to Revisit" in ADR-0007).

## Alternatives Considered

### LangChain (full framework adoption)

- **ALT-001**: **Description**: Use LangChain for retrievers, agents, output parsers, and chain composition via LCEL.
- **ALT-002**: **Rejection Reason**: Framework abstraction cost (version coupling, opaque streaming, hidden retries) outweighs saved boilerplate. Once you have `_llm_json()` + `HybridRetrievalService` working, LangChain's primary value is gone.

### LangGraph (stateful agent runtime)

- **ALT-003**: **Description**: Use LangGraph for explicit graph-state agents with checkpointing, branching, and durable execution.
- **ALT-004**: **Rejection Reason**: The current chat loop is linear (classify → tool → respond). LangGraph's value emerges with cyclic loops, multi-agent handoffs, and human-in-the-loop pauses — none of which exist today. Migration cost would not be repaid by current workloads.

### Hybrid (LangChain inside services, raw SDK outside)

- **ALT-005**: **Description**: Adopt LangChain only for retrievers and output parsing while keeping raw SDK at the chat boundary.
- **ALT-006**: **Rejection Reason**: Two LLM-call patterns in one codebase is a maintenance trap. Cognitive load compounds across the team; debugging requires understanding both worlds.

## Implementation Notes

- **IMP-001**: All LLM calls go through `openrouter_service.py`, `openai_service.py`, or `llm_provider.py`. No direct `httpx` or `openai` imports outside these modules.
- **IMP-002**: Structured outputs use the `_llm_json()` helper in `document_tool_service.py`: OpenRouter `response_format={"type": "json_object"}` + Pydantic `model_validate_json()`.
- **IMP-003**: Tool dispatch lives in `tool_service.py::execute_tool()` — no `AgentExecutor` equivalent.
- **IMP-004**: LangSmith observability is enabled via env vars and wrapper utilities; it does not introduce framework code paths and is permitted under this ADR (see ADR-0007 Part A).
- **IMP-005**: When considering a new framework adoption in the future, document the trigger in a follow-up ADR and reference this one.

## References

- **REF-001**: ADR-0007 — Model Chain-of-Thought / Reasoning Observability (extends ADR-0001 by adding LangSmith tracing and OpenRouter `reasoning` param within the raw-SDK envelope).
- **REF-002**: `CLAUDE.md` — "No LangChain, no LangGraph. Raw SDK calls only." (project-level rule).
- **REF-003**: `Project_Architecture_Blueprint.md` Section 13 — original ADR-001 entry.
- **REF-004**: OpenRouter API documentation — https://openrouter.ai/docs
- **REF-005**: LangSmith Python SDK (`@traceable`, `wrap_openai`) — https://docs.smith.langchain.com/
