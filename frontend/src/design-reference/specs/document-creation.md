# Document Creation Screen

**Sources:**
- `_figma-source/src/imports/pasted_text/document-creation-page.md`
- `_figma-source/src/imports/pasted_text/knowledge-hub-doc-creation-lay.md` (Column 2 revision)
**Component:** `_figma-source/src/app/components/DocumentCreation.tsx` (nav id: 2, FilePlus icon)

## Layout

3-column: Icon Rail (60px) + Document Form Panel (360px) + Main Area (remaining, blank/empty state)

## Column 2: Document Form Panel (360px)

- bg: bg-surface, right border: border-subtle
- Split into two FIXED-HEIGHT sections with independent scroll:
  - Top form: 675px fixed height
  - Divider: 1px border-subtle
  - Bottom history: 224px fixed height

### Section 1: Create Document Form (675px, scrollable)

**Header** (64px, fixed, not scrollable):
- "Create Document" 15px semibold + "Fill in details to generate" 11px text-faint
- Close (X) icon button 28x28

**Scrollable Form Body** (flex-1, overflow-y-auto, padding 20px, gap 16px):
- Custom scrollbar: 4px width, purple thumb

**Form Fields:**
1. **Document Type** (SectionLabel + select dropdown):
   - Options: NDA, Contract, Agreement, Compliance Report, Letter, Custom
   - Select: bg-elevated, rounded-[10px], border-subtle
2. **Title** (TextInput): "Enter document title..."
3. **Framework / Template** (SectionLabel + select): Indonesia Law, International, Singapore, Custom
4. **Output Language** (SectionLabel + radio group): Bahasa Indonesia / English
   - Radio: accent-primary filled dot when selected
5. **Key Parties** (SectionLabel + TextInput): "Add party names..."
6. **Specific Clauses** (SectionLabel + tag input):
   - Tags: purple pills with X remove button
   - Input: "Type and press Enter..."
7. **Additional Context** (SectionLabel + textarea):
   - bg-elevated, rounded-[10px], min-height 80px
   - Placeholder: "Any specific requirements..."

**Generate Button** (pinned at bottom of form section):
- ActionButton: "Generate Document" with Sparkles icon
- Disabled when no document type selected

### Section 2: Recent Creations History (224px, scrollable)

- Uses HistorySection component
- ColumnHeader: "Recent Creations" + chevron toggle
- 6 history rows with document type badge colors:
  - NDA = purple, Contract = cyan, Agreement = green, Report = amber
  - Each row: badge + title (truncated) + timestamp + type label

## Column 3: Main Area (Empty State)

- bg-base + mesh gradient
- EmptyState centered: large FilePlus icon + "Create a New Document" title + description + HintChipRow

## States

- Form fields: default / focused (border-accent + glow)
- Generate button: disabled (gray) / enabled (purple) / hover (lighter + shadow)
- Clause tags: default / hover (X appears) / removing
- History rows: default / hover (bg-hover + chevron)
- Radio buttons: unselected / selected (purple fill)
