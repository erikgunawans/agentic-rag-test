# Compliance Check Screen

**Source:** `_figma-source/src/imports/pasted_text/compliance-check-page.tsx`
**Component:** `_figma-source/src/app/components/ComplianceCheck.tsx` (nav id: 4, ShieldCheck icon)

## Layout

3-column: Icon Rail (60px) + Compliance Panel (360px) + Main Area (remaining, blank/empty state)

## Column 2: Compliance Panel (360px)

- bg: bg-surface, right border: border-subtle
- Split into two fixed-height sections

### Section 1: Upload & Config (top, ~675px)

**Header** (64px):
- "Compliance Check" 15px semibold + "Upload document to check" 11px text-faint
- Close (X) icon button

**Form Content** (scrollable, padding 20px, gap 16px):

1. **Upload Document** (SectionLabel + DropZone):
   - Single document upload
2. **Regulation Framework** (SectionLabel + select):
   - Options: OJK Regulations, POJK Standards, Indonesian Civil Code, International Standards, Custom
3. **Check Categories** (SectionLabel + checkboxes):
   - Data Protection, Financial Compliance, Labor Laws, Environmental, Anti-Corruption
   - Checkboxes: accent-primary when checked
4. **Compliance Standard** (SectionLabel + select):
   - ISO 27001, SOC 2, GDPR, Custom
5. **Severity Threshold** (SectionLabel + AnalysisDepthControl):
   - All Issues / Major Only / Critical Only
   - 3-segment toggle, active segment highlighted

**Check Button** (pinned bottom):
- ActionButton: "Run Compliance Check" with ShieldCheck icon
- Disabled until document uploaded

### Section 2: Recent Checks History (224px)

- HistorySection with compliance-specific badges
- Uses ComplianceStatusBadge: Compliant (green), Issues Found (amber), Non-Compliant (red)
- Each row: status badge + filename + timestamp + status label

## Column 3: Main Area (Empty State)

- EmptyState: ShieldCheck icon + "Check Document Compliance" + description
- HintChipRow: "Regulatory gaps", "Required clauses", "Risk areas"

## States

- DropZone: empty / drag-over / file-attached
- Check button: disabled / enabled / hover
- Category checkboxes: unchecked / checked
- Severity toggle: Quick / Standard / Deep (active segment)
- History rows: default / hover
- ComplianceStatusBadge: Compliant / Issues / Non-Compliant
