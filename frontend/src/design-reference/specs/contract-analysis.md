# Contract Analysis Screen

**Source:** `_figma-source/src/imports/pasted_text/contract-analysis.tsx`
**Component:** `_figma-source/src/app/components/ContractAnalysis.tsx` (nav id: 5, Scale icon)

## Layout

3-column: Icon Rail (60px) + Analysis Panel (360px) + Main Area (remaining, blank/empty state)

## Column 2: Analysis Panel (360px)

- bg: bg-surface, right border: border-subtle
- Split into two fixed-height sections

### Section 1: Upload & Config (top, ~675px)

**Header** (64px):
- "Contract Analysis" 15px semibold + "Upload contract to analyze" 11px text-faint
- Info (i) icon button

**Form Content** (scrollable, padding 20px, gap 16px):

1. **Upload Contract** (SectionLabel + DropZone):
   - Single document upload
2. **Analysis Types** (SectionLabel + checkboxes):
   - Risk Assessment, Key Obligations, Critical Clauses, Missing Terms
   - All checked by default
3. **Governing Law** (SectionLabel + select dropdown):
   - Indonesia, International, Singapore Law, Custom / Other
4. **Analysis Depth** (SectionLabel + AnalysisDepthControl):
   - Quick / Standard / Deep
   - 3-segment toggle: active = bg accent-primary, text white; inactive = text-secondary

**Analyze Button** (pinned bottom):
- ActionButton: "Generate Analysis" with FileSearch icon
- Disabled until contract uploaded

### Section 2: Recent Analyses History (224px)

- Uses HistorySection component with SubHeader "Recent Analyses" + "View all"
- History rows with RiskBadge:
  - Low Risk: green badge (FileCheck icon), `bg-success/12 text-success`
  - Medium Risk: amber badge (FileWarning icon), `bg-warning/12 text-warning`
  - High Risk: red badge (FileX icon), `bg-danger/12 text-danger`
- Each row: risk badge + filename + analysis depth + timestamp + risk label
- Rows show chevron on hover

## Column 3: Main Area (Empty State)

- EmptyState: Scale icon + "Analyze Your Contract" + description
- HintChipRow with 3 chips:
  - Green dot + "Low risk clauses"
  - Amber dot + "Medium risk"
  - Red dot + "High risk flags"

## Shared Components Used

- ColumnHeader (panel header with title + icon)
- SubHeader ("Recent Analyses" + "View all")
- HistoryRow (individual history items)
- DropZone (file upload area)
- ActionButton (bottom CTA)
- SectionLabel (uppercase labels)
- HintChipRow (empty state hints)
- EmptyState (main area empty)
- AnalysisDepthControl (3-segment toggle)
- RiskBadge (risk level indicator)

## States

- DropZone: empty / drag-over / file-attached
- Analyze button: disabled / enabled / hover
- Analysis type checkboxes: unchecked / checked
- Depth toggle: Quick / Standard / Deep active states
- Governing law dropdown: closed / open / selected
- History rows: default / hover (chevron appears)
- Risk badges: Low (green) / Med (amber) / High (red)
