Revise Column 2 of the Knowledge Hub Document Creation page.

The column is split into two FIXED-HEIGHT sections, each with 
its own independent vertical scroll. The divider between them 
is always visible regardless of content length. Neither section 
ever collapses or pushes the other out of view.

Column 2 total: 360px wide, 900px full height.
Split ratio: 675px top (form) + 1px divider + 224px bottom (history)

---

SECTION 1 — CREATE DOCUMENT FORM (top, 675px fixed height)

This section is a fixed-height scroll container.
The form content scrolls WITHIN this 675px area only.
The section itself never grows or shrinks.

Structure (auto layout vertical, align stretch):

A. Header (64px, fixed, NOT part of scroll):
   Auto layout horizontal, align center, padding 0 20px, space-between
   - Left stack (auto layout vertical, gap 2px):
     "Create Document" 15px semibold text-primary (#F1F5F9)
     "Fill in details to generate" 11px text-faint (#475569)
   - Close icon button: 28×28px, radius 8px,
     X icon 14px text-secondary, hover bg bg-hover
   Bottom border: 1px solid border-subtle (#1E2D45)

B. Scrollable form body (flex 1, overflow-y scroll):
   All existing form field content scrolls here.
   Padding: 20px all sides
   Auto layout: vertical, gap 16px

   Scrollbar style:
   - Width: 4px
   - Track: transparent
   - Thumb: rgba(124,92,252,0.25), radius 4px
   - Hover thumb: rgba(124,92,252,0.45)

   Bottom fade overlay (NOT part of scroll, sits above it):
   - Height 40px, width 100%
   - Gradient fill: transparent → bg-surface (#0F1829)
   - Positioned at the very bottom of scroll area
   - Indicates more content below

C. Sticky Generate Button (56px, fixed, NOT part of scroll):
   Always visible at the bottom of Section 1.
   Padding: 0 20px, margin-bottom 12px, margin-top 8px
   Button: full width, height 44px, bg accent (#7C5CFC),
   radius 12px, 14px semibold white
   Hover: bg #8B6EFD, shadow 0 4px 20px rgba(124,92,252,0.4)
   Label varies by form type:
   Generic/Sales/Service → "Generate Draft"
   NDA → "Generate NDA"

   Thin separator above button:
   1px line, gradient transparent → border-subtle → transparent

---

COLUMN DIVIDER (1px, always visible)

Full-width horizontal line, fill border-subtle (#1E2D45)
This line is ALWAYS in the same vertical position (675px from top)
regardless of scroll state in either section above or below.

---

SECTION 2 — DOCUMENT HISTORY (bottom, 224px fixed height)

This section is also a fixed-height scroll container.
History rows scroll WITHIN this 224px area only.
The section header stays fixed — only the list rows scroll.

Background: bg-surface (#0F1829)
Auto layout: vertical, align stretch, gap 0

A. Sub-header (40px, fixed, NOT part of scroll):
   Auto layout horizontal, align center, padding 0 16px, space-between
   Bottom border: 1px solid border-subtle (#1E2D45)

   Left group (auto layout horizontal, gap 6px, align center):
   - History/clock icon: 14px text-faint (#475569)
   - "Recent Documents" 12px semibold text-secondary (#94A3B8)

   Right:
   - "View all →" 11px text-faint (#475569)
     hover: text-secondary, no background

B. Scrollable history list (flex 1, overflow-y scroll):
   Auto layout: vertical, gap 0
   Shows as many rows as fit, rest scroll into view

   Scrollbar style: same as form section above

   Each history row (44px height, full width):
   Auto layout horizontal, align center, gap 10px, padding 0 16px
   Hover: bg bg-hover (#1C2840)
   Cursor: pointer

   Row structure:
   - LEFT: File type badge (30×30px, radius 8px, flex-shrink 0):
     PDF  → bg rgba(248,113,113,0.12), file icon 13px #F87171
     DOCX → bg rgba(34,211,238,0.12),  file icon 13px #22D3EE
     XLSX → bg rgba(52,211,153,0.12),  file icon 13px #34D399

   - CENTER (flex 1, min-width 0, auto layout vertical, gap 2px):
     Name: 12px medium text-primary, truncate ellipsis,
           white-space nowrap, overflow hidden
     Meta row (auto layout horizontal, gap 5px, align center):
       Type chip: 10px text-faint, bg bg-elevated (#162033),
                  padding 1px 6px, radius 4px
                  e.g. "NDA" / "Generic" / "Sales" / "Service"
       Dot: 3×3px circle, fill text-faint (#475569)
       Timestamp: 10px text-faint — "Just now" / "2h ago" / "Yesterday" / "2d ago"

   - RIGHT (flex-shrink 0):
     Status icon 14px:
     Done     → checkmark-circle, color #34D399
     Draft    → pencil-line, color #94A3B8
     Failed   → x-circle, color #F87171
     On hover: status icon replaced by 
               chevron-right 14px text-faint (#475569)

   History rows (show 6+ for scrollability):
   1.  "NDA_Kerahasiaan_PT_Marina.pdf"   · PDF  · NDA     · Just now  · Done ✓
   2.  "Kontrak_Distribusi_Q1.docx"      · DOCX · Sales   · 2h ago    · Done ✓
   3.  "Service_Agreement_Draft.docx"    · DOCX · Service · Yesterday · Draft ✎
   4.  "Generic_Compliance_Report.pdf"   · PDF  · Generic · 2d ago    · Done ✓
   5.  "NDA_Proyek_Ekspansi.docx"        · DOCX · NDA     · 3d ago    · Done ✓
   6.  "Sales_Contract_Retail.pdf"       · PDF  · Sales   · 4d ago    · Failed ✗
   7.  "Perjanjian_Lisensi_SW.docx"      · DOCX · Generic · 5d ago    · Done ✓
   (rows 5–7 require scroll to reach)

   Empty state (when no history):
   Height: full, auto layout vertical, align center, 
   justify center, gap 6px, padding 16px
   - Clock icon 20px, text-faint, opacity 0.35
   - "No documents yet" 12px text-faint, centered
   - "Generated documents appear here" 11px text-faint, 
     centered, opacity 0.7

---

FINAL COLUMN 2 HEIGHT BREAKDOWN

┌──────────────────────────────────┐ ─ 0px
│  Header (fixed)          64px   │
├─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─│
│  ↕ Form scroll area      551px  │
│    (64 + 551 + 60 = 675)        │
│  ░░░ fade overlay               │
├─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─│
│  Sticky generate btn     60px   │
├══════════════════════════════════╡ ─ 675px (always at this position)
│  Sub-header (fixed)      40px   │
├─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─│
│  ↕ History scroll area   184px  │ ─ 716px
│    (7 rows × 44px = 308px       │
│     scrollable within 184px)    │
└──────────────────────────────────┘ ─ 900px

---

COMPONENT STATES

Form section:
- Scrolled to top (fade overlay visible at bottom)
- Scrolled to bottom (fade overlay hidden, generate button 
  always visible regardless of scroll position)

History section:
- Populated + scrollable (6–7 rows, bottom rows require scroll)
- Empty state (clock icon + messages)
- Row hover (chevron appears, bg highlight)
- Row: Done / Draft / Failed status variants

SPACING: 4px base unit
SCROLLBAR: 4px wide, thumb rgba(124,92,252,0.25),
           hover rgba(124,92,252,0.45), track transparent