# Design Spec: 2026 UI Refresh — Calibrated Restraint

**Date:** 2026-04-14
**Branch:** feat/design-2026-refresh
**Direction:** Shift from navy-blue tinted surfaces to zinc-neutral, reduce visual noise, reserve glass for transient overlays, tighten typography, flatten buttons.

## 1. Color Palette

### Base Surfaces (navy → zinc)

| Token | Current | New |
|-------|---------|-----|
| `--background` | `#0B1120` | `#09090B` |
| `--card` | `oklch(0.18 0.015 260)` | `#18181B` |
| `--card-foreground` | `oklch(0.95 0 0)` | `#FAFAFA` |
| `--popover` | `oklch(0.18 0.015 260)` | `#18181B` |
| `--popover-foreground` | `oklch(0.95 0 0)` | `#FAFAFA` |
| `--secondary` | `oklch(0.22 0.015 260)` | `#27272A` |
| `--secondary-foreground` | `oklch(0.90 0 0)` | `#E4E4E7` |
| `--muted` | `oklch(0.22 0.015 260)` | `#27272A` |
| `--muted-foreground` | `oklch(0.60 0 0)` | `#A1A1AA` |
| `--accent` | `oklch(0.25 0.02 270)` | `#3F3F46` |
| `--accent-foreground` | `oklch(0.95 0 0)` | `#FAFAFA` |
| `--foreground` | `oklch(0.95 0 0)` | `#FAFAFA` |

### Borders

| Token | Current | New |
|-------|---------|-----|
| `--border` | `oklch(1 0 0 / 8%)` | `oklch(1 0 0 / 5%)` |
| `--input` | `oklch(1 0 0 / 12%)` | `oklch(1 0 0 / 8%)` |

### Sidebar & Icon Rail

| Token | Current | New |
|-------|---------|-----|
| `--sidebar` | `oklch(0.12 0.015 260)` | `#111113` |
| `--sidebar-foreground` | `oklch(0.90 0 0)` | `#E4E4E7` |
| `--sidebar-accent` | `oklch(0.20 0.02 270)` | `#27272A` |
| `--sidebar-accent-foreground` | `oklch(0.95 0 0)` | `#FAFAFA` |
| `--sidebar-border` | `oklch(1 0 0 / 8%)` | `oklch(1 0 0 / 5%)` |
| `--icon-rail` | `oklch(0.10 0.015 260)` | `#0C0C0E` |
| `--icon-rail-foreground` | `oklch(0.55 0 0)` | `#71717A` |

### Unchanged

- `--primary`: `oklch(0.55 0.20 280)` — purple accent stays
- `--primary-foreground`: `oklch(0.98 0 0)`
- `--ring`: `oklch(0.55 0.20 280)`
- `--destructive`: `oklch(0.65 0.20 25)`
- `--icon-rail-active`: `oklch(0.55 0.20 280)`
- All `--feature-*` accent colors
- All `--chart-*` colors

## 2. Typography

### Letter-spacing

| Element | Current | New |
|---------|---------|-----|
| H1 (text-xl, text-2xl, text-3xl) | `0` | `-0.02em` |
| H2 (text-lg) | `0` | `-0.01em` |
| H3 (text-sm headings) | `0` | `0` (unchanged) |
| Body | `0` | `0` (unchanged) |
| Captions (text-[10px], text-xs labels) | `0` | `+0.01em` |

### Font weight

| Element | Current | New |
|---------|---------|-----|
| Page titles (h1) | `font-bold` (700) | `font-semibold` (600) |
| Section headings (h2) | `font-bold` (700) / `font-semibold` (600) | `font-semibold` (600) |
| Sub-headings (h3) | `font-semibold` (600) | `font-medium` (500) |

Implementation: Add base styles in `@layer base` for heading elements.

## 3. Glass Treatment

**Rule:** Glass (backdrop-blur) only on transient overlays. Remove from persistent panels.

### Remove glass from:
- `ThreadPanel` sidebar wrapper — replace `glass dot-grid` with solid bg (`bg-sidebar`)
- All 10 page sidebar panels — remove `glass` class
- `MessageInput` card — remove `glass` class
- `WelcomeInput` card — remove `glass` class (if present)
- `FeaturePageLayout` right panel — remove `glass` class

### Keep glass on:
- Tooltips (`TooltipContent`)
- Popovers
- Mobile overlay backdrop
- Mobile header bar (`bg-background/95 backdrop-blur-md`)

### Glass token update:
| Token | Current | New |
|-------|---------|-----|
| `--glass-bg` | `oklch(0.16 0.015 260 / 0.65)` | `oklch(0.14 0 0 / 0.75)` |
| `--glass-border` | `oklch(1 0 0 / 12%)` | `oklch(1 0 0 / 8%)` |
| `--glass-blur` | `16px` | `16px` (unchanged) |

## 4. Buttons

### Primary button
- Remove gradient from `InputActionBar` send button: `bg-gradient-to-br from-primary to-[oklch(0.55_0.18_250)]` → `bg-primary`
- Remove gradient from all inline primary buttons across pages
- Add active state: `active:scale-[0.98]`

### User message bubbles
- Keep gradient on user chat bubbles: `bg-gradient-to-br from-primary to-[oklch(0.50_0.18_260)]` — this is content, not a button

## 5. Mesh Background

### mesh-bg pseudo-elements (index.css)

**::before (top-right glow):**
- Current: `rgba(76, 29, 149, 0.06)`, no blur
- New: `rgba(139, 92, 246, 0.04)`, add `filter: blur(40px)`

**::after (bottom-left glow):**
- Current: `rgba(10, 31, 61, 0.3)`, no blur
- New: `rgba(139, 92, 246, 0.03)`, add `filter: blur(40px)`

Both orbs become purple-hued (matching accent), lower opacity, heavier blur. Monochrome ambient glow.

## 6. Dot Grid

- Opacity: `oklch(1 0 0 / 0.04)` → `oklch(1 0 0 / 0.03)`
- Spacing: 24px (unchanged)
- Implementation: ::before pseudo (unchanged)

## 7. Shadows & Glows

| Token | Current | New |
|-------|---------|-----|
| `--glow-primary` | `0 0 20px oklch(0.55 0.20 280 / 0.15)` | `0 0 24px oklch(0.55 0.20 280 / 0.12)` |
| `--glow-sm` | `0 0 10px oklch(0.55 0.20 280 / 0.10)` | `0 0 14px oklch(0.55 0.20 280 / 0.08)` |
| `--shadow-*` | Current values | Unchanged |

## 8. Transitions

### Global easing
- Replace `transition-colors` default easing with `cubic-bezier(0.4, 0, 0.2, 1)` where applicable
- This is not a global override — apply via the existing `interactive-lift` class and inline transitions

### interactive-lift update
```css
.interactive-lift {
  transition: transform 0.15s cubic-bezier(0.4, 0, 0.2, 1),
              box-shadow 0.15s cubic-bezier(0.4, 0, 0.2, 1);
}
.interactive-lift:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
}
.interactive-lift:active {
  transform: translateY(0) scale(0.98);
  transition-duration: 0.05s;
}
```

## 9. Scrollbar

Update scrollbar thumb color to match zinc palette:
- Current: `oklch(0.25 0.015 260)` → New: `#3F3F46`
- Hover: `oklch(0.35 0.015 260)` → New: `#52525B`

## 10. Files to Modify

### CSS (1 file)
- `frontend/src/index.css` — All design tokens, utility classes, keyframes

### Layout (2 files)
- `frontend/src/layouts/AppLayout.tsx` — Remove any glass-related classes if present
- `frontend/src/components/layout/ThreadPanel.tsx` — Replace `glass dot-grid` with solid sidebar bg

### Chat components (3 files)
- `frontend/src/components/chat/MessageInput.tsx` — Remove `glass` from card
- `frontend/src/components/chat/WelcomeInput.tsx` — Remove `glass` from card (if present)
- `frontend/src/components/chat/InputActionBar.tsx` — Flatten send button gradient

### Pages (10 files — sidebar glass removal)
- `DocumentsPage.tsx`
- `ClauseLibraryPage.tsx`
- `RegulatoryPage.tsx`
- `ApprovalInboxPage.tsx`
- `ComplianceCheckPage.tsx`
- `ContractAnalysisPage.tsx`
- `DocumentComparisonPage.tsx`
- `DocumentCreationPage.tsx`
- `SettingsPage.tsx`
- `AdminSettingsPage.tsx`

### Shared (1 file)
- `frontend/src/components/shared/FeaturePageLayout.tsx` — Remove `glass` from right panel

### Grep for inline gradients
- Search all `.tsx` files for `bg-gradient-to-br from-primary` on buttons (not chat bubbles) and replace with `bg-primary`

## Out of Scope

- Layout structure changes (already done in prior session)
- Font family change (Geist stays)
- New components or pages
- Backend changes
- Auth page (already has its own dark design)
