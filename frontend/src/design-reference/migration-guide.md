# Migration Guide

How to transition the current RAG app frontend to the Knowledge Hub design.

## 1. Layout Architecture Change

**Current:** Each page manages its own layout. No shared wrapper.
**Target:** 3-column layout: IconRail + Sidebar/Panel + Main Content

**Reference:** `_figma-source/src/app/App.tsx` (38KB) contains the full 3-column layout pattern with conditional rendering per active nav icon.

### Steps:
1. Create `src/layouts/AppLayout.tsx` as a shared layout wrapper
2. Move routing to use `<Outlet>` pattern with AppLayout:
   ```
   / -> AppLayout
     /index -> ChatPage (sidebar: ThreadPanel)
     /documents -> DocumentsPage (sidebar: Upload+Filter panel)
     /create -> DocumentCreation (sidebar: Form panel)
     /compare -> DocumentComparison (sidebar: Config panel)
     /compliance -> ComplianceCheck (sidebar: Config panel)
     /analysis -> ContractAnalysis (sidebar: Config panel)
     /settings -> SettingsPage
     /admin/settings -> AdminSettingsPage
   ```
3. AppLayout renders: `<IconRailNew>` + sidebar slot (varies by route) + `<Outlet>`
4. Each page provides its own sidebar content and main content

### IconRail Navigation Mapping:
| Icon | Route | Figma nav id |
|---|---|---|
| Folder | /documents | 0 |
| Home | / (chat) | 1 |
| FilePlus | /create | 2 |
| GitCompare | /compare | 3 |
| ShieldCheck | /compliance | 4 |
| Scale | /analysis | 5 |

## 2. Font

**Decision:** Keep Geist Variable. Do not add Inter.
The designs render correctly with any clean sans-serif at the specified sizes/weights.

## 3. Dependencies

### DO NOT import from Figma export:
| Package | Reason |
|---|---|
| `@mui/material`, `@mui/icons-material`, `@emotion/*` | MUI not used in our system |
| `motion` | Animation library, use Tailwind transitions/CSS animations |
| `react-dnd`, `react-dnd-html5-backend` | Drag-and-drop, use native HTML5 DnD API |
| `next-themes` | Theme management, not needed (dark-mode-only) |
| `@radix-ui/*` | Direct Radix usage conflicts with @base-ui/react |
| `react-responsive-masonry` | Masonry layout, not used |
| `react-slick` | Carousel, not used |
| `react-popper`, `@popperjs/core` | Positioning, handled by @base-ui/react |
| `recharts` | Charts, not needed currently |
| `canvas-confetti` | Celebration effects, not needed |

### Already in our system:
- `lucide-react` (icons)
- `class-variance-authority` (variants)
- `clsx` + `tailwind-merge` (class merging)
- `@base-ui/react` (headless UI primitives)
- `tailwindcss` v4

## 4. Inline Style Conversion Strategy

The Figma export uses heavy inline styles. Convert using this mapping:

| Inline Style | Tailwind Class |
|---|---|
| `style={{ backgroundColor: '#0F1829' }}` | `bg-bg-surface` |
| `style={{ color: '#94A3B8' }}` | `text-muted-foreground` |
| `style={{ color: '#475569' }}` | `text-text-faint` |
| `style={{ border: '1px solid #1E2D45' }}` | `border border-border-subtle` |
| `style={{ borderRadius: '16px' }}` | `rounded-2xl` |
| `style={{ fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.08em' }}` | `text-[11px] font-semibold uppercase tracking-wider` |
| `style={{ width: '36px', height: '36px' }}` | `size-9` |
| `style={{ gap: '12px' }}` | `gap-3` |

### Hover states:
Replace `onMouseEnter`/`onMouseLeave` handlers with Tailwind `hover:` utilities:
```tsx
// Before (Figma)
onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = '#1C2840' }}
onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = 'transparent' }}

// After
className="hover:bg-bg-hover"
```

### Conditional styles:
Replace ternary style objects with `cn()`:
```tsx
// Before (Figma)
style={{ backgroundColor: isActive ? 'rgba(124,92,252,0.12)' : 'transparent' }}

// After
className={cn("bg-transparent", isActive && "bg-accent-primary/12")}
```

## 5. Background Mesh Gradient

The main content area uses a multi-layer background effect:

```css
.bg-mesh-gradient {
  background-color: var(--bg-base, #0B1120);
  background-image:
    radial-gradient(ellipse at 10% 10%, rgba(26, 15, 58, 0.6) 0%, transparent 600px),
    radial-gradient(ellipse at 90% 90%, rgba(10, 31, 61, 0.6) 0%, transparent 500px);
}
```

Apply as: `className="bg-mesh-gradient"` on the main content column.

Optional noise overlay (4% opacity) can be added via a pseudo-element or SVG filter if needed for texture.

## 6. Custom Scrollbar

Applied via `.scrollbar-kh` class (defined in index.css):
- 4px width, transparent track
- Purple thumb: `rgba(124,92,252,0.25)`, hover: `rgba(124,92,252,0.45)`
- Used in: form panels, history sections, drop zone scroll areas

## 7. Routing

Keep `react-router-dom` with the existing route structure. Add new routes for the 4 new screens:
- `/create` - Document Creation
- `/compare` - Document Comparison
- `/compliance` - Compliance Check
- `/analysis` - Contract Analysis

These will be added when each feature is implemented, not during this preparation phase.

## 8. Dark Mode

The app is dark-mode-only. The `.dark` class is always applied. No light/dark toggle needed.
Knowledge Hub tokens are defined in both `:root` (fallback) and `.dark` (primary).
