# Phase 16: v1.1 Backlog Cleanup (Fix B + Panel Tests + asChild Sweep) - Context

**Gathered:** 2026-05-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Three independent maintenance workstreams bundled into one phase to close v1.1's
inherited rough edges. All three are local edits with **no schema migrations,
no new env vars, no production-runtime feature flags**, and zero dependency
between sub-tracks — they could in principle ship as three commits in any
order.

1. **REDACT-01 (Fix B — Domain-term Deny List)** — The PII detection layer at
   `backend/app/services/redaction/detection.py` already has a hardcoded
   `_DENY_LIST_CASEFOLD` frozenset (added during v1.0 close after thread
   `bf1b7325` falsely redacted "Indonesian", "OJK", "UU PDP", etc.) and a
   passing test at `backend/tests/unit/test_detection_domain_deny_list.py`.
   What v1.1 left undone is the **"configurable"** half of REDACT-01: today
   the list is a module-level frozen constant — a deployer cannot extend it
   without a code change. Phase 16 makes the deny list runtime-configurable
   (per ROADMAP §Phase 16 SC#1: "honors a *configurable* deny list") while
   keeping the existing baked-in defaults so no production behavior regresses
   on the previously-fixed thread.

2. **TEST-01 (CodeExecutionPanel Component Tests)** — `CodeExecutionPanel.tsx`
   (359 lines) shipped in Phase 11 with UAT-only verification. Phase 16
   bootstraps a frontend test framework (currently absent — `package.json`
   has no vitest/jest, and `find ... -name '*.test.*'` returns zero hits) and
   adds component tests for the four behaviors called out in ROADMAP §Phase
   16 SC#2: streaming output, terminal rendering, signed-URL file download,
   and history-reconstruction render parity.

3. **UI-01 (`asChild` Shim Sweep)** — Two of three named wrappers in the
   ROADMAP slug do not yet exist. Reality on disk:
   - `frontend/src/components/ui/select.tsx` exists; `SelectTrigger` does
     **not** carry the `asChild`→`render` shim that `tooltip.tsx` and
     `popover.tsx` already have.
   - `frontend/src/components/ui/dropdown-menu.tsx` does **not** exist
     (`@base-ui/react/menu` is unwrapped today).
   - `frontend/src/components/ui/dialog.tsx` does **not** exist
     (`@base-ui/react/dialog` is unwrapped; the only "dialog" today is a
     handrolled `CreateFolderDialog.tsx` not built on base-ui).

   Phase 16 adds the shim to `select.tsx` and creates `dropdown-menu.tsx`
   and `dialog.tsx` as new shadcn-style wrappers with the standard `asChild`
   shim from day one. Build cleanliness is verified via the existing
   `tsc -b` (project-references) build, which is what catches missing-shim
   typescript errors.

**Not in scope** (explicitly rejected scope creep — see deferred ideas):
- Migrating the existing `CreateFolderDialog.tsx` onto the new `dialog.tsx`
  primitive (out of scope; would touch unrelated DocumentsPage flow).
- Adding deny-list editing UI in admin settings (env-var/system_settings
  toggle is sufficient per recommended-default decision below).
- Backfilling tests for other Phase 11 components (only `CodeExecutionPanel`
  is in REDACT-01's bundled scope).

</domain>

<decisions>
## Implementation Decisions

### REDACT-01 — Configurable Deny List Surface

- **D-P16-01:** **Use the existing `system_settings` single-row pattern, not a new env var or a new table.** Add a column `pii_domain_deny_list_extra TEXT NOT NULL DEFAULT ''` to `system_settings` via a new numbered migration (next free number — likely `037_*`) and read it through the existing 60s-cached `get_system_settings()` helper. Stored format: comma-separated case-insensitive terms, mirroring the existing `pii_surrogate_entities` / `pii_redact_entities` columns. Reason: every other PII config knob is already in `system_settings` (toggle, provider overrides, threshold buckets); admin-team workflow (CLAUDE.md "Admin / RBAC") expects new privacy knobs there. Auto-pick rationale: this was the "first / recommended" option in the gray-area sweep — the path of least surprise given existing patterns.

- **D-P16-02:** **Merge baked-in `_DENY_LIST_CASEFOLD` ∪ runtime `pii_domain_deny_list_extra`, not replace.** The hardcoded frozenset stays as the safe-by-default baseline (covers the original `bf1b7325` regression set: Indonesian, OJK, UU PDP, BJR, KUHP, KUHAP, UU ITE, UUPK, Bahasa, Mahkamah Agung, etc.). Runtime extras union into it case-folded inside `_is_domain_term`. Empty extras (default) → identical behavior to today. Reason: zero-regression guarantee on the production false-positive that triggered Fix B in the first place.

- **D-P16-03:** **Cache invalidation rides the existing 60s `get_system_settings()` TTL.** No bespoke cache for the deny list. After a deployer updates the row, the next analyzer call within 60s reads stale, then refreshes. Acceptable: deny-list edits are rare administrative ops, not request-path mutations. Reason: matches every other system-settings consumer and avoids inventing parallel cache infra.

- **D-P16-04:** **Lookup remains O(1) per detected entity span; no per-call `system_settings` round-trip.** `_is_domain_term` reads from a process-local `frozenset` snapshot constructed from `(_DENY_LIST_CASEFOLD ∪ runtime_extras_casefold)` cached for 60s. The cache key is the runtime-extras string itself; rebuilds happen at most once per minute regardless of detection volume. Reason: detection runs in the chat hot path (PERF-02 budget); we cannot afford an async settings call inside `detect_entities`.

- **D-P16-05:** **Regression test guard: extend `test_detection_domain_deny_list.py` rather than create a new file.** Add parametrized cases that (a) set runtime extras to `"foobar,baz"` and assert those terms are denied, (b) leave runtime extras empty and assert original `bf1b7325` regression set still passes, (c) assert real PII (`Pak Budi`, phone numbers, emails) still gets surrogate-bucketed under both modes. Reason: keeps the deny-list test surface in one file; reuses existing fixtures.

### TEST-01 — Frontend Test Framework Choice

- **D-P16-06:** **Vitest + @testing-library/react + jsdom.** The frontend stack is Vite already; vitest reuses Vite's transformer (zero new build pipeline), supports ESM, has fast watch mode, and is the de-facto standard for new Vite projects in 2026. Auto-pick rationale: first/recommended option for a Vite-native project; alternative would be Jest which requires duplicating Vite's transform via `@swc/jest` or `babel-jest` (rejected as over-investment for a 1-component test suite).

- **D-P16-07:** **Add as `devDependencies` only.** Packages: `vitest`, `@testing-library/react`, `@testing-library/jest-dom`, `@testing-library/user-event`, `jsdom`. Add `"test": "vitest run"` and `"test:watch": "vitest"` to `frontend/package.json` `scripts`. Co-locate test files next to the component (`CodeExecutionPanel.test.tsx`) per the React community default. Reason: keeps the testing surface small and lets future phases extend without re-bootstrapping.

- **D-P16-08:** **Mock `apiFetch` for signed-URL refresh; do NOT spin up MSW or a fake backend.** The component imports `apiFetch` from `@/lib/api` for the `GET /code-executions/{id}` round-trip (line ~17 of the file). Use vitest's `vi.mock('@/lib/api', ...)` to inject a fake. Reason: the test suite is for *component behavior*, not contract-testing the backend; MSW would be 10x the maintenance for marginal value at this size.

- **D-P16-09:** **Test cases — one per ROADMAP §Phase 16 SC#2 sub-bullet, plus 2 edge cases.** The four required:
  1. **Streaming output** — feed live `stdout: string[]` / `stderr: string[]` props, assert lines render in order with green / red color classes.
  2. **Terminal rendering** — assert dark-bg terminal block exists and renders ANSI-stripped text.
  3. **Signed-URL file download** — click Download, assert `apiFetch('/code-executions/{id}', ...)` is called and the returned signed URL triggers a navigation (mock `window.location.href` setter or use `<a>` ref).
  4. **History-reconstruction parity** — feed persisted `msg.tool_calls.calls[N].output`, assert visual output matches the streaming-mode render (same DOM shape, same icons, same status badge).
  5. *(Edge)* `executionId` undefined → Download button is disabled, no error.
  6. *(Edge)* Status `timeout` → renders the ⏱ icon with the `Clock` lucide component visible.

- **D-P16-10:** **Skip the live signed-URL navigation actually firing in jsdom.** jsdom doesn't follow redirects or do real downloads. The test asserts the API call shape and the rendered href on the anchor (or the call to `window.open`); the actual byte transfer is out of scope for component tests.

### UI-01 — `asChild` Shim Sweep — File Inventory & Pattern

- **D-P16-11:** **Three deliverables, three independent commits inside the phase:**
  1. *Patch* `select.tsx` — add the `asChild`→`render` shim to `SelectTrigger` (mirror of the `popover.tsx` / `tooltip.tsx` exact 5-line pattern).
  2. *New file* `dropdown-menu.tsx` — wrap `@base-ui/react/menu` as a shadcn-style `DropdownMenu` / `DropdownMenuTrigger` / `DropdownMenuContent` / `DropdownMenuItem` set, with `asChild` shim on `DropdownMenuTrigger`.
  3. *New file* `dialog.tsx` — wrap `@base-ui/react/dialog` as a shadcn-style `Dialog` / `DialogTrigger` / `DialogContent` / `DialogTitle` / `DialogDescription` set, with `asChild` shim on `DialogTrigger`.

   Reason: matches the literal slug "(Fix B + Panel Tests + asChild Sweep)" — three files, three behaviors. Auto-pick rationale: first/recommended option (the alternative was "lump dropdown-menu and dialog into a single bigger sweep that also covers radio-group, tabs, etc." — rejected as scope creep).

- **D-P16-12:** **Reuse the exact `popover.tsx` shim signature pattern verbatim.** From `popover.tsx`:
  ```tsx
  function PopoverTrigger({ asChild, children, ...props }: PopoverPrimitive.Trigger.Props & { asChild?: boolean }) {
    if (asChild) {
      return <PopoverPrimitive.Trigger data-slot="popover-trigger" render={children as React.ReactElement} {...props} />
    }
    return <PopoverPrimitive.Trigger data-slot="popover-trigger" {...props}>{children}</PopoverPrimitive.Trigger>
  }
  ```
  Substitute `Popover` → `Select` / `Menu` / `Dialog`. Same `data-slot` naming convention. Same `(... & { asChild?: boolean })` type intersection. Reason: consistency across all six wrappers (button, input, popover, tooltip, select, scroll-area + new dropdown-menu + dialog) means future authors copy-paste the same form.

- **D-P16-13:** **No call-site rewrites in this phase.** ROADMAP §Phase 16 SC#3 says "existing call sites that pass `asChild` no longer error." Today the only `asChild` consumers in the tree are `IconRail.tsx` (3x `<TooltipTrigger asChild>`) and `SkillsPage.tsx` (1x `<PopoverTrigger asChild>`) — both already work. We're adding the shim to *new* wrappers (dropdown-menu, dialog) and the existing select wrapper preemptively, so future call sites pass `asChild` without breaking. Reason: avoid touching unrelated UI; the success criterion is satisfied by the shim being present, not by manufacturing call sites.

- **D-P16-14:** **Verification = `cd frontend && npx tsc --noEmit && npm run build`.** The `build` script runs `tsc -b && vite build` per `package.json` — this is the exact "project-references mode" the ROADMAP success criterion calls out. The PostToolUse hook auto-runs lint/typecheck on `.tsx` edits (CLAUDE.md), so CI parity is implicit. Reason: no new tooling needed; the existing build chain already enforces SC#3.

### Cross-track — Sequencing & Wave Independence

- **D-P16-15:** **Three plans, parallelizable.** REDACT-01, TEST-01, UI-01 touch disjoint files (backend Python vs. frontend test infra vs. frontend UI components). The planner should produce three independent plans; the executor can run them as a 3-way wave inside the phase. Reason: `STATE.md` Wave A flags Phase 16 as parallel-safe with Phases 12 and 13; sub-plan parallelism extends that property.

- **D-P16-16:** **Single phase commit at the end, with the standard `feat(16): …` style.** No per-track milestone commits — the executor's atomic commit per plan already gives traceability. Reason: matches every prior shipped phase's git pattern.

### Claude's Discretion

- Exact column SQL type / default for `pii_domain_deny_list_extra` (`TEXT NOT NULL DEFAULT ''` is strongly preferred but the planner may pick `VARCHAR(8192)` if there's a justifiable cap).
- Exact migration filename suffix (e.g. `037_pii_domain_deny_list_extra.sql`).
- Whether to expose the deny-list extra read in `GET /admin/settings` API or only via direct `system_settings` row update — both are admin-only and either satisfies REDACT-01 SC#1.
- Exact Tailwind class strings on the new `dropdown-menu.tsx` and `dialog.tsx` content blocks — must conform to 2026 Calibrated Restraint (zinc-neutral, no blur on dialog overlays — wait, dialogs ARE transient overlays so blur IS allowed per CLAUDE.md "Glass" rule; planner judgment).
- Ordering of test cases inside `CodeExecutionPanel.test.tsx` (D-P16-09 lists them, but the file structure — `describe` blocks, fixture builders — is implementation detail).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### REDACT-01 — PII Deny List
- `backend/app/services/redaction/detection.py` §lines 60-90 — current `_DENY_LIST_CASEFOLD` constant + `_is_domain_term` helper (the surface to make configurable).
- `backend/app/services/redaction/detection.py` §lines 255-290 — `detect_entities` call site where `_is_domain_term` is invoked, post-Presidio, pre-bucket-dispatch.
- `backend/app/services/system_settings_service.py` — the single-row `system_settings` cache (60s TTL); blueprint for D-P16-01.
- `backend/tests/unit/test_detection_domain_deny_list.py` — existing regression test; D-P16-05 extends rather than replaces.
- `.planning/STATE.md` §Deferred Items, row "v1.0 / Privacy / Fix B" — the carry-over source row.
- `.planning/PROJECT.md` §Key Decisions, row "D-48 canonical-only egress scan" — references the production thread `bf1b7325` that motivated Fix B.

### TEST-01 — CodeExecutionPanel Tests
- `frontend/src/components/chat/CodeExecutionPanel.tsx` — the 359-line subject-under-test; props shape and SSE event consumption documented in its own header comment.
- `frontend/src/hooks/useChatState.ts` — owns `sandboxStreams: Map<string, {stdout: string[], stderr: string[]}>` (the live-streaming buffer the panel reads).
- `frontend/src/lib/api.ts` — `apiFetch` is the call to mock for signed-URL refresh.
- `.planning/phases/11-code-execution-ui-persistent-tool-memory/11-CONTEXT.md` §Streaming → Persisted Reconciliation (D-P11-02 / D-P11-06) — defines the live→persisted transition the tests must verify.
- `frontend/package.json` §scripts — `lint` / `build` exist; `test` script will be added.

### UI-01 — base-ui asChild Shim
- `frontend/src/components/ui/popover.tsx` §lines 12-18 — canonical shim source-of-truth (D-P16-12 says copy this pattern).
- `frontend/src/components/ui/tooltip.tsx` §lines 23-30 — second instance of the same shim (sanity check: identical signature).
- `frontend/src/components/ui/select.tsx` — needs shim added on `SelectTrigger`.
- `frontend/src/components/layout/IconRail.tsx` §lines 97, 170, 197 — existing `asChild` consumers (regression target — must keep working after sweep).
- `frontend/src/pages/SkillsPage.tsx` §line 563 — existing `<PopoverTrigger asChild>` (regression target).
- CLAUDE.md §"Gotchas" — "base-ui tooltips use `render` prop, not `asChild`. The shim in `tooltip.tsx` translates `asChild` to `render`." — the rule the sweep enforces.
- CLAUDE.md §"Design System" — Glass / blur rule; relevant to dialog overlay styling.

### Cross-cutting
- `.planning/REQUIREMENTS.md` §Bundled v1.1 Backlog (REDACT-01, TEST-01, UI-01) — the requirement IDs and their one-liner descriptions.
- `.planning/ROADMAP.md` §Phase 16 — the 4 success criteria and the dependency note ("Depends on: Nothing").
- `docs/superpowers/PRD-advanced-tool-calling.md` — milestone PRD; Phase 16 is the bundled backlog appendix to it.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- **`_is_domain_term` and `_DENY_LIST_CASEFOLD`** (`backend/app/services/redaction/detection.py` L64-90) — already wired into `detect_entities` at L270. Phase 16 swaps the lookup target from a frozen module constant to a 60s-cached union with `system_settings.pii_domain_deny_list_extra`.
- **`get_system_settings()` helper** (`backend/app/services/system_settings_service.py`) — 60s TTL single-row cache. Add the new column to its read; everything else (RLS policy, admin UI binding) follows existing patterns.
- **`popover.tsx` / `tooltip.tsx` shim pattern** — exact 5-line shape that gets copy-pasted into `select.tsx`, `dropdown-menu.tsx`, `dialog.tsx`. No invention required.
- **`apiFetch`** (`frontend/src/lib/api.ts`) — sole network dependency for `CodeExecutionPanel`; mock target for D-P16-08.
- **`useChatState.sandboxStreams`** (`frontend/src/hooks/useChatState.ts`) — already exposes the live-streaming arrays; tests construct fixture maps that mirror its shape.
- **`PostToolUse` hooks** (CLAUDE.md §Automations) — auto-run `tsc --noEmit && eslint` on `.tsx` edits and `py_compile` on `.py` edits. CI parity for free.

### Established Patterns

- **`system_settings` is a single-row table** (CLAUDE.md "Gotchas" + `system_settings_service.py`). Never use it as KV store. New PII knobs go as columns. Migration is required (the next sequential `0NN_*.sql` file under `backend/migrations/`).
- **Numbered migrations** — `001` through `036` applied. Use `/create-migration` to generate the next; the pre-commit hook blocks edits to applied migrations.
- **base-ui wrappers** — `data-slot="..."` naming convention on every primitive (see all 6 existing wrappers in `frontend/src/components/ui/`). New wrappers must follow.
- **Co-located React tests** — community default (vitest, react-testing-library) is `*.test.tsx` next to component. Phase 16 is the first frontend test, so this convention is being established here.
- **Fix B baseline behavior is locked** — `bf1b7325`-style false positives MUST stay denied even with empty runtime extras (D-P16-02 zero-regression guarantee).
- **Three workstreams must NOT cross-couple** — by design, REDACT-01 / TEST-01 / UI-01 share no files. The planner generating three plans should respect this.

### Integration Points

- **Migration `037_*` (or next free number)** → adds `pii_domain_deny_list_extra TEXT NOT NULL DEFAULT ''` to `system_settings`. RLS policy already covers the row (admin-write, system-readable).
- **`detect_entities` (chat hot path)** — receives the new union'd deny list via the local 60s cache. No async call inside; the cache rebuild happens out-of-band at the next `get_system_settings()` cycle.
- **Egress filter at `backend/app/services/redaction/egress.py`** — out of scope, but worth noting: the deny list filters BEFORE registry insertion, so egress filtering remains unchanged. No regressions to D-89.
- **`frontend/package.json`** — adds devDeps + test script; `vite.config.ts` may need a `test:` block for vitest jsdom env config (planner discretion).
- **Existing call sites of `<TooltipTrigger asChild>`** (IconRail), `<PopoverTrigger asChild>` (SkillsPage) — must continue to work; UI-01 adds shims to OTHER wrappers, doesn't touch these.
- **`docs/superpowers/specs/2026-04-14-design-2026-refresh.md`** — design tokens for new dialog/dropdown wrappers (zinc base, purple accent). Planner reads for class strings.

</code_context>

<specifics>
## Specific Ideas

- **The deny-list defaults are non-negotiable.** Whatever runtime-extras mechanism Phase 16 ships, the existing baked-in set (Indonesian, OJK, BJR, UU PDP, KUHP, KUHAP, UU ITE, UUPK, Bahasa, Mahkamah Agung, BI, KPK, BPK, Indonesia, Indonesians, English) MUST remain denied in the empty-extras case. The production thread `bf1b7325` is the canonical regression — D-P16-05 explicitly tests it.

- **Cities are still NOT on the deny list.** D-09 reasoning from v1.0 (in `detection.py` comments): "Jakarta" can appear in real personal addresses, where a false negative on the address is worse than a false positive on the bare city name. Deployers should NOT add Jakarta / Surabaya / Bandung to the runtime extras list either. This is a documentation note for admin UI, not a code constraint.

- **`_DENY_LIST_CASEFOLD` is a frozenset; the union must produce a frozenset to preserve O(1) lookup semantics in `_is_domain_term`.** D-P16-04 hinges on this. The planner's local cache should hold `frozenset(_DENY_LIST_CASEFOLD | parsed_extras_casefold)`, not a list.

- **`CodeExecutionPanel` exposes `executionId?: string` (optional, see component header L40-46).** Tests for the disabled-Download case (D-P16-09 edge #5) construct a fixture with `executionId: undefined`. The panel must continue to render gracefully — a behavior the original Phase 11 plan called out explicitly.

- **`CreateFolderDialog.tsx` is hand-rolled, not base-ui.** Phase 16's new `dialog.tsx` is for *future* dialogs; we do NOT migrate `CreateFolderDialog` onto it (deferred — see below).

- **`tsc -b` (project-references mode) is the build command.** `frontend/package.json` `build` script is `tsc -b && vite build`. This is the build that catches the missing-shim TS errors per ROADMAP SC#3. `npx tsc --noEmit` in plain mode is a weaker check.

</specifics>

<deferred>
## Deferred Ideas

- **Admin UI panel for editing the deny list** — D-P16-01 ships configurability via the `system_settings` row; an actual admin-page form is a future polish item. Defer to a v1.3 admin-UX phase.
- **Migrating `CreateFolderDialog.tsx` onto the new `dialog.tsx` primitive** — out of scope. Touches DocumentsPage flow. Future cleanup phase.
- **Component tests for other Phase 11 surfaces** (`SubAgentPanel.tsx`, `ToolCallList.tsx`, `MessageView.tsx`) — only `CodeExecutionPanel` is in the bundled scope. Future testing phase.
- **MSW (mock-service-worker) for backend contract tests** — D-P16-08 explicitly chose simple `vi.mock` over MSW. Revisit when the frontend test suite grows beyond ~5 components.
- **`asChild` shim sweep for additional base-ui primitives** (radio-group, tabs, accordion, slider, switch, checkbox) — not in the v1.1 backlog row; only select / dropdown-menu / dialog are named. Future maintenance phase if those wrappers get adopted.
- **Auto-detection of context-specific deny terms** (e.g. learn from registry rejection patterns over time) — future ML enhancement. The deny list stays static + admin-managed.
- **Per-tenant deny lists** — single-tenant deployment, `system_settings` is global. Multi-tenant phase if/when that becomes a product direction.

</deferred>

---

*Phase: 16-v1-1-backlog-cleanup-fix-b-panel-tests-aschild-sweep*
*Context gathered: 2026-05-02*
