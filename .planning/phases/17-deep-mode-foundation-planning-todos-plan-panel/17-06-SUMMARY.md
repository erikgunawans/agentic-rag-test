---
phase: 17-deep-mode-foundation-planning-todos-plan-panel
plan: "06"
subsystem: frontend-chat-ui
tags: [deep-mode, toggle, badge, ui, vitest, tdd, i18n, dark-launch]
dependency_graph:
  requires: [17-02]
  provides: [DEEP-01-ui, DEEP-04-consumer, DEEP-03-byte-identical-gate]
  affects: [MessageInput, WelcomeInput, MessageView, AgentBadge, InputActionBar, useChatState, usePublicSettings]
tech_stack:
  added: []
  patterns:
    - Per-message toggle state with post-send reset (D-24)
    - Feature flag gating via deepModeEnabled from /settings/public (D-16)
    - Byte-identical payload preservation when toggle off (DEEP-03)
    - TDD: RED commit → GREEN commits (per-task)
key_files:
  created:
    - frontend/src/components/chat/__tests__/DeepModeToggle.test.tsx
    - frontend/src/components/chat/__tests__/MessageView.deepMode.test.tsx
  modified:
    - backend/app/routers/settings.py
    - frontend/src/hooks/usePublicSettings.ts
    - frontend/src/lib/database.types.ts
    - frontend/src/components/chat/InputActionBar.tsx
    - frontend/src/components/chat/MessageInput.tsx
    - frontend/src/components/chat/WelcomeInput.tsx
    - frontend/src/components/chat/AgentBadge.tsx
    - frontend/src/components/chat/MessageView.tsx
    - frontend/src/hooks/useChatState.ts
    - frontend/src/i18n/translations.ts
decisions:
  - "Used InputActionBar to centralize toggle rendering; both MessageInput and WelcomeInput share it (form-duplication rule satisfied without duplicating toggle code)"
  - "onSend signature extended to (message, opts?) instead of separate prop, matching existing handleSendMessage pattern in useChatState"
  - "data-testid='send-button' added for language-agnostic test selection (i18n key chat.send='Kirim pesan' breaks role/name queries)"
  - "DeepModeBadge uses inline oklch styling to avoid Tailwind purge issues with dynamic purple-accent values; no glass"
metrics:
  duration: "~25 minutes"
  completed: "2026-05-03"
  task_count: 3
  file_count: 11
---

# Phase 17 Plan 06: Deep Mode Toggle and Badge Summary

Per-message Deep Mode toggle button (DEEP-01) + Deep Mode badge on assistant messages (DEEP-04 consumer) implemented with TDD.

## One-Liner

Per-message Deep Mode UI toggle (ghost→filled purple accent) gated on `deep_mode_enabled` feature flag, with assistant-message badge consuming the `messages.deep_mode` column.

## What Was Built

### Task 1: Backend settings + failing tests (RED)

- `backend/app/routers/settings.py`: extended `GET /settings/public` to include `deep_mode_enabled: settings.deep_mode_enabled`. Return type widened from `dict[str, int]` to `dict`.
- `frontend/src/lib/database.types.ts`: added `deep_mode?: boolean` to `Message`, added `deep_mode_enabled: boolean` to `PublicSettings`.
- `frontend/src/hooks/usePublicSettings.ts`: added `deepModeEnabled: boolean` to `PublicSettingsState`; returned from hook.
- Two test files created with 11 failing tests (RED):
  - `DeepModeToggle.test.tsx`: 7 tests — visibility, aria semantics, click toggle, send with flag on/off, reset after send
  - `MessageView.deepMode.test.tsx`: 4 tests — badge renders on deep_mode=true, hidden on false, hidden for user messages

### Task 2: Toggle implementation (GREEN for toggle tests)

- `frontend/src/components/chat/InputActionBar.tsx`: Deep Mode toggle button added
  - Conditional on `deepModeEnabled` prop (D-16 dark-launch invariant)
  - `data-testid="deep-mode-toggle"`, `aria-pressed`, `aria-label` (i18n key)
  - Styling: ghost (off) → filled `oklch(0.55 0.22 290)` purple accent (on)
  - `Brain` icon from lucide-react; no glass/backdrop-blur (CLAUDE.md)
  - `data-testid="send-button"` added for language-agnostic test selection
- `frontend/src/components/chat/MessageInput.tsx`:
  - `useState(false)` for per-message `deepMode`; reset after `onSend`
  - `onSend(message, opts?)` signature extended for `deepMode` flag
  - Reads `deepModeEnabled` from `usePublicSettings()`
- `frontend/src/components/chat/WelcomeInput.tsx`: mirrors MessageInput (CLAUDE.md form-duplication rule)
- `frontend/src/hooks/useChatState.ts`:
  - `sendMessageToThread`, `handleSendMessage`, `handleSendFirstMessage` accept `opts?: { deepMode?: boolean }`
  - Only adds `deep_mode: true` to POST `/chat/stream` body when truthy (DEEP-03 byte-identical)
- `frontend/src/i18n/translations.ts`: added `chat.deepMode.toggleLabel`, `chat.deepMode.toggleAriaLabel`, `chat.deepMode.badge` for `id` (Indonesian default) and `en`

### Task 3: Badge implementation (GREEN for badge tests)

- `frontend/src/components/chat/AgentBadge.tsx`: added `DeepModeBadge` export
  - `Brain` icon + `chat.deepMode.badge` i18n text
  - `data-testid="deep-mode-badge"` for test assertions
  - Inline oklch styling for purple-accent background/text; no glass
- `frontend/src/components/chat/MessageView.tsx`:
  - Imports `DeepModeBadge` from `AgentBadge`
  - Renders `<DeepModeBadge />` when `msg.role === 'assistant' && msg.deep_mode`
  - Reads `msg.deep_mode` from `Message.deep_mode?` (migration 038 column)

## Test Results

- DeepModeToggle.test.tsx: **7/7 pass**
- MessageView.deepMode.test.tsx: **4/4 pass**
- Full test suite: **54/54 pass** (zero regressions)

## Verification Against Plan Criteria

| Criterion | Status |
|-----------|--------|
| Toggle hidden when deep_mode_enabled=false | PASS |
| Toggle visible when deep_mode_enabled=true | PASS |
| Toggle click flips aria-pressed | PASS |
| Send with toggle ON → deep_mode: true in payload | PASS |
| Send with toggle OFF → deep_mode omitted (DEEP-03) | PASS |
| Toggle resets to off after send (D-24) | PASS |
| Mobile + desktop variants updated (WelcomeInput too) | PASS — InputActionBar shared by both |
| Badge on assistant deep_mode=true messages | PASS |
| Badge hidden on deep_mode=false messages | PASS |
| Badge hidden for user messages | PASS |
| i18n keys in id.json (default) and en.json | PASS |
| tsc --noEmit clean | PASS |
| No glass / backdrop-blur on persistent panels | PASS |

## Deviations from Plan

### Auto-deviation: InputActionBar centralized toggle

The plan suggested adding the toggle "button next to Send" directly in `MessageInput.tsx` and `WelcomeInput.tsx`. Instead, the toggle was added to the shared `InputActionBar.tsx` component that both forms already use. This honors the CLAUDE.md form-duplication rule without duplicating the toggle code, and keeps the props pattern consistent with the existing `webSearchEnabled`/`onToggleWebSearch` pattern.

### Auto-deviation: data-testid on send button

Added `data-testid="send-button"` to the send button in `InputActionBar.tsx`. The tests initially used `{ name: /send/i }` which fails because the i18n key `chat.send` resolves to "Kirim pesan" in Indonesian (the default locale). The testid makes tests locale-agnostic, which is the correct approach per project i18n conventions.

### Auto-deviation: Inline oklch for DeepModeBadge styling

The plan suggested using `bg-purple-accent/10 text-purple-accent` Tailwind classes. However, the project's purple accent is a CSS custom property (`--color-accent-purple`) not mapped to a Tailwind utility class. Used inline `style` with `oklch(0.55 0.22 290)` values (matching the toggle button's purple accent) to avoid Tailwind class-not-found issues. This is consistent with the existing design token usage in the codebase.

## Known Stubs

None. The toggle and badge are fully wired:
- Toggle: `deepModeEnabled` from live `/settings/public` endpoint; `deep_mode: true` in actual POST body
- Badge: reads `msg.deep_mode` from the actual Supabase message row (migration 038 column)

## Threat Flags

No new threat surface introduced. T-17-14 (UI bypass) is acknowledged: the server-side gate (Plan 17-04, `deep_mode_enabled=false` → 400 rejection) is the authoritative control. The UI hide is convenience only, as documented in the threat register.

## Self-Check: PASSED

Created files exist:
- `frontend/src/components/chat/__tests__/DeepModeToggle.test.tsx` — FOUND
- `frontend/src/components/chat/__tests__/MessageView.deepMode.test.tsx` — FOUND

Commits exist:
- `0ec0f95` (test/RED) — FOUND
- `3683734` (feat/toggle GREEN) — FOUND
- `fe74ec9` (feat/badge GREEN) — FOUND
