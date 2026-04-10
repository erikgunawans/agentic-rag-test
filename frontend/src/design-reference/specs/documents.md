# Documents Screen

**Source:** `_figma-source/src/imports/pasted_text/knowledge-hub-documents.md`
**Component:** `_figma-source/src/app/components/Documents.tsx` (nav id: 0, Folder icon)

## Layout

3-column: Icon Rail (60px, simple variant) + Upload & Filter Panel (300px) + Document Grid (remaining)

Note: When Documents is active, the icon rail switches to a simpler full-height variant (not floating pill).

## Column 1: Icon Rail (Simple Variant)

- Width: 60px, bg: `bg-deep` (#080C14), full height
- Same icons, but stacked directly (no floating pill, no backdrop blur)
- Folder icon is active state

## Column 2: Upload + Filter Panel (300px)

- bg: bg-surface, right border: border-subtle
- Split into two sections with 1px divider

### Section 1: Upload (top)
1. **Header** (64px): "Documents" 15px semibold + clock/history icon button
2. **Drop Zone** (margin 12px 16px):
   - bg-elevated, rounded-2xl, 2px dashed border `accent-primary/35`
   - Inner glow: radial `accent-primary/6`
   - Upload cloud icon (40px circle bg) + "Drag & drop files here" + file types + "Browse Files" button
   - Drag-over: border becomes `accent-primary/70`, tint overlay
3. **Recent Uploads** label (11px uppercase) + 3 rows:
   - File badge (30x30, PDF=red, DOCX=cyan) + name + meta + status dot (green/amber)
4. **Storage Quota**: progress bar (4px, gradient fill), "2.4 GB / 10 GB"

### Section 2: Filter (bottom, fills remaining)
1. **Header** (52px): "Filter" + "Reset" link
2. **Search** (32px): bg-elevated, magnifier + "Search types..."
3. **Document Type** label + 8 filter items:
   - Active: bg `accent-primary/12`, left accent bar (3px), label + count pill in purple
   - Default: hover bg-hover, label text-secondary, count in text-faint
   - Items: All Documents (47), NDA (12), Kontrak (9), Kepatuhan (8), Laporan (7), Perjanjian (6), Invoice (3), Lainnya (2)
4. **Status** label + 3 checkboxes:
   - Checked: bg accent-primary + white checkmark
   - Items: Analyzed (green dot, 38), Processing (amber dot, 6), Pending (gray dot, 3)

## Column 3: Document Grid

- bg: bg-base + subtle mesh gradient (radial purple from top-right at 6% opacity)

### Top Bar (64px):
- Left: "All Documents" 20px semibold + "47 documents" count
- Right: search (240px) + sort dropdown + view toggle (grid/list) + "New Document" button

### Document Cards (3-column grid, 16px gap):
- Size: ~336px x 180px, bg-elevated, rounded-2xl, border-subtle
- Layout: file type badge (PDF/DOCX pill) + options menu -> title + category + preview text -> avatar stack + modified time + status chip
- Hover: 3px gradient top bar appears, border-accent, elevated shadow
- Status chips: Analyzed (green), Processing (amber)
- 8 cards + 1 ghost card (dashed border, "Upload New" centered)

## States

- Document card: default / hover (gradient bar + border)
- Filter item: default / hover / active (left accent bar)
- File badge: PDF (red) / DOCX (cyan) / XLSX (green) variants
- Status chip: Analyzed / Processing / Pending
- Drop zone: idle / drag-over
- View toggle: grid active / list active
