---
phase: 17-deep-mode-foundation-planning-todos-plan-panel
plan: 02
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/app/config.py
  - backend/.env.example
  - backend/tests/unit/test_config_deep_mode.py
autonomous: true
requirements: [CONF-01, CONF-02, CONF-03, DEEP-02]
must_haves:
  truths:
    - "backend/app/config.py exposes Settings fields max_deep_rounds (default 50), max_tool_rounds (default 25), max_sub_agent_rounds (default 15)."
    - "backend/app/config.py exposes Settings field deep_mode_enabled (default false) — feature flag mirroring TOOL_REGISTRY_ENABLED / SANDBOX_ENABLED precedent (D-16)."
    - "Existing tools_max_iterations field is preserved as deprecated alias (D-15) with a runtime deprecation warning logged on read; effective value falls back to MAX_TOOL_ROUNDS env when unset."
    - "Reading Settings() with empty env returns max_deep_rounds=50, max_tool_rounds=25, max_sub_agent_rounds=15, deep_mode_enabled=false."
    - "Reading Settings() with env MAX_DEEP_ROUNDS=10 / MAX_TOOL_ROUNDS=30 / MAX_SUB_AGENT_ROUNDS=7 / DEEP_MODE_ENABLED=true returns those values."
    - "backend/.env.example documents all four new env vars with default-value comments."
    - "backend/app/main.py / chat.py imports of get_settings() continue to work unchanged (no breakage on existing callers)."
  artifacts:
    - path: "backend/app/config.py"
      provides: "Pydantic Settings extension with 4 new env-var fields per D-14, D-15, D-16."
      contains: "max_deep_rounds"
    - path: "backend/.env.example"
      provides: "Documentation of MAX_DEEP_ROUNDS / MAX_TOOL_ROUNDS / MAX_SUB_AGENT_ROUNDS / DEEP_MODE_ENABLED."
      contains: "MAX_DEEP_ROUNDS"
    - path: "backend/tests/unit/test_config_deep_mode.py"
      provides: "Unit tests for new Settings fields (defaults + env override + deprecated alias)."
      contains: "test_default_max_deep_rounds_50"
  key_links:
    - from: "backend/app/config.py"
      to: "DEEP_MODE_ENABLED env"
      via: "Pydantic Settings"
      pattern: "deep_mode_enabled"
    - from: "backend/app/config.py"
      to: "tools_max_iterations"
      via: "deprecated alias"
      pattern: "tools_max_iterations"
---

<objective>
Add the four deployment knobs that govern the Deep Mode loop — `MAX_DEEP_ROUNDS`, `MAX_TOOL_ROUNDS`, `MAX_SUB_AGENT_ROUNDS` (CONF-01..03) — and the dark-launch feature flag `DEEP_MODE_ENABLED` (D-16) to the existing Pydantic Settings pattern in `backend/app/config.py`.

Per D-14 (CONTEXT.md): these are deployment knobs, not user-runtime settings, so they live in env-driven Pydantic Settings (matching `tools_max_iterations`, `llm_context_window`, `tool_registry_enabled`, `sandbox_enabled` precedent), NOT in `system_settings`.

Per D-15: legacy `tools_max_iterations` field preserved as deprecated alias for one-milestone migration; default raised conceptually from 5 → 25 via the new `MAX_TOOL_ROUNDS` (read order: env MAX_TOOL_ROUNDS → env TOOLS_MAX_ITERATIONS → default 25).

Per D-16: `DEEP_MODE_ENABLED` defaults `false` for v1.3 dark launch (mirrors TOOL_REGISTRY_ENABLED / SANDBOX_ENABLED). Toggle hidden in UI when off; chat endpoint rejects deep_mode payloads when off.

Wave 1 — independent of Plan 17-01 because pure config addition does not touch the schema. Can run in parallel with 17-01.

Output: Settings extension + .env.example doc + unit tests.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/STATE.md
@.planning/phases/17-deep-mode-foundation-planning-todos-plan-panel/17-CONTEXT.md
@backend/app/config.py

<interfaces>
**Existing `Settings` pattern in `backend/app/config.py`:**
- `class Settings(BaseSettings)` with `model_config = SettingsConfigDict(env_file=".env", extra="ignore")`.
- Fields are flat module-level on Settings (e.g., `tools_max_iterations: int = 5`, `tool_registry_enabled: bool = False`, `sandbox_enabled: bool = False`).
- `get_settings()` is `@lru_cache`d; consumers call `from app.config import get_settings`.
- Env var names map to field names via SCREAMING_SNAKE_CASE upper-case (so `max_deep_rounds` reads from env `MAX_DEEP_ROUNDS`).

**Existing `tools_max_iterations: int = 5`** is the field we're soft-deprecating. Reads at `chat.py:992` use `settings.tools_max_iterations`. After this plan, `chat.py` will read `settings.max_tool_rounds` (Plan 17-04 makes that switch).

**Existing dark-launch flag pattern** (e.g., `tool_registry_enabled: bool = False`, line 87): When False, the flag-gated code path is byte-identical to the prior milestone. We replicate exactly this for `deep_mode_enabled`.
</interfaces>

</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Write failing unit tests for new Settings fields</name>
  <files>backend/tests/unit/test_config_deep_mode.py</files>
  <behavior>
    - test_default_max_deep_rounds_50: instantiate Settings() with empty env → max_deep_rounds == 50.
    - test_default_max_tool_rounds_25: empty env → max_tool_rounds == 25.
    - test_default_max_sub_agent_rounds_15: empty env → max_sub_agent_rounds == 15.
    - test_default_deep_mode_enabled_false: empty env → deep_mode_enabled is False.
    - test_env_override_max_deep_rounds: monkeypatch env MAX_DEEP_ROUNDS=10 → Settings().max_deep_rounds == 10.
    - test_env_override_deep_mode_enabled: monkeypatch DEEP_MODE_ENABLED=true → Settings().deep_mode_enabled is True.
    - test_legacy_tools_max_iterations_alias: when only legacy env TOOLS_MAX_ITERATIONS=7 is set (no MAX_TOOL_ROUNDS) → Settings().max_tool_rounds == 7 AND a DeprecationWarning is emitted (capture via pytest.warns or warnings.catch_warnings).
    - test_max_tool_rounds_takes_precedence: when both MAX_TOOL_ROUNDS=30 and TOOLS_MAX_ITERATIONS=7 are set → max_tool_rounds == 30, no warning.
  </behavior>
  <action>
    Create `backend/tests/unit/test_config_deep_mode.py`. Use pytest's `monkeypatch` fixture for env manipulation. Clear the `get_settings` lru_cache between tests (`from app.config import get_settings; get_settings.cache_clear()`).

    Run:
    ```
    cd backend && source venv/bin/activate && pytest tests/unit/test_config_deep_mode.py -v
    ```
    Expect all 8 tests fail (fields don't exist yet — RED).
  </action>
  <verify>
    <automated>cd backend && source venv/bin/activate && pytest tests/unit/test_config_deep_mode.py -v 2>&1 | grep -cE "FAILED|ERROR" | grep -q "[1-9]"</automated>
  </verify>
  <done>Test file exists, 8 tests defined, all failing (AttributeError on Settings instance).</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Extend Settings with the four new fields + deprecated alias logic</name>
  <files>backend/app/config.py</files>
  <action>
    Add the following to `backend/app/config.py` Settings class. Place fields in a clearly-marked Phase 17 block; do NOT remove or rename `tools_max_iterations` (kept for back-compat).

    Per D-14, D-15, D-16:

    ```python
    # Phase 17 / v1.3 (DEEP-02, CONF-01..03; D-14 / D-15 / D-16):
    # Loop iteration caps for the Deep Mode branch + standard tool loop + sub-agent loop.
    # Env-driven (NOT system_settings) — these are deployment knobs, not user-runtime settings.
    max_deep_rounds: int = 50
    max_tool_rounds: int = 25
    max_sub_agent_rounds: int = 15

    # Phase 17 / v1.3 (DEEP-03; D-16):
    # Dark-launch feature flag. When False, the Deep Mode toggle is hidden in the UI,
    # the /chat endpoint rejects deep_mode=true payloads, and the codebase is byte-identical
    # to pre-Phase-17 (CONF-01 / DEEP-03 invariant). Mirrors TOOL_REGISTRY_ENABLED /
    # SANDBOX_ENABLED dark-launch precedent.
    deep_mode_enabled: bool = False
    ```

    Then add a `model_validator(mode="after")` (Pydantic v2 idiom; see existing v1.0 redaction validator in this file for the precedent) that handles the `tools_max_iterations` → `max_tool_rounds` deprecation alias per D-15:

    ```python
    @model_validator(mode="after")
    def _migrate_tools_max_iterations_alias(self) -> "Settings":
        # D-15 deprecation: TOOLS_MAX_ITERATIONS env still readable for one milestone.
        # If MAX_TOOL_ROUNDS not explicitly set (still equals default 25) BUT
        # TOOLS_MAX_ITERATIONS env was provided (and != legacy default 5),
        # back-fill max_tool_rounds and emit a deprecation warning.
        import os, warnings
        env_legacy = os.environ.get("TOOLS_MAX_ITERATIONS")
        env_new = os.environ.get("MAX_TOOL_ROUNDS")
        if env_legacy is not None and env_new is None:
            warnings.warn(
                "TOOLS_MAX_ITERATIONS is deprecated; set MAX_TOOL_ROUNDS instead. "
                "Falling back to TOOLS_MAX_ITERATIONS for this run (Phase 17 / D-15).",
                DeprecationWarning,
                stacklevel=2,
            )
            try:
                self.max_tool_rounds = int(env_legacy)
            except ValueError:
                pass
        return self
    ```

    Note: `tools_max_iterations` field is left in place (existing field at line 73) — `chat.py` will switch to reading `max_tool_rounds` in Plan 17-04.

    Re-run unit tests:
    ```
    cd backend && source venv/bin/activate && pytest tests/unit/test_config_deep_mode.py -v
    ```
    All 8 should now pass.

    Re-run import smoke (PostToolUse hook does this automatically; replicate locally):
    ```
    cd backend && source venv/bin/activate && python -c "from app.main import app; print('OK')"
    ```
  </action>
  <verify>
    <automated>cd backend && source venv/bin/activate && pytest tests/unit/test_config_deep_mode.py -v 2>&1 | grep -q "8 passed" && python -c "from app.main import app; print('OK')" | grep -q "OK"</automated>
  </verify>
  <done>All 8 unit tests pass (TDD GREEN). FastAPI app imports cleanly with new Settings fields. Existing chat.py runtime unaffected (still reads tools_max_iterations).</done>
</task>

<task type="auto">
  <name>Task 3: Document new env vars in .env.example</name>
  <files>backend/.env.example</files>
  <action>
    Add a Phase 17 section to `backend/.env.example` (create the file if it doesn't exist, copying from any existing `.env.template` or `.env.sample` if present). Append:

    ```bash
    # Phase 17 / v1.3 — Agent Harness loop caps (CONF-01..03)
    # Deep Mode branch iteration limit (default 50)
    MAX_DEEP_ROUNDS=50
    # Standard tool-calling loop iteration limit (default 25; replaces legacy TOOLS_MAX_ITERATIONS=5)
    MAX_TOOL_ROUNDS=25
    # Sub-agent loop iteration limit (default 15)
    MAX_SUB_AGENT_ROUNDS=15

    # Phase 17 / v1.3 — Deep Mode dark-launch flag (D-16)
    # When false, Deep Mode toggle is hidden in UI and /chat rejects deep_mode=true payloads.
    # Flip to true once Phases 17 + 18 + 19 are shipped and UAT passes.
    DEEP_MODE_ENABLED=false
    ```
  </action>
  <verify>
    <automated>grep -q "MAX_DEEP_ROUNDS=50" backend/.env.example && grep -q "DEEP_MODE_ENABLED=false" backend/.env.example && grep -q "MAX_TOOL_ROUNDS=25" backend/.env.example</automated>
  </verify>
  <done>.env.example documents all four new env vars with their defaults and comments referring to CONF-01..03 + D-16.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| operator→Railway env | Operator sets MAX_DEEP_ROUNDS / DEEP_MODE_ENABLED in Railway dashboard; misconfiguration could over-allocate compute or expose unfinished feature |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-17-04 | D (Denial of Service) | MAX_DEEP_ROUNDS too high | accept | Default 50 is conservative; operator-controlled; runaway loops still bounded by per-call timeouts and KV-cache cost (compute spend visible in OpenRouter dashboard) |
| T-17-05 | E (Elevation of Privilege) | DEEP_MODE_ENABLED flipped on prematurely | mitigate | Default `false`; .env.example explicit comment "Flip to true once Phases 17 + 18 + 19 are shipped and UAT passes"; UI toggle hidden when flag off (Plan 17-06) and endpoint rejects payloads (Plan 17-04) |

</threat_model>

<verification>
- `pytest tests/unit/test_config_deep_mode.py -v` returns 8 passed.
- `python -c "from app.main import app; print('OK')"` prints OK.
- `tools_max_iterations` field still present (existing callers in chat.py do NOT break).
- Deprecation warning fires when only TOOLS_MAX_ITERATIONS env is set.
- `.env.example` documents all four new env vars.
</verification>

<success_criteria>
- CONF-01, CONF-02, CONF-03 covered: env-driven, documented defaults, no system_settings dependence.
- DEEP-02 partially covered (MAX_DEEP_ROUNDS plumbing — full satisfaction requires Plan 17-04 chat-loop branch consumes it).
- DEEP-03 dark-launch foundation: `deep_mode_enabled` field exists and defaults False; downstream plans gate on it.
- Backward compat preserved: existing `tools_max_iterations` reads unaffected; deprecation warning logs but does not break.
</success_criteria>

<output>
After completion, create `.planning/phases/17-deep-mode-foundation-planning-todos-plan-panel/17-02-SUMMARY.md`
</output>
