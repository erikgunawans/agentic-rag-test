# Design Spec: Grouped Icon Rail

**Date:** 2026-04-15
**Branch:** feat/grouped-icon-rail
**Goal:** Reduce icon rail from 14 items to 7 by grouping related features into flyout popovers while keeping Chat and Dashboard as standalone 1-click items.

## Rail Structure (top to bottom)

| Position | Item | Type | Route / Contains |
|----------|------|------|------------------|
| Top | Logo + Panel toggle | Fixed | — |
| 1 | Chat | Standalone | `/` |
| 2 | Dashboard | Standalone | `/dashboard` |
| — | Separator | Visual | thin line divider |
| 3 | Documents | Group (flyout) | Documents (`/documents`), Create (`/create`), Compare (`/compare`) |
| 4 | Legal Tools | Group (flyout) | Clause Library (`/clause-library`), Compliance (`/compliance`), Analysis (`/analysis`), Obligations (`/obligations`) |
| 5 | Governance | Group (flyout) | Approvals (`/approvals`), Regulatory (`/regulatory`), Integrations (`/integrations`) |
| — | Spacer | flex-1 | — |
| Bottom | Settings | Standalone | `/settings` |
| Bottom | User Avatar | Fixed | user info |

## Icons

| Item | Lucide Icon |
|------|-------------|
| Chat | `Home` (existing) |
| Dashboard | `LayoutDashboard` (existing) |
| Documents | `Folder` (existing, represents the group) |
| Legal Tools | `Scale` (existing, represents the group) |
| Governance | `ShieldCheck` (existing, represents the group) |
| Settings | `Settings` (existing) |

## Interaction

### Standalone items (Chat, Dashboard, Settings)
- Click → navigate directly to route
- Active state: purple background + left gradient border (existing pattern)
- Tooltip on hover showing name

### Group items (Documents, Legal Tools, Governance)
- Click → open flyout popover to the right (using existing Popover component)
- Flyout content: group label header + list of items (icon + text label)
- Click flyout item → navigate to page, popover auto-closes
- Active state: group icon gets active style when ANY child route matches `location.pathname`
- Tooltip on hover showing group name
- Small badge indicator (optional): tiny dot or count showing number of items

### Flyout styling
- Reuse existing Popover component from `@/components/ui/popover`
- Background: solid `#141414` with border `rgba(255,255,255,0.08)`, rounded-xl
- Items: icon (h-4 w-4) + label text, padding 8px, rounded-lg hover state
- Active child item: `bg-primary/10 text-primary`
- Header: group name in `text-[10px] uppercase tracking-wider text-muted-foreground`

## Separator
- Thin horizontal line between standalone items and groups
- `w-6 h-px bg-border` centered on the rail
- Adds visual hierarchy without taking much space

## Active State Detection

A group is "active" when `location.pathname` starts with any of its children's paths:

```typescript
const isGroupActive = (children: NavItem[]) =>
  children.some(child => 
    child.end 
      ? location.pathname === child.path 
      : location.pathname.startsWith(child.path)
  )
```

## What Gets Removed

- The existing "More Modules" popover (grid icon) — no longer needed
- The `moreItems` array — Regulatory and Integrations move into Governance group
- 10 individual `navItems` entries replaced by 2 standalone + 3 groups

## Files to Modify

### Modified (1 file)
- `frontend/src/components/layout/IconRail.tsx` — restructure navItems, add group popovers, remove "More Modules"

### Unchanged
- All page files (routes stay the same)
- `AppLayout.tsx` (IconRail interface unchanged)
- `popover.tsx` (reused as-is)
- Mobile layout (icon rail is `hidden md:flex`)
- i18n translations (reuse existing `nav.*` keys, add `nav.documents.group`, `nav.legalTools`, `nav.governance`)

## Out of Scope

- Mobile navigation changes (icon rail hidden on mobile)
- Sidebar panel changes
- Route restructuring
- New pages or features
