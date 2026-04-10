# Spacing & Radius

## Base Unit

**4px base unit** — all gaps, padding, and margins are multiples of 4px.

## Column Widths

| Column | Width | Context |
|---|---|---|
| IconRail (floating pill) | 56px (pill) within 60-88px container | All pages |
| Chat History Sidebar | 260px | Chat/Home page |
| Upload + Filter Panel | 300px | Documents page |
| Form/Config Panel | 360px | Creation, Comparison, Compliance, Analysis |
| Main Content | Remaining (fills) | All pages |

## Corner Radius Scale

| Value | Usage |
|---|---|
| 4px | Scrollbar thumb, small internal elements |
| 8px | Icon buttons, filter items, hover states |
| 10px | Search inputs, action buttons, file badges |
| 12px | Action buttons, New Chat button |
| 16px | Cards, drop zones, document cards |
| 20px | Input card, status pills, count pills |
| 28px | IconRail floating pill |

## Key Component Heights

| Component | Height |
|---|---|
| Header bar | 64-72px |
| Sub-header ("Recent Analyses") | 52px |
| History row | 44px |
| Action button | 44px |
| Conversation list item | 52px |
| Search bar | 32-36px |
| Hint chip | 26px |
| File badge | 30x30px |
| Icon button | 28-36px |
| New Chat button | 44px |
| User profile footer | 72px |

## Padding Patterns

| Context | Padding |
|---|---|
| Panel horizontal | 16-20px |
| Card internal | 16px |
| Input card | 20px |
| Section label | 8px 20px |
| Filter items | 0 12px |
| Main content grid | 20px 24px |

## Grid

| Context | Columns | Gap |
|---|---|---|
| Document cards | 3 columns | 16px |
| Quick-action bento | 2 columns (asymmetric) | 12px |
| Hint chips | horizontal row | 8px |

## Shadow System

| Context | Shadow |
|---|---|
| IconRail floating pill | `0 8px 32px rgba(0,0,0,0.4)` |
| Input card idle | `0 4px 24px rgba(0,0,0,0.3)` |
| Input card focused | `0 0 0 1px border-accent, 0 0 40px accent-glow` |
| Document card hover | `0 8px 32px rgba(0,0,0,0.3)` |
| Button hover | `0 4px 16px rgba(124,92,252,0.4)` |
| Active icon glow | `0 0 16px rgba(124,92,252,0.5)` |
