---
phase: 11-code-execution-ui-persistent-tool-memory
plan: 06
subsystem: ui

tags: [typescript, react, component, frontend, code-execution, sandbox-ui, i18n]

# Dependency graph
requires:
  - plan: 11-02
    provides: "frontend ToolCallRecord shape (tool_call_id + status fields) + CodeStdoutEvent/CodeStderrEvent SSE union — types the panel reads from after refetch / during streaming"
  - plan: 11-03
    provides: "GET /code-executions/{execution_id} endpoint — refresh-signed-URL roundtrip on file download click"
  - plan: 11-05
    provides: "useChatState.sandboxStreams Map<tool_call_id, { stdout, stderr }> — caller passes the current entry's arrays as stdoutLines / stderrLines props during streaming"
provides:
  - "frontend/src/components/chat/CodeExecutionPanel.tsx — self-contained inline panel for execute_code tool calls (Python badge, status indicator, live timer, collapsible code preview, terminal-style stdout/stderr, error pill, file download cards)"
  - "17 sandbox.* i18n keys per locale (id + en) under flat dotted-key style — consumed by the panel via useI18n()"
affects: [11-07]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Live → persisted source switch via prop hand-off: caller (Plan 11-07) decides per-render whether to feed sandboxStreams.get(toolCallId) (during streaming) or msg.tool_calls.calls[N].output (after refetch). Panel itself is stateless about the source — symmetric with the existing streamingContent → message-row pattern useChatState already uses for assistant text."
    - "Refresh-on-click signed-URL pattern: handleDownload calls apiFetch('/code-executions/{executionId}'), reads json.files[].signed_url for the matching filename, opens with window.open(url, '_blank', 'noopener,noreferrer'). URL is never persisted in component state — released after the open() call."
    - "Card-scoped (not panel-scoped) loading + error state for downloads: downloadingFile / downloadError keyed by filename so multiple files in the same panel can have independent UX."
    - "Status-icon switch pattern: single IIFE returns { Icon, cls, label } per status case — colocates icon component, color class, and i18n label together so adding/changing a status is one-spot."
    - "motion-safe:animate-spin + motion-safe:animate-pulse — Tailwind's prefers-reduced-motion variant suppresses the animation automatically, no extra index.css handling needed."

key-files:
  created:
    - "frontend/src/components/chat/CodeExecutionPanel.tsx — 359 lines. Default export `CodeExecutionPanel`. Props per UI-SPEC §Component Inventory. No tests at this layer — visual contract is exhaustively spec'd in 11-UI-SPEC and the integration/visual coverage lives in Plan 11-07's wiring."
  modified:
    - "frontend/src/i18n/translations.ts — +40 lines (17 keys × 2 locales + 4 comment lines). Added under both id and en blocks in dotted-key style ('sandbox.status.pending' etc.) to match the existing chat.* / nav.* / settings.* convention."

key-decisions:
  - "Followed the existing flat-dotted-key style ('sandbox.status.running' as a string literal) instead of a nested sandbox: { status: { running } } object, because the rest of translations.ts is exclusively flat dotted (Record<string, string> per the type declaration in I18nContext.tsx). The plan permitted either, and matching the existing style avoids a one-off shape that would require a different t() resolution."
  - "Did NOT implement client-side replacement of the backend-emitted truncation marker (e.g. swapping '…[truncated, N more bytes]' for the localized sandbox.truncated value). Plan 11-06 §Task 1 explicitly allowed this choice. Backend already emits the marker as part of the persisted output (Plan 11-01 + 11-04); the i18n key is in place as a future re-localization hook. Rendering the backend string verbatim keeps the v1 implementation simpler. If localized truncation is required later, a one-line .replace() on each line in the stderr/stdout map is the trivial follow-up."
  - "Stdout-then-stderr render order, NOT strict arrival-order interleave. The plan §implementation notes called this out as deferred for the v1 contract — the upstream useChatState.sandboxStreams keeps the two arrays separate (Plan 11-05). Most runs are stdout-dominant; a tighter interleave would require the Plan 11-05 callback to push into a single ordered array with a discriminator. Logged as a deferred polish item; not a regression."
  - "Used motion-safe:animate-spin / motion-safe:animate-pulse (Tailwind's prefers-reduced-motion variant) instead of relying solely on the .shimmer @media block. The .shimmer suppression covers the skeleton case but the spinner inside the status indicator and the cursor inside the empty terminal are bare animate-* utilities — wrapping with motion-safe: is a one-keyword cost that aligns with the panel's accessibility intent."
  - "executionId prop typed `string | undefined` with the download button disabled when absent. Sandbox tool_output canonical key is `out.execution_id` (backend sandbox_service.py L284) — the panel does not fall back to `out.id` (no such key exists; the chain has been removed in this phase per the plan's explicit guidance). Legacy / non-sandbox rows that lack execution_id render the panel without download — the file cards still show filename + size, but the button is disabled. This is the gracefully-degraded path the plan asked for."
  - "Pre-existing lint errors in 8 unrelated files surfaced under `npm run lint` — pre-existing on master HEAD before Plan 11-06; logged to deferred-items.md per executor scope-boundary rule. Targeted lint on the two files modified by this plan (CodeExecutionPanel.tsx, translations.ts) exits 0 cleanly."

requirements-completed: [SANDBOX-07]

# Metrics
duration: ~12m
completed: 2026-05-01
---

# Phase 11 Plan 06: CodeExecutionPanel Component Summary

**Self-contained inline React component for `execute_code` tool calls — renders Python badge, 5-state status indicator, live execution timer, collapsible code preview, terminal-style stdout (green) / stderr (red) on zinc-900 background, and refresh-signed-URL file download cards. All visible text routed through 17 new `sandbox.*` i18n keys (Indonesian + English).**

## Performance

- **Duration:** ~12m (read context + plan; single Write for the component; targeted edits to translations.ts; one cosmetic comment edit to satisfy the plan's literal `! grep -q "backdrop-blur"` gate without changing any runtime CSS).
- **Started:** 2026-05-01T20:25Z
- **Completed:** 2026-05-01T20:38Z
- **Tasks:** 2
- **Files created:** 1 (`CodeExecutionPanel.tsx`)
- **Files modified:** 1 (`translations.ts`)
- **Net change:** +359 lines (component) + 40 lines (i18n) = +399 lines

## Accomplishments

### Task 1 — i18n keys

17 keys added per locale (34 total) under both the `id` and `en` blocks of `translations.ts`:

| Group | Keys |
|---|---|
| Status (5) | `sandbox.status.{pending, running, success, error, timeout}` |
| Panel labels (7) | `sandbox.{showCode, hideCode, filesGenerated, download, downloadError, copyCode, codeCopied}` |
| Error labels (4) | `sandbox.error.{runtime, timeout, oom, unknown}` |
| Truncation (1) | `sandbox.truncated` (with `{bytes}` placeholder, supported by useI18n's params arg) |

Indonesian copy exactly per UI-SPEC §Copywriting Contract — `Berjalan…`, `Selesai`, `Gagal`, `Kedaluwarsa`, `Tampilkan kode`, `Sembunyikan kode`, `File yang dihasilkan`, `Unduh`, `Tersalin!`, `Kesalahan runtime Python`, `…[terpotong, {bytes} byte lagi]`. English mirrors verbatim.

### Task 2 — Component

`CodeExecutionPanel.tsx` (359 lines) implements the full UI-SPEC §Component Inventory contract:

**Header** — Always visible. Python language badge (`bg-primary/15 text-primary` with `<Terminal />` icon) + status indicator (icon + label + color per the 5-state table) + execution time (`tabular-nums`, live ticking via 100ms `setInterval`, frozen on `executionMs` once status leaves running/pending) + chevron toggle (right-aligned, rotates 90° when expanded).

**Status states (5):**
| Status | Icon | Color |
|---|---|---|
| `pending` | `Loader2` (spin) | `text-muted-foreground` |
| `running` | `Loader2` (spin) | `text-primary` |
| `success` | `CheckCircle2` | `text-green-500 dark:text-green-400` |
| `error` | `XCircle` | `text-red-500 dark:text-red-400` |
| `timeout` | `Clock` | `text-amber-500 dark:text-amber-400` |

**Code preview** — Collapsed by default (D-P11-09). When expanded: zinc-900 background, zinc-100 monospace text, `whitespace-pre-wrap break-all`, `max-h-80 overflow-y-auto`, copy-to-clipboard button absolute-positioned top-right. No syntax highlighting library (deferred — bundle weight cost not justified per UI-SPEC).

**Terminal output area** — Visible when any stdout/stderr exists OR when status is pending/running. `bg-zinc-900 dark:bg-zinc-950 max-h-60 overflow-y-auto px-3 py-2 font-mono text-xs leading-relaxed`. stdout lines render in `text-green-400`, stderr lines in `text-red-400`. Empty-running state shows a `motion-safe:animate-pulse` cursor `▊` in green. Autoscroll uses the 8px sticky-bottom threshold from UI-SPEC §Streaming Lifecycle (`scrollTop + clientHeight >= scrollHeight - 8`); a manual scroll-up disables autoscroll until the user scrolls back to the bottom.

**Error pill** — Renders below the terminal area when `status === 'error'` and `errorType` is present. Error type strings map to i18n keys (`sandbox.error.runtime / timeout / oom / unknown`). Border + background + text classes match UI-SPEC §Error State (`border-red-500/30 bg-red-500/10 dark:bg-red-500/15 text-red-700 dark:text-red-300`).

**File cards footer** — Section header `sandbox.filesGenerated`, then one card per file. Each card: `<FileDown />` icon + truncating filename + human-readable size (`formatBytes` helper covers B / KB / MB / GB) + `<Button size="sm" variant="default">` download. Click flow:
1. Card-scoped loading state (`<Loader2 motion-safe:animate-spin />` replaces `<Download />`).
2. `apiFetch('/code-executions/{executionId}')` → reads `json.files[].signed_url` for the matching filename.
3. `window.open(signed_url, '_blank', 'noopener,noreferrer')` — strips opener access (T-11-06-2 mitigation).
4. On failure: 2-second `<AlertCircle />` + `sandbox.downloadError` indicator on that card only.

The download button is `disabled` when `executionId` is undefined (legacy / non-sandbox rows lack the canonical `out.execution_id` per backend `sandbox_service.py` L284).

## Design-System Compliance

| Rule | Status |
|---|---|
| No `backdrop-blur` (CLAUDE.md persistent-panel glass rule) | PASS — confirmed via `! grep -q "backdrop-blur"` |
| No gradient (CLAUDE.md "buttons solid flat") | PASS — only solid `bg-card`, `bg-zinc-900`, `bg-primary/15`, `bg-red-500/10` |
| No raw HTML insertion (XSS posture) | PASS — all output rendered as React text children inside `<pre>` and `<div>`. No raw-HTML escape hatch is referenced anywhere in the file (verified by negative grep). |
| Lucide icons only (project icon library) | PASS — `Terminal, Copy, ChevronRight, Loader2, CheckCircle2, XCircle, Clock, AlertCircle, FileDown, Download` |
| `Button` from `@/components/ui/button` (not raw `<button>` for the download CTA) | PASS — `<Button size="sm" variant="default">` per UI-SPEC §File Cards |
| i18n via `useI18n()` for all visible strings | PASS — 11 `t('sandbox.*')` call sites; the `Python` badge label intentionally hardcoded (proper noun, not translated, per UI-SPEC §Python Badge Label) |
| Accessibility: `aria-live="polite"` on status, `role="log"` on terminal, `aria-expanded` on toggle, `aria-label` on download buttons + copy button | PASS |

## `out.execution_id` Resolution Posture

Per the plan's explicit guidance (echoing the verified ground truth from `backend/app/services/sandbox_service.py` L284):

- The sandbox tool_output dict carries the canonical key `execution_id` (UUID string).
- There is **no** `id` key on sandbox output; the legacy `?? out.id` fallback chain has been removed.
- `executionId` is typed `string | undefined`. Plan 11-07 will resolve it from `call.output.execution_id` and pass it through.
- When undefined, the file-download button is disabled (`disabled={!executionId || isDl}`); the panel still renders gracefully (header, code preview, terminal, file rows minus the working button). This is the documented degraded path for legacy or non-sandbox rows.

## Verification Gates

- `cd frontend && npx tsc --noEmit` — exit 0 (silent, full-project type check)
- `cd frontend && npx eslint src/components/chat/CodeExecutionPanel.tsx src/i18n/translations.ts` — exit 0 (silent, targeted)
- All 17 `sandbox.*` keys present in both `id` and `en` blocks — confirmed (`grep -c "'sandbox\\." translations.ts` = 34 = 17 × 2)
- `! grep -q "backdrop-blur" CodeExecutionPanel.tsx` — PASS (after the cosmetic comment edit on L30 — see Deviations §1)

## Deviations from Plan

### 1. [Rule 3 — Blocking] Cosmetic comment edit so the literal grep gate passes

- **Found during:** Task 2 verification.
- **Issue:** The plan's `<verification>` block uses `! grep -q "backdrop-blur"` (a literal-string negation). The component had a comment that read "NO backdrop-blur", which contains the literal token even though no Tailwind class of that name is used anywhere in the file. The literal grep gate would have failed.
- **Fix:** Rephrased the comment from `NO backdrop-blur` to `NO blurred backgrounds` on L30. Same semantic intent, same safety invariant ('no `backdrop-blur` Tailwind class anywhere in the file'), and the literal grep now passes.
- **Files modified:** `frontend/src/components/chat/CodeExecutionPanel.tsx` (1 word in 1 comment line).
- **Verification:** `grep -q "backdrop-blur" src/components/chat/CodeExecutionPanel.tsx` returns no match → PASS.
- **Commit:** Folded into the Task 2 commit (`5bab150`); no separate commit needed.

**Total deviations:** 1 auto-fixed (Rule 3 — blocking gate). **Impact:** None — cosmetic comment wording only, zero runtime/CSS/UX change.

## Authentication Gates

None encountered.

## Deferred Issues

### Pre-existing lint errors (out of scope)

`npm run lint` reports 10 pre-existing errors in 8 unrelated files (`UserAvatar.tsx`, `button.tsx`, `AuthContext.tsx`, `useToolHistory.ts`, `I18nContext.tsx`, `DocumentCreationPage.tsx`, `DocumentsPage.tsx`, `ThemeContext.tsx`). All present on master HEAD before Plan 11-06; none in files touched by this plan. Logged to `.planning/phases/11-code-execution-ui-persistent-tool-memory/deferred-items.md` per executor scope-boundary rule. Should be addressed by a dedicated lint-cleanup plan, not Plan 11-06.

### Strict stdout/stderr arrival-order interleave (deferred — v1 contract)

Per the plan's explicit allowance and the upstream Plan 11-05 contract (separate `stdout` / `stderr` arrays in `sandboxStreams`), the panel renders all stdout lines first, then all stderr lines. Most sandbox runs are stdout-dominant; the visible UX is acceptable for v1. A future enhancement could merge into a single ordered array with a discriminator field — would require a Plan 11-05 callback signature change.

### Localized truncation-marker replacement (deferred — i18n key in place as future hook)

The backend (Plan 11-01 + 11-04) already emits the truncation marker into the persisted output as ASCII text. The `sandbox.truncated` i18n key is added but not actively consumed by a `.replace(...)` swap in this v1 panel. If localized truncation becomes a UX requirement later, the swap is a one-line addition inside the stdout/stderr `.map(...)`.

## Task Commits

Each task committed atomically:

1. **Task 1 — i18n keys (17 × 2 locales)** — `bbac641` (`feat(11-06): add sandbox.* i18n keys for Code Execution Panel`)
2. **Task 2 — CodeExecutionPanel.tsx component** — `5bab150` (`feat(11-06): add CodeExecutionPanel component (SANDBOX-07)`)

## Files Created/Modified

- **Created:** `frontend/src/components/chat/CodeExecutionPanel.tsx` (359 lines, default export `CodeExecutionPanel`).
- **Modified:** `frontend/src/i18n/translations.ts` (+40 lines: 17 keys × 2 locales + 4 lines of grouping comments).

## Next Plan Readiness

Plan 11-07 — *Wire `CodeExecutionPanel` into `ToolCallList` + thread `sandboxStreams` through `MessageView`* — has all upstream dependencies satisfied:

- The panel itself ships in this plan (Plan 11-06).
- `useChatState.sandboxStreams` Map is exposed (Plan 11-05).
- `ToolCallRecord.tool_call_id` + `status` field types are in `database.types.ts` (Plan 11-02).
- `GET /code-executions/{execution_id}` endpoint is live (Plan 11-03).
- `ToolCallRecord` persistence with full output, status, and tool_call_id is wired through `chat.py` (Plan 11-04).

Wave 3 can now proceed to Plan 11-07's routing layer with no blockers.

## Self-Check: PASSED

- `[ -f frontend/src/components/chat/CodeExecutionPanel.tsx ]` → FOUND
- `[ -f frontend/src/i18n/translations.ts ]` → FOUND (modified)
- `git log --oneline | grep -q "bbac641"` → FOUND
- `git log --oneline | grep -q "5bab150"` → FOUND
- All `<acceptance_criteria>` from Tasks 1 + 2 verified PASS via the verification block above.
- Re-run of plan-level `<verification>` block: `tsc --noEmit` exit 0; `eslint <files>` exit 0; required identifiers grep PASS; `backdrop-blur` negation grep PASS.
