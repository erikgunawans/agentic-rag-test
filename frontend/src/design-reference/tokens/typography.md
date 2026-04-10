# Typography

## Font

**Decision:** Keep **Geist Variable** (already installed via `@fontsource-variable/geist`). The Figma design uses Inter, but Geist has similar metrics and is already integrated.

## Type Scale

| Style | Size | Weight | Line Height | Letter Spacing | Tailwind Equivalent |
|---|---|---|---|---|---|
| Display | 38px | 700 (bold) | 1.1 | -0.02em | `text-4xl font-bold tracking-tight` |
| Heading | 20px | 600 (semibold) | 1.3 | normal | `text-xl font-semibold` |
| Body | 15px | 400 (regular) | 1.6 | normal | `text-[15px]` or `text-base` |
| Caption | 12px | 500 (medium) | 1.4 | normal | `text-xs font-medium` |
| Label | 11px | 600 (semibold) | 1.4 | 0.08em | `text-[11px] font-semibold uppercase tracking-wider` |

## Usage in Components

| Context | Style | Example |
|---|---|---|
| Welcome greeting ("Hi, Erik") | Display | 38px bold, gradient on name |
| Page/panel titles | Heading | "Knowledge Hub", "Documents" |
| Chat messages, descriptions | Body | 15px regular |
| Timestamps, metadata | Caption | "2h ago", "845 KB" |
| Section headers | Label | "TODAY", "RECENT UPLOADS", "DOCUMENT TYPE" |

## Notes

- The Label style is used heavily throughout sidebar sections and filter panels
- Body text at 15px is slightly larger than the current codebase default (14px via `text-sm`)
- Display style only appears on the welcome/home screen
