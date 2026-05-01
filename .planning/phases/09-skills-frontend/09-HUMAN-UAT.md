---
status: partial
phase: 09-skills-frontend
source: [09-VERIFICATION.md]
started: 2026-05-01T05:30:00Z
updated: 2026-05-01T05:30:00Z
---

## Current Test

[awaiting human testing]

## Tests

### 1. Try in Chat — no prior active thread
expected: Navigate to /skills, select any skill, click "Try in Chat". A new thread is created and "Please use the {skill-name} skill." appears as the first sent message.
result: [pending]

### 2. Try in Chat — with existing active thread
expected: With an active thread open, navigate to /skills, select a skill, click "Try in Chat". The message is appended to the existing thread.
result: [pending]

### 3. Create with AI — fresh session
expected: On the SkillsPage, click the "Create with AI" button (or equivalent new-skill trigger). Navigates to / and sends "I want to create a new skill." as the first message.
result: [pending]

### 4. Skills nav entry visible and active
expected: Skills tab (Zap icon) appears in IconRail between Chat and Dashboard. Clicking it navigates to /skills and the tab shows the purple active stripe.
result: [pending]

### 5. Skills list loads and search filters
expected: /skills page loads the skill list. Typing in the search box filters results after 300ms debounce.
result: [pending]

### 6. Create, edit, delete skill
expected: Can create a new skill (POST), edit own private skill fields (PATCH), and delete (DELETE with filename-specific confirm dialog).
result: [pending]

### 7. Share / Unshare
expected: Can share a private skill (becomes GLOBAL badge), can unshare (returns to private). Banners render correctly per ownership state.
result: [pending]

### 8. File upload and preview drawer
expected: Can upload a file to a skill (10 MB limit enforced). Clicking a file opens the 480px drawer. Text files show monospace pre block. Binary shows download card. Escape / backdrop / × closes it.
result: [pending]

### 9. Import from ZIP
expected: Import button triggers ZIP upload. Progress overlay shows. Summary modal shows created/error counts.
result: [pending]

### 10. Locale switching
expected: Toggle app locale ID↔EN. All skills.* strings update correctly. Indonesian is default.
result: [pending]

### 11. Panel collapse button accessibility
expected: The panel collapse button (PanelLeftClose icon) announces "Collapse panel" / "Ciutkan panel" to screen readers, not "Cancel" / "Batal".
result: [pending]

## Summary

total: 11
passed: 0
issues: 0
pending: 11
skipped: 0
blocked: 0

## Gaps
