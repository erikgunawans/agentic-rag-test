---
phase: 13-unified-tool-registry-tool-search-meta-tool
plan: 04
type: execute
wave: 2
depends_on:
  - 13-01
files_modified:
  - backend/app/services/tool_registry.py
  - backend/tests/unit/test_tool_search.py
autonomous: true
requirements:
  - TOOL-02
  - TOOL-03
must_haves:
  truths:
    - "tool_search is registered in the registry as source='native', loading='immediate' so it always appears in the LLM tools array"
    - "tool_search schema is {keyword: str | null, regex: str | null} — both nullable, neither required"
    - "Calling tool_search with both null returns {error: 'either keyword or regex required'}"
    - "Calling tool_search with both keyword and regex set: regex wins, response includes hint='regex wins when both keyword and regex are passed'"
    - "Keyword match is case-insensitive substring search against (name + ' ' + description)"
    - "Regex match uses re.search with re.IGNORECASE; pattern is rejected if longer than 200 chars (catastrophic-backtracking guard)"
    - "tool_search results capped at top 10 with ranking: name match > description match > longer span > shorter; ties broken alphabetically"
    - "Matched tool names are added to the active_set passed by the caller (mutates by reference)"
    - "tool_search itself is excluded from its own results (cannot recursively self-add)"
    - "Result shape: {matches: [<full openai schema>...], hint: str | None, error: str | null}"
  artifacts:
    - path: "backend/app/services/tool_registry.py"
      provides: "tool_search(keyword, regex, active_set, agent_allowed_tools) async function + module-level self-registration of tool_search as a native immediate tool"
      contains: "async def tool_search"
    - path: "backend/tests/unit/test_tool_search.py"
      provides: "Unit tests for keyword, regex, both, neither, ranking, top-10 cap, agent filter, regex safety, active-set mutation"
  key_links:
    - from: "tool_search executor"
      to: "active_set: set[str]"
      via: "matched tool names mutate the set in place"
      pattern: "active_set\\.add\\("
    - from: "tool_search self-registration"
      to: "_REGISTRY['tool_search']"
      via: "register() call at module load"
      pattern: "name=['\"]tool_search['\"]"
---

<objective>
Implement the `tool_search` meta-tool (D-P13-05) that lets the LLM discover deferred-loading tools by keyword or regex. Adds matched tools to a per-request active set (D-P13-04 for the always-on registration; D-P13-05 for the schema and matcher behavior). Self-registers `tool_search` in the registry as `source="native"`, `loading="immediate"` so it always appears in the LLM tools array — but is EXCLUDED from the catalog table rows (the meta-callout line in 13-01's `_CATALOG_HEADER` is the only place it appears in the system prompt).

Purpose: TOOL-02 (LLM can call `tool_search` with keyword/regex; receives full OpenAI schemas; matched tools added to active set for the rest of the turn). TOOL-03 (active set is ephemeral — caller owns lifetime per 13-01's `make_active_set()`; no cross-turn persistence in the registry layer).

Output: ~80-120 LOC additive to `tool_registry.py` + a dedicated test file. Runs in parallel with 13-02 and 13-03 (all three depend only on 13-01).
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/phases/13-unified-tool-registry-tool-search-meta-tool/13-CONTEXT.md
@.planning/phases/13-unified-tool-registry-tool-search-meta-tool/13-PATTERNS.md
@.planning/phases/13-unified-tool-registry-tool-search-meta-tool/13-01-tool-registry-foundation-PLAN.md
@backend/app/services/tool_registry.py

<interfaces>
<!-- From 13-01: register API + _passes_agent_filter + _REGISTRY backing dict. -->

From backend/app/services/tool_registry.py (created by 13-01):
```python
_REGISTRY: dict[str, ToolDefinition]                 # backing store

def register(name, description, schema, source, loading, executor) -> None: ...

def _passes_agent_filter(
    tool: ToolDefinition,
    agent_allowed_tools: list[str] | None,
) -> bool: ...

def make_active_set() -> set[str]: ...
```

The active set is a plain `set[str]` of tool names. Caller (chat.py in 13-05) creates one via `make_active_set()`, passes it to `build_llm_tools` and `tool_search`. Lifetime = SSE event_generator scope.
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Implement tool_search matcher with ranking, regex safety, agent filter, and active-set mutation</name>
  <files>backend/app/services/tool_registry.py, backend/tests/unit/test_tool_search.py</files>
  <read_first>
    - backend/app/services/tool_registry.py (the file as written by 13-01 — confirm `_REGISTRY`, `_passes_agent_filter`, and helper signatures)
    - .planning/phases/13-unified-tool-registry-tool-search-meta-tool/13-PATTERNS.md "Half E" (matcher sketch) and "No Analog Found" (ranking algorithm)
    - .planning/phases/13-unified-tool-registry-tool-search-meta-tool/13-CONTEXT.md §D-P13-05 (two-param schema, regex wins, top-10 cap)
    - <security_threat_model> in the spawn-time context (regex catastrophic-backtracking guard via 200-char pattern length cap)
  </read_first>
  <behavior>
    - Test 1 (keyword): registry has 5 tools (search_documents, query_database, web_search, legal_review, execute_code). `await tool_search(keyword="search", active_set=set())` matches `search_documents` and `web_search` (substring match on name+description), returns them in `matches[]`, mutates `active_set` to contain both names. Returns `hint=None` and no `error` key.
    - Test 2 (regex): same fixture. `await tool_search(regex="^search_")` returns ONLY `search_documents`. Active set mutated. Hint None.
    - Test 3 (both null): `await tool_search()` returns `{"error": "either keyword or regex required", "matches": []}` and does NOT mutate active_set.
    - Test 4 (both passed → regex wins): `await tool_search(keyword="documents", regex="^search_")` matches by regex (only `search_documents`), response includes `hint="regex wins when both keyword and regex are passed"`. Active set contains `{"search_documents"}` only.
    - Test 5 (case-insensitive): `await tool_search(keyword="LEGAL")` matches `legal_review`. `await tool_search(regex="LEGAL")` also matches.
    - Test 6 (top-10 cap): register 15 tools whose names share a common substring "tool_". `await tool_search(keyword="tool_")` returns at most 10 matches. The 5 omitted are alphabetically last.
    - Test 7 (ranking — name > description): registered tools `apple_search` (description="generic") and `banana` (description="this is a search tool"). `await tool_search(keyword="search")` returns `apple_search` BEFORE `banana` (name match outranks description match).
    - Test 8 (ranking — longer span): registered tools `xy_search` (name match span len = 6 chars) and `search` (name match span len = 6 chars). With identical span and identical match-class, ordering breaks alphabetically: `search` before `xy_search`.
    - Test 9 (regex safety — length cap): `await tool_search(regex="A" * 201)` returns `{"error": "regex pattern too long (max 200 chars)", "matches": []}` without invoking `re.search`.
    - Test 10 (regex safety — invalid pattern): `await tool_search(regex="(?P<")` returns `{"error": "invalid regex: ...", "matches": []}` and does NOT raise. Active set untouched.
    - Test 11 (agent filter — plan-checker warning B fix): registry has search_documents (native), legal_review (skill), tool_search (native), restricted_tool (native). `await tool_search(keyword=None, regex=".", agent_allowed_tools=["search_documents"])` returns search_documents (allowed) + legal_review (skill bypass) but NOT restricted_tool. Uses `regex="."` to match any non-empty name — the prior `keyword=".*"` was a literal substring search for the chars `.*`, which no tool name contains, making the assertion vacuous. tool_search excludes itself per Test 12 (independent of the agent filter).
    - Test 12 (self-exclusion): `tool_search` itself is in the registry. `await tool_search(keyword="tool_search")` does NOT include `tool_search` in the matches array (cannot recursively self-add).
    - Test 13 (active_set is mutated by reference): `s = set(); await tool_search(keyword="search", active_set=s); assert "search_documents" in s`.
    - Test 14 (active_set=None safe): `await tool_search(keyword="search", active_set=None)` returns matches but does not crash; the response is the only side-effect channel.
    - Test 15 (self-registration at module load): after `import tool_registry; _clear_for_tests()` then re-registering tool_search via the module's own self-register block (or via `_register_tool_search()` if extracted to a helper for testability), `_REGISTRY["tool_search"].source == "native"`, `loading == "immediate"`, schema's parameters object has `keyword` and `regex` properties both with `type=["string", "null"]`.
  </behavior>
  <action>
    1. In `backend/app/services/tool_registry.py`, append AFTER `build_catalog_block` (end of file at this point):

       ```python
       import re

       _REGEX_MAX_LEN = 200  # Catastrophic-backtracking guard per security_threat_model.
       _SEARCH_RESULT_CAP = 10  # CONTEXT.md §Discretion §tool_search result cap.


       def _score_match(tool: ToolDefinition, query: str, *, is_regex: bool) -> tuple[int, int, str]:
           """Rank a match. Higher tuple sorts first (Python sorts ascending — we negate).

           Returns (match_class, neg_span_len, name_lower) where:
             match_class: 2 if matched in name, 1 if matched only in description, 0 otherwise.
             neg_span_len: -span_length so longer spans sort first under ascending sort.
             name_lower: alphabetical tiebreaker.
           Caller filters out (0, ...) entries before returning matches.
           """
           name = tool.name
           desc = tool.description or ""
           name_lc = name.lower()
           desc_lc = desc.lower()
           if is_regex:
               try:
                   pattern = re.compile(query, re.IGNORECASE)
               except re.error:
                   return (0, 0, name_lc)
               m_name = pattern.search(name)
               m_desc = pattern.search(desc)
               name_match = m_name is not None
               desc_match = m_desc is not None
               span_len = (
                   (m_name.end() - m_name.start()) if m_name
                   else (m_desc.end() - m_desc.start()) if m_desc
                   else 0
               )
           else:
               q = query.lower()
               name_match = q in name_lc
               desc_match = q in desc_lc
               span_len = len(q) if (name_match or desc_match) else 0
           if name_match:
               return (2, -span_len, name_lc)
           if desc_match:
               return (1, -span_len, name_lc)
           return (0, 0, name_lc)


       @traced(name="tool_search")
       async def tool_search(
           *,
           keyword: str | None = None,
           regex: str | None = None,
           active_set: set[str] | None = None,
           agent_allowed_tools: list[str] | None = None,
       ) -> dict:
           """D-P13-05: discover registry tools by keyword (substring) or regex.

           Both null → error. Both passed → regex wins (logged via `hint`).
           Returns {"matches": [<full openai schema>...], "hint": str|None, "error": str|None}.
           Side effect: matched tool names added to `active_set` (mutate by reference).

           Self-exclusion: tool_search never includes itself in matches (D-P13-04).
           Agent filter: D-P13-06 — skill bypass + tool_search always-on (irrelevant
           here because tool_search excludes itself); native/mcp gated by agent.tool_names.
           Regex safety: pattern length capped at 200 chars; re.compile errors return as
           a structured error rather than raising.
           """
           if keyword is None and regex is None:
               return {"matches": [], "hint": None, "error": "either keyword or regex required"}

           hint = None
           if keyword is not None and regex is not None:
               hint = "regex wins when both keyword and regex are passed"

           # Pick query + mode. Regex wins when both passed.
           is_regex = regex is not None
           query = regex if is_regex else keyword
           assert query is not None  # for type-checker; both-null returns early above

           if is_regex:
               if len(query) > _REGEX_MAX_LEN:
                   return {
                       "matches": [], "hint": hint,
                       "error": f"regex pattern too long (max {_REGEX_MAX_LEN} chars)",
                   }
               try:
                   re.compile(query)  # validate before scoring loop
               except re.error as e:
                   return {"matches": [], "hint": hint, "error": f"invalid regex: {e}"}

           candidates: list[tuple[tuple[int, int, str], ToolDefinition]] = []
           for tool in _REGISTRY.values():
               if tool.name == "tool_search":
                   continue  # self-exclusion (D-P13-04)
               if not _passes_agent_filter(tool, agent_allowed_tools):
                   continue
               score = _score_match(tool, query, is_regex=is_regex)
               if score[0] == 0:
                   continue
               # Negate match_class so higher class sorts first; span already negative.
               candidates.append(((-score[0], score[1], score[2]), tool))

           candidates.sort(key=lambda x: x[0])
           top = candidates[:_SEARCH_RESULT_CAP]

           matches = [tool.schema for _, tool in top]
           if active_set is not None:
               for _, tool in top:
                   active_set.add(tool.name)

           return {"matches": matches, "hint": hint, "error": None}
       ```

    2. Add a `_register_tool_search()` helper (extracted for testability — called once at module load, can be re-invoked in tests after `_clear_for_tests()`):

       ```python
       _TOOL_SEARCH_SCHEMA = {
           "type": "function",
           "function": {
               "name": "tool_search",
               "description": (
                   "Find tools in the registry by keyword (case-insensitive substring) "
                   "or regex (Python re.search, IGNORECASE). Returns matching tools' "
                   "OpenAI schemas and adds them to the active set for the rest of the "
                   "current request."
               ),
               "parameters": {
                   "type": "object",
                   "properties": {
                       "keyword": {
                           "type": ["string", "null"],
                           "description": "Plain substring; case-insensitive. Use for casual searches.",
                       },
                       "regex": {
                           "type": ["string", "null"],
                           "description": (
                               "Python re.search pattern; case-insensitive. Patterns longer "
                               "than 200 characters are rejected. Examples: '^kb_', 'search$'."
                           ),
                       },
                   },
                   "required": [],
               },
           },
       }


       def _register_tool_search() -> None:
           """Self-register tool_search as source='native', loading='immediate'.

           Always-on (D-P13-04): the chat.py wiring in 13-05 includes tool_search
           in the LLM tools array on every request when the flag is on, and the
           catalog formatter excludes it from rows so it appears only in the
           meta-callout line.

           The executor adapter exposes the same async tool_search() to the chat
           tool-loop. The loop passes the per-request active_set and (in multi-agent
           mode) the agent's tool_names list as keyword arguments via the registry
           dispatcher in 13-05.
           """
           async def _executor(arguments: dict, user_id: str, context: dict | None = None, **kwargs):
               # context['active_set'] and context['agent_allowed_tools'] are set by
               # the chat.py registry dispatcher in 13-05. Default to None when absent
               # (e.g., direct test invocations).
               ctx = context or {}
               return await tool_search(
                   keyword=arguments.get("keyword"),
                   regex=arguments.get("regex"),
                   active_set=ctx.get("active_set"),
                   agent_allowed_tools=ctx.get("agent_allowed_tools"),
               )
           register(
               name="tool_search",
               description=_TOOL_SEARCH_SCHEMA["function"]["description"],
               schema=_TOOL_SEARCH_SCHEMA,
               source="native",
               loading="immediate",
               executor=_executor,
           )


       # Run self-registration at module load so tool_search is always present in
       # the registry when this module is imported. The chat.py flag-off path never
       # imports this module, so this call is also gated effectively by the flag.
       _register_tool_search()
       ```

    3. Update `_clear_for_tests` (from 13-01) to ALSO call `_register_tool_search()` so tests start with `tool_search` already registered (matches production behavior at module load). Modify the helper:

       ```python
       def _clear_for_tests() -> None:  # pragma: no cover
           """TEST-ONLY — never call from production. Clears registry then re-registers tool_search."""
           _REGISTRY.clear()
           _register_tool_search()
       ```

    4. Create `backend/tests/unit/test_tool_search.py` with the 15 behavior tests above. Use the autouse `_clear_for_tests` fixture.

    5. Test 8 ranking detail: when match_class and span_len are tied, Python's tuple sort breaks ties by the third element (`name_lc`). Verify `sorted(["xy_search", "search"]) == ["search", "xy_search"]` (alphabetical) by registering both and asserting result order.
  </action>
  <verify>
    <automated>cd backend &amp;&amp; source venv/bin/activate &amp;&amp; pytest tests/unit/test_tool_search.py -x -v</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c "^async def tool_search" backend/app/services/tool_registry.py` returns 1.
    - `grep -c "^def _score_match" backend/app/services/tool_registry.py` returns 1.
    - `grep -c "^def _register_tool_search" backend/app/services/tool_registry.py` returns 1.
    - `grep -c "_REGEX_MAX_LEN\s*=\s*200" backend/app/services/tool_registry.py` returns 1.
    - `grep -c "regex pattern too long" backend/app/services/tool_registry.py` returns 1 (length-cap branch).
    - `grep -c "invalid regex:" backend/app/services/tool_registry.py` returns 1 (compile-error branch).
    - `grep -c "regex wins when both keyword and regex are passed" backend/app/services/tool_registry.py` returns 1 (hint string).
    - `grep -c "either keyword or regex required" backend/app/services/tool_registry.py` returns 1 (both-null error).
    - `pytest backend/tests/unit/test_tool_search.py -v` shows all 15 PASSED.
    - `pytest backend/tests/unit/test_tool_registry.py -v` (from 13-01) ALSO passes (the `_clear_for_tests` change must not break those tests). Re-run shows 25/25 passing — and Test 7 from 13-01 ("registry empty at clean module import") may need adjusting: after this plan, `_REGISTRY` is NOT empty at import (tool_search is auto-registered). Update Test 7 in `test_tool_registry.py` to assert `_REGISTRY == {"tool_search": <ToolDefinition>}` instead of `{}`. This is a controlled edit gated by this plan; document the change in 13-04-SUMMARY.md.
    - `cd backend && source venv/bin/activate && python -c "from app.services import tool_registry; print(list(tool_registry._REGISTRY.keys()))"` prints `['tool_search']`.
    - `cd backend && source venv/bin/activate && python -c "from app.main import app; print('OK')"` prints OK.
  </acceptance_criteria>
  <done>tool_search async function implemented with all 5 D-P13-05 requirements (keyword/regex/both/neither/regex-wins), ranking algorithm produces deterministic results, top-10 cap, regex-length and compile-error guards, self-exclusion, active-set mutation, agent filter integration; tool_search self-registers as source=native immediate; 15 behavior tests pass; 13-01's tests still pass after the `_clear_for_tests` update.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| LLM-supplied regex pattern | Untrusted regex flows from the LLM into Python `re.search`. Catastrophic backtracking is the primary attack. |
| LLM-supplied keyword | Untrusted substring; less attack surface (just a `.lower()` and `in` check). |
| active_set mutation | tool_search mutates a set owned by the caller. Caller must own the set's lifetime. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-13-04-01 | Denial of Service | Catastrophic-backtracking regex (e.g. `(a+)+$` on long input) | mitigate | Hard length cap at `_REGEX_MAX_LEN = 200` chars per security_threat_model. Patterns longer than 200 chars return a structured error before `re.compile` runs. Patterns ≤ 200 chars are scanned against tool names/descriptions which are also bounded (typically < 200 chars), bounding worst-case backtracking. Secondary mitigation: `re.compile` errors are caught and returned as a structured error (no exception leakage). |
| T-13-04-02 | Denial of Service | Compiled regex re-compiled per tool in scoring loop | accept | The scoring function compiles once via `pattern = re.compile(...)` inside `_score_match`. With 200-char limit and a few dozen tools per request, the per-request cost stays well under 10ms. If profiling later shows this is hot, hoist the compile to outside the loop (single-line refactor, no API change). |
| T-13-04-03 | Tampering | LLM tries to use tool_search to recursively register itself or to elevate its own access | mitigate | Self-exclusion: `if tool.name == "tool_search": continue` filters tool_search from its own results. Active-set mutation only adds existing registered tool names — never registers new tools. Calling tool_search via the executor cannot bypass `_passes_agent_filter` (called for every candidate). |
| T-13-04-04 | Information Disclosure | tool_search reveals tools the agent should not see | mitigate | `agent_allowed_tools` filter applied in the candidate loop via `_passes_agent_filter`. Multi-agent context (chat.py 13-05) passes the active agent's `tool_names`; single-agent passes None (no filter). Skills always pass (skill bypass), tool_search self-excludes — no leakage. |
| T-13-04-05 | Tampering | Active-set leaks across requests | mitigate | tool_search NEVER creates an active set — it only mutates one passed by the caller. Caller owns the set's lifetime (closure inside `event_generator` per Plan 13-05). When `active_set=None`, no mutation happens (matches+hint are the only outputs). |
| T-13-04-06 | Repudiation | LLM exploits "regex wins" hint silently | accept | Hint is logged in the response payload (visible in chat history and SSE event traces). The LLM sees the hint inline and operators see it in stored tool_calls JSONB. |
</threat_model>

<verification>
- All 15 tests in `test_tool_search.py` pass.
- 25 tests in `test_tool_registry.py` (from 13-01, with the one Test 7 update for the new "tool_search auto-registered" baseline) pass.
- `python -c "from app.services import tool_registry; assert 'tool_search' in tool_registry._REGISTRY; print('OK')"` prints OK.
- `python -c "import asyncio; from app.services import tool_registry; r = asyncio.run(tool_registry.tool_search()); assert r['error'] == 'either keyword or regex required'; print('OK')"` prints OK.
- Full app import: `python -c "from app.main import app; print('OK')"` prints OK.
- Regex DoS smoke test: `python -c "import asyncio, time; from app.services import tool_registry; t=time.time(); r=asyncio.run(tool_registry.tool_search(regex='A'*250)); assert 'too long' in r['error']; assert time.time()-t < 0.1; print('OK')"` prints OK.
</verification>

<success_criteria>
- `tool_search` registered as `source="native"`, `loading="immediate"` and present in `_REGISTRY` at module load.
- Two-param schema enforced: `{keyword: str | null, regex: str | null}`, both nullable.
- Both-null → structured error response.
- Both-set → regex wins + `hint` in response.
- Keyword: case-insensitive substring against `name + ' ' + description`.
- Regex: `re.search` with `re.IGNORECASE`; 200-char length guard; compile errors caught.
- Top-10 cap with deterministic ranking (name > description; longer span > shorter; alphabetical tiebreaker).
- Self-exclusion (tool_search never matches itself).
- Agent filter integration (skill bypass, tool_search always-on, native/mcp gated by name) via shared `_passes_agent_filter`.
- Active-set mutation by reference; `active_set=None` is safe.
- TOOL-02: ✓ (LLM can call tool_search, receives matches + active set updated).
- TOOL-03: ✓ (active set is caller-owned; no cross-request persistence in tool_registry layer).
</success_criteria>

<output>
After completion, create `.planning/phases/13-unified-tool-registry-tool-search-meta-tool/13-04-SUMMARY.md` summarizing:
- tool_search signature and result shape
- Self-registration behavior (always-on, excluded from catalog rows)
- Ranking algorithm specifics (match_class > span > alphabetical)
- Regex safety guards (200-char cap, compile-error catch)
- Test count (15 in test_tool_search.py + Test 7 update in test_tool_registry.py)
- Note that chat.py is not yet wired (13-05) — the executor reads active_set / agent_allowed_tools from `context` dict, which 13-05 must populate.
</output>
