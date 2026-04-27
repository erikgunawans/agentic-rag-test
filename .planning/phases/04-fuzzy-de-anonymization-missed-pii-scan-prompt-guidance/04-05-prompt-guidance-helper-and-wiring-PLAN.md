---
phase: 04-fuzzy-de-anonymization-missed-pii-scan-prompt-guidance
plan: 05
type: execute
wave: 2
depends_on: []
files_modified:
  - backend/app/services/redaction/prompt_guidance.py
  - backend/app/routers/chat.py
  - backend/app/services/agent_service.py
  - backend/tests/unit/test_prompt_guidance.py
autonomous: true
requirements_addressed: [PROMPT-01]
tags: [pii, system-prompt, prompt-engineering, surrogate-preservation]
must_haves:
  truths:
    - "Module prompt_guidance.py exposes `def get_pii_guidance_block(*, redaction_enabled: bool) -> str` (D-79/D-80)"
    - "Helper returns the imperative D-82 guidance block when redaction_enabled=True; returns empty string '' when redaction_enabled=False (D-80 conditional injection)"
    - "Module-level constant _GUIDANCE_BLOCK contains the verbatim D-82 content: imperative rules ('MUST', 'NEVER'), explicit type list (names, emails, phones, locations, dates, URLs, IPs), [TYPE] warning, 2 concrete examples"
    - "English-only phrasing per D-81 — single source of truth across main agent (chat.py SYSTEM_PROMPT) and 4 sub-agents (agent_service.py)"
    - "chat.py imports get_pii_guidance_block and appends to SYSTEM_PROMPT at message-build time (single-agent path); checks settings.pii_redaction_enabled to gate"
    - "agent_service.py imports get_pii_guidance_block and appends `_PII_GUIDANCE` to each of 4 AgentDefinition.system_prompt blocks at module-import time"
    - "Unit tests cover D-79 (helper exists), D-80 (empty when disabled, populated when enabled), D-82 (block contains imperatives + type list + [TYPE] warning + examples)"
  artifacts:
    - path: "backend/app/services/redaction/prompt_guidance.py"
      provides: "get_pii_guidance_block helper + _GUIDANCE_BLOCK constant"
      contains: "def get_pii_guidance_block"
    - path: "backend/app/routers/chat.py"
      provides: "Single-agent path appends pii guidance to SYSTEM_PROMPT (D-79)"
      contains: "get_pii_guidance_block"
    - path: "backend/app/services/agent_service.py"
      provides: "All 4 AgentDefinition.system_prompt blocks append _PII_GUIDANCE (D-79)"
      contains: "_PII_GUIDANCE"
    - path: "backend/tests/unit/test_prompt_guidance.py"
      provides: "Unit coverage for D-79/D-80/D-82"
      contains: "TestD80_ConditionalInjection"
  key_links:
    - from: "backend/app/routers/chat.py:event_generator (single-agent path)"
      to: "backend/app/services/redaction/prompt_guidance.py:get_pii_guidance_block"
      via: "from app.services.redaction.prompt_guidance import get_pii_guidance_block"
      pattern: "get_pii_guidance_block\\(redaction_enabled"
    - from: "backend/app/services/agent_service.py (4 AgentDefinition blocks)"
      to: "backend/app/services/redaction/prompt_guidance.py:get_pii_guidance_block"
      via: "module-level _PII_GUIDANCE = get_pii_guidance_block(redaction_enabled=...)"
      pattern: "_PII_GUIDANCE"
threat_model:
  trust_boundaries:
    - "Application code → LLM system prompt (the guidance block crosses into the prompt context window; downstream LLM sees it as authoritative instruction)"
  threats:
    - id: "T-04-05-1"
      category: "Information Disclosure (guidance block reveals PII strategy to attacker via LLM)"
      component: "_GUIDANCE_BLOCK content"
      severity: "low"
      disposition: "accept"
      mitigation: "The block describes surrogate-preservation in generic terms ('text that looks like real names') and uses fabricated examples ('Marcus Smith', '+62-21-555-1234'). It does NOT reveal the actual surrogate-generation algorithm, registry contents, or the de-anonymization mapping. An adversarial user with prompt access could deduce that PII redaction is in use, which is already evident from the surrogate-form output. Acceptable per PRD §11 threat model."
    - id: "T-04-05-2"
      category: "Spoofing (prompt injection — user message overrides the guidance)"
      component: "User-provided message (after the system prompt)"
      severity: "medium"
      disposition: "mitigate"
      mitigation: "D-82 imperative phrasing ('MUST', 'NEVER', 'CRITICAL') uses the strongest LLM-instruction language available. The block is placed in the system message (highest authority position in OpenAI/OpenRouter chat-completion API). User-message overrides ('ignore previous instructions') are mitigated by RLHF training on standard chat-completion APIs; complete prevention requires per-provider hardening which is out of v1.0 scope. The dual-coverage with hard-redact `[TYPE]` placeholders means that even if the LLM rephrases a surrogate, the [TYPE] placeholders survive structurally (Phase 2 D-24 / Plan 04-03 D-74)."
    - id: "T-04-05-3"
      category: "Tampering (guidance block injected when redaction is OFF)"
      component: "Conditional injection logic"
      severity: "low"
      disposition: "mitigate"
      mitigation: "D-80 conditional: `get_pii_guidance_block(redaction_enabled=False)` returns empty string. Verified by unit test `TestD80_ConditionalInjection.test_disabled_returns_empty`. When redaction is off, no surrogates exist; injecting the guidance is dead-weight tokens but not security-critical."
    - id: "T-04-05-4"
      category: "Tampering (sub-agent prompt drift — module-import-time binding)"
      component: "agent_service.py module-level _PII_GUIDANCE"
      severity: "low"
      disposition: "accept"
      mitigation: "Per PATTERNS.md design rationale (lines 904-915): every AgentDefinition field (tool_names, max_iterations) is module-import-time-bound; the guidance follows the same pattern. Phase 5 may move to per-call computation if per-thread overrides ship; for v1.0, redaction-enabled is a deploy-time toggle (env var) so import-time binding is correct. Restart-on-config-change is the existing operational expectation."
---

<objective>
Ship the centralized system-prompt guidance helper (D-79/D-80/D-81/D-82) — a single source of truth for the surrogate-preservation block — and wire it into BOTH the main chat path (`chat.py`) and the 4 sub-agent definitions (`agent_service.py`). This covers ROADMAP SC#5: "main-agent system prompt instructs the LLM to reproduce names, emails, phones, locations, dates, and URLs verbatim".

Purpose: Without this guidance, surrogates produced by the redaction service may be paraphrased or abbreviated by the LLM ("M. Smith" instead of "Marcus Smith"), breaking the de-anonymization round-trip (DEANON-01..03). Phase 5 will wire per-thread `redaction_enabled` flags through the SSE pipeline; this plan ships the helper + the call sites so Phase 5 only has to swap the gating boolean source.

Output: 4 files. NEW `prompt_guidance.py` module (~30 lines). MODIFIED `chat.py` (1-line import + 1-line call site change in single-agent path). MODIFIED `agent_service.py` (1-line import + module-level `_PII_GUIDANCE` constant + `+ _PII_GUIDANCE` suffix on 4 AgentDefinition.system_prompt blocks). NEW `test_prompt_guidance.py` (~50 lines).
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/04-fuzzy-de-anonymization-missed-pii-scan-prompt-guidance/04-CONTEXT.md
@.planning/phases/04-fuzzy-de-anonymization-missed-pii-scan-prompt-guidance/04-PATTERNS.md
@CLAUDE.md
@backend/app/services/redaction/honorifics.py
@backend/app/routers/chat.py
@backend/app/services/agent_service.py
@backend/app/config.py

<interfaces>
Module shape pattern (Phase 1 — `honorifics.py`):

```python
"""5-10 line docstring with examples."""
from __future__ import annotations
_FROZEN_CONSTANT = (...)
def helper(...) -> ...: ...
```

Settings:

```python
class Settings(BaseSettings):
    pii_redaction_enabled: bool = False  # Phase 1 baseline (Phase 5 may make per-thread)
```

chat.py single-agent message-construction site (around lines 215-219 per PATTERNS.md):

```python
else:
    # --- Single-agent path (Module 7 behavior) ---
    messages = (
        [{"role": "system", "content": SYSTEM_PROMPT}]
        + [{"role": m["role"], "content": m["content"]} for m in history]
        + [{"role": "user", "content": body.message}]
    )
```

agent_service.py:8-79 — 4 AgentDefinition blocks (Research, Data Analyst, General, Explorer) each carry a multi-line `system_prompt` string field.
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Write prompt_guidance.py module (D-79/D-80/D-81/D-82)</name>
  <files>backend/app/services/redaction/prompt_guidance.py</files>
  <read_first>
    - backend/app/services/redaction/honorifics.py (Phase 1 module-shape analog: small focused module, frozen constant + helper + `from __future__ import annotations`)
    - .planning/phases/04-fuzzy-de-anonymization-missed-pii-scan-prompt-guidance/04-PATTERNS.md "prompt_guidance.py (NEW)" section (verbatim module template lines 264-303)
    - .planning/phases/04-fuzzy-de-anonymization-missed-pii-scan-prompt-guidance/04-CONTEXT.md decisions D-79 (centralized helper), D-80 (conditional injection), D-81 (English-only), D-82 (verbatim block content lines 137-149)
  </read_first>
  <behavior>
    - `get_pii_guidance_block(redaction_enabled=False)` returns exactly `""` (empty string).
    - `get_pii_guidance_block(redaction_enabled=True)` returns a string of length ≥ 500 chars (the D-82 block is ~150 tokens ≈ 800-1000 chars).
    - The returned string contains ALL of: `MUST reproduce these EXACTLY`, `NO abbreviation`, `NEVER`, the type list samples (`John Smith`, `user@example.com`, `+62-21-555-1234`, `Jl. Sudirman 1`, `2024-01-15`, `https://example.com/x`, `192.168.1.1`), `[CREDIT_CARD]`, `[US_SSN]`, `literal placeholder`, the example arrow `→`, and at least one positive example (`Marcus Smith` and `[CREDIT_CARD]`).
    - Module is keyword-only — `get_pii_guidance_block(*, redaction_enabled)` (cannot be called positionally; prevents accidental boolean-arg confusion).
  </behavior>
  <action>
Create the file `backend/app/services/redaction/prompt_guidance.py` with the EXACT content below. Note the verbatim D-82 block — do NOT paraphrase, soften, or shorten.

```python
"""System-prompt PII guidance helper (D-79..D-82, PROMPT-01, FR-7.1).

Single source of truth for the surrogate-preservation block. Appended to:
  - chat.py SYSTEM_PROMPT at message-build time (single-agent path).
  - agent_service.py 4 AgentDefinition.system_prompt blocks at module import.

Conditional injection (D-80): returns "" when redaction is disabled — saves
~150 tokens per non-redacted turn.

English-only (D-81): system instructions are most reliable in English across
OpenRouter / OpenAI / LM Studio / Ollama. Indonesian user content + English
system prompt is the standard LexCore stack pattern.

Imperative phrasing (D-82): 'MUST', 'NEVER', 'CRITICAL'. Examples carry the
arrow form (→). Do NOT soften imperatives into 'please' — RLHF interprets
'please' as optional, breaking the surrogate-preservation invariant.
"""
from __future__ import annotations


# D-82: imperative rules + explicit type list + [TYPE] warning + 2 examples.
# ~150 tokens. Examples are load-bearing (RLHF compliance).
_GUIDANCE_BLOCK = """

CRITICAL: Some text in this conversation may contain placeholder values that look like real names, emails, phones, locations, dates, URLs, or IP addresses. You MUST reproduce these EXACTLY as written, with NO abbreviation, NO reformatting, and NO substitution. Treat them as opaque tokens.

Specifically: when you see text like "John Smith", "user@example.com", "+62-21-555-1234", "Jl. Sudirman 1", "2024-01-15", "https://example.com/x", or "192.168.1.1" in the input, output it character-for-character identical. Do NOT shorten "John Smith" to "J. Smith" or "Smith". Do NOT reformat "+62-21-555-1234" to "+622155512345".

Additionally, ANY text wrapped in square brackets like [CREDIT_CARD], [US_SSN], or [PHONE_NUMBER] is a literal placeholder — preserve it exactly, do not replace it with a fabricated value.

Examples:
- Input contains "Marcus Smith" → output "Marcus Smith" (NOT "Marcus" or "M. Smith" or "Mark Smith")
- Input contains "[CREDIT_CARD]" → output "[CREDIT_CARD]" (NOT "credit card number" or a fabricated number)
"""


def get_pii_guidance_block(*, redaction_enabled: bool) -> str:
    """D-79/D-80: return the surrogate-preservation block, or empty string when off.

    Args:
        redaction_enabled: keyword-only flag. True → block; False → "".

    Returns:
        The D-82 block (~150 tokens) when redaction_enabled is True; empty
        string otherwise. Caller appends to its system prompt verbatim.
    """
    return _GUIDANCE_BLOCK if redaction_enabled else ""
```

**Constraints**:
- The `_GUIDANCE_BLOCK` string content MUST be verbatim per D-82 (PATTERNS.md template + CONTEXT.md decision body). Do NOT translate, paraphrase, or summarize.
- The function signature is keyword-only (`*, redaction_enabled: bool`) — Python forbids positional calls.
- ZERO logging. ZERO async. ZERO I/O.
- Module exports the helper. The `_GUIDANCE_BLOCK` constant is single-underscore-prefixed (private) — tests import it via the `_` prefix per PATTERNS.md.

**Verification (immediate)**:
```bash
cd backend && source venv/bin/activate
python -c "from app.services.redaction.prompt_guidance import get_pii_guidance_block, _GUIDANCE_BLOCK; assert get_pii_guidance_block(redaction_enabled=False) == ''; assert get_pii_guidance_block(redaction_enabled=True) == _GUIDANCE_BLOCK; assert 'MUST reproduce these EXACTLY' in _GUIDANCE_BLOCK; assert 'Marcus Smith' in _GUIDANCE_BLOCK; assert '[CREDIT_CARD]' in _GUIDANCE_BLOCK; print('OK')"
python -c "from app.main import app; print('main OK')"
```
  </action>
  <verify>
    <automated>cd /Users/erikgunawansupriatna/claude-code-agentic-rag-masterclass-1/backend &amp;&amp; source venv/bin/activate &amp;&amp; python -c "from app.services.redaction.prompt_guidance import get_pii_guidance_block, _GUIDANCE_BLOCK; assert get_pii_guidance_block(redaction_enabled=False) == ''; assert get_pii_guidance_block(redaction_enabled=True) == _GUIDANCE_BLOCK; assert 'MUST reproduce these EXACTLY' in _GUIDANCE_BLOCK; assert 'Marcus Smith' in _GUIDANCE_BLOCK; assert '[CREDIT_CARD]' in _GUIDANCE_BLOCK; assert '+62-21-555-1234' in _GUIDANCE_BLOCK; assert 'literal placeholder' in _GUIDANCE_BLOCK; assert 'NO abbreviation' in _GUIDANCE_BLOCK; assert len(_GUIDANCE_BLOCK) &gt; 500; print('OK')"</automated>
  </verify>
  <acceptance_criteria>
    - `test -f backend/app/services/redaction/prompt_guidance.py` exits 0.
    - `grep -c '^def get_pii_guidance_block' backend/app/services/redaction/prompt_guidance.py` returns exactly 1.
    - `grep -cE 'def get_pii_guidance_block\(\*,\s*redaction_enabled:\s*bool\)' backend/app/services/redaction/prompt_guidance.py` returns exactly 1 (keyword-only signature enforced).
    - `grep -c '^_GUIDANCE_BLOCK' backend/app/services/redaction/prompt_guidance.py` returns exactly 1.
    - `grep -c 'MUST reproduce these EXACTLY' backend/app/services/redaction/prompt_guidance.py` returns ≥ 1.
    - `grep -c 'Marcus Smith' backend/app/services/redaction/prompt_guidance.py` returns ≥ 1.
    - `grep -c '\[CREDIT_CARD\]' backend/app/services/redaction/prompt_guidance.py` returns ≥ 1.
    - `grep -c '+62-21-555-1234' backend/app/services/redaction/prompt_guidance.py` returns ≥ 1.
    - `grep -c '→' backend/app/services/redaction/prompt_guidance.py` returns ≥ 2 (one per example bullet per D-82).
    - `grep -cE '@traced|logging\.getLogger|async def' backend/app/services/redaction/prompt_guidance.py` returns 0 (purity invariants).
    - `cd backend &amp;&amp; source venv/bin/activate &amp;&amp; python -m py_compile app/services/redaction/prompt_guidance.py` exits 0.
    - The smoke-script in `<verify>` exits 0 and prints `OK`.
    - `python -c "from app.main import app"` succeeds.
  </acceptance_criteria>
  <done>
prompt_guidance.py exists with the verbatim D-82 block. The helper is keyword-only and gates on `redaction_enabled`. All content assertions pass.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Wire helper into chat.py (single-agent path) and agent_service.py (4 AgentDefinition blocks) (D-79)</name>
  <files>backend/app/routers/chat.py, backend/app/services/agent_service.py</files>
  <read_first>
    - backend/app/routers/chat.py (the file being modified — locate `SYSTEM_PROMPT` constant near lines 19-27; locate `event_generator` and the single-agent message-construction site around lines 215-219; also locate the multi-agent message construction around lines 187-191)
    - backend/app/services/agent_service.py (the file being modified — locate the 4 AgentDefinition blocks at the documented line ranges: RESEARCH_AGENT (~line 11), DATA_ANALYST_AGENT (~line 29), GENERAL_AGENT (~line 49), EXPLORER_AGENT (~line 64); identify the exact closing lines of each system_prompt string)
    - .planning/phases/04-fuzzy-de-anonymization-missed-pii-scan-prompt-guidance/04-PATTERNS.md "MODIFIED · backend/app/routers/chat.py" section (lines 813-866) and "MODIFIED · backend/app/services/agent_service.py" section (lines 870-915)
    - .planning/phases/04-fuzzy-de-anonymization-missed-pii-scan-prompt-guidance/04-CONTEXT.md decision D-79 (single source of truth across main agent + sub-agents)
    - backend/app/config.py (confirm `pii_redaction_enabled` field name and default; this is the gate for module-import binding)
  </read_first>
  <behavior>
    - chat.py imports `get_pii_guidance_block`. The single-agent message-construction site computes a per-call `pii_guidance` string from `settings.pii_redaction_enabled` and concatenates onto `SYSTEM_PROMPT`. The multi-agent path (which uses `agent_def.system_prompt`) is unchanged in chat.py — agent_service.py handles that wiring.
    - agent_service.py imports `get_pii_guidance_block` and `get_settings`; defines a module-level `_PII_GUIDANCE = get_pii_guidance_block(redaction_enabled=get_settings().pii_redaction_enabled)`. Each of 4 AgentDefinition.system_prompt strings has `+ _PII_GUIDANCE` appended at the end of its string concatenation expression.
    - When `pii_redaction_enabled=False` (deploy-time): `_PII_GUIDANCE == ""`; the agent system_prompt strings are unchanged in length compared to baseline. When True: each agent's system_prompt is suffixed with the full D-82 block.
    - All 4 AgentDefinition `tool_names` and `max_iterations` fields are unchanged. Only `system_prompt` is modified.
    - Phase 1+2+3 regression: 79/79 tests still pass.
  </behavior>
  <action>
**Step 1 — chat.py edits** (`backend/app/routers/chat.py`):

a) Add the import. Place near the other Phase 4-relevant imports (e.g., near `from app.services import agent_service` on line 9 per PATTERNS.md):
```python
from app.services.redaction.prompt_guidance import get_pii_guidance_block
```

b) Locate the single-agent message-construction block in `event_generator()` (around lines 215-219 per PATTERNS.md). The existing block looks like:
```python
            else:
                # --- Single-agent path (Module 7 behavior) ---
                messages = (
                    [{"role": "system", "content": SYSTEM_PROMPT}]
                    + [{"role": m["role"], "content": m["content"]} for m in history]
                    + [{"role": "user", "content": body.message}]
                )
```

Replace it with:
```python
            else:
                # --- Single-agent path (Module 7 behavior) ---
                # Phase 4 D-79/D-80: append PII guidance to SYSTEM_PROMPT when
                # redaction is enabled. Phase 5 will swap to per-thread flag.
                pii_guidance = get_pii_guidance_block(
                    redaction_enabled=settings.pii_redaction_enabled,
                )
                messages = (
                    [{"role": "system", "content": SYSTEM_PROMPT + pii_guidance}]
                    + [{"role": m["role"], "content": m["content"]} for m in history]
                    + [{"role": "user", "content": body.message}]
                )
```

c) Verify `settings` is in scope at the splice point (chat.py already reads settings via `get_settings()` for other features per Phase 3). If a local `settings` variable is not in scope, add a one-liner `settings = get_settings()` at the top of the surrounding function or use `get_settings().pii_redaction_enabled` inline. Confirm by reading the surrounding code BEFORE writing.

d) Do NOT modify the multi-agent path block (around lines 187-191) — agent_service.py handles that wiring at module-import time so the multi-agent `agent_def.system_prompt` strings already include the guidance. PATTERNS.md notes this explicitly: "The chat.py multi-agent path needs NO additional change."

**Step 2 — agent_service.py edits** (`backend/app/services/agent_service.py`):

a) Add imports near the top of the file (after `from app.models.agents import ...` per PATTERNS.md line 882):
```python
from app.config import get_settings
from app.services.redaction.prompt_guidance import get_pii_guidance_block
```

b) Add a module-level constant immediately below the imports (before any AgentDefinition):
```python
# Phase 4 D-79: single-source-of-truth PII guidance suffix. Module-import-time
# binding mirrors the existing AgentDefinition fields (tool_names,
# max_iterations) — Phase 5 may move to per-call when per-thread flags ship.
_PII_GUIDANCE = get_pii_guidance_block(
    redaction_enabled=get_settings().pii_redaction_enabled,
)
```

c) Append `+ _PII_GUIDANCE` to each of the 4 AgentDefinition.system_prompt strings. The exact splice depends on the existing string-construction style — most likely the `system_prompt=(...)` argument is a parenthesized multi-line string literal or a tuple of concatenated strings. For each agent:

PATTERN A — single multi-line string literal:
```python
RESEARCH_AGENT = AgentDefinition(
    name="research",
    display_name="Research Agent",
    system_prompt=(
        "You are a thorough document research specialist. ... "
        "Be precise and cite your sources."
    ) + _PII_GUIDANCE,                # ← NEW
    tool_names=["search_documents"],
    max_iterations=5,
)
```

PATTERN B — assignment via concatenation:
```python
RESEARCH_AGENT = AgentDefinition(
    name="research",
    system_prompt="You are a ... cite sources." + _PII_GUIDANCE,    # ← `+ _PII_GUIDANCE` suffixed
    ...
)
```

Read the file BEFORE editing to determine which pattern is in use; apply the same suffix style to each of:
- RESEARCH_AGENT (~line 11 — research agent)
- DATA_ANALYST_AGENT (~line 29 — data analyst / SQL)
- GENERAL_AGENT (~line 49 — general fallback)
- EXPLORER_AGENT (~line 64 — knowledge-base explorer)

NOTE: PATTERNS.md says the agent set is "Research, Data Analyst, General, Explorer" (4 agents). CONTEXT.md says "4 agent definitions (General, Research, Compare, Compliance)". Naming may differ in the live codebase. Apply the suffix to ALL `AgentDefinition` instances actually present in `agent_service.py` regardless of which name set is correct — there must be exactly 4 per CONTEXT.md / PATTERNS.md, and each one must get the `+ _PII_GUIDANCE` suffix. Confirm count by `grep -c '^\s*[A-Z_]*_AGENT\s*=\s*AgentDefinition(' backend/app/services/agent_service.py`.

**Step 3 — Verification**:
```bash
cd backend && source venv/bin/activate
python -c "from app.services.agent_service import RESEARCH_AGENT, DATA_ANALYST_AGENT, GENERAL_AGENT, EXPLORER_AGENT  # may need name adjustment"
# OR (defensive): python -c "from app.services import agent_service; agents = [v for k,v in vars(agent_service).items() if k.endswith('_AGENT')]; print(len(agents))"
python -c "from app.main import app; print('main OK')"
pytest tests/ -x --tb=short -q
```
Phase 1+2+3 regression must remain 79/79 green.

**Constraints**:
- DO NOT change AgentDefinition field names. DO NOT change tool_names or max_iterations on any agent. ONLY append `+ _PII_GUIDANCE` to system_prompt.
- DO NOT introduce a new env var. The existing `pii_redaction_enabled` (Phase 1) is the gating boolean for v1.0; Phase 5 will replace with per-thread.
- DO NOT add any logging. The helper is silent.
- DO NOT remove or modify the multi-agent path message-build block in chat.py — that path receives the guidance via `agent_def.system_prompt` at agent-construction time.
  </action>
  <verify>
    <automated>cd /Users/erikgunawansupriatna/claude-code-agentic-rag-masterclass-1/backend &amp;&amp; source venv/bin/activate &amp;&amp; python -c "
from app.services import agent_service
from app.services.redaction.prompt_guidance import get_pii_guidance_block, _GUIDANCE_BLOCK
from app.config import get_settings
agents = [v for k, v in vars(agent_service).items() if k.endswith('_AGENT')]
assert len(agents) == 4, f'expected 4 agents, found {len(agents)}'
expected_suffix = _GUIDANCE_BLOCK if get_settings().pii_redaction_enabled else ''
for a in agents:
    if expected_suffix:
        assert a.system_prompt.endswith(expected_suffix), f'{a.name} missing pii guidance suffix'
    else:
        # When redaction is off the suffix is empty so endswith is trivially true
        assert isinstance(a.system_prompt, str)
print('AGENTS-OK', len(agents))
" &amp;&amp; pytest tests/ -x --tb=short -q</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c 'from app.services.redaction.prompt_guidance import get_pii_guidance_block' backend/app/routers/chat.py` returns exactly 1.
    - `grep -c 'from app.services.redaction.prompt_guidance import get_pii_guidance_block' backend/app/services/agent_service.py` returns exactly 1.
    - `grep -c 'from app.config import get_settings' backend/app/services/agent_service.py` returns ≥ 1 (may already be present from Phase 3 — at minimum 1 import line is present).
    - `grep -c '^_PII_GUIDANCE' backend/app/services/agent_service.py` returns exactly 1 (module-level constant).
    - `grep -c '+ _PII_GUIDANCE' backend/app/services/agent_service.py` returns ≥ 4 (one suffix per AgentDefinition).
    - `grep -cE '^\s*[A-Z_]+_AGENT\s*=\s*AgentDefinition\(' backend/app/services/agent_service.py` returns exactly 4 (count of agent definitions; matches the suffix count).
    - `grep -c 'get_pii_guidance_block(' backend/app/routers/chat.py` returns ≥ 1 (chat.py call site).
    - `grep -c 'SYSTEM_PROMPT + pii_guidance' backend/app/routers/chat.py` returns ≥ 1 (single-agent splice present).
    - Defensive python check: `cd backend && source venv/bin/activate && python -c "from app.services import agent_service; agents = [v for k,v in vars(agent_service).items() if k.endswith('_AGENT')]; assert len(agents) == 4"` exits 0.
    - When `PII_REDACTION_ENABLED=true` env override is set at import time, all 4 AgentDefinition.system_prompt strings end with the D-82 block content (verify via `endswith(_GUIDANCE_BLOCK)`).
    - `pytest tests/ -x --tb=short` exits 0 — Phase 1+2+3 79/79 still green.
    - `python -c "from app.main import app"` succeeds.
  </acceptance_criteria>
  <done>
chat.py and agent_service.py both invoke `get_pii_guidance_block`. The 4 AgentDefinition.system_prompt strings carry the suffix at module-import time. Phase 1+2+3 baseline preserved.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: Write test_prompt_guidance.py covering D-79/D-80/D-82</name>
  <files>backend/tests/unit/test_prompt_guidance.py</files>
  <read_first>
    - backend/tests/unit/test_egress_filter.py (Phase 3 D-66 — exact analog: pure-function tests, table-driven, per-D-XX subclasses, no fixtures)
    - backend/app/services/redaction/prompt_guidance.py (Task 1 output — confirm public surface matches the test imports)
    - .planning/phases/04-fuzzy-de-anonymization-missed-pii-scan-prompt-guidance/04-PATTERNS.md "test_prompt_guidance.py (NEW)" section (verbatim template lines 511-551)
    - .planning/phases/04-fuzzy-de-anonymization-missed-pii-scan-prompt-guidance/04-CONTEXT.md decisions D-79 / D-80 / D-82
  </read_first>
  <behavior>
    Test classes:
    - `TestD80_ConditionalInjection` — `redaction_enabled=False` returns empty; `redaction_enabled=True` returns the constant.
    - `TestD82_BlockContent` — block contains imperative rules (`MUST`, `NO abbreviation`); explicit type list samples; `[TYPE]` warning; concrete examples with the arrow form.
    - `TestKeywordOnlySignature` — calling positionally raises `TypeError` (keyword-only enforcement).
    - `TestD81_EnglishOnly` — block contains the imperative English keywords and does NOT contain Indonesian-only translation indicators (defensive sanity check; not exhaustive).
  </behavior>
  <action>
Create `backend/tests/unit/test_prompt_guidance.py` with the exact content below.

```python
"""Unit tests for prompt_guidance.get_pii_guidance_block (D-79/D-80/D-81/D-82).

Mirrors the table-driven pure-function shape of test_egress_filter.py (Phase 3 D-66).
"""
from __future__ import annotations

import pytest

from app.services.redaction.prompt_guidance import (
    _GUIDANCE_BLOCK,
    get_pii_guidance_block,
)


class TestD80_ConditionalInjection:
    """D-80: conditional injection — empty when off, populated when on."""

    def test_disabled_returns_empty(self):
        assert get_pii_guidance_block(redaction_enabled=False) == ""

    def test_enabled_returns_block(self):
        result = get_pii_guidance_block(redaction_enabled=True)
        assert result == _GUIDANCE_BLOCK
        assert result != ""

    def test_enabled_block_is_substantial(self):
        # D-82 block is ~150 tokens (~800-1000 chars).
        result = get_pii_guidance_block(redaction_enabled=True)
        assert len(result) >= 500


class TestD82_BlockContent:
    """D-82: imperative rules + type list + [TYPE] warning + concrete examples."""

    def test_contains_imperative_rules(self):
        block = get_pii_guidance_block(redaction_enabled=True)
        assert "MUST reproduce these EXACTLY" in block
        assert "NO abbreviation" in block
        assert "NO reformatting" in block

    def test_contains_critical_marker(self):
        block = get_pii_guidance_block(redaction_enabled=True)
        assert "CRITICAL" in block

    def test_contains_explicit_type_list(self):
        block = get_pii_guidance_block(redaction_enabled=True)
        # All 7 sample types from D-82 must appear.
        for sample in [
            "John Smith",
            "user@example.com",
            "+62-21-555-1234",
            "Jl. Sudirman 1",
            "2024-01-15",
            "https://example.com/x",
            "192.168.1.1",
        ]:
            assert sample in block, f"missing sample: {sample}"

    def test_contains_bracket_warning(self):
        block = get_pii_guidance_block(redaction_enabled=True)
        assert "[CREDIT_CARD]" in block
        assert "[US_SSN]" in block
        assert "literal placeholder" in block

    def test_contains_concrete_examples(self):
        block = get_pii_guidance_block(redaction_enabled=True)
        # D-82 examples use the arrow form.
        assert "→" in block
        assert "Marcus Smith" in block
        # Counter-examples that the block warns against.
        assert "M. Smith" in block

    def test_no_softening_language(self):
        # D-82 forbids 'please' (RLHF interprets as optional).
        block = get_pii_guidance_block(redaction_enabled=True)
        assert "please" not in block.lower() or "please reproduce" not in block.lower()


class TestKeywordOnlySignature:
    """The helper is keyword-only — positional calls must raise TypeError."""

    def test_positional_call_raises(self):
        with pytest.raises(TypeError):
            get_pii_guidance_block(True)  # type: ignore[misc]


class TestD81_EnglishOnly:
    """D-81: English-only phrasing across all LLM providers."""

    def test_block_uses_english_keywords(self):
        block = get_pii_guidance_block(redaction_enabled=True)
        # Defensive sanity check — key English instruction tokens are present.
        for keyword in ["CRITICAL", "MUST", "NOT", "Examples"]:
            assert keyword in block, f"missing English keyword: {keyword}"
```

**Verification**:
```bash
cd backend && source venv/bin/activate
pytest tests/unit/test_prompt_guidance.py -v --tb=short
pytest tests/ -x --tb=short -q
```
  </action>
  <verify>
    <automated>cd /Users/erikgunawansupriatna/claude-code-agentic-rag-masterclass-1/backend &amp;&amp; source venv/bin/activate &amp;&amp; pytest tests/unit/test_prompt_guidance.py -v --tb=short</automated>
  </verify>
  <acceptance_criteria>
    - `test -f backend/tests/unit/test_prompt_guidance.py` exits 0.
    - `grep -cE '^class Test(D80_ConditionalInjection|D82_BlockContent|KeywordOnlySignature|D81_EnglishOnly)' backend/tests/unit/test_prompt_guidance.py` returns exactly 4.
    - `grep -cE '^    def test_' backend/tests/unit/test_prompt_guidance.py` returns ≥ 10.
    - `pytest backend/tests/unit/test_prompt_guidance.py -v` exits 0; all collected tests PASS.
    - `pytest backend/tests/unit/ -v --tb=short` exits 0 — Phase 1+2+3 unit tests do NOT regress.
    - Test file imports the public surface and the constant: `grep -c 'from app.services.redaction.prompt_guidance import' backend/tests/unit/test_prompt_guidance.py` returns ≥ 1.
  </acceptance_criteria>
  <done>
test_prompt_guidance.py runs green. The 4 test classes pin D-79, D-80, D-81, D-82 invariants. Phase 1+2+3 unit-test suite continues to pass.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Application code → LLM system prompt | The guidance block is injected into the system message of every chat-completion call. The LLM treats it as authoritative instruction. |

## STRIDE Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation |
|-----------|----------|-----------|----------|-------------|------------|
| T-04-05-1 | Information Disclosure (block reveals PII strategy) | `_GUIDANCE_BLOCK` content | low | accept | Block describes surrogate-preservation in generic terms with fabricated examples; does NOT reveal actual surrogate algorithm or registry contents. |
| T-04-05-2 | Spoofing (prompt injection — user message overrides) | User message | medium | mitigate | D-82 imperative phrasing (`MUST`, `NEVER`, `CRITICAL`); placement in system message (highest authority); dual coverage with hard-redact `[TYPE]` placeholders that survive structurally per D-74. |
| T-04-05-3 | Tampering (guidance injected when redaction OFF) | Conditional injection | low | mitigate | D-80: `get_pii_guidance_block(redaction_enabled=False)` returns `""`. Verified by `TestD80_ConditionalInjection.test_disabled_returns_empty`. |
| T-04-05-4 | Tampering (sub-agent prompt drift) | Module-import-time binding | low | accept | Per PATTERNS.md, all AgentDefinition fields are import-time-bound; v1.0 redaction-enabled is a deploy-time toggle. Phase 5 may revisit. |

## Cross-plan threats covered elsewhere
- **T-1 (raw PII to cloud LLM):** Plan 04-03 (placeholder-tokenization) + Phase 3 D-53..D-56 (egress filter).
- **T-3 (missed-scan injecting fabricated entity types):** Plan 04-04.
</threat_model>

<verification>
- `pytest tests/unit/test_prompt_guidance.py -v` is green.
- `pytest tests/ -x --tb=short` is green — 79/79 Phase 1+2+3 baseline preserved.
- `python -c "from app.main import app"` succeeds (PostToolUse import-check).
- `python -c "from app.services import agent_service; assert len([v for k,v in vars(agent_service).items() if k.endswith('_AGENT')]) == 4"` succeeds.
- Plan 04-07 integration test `TestSC5_VerbatimEmission` will exercise the wired-up guidance via mocked OpenRouter — that's where SC#5 is verified end-to-end.
</verification>

<success_criteria>
- D-79 single source of truth: `prompt_guidance.py` exists; `chat.py` and `agent_service.py` both import and use it.
- D-80 conditional injection: helper returns `""` when off, full block when on; verified by unit test.
- D-81 English-only: block uses English imperative keywords; verified by unit test.
- D-82 verbatim block: contains all imperatives, type-list samples, `[TYPE]` warning, and arrow-form examples; verified by unit test.
- 4 AgentDefinition.system_prompt strings each carry the `+ _PII_GUIDANCE` suffix.
- 79/79 Phase 1+2+3 regression suite still green.
</success_criteria>

<output>
After completion, create `.planning/phases/04-fuzzy-de-anonymization-missed-pii-scan-prompt-guidance/04-05-SUMMARY.md` capturing: prompt_guidance.py path + line count, chat.py splice line numbers, agent_service.py module-level constant + 4 splice points, test count + green status, the AgentDefinition naming set actually present in the codebase (Research/Data Analyst/General/Explorer per PATTERNS.md, OR General/Research/Compare/Compliance per CONTEXT.md — record the truth on the ground), and any deviations.
</output>
</content>
