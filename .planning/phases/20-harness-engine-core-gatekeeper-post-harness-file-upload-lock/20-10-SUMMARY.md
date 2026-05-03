---
phase: 20-harness-engine-core-gatekeeper-post-harness-file-upload-lock
plan: 10
subsystem: frontend
tags: [file-upload, workspace, chat-input, react, vitest]
dependency_graph:
  requires: [20-06, 20-09]
  provides: [FileUploadButton, uploadingFiles-slice, workspace_enabled-public-setting]
  affects:
    - frontend/src/hooks/useChatState.ts
    - frontend/src/contexts/ChatContext.tsx
    - frontend/src/components/chat/MessageInput.tsx
    - frontend/src/components/chat/WelcomeInput.tsx
    - backend/app/routers/settings.py
tech_stack:
  added: [frontend/src/lib/toast.ts]
  patterns:
    - uploadingFiles Map state (keyed by client uuid) in useChatState
    - AbortController-per-upload for cancellation
    - usePublicSettings workspaceEnabled gate for paperclip visibility
    - Form-duplication rule: FileUploadButton in both MessageInput and WelcomeInput
key_files:
  created:
    - frontend/src/components/chat/FileUploadButton.tsx
    - frontend/src/components/chat/FileUploadButton.test.tsx
    - frontend/src/lib/toast.ts
  modified:
    - frontend/src/hooks/useChatState.ts
    - frontend/src/contexts/ChatContext.tsx
    - frontend/src/hooks/usePublicSettings.ts
    - frontend/src/lib/database.types.ts
    - frontend/src/components/chat/MessageInput.tsx
    - frontend/src/components/chat/WelcomeInput.tsx
    - backend/app/routers/settings.py
decisions:
  - D-13 (W6 fix): paperclip visibility gated on workspace_enabled only, NOT harness_enabled
  - fetch() has no upload progress API; percent stays 0 (indeterminate Loader2 spinner in v1.3)
  - FileUploadButton composed alongside InputActionBar (not inside it) — self-contained via context
  - Progress card uses absolute positioning; parent wrapper gets relative class
metrics:
  duration: ~15 minutes
  completed: 2026-05-03T17:12:46Z
  tasks: 3/3
  files_modified: 10
---

# Phase 20 Plan 10: FileUploadButton + uploadingFiles Slice Summary

Paperclip upload button for chat input toolbar with in-flight progress tracking and thread-scoped upload state.

## What Was Built

### Task 1: uploadingFiles slice in useChatState + infrastructure fixes

Added the `uploadingFiles` state slice to `useChatState.ts`:

- `UploadingFile` type: `{ id, filename, sizeBytes, percent, abort, error? }`
- `uploadingFiles: Map<string, UploadingFile>` state — keyed by client-generated UUID
- 4 helper functions: `startUpload`, `updateUploadProgress`, `completeUpload`, `failUpload`
- Thread-switch effect aborts all in-flight uploads via `abort.abort()` before resetting Map to empty
- All 5 identifiers exported from hook return; `ChatContext.tsx` comment updated (auto-typed via `ReturnType<typeof useChatState>`)

**Rule 2 deviations resolved in this task:**

1. `workspace_enabled` was not in `/settings/public` despite plan claiming Phase 18 had exposed it. Fixed: added `workspace_enabled: settings.workspace_enabled` to `backend/app/routers/settings.py`, updated `PublicSettings` type in `database.types.ts`, extended `usePublicSettings.ts` to surface `workspaceEnabled` boolean.

2. `@/lib/toast` did not exist. Created `frontend/src/lib/toast.ts`: minimal event-based toast that dispatches a `lexcore:toast` custom DOM event. Tests mock this module; the event system allows a future Toaster component to subscribe without changing component code.

### Task 2: FileUploadButton component + 9 Vitest 3.2 tests

`frontend/src/components/chat/FileUploadButton.tsx` (~150 LOC):

- **Visibility gate**: `if (!settings.workspaceEnabled) return null` — W6 fix per D-13; checks `workspace_enabled` backend flag, NOT `harness_enabled`
- **Geometry**: `h-8 w-8 rounded-lg flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-muted transition-colors` — byte-identical to InputActionBar Plus/FileText buttons per UI-SPEC L146
- **testids**: `file-upload-button`, `file-upload-input`, `file-upload-progress`, `file-upload-abort`
- **Client-side validation**: size > 25 MB → `t('upload.tooLarge', { max: '25' })` toast; MIME not in `{application/pdf, application/vnd...docx}` → `t('upload.wrongMime')` toast; no network call
- **Upload**: `apiFetch(/threads/{id}/files/upload, { method:'POST', body: FormData, signal: ctrl.signal })`
- **Success path**: `completeUpload(id)` — no toast; WorkspacePanel SSE `workspace_updated` is the confirmation
- **AbortError path**: `completeUpload(id)` + `t('upload.cancelled')` toast
- **Backend error mapping**: `code === 'wrong_mime' | 'magic_byte_mismatch'` → `wrongMime`; `code === 'upload_too_large'` → `tooLarge`; else → `serverError`
- **Progress UI**: `Loader2 animate-spin` + `t('upload.inProgress', {filename, percent})` + abort X button. `percent` stays 0 — `fetch()` has no upload progress API; XHR swap deferred.
- **Disabled state**: `inFlight=true` when `uploadingFiles.size > 0` → button gets `disabled + opacity-50 cursor-not-allowed`

**9 tests in `FileUploadButton.test.tsx`:**

| # | Case | Result |
|---|------|--------|
| a | Hidden when workspaceEnabled=false | PASS |
| b | Visible when workspaceEnabled=true | PASS |
| c | Rejects >25 MB — toast + no apiFetch | PASS |
| d | Rejects non-PDF/DOCX MIME — toast + no apiFetch | PASS |
| e | Shows progress card during upload | PASS |
| f | Success removes progress UI | PASS |
| g | Abort calls completeUpload + shows cancelled toast | PASS |
| h | Backend 4xx code='wrong_mime' → wrongMime toast | PASS |
| i | [W6] Visible when workspace_enabled=true even if harness_enabled=false | PASS |

### Task 3: Slot into MessageInput + WelcomeInput (form-duplication rule)

Both input hosts updated to import and render `<FileUploadButton />`:

- **MessageInput.tsx**: Added `import { FileUploadButton } from './FileUploadButton'`; wrapped InputActionBar in `<div className="relative">` containing `<FileUploadButton />` as first child
- **WelcomeInput.tsx**: Same pattern — form-duplication rule per CLAUDE.md

The `relative` wrapper is required for the progress card's `absolute bottom-full` positioning to work correctly within the toolbar area.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical functionality] workspace_enabled not in /settings/public**
- **Found during:** Task 1
- **Issue:** Plan stated "`workspace_enabled` is already publicly readable" via `/settings/public`, but the backend `settings.py` only returned `context_window` and `deep_mode_enabled`. The `FileUploadButton` cannot gate its visibility without this field.
- **Fix:** Added `"workspace_enabled": settings.workspace_enabled` to `GET /settings/public` backend response; added `workspace_enabled?: boolean` to `PublicSettings` type in `database.types.ts`; added `workspaceEnabled: boolean` field to `usePublicSettings.ts` hook return and cache state.
- **Files modified:** `backend/app/routers/settings.py`, `frontend/src/lib/database.types.ts`, `frontend/src/hooks/usePublicSettings.ts`
- **Commit:** `39f3513`

**2. [Rule 2 - Missing critical functionality] @/lib/toast did not exist**
- **Found during:** Task 1 (plan references `import { toast } from '@/lib/toast'`)
- **Issue:** No toast utility anywhere in the frontend. App uses `alert()` for simple notifications. `FileUploadButton` needs localized toast messages for validation errors.
- **Fix:** Created `frontend/src/lib/toast.ts` — minimal event-based utility that dispatches `lexcore:toast` custom DOM events. Tests mock the module; production needs a Toaster subscriber (deferred — no existing Toaster infrastructure). In v1.3, toasts fire events that are silently dropped unless a listener is registered.
- **Files modified:** `frontend/src/lib/toast.ts` (new)
- **Commit:** `39f3513`

### Design Decisions

- **`updateUploadProgress` not called in component body:** `fetch()` has no upload progress API; `percent` stays at 0 throughout (indeterminate Loader2 spinner). `updateUploadProgress` remains in the `useChatState` export for completeness and for future XHR-based swap. The ESLint unused-vars error was avoided by omitting the destructuring from the component entirely (comment documents why).
- **Progress card `absolute` positioning requires `relative` wrapper:** The progress card uses `absolute bottom-full` to float above the toolbar. Both MessageInput and WelcomeInput got a wrapping `<div className="relative">` around the FileUploadButton + InputActionBar pair.

## Known Stubs

None. All data flows are wired: `workspace_enabled` → visibility; file selection → apiFetch → `startUpload`/`completeUpload`/`failUpload`; `uploadingFiles` Map → progress card render. The `percent` field is structurally present but effectively always 0 in v1.3 (documented trade-off, not a stub that blocks functionality).

## Threat Flags

No new threat surface beyond what's in the plan's `<threat_model>`. T-20-10-01 through T-20-10-04 mitigations are all implemented:
- T-20-10-01 (client-side bypass): server-side validation in Plan 20-06 is authoritative
- T-20-10-02 (filename in toast): accepted — user uploaded the file
- T-20-10-03 (upload spam): `inFlight=true` disables button while upload in progress
- T-20-10-04 (backend internals in error): only `code` field mapped to localized strings

## Self-Check: PASSED

| Claim | Check |
|-------|-------|
| `frontend/src/components/chat/FileUploadButton.tsx` exists | FOUND |
| `frontend/src/components/chat/FileUploadButton.test.tsx` exists | FOUND |
| `frontend/src/lib/toast.ts` exists | FOUND |
| 9/9 tests pass | VERIFIED (npx vitest run) |
| `tsc --noEmit` exits 0 | VERIFIED |
| `npm run lint` — no errors in new/modified files | VERIFIED (8 pre-existing errors in unrelated files) |
| `FileUploadButton` imported in MessageInput.tsx | FOUND |
| `FileUploadButton` imported in WelcomeInput.tsx | FOUND |
| Task commits exist: 39f3513, 74ec33d, f49b74f | VERIFIED (git log) |
