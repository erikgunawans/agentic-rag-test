# 2026 Design Refresh — Calibrated Restraint Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Shift the PJAA CLM UI from navy-blue tinted surfaces to zinc-neutral, flatten buttons, remove glass from persistent panels, tighten typography, and refine atmospheric effects — matching 2026 "calibrated restraint" design trends.

**Architecture:** CSS-first approach. Task 1 updates all design tokens and utility classes in index.css. Tasks 2-4 update component classes across TSX files. No new files, no structural changes, no backend work.

**Tech Stack:** Tailwind CSS, CSS custom properties, React TSX

**Spec:** `docs/superpowers/specs/2026-04-14-design-2026-refresh.md`

---

### Task 1: Update Design Tokens, Utility Classes & Effects (index.css)

**Files:**
- Modify: `frontend/src/index.css`

This is the core task. All color tokens, glass tokens, mesh-bg, dot-grid, shadows, scrollbar, interactive-lift, and typography base styles.

- [ ] **Step 1: Update color tokens in :root**

Replace the `:root` block (lines 52-114) with zinc-neutral values:

```css
:root {
    /* Zinc-neutral palette — 2026 Calibrated Restraint */
    --background: #09090B;
    --foreground: #FAFAFA;
    --card: #18181B;
    --card-foreground: #FAFAFA;
    --popover: #18181B;
    --popover-foreground: #FAFAFA;
    --primary: oklch(0.55 0.20 280);
    --primary-foreground: oklch(0.98 0 0);
    --secondary: #27272A;
    --secondary-foreground: #E4E4E7;
    --muted: #27272A;
    --muted-foreground: #A1A1AA;
    --accent: #3F3F46;
    --accent-foreground: #FAFAFA;
    --destructive: oklch(0.65 0.20 25);
    --border: oklch(1 0 0 / 5%);
    --input: oklch(1 0 0 / 8%);
    --ring: oklch(0.55 0.20 280);
    --chart-1: oklch(0.55 0.20 280);
    --chart-2: oklch(0.60 0.15 200);
    --chart-3: oklch(0.65 0.15 150);
    --chart-4: oklch(0.55 0.15 50);
    --chart-5: oklch(0.60 0.20 320);
    --radius: 0.625rem;

    /* Sidebar */
    --sidebar: #111113;
    --sidebar-foreground: #E4E4E7;
    --sidebar-primary: oklch(0.55 0.20 280);
    --sidebar-primary-foreground: oklch(0.98 0 0);
    --sidebar-accent: #27272A;
    --sidebar-accent-foreground: #FAFAFA;
    --sidebar-border: oklch(1 0 0 / 5%);
    --sidebar-ring: oklch(0.55 0.20 280);

    /* Icon rail */
    --icon-rail: #0C0C0E;
    --icon-rail-foreground: #71717A;
    --icon-rail-active: oklch(0.55 0.20 280);

    /* Feature accent colors — unchanged */
    --feature-creation: oklch(0.55 0.24 280);
    --feature-management: oklch(0.70 0.15 195);
    --feature-compliance: oklch(0.72 0.17 160);
    --feature-analysis: oklch(0.70 0.18 85);

    /* 2026 Design — Glow shadows (wider, subtler) */
    --glow-primary: 0 0 24px oklch(0.55 0.20 280 / 0.12);
    --glow-sm: 0 0 14px oklch(0.55 0.20 280 / 0.08);

    /* 2026 Design — Layered shadows — unchanged */
    --shadow-xs: 0 1px 2px oklch(0 0 0 / 0.15);
    --shadow-sm: 0 2px 6px oklch(0 0 0 / 0.2), 0 1px 2px oklch(0 0 0 / 0.1);
    --shadow-md: 0 4px 14px oklch(0 0 0 / 0.25), 0 1px 4px oklch(0 0 0 / 0.15);
    --shadow-lg: 0 8px 30px oklch(0 0 0 / 0.3), 0 2px 8px oklch(0 0 0 / 0.2);

    /* 2026 Design — Glassmorphism (zinc-neutral, transient only) */
    --glass-bg: oklch(0.14 0 0 / 0.75);
    --glass-border: oklch(1 0 0 / 8%);
    --glass-blur: 16px;
}
```

- [ ] **Step 2: Update scrollbar colors**

Replace scrollbar thumb colors (lines 130, 140, 144):

```css
  * {
    scrollbar-width: thin;
    scrollbar-color: #3F3F46 transparent;
  }
  /* ... */
  *::-webkit-scrollbar-thumb {
    background: #3F3F46;
    border-radius: 3px;
  }
  *::-webkit-scrollbar-thumb:hover {
    background: #52525B;
  }
```

- [ ] **Step 3: Add typography base styles**

Add heading typography rules inside the `@layer base` block, after the scrollbar styles:

```css
  /* 2026 Typography — tighter headings */
  h1 {
    letter-spacing: -0.02em;
    font-weight: 600;
  }
  h2 {
    letter-spacing: -0.01em;
    font-weight: 600;
  }
  h3 {
    font-weight: 500;
  }
```

- [ ] **Step 4: Update mesh-bg pseudo-elements**

Replace the mesh-bg `::before` and `::after` rules (lines 226-239) with purple-hued, blurred orbs:

```css
.mesh-bg::before {
  top: -100px;
  right: -100px;
  width: 600px;
  height: 600px;
  background: radial-gradient(circle, rgba(139, 92, 246, 0.04) 0%, transparent 70%);
  filter: blur(40px);
}
.mesh-bg::after {
  bottom: -80px;
  left: -80px;
  width: 500px;
  height: 500px;
  background: radial-gradient(circle, rgba(139, 92, 246, 0.03) 0%, transparent 70%);
  filter: blur(40px);
}
```

- [ ] **Step 5: Update dot-grid opacity**

Change dot opacity from 0.04 to 0.03 (line 249):

```css
  background-image: radial-gradient(oklch(1 0 0 / 0.03) 1px, transparent 1px);
```

- [ ] **Step 6: Update interactive-lift**

Replace the interactive-lift rules (lines 302-312):

```css
.interactive-lift {
  transition: transform 0.15s cubic-bezier(0.4, 0, 0.2, 1),
              box-shadow 0.15s cubic-bezier(0.4, 0, 0.2, 1);
}
.interactive-lift:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
}
.interactive-lift:active {
  transform: translateY(0) scale(0.98);
  transition-duration: 0.05s;
}
```

- [ ] **Step 7: Run type check**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors (CSS changes don't affect types)

- [ ] **Step 8: Commit**

```bash
git add frontend/src/index.css
git commit -m "feat: 2026 design tokens — zinc palette, refined effects, tighter typography"
```

---

### Task 2: Remove Glass from Persistent Panels

**Files:**
- Modify: `frontend/src/components/layout/ThreadPanel.tsx`
- Modify: `frontend/src/components/chat/MessageInput.tsx`
- Modify: `frontend/src/components/chat/WelcomeInput.tsx`
- Modify: `frontend/src/components/shared/FeaturePageLayout.tsx`

- [ ] **Step 1: Update ThreadPanel — remove glass and dot-grid**

In `frontend/src/components/layout/ThreadPanel.tsx`, find:

```tsx
className="flex h-full w-[340px] shrink-0 flex-col border-r border-border glass dot-grid transition-all duration-200"
```

Replace with:

```tsx
className="flex h-full w-[340px] shrink-0 flex-col border-r border-border bg-sidebar transition-all duration-200"
```

- [ ] **Step 2: Update MessageInput — remove glass from card**

In `frontend/src/components/chat/MessageInput.tsx`, find:

```tsx
className="mx-auto max-w-2xl rounded-2xl border bg-card glass p-4 shadow-[var(--shadow-md)] transition-shadow focus-within:shadow-[var(--glow-primary)]"
```

Replace with:

```tsx
className="mx-auto max-w-2xl rounded-2xl border bg-card p-4 shadow-[var(--shadow-md)] transition-shadow focus-within:shadow-[var(--glow-primary)]"
```

- [ ] **Step 3: Update WelcomeInput — remove glass from card**

In `frontend/src/components/chat/WelcomeInput.tsx`, find:

```tsx
className="w-full rounded-2xl border bg-card glass p-4 shadow-[var(--shadow-md)] transition-shadow focus-within:shadow-[var(--glow-primary)]"
```

Replace with:

```tsx
className="w-full rounded-2xl border bg-card p-4 shadow-[var(--shadow-md)] transition-shadow focus-within:shadow-[var(--glow-primary)]"
```

- [ ] **Step 4: Update FeaturePageLayout — remove glass from right panel**

In `frontend/src/components/shared/FeaturePageLayout.tsx`, find:

```tsx
className="hidden lg:flex w-[223px] shrink-0 flex-col border-l border-border/50 glass"
```

Replace with:

```tsx
className="hidden lg:flex w-[223px] shrink-0 flex-col border-l border-border/50 bg-sidebar"
```

- [ ] **Step 5: Run type check**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/layout/ThreadPanel.tsx \
       frontend/src/components/chat/MessageInput.tsx \
       frontend/src/components/chat/WelcomeInput.tsx \
       frontend/src/components/shared/FeaturePageLayout.tsx
git commit -m "feat: remove glass from persistent panels — solid surfaces only"
```

---

### Task 3: Remove Glass from All Page Sidebar Panels

**Files:**
- Modify: `frontend/src/pages/DocumentsPage.tsx`
- Modify: `frontend/src/pages/ClauseLibraryPage.tsx`
- Modify: `frontend/src/pages/RegulatoryPage.tsx`
- Modify: `frontend/src/pages/ApprovalInboxPage.tsx`
- Modify: `frontend/src/pages/ComplianceCheckPage.tsx`
- Modify: `frontend/src/pages/ContractAnalysisPage.tsx`
- Modify: `frontend/src/pages/DocumentComparisonPage.tsx`
- Modify: `frontend/src/pages/DocumentCreationPage.tsx`
- Modify: `frontend/src/pages/SettingsPage.tsx`
- Modify: `frontend/src/pages/AdminSettingsPage.tsx`

All 10 pages have the same pattern on their desktop sidebar panel.

- [ ] **Step 1: Replace glass with bg-sidebar on all 10 pages**

In every file, find:

```
hidden md:flex w-[340px] shrink-0 flex-col border-r border-border/50 glass
```

Replace with:

```
hidden md:flex w-[340px] shrink-0 flex-col border-r border-border/50 bg-sidebar
```

Note: `DocumentsPage.tsx` has `overflow-y-auto` appended — preserve that:

```
hidden md:flex w-[340px] shrink-0 flex-col border-r border-border/50 bg-sidebar overflow-y-auto
```

- [ ] **Step 2: Run type check**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/DocumentsPage.tsx \
       frontend/src/pages/ClauseLibraryPage.tsx \
       frontend/src/pages/RegulatoryPage.tsx \
       frontend/src/pages/ApprovalInboxPage.tsx \
       frontend/src/pages/ComplianceCheckPage.tsx \
       frontend/src/pages/ContractAnalysisPage.tsx \
       frontend/src/pages/DocumentComparisonPage.tsx \
       frontend/src/pages/DocumentCreationPage.tsx \
       frontend/src/pages/SettingsPage.tsx \
       frontend/src/pages/AdminSettingsPage.tsx
git commit -m "feat: replace glass with solid bg-sidebar on all page sidebars"
```

---

### Task 4: Flatten Gradient Buttons + Typography Fix

**Files:**
- Modify: `frontend/src/components/chat/InputActionBar.tsx`
- Modify: `frontend/src/pages/DocumentsPage.tsx`

- [ ] **Step 1: Flatten InputActionBar send button gradient**

In `frontend/src/components/chat/InputActionBar.tsx`, find:

```tsx
className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-primary to-[oklch(0.55_0.18_250)] text-primary-foreground transition-all disabled:opacity-50 hover:shadow-[var(--glow-sm)]"
```

Replace with:

```tsx
className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground transition-all disabled:opacity-50 hover:shadow-[var(--glow-sm)] active:scale-[0.98]"
```

- [ ] **Step 2: Fix DocumentsPage heading weight**

In `frontend/src/pages/DocumentsPage.tsx`, find:

```tsx
<h1 className="text-lg font-bold tracking-tight">{t('documents.title')}</h1>
```

Replace with:

```tsx
<h1 className="text-lg tracking-tight">{t('documents.title')}</h1>
```

(The `font-semibold` and `letter-spacing: -0.01em` are now set by the `h1` base style in CSS, so no explicit class needed.)

- [ ] **Step 3: Verify no other gradient buttons exist (chat bubbles should keep gradient)**

Run: `grep -rn "bg-gradient-to-br from-primary" frontend/src/`

Expected output should only show `MessageView.tsx` (user chat bubbles — intentionally kept):
```
frontend/src/components/chat/MessageView.tsx:101: 'bg-gradient-to-br from-primary to-[oklch(0.50_0.18_260)] text-primary-foreground'
```

- [ ] **Step 4: Run type check**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/chat/InputActionBar.tsx \
       frontend/src/pages/DocumentsPage.tsx
git commit -m "feat: flatten gradient buttons, fix heading weight for 2026 typography"
```

---

### Task 5: Final Verification & Build Check

- [ ] **Step 1: Run full type check**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 2: Run lint**

Run: `cd frontend && npm run lint`
Expected: No new errors

- [ ] **Step 3: Verify gradient text and chat bubble gradients still work**

Run: `grep -rn "gradient-text\|bg-gradient-to-br" frontend/src/`

Expected: `gradient-text` class should appear in `WelcomeScreen.tsx` and `index.css`. `bg-gradient-to-br` should only appear in `MessageView.tsx` (user chat bubbles).

- [ ] **Step 4: Verify no remaining glass on persistent panels**

Run: `grep -rn "glass" frontend/src/ | grep -v node_modules | grep -v ".css"`

Expected: No matches in TSX files. The `.glass` class definition stays in `index.css` (used by tooltips/popovers), but no TSX component should reference it on persistent panels.

- [ ] **Step 5: Commit verification results (if any fixes needed)**

If all checks pass, no commit needed. If fixes were required, commit them:

```bash
git add -A
git commit -m "fix: address lint/type issues from design refresh"
```
