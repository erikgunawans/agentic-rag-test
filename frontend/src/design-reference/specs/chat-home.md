# Chat / Home Screen

**Source:** `_figma-source/src/imports/pasted_text/knowledge-hub-dashboard.txt`
**Component:** `_figma-source/src/app/App.tsx` (nav id: 1, Home icon)

## Layout

3-column: IconRail (floating pill) + Chat History Sidebar (260px) + Main Content (remaining)

## Column 1: Floating Icon Rail

- Width: 56px pill within 88px container, vertically centered
- Pill: `bg-bg-surface/70` + backdrop-blur-24 + border border-subtle + shadow
- Corner radius: 28px (full pill shape)
- Contents: Logo (Sparkles icon, 28px white, active purple bg 40x40) -> divider -> 6 nav icons -> spacer -> avatar
- Nav icons: 20px, 36x36 touch target, rounded-lg
- Active: `bg-accent-primary/12`, `text-accent-primary`, glow shadow
- Hover: `bg-bg-hover`, `text-foreground`

## Column 2: Chat History Sidebar

- Width: 260px, bg: `bg-surface`, right border: `border-subtle`

### Sections (top to bottom):
1. **Header** (72px): "Knowledge Hub" title + "Chat History" subtitle + collapse button
2. **New Chat button** (44px): Full-width, bg accent-primary, rounded-xl, "+ New Chat"
3. **Search bar** (36px): bg-elevated, rounded-[10px], magnifier icon + placeholder
4. **Conversation list**: Time-grouped sections (TODAY, YESTERDAY, LAST WEEK)
   - Group label: 11px uppercase semibold text-faint, tracking-wider
   - List items: 52px height, chat icon + title (13px truncated) + timestamp (11px)
   - Hover: bg-hover
5. **User profile** (72px, pinned bottom): Avatar + name + role + settings icon

## Column 3: Main Content (Welcome State)

- Background: bg-base + mesh gradient overlay (see migration-guide.md)

### Hero Group (centered):
1. Logo + greeting: Sparkles icon 44px + "Hi, Erik Gunawan" 38px bold
   - "Erik Gunawan" text uses accent gradient (start -> mid -> end)
2. Subtitle: 16px text-secondary, max-w-[560px], centered

### Input Card (margin-top 32px):
- Width: 820px, min-height: 130px, bg-elevated, rounded-[20px]
- Border: border-subtle, focus: border-accent + accent-glow shadow
- Placeholder: "Apa pertanyaan anda saat ini?" 15px text-faint
- Bottom toolbar: attachment + document buttons (left) | version pill + voice + send (right)
- Send button: 36px, bg accent-primary, paper-plane icon white

### Quick-Action Bento Grid (margin-top 20px, 820px):
- 2x2 asymmetric layout, 12px gap, 72px row height
- Row 1: "Pembuatan Dokumen" (340px) + "Perbandingan Dokumen" (fill)
- Row 2: "Kepatuhan Dokumen" (fill) + "Analisis Kontrak" (340px)
- Each card: bg-elevated, rounded-2xl, border-subtle, icon + title + subtitle
- Hover: border changes to per-color accent, matching color glow shadow

## States

- Icon rail icons: default / hover / active
- Sidebar conversations: default / hover / selected
- Input card: idle / focused (border + shadow change)
- Quick-action cards: default / hover (per-color glow)
- New Chat button: default / hover (lighter purple + shadow)
- Send button: default / hover (lighter purple + glow shadow)
