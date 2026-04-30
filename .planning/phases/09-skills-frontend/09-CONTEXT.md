# Phase 9: Skills Frontend - Context

**Gathered:** 2026-05-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Build the complete Skills page UI — navigation tab, searchable skill list, two-column layout (list + inline editor), skill file management section, and a slide-in file preview panel. All backend APIs (CRUD, file upload/delete/preview, share/export/import) are fully shipped from Phases 7 and 8. This phase is **pure frontend**.

**Deliverables:**
1. `frontend/src/pages/SkillsPage.tsx` — Full Skills page with two-column layout
2. `frontend/src/components/layout/IconRail.tsx` patch — Add Skills standalone nav item (`Zap` icon, `/skills` path)
3. `frontend/src/App.tsx` patch — Register `/skills` route
4. `frontend/src/i18n/` — Add `nav.skills` translation key (ID + EN)

**Out of scope (explicitly deferred):**
- Code execution sandbox UI — Phase 11
- Persistent tool memory UI — Phase 11
- Skill analytics / versioning — future milestone
- Binary file rich preview (PDF render, image thumbnail) — deferred per REQUIREMENTS.md

</domain>

<decisions>
## Implementation Decisions

### Navigation

- **D-P9-01:** `Skills` is added as a **standalone item** in `standaloneItems[]` in `IconRail.tsx` — same tier as Chat, Dashboard, BJR, and PDP. Not grouped. Matches PRD's "third top-level tab" intent and maximizes discoverability.
- **D-P9-02:** Lucide icon: **`Zap`** — suggests capability/power-up ("agent superpowers"). Import alongside existing icons in `IconRail.tsx`.
- **D-P9-03:** Position in `standaloneItems[]`: **after Chat (`/`), before Dashboard** — final order: `/ → /skills → /dashboard → /bjr → /pdp`. Skills lives adjacent to Chat since it directly enhances the chat experience.
- **D-P9-04:** Route: `path="skills"`, labelKey: `nav.skills`. Register in `App.tsx` alongside other AppLayout child routes.

### Page Layout

- **D-P9-05:** Two-column layout following the `ClauseLibraryPage` structural analog — searchable skill list on the left, inline editor panel on the right. No separate modal for editing.
- **D-P9-06:** "Create Manually" opens the **right editor panel in create mode** (not a modal dialog). Same panel is reused for both create and edit — `editMode: 'create' | 'edit' | null` state machine, consistent with `ClauseLibraryPage`.

### File Preview Panel

- **D-P9-07:** File preview **overlays the editor panel as a floating drawer** — NOT a third column. The editor stays mounted behind it. Opens when user clicks a file row; closes on the × button or backdrop click.
- **D-P9-08:** Text file content rendered in a scrollable **monospace `<pre>` block**. Binary files show a "Binary file — cannot preview" message with a Download button. (PRD §Feature 2 §UI specifies this pattern explicitly.)

### Skill Creation — Three Paths

- **D-P9-09:** "Create with AI" navigates to the Chat page with the following message pre-populated in the chat input: **`"I want to create a new skill."`** — simple enough for the `skill-creator` skill to catch via the catalog, without over-specifying the invocation.
- **D-P9-10:** After the LLM saves a new skill via `save_skill` in chat, the Skills page **auto-refreshes on mount** — data fetched fresh whenever `SkillsPage` mounts. No cross-page state invalidation or URL param needed.

### Global Skill View State

- **D-P9-11:** When a user selects a **global skill they do not own**: all form inputs are **disabled** (visually grayed), an info banner appears at the top of the editor ("Global skill — view only"), and the action buttons show **only [Export] and [Try in Chat]**. No Save, Delete, or Share buttons.
- **D-P9-12:** When the user IS the **creator** of a shared global skill (`created_by === currentUser.id` and `user_id IS NULL`): same disabled inputs + banner + **[Unshare] button**. Clicking Unshare calls `PATCH /skills/{id}/share`, re-fetches the skill, and unlocks the editor (skill becomes private again).
- **D-P9-13:** For the user's own **private skills**: full editor — all inputs enabled, action buttons: [Save] [Delete] [Share] [Export] [Try in Chat].

### "Try in Chat"

- **Claude's Discretion:** The exact pre-populated message for the "Try in Chat" button. It should reference the skill by name to trigger loading (e.g., `"Please use the [skill-name] skill."` or similar). Choose the most natural phrasing that matches how `load_skill` discovery works from the system prompt catalog.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Primary Specification
- `docs/PRD-skill.md` §Feature 1 §UI — Page layout (two-column), skill list, editor fields, three creation paths, "Try in Chat" behavior, ownership model badges
- `docs/PRD-skill.md` §Feature 2 §UI — File list in editor, upload button visibility rule (own skills only), file preview panel behavior (text inline vs. binary + download)

### Requirements
- `.planning/REQUIREMENTS.md` §SKILL-11 — "Skills" tab in top navigation
- `.planning/REQUIREMENTS.md` §SFILE-04 — File preview panel: slide-in, copy + download buttons

### Roadmap
- `.planning/ROADMAP.md` §Phase 9 — 5 success criteria (authoritative scope anchor)

### Prior Phase Decisions (binding)
- `.planning/phases/07-skills-database-api-foundation/07-CONTEXT.md` — D-P7-01..14: ownership model (`user_id IS NULL` = global, `created_by` = immutable creator), sharing rules (D-P7-02/03: creator can unshare, no one can edit a global skill), RLS patterns, file schema
- `.planning/phases/08-llm-tool-integration-discovery/08-CONTEXT.md` — D-P8-01..13: catalog format, `load_skill` response schema (includes files table), `save_skill` conflict behavior, `read_skill_file` tool and mime-type classification

### Codebase Conventions
- `.planning/codebase/CONVENTIONS.md` — Router skeleton, response format, audit pattern, Pydantic validator usage
- `frontend/src/pages/ClauseLibraryPage.tsx` — **Closest structural analog** (list-left / editor-right, `editMode` state, `apiFetch`, `useSidebar`, `useI18n`). Reuse its CSS class patterns (`inputBase`, `inputClass`, `textareaClass`) and layout structure.
- `frontend/src/components/layout/IconRail.tsx` — `standaloneItems[]` array to extend (lines 25–30); follow the existing `NavItem` shape
- `frontend/src/App.tsx` — Route tree; add `<Route path="skills" element={<SkillsPage />} />` alongside other AppLayout children

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `ClauseLibraryPage.tsx` — Full list+editor pattern: left panel with search/filter, right panel with form, `editMode: 'create' | 'edit' | null`, `useSidebar`, `useI18n`, `apiFetch`. Copy the two-column layout skeleton wholesale and adapt.
- `IconRail.tsx:25-30` (`standaloneItems`) — Extend this array with `{ path: '/skills', icon: Zap, labelKey: 'nav.skills' }`. Import `Zap` from `lucide-react`.
- `apiFetch` from `@/lib/api` — All API calls use this; handles auth headers automatically.
- `useSidebar` hook — Panel collapse behavior; already used in ClauseLibraryPage.
- `useI18n` hook — Translation lookups; add `nav.skills` key to both language files.
- shadcn/ui `Button`, `Badge`, `Switch` — Already installed; use for action buttons, global/disabled badges, enabled toggle.

### Established Patterns
- **List + inline editor** — `ClauseLibraryPage` is the canonical pattern: no modal, editor panel on right, state machine `editMode: null | 'create' | 'edit'`.
- **Global badge** — Other pages use a small badge for global/shared items. Match the existing style (see clause library).
- **`apiFetch` + `useCallback` + `useEffect` with debounce** — Search input debouncing (300ms) used in ClauseLibraryPage; reuse for skill search.
- **Design system** — 2026 Calibrated Restraint: zinc-neutral base, purple accent. No `backdrop-blur` on persistent panels. No gradients. Flat solid buttons.
- **Form duplication note** — CLAUDE.md warns that `DocumentCreationPage` has both mobile and desktop panels. For `SkillsPage`, ClauseLibraryPage's single-panel approach (mobile overlay via `mobilePanelOpen` state) is the correct pattern to follow instead.

### Integration Points
- **Skills API** (all from `backend/app/routers/skills.py`):
  - `GET /skills` — list (supports `?search=`, `?is_global=`, `?is_enabled=`, `?limit=`)
  - `POST /skills` — create (body: `{name, description, instructions, enabled?}`)
  - `PATCH /skills/{id}` — update (own skills only; 403 for global)
  - `DELETE /skills/{id}` — delete (own skills only)
  - `PATCH /skills/{id}/share` — toggle global/private (creator only)
  - `GET /skills/{id}/export` — download ZIP (StreamingResponse)
  - `POST /skills/import` — import from ZIP (multipart/form-data)
  - `POST /skills/{id}/files` — upload file (multipart/form-data, 10 MB per-file cap)
  - `DELETE /skills/{id}/files/{file_id}` — delete file
  - `GET /skills/{id}/files/{file_id}/content` — get text content or binary metadata
- **Chat navigation** — `useNavigate()` from react-router-dom; navigate to `/` with a `state.prefill` or query param pattern to pre-populate the chat input for "Create with AI" and "Try in Chat" flows. Check how `ChatPage` accepts pre-populated messages (if not implemented, implement simple `?message=` query param read on mount).

</code_context>

<specifics>
## Specific Ideas

- **"Create with AI" exact prefill:** `"I want to create a new skill."` — this is the exact string to set in the chat input when navigating to chat for AI-guided creation.
- **Unshare action:** Only visible when `selectedSkill.created_by === currentUser.id && selectedSkill.user_id === null`. This check identifies "I am the creator and the skill is currently global."
- **Icon import:** `Zap` is not currently imported in `IconRail.tsx` — needs to be added to the destructured Lucide import at line 3.
- **Disabled state visual:** Use Tailwind `opacity-60 pointer-events-none` or native `disabled` attribute on inputs — keep consistent with what's used elsewhere (shadcn/ui `disabled` prop on `Input`/`Textarea`).

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 9-Skills Frontend*
*Context gathered: 2026-05-01*
