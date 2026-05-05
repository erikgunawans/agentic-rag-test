---
phase: 22-contract-review-harness-docx-deliverable
plan: 11
type: execute
wave: 7
depends_on: ["22-03", "22-10"]
files_modified:
  - frontend/src/lib/database.types.ts
  - frontend/src/hooks/useChatState.ts
  - frontend/src/components/chat/MessageView.tsx
  - frontend/src/components/chat/WorkspacePanel.tsx
  - frontend/src/i18n/translations.ts
  - frontend/src/components/chat/__tests__/MessageView.harness-artifact.test.tsx
autonomous: true
requirements: [CR-08, DOCX-08]
must_haves:
  truths:
    - "REVIEW #11: i18n is `frontend/src/i18n/translations.ts` (FLAT key style, not nested JSON in i18n/locales/*.json — those don't exist)"
    - "REVIEW #11: Message type lives in `frontend/src/lib/database.types.ts:27` (NOT inline in useChatState.ts)"
    - "REVIEW #8 closed: SSEEvent union extended for `harness_artifact` (with harness_run_id + harness_mode + assistant_message_id) AND `summary_complete` (already emitted by post_harness.py:228, currently unhandled in frontend) AND `workspace_updated` (engine emission per plan 22-03)"
    - "REVIEW #8 closed: Message type gets `harness_run_id` (correlation anchor) AND `harness_mode` AND `harness_artifact` fields"
    - "REVIEW #8 closed: useChatState reducer handles summary_complete → marks the assistant message it created with harness_run_id + harness_mode; subsequent harness_artifact event finds that message by harness_run_id and attaches the artifact deterministically (no timing heuristics)"
    - "MessageView renders download chip when msg.harness_artifact present + ok; renders fallback note when ok=false"
    - "WorkspaceFile.source union includes 'harness'; SOURCE_COLORS map has the entry"
    - "i18n keys added (FLAT) in translations.ts: `harness.docx.downloadAriaLabel`, `harness.docx.fallbackAriaLabel`, `harness.docx.fallbackDefault`, `workspace.source.harness`"
    - "No glass / backdrop-blur on the persistent download chip"
  artifacts:
    - path: "frontend/src/lib/database.types.ts"
      provides: "SSEEvent harness_artifact + summary_complete variants; Message.harness_run_id/harness_mode/harness_artifact fields; WorkspaceFile.source 'harness' union member"
      contains: "harness_artifact"
    - path: "frontend/src/hooks/useChatState.ts"
      provides: "Reducer cases for harness_artifact + summary_complete; deterministic correlation via harness_run_id"
      contains: "summary_complete"
    - path: "frontend/src/components/chat/MessageView.tsx"
      provides: "Download chip + fallback note rendering"
      contains: "harness-docx-chip"
    - path: "frontend/src/components/chat/WorkspacePanel.tsx"
      provides: "harness SOURCE_COLORS entry"
      contains: "harness:"
    - path: "frontend/src/i18n/translations.ts"
      provides: "FLAT i18n keys for harness.docx.* and workspace.source.harness in id + en blocks"
      contains: "harness.docx.downloadAriaLabel"
  key_links:
    - from: "harness_engine.py harness_artifact + workspace_updated SSE events (plan 22-03 / REVIEW #7 + #8)"
      to: "useChatState reducer"
      via: "harness_run_id correlation against the assistant message tagged by summary_complete"
      pattern: "harness_run_id"
    - from: "post_harness.py summary_complete event (existing, line 228+267)"
      to: "useChatState reducer (currently UNHANDLED — add now per REVIEW #8)"
      via: "assistant_message_id field gives the persisted assistant Message id"
      pattern: "summary_complete"
---

<objective>
Wire the frontend to render the DOCX deliverable. Three review findings drive this plan:

1. **REVIEW #8 (correlation):** `Message` type currently lacks `harness_run_id` and `harness_mode`. `summary_complete` event is unhandled. Fix:
   - Extend SSEEvent for `harness_artifact`, `summary_complete`, `workspace_updated`.
   - Extend Message type with `harness_run_id`, `harness_mode`, `harness_artifact`.
   - useChatState reducer for `summary_complete` event tags the assistant message with `harness_run_id` + `harness_mode`.
   - useChatState reducer for `harness_artifact` event finds the message by `harness_run_id` and attaches the artifact deterministically. No timing heuristics.

2. **REVIEW #11 (correct file targets):**
   - i18n is `frontend/src/i18n/translations.ts` (verified — FLAT key style like `'harness.docx.downloadAriaLabel': 'Download {{name}}'`). NOT `frontend/src/i18n/locales/*.json` (those files don't exist).
   - `Message` interface is in `frontend/src/lib/database.types.ts:27` (NOT inline in useChatState.ts).

3. **D-22-14:** inline chat link + workspace panel listing, no auto-download.

Output: 5 file edits + Vitest suite.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/ROADMAP.md
@.planning/REQUIREMENTS.md
@.planning/phases/22-contract-review-harness-docx-deliverable/22-CONTEXT.md
@.planning/phases/22-contract-review-harness-docx-deliverable/22-PATTERNS.md
@.planning/phases/22-contract-review-harness-docx-deliverable/22-REVIEWS.md
@frontend/src/components/chat/MessageView.tsx
@frontend/src/components/chat/WorkspacePanel.tsx
@frontend/src/i18n/translations.ts
@frontend/src/lib/database.types.ts
</context>

<interfaces>
<!-- VERIFIED file paths (REVIEW #11): -->
<!--   frontend/src/i18n/translations.ts        (NOT i18n/locales/*.json) -->
<!--   frontend/src/lib/database.types.ts       (Message at line 27, harness_run_id at lines 125 and 163) -->
<!--   frontend/src/lib/database.types.ts:319   (WorkspaceFile.source = 'agent' | 'sandbox' | 'upload') -->

<!-- translations.ts shape (FLAT key, NOT nested): -->
<!--   export const translations: Record<Locale, Record<string, string>> = { -->
<!--     id: { 'welcome.greeting': 'Halo, {name}', ... }, -->
<!--     en: { 'welcome.greeting': 'Hello, {name}', ... } -->
<!--   } -->

SSEEvent additions:
```typescript
export interface HarnessArtifactEvent {
  type: 'harness_artifact'
  harness_run_id: string
  harness_mode: string                  // REVIEW #8 — e.g. 'contract-review'
  phase_index: number
  phase_name: string
  ok: boolean
  docx_path?: string
  signed_url?: string
  error?: string
  code?: string
  detail?: string
  fallback_message?: string
}

export interface SummaryCompleteEvent {
  type: 'summary_complete'
  assistant_message_id: string | null   // REVIEW #8 — the persisted Message.id
  harness_run_id?: string
  harness_mode?: string
}

export interface WorkspaceUpdatedEvent {
  type: 'workspace_updated'
  thread_id?: string
  file_path: string
  operation: 'create' | 'update' | 'delete'
  source: 'agent' | 'sandbox' | 'upload' | 'harness'
  size_bytes?: number
  harness_run_id?: string
}
```

Message type additions (REVIEW #8):
```typescript
export interface Message {
  // ...existing fields...
  // Phase 22 / REVIEW #8 — harness correlation:
  harness_run_id?: string | null
  harness_mode?: string | null
  harness_artifact?: {
    ok: boolean
    file_path?: string
    signed_url?: string
    fallback_message?: string
  } | null
}
```

Reducer correlation strategy (REVIEW #8 — deterministic, no timing):
1. `summary_complete` event arrives FIRST (post_harness.py emits it after the post-harness assistant message is persisted, line 267). Reducer:
   - finds the local Message by `assistant_message_id` (already in store from delta events)
   - tags it with `harness_run_id` (from event payload) and `harness_mode`
2. `harness_artifact` event arrives SECOND. Reducer:
   - finds the assistant Message in active thread with matching `harness_run_id`
   - attaches the artifact

Falls back to last-assistant-message heuristic ONLY if no match (logged warning).
</interfaces>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: SSEEvent + Message + WorkspaceFile type extensions in database.types.ts (REVIEW #8 + #11)</name>
  <files>frontend/src/lib/database.types.ts</files>
  <read_first>
    - frontend/src/lib/database.types.ts (full file — find SSEEvent union, Message interface at line 27, WorkspaceFile at line 319)
    - .planning/phases/22-contract-review-harness-docx-deliverable/22-REVIEWS.md (review findings #8 + #11)
  </read_first>
  <behavior>
    - Test 1: TypeScript compiles after extending SSEEvent (`npx tsc --noEmit` exits 0).
    - Test 2: `WorkspaceFile['source']` accepts `'harness'`.
    - Test 3: `Message` accepts `harness_run_id`, `harness_mode`, `harness_artifact` fields.
  </behavior>
  <action>
    Edit `frontend/src/lib/database.types.ts`:

    **A) Find the SSEEvent union (likely a `type SSEEvent = ... | ... | ...` discriminated union or interface variants).** Add THREE new variants if not present, OR widen existing ones:

    ```typescript
    export interface HarnessArtifactEvent {
      type: 'harness_artifact'
      harness_run_id: string
      harness_mode: string                  // Phase 22 / REVIEW #8 correlation anchor
      phase_index: number
      phase_name: string
      ok: boolean
      docx_path?: string
      signed_url?: string
      error?: string
      code?: string
      detail?: string
      fallback_message?: string
    }

    export interface SummaryCompleteEvent {
      type: 'summary_complete'
      assistant_message_id: string | null
      harness_run_id?: string                // Phase 22 / REVIEW #8 — correlation
      harness_mode?: string
    }

    export interface WorkspaceUpdatedEvent {
      type: 'workspace_updated'
      thread_id?: string
      file_path: string
      operation: 'create' | 'update' | 'delete'
      source: 'agent' | 'sandbox' | 'upload' | 'harness'
      size_bytes?: number
      harness_run_id?: string
    }
    ```

    Add these to the SSEEvent discriminated union (find the existing `type SSEEvent = ... | ...` line and append `| HarnessArtifactEvent | SummaryCompleteEvent | WorkspaceUpdatedEvent`).

    **B) Extend Message interface (line 27)** with three new optional fields per REVIEW #8:
    ```typescript
    export interface Message {
      // ...existing fields preserved...
      // Phase 22 / REVIEW #8 — correlation for post-harness DOCX artifact attachment:
      harness_run_id?: string | null
      harness_mode?: string | null
      harness_artifact?: {
        ok: boolean
        file_path?: string
        signed_url?: string
        fallback_message?: string
      } | null
    }
    ```

    **C) Widen WorkspaceFile.source union (line 319)** from `'agent' | 'sandbox' | 'upload'` to `'agent' | 'sandbox' | 'upload' | 'harness'`. Single-line edit.
  </action>
  <verify>
    <automated>cd frontend && npx tsc --noEmit</automated>
  </verify>
  <acceptance_criteria>
    - `cd frontend && npx tsc --noEmit` exits 0
    - `grep -c "HarnessArtifactEvent" frontend/src/lib/database.types.ts` returns `>= 1`
    - `grep -c "SummaryCompleteEvent" frontend/src/lib/database.types.ts` returns `>= 1`
    - `grep -c "WorkspaceUpdatedEvent" frontend/src/lib/database.types.ts` returns `>= 1`
    - `grep -c "harness_artifact" frontend/src/lib/database.types.ts` returns `>= 2` (event + Message field)
    - `grep -c "'harness'" frontend/src/lib/database.types.ts` returns `>= 1` (WorkspaceFile.source)
    - `grep -c "REVIEW #8" frontend/src/lib/database.types.ts` returns `>= 2`
  </acceptance_criteria>
  <done>Types extended; TS compiles cleanly; correlation fields available.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: useChatState reducer for summary_complete + harness_artifact (REVIEW #8 deterministic correlation)</name>
  <files>frontend/src/hooks/useChatState.ts</files>
  <read_first>
    - frontend/src/hooks/useChatState.ts (find SSE event handler/reducer; existing `case 'harness_run_start':` and `case 'batch_progress':` for analog shape; lines 600-700 for harness handling examples)
    - frontend/src/lib/database.types.ts (post-Task-1 — Message type updated)
    - .planning/phases/22-contract-review-harness-docx-deliverable/22-REVIEWS.md (review finding #8)
  </read_first>
  <behavior>
    - Test 1: When `summary_complete` event arrives with `assistant_message_id="m1"`, `harness_run_id="r42"`, `harness_mode="contract-review"`, the local Message with id="m1" is updated to have those two fields.
    - Test 2: When `harness_artifact` event arrives with `harness_run_id="r42"` and `ok=true, docx_path, signed_url`, the Message tagged in Test 1 gets `harness_artifact={ok:true, file_path, signed_url}` attached.
    - Test 3: Order independence — if `harness_artifact` arrives BEFORE `summary_complete`, the artifact is queued by `harness_run_id` and attached when `summary_complete` arrives. After 5 seconds without correlation, the queued artifact is dropped (logged).
    - Test 4: When `harness_artifact.ok=false`, the message gets `harness_artifact={ok:false, fallback_message}`.
  </behavior>
  <action>
    Edit `frontend/src/hooks/useChatState.ts`:

    **A) Find the existing SSE event handler** (search for `case 'harness_run_start':` or similar; the dispatcher likely uses a switch on `event.type`).

    **B) Add reducer case `case 'summary_complete':`** — tag the assistant message:
    ```typescript
    case 'summary_complete': {
      // Phase 22 / REVIEW #8: tag the persisted assistant message with harness correlation,
      // so a subsequent harness_artifact event can find it deterministically.
      const messageId = event.assistant_message_id
      if (!messageId) break
      // Mutate the message in the active-thread store
      setMessages(prev => prev.map(m => m.id === messageId
        ? { ...m, harness_run_id: event.harness_run_id ?? null,
                  harness_mode: event.harness_mode ?? null }
        : m
      ))
      // Drain any queued artifact for this harness_run_id
      const runId = event.harness_run_id
      if (runId && pendingArtifacts.current.has(runId)) {
        const artifact = pendingArtifacts.current.get(runId)!
        pendingArtifacts.current.delete(runId)
        setMessages(prev => prev.map(m => m.id === messageId
          ? { ...m, harness_artifact: artifact }
          : m
        ))
      }
      break
    }
    ```

    **C) Add reducer case `case 'harness_artifact':`** — find the message by harness_run_id; if not found yet, queue it:
    ```typescript
    case 'harness_artifact': {
      // Phase 22 / REVIEW #8: deterministic correlation by harness_run_id.
      // No timing heuristic — the message tagged by summary_complete carries the run id.
      const runId = event.harness_run_id
      if (!runId) {
        console.warn('harness_artifact event missing harness_run_id', event)
        break
      }
      const artifact = event.ok
        ? { ok: true as const, file_path: event.docx_path, signed_url: event.signed_url }
        : { ok: false as const, fallback_message: event.fallback_message ?? 'DOCX export unavailable.' }

      // Locate the message tagged with this harness_run_id
      const target = messages.find(m => m.harness_run_id === runId && m.role === 'assistant')
      if (target) {
        setMessages(prev => prev.map(m => m.id === target.id
          ? { ...m, harness_artifact: artifact }
          : m
        ))
      } else {
        // Queue for up to 5 seconds — summary_complete may arrive after the artifact
        pendingArtifacts.current.set(runId, artifact)
        setTimeout(() => {
          if (pendingArtifacts.current.has(runId)) {
            pendingArtifacts.current.delete(runId)
            console.warn('harness_artifact dropped after 5s — no matching message', runId)
          }
        }, 5000)
      }
      break
    }
    ```

    **D) Declare the pendingArtifacts ref** at the top of useChatState (alongside other useRef declarations):
    ```typescript
    // Phase 22 / REVIEW #8: artifact-arrives-before-summary_complete fallback queue.
    // Keyed by harness_run_id; drained when summary_complete tags a message.
    const pendingArtifacts = useRef<Map<string, NonNullable<Message['harness_artifact']>>>(new Map())
    ```

    **E) Add `case 'workspace_updated':`** if not already present — most paths already handle this from Phase 18/20, but the engine emission path (plan 22-03) is new. Triggers a WorkspacePanel re-fetch:
    ```typescript
    case 'workspace_updated': {
      // Phase 22 / REVIEW #7: engine emits this after post_execute writes a binary.
      // Trigger workspace file list refresh (existing pattern from Phase 18 sandbox path).
      void refetchWorkspaceFiles()
      break
    }
    ```
    (If `refetchWorkspaceFiles` exists already, use the same trigger pattern as existing handlers.)
  </action>
  <verify>
    <automated>cd frontend && npx tsc --noEmit && npm run lint -- --quiet</automated>
  </verify>
  <acceptance_criteria>
    - `cd frontend && npx tsc --noEmit` exits 0
    - `cd frontend && npm run lint` exits 0
    - `grep -c "summary_complete" frontend/src/hooks/useChatState.ts` returns `>= 1` (REVIEW #8 — was UNHANDLED before)
    - `grep -c "harness_artifact" frontend/src/hooks/useChatState.ts` returns `>= 3`
    - `grep -c "pendingArtifacts" frontend/src/hooks/useChatState.ts` returns `>= 3`
    - `grep -c "REVIEW #8" frontend/src/hooks/useChatState.ts` returns `>= 2`
  </acceptance_criteria>
  <done>Reducer handles summary_complete + harness_artifact + workspace_updated; deterministic correlation in place.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: MessageView download chip + fallback note rendering</name>
  <files>frontend/src/components/chat/MessageView.tsx</files>
  <read_first>
    - frontend/src/components/chat/MessageView.tsx (lines 142-170 — existing assistant bubble + ask-user IIFE)
  </read_first>
  <behavior>
    - Test 1: Renders chip with href + download attrs when `harness_artifact: {ok:true, file_path, signed_url}`.
    - Test 2: Renders fallback note (`role="note"`) when `ok=false`.
    - Test 3: No chip and no note when `harness_artifact` undefined/null.
    - Test 4: Chip has NO `backdrop-blur` (Glass rule).
    - Test 5: `<a>` has `target="_blank"` and `rel="noopener noreferrer"`.
  </behavior>
  <action>
    Edit `frontend/src/components/chat/MessageView.tsx`:

    **A) Update lucide imports (line ~2)** — add `FileText`, `Download`, `AlertCircle`.

    **B) Add IIFE block after the existing ask-user block:**
    ```tsx
    {/* Phase 22 / D-22-14 / REVIEW #8: harness DOCX download chip + fallback note */}
    {(() => {
      const a = msg.harness_artifact
      if (!a) return null
      if (a.ok && a.file_path && a.signed_url) {
        return (
          <a
            href={a.signed_url}
            download={a.file_path}
            target="_blank"
            rel="noopener noreferrer"
            role="link"
            aria-label={t('harness.docx.downloadAriaLabel', { name: a.file_path })}
            className="flex items-center gap-2 mt-2 px-3 py-2 rounded border border-border/50 hover:bg-accent/50 transition-colors text-sm text-foreground"
            data-testid="harness-docx-chip"
          >
            <FileText size={16} className="text-primary shrink-0" aria-hidden="true" />
            <span className="flex-1 truncate">{a.file_path}</span>
            <Download size={14} className="text-muted-foreground" aria-hidden="true" />
          </a>
        )
      }
      if (!a.ok) {
        return (
          <div
            role="note"
            aria-label={t('harness.docx.fallbackAriaLabel')}
            className="flex items-start gap-2 mt-2 px-3 py-2 rounded border border-amber-500/30 bg-amber-500/10 text-sm text-foreground"
            data-testid="harness-docx-fallback"
          >
            <AlertCircle size={16} className="text-amber-500 shrink-0 mt-0.5" aria-hidden="true" />
            <p className="text-xs leading-relaxed">{a.fallback_message ?? t('harness.docx.fallbackDefault')}</p>
          </div>
        )
      }
      return null
    })()}
    ```

    **CLAUDE.md Glass rule:** NO `backdrop-blur` here.
  </action>
  <verify>
    <automated>cd frontend && npx tsc --noEmit && npm run lint -- --quiet</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c "harness-docx-chip\|harness-docx-fallback" frontend/src/components/chat/MessageView.tsx` returns `2`
    - `grep -c "harness.docx.download\|harness.docx.fallback" frontend/src/components/chat/MessageView.tsx` returns `>= 2`
    - `cd frontend && npx tsc --noEmit` exits 0
  </acceptance_criteria>
  <done>Chip + fallback note render; no glass; a11y wired.</done>
</task>

<task type="auto">
  <name>Task 4: WorkspacePanel SOURCE_COLORS + i18n keys in translations.ts (REVIEW #11)</name>
  <files>frontend/src/components/chat/WorkspacePanel.tsx, frontend/src/i18n/translations.ts</files>
  <read_first>
    - frontend/src/components/chat/WorkspacePanel.tsx (lines 80-95 — SOURCE_COLORS map)
    - frontend/src/i18n/translations.ts (full file — confirm FLAT key style, find existing harness.* and workspace.* keys to follow convention)
    - .planning/phases/22-contract-review-harness-docx-deliverable/22-REVIEWS.md (review finding #11 — i18n is translations.ts NOT locales/*.json)
  </read_first>
  <action>
    **A) `frontend/src/components/chat/WorkspacePanel.tsx`:** find SOURCE_COLORS object. Add `harness: 'bg-green-500/20 text-green-300'` entry.

    **B) `frontend/src/i18n/translations.ts` — REVIEW #11 verbatim:** the file uses FLAT key style (e.g., `'welcome.greeting': 'Halo, {name}'`), NOT nested JSON. Add to BOTH the `id` and `en` blocks:

    Indonesian (`id` block):
    ```typescript
    'harness.docx.downloadAriaLabel': 'Unduh {name}',
    'harness.docx.fallbackAriaLabel': 'Ekspor DOCX gagal',
    'harness.docx.fallbackDefault': 'Ekspor DOCX tidak tersedia saat ini — ringkasan markdown ada di atas. Coba ulang harness untuk mencoba lagi.',
    'workspace.source.harness': 'Harness',
    ```

    English (`en` block):
    ```typescript
    'harness.docx.downloadAriaLabel': 'Download {name}',
    'harness.docx.fallbackAriaLabel': 'DOCX export failed',
    'harness.docx.fallbackDefault': 'DOCX export unavailable right now — the markdown summary is above. Retry by re-running the harness if needed.',
    'workspace.source.harness': 'Harness',
    ```

    Use `{name}` (single-curly) interpolation if that's the existing convention; check the `'welcome.greeting': 'Halo, {name}'` pattern at the top of the file to confirm. Match exactly.

    **DO NOT** create `frontend/src/i18n/locales/id.json` or `frontend/src/i18n/locales/en.json` — those files do not exist (REVIEW #11). The single source of truth is `translations.ts`.
  </action>
  <verify>
    <automated>cd frontend && npx tsc --noEmit</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c "harness:" frontend/src/components/chat/WorkspacePanel.tsx` returns `>= 1`
    - `grep -c "harness.docx.downloadAriaLabel" frontend/src/i18n/translations.ts` returns `2` (one per locale)
    - `grep -c "harness.docx.fallbackDefault" frontend/src/i18n/translations.ts` returns `2`
    - `grep -c "workspace.source.harness" frontend/src/i18n/translations.ts` returns `2`
    - `grep -c "Unduh\|tidak tersedia" frontend/src/i18n/translations.ts` returns `>= 2` (Indonesian)
    - **`ls frontend/src/i18n/locales/ 2>/dev/null` exits 1 OR returns nothing** (REVIEW #11 — those files must not be created)
    - `cd frontend && npx tsc --noEmit` exits 0
  </acceptance_criteria>
  <done>SOURCE_COLORS gets harness entry; FLAT i18n keys added in translations.ts; locales/*.json NOT created.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 5: Vitest coverage — chip + fallback + reducer correlation (REVIEW #8)</name>
  <files>frontend/src/components/chat/__tests__/MessageView.harness-artifact.test.tsx</files>
  <read_first>
    - frontend/src/components/chat/__tests__/* (analog tests; especially any ask_user question-bubble test)
    - frontend/src/components/chat/MessageView.tsx (post-Task-3 state)
  </read_first>
  <behavior>
    - Test 1: Chip renders correctly when `harness_artifact: {ok:true, file_path, signed_url}`.
    - Test 2: Fallback note renders when `ok=false`.
    - Test 3: No chip / no note when undefined.
    - Test 4: `<a>` has correct security attrs (target=_blank, rel=noopener noreferrer).
    - Test 5: When `fallback_message` empty, default i18n string renders.
    - Test 6 (REVIEW #8 — race condition): dispatch `harness_artifact` before `summary_complete`; nothing renders. Then dispatch `summary_complete`; chip renders. After 5s without summary_complete, queued artifact is dropped (no error).
  </behavior>
  <action>
    Create `frontend/src/components/chat/__tests__/MessageView.harness-artifact.test.tsx` with 6 Vitest tests using Testing Library. Vitest 3.2+ (CLAUDE.md gotcha).

    Test 1 example:
    ```tsx
    import { describe, it, expect } from 'vitest'
    import { render, screen } from '@testing-library/react'
    import { I18nProvider } from '../../../i18n/I18nContext'
    import MessageView from '../MessageView'

    const wrap = (ui: React.ReactNode) => render(<I18nProvider>{ui}</I18nProvider>)

    describe('MessageView harness_artifact', () => {
      it('renders download chip when ok=true', () => {
        const msg = {
          id: 'm1', role: 'assistant' as const, content: 'Done.',
          harness_artifact: { ok: true, file_path: 'x.docx', signed_url: 'https://example.com/x.docx' },
        }
        wrap(<MessageView msg={msg as any} ... />)
        const chip = screen.getByTestId('harness-docx-chip')
        expect(chip).toHaveAttribute('href', 'https://example.com/x.docx')
        expect(chip).toHaveAttribute('download', 'x.docx')
        expect(chip).toHaveAttribute('target', '_blank')
        expect(chip).toHaveAttribute('rel', 'noopener noreferrer')
      })
    })
    ```
  </action>
  <verify>
    <automated>cd frontend && npm test -- src/components/chat/__tests__/MessageView.harness-artifact.test.tsx --run</automated>
  </verify>
  <acceptance_criteria>
    - `npm test -- src/components/chat/__tests__/MessageView.harness-artifact.test.tsx --run` exits 0 with 6 tests
    - `grep -c "getByTestId\|harness-docx" frontend/src/components/chat/__tests__/MessageView.harness-artifact.test.tsx` returns `>= 5`
    - `grep -c "REVIEW #8" frontend/src/components/chat/__tests__/MessageView.harness-artifact.test.tsx` returns `>= 1`
  </acceptance_criteria>
  <done>6 tests pass — chip, fallback, a11y, REVIEW #8 race-condition queue all locked in.</done>
</task>

</tasks>

<truths>
- D-22-14 (inline chat link + workspace panel listing, no auto-download).
- D-22-15 (non-fatal fallback) — fallback note renders when harness_artifact.ok=false.
- CLAUDE.md Glass rule: persistent download chip uses solid bg.
- Vitest 3.2 required.
- WorkspacePanel auto-renders DOCX via existing workspace_updated SSE; only badge color needs new 'harness' source.
- REVIEW #8 closed: deterministic correlation via harness_run_id (set by summary_complete handler) → harness_artifact attaches to the right message. 5-second fallback queue handles event arrival order.
- REVIEW #11 closed: i18n is `translations.ts` (FLAT keys), Message in `database.types.ts`. No locales/*.json files created.
- Off-mode: when contract_review_enabled=False, no harness_artifact event ever emitted; new useChatState case is dead code.
</truths>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| harness_artifact SSE event → useChatState | Backend-supplied; signed_url is authoritative |
| `<a download>` → user browser → Supabase signed URL | rel="noopener noreferrer" prevents window.opener leak |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-22-11-01 | Tampering | Malicious signed_url XSS via javascript: scheme | mitigate | Backend constructs signed_url from Supabase storage exclusively (https://...); browser blocks javascript: on download attribute |
| T-22-11-02 | Information Disclosure | Signed URL leaked via window.opener | mitigate | rel="noopener noreferrer" |
| T-22-11-03 | Tampering | Malicious harness_run_id triggers UI confusion | accept | Backend-controlled; bounded set per active thread |
</threat_model>

<verification>
1. `cd frontend && npx tsc --noEmit` exits 0
2. `cd frontend && npm run lint` exits 0
3. `cd frontend && npm test -- --run` exits 0
4. `grep -c "harness_artifact" frontend/src/lib/database.types.ts frontend/src/hooks/useChatState.ts frontend/src/components/chat/MessageView.tsx` returns `>= 5`
5. `grep -c "summary_complete" frontend/src/hooks/useChatState.ts` returns `>= 1` (REVIEW #8 anti-regression)
6. `ls frontend/src/i18n/locales/ 2>/dev/null` returns nothing (REVIEW #11 anti-regression)
</verification>

<success_criteria>
- harness_artifact + summary_complete + workspace_updated SSE events handled
- Message type carries harness_run_id + harness_mode + harness_artifact
- Reducer correlates artifact to message deterministically by harness_run_id
- Download chip renders with proper a11y + security attrs
- Fallback note shows when DOCX generation fails
- WorkspacePanel badges harness-source files in green
- ID + EN i18n parity in translations.ts (FLAT key style; no locales/*.json files created)
</success_criteria>

<output>
After completion, create `.planning/phases/22-contract-review-harness-docx-deliverable/22-11-SUMMARY.md`.
</output>
