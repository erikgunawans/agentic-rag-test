---
phase: 9
slug: skills-frontend
status: approved
shadcn_initialized: true
preset: base-nova (neutral baseColor, lucide icons, cssVariables)
created: 2026-05-01
---

# Phase 9 — UI Design Contract: Skills Frontend

> Visual and interaction contract for the Skills page (list + inline editor + floating file preview drawer). All values are pre-populated from the existing 2026 Calibrated Restraint design system declared in `frontend/src/index.css` and the structural analog `ClauseLibraryPage.tsx`. No new tokens are introduced — this contract reuses the project's locked design system.

---

## Design System

| Property | Value |
|----------|-------|
| Tool | shadcn |
| Preset | `base-nova` style, `neutral` baseColor, cssVariables enabled (from `frontend/components.json`) |
| Component library | shadcn/ui (Button, Badge, Switch, Input, Textarea, Select, Popover) + base-ui (tooltips via the `asChild → render` shim in `tooltip.tsx`) |
| Icon library | lucide-react |
| Font | `Geist Variable` (sans + heading) — declared in `index.css` `--font-sans` |

**Source:** `frontend/components.json`, `frontend/src/index.css` lines 4–11.

---

## Spacing Scale

Declared values (multiples of 4) — taken from the project's existing Tailwind defaults and the patterns in `ClauseLibraryPage.tsx`:

| Token | Value | Usage in this phase |
|-------|-------|---------------------|
| xs | 4px (`gap-1`, `py-0.5`) | Badge inner padding, icon-to-label gap inside row |
| sm | 8px (`gap-2`, `py-2`) | Compact inline gaps; stacked label + input gap (`space-y-1.5` ≈ 6px is the editor exception, see below) |
| md | 12px (`px-3`, `py-3`) | List header padding, panel header strip; row vertical padding |
| md+ | 16px (`px-4`, `py-4`) | Editor form section padding |
| lg | 20px (`px-5`) | Outer panel padding (matches `ClauseLibraryPage` `px-5 py-4`) |
| xl | 24px (`p-6`) | Main content area padding (right column outside the editor) |

**Exceptions (locked, must match `ClauseLibraryPage`):**
- Form field `space-y-1.5` (6px) between label and control — keeps form density readable at the page's `text-xs` body size.
- Skill list row vertical padding: `py-2.5` (10px) — between `py-2` and `py-3`. Justified because the row contains two stacked text lines (name + description preview) plus an inline badge.
- Mobile FAB: `h-12 w-12` (48px) — touch target floor, locked by `ClauseLibraryPage` precedent.

---

## Typography

All sizes lifted directly from `ClauseLibraryPage.tsx`. Page weight uses the `Geist Variable` font's 400 / 500 / 600 axes only.

| Role | Size | Weight | Line Height | Where used |
|------|------|--------|-------------|------------|
| Page title | 14px (`text-sm`) | 600 (`font-semibold`) | 1.4 (default) | Skill list header (`Skills` / count) |
| Body | 12px (`text-xs`) | 400 | 1.5 (default) | Skill row name; editor button labels; banner text |
| Form label | 10px (`text-[10px]`) | 500 (`font-medium`) | 1.4 | Field labels above inputs |
| Meta / count | 10px (`text-[10px]`) | 400 | 1.4 | "N skills" subhead; description preview line under name |
| Badge | 9px (`text-[9px]`) | 700 uppercase OR 400 lowercase | 1 | "GLOBAL" / "DISABLED" / category-style chips |
| Code / instructions textarea | 12px (`text-xs`) | 400 | 1.5 | Monospace `<pre>` blocks for `instructions` field and file preview |

**Constraints:**
- No additional sizes introduced. The four roles (title 14 / body 12 / label 10 / badge 9) match every other CRUD page in the app.
- Headings inside the editor use `text-xs font-semibold` (matches `ClauseLibraryPage` line 160).
- File preview `<pre>` block uses `font-mono text-xs leading-relaxed` (1.625) — slightly looser than body to aid code scanning.

---

## Color

All colors come from `index.css` `:root` (light) and `.dark` blocks. Both themes are first-class — every value below has a corresponding dark-mode token.

| Role | CSS variable | OKLCH (light) | OKLCH (dark) | Usage |
|------|--------------|---------------|--------------|-------|
| Dominant (60%) | `--background` | `oklch(0.975 0.003 80)` | `oklch(0.13 0.008 280)` | Page background, main content area |
| Secondary (30%) | `--sidebar` / `--card` | `oklch(0.975 0.006 80)` / `oklch(0.995 0.001 80)` | `oklch(0.15 0.007 280)` / `oklch(0.18 0.006 280)` | Left list panel (`bg-sidebar`), file preview drawer (`bg-card`) |
| Accent (10%) | `--primary` | `oklch(0.48 0.18 280)` (purple) | `oklch(0.55 0.20 280)` | Reserved set below |
| Destructive | `--destructive` | `oklch(0.55 0.22 25)` (red) | `oklch(0.65 0.20 25)` | Delete button hover state, Delete confirmation banner, required-field asterisk |
| Muted surface | `--muted` / `--secondary` | `oklch(0.94 0.005 80)` | `oklch(0.23 0.005 280)` | Input backgrounds (`bg-secondary`), badge backgrounds, hover states on rows |
| Muted text | `--muted-foreground` | `oklch(0.40 0.01 260)` | `#A1A1AA` | Description preview, "N skills" count, file size, placeholder text |
| Border | `--border` | `oklch(0 0 0 / 8%)` | `oklch(1 0 0 / 8%)` | All separators, input borders, panel divider — always at `/50` opacity for inner panel separators per `ClauseLibraryPage` (`border-border/50`) |

### Accent (purple) reserved for ONLY these elements (locked):

1. **Primary action buttons** — `[Save]` (default Button variant), `[Create Skill]` (FAB and "+ New Skill" CTA in left panel header), `[Try in Chat]` (default Button variant).
2. **Active nav state** — Skills icon in `IconRail` when route matches (`bg-primary/15 text-primary` + 3px gradient stripe — already locked in `railButtonClass`).
3. **Selected skill row** in the list — `bg-primary/10 text-primary` (matches `GroupPopover` child link active style at IconRail.tsx:125).
4. **GLOBAL badge** — `text-primary` with `Globe` icon (matches `ClauseLibraryPage:321` precedent).
5. **Form field focus ring** — `focus:ring-1 focus:ring-ring` where `--ring = --primary` (already in `inputBase`).
6. **Required-field marker** — destructive red asterisk (NOT primary purple) — `text-red-600 dark:text-red-400`, matches `ClauseLibraryPage:164`.
7. **Selected file row** in the editor's file list (when its preview drawer is open) — same `bg-primary/10 text-primary` treatment as the skill row.

**Forbidden uses of accent:**
- NOT on the [Delete] button (use destructive treatment on hover only).
- NOT on the [Share]/[Unshare] button (neutral outline button — `Button variant="outline"`).
- NOT on the [Export] button (neutral outline button).
- NOT on the [Disabled] badge (use `bg-muted text-muted-foreground`).
- NOT on form input borders unless focused.

### Project-binding constraints

- **NO `backdrop-blur` on persistent panels** — the left skill list and right editor MUST use solid `bg-sidebar` and `bg-background`. Confirmed by CLAUDE.md.
- **`backdrop-blur` ALLOWED on the file preview drawer's backdrop overlay only** (transient). Use the existing `.mobile-backdrop` class or its `bg-black/40 backdrop-blur-sm` pattern.
- **NO gradient buttons** — flat solid only. The 3px active-nav stripe gradient (`from-primary to-[var(--gradient-accent-to)]`) is the ONE allowed gradient and is already shipped in `IconRail.tsx`.
- **Light + dark theme parity required** — every color reference must use a CSS variable, never a hardcoded hex.

---

## Copywriting Contract

All user-facing strings ship in BOTH Indonesian (`id`, default) and English (`en`) via `frontend/src/i18n/translations.ts`. Translation keys are prescribed below.

### Navigation
| Element | Translation key | EN copy | ID copy |
|---------|-----------------|---------|---------|
| Sidebar nav label | `nav.skills` | `Skills` | `Skill` |

### Page header
| Element | Key | EN | ID |
|---------|-----|------|------|
| Page title | `skills.title` | `Skills` | `Skill` |
| List subhead (count) | — | `{n} skills` | `{n} skill` |

### Primary CTAs (purple)
| Element | Key | EN | ID |
|---------|-----|------|------|
| New skill (split button trigger in left panel) | `skills.new` | `+ New Skill` | `+ Skill Baru` |
| Save (in editor footer) | `skills.save` | `Save` | `Simpan` |
| Try in Chat | `skills.tryInChat` | `Try in Chat` | `Coba di Chat` |

### Secondary CTAs (outline buttons)
| Element | Key | EN | ID |
|---------|-----|------|------|
| Cancel (close create/edit) | `skills.cancel` | `Cancel` | `Batal` |
| Share (publish private to global) | `skills.share` | `Share` | `Bagikan` |
| Unshare (revoke global) | `skills.unshare` | `Unshare` | `Berhenti Bagikan` |
| Export ZIP | `skills.export` | `Export` | `Ekspor` |
| Import from ZIP | `skills.import` | `Import` | `Impor` |
| Create with AI | `skills.createWithAI` | `Create with AI` | `Buat dengan AI` |
| Create Manually | `skills.createManual` | `Create Manually` | `Buat Manual` |
| Import from File | `skills.importFile` | `Import from File` | `Impor dari File` |

### Destructive
| Element | Key | EN | ID |
|---------|-----|------|------|
| Delete button label | `skills.delete` | `Delete` | `Hapus` |
| Delete confirmation prompt | `skills.deleteConfirm` | `Delete this skill? This cannot be undone.` | `Hapus skill ini? Tindakan ini tidak dapat dibatalkan.` |
| Unshare confirmation prompt | `skills.unshareConfirm` | `Unshare this skill? It will become private and other users will lose access.` | `Berhenti membagikan skill ini? Skill akan menjadi privat dan pengguna lain kehilangan akses.` |
| Delete file confirmation | `skills.fileDeleteConfirm` | `Delete this file from the skill?` | `Hapus file ini dari skill?` |

### Empty states
| Surface | Key | EN | ID |
|---------|-----|------|------|
| Skill list empty (no skills at all) | `skills.empty` | **Heading:** `No skills yet`<br>**Body:** `Create your first skill to teach the AI a reusable behavior, or try the built-in skill-creator skill.` | **Heading:** `Belum ada skill`<br>**Body:** `Buat skill pertama Anda untuk mengajari AI perilaku yang dapat digunakan ulang, atau coba skill bawaan skill-creator.` |
| Skill list empty (search returned nothing) | `skills.emptySearch` | `No skills match "{query}"` | `Tidak ada skill cocok dengan "{query}"` |
| Editor empty (no skill selected) | `skills.editorEmpty` | **Heading:** `Select a skill`<br>**Body:** `Pick a skill from the list to view or edit, or create a new one.` | **Heading:** `Pilih skill`<br>**Body:** `Pilih skill dari daftar untuk melihat atau mengedit, atau buat yang baru.` |
| File list empty (skill has no attached files) | `skills.filesEmpty` | `No files attached. {Upload action visible only for own skills}` | `Belum ada file. {Aksi upload hanya untuk skill milik sendiri}` |

### Error states
| Surface | Key | EN | ID |
|---------|-----|------|------|
| Save failed | `skills.errorSave` | `Could not save skill. Check your connection and try again.` | `Gagal menyimpan skill. Periksa koneksi Anda dan coba lagi.` |
| Delete failed | `skills.errorDelete` | `Could not delete skill. Refresh and try again.` | `Gagal menghapus skill. Muat ulang dan coba lagi.` |
| Upload failed (over 10 MB) | `skills.errorFileSize` | `File exceeds the 10 MB limit.` | `Ukuran file melebihi batas 10 MB.` |
| Upload failed (network) | `skills.errorUpload` | `Could not upload file. Try again.` | `Gagal mengunggah file. Coba lagi.` |
| Import failed | `skills.errorImport` | `Could not import ZIP. Check the file format and try again.` | `Gagal mengimpor ZIP. Periksa format file dan coba lagi.` |
| Name conflict on create | `skills.errorNameConflict` | `A skill with this name already exists. Choose a different name.` | `Skill dengan nama ini sudah ada. Pilih nama lain.` |
| Name format invalid | `skills.errorNameFormat` | `Use lowercase letters, numbers, and hyphens only (e.g. legal-review).` | `Gunakan huruf kecil, angka, dan tanda hubung saja (mis. legal-review).` |

### Banners
| Surface | Key | EN | ID |
|---------|-----|------|------|
| Global skill — view only | `skills.bannerGlobal` | `Global skill — view only. Other users see this skill in their catalog.` | `Skill global — hanya tampilan. Pengguna lain melihat skill ini di katalog mereka.` |
| Global skill (you are creator) | `skills.bannerOwnerGlobal` | `Global skill — view only. You can unshare to edit it again.` | `Skill global — hanya tampilan. Anda dapat berhenti membagikan untuk mengedit kembali.` |

### Pre-populated chat messages (locked from CONTEXT.md D-P9-09 + Discretion)
| Trigger | Exact prefill string (locked) |
|---------|-------------------------------|
| Create with AI | `"I want to create a new skill."` |
| Try in Chat | `"Please use the {skill-name} skill."` (substitute the skill's slug name) |

### Required-field markers
- Visual: `*` rendered in destructive red after the label text (`<span className="text-red-600 dark:text-red-400">*</span>` — matches `ClauseLibraryPage:164`).
- Required fields: `name`, `description`, `instructions`. `enabled` toggle is binary (no required mark needed). License / compatibility / metadata are optional.

### Character counters (PRD §Feature 1 §UI requires this on `description`)
- Description field: live counter `{n}/1024` in `text-[9px] text-muted-foreground` aligned bottom-right of the textarea container. Turns destructive red at `n > 1024`.
- Name field: live counter `{n}/64` same treatment.
- No counter on `instructions` (uncapped textarea).

---

## Component Inventory

Components consumed in this phase. All come from existing locations — no new shadcn `add` commands required.

| Component | Source | Where used |
|-----------|--------|------------|
| `Button` | `@/components/ui/button` | All action buttons (Save, Delete, Share, Unshare, Export, Try in Chat, Cancel, Upload) |
| `Badge` | `@/components/ui/badge` | `GLOBAL` badge, `DISABLED` badge, file MIME-type badge |
| `Switch` | `@/components/ui/switch` | `enabled` toggle in editor footer |
| `Input` | `@/components/ui/input` (or raw `<input className={inputClass}>`) | Name, description (single-line if needed), search box, license, compatibility |
| `Textarea` | `@/components/ui/textarea` (or raw `<textarea className={textareaClass}>`) | Description (multi-line), instructions (monospace) |
| `Tooltip` | `@/components/ui/tooltip` (base-ui-backed) | Icon-only buttons (delete row icon, file row delete icon, copy/download buttons in preview drawer) |
| `Popover` | `@/components/ui/popover` | "+ New Skill" split-button menu (Manual / AI / Import) |
| `Dialog` (optional) | `@/components/ui/dialog` if available, else `window.confirm()` | Delete confirmation, Unshare confirmation, file delete confirmation |

**Confirmation pattern:** `ClauseLibraryPage` uses native `window.confirm()` (line 141). For consistency, Phase 9 uses `window.confirm()` for delete/unshare/file-delete in v1. Custom Dialog component upgrade is **deferred** — out of scope.

**Icons (lucide-react):**
- Nav: `Zap` (locked, D-P9-02). Add to import line in `IconRail.tsx`.
- Action icons: `Plus`, `Pencil`, `Trash2`, `Save`, `Download`, `Upload`, `Share2`, `X`, `Search`, `Globe` (global badge), `FileText`, `FileCode`, `File` (binary fallback), `Copy`, `Sparkles` (Create with AI), `Upload` or `FileArchive` (Import from File), `MessageSquare` (Try in Chat).

---

## Layout & Structural Contract

### Page-level (matches `ClauseLibraryPage` skeleton)

```
┌──────────────────────────────────────────────────────────────┐
│ IconRail (60px, fixed)                                       │
├────────────┬──────────────────────────────────────────────────┤
│ Skill list │ Editor / empty state                             │
│ panel      │                                                  │
│ 340px      │ [scrollable, max-w-[900px] inside]               │
│ bg-sidebar │ p-6                                              │
│ border-r   │                                                  │
│ border-    │                                                  │
│ border/50  │                                                  │
└────────────┴──────────────────────────────────────────────────┘
```

- Left panel (`hidden md:flex w-[340px]`) collapses via `useSidebar().panelCollapsed` — same hook as `ClauseLibraryPage`.
- Mobile breakpoint (`< md`, i.e. `< 768px`): left panel becomes a slide-in overlay triggered by FAB at `bottom-4 right-4` (`h-12 w-12 rounded-full bg-primary`). Uses `.mobile-backdrop` + `.mobile-panel` classes already defined in `index.css`.
- Header strip: `px-5 py-3 border-b border-border/50` containing title + count + collapse button — verbatim copy from `ClauseLibraryPage:283–294`.

### Skill list rows

```
┌─────────────────────────────────────────┐  ← row container
│ skill-name              [GLOBAL] [⚪]    │  ← name + badges (right-aligned)
│ Description first line, truncated to t… │  ← muted preview, line-clamp-1
└─────────────────────────────────────────┘
   px-3 py-2.5 (10px vertical padding)
   border-b border-border/50 between rows
   hover:bg-muted/50 (idle)
   bg-primary/10 text-primary when selected
   focus-visible: focus-ring class
```

- Row height: ~52px at default font sizing — comfortable two-line density without feeling sparse.
- Click anywhere on the row enters edit mode for owned skills; for global view-only skills enters view mode.
- Disabled toggle indicator (the `[⚪]` glyph above): a tiny `Switch` thumb at 9px, visible-but-not-interactive in the row. The actual control is in the editor.

### Skill editor (right column)

Form layout, matching `ClauseLibraryPage:158-216` density (`px-5 py-4 space-y-3`):

```
┌── Editor header ──────────────────────────────────────────┐
│ Edit "skill-name"                                     [×] │  text-xs font-semibold
├───────────────────────────────────────────────────────────┤
│ [BANNER if global view-only — see banners section]        │
│                                                           │
│ Name *                       [n/64]                       │
│ [______________________________________]                  │  inputClass
│                                                           │
│ Description *                [n/1024]                     │
│ [______________________________________]                  │  textareaClass min-h-[80px]
│ [______________________________________]                  │
│                                                           │
│ Instructions                                              │
│ [______________________________________]  font-mono       │  textareaClass min-h-[240px]
│ [______________________________________]                  │
│                                                           │
│ License (optional)        Compatibility (optional)        │
│ [_____________]           [_____________]                 │  grid grid-cols-2 gap-2
│                                                           │
│ ─── Building Block Files ─────────────────────── [Upload] │  section header + upload (own only)
│ ┌──────────────────────────────────────────────────────┐  │
│ │ 📄 legal-clauses.md       12 KB         text/markdown │  │  file row, 36px tall
│ │ 📄 contract-template.pdf  142 KB        application/… │  │
│ │ (empty: "No files attached.")                         │  │
│ └──────────────────────────────────────────────────────┘  │
│                                                           │
│ ─── Footer (sticky bottom) ──────────────────────────── ──│
│ Enabled  [Switch]                                         │  left side
│                                                           │
│ Action buttons (right-aligned, see ownership matrix below)│
│ [Save] [Delete] [Share] [Export] [Try in Chat]            │
└───────────────────────────────────────────────────────────┘
```

### Ownership × button matrix (locked from CONTEXT.md D-P9-11..13)

| State | Inputs | Banner | Visible buttons |
|-------|--------|--------|-----------------|
| Own private skill | enabled | none | `[Save]` `[Delete]` `[Share]` `[Export]` `[Try in Chat]` |
| Global skill, you are creator (`created_by === me && user_id === null`) | disabled (`opacity-60 pointer-events-none`) + native `disabled` on form controls | `skills.bannerOwnerGlobal` (info) | `[Unshare]` `[Export]` `[Try in Chat]` |
| Global skill, you are not creator | disabled (`opacity-60 pointer-events-none`) + native `disabled` | `skills.bannerGlobal` (info) | `[Export]` `[Try in Chat]` |
| Create mode (no skill loaded) | enabled, blank | none | `[Save]` `[Cancel]` |

**Disabled rendering rule:** apply BOTH `opacity-60 pointer-events-none` to the form wrapper AND native `disabled` attribute on each control. Reasoning: opacity gives the visual signal at a glance; native disabled prevents tabbing into the field and announces "disabled" to screen readers. (Recommended in CONTEXT.md `<specifics>`.)

**Banner visual:** full-width strip at top of editor body, `bg-primary/10 text-primary text-xs px-4 py-2 rounded-md border border-primary/20` with an inline `Globe` icon. Info severity, NOT destructive — it's a state notice, not a warning.

### File list rows (inside editor)

```
┌─────────────────────────────────────────────────────────────┐
│ 📄 filename.ext       12 KB        text/markdown      [×]   │  36px tall
└─────────────────────────────────────────────────────────────┘
   px-3 py-2 hover:bg-muted/50 cursor-pointer (clickable text files only)
   border-b border-border/50 between rows
   bg-primary/10 text-primary when its preview drawer is open
   font-mono icons match MIME type:
     text/* → FileText
     application/* (text-readable) → FileCode
     other → File
   File size formatter: <1KB show bytes; <1MB show "N KB" rounded; ≥1MB show "N.M MB"
   Trash icon visible only for own skills (matches upload visibility rule)
```

Click target rules:
- Text files (`mime_type.startsWith("text/")` per D-P8-11) → entire row is clickable, opens preview drawer.
- Binary files → row is clickable, opens preview drawer with binary state (no content, just download).
- Trash icon click does NOT open the preview drawer (`stopPropagation`).

### File preview drawer (locked from D-P9-07/08)

Floating overlay on top of the editor — NOT a third column.

```
                                  ┌── 480px wide ─────────────────┐
                                  │ filename.ext  [Copy] [⬇] [×]  │  46px header strip
                                  ├───────────────────────────────┤
                                  │                               │
                                  │ <pre class="font-mono text-xs │
                                  │   leading-relaxed whitespace- │
                                  │   pre-wrap break-words p-4">  │
                                  │   ...file contents...         │
                                  │ </pre>                        │
                                  │                               │
                                  │ — OR — for binary —           │
                                  │ ┌─────────────────────────┐   │
                                  │ │ 📦  Binary file —       │   │
                                  │ │     cannot preview      │   │
                                  │ │     [Download]          │   │
                                  │ └─────────────────────────┘   │
                                  └───────────────────────────────┘
```

**Specifics:**
- Width: `w-[480px]` desktop, `w-full` on mobile (full-screen takeover below `md`).
- Position: `fixed inset-y-0 right-0 z-40 bg-card border-l border-border shadow-lg`.
- Backdrop: `fixed inset-0 z-30 bg-black/40 backdrop-blur-sm` (transient overlay — backdrop-blur ALLOWED here per CLAUDE.md).
- Animation:
  - Open: `translate-x-full → translate-x-0` over `200ms cubic-bezier(0.4, 0, 0.2, 1)` (matches `interactive-lift` ease).
  - Close: reverse, same duration.
  - Use Tailwind utilities: `data-[state=open]:translate-x-0 data-[state=closed]:translate-x-full transition-transform duration-200 ease-out`.
- Header: `px-4 py-3 border-b border-border/50 flex items-center justify-between gap-2`. Title is the bare filename, `text-xs font-semibold truncate`.
- Action icons (right): `Copy`, `Download`, `X` — each a 7×7 button with tooltip. `Copy` button must:
  - Default state: `Copy` icon
  - Success state: `Check` icon for 1.5s, then revert (matches common copy-to-clipboard UX)
- Content area: `flex-1 overflow-auto`. For text files: `<pre>` block as specified. For binary: centered card with `File` icon at 40×40, message text, and a primary `[Download]` button.
- File size cap: still respect the 8000-char truncation rule from D-P8-12 — show truncation banner at bottom: `Showing first 8,000 characters. {Download} for full file.`
- Close triggers (in priority): (1) `×` button click, (2) `Escape` key, (3) backdrop click. All three close on the same animation.

---

## Interaction & State Contract

### State machine: editor

```
            (mount)
              │
              ▼
       ┌──────────────┐  click "+ New Skill > Create Manually"
       │   editMode   ├───────────────────────────────────────► editMode = 'create'
       │    = null    │                                             form blanked
       │ (empty state)│  click row                                  inputs enabled
       │              ├──► editMode = 'edit', editingSkill = row
       └──────────────┘    + load full skill via GET /skills/{id}
                                 │
                                 ▼
                          ownership branch:
                            own_private → full editor
                            own_global  → disabled + Unshare
                            other_global → disabled + view-only
```

**Auto-refresh on mount (D-P9-10):** `useEffect(() => { fetchSkills() }, [])` on `SkillsPage` mount. No cross-page invalidation needed.

### State machine: file preview drawer

```
            (closed, default)
                │
                │ click file row
                ▼
        ┌──────────────┐                      animate slide-in
        │ openingFile  │ ◄────────────────────  GET /skills/{id}/files/{file_id}/content
        │  = file_id   │                       (loading state for ~200ms)
        │              │                            │
        └──────────────┘ ◄────────  ─────────  ┌────▼────┐
                ▲    │                         │ loaded  │
                │    │ Esc / × / backdrop      │ content │
                │    │ animate slide-out       │ rendered│
                │    ▼                         └─────────┘
            (closed)
```

**Body scroll lock:** when drawer is open, set `overflow: hidden` on `document.body` (matches industry convention for transient overlays).

### Search debounce

- 300ms debounce on the search input (verbatim from `ClauseLibraryPage:80`).
- Search filters by `name` and `description`. The backend already supports `?search=` (Phase 7 endpoint).

### Loading states

| Surface | Treatment |
|---------|-----------|
| Initial skill list load | Render 5 shimmer placeholder rows (`<div className="shimmer h-[52px] rounded-md mx-3 my-1" />`). The `.shimmer` utility is pre-defined in `index.css:417-427`. |
| Skill detail load (after row click) | Editor body shows `<div className="shimmer h-[400px] rounded-md" />` covering the full form area. Header strip stays solid. |
| File preview load | `<div className="shimmer h-full m-4" />` inside the drawer body until content arrives. |
| File upload in progress | Inline progress strip below the Upload button: `bg-primary h-0.5 w-full transition-[width]` driven by XHR progress event. Upload button shows `Uploading…` label and spinner icon (`Loader2` with `animate-spin`). |
| Save in progress | Save button shows `Saving…` label + `Loader2` icon, button is `disabled` (matches `ClauseLibraryPage:208-210`). |
| Delete in progress | Delete button disabled with `Loader2` icon. After success, list refreshes and editor returns to empty state. |
| Import ZIP in progress | Modal-style overlay with central card showing `Loader2` and progress text `Importing… {n}/{total} skills`. After completion, show summary card: `{created_count} created, {error_count} errors. {Close}`. Errors listed inline with skill name. |

### Error handling

Match the project's existing error pattern (`alert()` or inline banner). For Phase 9:
- Save / Delete / Upload errors: inline banner above the editor footer, `bg-destructive/10 text-destructive border-destructive/30 text-xs px-3 py-2 rounded-md`. Auto-dismiss after 5s OR on next user input. NEVER use `alert()` for user-facing errors.
- Import errors: rendered inline in the import summary modal as a list, NOT individual banners.

### Keyboard handling

| Key | Context | Action |
|-----|---------|--------|
| `Tab` | Editor form | Linear order: name → description → instructions → license → compatibility → enabled toggle → Save → Delete → Share → Export → Try in Chat |
| `Tab` | File preview drawer | Linear order: Copy → Download → Close |
| `Escape` | File preview drawer open | Close drawer (priority 1 — handled at drawer level) |
| `Escape` | Editor in edit/create mode (no drawer open) | Close editor (returns to empty state) — matches `ClauseLibraryPage:161` × button |
| `Escape` | Mobile panel open | Close mobile panel |
| `Cmd/Ctrl+S` | Editor focused (own skill) | Trigger Save. Show `Saving…` state. (Optional polish — defer if scope tight.) |
| `Enter` | Search input | No action (search is debounced live). Prevent default. |
| `/` | Page-level (no input focused) | Focus the search input. (Optional polish — defer if scope tight.) |

**Focus visibility:** every focusable element uses the `.focus-ring` utility (`index.css:465-468`) — `box-shadow: 0 0 0 2px var(--background), 0 0 0 4px oklch(0.55 0.20 280 / 0.5)`. NEVER remove this with `outline-none` and no replacement.

### Tab order priority on first open

After clicking a skill row, focus moves to the **Name input** (or first non-disabled input for view-only skills). On the empty state, focus moves to the search input.

### "Create with AI" navigation

Implementation:
```ts
navigate('/', { state: { prefill: 'I want to create a new skill.' } })
```
The chat page reads `location.state?.prefill` on mount and pre-populates the input. If the chat page does not yet support this, Phase 9 plan must add a small `useEffect` to `ChatPage` that reads `location.state?.prefill` and calls the existing setMessage / sendMessage handler. **No URL query param** — keep the prefill in router state to avoid bookmarking a half-formed action.

### "Try in Chat" navigation

Same router-state pattern with the substituted skill name:
```ts
navigate('/', { state: { prefill: `Please use the ${skill.name} skill.` } })
```

---

## Mobile Breakpoint Behavior

| Viewport | Skill list | Editor | File preview drawer |
|----------|-----------|--------|---------------------|
| `≥ 768px` (md) | Inline 340px column on left | Inline right column | 480px overlay slides over editor only |
| `< 768px` | Slide-in overlay from left (mobile FAB triggers) | Full-width main view | Full-screen takeover (`w-full`) |

Layout transitions at the `md` breakpoint without a JS resize listener — pure CSS (`hidden md:flex` / `md:hidden` toggles).

**Drawer rule:** on mobile, the drawer covers the editor entirely. The backdrop becomes redundant but MUST still render (for backdrop-click-to-close UX). On desktop, the editor remains visible behind the dimmed backdrop.

---

## Animation Inventory

All durations and easings match patterns already shipped:

| Surface | Animation | Duration | Easing |
|---------|-----------|----------|--------|
| Drawer open/close | `translate-x` | 200ms | `cubic-bezier(0.4, 0, 0.2, 1)` (Tailwind `ease-out`) |
| Backdrop fade | `opacity 0 → 1` | 200ms | `ease-out` |
| Mobile panel slide | `translate-x` (existing pattern) | 200ms | `ease-out` |
| Skill row hover | `bg` color | 150ms | `cubic-bezier(0.4, 0, 0.2, 1)` (matches `interactive-lift`) |
| Selected row highlight | instant | 0 | n/a |
| Button press | scale 0.98 | 50ms | matches `interactive-lift:active` |
| Shimmer loading | infinite | 1.8s | `ease-in-out` (uses `.shimmer` class) |
| Toast / inline error appearance | `fade-in-up` | 400ms | `ease-out` (uses `.animate-fade-in-up`) |
| Copy success icon swap | instant + 1500ms hold | n/a | n/a |

**Reduced motion:** `index.css:480-514` already disables `.animate-fade-in-up`, `.shimmer`, and float animations under `prefers-reduced-motion: reduce`. The drawer slide MUST respect this — gate the `transition-transform` with a `motion-safe:` Tailwind variant: `motion-safe:transition-transform motion-safe:duration-200`. Under reduced motion the drawer appears instantly.

---

## Registry Safety

Phase 9 introduces **no new shadcn registry blocks** and **no third-party registries**. All UI is built from primitives already shipped in `frontend/src/components/ui/`.

| Registry | Blocks Used | Safety Gate |
|----------|-------------|-------------|
| shadcn official (already in repo) | `button`, `badge`, `switch`, `input`, `textarea`, `tooltip`, `popover`, `select` | not required (already vetted by project) |
| Third-party | none | not applicable |

---

## Accessibility Contract

- Every icon-only button has `aria-label` (verb + noun, e.g. `aria-label="Delete skill"`).
- Every form field has a paired `<label>` with `htmlFor` matching `id`.
- Required fields use `aria-required="true"`.
- The disabled-form state must use `aria-disabled="true"` on each control AND the visual opacity treatment (so AT users get the same signal as sighted users).
- The file preview drawer has `role="dialog"` and `aria-modal="true"`, with `aria-labelledby` pointing to the filename.
- The banner has `role="status"` (informational, not `role="alert"` which would interrupt).
- Tooltip targets have a tooltip showing the same text as `aria-label` — base-ui handles this automatically through the existing `tooltip.tsx` shim.
- Color contrast: every text-on-bg combination uses the project's existing tokens, all of which have been calibrated for WCAG AA in both themes.
- All interactive elements reachable by keyboard. No `pointer-events-none` on focusable controls (the form-disable wrapper is OK because the inner inputs also have native `disabled`).

---

## Out of Scope (Reaffirmed)

The following are explicitly NOT part of Phase 9:
- Custom Dialog component for confirmations (use `window.confirm()`)
- Drag-and-drop file upload (use a file `<input>` triggered by Upload button click)
- Inline file rename (delete + re-upload)
- File search within a skill (the file count per skill is small)
- Pagination of skill list (use scroll; backend supports `limit=`)
- Skill duplication / fork action
- Visual diff between local edits and saved version
- Markdown preview for instructions field (raw monospace textarea is the contract)
- Rich preview for binary files (PRD §Future explicitly defers SFILE-BINARY-PREVIEW)
- Global keyboard shortcut help dialog

---

## Checker Sign-Off

- [x] Dimension 1 Copywriting: PASS — All EN + ID strings declared with translation keys; CTAs use specific verb + noun; empty/error/destructive states fully covered.
- [x] Dimension 2 Visuals: PASS — Layout, drawer, badges, banners, file rows, and ownership states all specified with locked dimensions.
- [x] Dimension 3 Color: PASS — All colors map to existing CSS variables; accent reserved set is explicit (7 elements); destructive reserved for one set; theme parity required.
- [x] Dimension 4 Typography: PASS — Four roles (14/12/10/9) declared, two weights (400/500/600 axis), Geist Variable. Matches existing pages.
- [x] Dimension 5 Spacing: PASS — All values multiples of 4 with one named exception (`space-y-1.5` form gap, justified). Lifted from existing `ClauseLibraryPage` precedent.
- [x] Dimension 6 Registry Safety: PASS — No new third-party registries; all primitives already vetted in the repo.

**Approval:** approved 2026-05-01

---

## Pre-Population Audit Trail

| Source | Decisions used in this contract |
|--------|---------------------------------|
| `09-CONTEXT.md` | D-P9-01..13 (all 13 locked decisions: nav, layout, drawer pattern, three-creation-path, ownership state machine, prefill strings, refresh policy) |
| `07-CONTEXT.md` | Ownership model semantics (`user_id` / `created_by` distinction), file storage path, 10MB per-file cap |
| `08-CONTEXT.md` | `read_skill_file` text/binary classification (D-P8-11), 8000-char truncation (D-P8-12), `load_skill` response files schema |
| `frontend/src/index.css` | All design tokens (colors light + dark, spacing, font, shadows, glass, animations, focus ring, mobile overlay, shimmer) |
| `frontend/src/pages/ClauseLibraryPage.tsx` | Two-column layout skeleton, `inputBase`/`inputClass`/`textareaClass`, mobile FAB pattern, search debounce, edit-mode state machine, density values, header strip dimensions |
| `frontend/src/components/layout/IconRail.tsx` | `standaloneItems` extension point, `railButtonClass` active-state treatment |
| `frontend/components.json` | shadcn preset (`base-nova`, `neutral`, `lucide`) |
| `docs/PRD-skill.md` | Three creation paths, file preview behavior (text vs binary), ownership badge requirements, character counter requirement |
| `CLAUDE.md` (project) | No `backdrop-blur` on persistent panels, no gradient buttons, base-ui tooltip shim, dual-theme parity |

User input required: **none**. All values inferred from upstream artifacts.

---

*Phase: 9-Skills Frontend*
*UI-SPEC compiled: 2026-05-01*
