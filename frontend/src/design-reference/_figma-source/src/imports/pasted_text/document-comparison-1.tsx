Create the Document Comparison page for Knowledge Hub. This view 
appears when the CLIPBOARD icon in the icon rail (Column 1) is 
clicked. Follows the same 3-column structure as all other pages.

Canvas: 1440×900px desktop frame.

---

OVERALL STRUCTURE (left to right)

| Column 1      | Column 2                  | Column 3              |
| Icon Rail     | Comparison Panel          | Main Area (blank)     |
| 60px fixed    | 360px fixed               | 1020px remaining      |

All columns full height. Borders act as dividers, no gap.

---

DESIGN TOKENS (same Knowledge Hub system)

bg-base: #0B1120 | bg-surface: #0F1829 | bg-elevated: #162033
bg-hover: #1C2840 | accent: #7C5CFC
accent-glow: rgba(124,92,252,0.15)
accent-gradient: linear #7C5CFC → #A78BFA → #60A5FA
text-primary: #F1F5F9 | text-secondary: #94A3B8 | text-faint: #475569
border-subtle: #1E2D45 | border-accent: rgba(124,92,252,0.4)
success: #34D399 | warning: #F59E0B | info: #22D3EE | danger: #F87171

Font: Inter Variable
Sizes: 11/12/13/14/15px | Weights: 400/500/600/700

---

COLUMN 1 — Icon Rail (60px, unchanged)

Clipboard icon is the ACTIVE state:
- Icon: clipboard or clipboard-list, 20px, color accent (#7C5CFC)
- Active bg: 36×36px rounded square, fill rgba(124,92,252,0.12),
  outer glow: 0 0 16px rgba(124,92,252,0.3)
All other icons: 20px, color text-secondary (#94A3B8)
Background: #080C14, full height

---

COLUMN 2 — Comparison Panel (360px, full height)

Background: bg-surface (#0F1829)
Right border: 1px solid border-subtle (#1E2D45)

Split into two fixed-height sections with independent scroll:
- TOP SECTION: Upload panel — 676px fixed height
- DIVIDER: 1px solid border-subtle (always visible at 676px)
- BOTTOM SECTION: History panel — 223px fixed height

===================================================
TOP SECTION — Upload Panel (676px fixed)
===================================================

Auto layout: vertical, align stretch, gap 0

A. Header (64px, fixed, not scrollable):
   Auto layout horizontal, align center, padding 0 20px, space-between
   - Left stack (auto layout vertical, gap 2px):
     "Compare Documents" 15px semibold text-primary
     "Upload two documents to compare" 11px text-faint
   - Icon button 28×28px, radius 8px:
     info-circle icon 14px text-secondary, hover bg bg-hover
   Bottom border: 1px solid border-subtle

B. Scrollable body (flex 1, overflow-y scroll):
   Padding: 20px
   Auto layout: vertical, gap 16px

   Scrollbar: 4px wide, thumb rgba(124,92,252,0.25),
   hover rgba(124,92,252,0.45), track transparent

   --- DOCUMENT 1 UPLOAD ---
   Section label row (auto layout horizontal, align center,
   gap 8px, margin-bottom 8px):
   - Numbered badge: 20×20px circle, bg accent (#7C5CFC),
     "1" 11px semibold white, radius 50%
   - "Document 1" 13px semibold text-primary
   - "(Required)" 11px text-faint, margin-left auto

   Drop zone frame (width 100%, height 130px):
   bg bg-elevated (#162033), radius 14px
   Border: 1.5px dashed rgba(100,116,139,0.4)
   Auto layout: vertical, align center, justify center,
   gap 6px, padding 16px

   Contents (idle state):
   - Upload icon container: 36×36px circle,
     bg rgba(124,92,252,0.10),
     upload-cloud icon 18px accent (#7C5CFC)
   - "Drag & drop or " 12px text-faint +
     "browse" 12px accent underlined — inline row
   - "PDF, DOCX, TXT up to 50MB" 11px text-faint, centered

   Hover/drag-over state:
   - Border: rgba(124,92,252,0.6)
   - Background tint: rgba(124,92,252,0.05)
   - Upload icon bg: rgba(124,92,252,0.18)

   File-attached state (alternative view of same drop zone):
   - Background: rgba(52,211,153,0.05)
   - Border: 1.5px solid rgba(52,211,153,0.35)
   - Auto layout horizontal, align center, gap 10px, padding 14px 16px
   - Left: file badge 36×36px radius 10px,
     PDF → bg rgba(248,113,113,0.12), icon #F87171
     DOCX → bg rgba(34,211,238,0.12), icon #22D3EE
   - Center stack (flex 1):
     "NDA_Template_2026.pdf" 13px medium text-primary, truncate
     "2.4 MB · PDF" 11px text-faint
   - Right: checkmark-circle 16px #34D399 + 
     x-circle 14px text-faint (remove), gap 8px

   --- SWAP BUTTON (between the two upload zones) ---
   Auto layout horizontal, align center, justify center, 
   padding 4px 0, gap 8px

   - Thin line: flex 1, height 1px, bg border-subtle
   - Swap button: height 28px, padding 0 12px, radius 20px,
     bg bg-elevated, border 1px solid border-subtle
     Auto layout horizontal, gap 6px, align center:
     arrows-swap icon 12px text-faint
     "Swap" 11px text-secondary
     hover: border border-accent, icon color accent,
            text text-primary
   - Thin line: flex 1, height 1px, bg border-subtle

   --- DOCUMENT 2 UPLOAD ---
   Section label row (same structure as Document 1):
   - Numbered badge: 20×20px circle, bg #334155 (gray, unfilled state),
     "2" 11px semibold text-secondary
     Active/filled state: bg accent, "2" white (matches Doc 1 badge)
   - "Document 2" 13px semibold text-primary
   - "(Required)" 11px text-faint, margin-left auto

   Drop zone (identical dimensions and states to Document 1)
   Idle state border: rgba(100,116,139,0.3) — slightly more muted
   than Document 1 to suggest sequential flow

   --- COMPARISON OPTIONS ---
   Section label: "Comparison Focus (Optional)"
   13px medium text-primary, margin-top 4px

   3 option chips (auto layout horizontal, gap 8px, flex-wrap):
   Each chip: height 30px, padding 0 12px, radius 20px, 
   12px medium, border 1px solid border-subtle, 
   bg bg-elevated

   Active chip: bg rgba(124,92,252,0.12), 
                border border-accent, 
                text accent (#7C5CFC)
   Default chip: text text-secondary, hover border-accent

   Chips:
   - "Full Document" (active by default)
   - "Key Clauses Only"
   - "Risk Differences"

   Bottom fade overlay (40px, gradient transparent → bg-surface)
   at the bottom of scroll area

C. Sticky Generate Button (56px, fixed, not scrollable):
   Padding: 0 20px, margin: 8px 0 12px
   Separator: 1px gradient line above (transparent → border-subtle → transparent)

   Button: full width, height 44px, radius 12px
   Default state (both docs uploaded):
   - bg accent (#7C5CFC), 14px semibold white
   - Label: "Generate Comparison"
   - Left icon: git-compare or arrows-left-right 16px white
   - hover: bg #8B6EFD, shadow 0 4px 20px rgba(124,92,252,0.4)

   Disabled state (one or both docs missing):
   - bg bg-elevated (#162033)
   - border 1px solid border-subtle
   - Label: "Upload Both Documents First"
   - 14px text-faint, no icon glow
   - cursor: not-allowed

===================================================
DIVIDER (1px, always at 676px — never moves)
===================================================
Full-width horizontal line, fill border-subtle (#1E2D45)

===================================================
BOTTOM SECTION — Comparison History (223px fixed)
===================================================

Background: bg-surface (#0F1829)
Auto layout: vertical, align stretch, gap 0

A. Sub-header (40px, fixed, not scrollable):
   Auto layout horizontal, align center, padding 0 16px, space-between
   Bottom border: 1px solid border-subtle

   Left group (auto layout horizontal, gap 6px, align center):
   - History icon: 14px text-faint
   - "Recent Comparisons" 12px semibold text-secondary

   Right: "View all →" 11px text-faint, hover text-secondary

B. Scrollable history list (flex 1 = 183px, overflow-y scroll):
   Auto layout: vertical, gap 0
   Scrollbar: same 4px style as form section

   Each history row (44px height):
   Auto layout horizontal, align center, gap 10px, 
   padding 0 16px, hover bg bg-hover, cursor pointer

   Row structure:
   - LEFT: Comparison badge (30×30px, radius 8px, flex-shrink 0):
     Two overlapping mini file icons (offset by 4px),
     bg rgba(124,92,252,0.12), icon color accent (#7C5CFC)
     This badge is the same for all comparison rows

   - CENTER (flex 1, min-width 0, auto layout vertical, gap 2px):
     Title: 12px medium text-primary, truncate ellipsis
     Format: "Doc A vs Doc B" (abbreviated filenames)
     Meta row (auto layout horizontal, gap 5px, align center):
       Focus chip: 10px text-faint, bg bg-elevated, 
                   padding 1px 6px, radius 4px
                   "Full" / "Clauses" / "Risk"
       Dot: 3px circle fill text-faint
       Timestamp: 10px text-faint

   - RIGHT (flex-shrink 0):
     Status icon 14px:
     Done    → checkmark-circle, color #34D399
     Running → loader/spinner, color #F59E0B (animated)
     Failed  → x-circle, color #F87171
     On hover: replaced by chevron-right 14px text-faint

   History rows (6 rows, last 2 require scroll):
   1. "NDA_2026 vs NDA_2025"           · Full    · 1h ago     · Done ✓
   2. "Contract_A vs Contract_B"       · Clauses · 3h ago     · Done ✓
   3. "Compliance_Q1 vs Compliance_Q4" · Risk    · Yesterday  · Done ✓
   4. "Service_Agr vs Sales_Agr"       · Full    · 2d ago     · Done ✓
   5. "License_v1 vs License_v2"       · Clauses · 3d ago     · Failed ✗
   6. "NDA_Draft vs NDA_Final"         · Risk    · 4d ago     · Done ✓

   Empty state (when no history):
   Height: full, auto layout vertical, align center,
   justify center, gap 6px, padding 16px
   - Comparison icon 20px, text-faint, opacity 0.35
   - "No comparisons yet" 12px text-faint, centered
   - "Your comparison history appears here"
     11px text-faint, centered, opacity 0.7

---

COLUMN 3 — Main Area (1020px, blank/empty state)

Background: #0B1120 + mesh gradient:
- Radial rgba(76,29,149,0.06) top-right corner, 600px radius
- Radial rgba(10,31,61,0.3) bottom-left corner, 500px radius

Content: centered both axes, auto layout vertical,
align center, gap 16px

Empty state:
- Outer ring: 96×96px circle,
  bg rgba(124,92,252,0.06),
  border 1px solid rgba(124,92,252,0.12)
- Inner container: 72×72px circle,
  bg rgba(124,92,252,0.10),
  border 1px solid rgba(124,92,252,0.18)
- Icon: git-compare or arrows-left-right, 32px,
  color rgba(124,92,252,0.5)

- "No comparison yet" 18px semibold text-secondary,
  text-align center, margin-top 8px
- "Upload two documents in the panel on the left"
  14px text-faint, text-align center, max-width 340px,
  line-height 1.6
- "then click Generate Comparison to see results"
  14px text-faint, text-align center, max-width 340px

Optional hint chips row (auto layout horizontal, gap 8px,
justify center, margin-top 8px):
3 small chips showing what the comparison returns:
Each: height 26px, padding 0 10px, radius 20px,
      bg bg-elevated, border 1px solid border-subtle,
      11px text-faint, auto layout horizontal, gap 5px

Chips:
- dot #34D399 + "Matching clauses"
- dot #F87171 + "Differences"
- dot #F59E0B + "Risk flags"

---

COMPONENT STATES TO GENERATE

Upload zones:
- Idle (dashed border)
- Hover/drag-over (glowing border + bg tint)
- File attached (file chip with remove option)

Document badges:
- Numbered badge: unfilled (gray) / filled (accent)

Comparison option chips:
- Default / active / hover

Generate button:
- Disabled (one/both docs missing)
- Default/enabled (both docs uploaded)
- Hover

History rows:
- Default / hover (chevron appears)
- Done / Running / Failed status variants

History section:
- Populated (6 rows, scrollable)
- Empty state

SPACING: 4px base unit
RADIUS SCALE: 8 / 10 / 12 / 14 / 16 / 20px
SCROLLBAR: 4px, thumb rgba(124,92,252,0.25),
           hover rgba(124,92,252,0.45), track transparent