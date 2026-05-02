---
phase: 16-v1-1-backlog-cleanup-fix-b-panel-tests-aschild-sweep
plan: 03
status: completed
completed: 2026-05-02
---

# Summary — Plan 16-03: base-ui asChild Shim Sweep (UI-01)

## What Was Done

Applied the `asChild → render` prop shim to the remaining base-ui wrappers:

- **`frontend/src/components/ui/select.tsx`** — patched `SelectTrigger` with the same 5-line shim already in `popover.tsx` and `tooltip.tsx`; preserves existing className for the non-asChild branch
- **`frontend/src/components/ui/dropdown-menu.tsx`** (NEW) — wraps `@base-ui/react/menu` (`DropdownMenu` / `DropdownMenuTrigger` / `Content` / `Item`) with full asChild shim
- **`frontend/src/components/ui/dialog.tsx`** (NEW) — wraps `@base-ui/react/dialog` with full asChild shim; `DialogTrigger` supports `asChild` via `render` prop passthrough

## Key Decisions

- Pattern: translate `asChild` to `render` prop — same pattern as `tooltip.tsx` / `popover.tsx` shim shipped in v1.1
- New files for dropdown-menu and dialog (no prior file existed); select was a patch

## Requirements Covered

- **UI-01** ✅ — All base-ui component wrappers (select, dropdown-menu, dialog, tooltip, popover) now support `asChild` via the render-prop shim
