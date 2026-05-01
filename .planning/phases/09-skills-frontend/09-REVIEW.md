---
phase: 09
status: issues_found
files_reviewed: 5
findings:
  critical: 1
  warning: 2
  info: 0
  total: 3
generated: 2026-05-01
---

# Code Review — Phase 09: skills-frontend

## Summary
The Skills page and its navigation wiring are well-structured overall. One critical logic bug causes the prefill message from SkillsPage to be silently dropped whenever the user has no active thread. Two warnings cover an incorrect accessibility label on the panel collapse button and a UX gap in the file delete confirmation dialog.

## Findings

### CR-01: Prefill message silently dropped when no active thread (critical)
**File:** `frontend/src/pages/ChatPage.tsx:36`
**Confidence:** 100

**Issue:** `ChatPage` consumes `location.state.prefill` by calling `handleSendMessage(prefill)`. However, `handleSendMessage` contains an early-return guard:

```ts
if (!activeThreadId || isStreaming) return
```

When the user navigates from SkillsPage with no prior active thread — the most common path — `activeThreadId` is `null`. The call silently returns without creating a thread or sending anything. Immediately after, `consumedRef.current = true` and `navigate(…, { state: null })` fire, destroying the prefill permanently. The user sees the WelcomeScreen with no message sent and no feedback.

**Impact:** Both "Create with AI" and "Try in Chat" buttons on SkillsPage are broken for users who arrive without a pre-existing active thread. The prefill is consumed and discarded with no error, no retry, and no user feedback.

**Fix:** Branch on `activeThreadId` in the effect — use `handleSendFirstMessage` when no thread exists:

```ts
useEffect(() => {
  const stateObj = location.state as { prefill?: string } | null
  const prefill = stateObj?.prefill
  if (prefill && !consumedRef.current) {
    consumedRef.current = true
    if (activeThreadId) {
      handleSendMessage(prefill)
    } else {
      handleSendFirstMessage(prefill)
    }
    navigate(location.pathname, { replace: true, state: null })
  }
}, [location.state, location.pathname, activeThreadId, handleSendMessage, handleSendFirstMessage, navigate])
```

`handleSendFirstMessage` creates a new thread then sends the message to it — the correct path for a fresh navigation from SkillsPage.

---

### CR-02: Wrong aria-label on desktop panel collapse button (warning)
**File:** `frontend/src/pages/SkillsPage.tsx:1022`
**Confidence:** 85

**Issue:** The desktop panel collapse/toggle button uses `aria-label={t('skills.cancel')}`, which resolves to "Batal" (ID) or "Cancel" (EN). Screen reader users will hear "Cancel" announced for a button that collapses the skills list panel.

**Impact:** Accessibility violation. Screen reader users cannot distinguish this control from the form cancel button.

**Fix:** Use a dedicated translation key or a descriptive string:

```tsx
aria-label={panelCollapsed ? 'Expand panel' : 'Collapse panel'}
```

---

### CR-03: File delete confirmation shows no filename (warning)
**File:** `frontend/src/pages/SkillsPage.tsx:377-392`
**Confidence:** 80

**Issue:** `handleDeleteFile(fileId: string, filename: string)` accepts a `filename` argument but never uses it in the confirmation dialog. The `filename` parameter is suppressed with `void filename` to silence the linter.

**Impact:** When a skill has multiple files, the user's confirmation dialog gives no indication of *which* file is being deleted, creating a real risk of accidental deletion.

**Fix:** Interpolate the filename into the confirmation message:

```ts
if (!confirm(t('skills.fileDeleteConfirm', { filename }))) return
// remove the `void filename` line
```

And update the translation key in both locales:
```ts
'skills.fileDeleteConfirm': 'Hapus "{filename}" dari skill? Tindakan ini tidak dapat dibatalkan.',
'skills.fileDeleteConfirm': 'Delete "{filename}" from this skill? This cannot be undone.',
```

---

## Files Reviewed
- `frontend/src/App.tsx`
- `frontend/src/components/layout/IconRail.tsx`
- `frontend/src/i18n/translations.ts`
- `frontend/src/pages/ChatPage.tsx`
- `frontend/src/pages/SkillsPage.tsx`
