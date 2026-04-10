# Document Comparison Screen

**Source:** `_figma-source/src/imports/pasted_text/document-comparison.tsx`
**Component:** `_figma-source/src/app/components/DocumentComparison.tsx` (nav id: 3, GitCompare icon)

## Layout

3-column: Icon Rail (60px) + Comparison Panel (360px) + Main Area (remaining, blank/empty state)

## Column 2: Comparison Panel (360px)

- bg: bg-surface, right border: border-subtle
- Split into two fixed-height sections (same pattern as Document Creation)

### Section 1: Upload & Config (top, ~675px)

**Header** (64px):
- "Compare Documents" 15px semibold + "Upload two documents" 11px text-faint
- Close (X) icon button

**Form Content** (scrollable, padding 20px, gap 16px):

1. **Document A** (SectionLabel + DropZone):
   - DropZone with "Original Document" label
   - States: empty / file attached (shows filename + size + remove button)
2. **Document B** (SectionLabel + DropZone):
   - DropZone with "Revised Document" label
3. **Comparison Type** (SectionLabel + checkboxes):
   - Text Changes, Clause Differences, Risk Assessment, Formatting
   - Checkboxes: accent-primary when checked
4. **Focus Areas** (SectionLabel + tag input):
   - Same tag pattern as Document Creation
5. **Output Format** (SectionLabel + radio group):
   - Side-by-Side / Inline / Summary Only

**Compare Button** (pinned bottom):
- ActionButton: "Run Comparison" with GitCompare icon
- Disabled until both documents uploaded

### Section 2: Recent Comparisons History (224px)

- HistorySection with comparison-specific badges
- Badge colors: text changes = cyan, clause diff = purple
- Each row: badge + filenames + timestamp + status

## Column 3: Main Area (Empty State)

- EmptyState: GitCompare icon + "Compare Two Documents" + description
- HintChipRow: "Text differences", "Clause changes", "Risk delta"

## States

- DropZone: empty / drag-over / file-attached
- Compare button: disabled / enabled / hover
- Comparison type checkboxes: unchecked / checked
- History rows: default / hover
