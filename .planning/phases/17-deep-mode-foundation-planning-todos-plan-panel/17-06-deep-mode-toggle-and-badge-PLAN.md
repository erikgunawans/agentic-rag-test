---
phase: 17-deep-mode-foundation-planning-todos-plan-panel
plan: 06
type: execute
wave: 3
depends_on: [02]
files_modified:
  - frontend/src/components/chat/MessageInput.tsx
  - frontend/src/components/chat/WelcomeInput.tsx
  - frontend/src/components/chat/MessageView.tsx
  - frontend/src/components/chat/AgentBadge.tsx
  - frontend/src/hooks/useChatState.tsx
  - frontend/src/lib/api.ts
  - frontend/src/i18n/en.json
  - frontend/src/i18n/id.json
  - frontend/src/components/chat/__tests__/DeepModeToggle.test.tsx
  - frontend/src/components/chat/__tests__/MessageView.deepMode.test.tsx
autonomous: true
requirements: [DEEP-01, DEEP-04]
must_haves:
  truths:
    - "MessageInput.tsx renders a Deep Mode toggle button next to Send (per-message toggle, not per-thread); toggle resets to off after each message is sent (per-message semantic, D-24)."
    - "WelcomeInput.tsx (welcome screen first-message path) also renders the same toggle (form duplication rule, CLAUDE.md)."
    - "Toggle is hidden entirely when settings.deep_mode_enabled (from GET /settings/public) is false (D-16 dark-launch invariant)."
    - "Toggle visual: ghost button when off, filled purple-accent when on; uses existing 2026 Calibrated Restraint design tokens (D-24); no glass / backdrop-blur (CLAUDE.md panel rule)."
    - "Toggle adds aria-pressed semantics for accessibility; supports keyboard activation."
    - "When toggle is on, the request body sent to POST /chat includes deep_mode: true; otherwise the field is omitted (preserves byte-identical payload for non-deep-mode requests, DEEP-03)."
    - "MessageView.tsx renders a 'Deep Mode' badge on assistant messages whose row has deep_mode=true (DEEP-04 / MIG-04 consumer; D-23)."
    - "Badge styling: subtle purple-accent text/icon (NOT a loud chip), uses lucide-react icon, tokens from index.css :root."
    - "i18n strings for 'Deep Mode' label, toggle aria-label, badge text exist in both id.json (default) and en.json — Indonesian-first per project convention."
    - "useChatState reducer accepts a per-message deep_mode boolean as part of the send-message action and forwards it to api.ts; not persisted across messages."
    - "api.ts sendChatMessage signature accepts an optional deep_mode flag and adds it to POST /chat body when true."
    - "Vitest tests pass: DeepModeToggle renders correctly when flag is on, hidden when off, click toggles state, send action passes deep_mode through; MessageView renders badge when deep_mode=true, hides when false."
  artifacts:
    - path: "frontend/src/components/chat/MessageInput.tsx"
      provides: "Deep Mode toggle button (mobile + desktop variants per CLAUDE.md form-duplication rule)."
      contains: "deepMode"
    - path: "frontend/src/components/chat/WelcomeInput.tsx"
      provides: "Deep Mode toggle on welcome screen first-message input."
      contains: "deepMode"
    - path: "frontend/src/components/chat/MessageView.tsx"
      provides: "Deep Mode badge rendering on assistant rows with deep_mode=true."
      contains: "deep_mode"
    - path: "frontend/src/components/chat/AgentBadge.tsx"
      provides: "Optionally extended for Deep Mode variant; OR new sibling DeepModeBadge.tsx in same file."
      contains: "Deep Mode"
    - path: "frontend/src/hooks/useChatState.tsx"
      provides: "Reducer extension carrying per-message deep_mode through the send action."
      contains: "deep_mode"
    - path: "frontend/src/lib/api.ts"
      provides: "sendChatMessage signature accepts deep_mode: boolean."
      contains: "deep_mode"
    - path: "frontend/src/i18n/en.json"
      provides: "English strings for Deep Mode toggle + badge."
      contains: "deepMode"
    - path: "frontend/src/i18n/id.json"
      provides: "Indonesian strings for Deep Mode toggle + badge."
      contains: "deepMode"
    - path: "frontend/src/components/chat/__tests__/DeepModeToggle.test.tsx"
      provides: "Vitest tests for toggle visibility, click behavior, aria semantics, hidden-when-flag-off."
    - path: "frontend/src/components/chat/__tests__/MessageView.deepMode.test.tsx"
      provides: "Vitest tests for badge rendering on deep_mode=true rows; hidden on deep_mode=false."
  key_links:
    - from: "frontend/src/components/chat/MessageInput.tsx"
      to: "frontend/src/lib/api.ts"
      via: "deep_mode prop forwarded to sendChatMessage"
      pattern: "deep_mode"
    - from: "frontend/src/components/chat/MessageView.tsx"
      to: "messages.deep_mode (DB column)"
      via: "render badge when row.deep_mode === true"
      pattern: "deep_mode"
---

<objective>
Add the Deep Mode toggle button (DEEP-01) and the Deep Mode badge (DEEP-04 consumer) to the frontend.

Per D-24: ghost button next to Send when off, filled purple accent when on; both `MessageInput.tsx` (mobile + desktop variants per CLAUDE.md form-duplication rule) and `WelcomeInput.tsx` get the toggle.

Per D-16: toggle is hidden entirely when `deep_mode_enabled=false` (read from GET /settings/public, which already exposes feature flags per Phase 12 / CTX-03). When the flag is off, the user can't even attempt deep mode — DEEP-03 byte-identical UX preserved.

Per D-23: subtle Deep Mode badge on assistant messages with `deep_mode=true` (the DB column added in Plan 17-01). Uses existing `AgentBadge.tsx` (extension) or a new sibling component, follows 2026 Calibrated Restraint tokens, no glass.

Per D-26: state flows through existing `useChatState` reducer with a NEW action carrying the per-message `deep_mode` boolean. NOT persisted across messages (per-message semantic, DEEP-01).

Wave 3: depends on Plan 17-02 (deep_mode_enabled flag exposed via GET /settings/public, which already exists; just need to confirm `deep_mode_enabled` is included in the response — verify in Task 1).

Output: toggle in 2 input components, badge in MessageView, reducer/api changes, i18n strings, Vitest tests.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/STATE.md
@.planning/phases/17-deep-mode-foundation-planning-todos-plan-panel/17-CONTEXT.md
@.planning/phases/17-deep-mode-foundation-planning-todos-plan-panel/17-02-config-loop-caps-and-feature-flag-PLAN.md
@frontend/src/components/chat/MessageInput.tsx
@frontend/src/components/chat/WelcomeInput.tsx
@frontend/src/components/chat/MessageView.tsx
@frontend/src/components/chat/AgentBadge.tsx
@frontend/src/hooks/useChatState.tsx
@frontend/src/lib/api.ts

<interfaces>
**Existing `MessageInput.tsx` and `WelcomeInput.tsx` action bar pattern** — both already host buttons next to Send (e.g., InputActionBar). The Deep Mode toggle is added to the action bar, NOT inside Send. CLAUDE.md form-duplication rule means both components must be updated; missing one is a known sharp edge (DocumentCreationPage gotcha).

**Existing GET /settings/public** (Phase 12 / CTX-03) — exposes `llm_context_window` and other public settings. Plan 17-06 Task 1 verifies (and adds if necessary) `deep_mode_enabled` to this response. If missing, extend `backend/app/routers/settings.py` to include `deep_mode_enabled: settings.deep_mode_enabled` and add a unit test.

**Existing `useChatState.tsx` reducer** — already handles SEND_MESSAGE action. Extend to accept `deep_mode: boolean` in the action payload (default false). Reducer does not persist across actions; toggle resets after each send.

**Existing `lib/api.ts` `sendChatMessage(...)` signature** — already accepts (thread_id, content, ...). Add an optional `deep_mode?: boolean` parameter; only include `deep_mode: true` in the JSON body when truthy (omit when false to preserve byte-identical legacy payload — DEEP-03 invariant).

**Existing `MessageView.tsx`** — renders assistant message rows. Each `msg` has fields including (after Plan 17-01) `msg.deep_mode: boolean`. Badge rendering: `{msg.role === 'assistant' && msg.deep_mode && <DeepModeBadge />}`.

**Existing `AgentBadge.tsx`** — already a small badge component for agent-mode indicators. Either extend it with a `deepMode` prop variant OR add a sibling `DeepModeBadge` in the same file. Discretionary; tests assert presence.

**Existing 2026 Calibrated Restraint design tokens** — purple accent `--color-accent-purple` etc. in `frontend/src/index.css :root`. Deep Mode badge uses these tokens directly.

**i18n** — `frontend/src/i18n/id.json` is default, `en.json` is fallback. Add keys `chat.deepMode.toggleAriaLabel`, `chat.deepMode.toggleLabel` ("Deep Mode" both langs since term is product-name), `chat.deepMode.badge`. Use existing `useTranslation()` hook to consume.

**Vitest 3.2 (v1.2 D-P16-02)** — co-located `__tests__/` convention; component tests use `@testing-library/react`. Look at `frontend/src/components/chat/CodeExecutionPanel.test.tsx` for the pattern.
</interfaces>

</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Verify+extend GET /settings/public to include deep_mode_enabled, then write failing Vitest tests</name>
  <files>backend/app/routers/settings.py, frontend/src/components/chat/__tests__/DeepModeToggle.test.tsx, frontend/src/components/chat/__tests__/MessageView.deepMode.test.tsx</files>
  <action>
    **1. Backend: extend GET /settings/public to include deep_mode_enabled.**

    Read `backend/app/routers/settings.py`. Find the `/public` endpoint (Phase 12 / CTX-03). Add `deep_mode_enabled: settings.deep_mode_enabled` to the response model and handler.

    Quick smoke verify backend:
    ```
    cd backend && source venv/bin/activate && python -c "from app.routers.settings import _public_settings_response; r = _public_settings_response(); assert 'deep_mode_enabled' in r; print('OK')"
    ```
    (or whatever the existing helper is named — replicate from Phase 12 idiom).

    **2. Frontend: write failing Vitest tests.**

    Create `frontend/src/components/chat/__tests__/DeepModeToggle.test.tsx`:
    - test_toggle_hidden_when_flag_off: mock GET /settings/public to return deep_mode_enabled=false; render MessageInput → no element with role/test-id 'deep-mode-toggle'.
    - test_toggle_visible_when_flag_on: mock to return deep_mode_enabled=true → toggle renders.
    - test_toggle_starts_off: render with flag on → button has aria-pressed="false".
    - test_toggle_click_flips: click toggle → aria-pressed="true"; click again → "false".
    - test_send_passes_deep_mode_true: enable toggle, click Send with content "hi" → mock sendChatMessage receives `{deep_mode: true, ...}`.
    - test_send_omits_deep_mode_when_off: disabled toggle, send "hi" → sendChatMessage receives object WITHOUT deep_mode key.
    - test_toggle_resets_after_send: toggle on, send → after send, aria-pressed reset to "false" (per-message semantic, D-24).

    Create `frontend/src/components/chat/__tests__/MessageView.deepMode.test.tsx`:
    - test_badge_renders_when_deep_mode_true: render MessageView with assistant msg having deep_mode=true → badge with text "Deep Mode" (or i18n key) is in document.
    - test_badge_hidden_when_deep_mode_false: msg.deep_mode=false → no badge element.
    - test_badge_hidden_for_user_messages: msg.role='user' with deep_mode=true → no badge (user messages don't render badge).

    Run:
    ```
    cd frontend && npx vitest run src/components/chat/__tests__/DeepModeToggle.test.tsx src/components/chat/__tests__/MessageView.deepMode.test.tsx
    ```
    Expect ~10 failures (components not extended yet — RED).
  </action>
  <verify>
    <automated>cd backend && source venv/bin/activate && python -c "from app.routers.settings import router; print('OK')" | grep -q OK && cd frontend && npx vitest run src/components/chat/__tests__/DeepModeToggle.test.tsx src/components/chat/__tests__/MessageView.deepMode.test.tsx 2>&1 | grep -cE "FAIL|fail" | grep -q "[1-9]"</automated>
  </verify>
  <done>Backend `/settings/public` returns deep_mode_enabled. Two test files exist with ~10 tests; all currently failing (toggle / badge not implemented).</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Implement Deep Mode toggle in MessageInput.tsx + WelcomeInput.tsx + reducer + api</name>
  <files>frontend/src/components/chat/MessageInput.tsx, frontend/src/components/chat/WelcomeInput.tsx, frontend/src/hooks/useChatState.tsx, frontend/src/lib/api.ts, frontend/src/i18n/en.json, frontend/src/i18n/id.json</files>
  <action>
    **1. i18n strings**

    `frontend/src/i18n/id.json` — add keys:
    ```json
    "chat": {
      "deepMode": {
        "toggleLabel": "Deep Mode",
        "toggleAriaLabel": "Aktifkan Deep Mode untuk pesan ini",
        "badge": "Deep Mode"
      },
      ...
    }
    ```
    `frontend/src/i18n/en.json` — same keys with English aria-label "Enable Deep Mode for this message".

    **2. lib/api.ts — extend sendChatMessage**

    Add optional `deep_mode?: boolean` param. In the request body, only include `deep_mode: true` when truthy (omit when false / undefined). DEEP-03 invariant: legacy payload preserved when toggle off.

    ```ts
    export async function sendChatMessage(args: {
      thread_id: string;
      content: string;
      deep_mode?: boolean;
      // ...
    }) {
      const body: Record<string, unknown> = { thread_id: args.thread_id, content: args.content, ... };
      if (args.deep_mode) body.deep_mode = true;
      // ...
    }
    ```

    **3. useChatState.tsx — reducer extension**

    Extend the SEND_MESSAGE action payload type with `deep_mode?: boolean`. Forward to api.ts. Do NOT persist `deepMode` slice across actions — the toggle is per-message and resets on the component side.

    **4. MessageInput.tsx — toggle button**

    Read `useFeatureFlags()` (or whatever existing hook reads from GET /settings/public). Render the toggle conditionally on `deep_mode_enabled`:

    ```tsx
    {deepModeEnabled && (
      <button
        type="button"
        aria-pressed={deepMode}
        aria-label={t('chat.deepMode.toggleAriaLabel')}
        data-testid="deep-mode-toggle"
        onClick={() => setDeepMode(!deepMode)}
        className={cn(
          "btn-ghost",
          deepMode && "bg-purple-accent text-white"
        )}
      >
        {t('chat.deepMode.toggleLabel')}
      </button>
    )}
    ```

    Local `useState<boolean>` for the toggle. On send, pass `deep_mode={deepMode}` to the parent send handler, then `setDeepMode(false)` to reset (per-message semantic).

    NO glass / backdrop-blur (CLAUDE.md panel rule). Use existing button tokens.

    Make BOTH mobile and desktop variants of MessageInput.tsx (form-duplication rule). If there are two separate panels (e.g., `MessageInputMobile` + `MessageInputDesktop`), update both.

    **5. WelcomeInput.tsx — same toggle**

    Mirror the MessageInput.tsx implementation. Toggle state, conditional rendering, send handler.

    Re-run Vitest:
    ```
    cd frontend && npx vitest run src/components/chat/__tests__/DeepModeToggle.test.tsx
    ```
    All 7 tests should pass.

    Verify type-check + lint:
    ```
    cd frontend && npx tsc --noEmit && npm run lint
    ```
  </action>
  <verify>
    <automated>cd frontend && npx vitest run src/components/chat/__tests__/DeepModeToggle.test.tsx 2>&1 | grep -E "PASS|pass" | head -1 && npx tsc --noEmit 2>&1 | grep -E "error" | grep -v "^$" | wc -l | grep -q "^0"</automated>
  </verify>
  <done>Toggle button live in MessageInput + WelcomeInput; conditional on deep_mode_enabled; click flips aria-pressed; sendChatMessage receives deep_mode flag; resets after send. 7 toggle tests pass. tsc clean, lint clean.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: Implement Deep Mode badge in MessageView.tsx + AgentBadge.tsx</name>
  <files>frontend/src/components/chat/MessageView.tsx, frontend/src/components/chat/AgentBadge.tsx</files>
  <action>
    Edit `AgentBadge.tsx` (or add a sibling `DeepModeBadge` component in the same file — discretionary). Use existing 2026 Calibrated Restraint tokens (purple accent), no glass:

    ```tsx
    export function DeepModeBadge() {
      const { t } = useTranslation();
      return (
        <span
          className="inline-flex items-center gap-1 rounded-md bg-purple-accent/10 px-1.5 py-0.5 text-xs font-medium text-purple-accent"
          data-testid="deep-mode-badge"
        >
          <Brain size={12} aria-hidden />
          {t('chat.deepMode.badge')}
        </span>
      );
    }
    ```

    `<Brain>` icon from lucide-react (already a project dep). Replace with another lucide icon if one is more appropriate; the choice is Claude's discretion.

    Edit `MessageView.tsx` — render badge on assistant messages with deep_mode=true:

    ```tsx
    {msg.role === 'assistant' && msg.deep_mode && <DeepModeBadge />}
    ```

    Place near the existing role/agent-mode badge area. NOT in user messages.

    Confirm Message type in `frontend/src/types` includes optional `deep_mode?: boolean` (the field will be returned by GET /threads/{id}/messages once Plan 17-01 migration applies). If the type doesn't have it, add the field (plain TS type extension, no DB write).

    Re-run badge tests:
    ```
    cd frontend && npx vitest run src/components/chat/__tests__/MessageView.deepMode.test.tsx
    ```
    All 3 tests pass.

    Type + lint:
    ```
    cd frontend && npx tsc --noEmit && npm run lint
    ```
  </action>
  <verify>
    <automated>cd frontend && npx vitest run src/components/chat/__tests__/MessageView.deepMode.test.tsx 2>&1 | grep -q "3 passed" && npx tsc --noEmit 2>&1 | grep -E "error" | grep -v "^$" | wc -l | grep -q "^0" && npm run lint 2>&1 | grep -cE "error" | grep -q "^0$"</automated>
  </verify>
  <done>Deep Mode badge component implemented; renders on assistant messages with deep_mode=true; hidden otherwise. 3 badge tests pass. Type-check and lint clean.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| client UI→backend feature flag | Browser must respect deep_mode_enabled flag — server-side check (Plan 17-04) is the authority |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-17-14 | E (Elevation of Privilege) | client bypasses UI gate, sends deep_mode=true while flag off | mitigate | Server-side gate in Plan 17-04 returns 400 regardless of UI state; UI hide is convenience only |
| T-17-15 | I (Information Disclosure) | badge leaks PII via tooltip | accept | Badge text is fixed string "Deep Mode"; no PII surface |

</threat_model>

<verification>
- Toggle visible only when deep_mode_enabled=true.
- Toggle click flips aria-pressed and forwards deep_mode to API.
- Toggle resets to off after send (per-message).
- Mobile + desktop variants both updated (form-duplication rule).
- Welcome screen first-message input has the toggle too.
- Badge renders on deep_mode=true assistant rows; hidden otherwise.
- 10 Vitest tests pass.
- tsc + ESLint clean.
- i18n strings present in id.json (default) and en.json.
</verification>

<success_criteria>
- DEEP-01 covered: per-message UI toggle.
- DEEP-04 (consumer side): badge surfaces persisted deep_mode column.
- DEEP-03 byte-identical UX preserved when flag off (toggle hidden, no payload field added).
- D-24 / D-23 design decisions honored.
- CLAUDE.md form-duplication rule honored (mobile + desktop + welcome screen all updated).
</success_criteria>

<output>
After completion, create `.planning/phases/17-deep-mode-foundation-planning-todos-plan-panel/17-06-SUMMARY.md`
</output>
