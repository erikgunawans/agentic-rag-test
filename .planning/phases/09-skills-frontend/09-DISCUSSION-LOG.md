# Phase 9: Skills Frontend - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-01
**Phase:** 9-Skills Frontend
**Areas discussed:** Navigation placement, File preview panel, Skill creation UX, Global skill view state

---

## Navigation Placement

| Option | Description | Selected |
|--------|-------------|----------|
| Standalone item (standaloneItems[]) | Same tier as Chat, Dashboard, BJR, PDP. High discoverability, always visible. Matches PRD "third top-level tab." | ✓ |
| New "Agent Tools" group | Skills in a new group alongside future Sandbox/Memory. More clicks to reach. | |

**User's choice:** Standalone — after Chat (`/`), before Dashboard. Order: `/ → /skills → /dashboard → /bjr → /pdp`

---

| Icon option | Description | Selected |
|-------------|-------------|----------|
| Zap | Suggests capability/power-up — skills as agent superpowers. | ✓ |
| Cpu | Signals AI/compute. | |
| Sparkles | Feels AI-native and modern. | |
| Blocks | Maps to "building blocks" from PRD. More literal. | |

**User's choice:** `Zap`

---

| Position | Description | Selected |
|----------|-------------|----------|
| After Chat, before Dashboard | Chat → Skills → Dashboard → BJR → PDP | ✓ |
| After Dashboard | Chat → Dashboard → Skills → BJR → PDP | |

**User's choice:** After Chat, before Dashboard — Skills is adjacent to Chat since it directly enhances the chat experience.

---

## File Preview Panel

| Option | Description | Selected |
|--------|-------------|----------|
| Overlay the editor (floating drawer) | Preview slides over the editor panel. Editor stays mounted behind. Closes on X or backdrop click. Simpler layout, no column shift. | ✓ |
| Push as third column | Editor narrows, preview appears as a third panel alongside. All three panels visible simultaneously. More complex responsive handling. | |

**User's choice:** Overlay — floating drawer over the editor panel.

---

| Text rendering | Description | Selected |
|----------------|-------------|----------|
| Monospace pre block | Scrollable `<pre>` with monospace font. PRD specifies this. | ✓ |
| Markdown rendered | Formatted markdown. Better for .md files but adds renderer dependency. | |

**User's choice:** Monospace `<pre>` block.

---

## Skill Creation UX

| Create Manually form | Description | Selected |
|----------------------|-------------|----------|
| Right panel (inline editor) | Same panel reused for create and edit. No modal. Consistent with ClauseLibraryPage. | ✓ |
| Modal dialog | Opens a dialog over the page. PRD says "form dialog." Separate component. | |

**User's choice:** Right panel — inline editor reuses the same panel for both create and edit modes.

---

| "Create with AI" prefill | Description | Selected |
|--------------------------|-------------|----------|
| Generic trigger: "I want to create a new skill." | Simple, lets skill-creator guide from there. | ✓ |
| Explicit invocation: "Use the skill-creator skill to help me create a new skill." | More explicit, reduces ambiguity. | |
| You decide | Leave to Claude. | |

**User's choice:** `"I want to create a new skill."` — exact string to pre-populate.

---

| Post-save refresh | Description | Selected |
|-------------------|-------------|----------|
| Auto-refresh on mount | Skills page fetches fresh on every mount. New skill appears when user navigates back. Zero complexity. | ✓ |
| Invalidate via state | Global context or URL param (`?refresh=1`) to signal refresh. More explicit. | |
| Manual refresh button | User taps refresh. Adds friction. | |

**User's choice:** Auto-refresh on mount.

---

## Global Skill View State

| Non-owner view | Description | Selected |
|----------------|-------------|----------|
| Disabled fields + info banner | Inputs disabled (grayed), banner: "Global skill — read-only", only [Export] and [Try in Chat] visible. Minimal code change. | ✓ |
| View-only mode (no form) | Different layout: styled text blocks, no inputs. Cleaner but separate rendering path. | |

**User's choice:** Disabled fields + info banner. Action buttons shown: [Export] [Try in Chat] only.

---

| Creator's global skill | Description | Selected |
|------------------------|-------------|----------|
| Show [Unshare] button | Creator sees banner + disabled inputs + [Unshare] [Export] [Try in Chat]. Clicking Unshare calls PATCH /skills/{id}/share and unlocks editor. | ✓ |
| Hide Unshare from editor | No unshare in editor; must use separate control. | |

**User's choice:** Show [Unshare] button to skill creator when their skill is currently global.

---

## Claude's Discretion

- **"Try in Chat" pre-populated message** — exact wording not specified. Should reference the skill by name to trigger `load_skill` discovery. Claude to pick natural phrasing (e.g., `"Please use the [skill-name] skill."`).

## Deferred Ideas

None — discussion stayed within phase scope.
