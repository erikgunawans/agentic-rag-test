# Component Inventory

Maps Figma shared components to adapted versions in `src/components/shared/`.

## A. Shared Components (adapted from Figma)

| Component | Source | Adapted Path | Priority | Used By |
|---|---|---|---|---|
| IconRailNew | `_figma-source/src/app/components/shared/IconRailNew.tsx` | `components/shared/IconRailNew.tsx` | HIGH | All pages (global nav) |
| ColumnHeader | `_figma-source/src/app/components/shared/ColumnHeader.tsx` | `components/shared/ColumnHeader.tsx` | HIGH | All pages (panel headers) |
| SubHeader | `_figma-source/src/app/components/shared/SubHeader.tsx` | `components/shared/SubHeader.tsx` | HIGH | All panel sub-sections |
| HistoryRow | `_figma-source/src/app/components/shared/HistoryRow.tsx` | `components/shared/HistoryRow.tsx` | HIGH | All pages with history |
| HistorySection | `_figma-source/src/app/components/shared/HistorySection.tsx` | `components/shared/HistorySection.tsx` | HIGH | Creation, Comparison, Compliance, Analysis |
| DropZone | `_figma-source/src/app/components/shared/DropZone.tsx` | `components/shared/DropZone.tsx` | HIGH | Documents, Comparison, Compliance, Analysis |
| ActionButton | `_figma-source/src/app/components/shared/ActionButton.tsx` | `components/shared/ActionButton.tsx` | MEDIUM | All action panels |
| EmptyState | `_figma-source/src/app/components/shared/EmptyState.tsx` | `components/shared/EmptyState.tsx` | MEDIUM | All main content empty states |
| HintChipRow | `_figma-source/src/app/components/shared/HintChipRow.tsx` | `components/shared/HintChipRow.tsx` | MEDIUM | Empty states |
| SectionLabel | `_figma-source/src/app/components/shared/SectionLabel.tsx` | `components/shared/SectionLabel.tsx` | MEDIUM | Form sections |
| TextInput | `_figma-source/src/app/components/shared/TextInput.tsx` | `components/shared/TextInput.tsx` | LOW | Document creation forms |
| ComplianceStatusBadge | `_figma-source/src/app/components/shared/ComplianceStatusBadge.tsx` | `components/shared/ComplianceStatusBadge.tsx` | LOW | Compliance page only |
| AnalysisDepthControl | `_figma-source/src/app/components/shared/AnalysisDepthControl.tsx` | `components/shared/AnalysisDepthControl.tsx` | LOW | Analysis + Compliance pages |
| RiskBadge | `_figma-source/src/app/components/shared/RiskBadge.tsx` | `components/shared/RiskBadge.tsx` | LOW | Contract analysis page |

## B. shadcn/ui Components (installed via CLI)

These are installed fresh via `npx shadcn@latest add` using base-nova style (@base-ui/react).

| Component | File | Used For |
|---|---|---|
| badge | `components/ui/badge.tsx` | Document type pills, status chips |
| card | `components/ui/card.tsx` | Document grid cards |
| select | `components/ui/select.tsx` | Framework/law/type dropdowns |
| tooltip | `components/ui/tooltip.tsx` | IconRail hover labels |
| dialog | `components/ui/dialog.tsx` | Confirmations, modals |
| tabs | `components/ui/tabs.tsx` | View mode toggles |
| checkbox | `components/ui/checkbox.tsx` | Filter status, analysis types |
| radio-group | `components/ui/radio-group.tsx` | Output language selector |
| textarea | `components/ui/textarea.tsx` | Additional context fields |
| progress | `components/ui/progress.tsx` | Storage quota bar |
| dropdown-menu | `components/ui/dropdown-menu.tsx` | Document card options (three dots) |
| label | `components/ui/label.tsx` | Form field labels |
| popover | `components/ui/popover.tsx` | IconRail group flyout |
| avatar | `components/ui/avatar.tsx` | User presence, document avatars |
| toggle | `components/ui/toggle.tsx` | Individual toggles (auto-dep) |
| toggle-group | `components/ui/toggle-group.tsx` | Analysis depth, view mode |
| switch | `components/ui/switch.tsx` | Toggle options |

## C. Components EXCLUDED

| Component | Reason |
|---|---|
| All `_figma-source/src/app/components/ui/*` | Use shadcn CLI base-nova versions instead (Figma uses @radix-ui directly) |
| FormVariantsReference | Design documentation only |
| TextInputStates | Design documentation only |
| ComplianceStatusReference | Design documentation only |
| AnalysisControlsReference | Design documentation only |
| KnowledgeHubOverview | Navigation map, not a real screen |
| IconRailReference | Design documentation only |
| ColumnHeaderReference | Design documentation only |
| HistorySectionReference | Design documentation only |
| IconRailGroupReference | Design documentation only |
| IconRailMaster | Demo variant |
| IconRail (original) | Superseded by IconRailNew |
| figma/ImageWithFallback | Figma-specific utility |

## D. Existing Components (unchanged)

These existing components continue to provide functionality and will be visually restyled during the UI redesign:

| Component | Path | Keeps |
|---|---|---|
| Button | `components/ui/button.tsx` | All variants |
| Input | `components/ui/input.tsx` | Form inputs |
| Separator | `components/ui/separator.tsx` | Dividers |
| ScrollArea | `components/ui/scroll-area.tsx` | Custom scrolling |
| Skeleton | `components/ui/skeleton.tsx` | Loading states |
| AuthGuard | `components/auth/AuthGuard.tsx` | Route protection |
| AdminGuard | `components/auth/AdminGuard.tsx` | Admin protection |
| All chat/* | `components/chat/*.tsx` | Chat functionality |
| All documents/* | `components/documents/*.tsx` | Document management |
