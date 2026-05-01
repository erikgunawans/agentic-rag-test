## 11-06 — Pre-existing lint errors (out of scope)

`npm run lint` reports 10 pre-existing errors in files unrelated to Plan 11-06.
Targeted lint on Plan 11-06 files (`CodeExecutionPanel.tsx`, `translations.ts`)
exits 0. Errors below are pre-existing on master and not introduced by Plan 11-06:

- src/components/layout/UserAvatar.tsx (react-refresh/only-export-components ×2)
- src/components/ui/button.tsx (react-refresh/only-export-components)
- src/contexts/AuthContext.tsx (react-refresh/only-export-components)
- src/hooks/useToolHistory.ts (setState-in-effect cascading render)
- src/i18n/I18nContext.tsx (react-refresh/only-export-components)
- src/pages/DocumentCreationPage.tsx:427 (no-empty)
- src/pages/DocumentsPage.tsx (setState-in-effect cascading render ×2)
- src/theme/ThemeContext.tsx (react-refresh/only-export-components)

Logged 2026-05-01 by 11-06 executor. Defer to a dedicated cleanup plan.
