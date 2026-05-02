# Phase 13: Unified Tool Registry & `tool_search` Meta-Tool - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-02
**Phase:** 13-unified-tool-registry-tool-search-meta-tool
**Areas discussed:** Native tool migration, Catalog format, tool_search input, Multi-agent integration

---

## Native tool migration

### Question 1 — Refactor depth

| Option | Description | Selected |
|--------|-------------|----------|
| Adapter wrap (Recommended) | Keep TOOL_DEFINITIONS + ToolService.execute_tool() as-is. New tool_registry.py wraps natives by enumeration; native executor delegates back. Skills + MCP get full registry citizenship. Lowest blast radius (~50-200 LOC); easiest TOOL-05 fallback (registry purely additive). | ✓ |
| Big-bang refactor | Delete TOOL_DEFINITIONS. All 14 tools call register() at startup. Registry single source of truth; ToolService.execute_tool becomes thin dispatcher. ~600-1000 LOC touched. TOOL-05 needs explicit parallel legacy path. | |
| Two-tier split | Registry handles catalog + tool_search + dispatch lookup. Execution stays in ToolService for ALL sources. Cleanly separates "what's available" from "how to call". Medium blast radius. | |

**User's choice:** Adapter wrap (Recommended)
**Notes:** Locked as D-P13-01. Forces a follow-up question about how skill + MCP interact with the wrap.

### Question 2 — Skill registration model

| Option | Description | Selected |
|--------|-------------|----------|
| Skill = first-class tool (Recommended) | Each enabled skill registers as its own tool. Name = skill.name, schema = {} (parameterless), executor wraps load_skill flow. PRD-literal interpretation. Phase 14 bridge gets clean per-skill stubs. | ✓ |
| Skills stay behind load_skill | Only the three meta-tools (load_skill / save_skill / read_skill_file) register as source='skill'. Phase 8 catalog preserved. Smallest behavior change. | |
| Hybrid surface | Meta-tools register as source='skill'. Individual skills appear in catalog only; their "executor" is a synthetic load_skill(name=X) wrapper. | |

**User's choice:** Skill = first-class tool (Recommended)
**Notes:** Locked as D-P13-02. Implies skills are now directly callable by name (e.g., `legal_review()`); foreshadows clean Phase 14 bridge stubs.

### Continuation

**Q:** More questions about Native tool migration, or move to next area?
**A:** Next area (Recommended).
**Deferred to Claude's discretion:** module location (→ new `tool_registry.py`), flag=false loading behavior (→ registry not loaded), skill-registration timing (→ per-request DB query, Phase 8 pattern).

---

## Catalog format

### Question 1 — Catalog structure

| Option | Description | Selected |
|--------|-------------|----------|
| Single table, source column (Recommended) | One `## Available Tools` markdown table with columns `\| Tool \| Source \| Description \|`, alphabetical across all sources. Replaces Phase 8's `## Your Skills` block entirely. Most LLM-legible. | ✓ |
| Grouped sub-tables | One `## Available Tools` heading with three sub-sections (Native / Skills / MCP), each its own table. More tokens on headings, easier to scan. | |
| Single table, source-grouped sort | Single table, `| Tool | Source | Description |`, sorted by source first, then alphabetical within. Compromise between the above two. | |

**User's choice:** Single table, source column (Recommended)
**Notes:** Locked as D-P13-03.

### Question 2 — `tool_search` surfacing

| Option | Description | Selected |
|--------|-------------|----------|
| Instruction callout above catalog (Recommended) | An instruction line above the table mirrors Phase 8's anti-speculation guardrail. tool_search registered as source='native' but excluded from catalog rows. | ✓ |
| Row in the catalog | tool_search appears as a regular row alongside other tools. Uniform treatment. Risk: LLM may not realize it's special. | |
| Both — callout + row | Maximum redundancy. Useful if the LLM tends to ignore prose. | |

**User's choice:** Instruction callout above catalog (Recommended)
**Notes:** Locked as D-P13-04.

### Continuation

**Q:** More questions about Catalog format, or move to next area?
**A:** Next area (Recommended).
**Deferred to Claude's discretion:** overflow behavior (>50 tools → alphabetical first 50 + footer, Phase 8 D-P8-07 pattern), description-column truncation (→ 80-char hard truncate), exact catalog placement in system prompt (→ same as Phase 8: after pii_guidance).

---

## tool_search input

### Question 1 — Schema shape

| Option | Description | Selected |
|--------|-------------|----------|
| Two params: keyword OR regex (Recommended) | `{keyword: str \| null, regex: str \| null}`. keyword = case-insensitive substring; regex = re.search pattern. Both null = error. Both passed = regex wins. Most explicit; LLM learns from schema descriptions. | ✓ |
| Single query param, auto-detect | `{query: str}`. Backend detects /…/ delimiters as regex; else substring. Compact but requires the LLM to learn the convention. | |
| Single query param, always regex | `{query: str}`. Always re.search. Plain keywords still match literally. Risk: LLM forgetting to escape special chars. | |

**User's choice:** Two params: keyword OR regex (Recommended)
**Notes:** Locked as D-P13-05.

### Continuation

**Q:** More questions about tool_search input, or move to next area?
**A:** Next area (Recommended).
**Deferred to Claude's discretion:** max-result cap (→ top 10 by relevance), tool_result shape (PRD-locked: full schemas inline + active set), active-set lifetime (→ end-of-HTTP-request scope).

---

## Multi-agent integration

### Question 1 — Registry vs `agent.allowed_tools`

| Option | Description | Selected |
|--------|-------------|----------|
| Filter by agent.allowed_tools (Recommended) | Catalog and tool_search results post-filtered by active agent's allowed_tools. tool_search always-on for any agent (special-cased). Multi-agent gets full registry benefit. | ✓ |
| Multi-agent bypasses registry | Even with TOOL_REGISTRY_ENABLED=true, multi-agent uses legacy build_rag_tools(). Two code paths. Multi-agent doesn't get tool_search until a future phase. | |
| Add allowed_sources per agent | New per-agent allowed_sources field combined with allowed_tools as intersection. More expressive but more config surface. | |

**User's choice:** Filter by agent.allowed_tools (Recommended)
**Notes:** Locked as D-P13-06. Skill bypass added (skills are user-scoped, not agent-scoped). MCP tools added by name on connect (Phase 15 problem).

---

## Closing

**Q:** Ready for context, or explore more gray areas?
**A:** Ready for context (Recommended).

## Claude's Discretion

Areas where the user opted to defer to planner/Claude's discretion (recorded in CONTEXT.md `<decisions>` "Claude's Discretion" subsection):

- Module location — new `backend/app/services/tool_registry.py`
- `ToolDefinition` shape — Pydantic model with 6 fields
- Skill registration timing — per-request DB query (Phase 8 pattern)
- Active-set storage — closure variable in SSE `event_generator()`
- Catalog overflow strategy — alphabetical first 50 + footer
- Description-column truncation — 80-char hard truncate
- `tool_search` result cap — top 10 by relevance
- Catalog refresh — built fresh per request, no cache
- `TOOL_REGISTRY_ENABLED` runtime toggle — env-var only for v1.2

## Deferred Ideas

Captured in CONTEXT.md `<deferred>` section. Highlights:

- Migrating `TOOL_REGISTRY_ENABLED` to system_settings DB toggle (parallels v1.0 `pii_redaction_enabled`)
- Per-user pinned tools / recently-used heuristics in catalog ordering
- Admin UI for the registry (view registered tools, source breakdown)
- Source-prefixed tool names for collision safety (deferred until Phase 15 MCP collisions observed)
- Catalog cache with TTL invalidation on skill mutation
- Auto-sized catalog cap based on remaining context window
- ToolDefinition serialization for multi-instance Railway scaling
- Removing `load_skill` meta-tool entirely (post-D-P13-02 redundancy)
