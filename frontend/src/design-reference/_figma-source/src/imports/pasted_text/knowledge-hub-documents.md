Create the Documents page for Knowledge Hub. When the document icon 
in the icon rail is active, the Chat History sidebar is fully replaced 
by the document layout. The total layout is: icon rail + 3 columns.

Canvas: 1440×900px desktop frame.

---

OVERALL STRUCTURE (left to right)

| Icon Rail | Column 2: Upload + Filter | Column 3: Main Document Area |
|  60px     |          300px            |        1080px (remaining)    |

All columns: full height, auto layout vertical, align stretch.
No gap between columns — use right borders as dividers.

---

DESIGN TOKENS

bg-base: #0B1120 | bg-surface: #0F1829 | bg-elevated: #162033
bg-hover: #1C2840 | accent: #7C5CFC
accent-glow: rgba(124,92,252,0.15)
accent-gradient: linear #7C5CFC → #A78BFA → #60A5FA
text-primary: #F1F5F9 | text-secondary: #94A3B8 | text-faint: #475569
border-subtle: #1E2D45 | border-accent: rgba(124,92,252,0.4)
success: #34D399 | warning: #F59E0B | info: #22D3EE | danger: #F87171

Font: Inter Variable
Sizes: 11/12/13/14/15/20px | Weights: 400/500/600/700

---

ICON RAIL (60px, unchanged)

Same as Knowledge Hub shell. Document icon is the active state:
- Icon: file-text or document icon, 20px, color accent (#7C5CFC)
- Active bg: 36×36px rounded square, fill rgba(124,92,252,0.12),
  outer glow: 0 0 16px rgba(124,92,252,0.3)
All other icons: 20px, color text-secondary (#94A3B8)
Background: bg-deep (#080C14), full height
Right border: none (Column 2 handles its own left edge)

---

COLUMN 2 — Upload + Filter Panel (300px)

Background: bg-surface (#0F1829)
Right border: 1px solid border-subtle (#1E2D45)
Auto layout: vertical, align stretch, gap 0
Divided into two stacked sections: Upload (top) + Filter (bottom)
Add a 1px solid border-subtle divider between the two sections.

=== SECTION 1: UPLOAD (top portion) ===

Header (64px, auto layout horizontal, align center,
padding 0 20px, space-between):
- "Documents" 15px semibold text-primary
- Clock/history icon button 28×28px, radius 8px, 
  icon text-secondary, hover bg bg-hover

Drop Zone (margin 12px 16px):
Frame: fill bg-elevated (#162033), radius 16px
Border: 2px dashed rgba(124,92,252,0.35)
Inner glow: radial gradient rgba(124,92,252,0.06) center → transparent
Auto layout: vertical, align center, justify center, gap 8px, padding 20px

  Contents:
  - Upload icon container: 40×40px circle, 
    bg rgba(124,92,252,0.10), upload-cloud icon 22px accent
  - "Drag & drop files here" 13px semibold text-primary, centered
  - "PDF, DOCX, XLSX up to 50MB" 11px text-faint, centered
  - Divider: thin line + "or" + thin line, 11px text-faint, full width
  - "Browse Files" button: 130×34px, bg accent, radius 10px,
    13px semibold white
    hover: bg #8B6EFD, shadow 0 4px 16px rgba(124,92,252,0.4)

  Drag-over state:
  - Border: rgba(124,92,252,0.7)
  - Fill tint: rgba(124,92,252,0.05)

Section label "RECENT UPLOADS" (padding 8px 20px 4px):
11px uppercase semibold text-faint, letter-spacing 0.08em

Recent Uploads List (auto layout vertical, gap 0):
3 rows (condensed to fit), each 52px height
Auto layout horizontal, align center, gap 10px, padding 0 16px
Hover: bg bg-hover

Each row:
- File badge 30×30px, radius 8px:
  PDF → bg rgba(248,113,113,0.12), icon #F87171
  DOCX → bg rgba(34,211,238,0.12), icon #22D3EE
- Text stack (flex 1, auto layout vertical, gap 2px):
  Name: 12px medium text-primary, truncate, max-width 170px
  Meta: 11px text-faint (size · time)
- Status dot 8px:
  Green #34D399 = uploaded | Amber #F59E0B = processing

Rows:
1. "NDA_Template_2026.pdf" · 2.4 MB · Just now · green
2. "PT_Marina_Contract.docx" · 845 KB · 2h ago · green
3. "Payment_Terms_Draft.docx" · 1.2 MB · 2d ago · amber

Storage Quota (auto layout vertical, gap 6px, padding 12px 16px 16px):
- Row: "Storage used" 12px text-secondary | 
  "2.4 GB / 10 GB" 12px semibold text-primary, space-between
- Progress bar: full width, height 4px, bg bg-hover, radius 2px
  Filled 24%, gradient accent-gradient, radius 2px

=== DIVIDER ===
1px horizontal line, full width, fill border-subtle (#1E2D45)

=== SECTION 2: FILTER (bottom portion, fills remaining height) ===

Header (52px, auto layout horizontal, align center,
padding 0 20px, space-between):
- "Filter" 15px semibold text-primary
- "Reset" 12px text-secondary, hover text-primary

Search (padding 0 12px 10px):
Height 32px, bg bg-elevated, radius 10px,
border 1px solid border-subtle
Magnifier 14px text-faint + "Search types..." 12px text-faint
Auto layout horizontal, gap 8px, padding 0 10px

Label "DOCUMENT TYPE" (padding 6px 20px 4px):
11px uppercase semibold text-faint, letter-spacing 0.08em

Type Filter List (auto layout vertical, gap 2px, padding 6px):
8 items, each 36px, radius 10px
Auto layout horizontal, align center, gap 8px, padding 0 12px

Active — "All Documents":
- bg rgba(124,92,252,0.12)
- Left accent bar: 3×20px, bg accent, radius 2px
- Label: 13px semibold accent
- Count pill: bg rgba(124,92,252,0.2), 11px accent,
  padding 2px 8px, radius 20px → "47"

Default items:
- Hover: bg bg-hover | left bar hidden
- Label: 13px medium text-secondary
- Count pill: bg bg-elevated, 11px text-faint, padding 2px 8px, radius 20px

Items:
1. ✓ All Documents · grid icon · 47 (ACTIVE)
2. NDA · shield icon · 12
3. Kontrak · file-signature · 9
4. Kepatuhan · check-badge · 8
5. Laporan · chart-bar · 7
6. Perjanjian · handshake · 6
7. Invoice · receipt · 3
8. Lainnya · folder · 2

Icons: 16px, color matches label state

Label "STATUS" (padding 12px 20px 4px):
Same label style

Status Checkboxes (auto layout vertical, gap 2px, padding 6px 16px):
3 rows, 32px each, auto layout horizontal, gap 10px, align center

Checkbox 16×16px, radius 4px:
- Checked: bg accent, white checkmark 10px
- Unchecked: border 1.5px text-faint, transparent

1. ✓ Analyzed · #34D399 dot 8px · "38" text-faint
2. ✓ Processing · #F59E0B dot 8px · "6" text-faint
3. □ Pending · #475569 dot 8px · "3" text-faint

---

COLUMN 3 — Main Document Area (1080px, remaining width)

Background: #0B1120 + subtle mesh gradient
(radial rgba(76,29,149,0.06) from top-right corner)
Auto layout: vertical, align stretch, gap 0

Top Bar (64px, auto layout horizontal, align center,
padding 0 24px, gap 12px,
border-bottom 1px solid border-subtle):

Left (auto layout horizontal, gap 8px, flex 1):
- "All Documents" 20px semibold text-primary
- "47 documents" 13px text-faint, align center

Right (auto layout horizontal, gap 8px):
- Search: 240×36px, bg bg-elevated, radius 10px,
  border border-subtle
  magnifier 14px + "Search documents..." 13px text-faint
  focus: border-accent + shadow 0 0 0 3px accent-glow
- Sort dropdown: 36px height, padding 0 12px, bg bg-elevated,
  border border-subtle, radius 10px
  "Modified date" 13px text-secondary + chevron-down
- View toggle (grouped pair, 36px each):
  Grid icon — active: bg rgba(124,92,252,0.15), icon accent
  List icon — default: transparent, icon text-faint
- "New Document": 36px height, padding 0 16px,
  bg accent, radius 10px, 13px semibold white, plus icon left
  hover: bg #8B6EFD, shadow 0 4px 16px rgba(124,92,252,0.3)

Document Grid (padding 20px 24px, auto layout vertical, gap 16px):
3-column grid, gap 16px

DOCUMENT CARD (width ≈ 336px, height 180px):
bg bg-elevated (#162033), radius 16px,
border 1px solid border-subtle, overflow hidden
Auto layout: vertical, padding 16px, gap 12px

Hover state:
- Top accent bar: 3px × full width, gradient accent-gradient,
  at very top of card
- Border: border-accent rgba(124,92,252,0.4)
- Shadow: 0 8px 32px rgba(0,0,0,0.3)

Top row (auto layout horizontal, align center, space-between):
- File type badge (height 26px, padding 0 10px, radius 20px,
  auto layout horizontal, gap 6px):
  PDF → bg rgba(248,113,113,0.12), icon + "PDF" 11px semibold #F87171
  DOCX → bg rgba(34,211,238,0.12), icon + "DOCX" 11px #22D3EE
- Options ··· 28×28px, radius 8px, hover bg bg-hover

Middle (auto layout vertical, gap 6px, flex 1):
- Title: 14px semibold text-primary, max 2 lines, line-height 1.4
- Category: 11px text-faint
- Preview: 12px text-faint, max 2 lines, line-height 1.5, truncated

Bottom row (auto layout horizontal, align center, space-between,
padding-top 8px, border-top 1px solid border-subtle):
- Avatar stack: 2 circles 20×20px, overlap -6px, gradient fills
- "Modified Xh ago" 11px text-faint
- Status chip (22px height, padding 0 8px, radius 20px):
  Analyzed: bg rgba(52,211,153,0.1), border rgba(52,211,153,0.3),
             "Analyzed" 10px semibold #34D399
  Processing: bg rgba(245,158,11,0.1), border rgba(245,158,11,0.3),
              "Processing" 10px semibold #F59E0B

8 cards across 3 rows + 1 ghost card:

Row 1:
- "NDA Kerahasiaan — PT Marina Group 2026" · PDF · NDA · Analyzed
- "Kontrak Kerjasama Distribusi Q1" · DOCX · Kontrak · Analyzed
- "Laporan Kepatuhan Regulasi OJK" · PDF · Kepatuhan · Analyzed

Row 2:
- "Perjanjian Lisensi Software Enterprise" · PDF · Perjanjian · Analyzed
- "Invoice Jasa Konsultasi — Maret 2026" · PDF · Invoice · Processing
- "Addendum Kontrak Sewa Gedung" · DOCX · Kontrak · Analyzed

Row 3:
- "Draft NDA — Proyek Ekspansi Regional" · DOCX · NDA · Processing
- "Compliance Checklist Q1 2026" · DOCX · Kepatuhan · Analyzed
- Ghost card: transparent bg, 2px dashed border-subtle, radius 16px
  Centered: plus icon 24px text-faint + "Upload New" 13px text-faint

---

COMPONENT STATES

- Document card: default / hover (gradient top bar visible)
- Filter item: default / hover / active (left accent bar)
- File badge: PDF / DOCX / XLSX color variants
- Status chip: Analyzed / Processing / Pending
- Drop zone: idle / drag-over
- View toggle: grid active / list active

SPACING: 4px base unit
RADIUS SCALE: 8 / 10 / 12 / 16 / 20px