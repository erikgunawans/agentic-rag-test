---
title: "ADR-0008: Internal-First Information Retrieval (Web Search Opt-In)"
status: "Accepted"
date: "2026-04-28"
authors: "Erik Gunawan Supriatna (LexCore Engineering)"
tags: ["architecture", "decision", "retrieval", "web-search", "tools", "privacy", "compliance", "uu-pdp"]
supersedes: ""
superseded_by: ""
---

# ADR-0008: Internal-First Information Retrieval (Web Search Opt-In)

## Status

**Accepted** — shipped 2026-04-28 as v0.4.0.0. Migration `033_web_search_toggle.sql` applied. Backend integration tests passing against production. Replaces the prior auto-selected web search behavior with explicit 3-layer opt-in.

## Context

LexCore is an Indonesian legal AI platform handling regulatory and contract content for clients with strong data-residency and confidentiality expectations under **UU PDP (Undang-Undang Pelindungan Data Pribadi)**. Today the chat path supports three tools registered in `tool_service.py`:

- `search_documents` — internal RAG over user-uploaded documents (vector + FTS + RRF + rerank).
- `query_database` — structured queries against internal tables (clauses, templates, obligations, BJR records).
- `web_search` — Tavily-powered external web search.

The Research Agent (selected via `agent_service.classify_intent()`) is currently free to choose any of the three tools based on its assessment of the query. This means **a web search can fire without explicit user opt-in**, which has three problems:

1. **Privacy / data exfiltration.** Search queries (and the LLM prompts that constructed them) are sent to a third-party API outside the LexCore data boundary. Even when the redaction pipeline (ADR-0004) anonymizes the LLM payload, the *outbound search query string* may carry contextual fragments that surface real entity names or sensitive context.
2. **Trust and predictability.** Legal users want to know whether an answer came from their own document corpus or the open internet. Auto-selected web search blurs that line and undermines auditability.
3. **Cost and latency.** Every web search adds API cost and seconds of latency. When internal data is sufficient, web search is wasted spend.

The user request that triggered this ADR was: *"I want the system to look for data inside the company first. Then if I want to use web search, I'll change the toggle."*

Considerations that shaped the decision:

- **Toggle scope.** Single toggles (admin-only or per-message-only) are too coarse. Different stakeholders need different granularity.
- **Default state.** Web search must default OFF — it's an exception, not a baseline.
- **Agent compatibility.** The Research Agent must respect the toggle state when planning tool use. It cannot propose a tool that the dispatcher will refuse to execute.
- **PII pipeline interaction.** When web search IS enabled, the PII redaction (ADR-0004) must extend its egress guard to outbound search queries, not just LLM payloads.
- **Audit trail.** Every web search invocation must record the toggle state at the time of invocation for compliance review.
- **Citation UX.** Web-sourced and internal-sourced citations must be visually distinct so users always know the provenance of an answer.

## Decision

**Adopt internal-first retrieval as an architectural principle**, with web search gated behind a three-layer toggle.

### Principle

Information retrieval defaults to internal company data sources only (`search_documents`, `query_database`). The `web_search` tool is **never auto-selected** by the agent classifier and is **never registered** with the tool dispatcher unless an explicit toggle path enables it for the current request.

### Three-Layer Toggle Model

| Layer | Storage | Default | Purpose |
|---|---|---|---|
| **L1 — System** | `system_settings.web_search_enabled BOOLEAN` | `true` | Admin-level kill switch. When `false`, web search is disabled platform-wide regardless of user or message settings. Used for compliance-strict deployments. |
| **L2 — Per-user default** | `user_preferences.web_search_default BOOLEAN` | `false` | Each user's preferred starting state. Defaults to OFF (internal-first). User can flip in `/settings`. |
| **L3 — Per-message override** | Request-level field on `POST /chat/stream` body | (inherits L2) | UI toggle in the chat composer ("🌐 Web") that overrides the per-user default for a single message. |

Effective state per request: `effective = L1 AND (L3 if provided else L2)`. If the system toggle is off (L1 = false), web search is unavailable regardless of L2/L3.

### PII Pipeline Extension (extends ADR-0004)

When web search is effective for a request and `pii_redaction_enabled = true`, the redaction pipeline's **egress guard MUST inspect outbound search queries** with the same rigor as LLM payloads. Outbound queries containing registry-known PII are blocked or anonymized using the same surrogate substitution. This must work for any current or future external-API tool — `web_search` is the first; the principle generalizes.

### Citation UX

Search results returned by `web_search` are tagged with a distinct source type (`source: "web"` vs. `source: "internal"`) so frontend rendering can apply different citation badges (e.g., a globe icon for web, a document icon for internal). This is required for audit and trust.

## Consequences

### Positive

- **POS-001**: Default behavior is privacy-preserving and predictable — internal data only, no surprise external API calls.
- **POS-002**: Three-layer toggle matches industry pattern (Perplexity Pro, ChatGPT Search, Claude with web tool) and lets each stakeholder control their own concern.
- **POS-003**: Compliance posture is configurable — admin-strict deployments can turn off web search platform-wide without code change.
- **POS-004**: PII surface area for outbound queries is constrained — egress guard explicitly inspects search queries, closing a gap where ADR-0004 only covered LLM payloads.
- **POS-005**: Audit trail captures toggle state at each `web_search` invocation, supporting post-hoc compliance review.
- **POS-006**: Cost and latency reduced for the common case (internal-first) without sacrificing capability for the long-tail case (research questions needing web context).
- **POS-007**: Citation provenance becomes explicit — users always know whether an answer came from their corpus or the internet.

### Negative

- **NEG-001**: Three-layer logic adds complexity to tool registration. The dispatcher must compute effective toggle state on every request, not at app startup.
- **NEG-002**: Agent classifier (`classify_intent()`) needs awareness of toggle state — must not propose `web_search` when the effective toggle is off, or its plan will be silently rejected.
- **NEG-003**: User education load — users will occasionally ask "why didn't it search the web?" and need to understand the toggle. Mitigated by clear UI affordance and tooltip.
- **NEG-004**: Migration required — `user_preferences.web_search_default` and `system_settings.web_search_enabled` columns. Per ADR-0002 migration template.
- **NEG-005**: PII egress guard for search queries is *new code* — must be tested as rigorously as the existing LLM-payload egress guard. Adds redaction unit-test surface.
- **NEG-006**: When the toggle is off mid-conversation, the assistant cannot reach out for fresh information — there's no graceful fallback, only a flat "I don't have external access for this query" response. UX must handle this clearly.

## Alternatives Considered

### Always-On Web Search (Current State)

- **ALT-001**: **Description**: Keep current behavior — Research Agent freely chooses among `search_documents`, `query_database`, `web_search` based on query type.
- **ALT-002**: **Rejection Reason**: Privacy by default is violated. Outbound search queries can leak context. User cannot predict provenance. Audit requires post-hoc inspection of every chat to determine if web was used. Unacceptable for compliance-grade legal platform.

### Always-Off Web Search (Remove the Tool)

- **ALT-003**: **Description**: Drop `web_search` from the tool catalog entirely. Force all answers to come from internal data.
- **ALT-004**: **Rejection Reason**: Removes a useful capability. Some queries genuinely require fresh external context (regulatory updates, news on a counterparty). Better to gate than remove.

### System-Only Toggle

- **ALT-005**: **Description**: Single admin toggle in `system_settings.web_search_enabled`. No per-user or per-message granularity.
- **ALT-006**: **Rejection Reason**: Not granular enough. Either everyone gets web search or no one does. Mismatch with how legal users actually work — sometimes you want internal-only, sometimes you want internet research, often within the same conversation.

### Per-Message Only

- **ALT-007**: **Description**: A composer toggle (`🌐 Web`) on every message; no admin or per-user layer. Default off.
- **ALT-008**: **Rejection Reason**: Power users who *always* want web search would have to flip the toggle on every message. No way for compliance-strict deployments to disable platform-wide. Lacks the layered defaults that match real workflow patterns.

### Per-User Preference Only

- **ALT-009**: **Description**: A per-user setting in `/settings` that turns web search on or off. No per-message override, no admin toggle.
- **ALT-010**: **Rejection Reason**: User can't toggle per-question — if you usually want internal-only but occasionally need web research, you'd have to navigate to settings each time. Friction. And no admin kill switch.

### Treat Web Search as a Separate Agent (Not a Tool)

- **ALT-011**: **Description**: Promote web search to a "Web Research Agent" alongside the Research Agent; user explicitly invokes by routing.
- **ALT-012**: **Rejection Reason**: Adds agent-orchestration complexity without solving the toggle problem — the user still needs a way to opt into the Web Research Agent. Tool gating is the simpler, more direct mechanism.

## Implementation Notes

> The full implementation plan (UX, schemas, audit fields, acceptance tests) will live in `docs/PRD-Web-Search-Toggle.md`. The notes below are the architectural shape only.

- **IMP-001**: Migration `034_web_search_toggle.sql` adds `system_settings.web_search_enabled BOOLEAN NOT NULL DEFAULT true` and `user_preferences.web_search_default BOOLEAN NOT NULL DEFAULT false`.
- **IMP-002**: `POST /chat/stream` request body gains an optional `web_search: bool | null` field. When `null`, the per-user default is used; when present, it overrides for this message only.
- **IMP-003**: New helper `compute_web_search_effective(system, user_pref, message_override) -> bool` lives in a shared util — invoked from the chat router before tool registration. Returns `system AND (override if not None else user_pref)`.
- **IMP-004**: `tool_service.get_tool_definitions(effective_web_search: bool)` becomes parameterized — `web_search` is included in the catalog only when `effective_web_search = true`. The function signature change is the load-bearing piece.
- **IMP-005**: `agent_service.classify_intent()` receives the effective toggle and is instructed (via prompt) to never propose `web_search` when off. Agent's tool plan is verified against the registered catalog before dispatch — defense in depth.
- **IMP-006**: PII egress guard extension — `tool_redaction.py::redact_tool_input()` already exists; extend it to scan outbound `web_search.input.query` strings against the conversation registry. Add unit tests asserting that registry-known PII in queries is blocked.
- **IMP-007**: Audit logging — every `web_search` invocation calls `log_action(..., action="web_search", details={"query": <redacted-query>, "toggle_state": "system_on/user_default/message_override"})`. Captures the *why* of every external-API call.
- **IMP-008**: Frontend composer adds a `🌐 Web` toggle button — sticky per-thread (remembered for this conversation), but resets to per-user default on new threads. Keyboard shortcut TBD.
- **IMP-009**: Citation badges — `MessageView.tsx` renders a globe icon (web) or document icon (internal) on each citation. Tooltip explains source type.
- **IMP-010**: Admin UI — `AdminSettingsPage.tsx` gains a `web_search_enabled` toggle. Per ADR-0002 / CLAUDE.md gotcha, must be added to BOTH mobile and desktop panels.
- **IMP-011**: User settings — `/settings` page adds `web_search_default` toggle. New `user_preferences` field surfaced via existing `user_preferences` router pattern.
- **IMP-012**: When the effective toggle is OFF and the agent identifies that the query genuinely needs external data, the response should explicitly say "I don't have access to current external information for this query — enable 🌐 Web search if you'd like me to look online." This is a UX decision but worth flagging as part of the architectural contract.

## When to Revisit

Re-open or supersede this ADR when:

- **T1**: A new external-API tool is added to the tool catalog (e.g., Dokmee external sync, Google Drive search). The internal-first principle and PII egress guard generalize to all such tools — verify they apply.
- **T2**: User feedback indicates the three-layer model is too complex; consider collapsing to a simpler scope.
- **T3**: A multi-agent orchestration pattern (per ADR-0007 LangGraph triggers T1) emerges and tool gating moves from request-time to agent-state-time. The toggle semantics may need to live inside the agent state graph rather than at the dispatcher boundary.
- **T4**: Regulatory requirements (UU PDP updates, sectoral rules) mandate stricter or looser default behavior.

## References

- **REF-001**: ADR-0001 — Raw SDK over Framework (tool dispatcher and agent classifier are raw-SDK code paths).
- **REF-002**: ADR-0002 — Single-Row System Settings (the `web_search_enabled` system toggle).
- **REF-003**: ADR-0004 — PII Surrogate Architecture (egress guard extension to outbound search queries).
- **REF-004**: ADR-0007 — Chain-of-Thought Observability (reasoning visible to users will surface tool selection — must consistently show "internal only" vs "web included" in reasoning traces).
- **REF-005**: `backend/app/services/tool_service.py` — current tool registration pattern.
- **REF-006**: `backend/app/services/agent_service.py` — `classify_intent()` agent selection.
- **REF-007**: `backend/app/services/redaction/tool_redaction.py` — existing tool-input/output redaction (will be extended).
- **REF-008**: `docs/PRD-Web-Search-Toggle.md` — implementation plan (to be written when this ADR is accepted).
- **REF-009**: `Project_Architecture_Blueprint.md` Section 13 — ADR index.
- **REF-010**: Tavily API — https://tavily.com/ (current web search provider).
