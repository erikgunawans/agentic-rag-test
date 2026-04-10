Create the Document Creation page for Knowledge Hub. This view 
appears when the PENCIL/EDIT icon in the icon rail (Column 1) 
is clicked. The layout follows the same 3-column structure:
icon rail + form panel + blank main area.

Canvas: 1440×900px desktop frame.

---

OVERALL STRUCTURE (left to right)

| Column 1      | Column 2              | Column 3              |
| Icon Rail     | Document Form Panel   | Main Area (blank)     |
| 60px fixed    | 360px fixed           | 1020px remaining      |

All columns full height. No gap — borders act as dividers.

---

DESIGN TOKENS (same Knowledge Hub system)

bg-base: #0B1120 | bg-surface: #0F1829 | bg-elevated: #162033
bg-hover: #1C2840 | accent: #7C5CFC
accent-glow: rgba(124,92,252,0.15)
accent-gradient: linear #7C5CFC → #A78BFA → #60A5FA
text-primary: #F1F5F9 | text-secondary: #94A3B8 | text-faint: #475569
border-subtle: #1E2D45 | border-accent: rgba(124,92,252,0.4)
required-red: #F87171 | success: #34D399 | warning: #F59E0B

Font: Inter Variable
Sizes: 11/12/13/14/15px | Weights: 400/500/600/700

---

COLUMN 1 — Icon Rail (60px, unchanged)

Same as Knowledge Hub shell.
Pencil/edit icon is now the ACTIVE state:
- Icon: pencil or edit icon, 20px, color accent (#7C5CFC)
- Active bg: 36×36px rounded square, fill rgba(124,92,252,0.12),
  outer glow: 0 0 16px rgba(124,92,252,0.3)
All other icons: 20px, color text-secondary (#94A3B8)
Background: #080C14, full height

---

COLUMN 2 — Document Form Panel (360px)

Background: bg-surface (#0F1829)
Right border: 1px solid border-subtle (#1E2D45)
Auto layout: vertical, align stretch, gap 0
IMPORTANT: This column is scrollable — content overflows vertically

=== HEADER (64px, fixed, not scrollable) ===
Auto layout horizontal, align center, padding 0 20px, space-between
- Left stack (auto layout vertical, gap 2px):
  "Create Document" 15px semibold text-primary
  "Fill in details to generate" 11px text-faint
- Close/collapse icon button: 28×28px, radius 8px, 
  X icon 14px text-secondary, hover bg bg-hover
Bottom border: 1px solid border-subtle

=== SCROLLABLE FORM BODY (padding 20px, auto layout vertical, gap 16px) ===

--- GLOBAL FORM ELEMENT STYLES ---
All apply consistently across every field below:

Field label:
- 13px medium text-primary
- Required asterisk: * in required-red (#F87171), same size, margin-left 2px

Text input (single line):
- Height: 40px, width: 100%, bg bg-elevated (#162033)
- Border: 1px solid border-subtle (#1E2D45), radius 10px
- Padding: 0 14px
- Placeholder: 13px text-faint (#475569)
- Text (filled): 13px text-primary
- Focus state: border border-accent, 
  box-shadow 0 0 0 3px rgba(124,92,252,0.12)
- Hover state: border rgba(124,92,252,0.25)

Textarea (multi-line):
- Min-height: 88px, same bg/border/radius as input
- Padding: 12px 14px
- Resize handle visible at bottom-right (subtle, text-faint color)
- Focus/hover: same as text input

Dropdown/Select:
- Same dimensions as text input (40px height)
- Right side: chevron-down icon 14px text-faint
- Auto layout horizontal, space-between, align center
- Selected value: 13px text-primary
- Placeholder "Select an option": 13px text-faint
- Active/open state: border border-accent

Date input:
- Same as text input, calendar icon 14px text-faint on right

Two-column row (for Duration Count + Duration Unit):
- Auto layout horizontal, gap 10px
- Left: 140px fixed width (count input)
- Right: flex 1 (unit dropdown)

--- DOCUMENT TYPE DROPDOWN (always first field) ---
Label: "Document Type" with * red asterisk
Dropdown with currently selected type shown
Options: Generic Document / NDA / Sales Contract / Service Contract / 
         Service Agreement / Employment Contract

---

FORM VARIANT A — GENERIC DOCUMENT
(shown when "Generic Document" selected)

Fields in order:
1. "Please specify document type" * — text input
   placeholder: "e.g., Independent Contractor Agreement"
2. "First Party" * — text input, placeholder "e.g., Buyer: John Doe"
3. "Second Party" — text input, placeholder "e.g., Seller: Jane Smith Inc."
4. "Effective Date" — date input, placeholder "dd/mm/yyyy"
5. Duration row (two columns):
   "Duration Count" — number input, placeholder "e.g., 1"
   "Duration Unit" — dropdown, placeholder "Select an option"
6. "Purpose of the document" * — textarea (88px)
   placeholder: "e.g., To define terms for software development services"
7. "Scope of Work" * — textarea (88px)
   placeholder: "Detailed description of services/work"
8. "Deliverables" * — textarea (88px)
   placeholder: "Specific outputs or results"
9. "Payment Terms (Optional)" — text input
   placeholder: "e.g., Net 30 days, 50% upfront"
10. "Governing Law" * — text input, default value "Indonesia"
11. "Additional Notes or Specific Requirements" — textarea (72px), no placeholder
12. Output Language section (see below)
13. Upload Reference Document (see below)
14. Upload Template Document (see below)
15. Generate button: "Generate Draft"

---

FORM VARIANT B — NDA
(shown when "NDA" selected)

Fields in order:
1. "Disclosing Party" * — text input, placeholder "e.g., Company A Inc."
2. "Receiving Party" * — text input, placeholder "e.g., Consultant X LLC"
3. "Purpose of Disclosure" * — textarea (88px)
   placeholder: "e.g., Evaluation of potential business partnership"
4. "Definition of Confidential Information" * — textarea (88px), no placeholder
5. "Obligations of Receiving Party" — dropdown, placeholder "Select an option"
6. "Term of Agreement" * — text input
   placeholder: "e.g., 5 years from effective date, indefinite"
7. "Return/Destruction of Confidential Information" * — text input
   placeholder: "Upon termination or request"
8. "Governing Law" * — text input, default value "Indonesia"
9. "Additional Notes or Specific Requirements" — textarea (72px)
10. Output Language section
11. Upload Reference Document
12. Upload Template Document
13. Generate button: "Generate NDA"

---

FORM VARIANT C — SALES CONTRACT
(shown when "Sales Contract" selected)

Fields in order:
1. "First Party" * — text input, placeholder "e.g., Buyer: John Doe"
2. "Second Party" * — text input, placeholder "e.g., Seller: Jane Smith Inc."
3. "Effective Date" * — date input
4. Duration row (two columns, both required *):
   "Duration Count" * | "Duration Unit" *
5. "Purpose of the document" * — textarea (88px)
6. "Scope of Work" * — textarea (88px)
7. "Deliverables" * — textarea (88px)
8. "Payment Terms (Optional)" — text input
9. "Governing Law" * — text input, default "Indonesia"
10. "Additional Notes or Specific Requirements" — textarea (72px)
11. Output Language section
12. Upload Reference Document
13. Upload Template Document
14. Generate button: "Generate Draft"

---

FORM VARIANT D — SERVICE CONTRACT
(shown when "Service Contract" selected)

Identical field structure to Sales Contract.
Generate button label: "Generate Draft"

---

REUSABLE FORM SECTIONS (shared across all variants)

--- Output Language ---
Label: "Output Language" 13px medium text-primary, no asterisk
Auto layout horizontal, gap 24px, align center, margin-top 4px

2 radio options:
Each option: auto layout horizontal, gap 8px, align center

Radio button (18×18px):
- Unselected: border 2px text-faint, fill transparent, radius 50%
- Selected: border 2px accent, inner circle 8×8px fill accent, radius 50%
  outer ring: border 2px #7C5CFC, fill transparent

Option 1: "English & Indonesian (Side-by-side)" 13px text-primary — SELECTED by default
Option 2: "Indonesian Only" 13px text-secondary

--- Upload Reference Document ---
Label: "Upload Reference Document (Optional)" 13px medium text-primary

Drop zone frame:
- Min-height 100px, width 100%, bg transparent
- Border: 1.5px dashed rgba(100,116,139,0.4) — #64748B at 40% opacity
- Border-radius: 12px
- Auto layout: vertical, align center, justify center, gap 6px, padding 20px

Contents:
- Upload icon: 28×28px, upload-cloud or arrow-up-from-bracket, color text-faint
- Row text: "Drop a file here, or " 13px text-faint + 
  "browse" 13px accent underlined (link style)
  inline auto layout horizontal
- "Accepted formats: .txt, .docx, .pdf" 11px text-faint, centered
- "up to 50 Mb" 11px text-faint, centered

Hover state:
- Border: rgba(124,92,252,0.5)
- Background: rgba(124,92,252,0.04)

--- Upload Template Document ---
Identical to Upload Reference Document above.
Label: "Upload Template Document (Optional)"

--- Generate Button (sticky bottom, not inside scroll) ---
Position: fixed at bottom of Column 2, above any padding
Height: 48px, width: calc(100% - 40px), margin: 0 20px 20px
Background: accent (#7C5CFC), border-radius: 12px
Label: varies per variant (see each form above)
Font: 14px semibold white, centered
Hover: bg #8B6EFD, shadow 0 4px 20px rgba(124,92,252,0.4)
Active/press: bg #6D4FE0, shadow none

Thin gradient line above button area:
1px line, gradient from transparent → border-subtle → transparent
Acts as visual separator between scroll area and sticky button

---

COLUMN 3 — Main Area (1020px, blank/empty state)

Background: #0B1120 + mesh gradient:
- Radial rgba(76,29,149,0.06) from top-right, 600px radius
- Radial rgba(10,31,61,0.3) from bottom-left, 500px radius

Content: centered both axes, auto layout vertical, 
align center, gap 12px

Empty state:
- Icon: document-plus or file-edit, 48×48px
  Contained in 80×80px circle, bg rgba(124,92,252,0.08),
  border 1px solid rgba(124,92,252,0.15)
  Icon color: rgba(124,92,252,0.5)
- "Your document will appear here" 16px medium text-secondary,
  text-align center
- "Fill in the form to generate your document" 13px text-faint,
  text-align center, max-width 320px, line-height 1.6

No other elements in Column 3.

---

COMPONENT VARIANTS TO GENERATE

Form panel variants (4 total, one per document type):
- Variant 1: Generic Document (active/default shown)
- Variant 2: NDA
- Variant 3: Sales Contract
- Variant 4: Service Contract

Field states:
- Input: empty / filled / focus / error
- Dropdown: closed / open / selected
- Textarea: empty / filled / focus
- Radio: unselected / selected
- Drop zone: idle / hover / file-attached
- Generate button: default / hover / loading

---

SPACING: 4px base unit — all values multiples of 4
RADIUS SCALE: 8 / 10 / 12 / 16px
SCROLLBAR: thin, 4px width, color border-subtle,
thumb color rgba(124,92,252,0.3), hover rgba(124,92,252,0.5)