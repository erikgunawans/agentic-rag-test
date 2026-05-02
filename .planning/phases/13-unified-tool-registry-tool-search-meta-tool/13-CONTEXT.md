# Phase 13: Unified Tool Registry & `tool_search` Meta-Tool - Context

**Gathered:** 2026-05-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Refactor LexCore's static 14-tool injection into a dynamic registry that holds native + skill + MCP tools and exposes them via a compact catalog (≤50 entries, ~500 tokens) plus a `tool_search` meta-tool. This is the foundation phase for v1.2's tool-calling stack — Phase 14 (sandbox HTTP bridge) and Phase 15 (MCP client) build on the registry produced here.

**Deliverables:**
1. `backend/app/services/tool_registry.py` — NEW module. Owns `ToolDefinition` dataclass/Pydantic, `dict[str, ToolDefinition]` backing store, `register(name, description, schema, source, loading, executor)` API, `tool_search(keyword, regex)` matcher, `build_catalog_block(active_agent_allowed_tools)` formatter, active-set state for the request lifetime.
2. `backend/app/services/tool_service.py` patch — minimal hook-in: at app startup (or first chat call), enumerate `TOOL_DEFINITIONS` and call `tool_registry.register()` once per native tool; `executor` callable for natives delegates back into `ToolService.execute_tool(name, args, …)`. Existing `TOOL_DEFINITIONS` list and `execute_tool` switch stay untouched (adapter wrap, D-P13-01).
3. `backend/app/services/skill_catalog_service.py` patch / replacement — when `TOOL_REGISTRY_ENABLED=true`, skills register as first-class tools (D-P13-02) instead of producing a separate `## Your Skills` block. The unified catalog block (D-P13-03) replaces the prior skill catalog block at the same prompt position.
4. `backend/app/routers/chat.py` patch — single-agent path: when `TOOL_REGISTRY_ENABLED=true`, build the system prompt's catalog from `tool_registry.build_catalog_block(...)` instead of `build_skill_catalog_block()`, build the LLM `tools` array from native + active-set instead of `tool_service.get_available_tools()`. Multi-agent path: same wiring but post-filtered by `agent.allowed_tools`. When flag is `false`, both paths take the legacy path byte-identically (TOOL-05).
5. `tool_search` registered as a native tool (`source="native"`, `loading="immediate"`). Always-on regardless of agent.
6. `backend/app/config.py` — add `tool_registry_enabled: bool = False` (env var `TOOL_REGISTRY_ENABLED`). Defaults `false` so v1.1 behavior is preserved out of the box.

**Out of scope (explicitly deferred):**
- Sandbox HTTP bridge / typed Python stubs — Phase 14 (BRIDGE-*).
- MCP client and MCP-source registration — Phase 15 (MCP-*).
- Per-user catalog pinning, recently-used heuristics, admin UI for the registry — future milestones.
- Auto-detect context window for catalog sizing — CTX-FUT-01.
- Rewriting the existing 14 native tools to call `register()` directly (the adapter wrap explicitly avoids this; native tool definitions stay in `TOOL_DEFINITIONS`).
- Persistent active-set across requests — TOOL-03 explicitly rules this out (ephemeral per-turn).

</domain>

<decisions>
## Implementation Decisions

### Migration Approach (TOOL-04, TOOL-05, TOOL-06)

- **D-P13-01:** **Adapter wrap.** New `backend/app/services/tool_registry.py` wraps native tools by enumerating `TOOL_DEFINITIONS` and registering each one at app startup; the `executor` callable for a native tool delegates back into `ToolService.execute_tool(name, args, user_id, ctx)`. Existing `tool_service.py` (1,283 LOC) is **not** refactored — `TOOL_DEFINITIONS` list and the `execute_tool()` dispatch switch stay byte-identical. Skills + MCP get full registry citizenship (their executors live next to their tool definitions, not in `ToolService`). When `TOOL_REGISTRY_ENABLED=false`, the registry module is **not initialized at all** — `chat.py` skips importing/calling it, giving a true byte-identical fallback (TOOL-05) with zero startup overhead.

- **D-P13-02:** **Skill = first-class tool.** Each enabled skill registers as its own tool in the registry. Tool name = `skill.name`, schema = `{}` (parameterless), `executor` is a small async wrapper that internally runs the existing Phase 8 `load_skill` flow (read instructions from DB, return them as the tool result content) and side-effects nothing else. Phase 8 meta-tools (`load_skill`, `save_skill`, `read_skill_file`) stay registered alongside as `source="native"` (still useful: `save_skill` for creation, `read_skill_file` for file lookup, `load_skill(name=X)` is functionally redundant when the skill is also a first-class tool but kept for backward compatibility / explicit invocation). Catalog interleaves all sources alphabetically (D-P13-03).

### Catalog Format (TOOL-01)

- **D-P13-03:** **Single unified `## Available Tools` table.** One markdown table with columns `| Tool | Source | Description |`, sorted alphabetically by name across all sources. Replaces Phase 8's `## Your Skills` block entirely. Same prompt position as today's skill_catalog block (after `pii_guidance`, mirroring D-P8-01). One anti-speculation guardrail line above the table covers all sources.

- **D-P13-04:** **`tool_search` elevated to meta-callout.** Above the catalog table, a single instruction line:
  > *"Call `tool_search` with a keyword or regex query when you need a tool not listed below."*
  `tool_search` is registered in the registry as `source="native"`, `loading="immediate"` so it's callable, but it is **explicitly excluded from the catalog table** to keep meta- and tool-rows visually separate. The instruction line is the only place it appears in the system prompt.

### `tool_search` Schema (TOOL-02, TOOL-03)

- **D-P13-05:** **Two-param schema: `{keyword: str | null, regex: str | null}`.**
  - `keyword`: case-insensitive substring match against `name + " " + description`.
  - `regex`: Python `re.search(pattern, name + " " + description, flags=re.IGNORECASE)` with the user-supplied pattern. Patterns are not anchored automatically — the LLM controls anchoring (`^foo`, `bar$`, etc.).
  - Both `null` → return error `{"error": "either keyword or regex required"}`.
  - Both passed → `regex` wins (logged as a hint to the LLM in the response).
  - Result shape per PRD: returns full OpenAI tool schemas inline AND adds matched tools to the active set for the rest of the request (TOOL-03 — ephemeral per-turn).
  - Phase 14 bridge stub mapping (foreshadowed): `def tool_search(keyword: str | None = None, regex: str | None = None) -> list[dict]`.

### Multi-Agent Integration

- **D-P13-06:** **Registry applies to multi-agent.** Both the catalog block and `tool_search` results are post-filtered by the active agent's `allowed_tools` when `agents_enabled=true`. `tool_search` is special-cased as **always-on** for any agent (does not need to appear in each agent's `allowed_tools`). Skills are **also bypass-allowed** — skills are user-scoped (per `auth.uid()`), not agent-scoped, so it makes no sense to whitelist `legal-review` per-agent. MCP tools, when registered in Phase 15, will be added to relevant agents' `allowed_tools` by name (likely via a startup hook that pushes `mcp:*` patterns or explicit names).
  - Concretely: catalog filtering = `[t for t in registry if t.source in ("skill",) or t.name == "tool_search" or t.name in agent.allowed_tools]` (skills always pass; tool_search always passes; everything else gated).
  - tool_search results filtered with the same predicate.

### Claude's Discretion (planner-handled)

- **Module location** — `backend/app/services/tool_registry.py` (new file, ~200-400 LOC expected). A `backend/app/registry/` package is overkill for v1.2. Co-locating with `tool_service.py` as a class inside it would bloat the already-1,283-LOC file.
- **`ToolDefinition` shape** — Pydantic model with fields `name: str`, `description: str`, `schema: dict` (OpenAI tool-call shape), `source: Literal["native", "skill", "mcp"]`, `loading: Literal["immediate", "deferred"]`, `executor: Callable[..., Awaitable[dict | str]]`. Pydantic for consistency with PROJECT.md's "Pydantic for structured outputs" convention.
- **Skill registration timing** — per-request DB query mirroring Phase 8's `build_skill_catalog_block` pattern (chat.py:491). Skills are re-registered fresh on every chat request from the user's RLS-scoped client; ~5-20ms added latency is acceptable. Avoids stale-skill problems and skill mutation invalidation complexity. (User chose "Next area" before drilling this; locked here as the obvious default consistent with prior phases.)
- **Active-set storage** — closure variable scoped to the SSE `event_generator()` in `chat.py`. No `RequestContext` object, no `contextvars`. Lifetime = until the SSE stream closes (matches PRD's "current conversation turn").
- **Catalog overflow (>50 tools)** — alphabetical first 50 with footer line `Showing 50 of N tools. Call tool_search with a keyword to find more.` (Phase 8 D-P8-07 pattern).
- **Description-column truncation** — hard truncate at 80 chars + ellipsis. Tool authors must write tight one-liners. Predictable token budget per row (~25 tokens).
- **`tool_search` result cap** — top 10 matches by relevance. Relevance: name match outranks description match; longer span outranks shorter; ties broken alphabetically.
- **Catalog refresh** — built fresh on every chat request (no cache). Token cost is negligible (~500 tokens of string formatting); avoids cache-invalidation complexity when skills change.
- **`TOOL_REGISTRY_ENABLED` runtime toggle** — env-var only for v1.2 (set in Railway / `.env`, restart required to flip). Migration to `system_settings` DB toggle parallels the v1.0 `pii_redaction_enabled` migration but isn't worth it before there's a reason. Future enhancement.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Primary Specification

- `docs/superpowers/PRD-advanced-tool-calling.md` §Feature 3 (lines 91-126) — Unified Tool Registry + Search. Locks: ≤50-entry catalog, `tool_search` returns full schemas + adds to active set, regex matching on name+description, single `dict[str, ToolDefinition]` backing store, `register()` accepts 6 params, `TOOL_REGISTRY_ENABLED=false` byte-identical fallback, native = startup/immediate, skill = DB-load/deferred, MCP = connect/deferred.
- `docs/superpowers/PRD-advanced-tool-calling.md` §New Configuration (line 216) — `TOOL_REGISTRY_ENABLED` flag definition.

### Requirements & Roadmap

- `.planning/REQUIREMENTS.md` §TOOL-01..06 (lines 30-37) — All six locked requirements covered by this phase.
- `.planning/REQUIREMENTS.md` §Future Requirements (line 64) — TOOL-related items deferred (none for TOOL-* directly; CTX-FUT-* is for Phase 12).
- `.planning/REQUIREMENTS.md` §Out of Scope (lines 80-93) — "Backwards-incompatible behavior when feature flags off" is a hard constraint mapped to TOOL-05 / D-P13-01.
- `.planning/ROADMAP.md` §Phase 13 — 5 success criteria (authoritative scope anchor).

### Prior Phase Decisions (binding)

- `.planning/phases/08-llm-tool-integration-discovery/08-CONTEXT.md` — D-P8-01..04 catalog injection pattern (binding for D-P13-03 placement); D-P8-05 markdown table format (now extended to source column); D-P8-06 alphabetical ordering (preserved); D-P8-07 cap-overflow footer (reused). D-P8-04 (skill tools always registered unconditionally) preserved by D-P13-02.
- `.planning/phases/11-code-execution-ui-persistent-tool-memory/11-CONTEXT.md` — D-P11-08 `ToolCallRecord` shape with `tool_call_id` + `status` fields. Every `executor` callable in the registry MUST produce records in this shape (or rely on the existing `_run_tool_loop` to wrap their output into a `ToolCallRecord`).

### Codebase Conventions & Architecture

- `.planning/codebase/ARCHITECTURE.md` §Flow 1 — Chat with tool-calling and SSE streaming. Names every integration point this phase touches (`chat.py:108-161` `_run_tool_loop`, `tool_service.py` god-node, `agent_service.py` per-agent tool subsetting).
- `.planning/codebase/STRUCTURE.md` §"New chat tool" — Existing pattern for adding a tool (append to `TOOL_DEFINITIONS` + dispatch branch in `execute_tool`). Phase 13 wraps this pattern, doesn't replace it.
- `.planning/codebase/CONVENTIONS.md` — Pydantic model patterns, async service skeleton.
- `CLAUDE.md` — "No LangChain, no LangGraph. Raw SDK calls only." (project constraint locked since v1.0)

### Privacy / Egress

- `backend/app/services/redaction/egress.py` — Privacy invariant: bridge calls and tool calls must respect the egress filter. Registry's `executor` callables that touch cloud LLMs (e.g., a hypothetical future `summarize_with_llm` skill) must route through this filter. Locked from PROJECT.md "Privacy invariant".

### Code Integration Points (must read)

- `backend/app/services/tool_service.py` — `TOOL_DEFINITIONS` list (line 35), `class ToolService` (line 387), `execute_tool()` dispatch switch. Phase 13 wraps but does NOT modify.
- `backend/app/services/skill_catalog_service.py` (112 LOC) — Existing `build_skill_catalog_block(user_id, token)` from Phase 8. Phase 13 either deprecates this in favor of `tool_registry.build_catalog_block()` when flag is on, or extends it to handle the unified table format.
- `backend/app/routers/chat.py` — System prompt assembly (~L491 single-agent, ~L437 multi-agent), tool injection (~L408 `tool_service.get_available_tools(...)`). Phase 13 patches both call sites with `if settings.tool_registry_enabled` branches.
- `backend/app/services/agent_service.py` — Agent registry; `agent.allowed_tools` list per agent. Phase 13 reads this for filtering (D-P13-06).
- `backend/app/config.py` — Pydantic Settings. Phase 13 adds `tool_registry_enabled: bool = False`.
- `backend/app/models/tools.py` — `ToolCallRecord`, `ToolCallSummary`. Phase 13 may add a `ToolDefinition` model here OR inside `tool_registry.py` (planner discretion; placing it in `models/tools.py` is more discoverable).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- **`TOOL_DEFINITIONS` list (`tool_service.py:35`)** — Source of truth for the 14 native tools. Each entry is already an OpenAI tool-call schema dict with `type: "function"`, `function: {name, description, parameters}`. Phase 13 enumerates this list and calls `register()` per entry — zero schema rewriting.
- **`ToolService.execute_tool()` dispatch (`tool_service.py:387+`)** — Native executors stay here. Registry's per-native `executor` is `lambda args, ctx: tool_service.execute_tool(name, args, ctx.user_id, ctx)` — a thin closure.
- **`build_skill_catalog_block()` (`skill_catalog_service.py:112` LOC total)** — Phase 8's table-rendering helper. Phase 13's `build_catalog_block()` is a generalization: same markdown shape, more sources, source column added. Reuse the row-truncation logic and the alphabetical sort.
- **System prompt append pattern (`chat.py:491`)** — `SYSTEM_PROMPT + pii_guidance + skill_catalog`. Phase 13 swaps `skill_catalog` for `tool_registry_catalog` when flag is on.
- **`agent.allowed_tools` (`agent_service.py`)** — Per-agent tool subset. Phase 13 reuses unchanged for D-P13-06 filtering.
- **`get_supabase_authed_client(token)` (`database.py`)** — RLS-scoped client used by Phase 8 to fetch user skills. Phase 13's per-request skill registration uses the same client.

### Established Patterns

- **Feature flags via `config.py` (Pydantic Settings)** — `pii_redaction_enabled`, `agents_enabled`, `sandbox_enabled` are existing flags. `tool_registry_enabled` follows the exact same pattern (env var → Pydantic field → branch in chat.py). Default `False` matches v1.0/v1.1 safe-off pattern.
- **Adapter wrapping for new abstractions** — Phase 11 D-P11-08 added optional fields to `ToolCallRecord` rather than renaming `output → result`. Phase 13's adapter wrap follows the same low-blast-radius posture.
- **Dispatch lookups are O(1) dict access** — Pydantic `ToolDefinition` lookups by name match `TOOL_DEFINITIONS` linear scan today; small but real win when tool count grows.
- **Per-request DB freshness for user-scoped data** — Phase 8's `build_skill_catalog_block` queries skills on every chat call. Same pattern for skill registration in Phase 13. No skill-mutation invalidation logic needed.
- **Egress filter intercepts all outbound LLM payloads** — Defense-in-depth from v1.0. Registry doesn't bypass it (executors that talk to cloud LLMs use the same `openrouter_service` / OpenAI-compatible APIs that already route through egress).

### Integration Points

- **`backend/app/services/tool_registry.py`** — NEW file. Owns `ToolDefinition`, registry singleton, `register()`, `tool_search()` matcher, `build_catalog_block()`, active-set context. Estimated 250-400 LOC.
- **`backend/app/routers/chat.py`** — Two existing branches (single-agent ~L491, multi-agent ~L437) gain `if settings.tool_registry_enabled:` branches that call into the registry; `else` keeps the existing call to `build_skill_catalog_block()` + `tool_service.get_available_tools()`.
- **`backend/app/services/tool_service.py`** — One bootstrap hook at module load (or first-call lazy init): enumerate `TOOL_DEFINITIONS` → `tool_registry.register(...)` once. Wrapped in `if settings.tool_registry_enabled:` so v1.1 path doesn't pay even the registration cost.
- **`backend/app/services/agent_service.py`** — Add a small helper `should_filter_tool(tool_def, agent)` that encapsulates D-P13-06's special-case logic (skill bypass, tool_search always-on, MCP gated). Single source of truth for the filter predicate.
- **`backend/app/config.py`** — Add `tool_registry_enabled: bool = False` field.
- **Tests** — New `backend/tests/unit/test_tool_registry.py` (registry mechanics: register, search, catalog rendering, active-set lifecycle, agent filtering); patch `backend/tests/api/test_chat_*.py` to exercise both flag-on and flag-off paths (TOOL-05 byte-identical assertion: same response shape and tool_calls when flag flips).

</code_context>

<specifics>
## Specific Ideas

- **Adapter-wrap is non-negotiable for v1.2** — the existing 14 tools have downstream consumers (multi-agent, RAG eval suite, document_tool_service indirectly) and a big-bang refactor risks regressions across the platform. The registry is purely additive when flag is off.
- **`tool_search` is a meta-callout, not a catalog row** — strong intent that the LLM treats it as a discovery primitive, not a regular tool. Catalog rows are "things you might call"; `tool_search` is "how you find more things to call".
- **Two-param `tool_search` schema (keyword OR regex)** is more LLM-readable than a single magic-syntax `query` param. Schema descriptions make the choice explicit ("`keyword` for plain substrings; `regex` for patterns like `^kb_` or `search$`").
- **Skill-as-first-class is the ambitious choice** — Phase 14's bridge generates Python stubs per active tool. With first-class skills, an LLM can call `legal_review()` directly inside sandbox code after `tool_search` activates it. With `load_skill`-only, sandbox code can't easily run a skill workflow.
- **Multi-agent gets the registry** — single-agent and multi-agent should not diverge on tool semantics; both go through the registry when flag is on, both fall back to legacy when flag is off.
- **`skill_catalog_service.py` will likely be deprecated for the registry path** — when `TOOL_REGISTRY_ENABLED=true`, `build_skill_catalog_block()` is no longer called; the unified `tool_registry.build_catalog_block()` covers skills. The legacy function stays to support flag-off mode (TOOL-05). Planner: do NOT delete `skill_catalog_service.py`.

</specifics>

<deferred>
## Deferred Ideas

- **`TOOL_REGISTRY_ENABLED` migrated to `system_settings` DB toggle** — like `pii_redaction_enabled` was migrated in v1.0. Defer until there's a reason (admin needs to flip without redeploy). For v1.2 the env-var-with-restart cycle is fine.
- **Per-user pinned tools / recently-used heuristics in catalog ordering** — could replace strict alphabetical when tool count exceeds 50. Defer until catalog overflow is observed in production.
- **Admin UI for the registry** — view registered tools, source breakdown, last-search hits. Future-milestone observability.
- **Source-prefixed tool names (`native:search`, `skill:legal-review`, `mcp:github_search`) for collision safety** — current model is first-write-wins with an error on duplicate. If MCP servers in Phase 15 produce naming collisions with natives, revisit.
- **Catalog cache with TTL invalidation on skill mutation** — current pattern is per-request fresh. Add a cache only if profiling shows the per-request DB query is hot.
- **Auto-sized catalog cap based on remaining context window** — currently hard-coded to 50 / ~500 tokens. Could dynamically expand if `LLM_CONTEXT_WINDOW` (CTX-03 from Phase 12) is large. Defer.
- **`ToolDefinition` serialization for multi-instance Railway scaling** — registry is per-process today. If the platform scales to multiple replicas with stateful active sets, this becomes a concern. Same family as the D-31 deferred async-lock issue.
- **Removing `load_skill` meta-tool entirely** — once D-P13-02 ships, `load_skill(name=X)` is redundant with calling `X()` directly. Keep it for backward compatibility through v1.2; consider removal in a future milestone.
- **Two more gray areas the user explicitly chose not to drill into:**
  - Skill registration timing (per-request vs startup+invalidate vs hybrid TTL cache) — defaulted to per-request.
  - tool_search result cap and active-set scope — defaulted to top 10 / end-of-request.

### Reviewed Todos (not folded)
None — `gsd-sdk query todo.match-phase 13` returned 0 matches.

</deferred>

---

*Phase: 13-Unified Tool Registry & `tool_search` Meta-Tool*
*Context gathered: 2026-05-02*
