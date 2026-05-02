# Phase 16: v1.1 Backlog Cleanup (Fix B + Panel Tests + asChild Sweep) - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-02
**Phase:** 16-v1-1-backlog-cleanup-fix-b-panel-tests-aschild-sweep
**Mode:** `--auto` (single-pass, no AskUserQuestion; Claude auto-selects first / recommended option for every gray area)
**Areas discussed:** REDACT-01 deny-list configurability surface; REDACT-01 cache invalidation strategy; TEST-01 frontend test framework; TEST-01 mocking strategy; UI-01 file inventory & pattern; UI-01 call-site rewrites; cross-track sequencing

---

## REDACT-01 Configurability Surface — How is the runtime deny list exposed?

| Option | Description | Selected |
|--------|-------------|----------|
| `system_settings` column with cached read (recommended) | New `pii_domain_deny_list_extra TEXT` column read via existing `get_system_settings()` 60s cache. Mirrors all other PII knobs. | ✓ |
| New env var `PII_DOMAIN_DENY_LIST_EXTRA` | Set at Railway; requires redeploy to change. | |
| Dedicated `pii_deny_list` table with admin CRUD UI | Multi-row, admin-curated, audited. Higher build cost. | |

**Auto-selected:** `system_settings` column with cached read.
**Rationale:** First / recommended option. Matches every existing PII config pattern (toggle, provider overrides, threshold buckets) — minimum surprise, reuses 60s cache, no new infra. Logged inline in CONTEXT.md as D-P16-01.

---

## REDACT-01 Defaults Behavior — Replace or Merge with hardcoded list?

| Option | Description | Selected |
|--------|-------------|----------|
| Merge runtime extras into baked-in `_DENY_LIST_CASEFOLD` (recommended) | Union — empty extras → identical behavior to today; protects `bf1b7325` regression. | ✓ |
| Replace `_DENY_LIST_CASEFOLD` with runtime value | Deployer must restate the full list; risk of accidentally dropping an entry. | |

**Auto-selected:** Merge / union.
**Rationale:** First / recommended option. Zero-regression guarantee on the production thread that motivated Fix B. Logged inline as D-P16-02.

---

## TEST-01 Test Framework — Which runner?

| Option | Description | Selected |
|--------|-------------|----------|
| Vitest + @testing-library/react + jsdom (recommended) | Vite-native; reuses existing transformer; ESM-friendly; standard for new Vite projects. | ✓ |
| Jest + @testing-library/react | Mature ecosystem; requires duplicating Vite's transform via SWC/Babel. | |
| Playwright Component Testing | Real browser; heavier setup; better for visual / interaction tests. | |

**Auto-selected:** Vitest.
**Rationale:** First / recommended option for a Vite-native frontend. Lowest setup cost, no parallel build pipeline. Logged as D-P16-06.

---

## TEST-01 API Mocking Strategy — How to fake `apiFetch`?

| Option | Description | Selected |
|--------|-------------|----------|
| `vi.mock('@/lib/api')` (recommended) | Lightweight; targets the single network dep in the panel. | ✓ |
| MSW (mock-service-worker) | HTTP-level interception; better for contract tests; heavier setup. | |
| Real backend in test env | Slow, flaky, requires fixtures. | |

**Auto-selected:** `vi.mock`.
**Rationale:** First / recommended option. Component-test scope; MSW is overkill at one-component scale. Logged as D-P16-08.

---

## UI-01 File Inventory — Three discrete files, or broader sweep?

| Option | Description | Selected |
|--------|-------------|----------|
| Three deliverables: patch `select.tsx`, create `dropdown-menu.tsx`, create `dialog.tsx` (recommended) | Matches the literal slug. Smallest blast radius. | ✓ |
| Broader sweep including radio-group, tabs, accordion, slider, switch, checkbox | Fixes future breakage proactively; significantly enlarges scope. | |
| Only patch existing wrappers; defer new wrappers to next phase that needs them | Smaller commit; leaves the slug half-honored. | |

**Auto-selected:** Three deliverables matching the slug.
**Rationale:** First / recommended option. Honors the literal phase name; rejects scope creep. Logged as D-P16-11.

---

## UI-01 Call-Site Rewrites — Should we add new `asChild` consumers to verify shim works?

| Option | Description | Selected |
|--------|-------------|----------|
| No new call-site rewrites; ship the shim only (recommended) | Existing `<TooltipTrigger asChild>` and `<PopoverTrigger asChild>` already work — they're the regression check. SC#3 satisfied by shim presence. | ✓ |
| Manufacture sample call sites for the new `dropdown-menu.tsx` and `dialog.tsx` | Adds unrelated UI; risks design-system drift. | |

**Auto-selected:** No new call-site rewrites.
**Rationale:** First / recommended option. `tsc -b` clean build is the SC; existing call sites are the regression target. Logged as D-P16-13.

---

## Cross-Track Sequencing — Three plans run sequentially or in parallel?

| Option | Description | Selected |
|--------|-------------|----------|
| Three plans, parallelizable inside the phase (recommended) | Disjoint files; STATE.md already flags Phase 16 as parallel-safe. | ✓ |
| Sequential REDACT → TEST → UI (or any other order) | Simpler executor logic; slower wall clock. | |

**Auto-selected:** Three parallel plans.
**Rationale:** First / recommended option. Files don't intersect; matches `workflow.parallel=true` config. Logged as D-P16-15.

---

## Claude's Discretion

- Exact column SQL type / default for `pii_domain_deny_list_extra`.
- Exact migration filename suffix / number.
- Whether to expose deny-list reading via `GET /admin/settings` API or only direct row update.
- Tailwind class strings on new `dropdown-menu.tsx` and `dialog.tsx` (must conform to 2026 Calibrated Restraint).
- `describe` / `it` block structure inside `CodeExecutionPanel.test.tsx`.

## Deferred Ideas

- Admin UI form for editing deny list (defer to v1.3 admin-UX phase).
- Migrating `CreateFolderDialog.tsx` onto new `dialog.tsx` (defer; touches unrelated flow).
- Component tests for `SubAgentPanel.tsx`, `ToolCallList.tsx`, `MessageView.tsx`.
- MSW for HTTP-level contract tests (revisit at ~5 components).
- Broader `asChild` shim sweep for radio-group / tabs / accordion / slider / switch / checkbox.
- Auto-learning deny terms from registry rejection patterns.
- Per-tenant deny lists (multi-tenant future).

---

*Auto-mode discussion: 7 gray areas, 7 recommended-default selections, single pass, no user prompts.*
