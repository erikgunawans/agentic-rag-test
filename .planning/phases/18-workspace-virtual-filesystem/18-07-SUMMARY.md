---
plan: "18-07"
phase: "18-workspace-virtual-filesystem"
status: complete
wave: 6
self_check: PASSED
subsystem: workspace-panel-frontend
tags: [workspace, frontend, react, sse, i18n, vitest, tdd]
dependency_graph:
  requires: ["18-04", "18-06"]
  provides: ["WorkspacePanel sidebar component", "workspaceFiles state slice in useChatState", "workspace_updated SSE reducer", "ChatPage right-rail slot"]
  affects:
    - frontend/src/components/chat/WorkspacePanel.tsx
    - frontend/src/components/chat/WorkspacePanel.test.tsx
    - frontend/src/hooks/useChatState.ts
    - frontend/src/i18n/translations.ts
    - frontend/src/pages/ChatPage.tsx
tech_stack:
  added: []
  patterns:
    - "WorkspacePanel follows PlanPanel aside-sidebar pattern (flex-col w-72 shrink-0 border-l)"
    - "workspaceFiles state slice mirrors sandboxStreams lifecycle (thread-switch reset + SSE reducer)"
    - "TDD RED → GREEN: test file committed before implementation was verified passing"
    - "node_modules symlink in worktree to share main project dependencies"
key_files:
  created:
    - frontend/src/components/chat/WorkspacePanel.tsx
    - frontend/src/components/chat/WorkspacePanel.test.tsx
  modified:
    - frontend/src/hooks/useChatState.ts
    - frontend/src/i18n/translations.ts
    - frontend/src/pages/ChatPage.tsx
decisions:
  - "WorkspacePanel slotted into ChatPage.tsx (not AppLayout.tsx) — it sits in the flex-row right-rail alongside PlanPanel, same as PlanPanel's slot"
  - "apiFetch returns Response object, not parsed data; used .text() for inline content fetch"
  - "I18nProvider has no initialLocale prop; tests set localStorage('locale','en') in beforeEach to force English locale"
  - "node_modules symlink created in worktree frontend dir to allow vitest to resolve its config dependencies"
  - "formatBytes exported from WorkspacePanel.tsx (not lifted to shared util) — consistent with CodeExecutionPanel pattern of local util"
metrics:
  duration: "~25 minutes"
  completed_at: "2026-05-03T09:14Z"
  tasks_completed: 3
  files_changed: 5
---

# Phase 18 Plan 07: WorkspacePanel Frontend Summary

**One-liner:** WorkspacePanel React sidebar with workspaceFiles state slice, workspace_updated SSE reducer, inline text viewer, binary download, collapsible header, and i18n strings — 7 vitest tests green.

## What Was Built

### Task 1: workspaceFiles state slice in useChatState.ts

- Exported `WorkspaceFile` type (file_path, size_bytes, source, mime_type, updated_at)
- Added `workspaceFiles: WorkspaceFile[]` state with `useState<WorkspaceFile[]>([])`
- Initial fetch useEffect on `activeThreadId` change: `GET /threads/{id}/files` → `setWorkspaceFiles`
- Immediate reset to `[]` on thread switch (prevents stale cross-thread files from showing)
- `workspace_updated` SSE case in the event dispatch: `create` prepends, `update` moves to top, `delete` removes
- Exposed `workspaceFiles` in hook return value
- Reset in `handleNewChat()` for clean new-thread state
- TypeScript check: 0 errors

### Task 2: WorkspacePanel.tsx component + i18n strings

**Component features:**
- Renders `null` when `files.length === 0` (WS-11 visibility rule — decoupled from Deep Mode)
- `<aside data-testid="workspace-panel">` — matches PlanPanel structural pattern
- Collapsible header with ChevronDown/ChevronRight button; aria-label reflects state
- File list: Icon + file_path + formatBytes(size_bytes) + SourceBadge + relativeTime
- Text files (text/* or application/json): click → `apiFetch().text()` + inline `<pre>` view with `data-testid="workspace-content-{file_path}"`
- Binary files: click → `window.open('/threads/{id}/files/{encoded_path}', '_blank', 'noopener,noreferrer')` → browser follows 307 to signed URL
- Content cached in component state to avoid re-fetching
- `encodeURIComponent(f.file_path)` used before URL construction (T-18-27)
- React text children inside `<pre>` — auto-escaped XSS protection (T-18-25)
- CLAUDE.md compliance: `bg-background` on `<aside>`, no `backdrop-blur`

**i18n strings added (both `id` and `en`):**
| Key | Indonesian | English |
|-----|-----------|---------|
| workspace.title | Ruang Kerja | Workspace |
| workspace.empty | Belum ada berkas | No files yet |
| workspace.source.agent | agen | agent |
| workspace.source.sandbox | sandbox | sandbox |
| workspace.source.upload | unggahan | upload |
| workspace.download | Unduh | Download |
| workspace.view | Lihat | View |
| workspace.collapse | Sembunyikan | Collapse |
| workspace.expand | Tampilkan | Expand |

### Task 3: 7 vitest tests (TDD) + slot into ChatPage

**Slot location:** `frontend/src/pages/ChatPage.tsx` — the flex-row right-rail where PlanPanel already lives. WorkspacePanel renders immediately after PlanPanel.

```tsx
<WorkspacePanel threadId={activeThreadId} files={workspaceFiles} />
```

**Test results:** 7/7 PASS

| # | Test | Status |
|---|------|--------|
| 1 | renders nothing when files is empty | PASS |
| 2 | file row with path, size badge, agent source badge | PASS |
| 3 | clicking text file fetches content + inline view | PASS |
| 4 | clicking binary file calls window.open | PASS |
| 5 | multiple files render in provided order | PASS |
| 6 | source badges use variant-specific color classes | PASS |
| 7 | collapse button toggles file list visibility | PASS |

## Commits

| Hash | Description |
|------|-------------|
| `d14177a` | feat(18-07): add workspaceFiles state slice + workspace_updated SSE reducer + initial fetch |
| `5ea4271` | feat(18-07): build WorkspacePanel.tsx component + add i18n strings (WS-07, WS-08, WS-11) |
| `57c4eb1` | test(18-07): add 7 WorkspacePanel vitest tests covering all behaviors (WS-07, WS-08, WS-11) |
| `a0161a7` | feat(18-07): slot WorkspacePanel into ChatPage right-rail (WS-11) |

## Deviations from Plan

### 1. [Rule 1 - Bug] apiFetch returns Response, not parsed data

**Found during:** Task 1 implementation
**Issue:** The plan showed `apiFetch(\`/threads/${threadId}/files\`).then((r: WorkspaceFile[]) => ...)` treating apiFetch return as parsed JSON. But `apiFetch` returns a `Response` object.
**Fix:** Added `.then((r) => r.json() as Promise<WorkspaceFile[]>)` for the list fetch. Used `.text()` for file content fetch in WorkspacePanel.
**Files modified:** `useChatState.ts`, `WorkspacePanel.tsx`

### 2. [Rule 1 - Bug] Test: I18nProvider uses localStorage default locale (Indonesian)

**Found during:** Task 3 TDD RED phase (Test 2 failure)
**Issue:** Test asserted badge text `'agent'` but I18nProvider reads localStorage and defaulted to `'id'` locale (Indonesian) returning `'agen'`.
**Fix:** Added `localStorage.setItem('locale', 'en')` in `beforeEach` to force English for badge text assertions.
**Files modified:** `WorkspacePanel.test.tsx`

### 3. [Rule 1 - Bug] Test 5: getAllByRole('button', {name:''}) invalid query

**Found during:** Task 3 TDD RED phase (Test 5 failure)
**Issue:** `getAllByRole('button', { name: '' })` throws because buttons have accessible names.
**Fix:** Removed unused variable assignment; used direct testId queries.
**Files modified:** `WorkspacePanel.test.tsx`

### 4. [Rule 3 - Infra] node_modules symlink for vitest in worktree

**Found during:** Task 3 test execution
**Issue:** Worktree `frontend/` had no `node_modules` — vitest couldn't find its config deps.
**Fix:** Created symlink `worktree/frontend/node_modules -> main/frontend/node_modules`. TypeScript and vitest both use the shared installation.

## Must-Haves Verified

- [x] WorkspacePanel renders only when files exist (WS-11) — `if (files.length === 0) return null`
- [x] Panel shows file_path, formatBytes(size_bytes), source badge, relativeTime
- [x] Text files open inline view (WS-08) — apiFetch + .text() + `<pre>` with data-testid
- [x] Binary files trigger download via GET endpoint (WS-08) — window.open with 307-redirect
- [x] workspace_updated SSE events update panel without refetch — setWorkspaceFiles reducer
- [x] Indonesian + English i18n strings provided — 9 keys each language
- [x] All 7 vitest tests pass
- [x] TypeScript compiles clean (0 errors)

## Known Stubs

None — WorkspacePanel reads live `workspaceFiles` from real SSE events and initial fetch. No placeholder data.

## Threat Flags

None — T-18-25, T-18-26, T-18-27 from the plan's threat register are all mitigated:
- T-18-25: React text children auto-escaping in `<pre>`
- T-18-26: accepted per plan
- T-18-27: `encodeURIComponent` applied to all `file_path` values in URL construction

## Self-Check: PASSED
