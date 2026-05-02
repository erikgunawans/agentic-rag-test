---
phase: 13-unified-tool-registry-tool-search-meta-tool
plan: 03
type: execute
wave: 2
depends_on:
  - 13-01
files_modified:
  - backend/app/services/skill_catalog_service.py
  - backend/tests/unit/test_skill_catalog_service.py
autonomous: true
requirements:
  - TOOL-04
  - TOOL-05
must_haves:
  truths:
    - "register_user_skills(user_id, token) queries the skills table via RLS-scoped client and registers each enabled skill as source='skill', loading='deferred', schema={parameterless}"
    - "Each skill's executor delegates to the existing Phase 8 load_skill flow (returns the skill instructions string as the tool result)"
    - "register_user_skills is fail-soft: any DB exception logs WARNING and returns silently — the chat flow never breaks because of registry skill registration errors"
    - "The legacy build_skill_catalog_block(user_id, token) is NOT modified — it stays as the flag-off byte-identical fallback (TOOL-05 invariant)"
    - "register_user_skills has zero side effects when the registry is empty for skill names that already exist (first-write-wins from 13-01 prevents double-registration)"
  artifacts:
    - path: "backend/app/services/skill_catalog_service.py"
      provides: "register_user_skills(user_id, token) async helper + _make_skill_executor(name) factory"
      contains: "register_user_skills"
    - path: "backend/tests/unit/test_skill_catalog_service.py"
      provides: "Tests for register_user_skills (success, empty rows, DB error fail-soft, RLS path, executor returns instructions)"
  key_links:
    - from: "backend/app/services/skill_catalog_service.py"
      to: "backend/app/services/tool_registry.py"
      via: "lazy import inside register_user_skills"
      pattern: "from app\\.services import tool_registry"
    - from: "_make_skill_executor"
      to: "ToolService.execute_tool('load_skill', ...)"
      via: "executor closure that calls load_skill internally with name=row.name"
      pattern: "execute_tool\\(\\s*['\"]load_skill['\"]"
---

<objective>
Implement D-P13-02 skill-as-first-class-tool registration: a NEW helper `register_user_skills(user_id, token)` in `skill_catalog_service.py` that queries the user's enabled skills via the RLS-scoped Supabase client and calls `tool_registry.register()` once per skill with `source="skill"`, `loading="deferred"`, `schema={parameterless}`, and an executor that delegates to the existing Phase 8 `load_skill` flow.

The legacy `build_skill_catalog_block(user_id, token)` function (lines 54-112) is left UNTOUCHED — it stays as the byte-identical flag-off fallback (TOOL-05 invariant per CONTEXT.md §Specifics: "do NOT delete `skill_catalog_service.py`").

Purpose: Skills become first-class registry citizens — the LLM can call them by name (e.g., `legal_review()`) once they're in the active set or appear in the catalog, instead of calling the meta-tool `load_skill(name="legal_review")`. Phase 14's bridge stub generation will produce a `legal_review()` Python stub for sandbox code.

Output: ~80-120 LOC of new helpers in `skill_catalog_service.py` + a unit test file. This plan can run in parallel with 13-02 (native adapter) and 13-04 (tool_search). chat.py wiring to actually CALL `register_user_skills` happens in 13-05.
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
@backend/app/services/skill_catalog_service.py
@backend/app/services/tool_service.py

<interfaces>
<!-- From 13-01: register API. From existing skill_catalog_service: pattern to mirror. -->

From backend/app/services/tool_registry.py (created by 13-01):
```python
def register(name, description, schema, source, loading, executor) -> None: ...
def make_active_set() -> set[str]: ...
async def build_catalog_block(*, agent_allowed_tools: list[str] | None = None) -> str: ...
```

From backend/app/services/skill_catalog_service.py (existing — DO NOT modify body, only append):
```python
# Lines 54-112: existing pattern
async def build_skill_catalog_block(user_id: str, token: str) -> str:
    """Phase 8: returns '## Your Skills' block or '' on error/empty.

    Pattern (lines 73-90):
      client = get_supabase_authed_client(token)
      result = (
          client.table("skills")
          .select("name, description")
          .eq("enabled", True)
          .order("name")
          .limit(21)
          .execute()
      )
      rows = result.data or []
    Fail-soft: any exception → log WARNING + return ""
    """
```

From backend/app/services/tool_service.py (existing — for executor delegation pattern):
```python
# load_skill is one of the 14 natives — its dispatch branch reads the skill from DB
# and returns its instructions as the tool_result content. Phase 13 skills reuse
# this delegation rather than re-implementing skill loading logic.
class ToolService:
    async def execute_tool(self, name, arguments, user_id, context=None, *,
                          registry=None, token=None, stream_callback=None) -> dict:
        if name == "load_skill":
            return await self._execute_load_skill(arguments, user_id, ...)
```

From backend/app/database.py (existing):
```python
def get_supabase_authed_client(token: str): ...  # RLS-scoped client
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Add register_user_skills + _make_skill_executor to skill_catalog_service.py with fail-soft DB pattern</name>
  <files>backend/app/services/skill_catalog_service.py, backend/tests/unit/test_skill_catalog_service.py</files>
  <read_first>
    - backend/app/services/skill_catalog_service.py (entire 112 LOC — full body)
    - backend/app/services/tool_service.py lines 35-360 (find the `load_skill` entry in TOOL_DEFINITIONS to copy its description as a baseline)
    - backend/app/services/tool_registry.py (created by 13-01 — confirm `register()` signature and the parameterless schema shape used in tool_search self-registration)
    - backend/tests/unit/test_skill_catalog_service.py (existing test file — for test fixture patterns to mirror)
    - .planning/phases/13-unified-tool-registry-tool-search-meta-tool/13-PATTERNS.md "skill_catalog_service.py PATCH" section (lines starting with "DO NOT MODIFY. Stays as the flag-off catalog builder.")
  </read_first>
  <behavior>
    - Test 1: `await register_user_skills(user_id="u1", token="t1")` with mocked Supabase returning 2 enabled skills produces exactly 2 entries in `tool_registry._REGISTRY` after the call, with `source == "skill"` and `loading == "deferred"`.
    - Test 2: Each registered skill has schema = `{"type": "function", "function": {"name": <skill_name>, "description": <skill_desc>, "parameters": {"type": "object", "properties": {}, "required": []}}}` (parameterless, exact shape).
    - Test 3: With `token=""` (empty string) or `token=None`, `register_user_skills` returns immediately without calling Supabase and without registering anything.
    - Test 4: When the Supabase query raises an exception, `register_user_skills` logs a WARNING (verifiable via `caplog`) and returns silently — does NOT raise to the caller.
    - Test 5: When Supabase returns 0 rows, `register_user_skills` returns silently — `tool_registry._REGISTRY` stays empty (no spurious registration).
    - Test 6: A skill executor's return value matches what `ToolService.execute_tool("load_skill", {"name": <skill_name>}, user_id, context)` returns. Verify via mocking ToolService.execute_tool — assert it is called with `name="load_skill"` and `arguments={"name": <skill_name>}`.
    - Test 7: Calling `register_user_skills` twice with the same skills does NOT duplicate-register (registry's first-write-wins logs WARNING, second call silently ignored — verify count stays at 2).
    - Test 8: `build_skill_catalog_block(user_id, token)` (the legacy function) returns identical output before and after this plan's changes — copy 1-2 representative golden outputs from existing tests to assert byte-identical (TOOL-05 invariant locally for this file).
  </behavior>
  <action>
    1. Open `backend/app/services/skill_catalog_service.py`. Locate the END of the file (after the existing `build_skill_catalog_block` function — line ~112). Append the following helpers WITHOUT modifying any line of the existing function body:

       ```python
       # ---------------------------------------------------------------------------
       # Phase 13 D-P13-02: register skills as first-class registry tools (TOOL-04).
       #
       # The legacy build_skill_catalog_block above is preserved verbatim and remains
       # the catalog builder used when settings.tool_registry_enabled=False (TOOL-05
       # byte-identical fallback). This new helper is invoked by chat.py only when
       # the flag is True (Plan 13-05 wiring).
       # ---------------------------------------------------------------------------
       def _make_skill_executor(skill_name: str):
           """Return an async closure that loads the skill via ToolService.execute_tool.

           Per D-P13-02: skill executors delegate to the existing Phase 8 load_skill
           dispatch — no re-implementation of skill loading logic.
           """
           # Lazy import to avoid a circular import at module load (tool_service ↔
           # skill_catalog_service). Safe because executors are only invoked at
           # request time, well after both modules have finished loading.
           async def _executor(
               arguments: dict,
               user_id: str,
               context: dict | None = None,
               *,
               _name: str = skill_name,
               **kwargs,
           ) -> dict | str:
               from app.services.tool_service import tool_service
               return await tool_service.execute_tool(
                   "load_skill",
                   {"name": _name},
                   user_id,
                   context,
                   **kwargs,
               )
           return _executor


       async def register_user_skills(user_id: str, token: str) -> None:
           """D-P13-02: register every enabled skill for this user as a first-class tool.

           Per-request DB query (CONTEXT.md §Discretion §Skill registration timing):
           skills are re-registered fresh on every chat request from the user's
           RLS-scoped client. ~5-20ms latency is acceptable; avoids stale-skill
           and skill-mutation invalidation complexity.

           Fail-soft: any DB exception logs at WARNING and returns silently. The
           chat flow must never break because of registry skill registration errors.
           """
           if not token:
               return
           try:
               client = get_supabase_authed_client(token)
               result = (
                   client.table("skills")
                   .select("name, description")
                   .eq("enabled", True)
                   .order("name")
                   .execute()
               )
               rows = result.data or []
           except Exception as e:  # noqa: BLE001 — fail-soft per CONTEXT.md
               logger.warning(
                   "register_user_skills failed for user_id=%s: %s", user_id, e
               )
               return
           if not rows:
               return
           # Lazy import: avoid loading the registry module on flag-off code paths
           # that happen to import skill_catalog_service for build_skill_catalog_block.
           from app.services import tool_registry
           for row in rows:
               name = row.get("name")
               if not name:
                   continue
               description = row.get("description") or ""
               schema = {
                   "type": "function",
                   "function": {
                       "name": name,
                       "description": description,
                       "parameters": {
                           "type": "object",
                           "properties": {},
                           "required": [],
                       },
                   },
               }
               tool_registry.register(
                   name=name,
                   description=description,
                   schema=schema,
                   source="skill",
                   loading="deferred",
                   executor=_make_skill_executor(name),
               )
       ```

       NOTE: `get_supabase_authed_client` and `logger` are already imported at the top of `skill_catalog_service.py` (existing code uses both). Do NOT add duplicate imports.

    2. In `backend/tests/unit/test_skill_catalog_service.py` (existing file — append, do not rewrite):
       - Use the autouse `_clear_for_tests` fixture pattern from 13-01 to reset `tool_registry._REGISTRY` between tests.
       - Patch `get_supabase_authed_client` with `unittest.mock.patch` to return a `MagicMock` whose `.table().select().eq().order().execute()` chain returns an object with `.data` attribute.
       - Test 6 (executor delegation): use `unittest.mock.patch.object(ToolService, "execute_tool")` with `AsyncMock` to capture the call signature.

    3. Test 8 (byte-identical legacy function): leave existing test cases for `build_skill_catalog_block` untouched. Run them after the change and confirm they all still pass — that IS the byte-identical assertion at the unit-test layer for this file.

    4. The MagicMock fixture for the Supabase client chain:
       ```python
       def _mock_supabase_with_skills(skills: list[dict]):
           client = MagicMock()
           client.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value.data = skills
           return client
       ```

    5. Test 4 (DB fail-soft): make the mock raise an Exception on `.execute()`. Use `pytest.raises` to assert the exception does NOT propagate (i.e., wrap in a try/except that asserts no exception) AND use `caplog` to assert WARNING level message contains "register_user_skills failed".
  </action>
  <verify>
    <automated>cd backend &amp;&amp; source venv/bin/activate &amp;&amp; pytest tests/unit/test_skill_catalog_service.py -x -v</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c "^async def register_user_skills" backend/app/services/skill_catalog_service.py` returns 1.
    - `grep -c "^def _make_skill_executor" backend/app/services/skill_catalog_service.py` returns 1.
    - `grep -c "^async def build_skill_catalog_block" backend/app/services/skill_catalog_service.py` returns 1 (existing function preserved).
    - `git diff backend/app/services/skill_catalog_service.py | grep -c "^-[^-]"` returns 0 (no deletions in the diff — additive only above the existing build_skill_catalog_block function or below; planner choice is below).
    - `pytest backend/tests/unit/test_skill_catalog_service.py -v` shows ALL tests passing — both new (Tests 1-7) and any pre-existing tests (covers Test 8 byte-identical assertion).
    - `cd backend && source venv/bin/activate && python -c "from app.services.skill_catalog_service import register_user_skills, _make_skill_executor, build_skill_catalog_block; print('OK')"` prints OK.
    - `grep -c "skill_name=name" backend/app/services/skill_catalog_service.py` shows the late-binding fix is present (default-arg `_name: str = skill_name`).
    - `cd backend && source venv/bin/activate && python -c "from app.main import app; print('OK')"` prints OK.
    - All existing skill-related tests still pass: `pytest backend/tests/api/test_chat_skill_catalog.py backend/tests/api/test_skills.py -v` shows no NEW failures.
  </acceptance_criteria>
  <done>register_user_skills exists with fail-soft DB pattern; _make_skill_executor closes over skill_name without late-binding bug; legacy build_skill_catalog_block byte-identical; 7 new behavior tests pass; existing skill tests still pass.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| User skills (DB) → registry → LLM prompt | Skill name + description are user-controlled (skill creation form); both are rendered into the system prompt via build_catalog_block (built in 13-01). |
| RLS-scoped client → skills table | Per-request query uses `get_supabase_authed_client(token)` — the user only sees their own skills via existing RLS policy. |
| Skill executor → ToolService.execute_tool("load_skill") | Inherits the existing Phase 8 auth + RLS path. No new auth surface. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-13-03-01 | Tampering | User-controlled skill name → markdown table prompt injection | mitigate | Pipe-sanitization happens in `_format_table_row` (built in 13-01). This plan registers the raw skill name; the formatter escapes pipes/newlines and truncates description at 80 chars. Skill names that include `## ` or markdown bold do not break the table because they appear inside `| name |` cell delimiters. |
| T-13-03-02 | Information Disclosure | Cross-user skill leakage via cached registry | mitigate | Per-request DB query with RLS-scoped client (`get_supabase_authed_client(token)`) — registry is repopulated fresh each request from the caller's authenticated context. NO caching layer is added in this plan. The chat.py splice in 13-05 must call `register_user_skills(user_id, token)` for the CURRENT user before each chat request to avoid stale skills from a prior user (verified by 13-05 acceptance). |
| T-13-03-03 | Denial of Service | DB outage during register_user_skills crashes chat | mitigate | Fail-soft `try/except Exception` (matches the pattern from `build_skill_catalog_block:85-90`). On exception: log WARNING and return — chat continues with natives-only catalog. |
| T-13-03-04 | Spoofing | Late-binding bug across skills causes all closures to load the same (last) skill | mitigate | Default-arg binding `_name: str = skill_name` in the closure factory `_make_skill_executor`. Test 6 verifies each closure carries its own captured name. |
| T-13-03-05 | Repudiation | Registration failures silently disappear | accept | Fail-soft logs at WARNING — operators see structured logs (`register_user_skills failed for user_id=%s: %s`). Acceptable because the alternative (raise → break chat) is worse for UX. |
| T-13-03-06 | Privacy invariant (project-specific) | Skill executor talks to OpenRouter in clear text bypassing egress filter | accept | Skill executors delegate to `ToolService.execute_tool("load_skill", ...)` — `_execute_load_skill` returns the skill instructions string from the DB only. It does NOT make outbound LLM calls itself. The instructions become part of the LLM message thread that chat.py wraps with the egress filter (chat.py:691-701, 1040-1058). Privacy invariant preserved. |
</threat_model>

<verification>
- All 7+ behavior tests pass.
- Pre-existing tests for `build_skill_catalog_block` (in `test_skill_catalog_service.py`, `test_chat_skill_catalog.py`, etc.) still pass — no regressions to TOOL-05 fallback path.
- `git diff backend/app/services/skill_catalog_service.py | grep -E "^[-+]"` shows only `+` lines (no `-` lines outside the test file).
- `python -c "from app.main import app; print('OK')"` succeeds.
</verification>

<success_criteria>
- `register_user_skills(user_id, token)` exists, queries the `skills` table via RLS-scoped client, registers every enabled skill as `source="skill"`, `loading="deferred"`, `schema={parameterless OpenAI shape}`, executor delegates to `ToolService.execute_tool("load_skill", {"name": <name>}, ...)`.
- Fail-soft DB error handling matches the existing `build_skill_catalog_block` pattern (try/except/log/return).
- Legacy `build_skill_catalog_block(user_id, token)` is untouched (verified by `git diff`).
- TOOL-04 skill-source: ✓ this plan adds the skill registration path.
- TOOL-05 fallback preservation: ✓ existing function body byte-identical, all pre-existing tests pass.
</success_criteria>

<output>
After completion, create `.planning/phases/13-unified-tool-registry-tool-search-meta-tool/13-03-SUMMARY.md` summarizing:
- New helper signatures (register_user_skills, _make_skill_executor)
- Test count and key fixtures (mock Supabase, AsyncMock for ToolService.execute_tool)
- Confirmation that build_skill_catalog_block is byte-identical to pre-Phase-13
- chat.py wiring (call site for register_user_skills) deferred to 13-05
</output>
