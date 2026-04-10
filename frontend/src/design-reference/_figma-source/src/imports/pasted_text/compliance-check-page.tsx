Create the Compliance Check page for Knowledge Hub. This view 
appears when the SHIELD-CHECK icon in the icon rail (Column 1) 
is clicked. Follows the same 3-column structure as all other pages.

Canvas: 1440×900px desktop frame.

---

OVERALL STRUCTURE (left to right)

| Column 1      | Column 2                  | Column 3              |
| Icon Rail     | Compliance Panel          | Main Area (blank)     |
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

Shield-check icon is the ACTIVE state:
- Icon: shield-check, 20px, color accent (#7C5CFC)
- Active bg: 36×36px rounded square, fill rgba(124,92,252,0.12),
  outer glow: 0 0 16px rgba(124,92,252,0.3)
All other icons: 20px, color text-secondary (#94A3B8)
Background: #080C14, full height

---

COLUMN 2 — Compliance Panel (360px, full height)

Background: bg-surface (#0F1829)
Right border: 1px solid border-subtle (#1E2D45)

Split into two fixed-height sections with independent scroll:
- TOP SECTION: Upload panel — 676px fixed height
- DIVIDER: 1px solid border-subtle (always at 676px, never moves)
- BOTTOM SECTION: History panel — 223px fixed height

===================================================
TOP SECTION — Upload Panel (676px fixed)
===================================================

Auto layout: vertical, align stretch, gap 0

A. Header (64px, fixed, not scrollable):
   Auto layout horizontal, align center, padding 0 20px, space-between
   - Left stack (auto layout vertical, gap 2px):
     "Compliance Check" 15px semibold text-primary
     "Upload a document to check compliance" 11px text-faint
   - Info icon button: 28×28px, radius 8px,
     info-circle 14px text-secondary, hover bg bg-hover
   Bottom border: 1px solid border-subtle (#1E2D45)

B. Scrollable body (flex 1, overflow-y scroll):
   Padding: 20px
   Auto layout: vertical, gap 20px

   Scrollbar: 4px wide, thumb rgba(124,92,252,0.25),
   hover rgba(124,92,252,0.45), track transparent

   --- DOCUMENT UPLOAD AREA ---

   Section label row (auto layout horizontal, align center,
   gap 8px, margin-bottom 8px):
   - Shield icon: 16×16px, color accent (#7C5CFC)
   - "Document to Check" 13px semibold text-primary
   - "(Required)" 11px text-faint, margin-left auto

   Drop zone (width 100%, height 160px):
   bg bg-elevated (#162033), radius 14px
   Border: 1.5px dashed rgba(100,116,139,0.4)
   Auto layout: vertical, align center, justify center,
   gap 8px, padding 20px

   Contents (idle state):
   - Icon container: 44×44px circle,
     bg rgba(124,92,252,0.10),
     border 1px solid rgba(124,92,252,0.15),
     shield-check icon 22px accent (#7C5CFC)
   - "Drag & drop your document here" 13px semibold text-primary,
     text-align center
   - "or " 12px text-faint + "browse files" 12px accent underlined,
     inline auto layout horizontal, justify center
   - "PDF, DOCX, TXT up to 50MB" 11px text-faint, centered

   Hover/drag-over state:
   - Border: rgba(124,92,252,0.6)
   - Background tint: rgba(124,92,252,0.05)
   - Icon container bg: rgba(124,92,252,0.18)
   - Drop shadow: 0 0 24px rgba(124,92,252,0.12)

   File-attached state (replaces idle state):
   Height: 80px (collapses once file is attached)
   bg rgba(52,211,153,0.05), radius 14px
   Border: 1.5px solid rgba(52,211,153,0.35)
   Auto layout: horizontal, align center,
   gap 12px, padding 0 16px

   - Left: file type badge 40×40px, radius 10px:
     PDF  → bg rgba(248,113,113,0.12), file icon 18px #F87171
     DOCX → bg rgba(34,211,238,0.12), file icon 18px #22D3EE
     TXT  → bg rgba(148,163,184,0.12), file icon 18px #94A3B8
   - Center stack (flex 1, auto layout vertical, gap 3px):
     Filename: 13px medium text-primary, truncate ellipsis
     Meta: "2.4 MB · PDF · Ready for check" 11px text-faint
   - Right group (auto layout horizontal, gap 8px, align center):
     checkmark-circle 16px #34D399
     x-circle 14px text-faint (remove button),
     hover color danger (#F87171)

   --- COMPLIANCE FRAMEWORK ---

   Section label: "Compliance Framework" 13px medium text-primary

   Dropdown (full width, height 40px):
   bg bg-elevated, border 1px solid border-subtle, radius 10px
   padding 0 14px, auto layout horizontal, 
   align center, space-between
   - Selected: "Indonesian Law (OJK / UU PT)" 13px text-primary
   - Chevron-down icon 14px text-faint
   - Focus: border border-accent, shadow 0 0 0 3px accent-glow
   - Hover: border rgba(124,92,252,0.25)

   Dropdown options (show as list below when open):
   Each option 36px, padding 0 14px, 13px text-primary
   Hover: bg bg-hover
   Options:
   - "Indonesian Law (OJK / UU PT)" (selected)
   - "International Contract Standards"
   - "GDPR / Data Privacy"
   - "Custom Framework"

   --- CHECK SCOPE ---

   Section label: "Check Scope" 13px medium text-primary

   4 scope toggle chips (auto layout horizontal, gap 8px,
   flex-wrap, width 100%):
   Each: height 30px, padding 0 12px, radius 20px,
   12px medium, border 1px solid border-subtle,
   bg bg-elevated

   Active chip: bg rgba(124,92,252,0.12),
                border border-accent,
                text accent (#7C5CFC)
   Default chip: text text-secondary
   Hover: border rgba(124,92,252,0.3), text text-primary

   Chips (all active by default):
   - "Legal Clauses" (active)
   - "Risk Flags" (active)
   - "Missing Terms" (active)
   - "Regulatory" (active)

   --- ADDITIONAL NOTES (OPTIONAL) ---

   Section label: "Additional Context (Optional)"
   13px medium text-primary

   Textarea: min-height 80px, width 100%
   bg bg-elevated, border 1px solid border-subtle,
   radius 10px, padding 12px 14px
   Placeholder: "e.g., Focus on payment clauses and 
   termination conditions..." 12px text-faint
   Focus: border border-accent,
          shadow 0 0 0 3px rgba(124,92,252,0.12)

   Bottom fade overlay:
   40px height, gradient transparent → bg-surface,
   at bottom of scroll area

C. Sticky Button Area (56px, fixed, not scrollable):
   Padding: 0 20px, margin: 8px 0 12px
   Thin separator line above: gradient transparent → 
   border-subtle → transparent

   Disabled state (no document uploaded):
   - Full width, height 44px, radius 12px
   - bg bg-elevated (#162033)
   - Border: 1px solid border-subtle
   - Left icon: shield 16px text-faint
   - Label: "Upload a Document First" 14px text-faint
   - cursor: not-allowed

   Enabled state (document uploaded):
   - bg accent (#7C5CFC), radius 12px
   - Left icon: shield-check 16px white
   - Label: "Run Compliance Check" 14px semibold white
   - hover: bg #8B6EFD, shadow 0 4px 20px rgba(124,92,252,0.4)
   - active/press: bg #6D4FE0

===================================================
DIVIDER (1px, always at 676px — never moves)
===================================================
Full-width horizontal line, fill border-subtle (#1E2D45)

===================================================
BOTTOM SECTION — Compliance History (223px fixed)
===================================================

Background: bg-surface (#0F1829)
Auto layout: vertical, align stretch, gap 0

A. Sub-header (40px, fixed, not scrollable):
   Auto layout horizontal, align center, padding 0 16px, space-between
   Bottom border: 1px solid border-subtle

   Left group (auto layout horizontal, gap 6px, align center):
   - Clock/history icon: 14px text-faint
   - "Recent Checks" 12px semibold text-secondary

   Right: "View all →" 11px text-faint, hover text-secondary

B. Scrollable history list (flex 1 = 183px, overflow-y scroll):
   Auto layout: vertical, gap 0
   Scrollbar: 4px, same style as top section

   Each history row (44px height):
   Auto layout horizontal, align center, gap 10px,
   padding 0 16px, hover bg bg-hover, cursor pointer

   Row structure:
   - LEFT: Compliance badge (30×30px, radius 8px, flex-shrink 0):
     Pass   → bg rgba(52,211,153,0.12), shield-check 14px #34D399
     Fail   → bg rgba(248,113,113,0.12), shield-x 14px #F87171
     Review → bg rgba(245,158,11,0.12), shield-alert 14px #F59E0B

   - CENTER (flex 1, min-width 0, auto layout vertical, gap 2px):
     Document name: 12px medium text-primary,
     truncate ellipsis, white-space nowrap, overflow hidden
     Meta row (auto layout horizontal, gap 5px, align center):
       Framework chip: 10px text-faint, bg bg-elevated,
                       padding 1px 6px, radius 4px
                       e.g. "OJK" / "GDPR" / "Intl"
       Dot: 3px circle fill text-faint
       Timestamp: 10px text-faint

   - RIGHT (flex-shrink 0):
     Result label 10px semibold:
     Pass   → "Passed" color #34D399
     Fail   → "Failed" color #F87171
     Review → "Review" color #F59E0B
     On hover: replaced by chevron-right 14px text-faint

   History rows (6 rows, last 2 require scroll):
   1. "NDA_Kerahasiaan_PT_Marina.pdf"   · OJK   · 1h ago    · Passed ✓
   2. "Kontrak_Distribusi_Q1.docx"      · OJK   · 3h ago    · Review ⚠
   3. "Compliance_Report_Q1.pdf"        · Intl  · Yesterday · Passed ✓
   4. "Service_Agreement_Draft.docx"    · GDPR  · 2d ago    · Failed ✗
   5. "License_Agreement_v2.pdf"        · OJK   · 3d ago    · Passed ✓
   6. "Payment_Terms_Draft.docx"        · Intl  · 4d ago    · Review ⚠

   Empty state (no history yet):
   Full height, auto layout vertical, align center,
   justify center, gap 6px, padding 16px
   - Shield icon 20px, text-faint, opacity 0.35
   - "No checks yet" 12px text-faint, centered
   - "Your compliance history appears here"
     11px text-faint, centered, opacity 0.7

---

COLUMN 3 — Main Area (1020px, blank/empty state)

Background: #0B1120 + mesh gradient:
- Radial rgba(76,29,149,0.06) top-right, 600px radius
- Radial rgba(10,31,61,0.3) bottom-left, 500px radius

Content: centered both axes, auto layout vertical,
align center, gap 16px

Empty state:
- Outer ring: 96×96px circle,
  bg rgba(124,92,252,0.06),
  border 1px solid rgba(124,92,252,0.12)
- Inner container: 72×72px circle,
  bg rgba(124,92,252,0.10),
  border 1px solid rgba(124,92,252,0.18)
- Icon: shield-check 32px, color rgba(124,92,252,0.5)

- "No compliance check yet" 18px semibold text-secondary,
  text-align center, margin-top 8px
- "Upload a document and run a compliance check"
  14px text-faint, text-align center,
  max-width 340px, line-height 1.6
- "to see detailed results here"
  14px text-faint, text-align center

Hint chips row (auto layout horizontal, gap 8px,
justify center, margin-top 8px):
3 chips, height 26px, padding 0 10px, radius 20px,
bg bg-elevated, border 1px solid border-subtle,
11px text-faint, auto layout horizontal, gap 5px

Chips:
- dot #34D399 + "Passed clauses"
- dot #F87171 + "Failed checks"
- dot #F59E0B + "Needs review"

---

COMPONENT STATES TO GENERATE

Upload zone:
- Idle (dashed border, shield icon)
- Hover/drag-over (purple glow, darker icon bg)
- File attached (green border, file chip with remove)

Compliance framework dropdown:
- Closed / open / option selected

Check scope chips:
- All active (default) / individual deactivated / hover

Run button:
- Disabled (no doc)
- Enabled (doc uploaded)
- Hover

History badge variants:
- Pass (green shield-check)
- Fail (red shield-x)
- Review (amber shield-alert)

History rows:
- Default / hover (chevron appears)
- Pass / Fail / Review result variants

History section:
- Populated (6 rows, scrollable)
- Empty state

SPACING: 4px base unit
RADIUS SCALE: 8 / 10 / 12 / 14 / 16 / 20px
SCROLLBAR: 4px, thumb rgba(124,92,252,0.25),
           hover rgba(124,92,252,0.45), track transparent