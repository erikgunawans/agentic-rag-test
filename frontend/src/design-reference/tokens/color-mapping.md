# Color Token Mapping

Maps Figma "Knowledge Hub" design tokens to the existing shadcn/Tailwind CSS variable system.

## Core Token Mapping

| Figma Token | Hex Value | Maps To (shadcn) | Tailwind Class | Notes |
|---|---|---|---|---|
| `--bg-deep` | `#080C14` | NEW `--bg-deep` | `bg-bg-deep` | IconRail bg, deepest layer |
| `--bg-base` | `#0B1120` | `.dark --background` | `bg-background` | Main content area (existing) |
| `--bg-surface` | `#0F1829` | NEW `--bg-surface` | `bg-bg-surface` | Sidebar/panel backgrounds |
| `--bg-elevated` | `#162033` | NEW `--bg-elevated` | `bg-bg-elevated` | Cards, inputs, elevated surfaces |
| `--bg-hover` | `#1C2840` | NEW `--bg-hover` | `bg-bg-hover` | Interactive hover states |
| `--accent-primary` | `#7C5CFC` | NEW `--accent-primary` | `text-accent-primary` | Purple accent, primary action color |
| `--text-primary` | `#F1F5F9` | `.dark --foreground` | `text-foreground` | Main text (existing) |
| `--text-secondary` | `#94A3B8` | `.dark --muted-foreground` | `text-muted-foreground` | Secondary text (existing) |
| `--text-faint` | `#475569` | NEW `--text-faint` | `text-text-faint` | Tertiary text, labels, timestamps |
| `--border-subtle` | `#1E2D45` | NEW `--border-subtle` | `border-border-subtle` | All borders |
| `--border-accent` | `rgba(124,92,252,0.4)` | NEW `--border-accent` | `border-border-accent` | Focus/accent borders |

## Accent Gradient

Used for gradient text effects (e.g., user name in welcome screen) and card hover glows.

| Token | Value | Tailwind |
|---|---|---|
| `--accent-gradient-start` | `#7C5CFC` | `from-accent-gradient-start` |
| `--accent-gradient-mid` | `#A78BFA` | `via-accent-gradient-mid` |
| `--accent-gradient-end` | `#60A5FA` | `to-accent-gradient-end` |

Usage: `bg-gradient-to-r from-accent-gradient-start via-accent-gradient-mid to-accent-gradient-end bg-clip-text text-transparent`

## Glow Token

| Token | Value | Usage |
|---|---|---|
| `--accent-glow` | `rgba(124,92,252,0.15)` | Box shadows, background glows behind active elements |

## Status Colors

| Token | Hex | Usage | Tailwind |
|---|---|---|---|
| `--success` | `#34D399` | Analyzed status, low risk, uploaded | `text-success`, `bg-success` |
| `--warning` | `#F59E0B` | Processing status, medium risk | `text-warning`, `bg-warning` |
| `--info` | `#22D3EE` | Cyan accents, DOCX badges, comparison | `text-info`, `bg-info` |
| `--danger` | `#F87171` | High risk, PDF badges, errors | `text-danger`, `bg-danger` |

## Per-Color Hover Glows (inline, not tokenized)

These are used on quick-action cards with per-color hover effects:

| Color | Glow BG | Border |
|---|---|---|
| Purple | `rgba(124, 92, 252, 0.15)` | `rgba(124, 92, 252, 0.4)` |
| Cyan | `rgba(34, 211, 238, 0.15)` | `rgba(34, 211, 238, 0.4)` |
| Green | `rgba(52, 211, 153, 0.15)` | `rgba(52, 211, 153, 0.4)` |
| Amber | `rgba(245, 158, 11, 0.15)` | `rgba(245, 158, 11, 0.4)` |
| Red | `rgba(248, 113, 113, 0.15)` | `rgba(248, 113, 113, 0.4)` |

## Tokens NOT Added (already covered by shadcn)

| Figma Token | Existing shadcn Equivalent |
|---|---|
| `--bg-base` (#0B1120) | `.dark --background` |
| `--text-primary` (#F1F5F9) | `.dark --foreground` |
| `--text-secondary` (#94A3B8) | `.dark --muted-foreground` |

These are mapped by adjusting the existing shadcn dark mode values during the UI redesign, rather than adding duplicate tokens.
