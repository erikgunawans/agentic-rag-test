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
  - frontend/src/i18n/locales/id.json
  - frontend/src/i18n/locales/en.json
  - frontend/src/components/chat/__tests__/MessageView.harness-artifact.test.tsx
autonomous: true
requirements: [CR-08, DOCX-08]
must_haves:
  truths:
    - "SSEEvent union widened to include harness_artifact event from plan 22-03"
    - "useChatState reducer handles harness_artifact event and stores artifact on the post-harness assistant message"
    - "MessageView renders a download chip linking to signed_url when msg.harness_artifact is present"
    - "MessageView renders a non-fatal failure note when harness_artifact has ok=false (D-22-15 fallback UX)"
    - "WorkspacePanel SOURCE_COLORS map includes 'harness' entry with green badge"
    - "WorkspaceFile.source type union includes 'harness'"
    - "i18n keys added for harness.docx.downloadAriaLabel + harness.docx.fallback in id.json + en.json"
    - "No glass / backdrop-blur on the persistent download chip (CLAUDE.md UI rule)"
  artifacts:
    - path: "frontend/src/lib/database.types.ts"
      provides: "Widened SSEEvent union with harness_artifact"
      contains: "harness_artifact"
    - path: "frontend/src/hooks/useChatState.ts"
      provides: "harness_artifact reducer + WorkspaceFile.source 'harness' type union"
      contains: "harness_artifact"
    - path: "frontend/src/components/chat/MessageView.tsx"
      provides: "Download chip + fallback note rendering"
      contains: "harness-docx-chip"
    - path: "frontend/src/components/chat/WorkspacePanel.tsx"
      provides: "harness SOURCE_COLORS entry"
      contains: "harness:"
    - path: "frontend/src/i18n/locales/id.json"
      provides: "Indonesian translations for harness.docx.* keys"
    - path: "frontend/src/i18n/locales/en.json"
      provides: "English translations for harness.docx.* keys"
  key_links:
    - from: "harness_engine.py harness_artifact SSE event (plan 22-03)"
      to: "useChatState reducer"
      via: "SSE handler routes to message slice"
      pattern: "harness_artifact"
    - from: "useChatState message slice"
      to: "MessageView download chip"
      via: "msg.harness_artifact field"
      pattern: "harness_artifact"
---

<objective>
Wire the frontend to render the DOCX deliverable. Plan 22-03 emits a `harness_artifact` SSE event after CR-08's post_execute completes. This plan plumbs that event through `useChatState` and renders a download chip on the post-harness assistant message bubble. WorkspacePanel auto-renders the file via existing `workspace_updated` SSE — only its color badge needs a `harness` entry.

Per D-22-14: inline chat link + workspace panel listing, NO browser auto-download.

Purpose: Without this plan, plan 22-10's DOCX is generated and stored but invisible to the user except as a workspace file (which is acceptable but not the D-22-14 contract).
Output: Reducer + MessageView chip + i18n + SOURCE_COLORS update + Vitest coverage.
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
@frontend/src/components/chat/MessageView.tsx
@frontend/src/components/chat/WorkspacePanel.tsx
</context>

<interfaces>
<!-- harness_artifact SSE event shape (from plan 22-03 task 1 specification) -->
```typescript
type HarnessArtifactEvent = {
  type: 'harness_artifact'
  harness_run_id: string
  phase_index: number
  phase_name: string
  ok: boolean
  // ok=true case:
  docx_path?: string
  signed_url?: string
  // ok=false case (D-22-15):
  error?: string
  code?: string
  detail?: string
  fallback_message?: string
}

// Per-message attachment captured from the event:
type MessageHarnessArtifact = {
  ok: boolean
  file_path?: string         // mapped from docx_path
  signed_url?: string
  fallback_message?: string  // when ok=false
}
```
</interfaces>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Widen SSEEvent union + WorkspaceFile.source type + add useChatState reducer</name>
  <files>frontend/src/lib/database.types.ts, frontend/src/hooks/useChatState.ts</files>
  <read_first>
    - frontend/src/lib/database.types.ts (find the SSEEvent union; commit 956af2e widened it for Phase 20-21 events — find harness_run / harness_phase_start entries as analog)
    - frontend/src/hooks/useChatState.ts (find SSE event router function — likely a switch on event.type; find existing harness handlers like 'harness_run_start', 'batch_progress')
    - .planning/phases/22-contract-review-harness-docx-deliverable/22-PATTERNS.md (lines 391-450 — recommended `harness_artifact` event slice approach)
  </read_first>
  <behavior>
    - Test 1: TypeScript compiles after extending SSEEvent (`npx tsc --noEmit` exits 0).
    - Test 2: `WorkspaceFile['source']` accepts `'harness'` (no type error in WorkspacePanel SOURCE_COLORS).
    - Test 3: When useChatState handler receives a `harness_artifact` event with `ok: true, docx_path: 'x.docx', signed_url: 'https://...'`, it attaches `{ ok: true, file_path: 'x.docx', signed_url: '...' }` to the LATEST assistant message in the active thread.
    - Test 4: When event has `ok: false, fallback_message: '...'`, the attachment is `{ ok: false, fallback_message: '...' }`.
  </behavior>
  <action>
    **A) `frontend/src/lib/database.types.ts`:** find the SSEEvent union. Add a new variant:

    ```typescript
    | {
        type: 'harness_artifact'
        harness_run_id: string
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
    ```

    Place it adjacent to the existing harness event variants (e.g., after `harness_phase_complete`). DO NOT modify any other variant.

    **B) `frontend/src/hooks/useChatState.ts`:** two changes.

    1. Find the WorkspaceFile type (search `WorkspaceFile` or `'sandbox' | 'agent'`). Extend the `source` union to include `'harness'`:
    ```typescript
    type WorkspaceFile = {
      ...
      source: 'agent' | 'sandbox' | 'upload' | 'harness'
      ...
    }
    ```

    2. Add a per-message `harness_artifact` field to the message type:
    ```typescript
    type Message = {
      ...
      harness_artifact?: {
        ok: boolean
        file_path?: string
        signed_url?: string
        fallback_message?: string
      }
    }
    ```

    3. In the SSE event handler/reducer (find the switch statement on `event.type`), add a `case 'harness_artifact':` branch that:
       - Locates the most-recent `role === 'assistant'` message with `harness_mode === 'contract-review'` (or matching the harness_run_id of the event)
       - **ISSUE-13 race-condition fix:** if NO assistant message yet exists with the matching harness_run_id at the moment the artifact event arrives (timing race: artifact arrives before the post-harness summary message is finalized), enqueue the artifact in a fallback queue keyed by `harness_run_id`. When the next assistant message arrives within 5 seconds AND its harness_run_id matches AND it has a non-empty content (or is the in-flight streaming message), drain the queue and attach. After 5 seconds, drop the queued artifact (rare; logs a console.warn).
       - Sets `msg.harness_artifact` to:
         ```typescript
         event.ok
           ? { ok: true, file_path: event.docx_path, signed_url: event.signed_url }
           : { ok: false, fallback_message: event.fallback_message ?? 'DOCX export unavailable.' }
         ```
       - Triggers a re-render

    Reference the existing `case 'harness_phase_complete':` or `case 'batch_progress':` for the exact reducer shape this codebase uses (immer? plain spread? hand-rolled?).

    Add a comment above the new case: `// Phase 22 / D-22-14 / DOCX-08: post_execute artifact attachment + ISSUE-13 fallback queue for the post-harness summary bubble.`
  </action>
  <verify>
    <automated>cd frontend && npx tsc --noEmit && npm run lint -- --quiet</automated>
  </verify>
  <acceptance_criteria>
    - `cd frontend && npx tsc --noEmit` exits 0
    - `cd frontend && npm run lint` exits 0
    - `grep -c "harness_artifact" frontend/src/lib/database.types.ts` returns `>= 1`
    - `grep -c "harness_artifact" frontend/src/hooks/useChatState.ts` returns `>= 2` (type field + reducer case)
    - `grep -c "'harness'" frontend/src/hooks/useChatState.ts` returns `>= 1`
  </acceptance_criteria>
  <done>Type union widened, reducer handles event, no TS errors.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Render download chip + fallback note in MessageView</name>
  <files>frontend/src/components/chat/MessageView.tsx</files>
  <read_first>
    - frontend/src/components/chat/MessageView.tsx (lines 142-170 — the existing assistant bubble + ask-user IIFE pattern to mirror)
    - .planning/phases/22-contract-review-harness-docx-deliverable/22-PATTERNS.md (lines 391-450 — exact patch shape with imports + className)
    - frontend/src/i18n/index.ts or wherever translation keys are looked up
  </read_first>
  <behavior>
    - Test 1: When msg has `harness_artifact: { ok: true, file_path: 'x.docx', signed_url: 'https://example.com/x.docx' }`, an `<a>` element renders with `href=signed_url`, `download=file_path`, `data-testid="harness-docx-chip"`.
    - Test 2: When ok=false, a div with `role="note"` renders containing the fallback_message text.
    - Test 3: When `msg.harness_artifact` is undefined, NO chip and NO note rendered.
    - Test 4: The chip has NO `backdrop-blur` class (Glass rule from CLAUDE.md).
    - Test 5: Component is keyboard-accessible (`<a>` is focusable; aria-label resolves through i18n).
  </behavior>
  <action>
    Edit `frontend/src/components/chat/MessageView.tsx`:

    **A) Update lucide imports** (line ~2):
    ```tsx
    import { GitFork, ChevronLeft, ChevronRight, ShieldAlert, MessageCircleQuestion, FileText, Download, AlertCircle } from 'lucide-react'
    ```
    (Add `FileText`, `Download`, `AlertCircle` if not already present.)

    **B) Add a NEW IIFE block AFTER the existing ask-user IIFE block** (after line ~166, before the closing of the bubble container):

    ```tsx
    {/* Phase 22 / D-22-14 / DOCX-08: harness DOCX download chip + non-fatal fallback note */}
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
      // ok=false → non-fatal fallback note (D-22-15)
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

    **CLAUDE.md Glass rule check**: NO `backdrop-blur` class anywhere in this block. The chip is a persistent UI element. Hover uses `hover:bg-accent/50` only — that's a solid color, not a glass effect.
  </action>
  <verify>
    <automated>cd frontend && npx tsc --noEmit && npm run lint -- --quiet</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c "harness-docx-chip\|harness-docx-fallback" frontend/src/components/chat/MessageView.tsx` returns `2`
    - `grep -c "backdrop-blur" frontend/src/components/chat/MessageView.tsx` returns the same count as before this plan (no new instances)
    - `grep -c "harness.docx.download\|harness.docx.fallback" frontend/src/components/chat/MessageView.tsx` returns `>= 2`
    - `cd frontend && npx tsc --noEmit` exits 0
    - `cd frontend && npm run lint` exits 0
  </acceptance_criteria>
  <done>Download chip + fallback note render under the assistant bubble; no glass on persistent UI.</done>
</task>

<task type="auto">
  <name>Task 3: Add 'harness' entry to WorkspacePanel SOURCE_COLORS + i18n keys</name>
  <files>frontend/src/components/chat/WorkspacePanel.tsx, frontend/src/i18n/locales/id.json, frontend/src/i18n/locales/en.json</files>
  <read_first>
    - frontend/src/components/chat/WorkspacePanel.tsx (lines 80-90 — SOURCE_COLORS map)
    - frontend/src/i18n/locales/id.json (find existing workspace.source.* keys)
    - frontend/src/i18n/locales/en.json (find existing workspace.source.* keys)
    - .planning/phases/22-contract-review-harness-docx-deliverable/22-PATTERNS.md (lines 454-468 — SOURCE_COLORS patch)
  </read_first>
  <action>
    **A) `frontend/src/components/chat/WorkspacePanel.tsx`:** find SOURCE_COLORS object (likely around line 80-90). Add `harness: 'bg-green-500/20 text-green-300'` entry.

    Before:
    ```tsx
    const SOURCE_COLORS: Record<WorkspaceFile['source'], string> = {
      agent: 'bg-purple-500/20 text-purple-300',
      sandbox: 'bg-blue-500/20 text-blue-300',
      upload: 'bg-zinc-500/20 text-zinc-300',
    }
    ```
    After:
    ```tsx
    const SOURCE_COLORS: Record<WorkspaceFile['source'], string> = {
      agent: 'bg-purple-500/20 text-purple-300',
      sandbox: 'bg-blue-500/20 text-blue-300',
      upload: 'bg-zinc-500/20 text-zinc-300',
      harness: 'bg-green-500/20 text-green-300',  // Phase 22 — DOCX from Contract Review post_execute
    }
    ```

    If the existing SOURCE_COLORS uses different shade variables (e.g., from tailwind tokens), match that style.

    **B) `frontend/src/i18n/locales/en.json`:** add (under existing `harness.*` section, or create one):
    ```json
    "harness": {
      ...
      "docx": {
        "downloadAriaLabel": "Download {{name}}",
        "fallbackAriaLabel": "DOCX export failed",
        "fallbackDefault": "DOCX export unavailable right now — the markdown summary is above. Retry by re-running the harness if needed."
      }
    },
    "workspace": {
      ...
      "source": {
        ...
        "harness": "Harness"
      }
    }
    ```

    **C) `frontend/src/i18n/locales/id.json`:** corresponding Indonesian translations:
    ```json
    "harness": {
      ...
      "docx": {
        "downloadAriaLabel": "Unduh {{name}}",
        "fallbackAriaLabel": "Ekspor DOCX gagal",
        "fallbackDefault": "Ekspor DOCX tidak tersedia saat ini — ringkasan markdown ada di atas. Coba ulang harness untuk mencoba lagi."
      }
    },
    "workspace": {
      ...
      "source": {
        ...
        "harness": "Harness"
      }
    }
    ```

    Match the JSON path style used by the existing keys (nested vs flattened) — peek at the existing `workspace.source.upload` key to confirm.
  </action>
  <verify>
    <automated>cd frontend && npx tsc --noEmit && python -c "import json; en=json.load(open('frontend/src/i18n/locales/en.json')); id=json.load(open('frontend/src/i18n/locales/id.json')); print('OK')"</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c "harness:" frontend/src/components/chat/WorkspacePanel.tsx` returns `>= 1` (the SOURCE_COLORS entry)
    - `grep -c "downloadAriaLabel\|fallbackDefault" frontend/src/i18n/locales/en.json` returns `>= 2`
    - `grep -c "Unduh\|tidak tersedia" frontend/src/i18n/locales/id.json` returns `>= 2`
    - `python -c "import json; json.load(open('frontend/src/i18n/locales/en.json')); json.load(open('frontend/src/i18n/locales/id.json'))"` exits 0 (valid JSON)
    - `cd frontend && npx tsc --noEmit` exits 0
  </acceptance_criteria>
  <done>SOURCE_COLORS includes harness entry; ID + EN translations added.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 4: Add Vitest coverage for download chip + fallback note + reducer</name>
  <files>frontend/src/components/chat/__tests__/MessageView.harness-artifact.test.tsx</files>
  <read_first>
    - frontend/src/components/chat/__tests__/MessageView.* (analog tests; especially any ask_user question-bubble test from Phase 19)
    - frontend/src/components/chat/MessageView.tsx (post-Task-2 state)
  </read_first>
  <behavior>
    - Test 1: Renders chip when `harness_artifact: { ok: true, file_path: 'x.docx', signed_url: 'https://example.com/x.docx' }` — assert `screen.getByTestId('harness-docx-chip')` exists, has correct href + download attrs, contains 'x.docx' text.
    - Test 2: Renders fallback note when `harness_artifact: { ok: false, fallback_message: 'DOCX export unavailable...' }` — assert `screen.getByTestId('harness-docx-fallback')` exists, contains the message.
    - Test 3: No chip and no note when `harness_artifact` undefined.
    - Test 4: `<a>` has `target="_blank"` and `rel="noopener noreferrer"` (security + UX).
    - Test 5: When `ok=false` and `fallback_message` is empty, fallback default i18n string renders.
    - Test 6 (ISSUE-13 race condition): dispatch a `harness_artifact` event BEFORE the matching assistant message exists; assert nothing renders yet. Then dispatch the assistant message creation event; assert the chip then renders attached to that new message. After 5+ seconds without a matching message, the queue is dropped (no error).
  </behavior>
  <action>
    Create `frontend/src/components/chat/__tests__/MessageView.harness-artifact.test.tsx`. Use Vitest 3.2 + Testing Library (already pinned in CLAUDE.md gotcha).

    Test stub:
    ```tsx
    import { describe, it, expect } from 'vitest'
    import { render, screen } from '@testing-library/react'
    import { MessageView } from '../MessageView'   // verify exact export path

    // I18nProvider wrapper if needed — peek at existing analog test
    const wrap = (ui: React.ReactNode) => render(<I18nProvider>{ui}</I18nProvider>)

    describe('MessageView harness_artifact rendering', () => {
      it('renders download chip when ok=true', () => {
        const msg = {
          id: 'm1', role: 'assistant', content: 'Done.',
          harness_artifact: { ok: true, file_path: 'x.docx', signed_url: 'https://example.com/x.docx' },
        }
        wrap(<MessageView msg={msg} ... />)
        const chip = screen.getByTestId('harness-docx-chip')
        expect(chip).toHaveAttribute('href', 'https://example.com/x.docx')
        expect(chip).toHaveAttribute('download', 'x.docx')
        expect(chip).toHaveAttribute('target', '_blank')
        expect(chip).toHaveAttribute('rel', 'noopener noreferrer')
        expect(chip).toHaveTextContent('x.docx')
      })

      it('renders fallback note when ok=false', () => { ... })
      it('renders nothing when harness_artifact undefined', () => { ... })
      it('uses fallbackDefault i18n when fallback_message is empty', () => { ... })
    })
    ```

    The exact MessageView prop shape and helper imports depend on the existing test analog — copy from the most-recent Phase 19 / Phase 21 frontend test in this directory. If `MessageView` is exported as default, use `import MessageView from '../MessageView'`.
  </action>
  <verify>
    <automated>cd frontend && npm test -- src/components/chat/__tests__/MessageView.harness-artifact.test.tsx --run</automated>
  </verify>
  <acceptance_criteria>
    - `npm test -- src/components/chat/__tests__/MessageView.harness-artifact.test.tsx --run` exits 0 with 6 tests passing
    - `grep -c "getByTestId\|harness-docx" frontend/src/components/chat/__tests__/MessageView.harness-artifact.test.tsx` returns `>= 5`
  </acceptance_criteria>
  <done>6 Vitest tests pass — chip + fallback + i18n + accessibility + ISSUE-13 race-condition fallback queue locked in.</done>
</task>

</tasks>

<truths>
- D-22-14 (inline chat link + workspace panel listing, no auto-download) — implemented via download chip on the post-harness assistant bubble + WorkspacePanel SOURCE_COLORS entry.
- D-22-15 (non-fatal fallback) — fallback note renders when harness_artifact.ok=false.
- CLAUDE.md Glass rule: persistent download chip uses solid bg, NO `backdrop-blur`.
- KV-cache friendliness N/A — frontend doesn't share LLM prompt prefix; just type union extension.
- Vitest 3.2 required (CLAUDE.md gotcha) — no version pin manipulation in this plan.
- WorkspacePanel auto-renders the file via existing `workspace_updated` SSE; only badge color needs the new 'harness' source.
- Off-mode: when contract_review_enabled=False, no harness_artifact event is ever emitted; the new useChatState case is dead code (D-16 byte-identical preserved at the runtime level).
</truths>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| harness_artifact SSE event → useChatState | Backend-supplied; signed_url is authoritative; URL points to Supabase Storage with RLS-guarded signed access |
| `<a download>` click → user browser → Supabase signed URL | rel="noopener noreferrer" prevents window.opener leak; signed URL has expiry |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-22-11-01 | Tampering | Malicious `signed_url` field could XSS via href javascript: | mitigate | Backend constructs signed_url from Supabase storage exclusively (https://...); frontend uses href attribute (browser blocks javascript: scheme on downloads); add an explicit `signed_url.startsWith('https://')` guard if paranoid |
| T-22-11-02 | Information Disclosure | Signed URL leaked via window.opener | mitigate | rel="noopener noreferrer" set on the `<a>` |
| T-22-11-03 | Phishing | User tricked by file_path display | accept | file_path is rendered as visible text; no shellish characters since filename comes from `contract-review-{8hex}.docx` template |
</threat_model>

<verification>
1. `cd frontend && npx tsc --noEmit` exits 0
2. `cd frontend && npm run lint` exits 0
3. `cd frontend && npm test -- --run` exits 0
4. `grep -c "harness_artifact" frontend/src/lib/database.types.ts frontend/src/hooks/useChatState.ts frontend/src/components/chat/MessageView.tsx` returns `>= 4`
</verification>

<success_criteria>
- harness_artifact SSE event flows from engine to MessageView
- Download chip renders with proper a11y + security attrs
- Fallback note shows when DOCX generation fails
- WorkspacePanel badges harness-source files in green
- ID + EN i18n parity
</success_criteria>

<output>
After completion, create `.planning/phases/22-contract-review-harness-docx-deliverable/22-11-SUMMARY.md`.
</output>
