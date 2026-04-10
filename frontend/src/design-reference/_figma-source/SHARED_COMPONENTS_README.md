# Shared Figma Components

This document describes the shared, reusable components extracted from the Knowledge Hub dashboard.

## Components Created

All components are located in `/src/app/components/shared/` and can be imported via:

```tsx
import { IconRail, SubHeader, HistoryRow, DropZone, ActionButton, HintChipRow, SectionLabel } from './components/shared';
```

---

### 1. IconRail

**Location:** `/src/app/components/shared/IconRail.tsx`

**Purpose:** The floating navigation rail with logo, nav icons, and avatar.

**Variants:**
- `floating` (default) - Full floating pill with backdrop blur
- `simple` - Minimal rail for documents view

**Props:**
```tsx
interface IconRailProps {
  navIcons: { Icon: LucideIcon; id: number }[];
  activeNav: number;
  onNavClick: (id: number) => void;
  variant?: 'floating' | 'simple';
}
```

**Usage:**
```tsx
<IconRail 
  navIcons={navIcons}
  activeNav={activeNav}
  onNavClick={setActiveNav}
  variant="floating"
/>
```

---

### 2. SubHeader

**Location:** `/src/app/components/shared/SubHeader.tsx`

**Purpose:** Column 2 sub-headers like "Recent Analyses" with optional "View all" button.

**Props:**
```tsx
interface SubHeaderProps {
  title: string;
  onViewAllClick?: () => void;
}
```

**Usage:**
```tsx
<SubHeader 
  title="Recent Analyses" 
  onViewAllClick={() => console.log('View all')}
/>
```

---

### 3. HistoryRow

**Location:** `/src/app/components/shared/HistoryRow.tsx`

**Purpose:** History list rows with badge, title, timestamp, status, and hover states.

**Features:**
- Badge with custom color
- Truncated title text
- Timestamp display
- Status label
- Chevron icon on hover
- Automatic hover background

**Props:**
```tsx
interface HistoryRowProps {
  title: string;
  timestamp: string;
  status: string;
  badgeColor: string;
  badgeBg: string;
  onClick?: () => void;
}
```

**Usage:**
```tsx
<HistoryRow
  title="NDA_PT_Marina_2026.pdf"
  timestamp="1h ago"
  status="Low Risk"
  badgeColor="#34D399"
  badgeBg="rgba(52, 211, 153, 0.12)"
  onClick={() => console.log('Row clicked')}
/>
```

---

### 4. DropZone

**Location:** `/src/app/components/shared/DropZone.tsx`

**Purpose:** File upload drop zone with drag-and-drop support.

**States:**
- Idle - Default state with upload icon
- Hover - Active drag-over state
- File attached - Shows file name with remove button

**Props:**
```tsx
interface DropZoneProps {
  label: string;
  onFileSelect?: (file: File | null) => void;
  accept?: string;
  fileName?: string;
}
```

**Usage:**
```tsx
<DropZone 
  label="Upload Document"
  accept=".pdf,.docx"
  onFileSelect={(file) => console.log(file)}
/>
```

---

### 5. ActionButton

**Location:** `/src/app/components/shared/ActionButton.tsx`

**Purpose:** Bottom action buttons like "Generate Analysis", "Run Comparison".

**States:**
- Enabled - Purple background with icon and label
- Disabled - Gray background, no hover effect
- Hover - Elevated with shadow

**Specifications:**
- Height: 44px
- Width: calc(100% - 40px)
- Margin: 0 20px
- Border radius: 12px
- Font: 14px semibold

**Props:**
```tsx
interface ActionButtonProps {
  label: string;
  Icon: LucideIcon;
  onClick?: () => void;
  disabled?: boolean;
}
```

**Usage:**
```tsx
<ActionButton 
  label="Run Analysis"
  Icon={FileSearch}
  onClick={() => console.log('Running...')}
  disabled={!hasFile}
/>
```

---

### 6. HintChipRow

**Location:** `/src/app/components/shared/HintChipRow.tsx`

**Purpose:** Row of 3 hint chips shown in empty states.

**Specifications:**
- Height: 26px
- Padding: 0 10px
- Border radius: 20px
- Font: 11px
- 6px color dot + label
- Gap: 8px between chips

**Props:**
```tsx
interface HintChipRowProps {
  chips: { color: string; label: string }[];
}
```

**Usage:**
```tsx
<HintChipRow 
  chips={[
    { color: '#34D399', label: 'Low risk clauses' },
    { color: '#F59E0B', label: 'Medium risk' },
    { color: '#F87171', label: 'High risk flags' }
  ]}
/>
```

---

### 7. SectionLabel

**Location:** `/src/app/components/shared/SectionLabel.tsx`

**Purpose:** Uppercase section labels like "UPLOAD DOCUMENT", "FILTERS".

**Specifications:**
- Font: 11px semibold
- Color: #475569
- Letter spacing: 0.08em
- Text transform: uppercase

**Props:**
```tsx
interface SectionLabelProps {
  children: React.ReactNode;
}
```

**Usage:**
```tsx
<SectionLabel>Upload Document</SectionLabel>
<SectionLabel>Analysis Type</SectionLabel>
```

---

## Design Tokens

All components use consistent design tokens:

**Colors:**
- Primary purple: `#7C5CFC`
- Text bright: `#F1F5F9`
- Text muted: `#94A3B8`
- Text faint: `#475569`
- Background dark: `#0B1120`
- Background card: `#162033`
- Border: `#1E2D45`

**Interactive States:**
- Hover background: `#1C2840`
- Active purple background: `rgba(124, 92, 252, 0.12)`
- Active purple border: `rgba(124, 92, 252, 0.4)`

**Measurements:**
- History row height: `44px`
- Action button height: `44px`
- Sub-header height: `52px`
- Section label height: auto
- Hint chip height: `26px`

---

## Benefits

1. **Consistency** - All pages use identical components with same styling
2. **Maintainability** - Update once, applies everywhere
3. **Type Safety** - Full TypeScript support
4. **Reusability** - Easy to add new pages/features
5. **Performance** - Shared component instances
6. **Documentation** - Clear props and usage examples

---

## Next Steps

To integrate these components into existing pages:

1. Import the components from `./components/shared`
2. Replace inline JSX with component calls
3. Pass appropriate props based on context
4. Remove duplicate code from individual pages
5. Test interactive states and hover effects
6. Verify responsive behavior

Example refactor:

**Before:**
```tsx
<div style={{ fontSize: '11px', fontWeight: 600, color: '#475569', letterSpacing: '0.08em', textTransform: 'uppercase' }}>
  Analysis Type
</div>
```

**After:**
```tsx
<SectionLabel>Analysis Type</SectionLabel>
```
