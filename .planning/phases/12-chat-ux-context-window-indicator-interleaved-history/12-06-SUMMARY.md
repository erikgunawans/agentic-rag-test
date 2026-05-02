---
phase: 12-chat-ux-context-window-indicator-interleaved-history
plan: 06
status: complete
requirements: [CTX-04, CTX-05, CTX-06]
tests_added: 15
tests_passing: 15
---

# Plan 12-06 Summary: ContextWindowBar component + MessageInput integration

## What Was Built

### 1. `ContextWindowBar.tsx` (NEW)
A 50-line stateless presentational component that renders:
- 4px (h-1) zinc-neutral track + colored fill
- Label `Xk / Yk (Z%)` with tabular-nums for stable digit width
- Color band: `bg-emerald-500` (0–59%), `bg-amber-500` (60–79%), `bg-rose-500` (80–100%+)
- Width clamped to 100% but label percent uncapped (e.g., `150k / 128k (117%)`)
- Returns `null` when `usage`, `contextWindow`, OR `usage.total` is `null` (CTX-05 / CTX-06 / D-P12-09 — no DOM, no vertical space)

### 2. `MessageInput.tsx` integration
- Added imports for `usePublicSettings` and `ContextWindowBar`
- Pulled `usage` from `useChatContext()` (already exposes the entire `useChatState` return per ChatContext.tsx pattern)
- Pulled `contextWindow` from `usePublicSettings()`
- Mounted `<ContextWindowBar />` inside the existing `max-w-2xl` container, ABOVE the fork-parent banner and textarea (D-P12-07: PRD says max-w-3xl; we reuse max-w-2xl for visual consistency — explicit spec deviation honored)

### 3. Tests — `ContextWindowBar.test.tsx`
15 vitest + RTL tests covering:
- Three null-state guards (renders nothing)
- Label format (Xk for thousands, raw integer for sub-1k)
- All three color bands at typical and boundary percentages (60%, 80%)
- Width style scaling
- h-1 height on track + fill
- Zinc background on track
- Tabular-nums on label
- Overflow clamping (>100% → width:100%, fill rose, label uncapped)

## Key Decisions Honored

- **CTX-05 / CTX-06 / D-P12-09**: Component returns `null` (mount/unmount), not opacity-zero — zero vertical space until first usage event
- **D-P12-07**: Bar mounted INSIDE the existing `max-w-2xl` container (PRD specified max-w-3xl; deviation documented in JSX comment)
- **D-P12-10**: Three-band color thresholds with rose at 80%+ INCLUSIVE (no 100% cap)
- **CLAUDE.md Design System**: Flat solid colors only (no gradients on bars)

## Files Changed

- `frontend/src/components/chat/ContextWindowBar.tsx` — NEW (~55 lines)
- `frontend/src/components/chat/ContextWindowBar.test.tsx` — NEW; 15 tests
- `frontend/src/components/chat/MessageInput.tsx` — added 2 imports + 1 hook call + 1 destructure + 1 JSX node (~10 lines added)

## Verification

```
npx tsc --noEmit                          → clean
npm run test -- ContextWindowBar          → 15/15 passed
npm run lint                              → no NEW errors on Phase 12 files
```

## Test Coverage (15)

1. `renders nothing when usage is null`
2. `renders nothing when contextWindow is null`
3. `renders nothing when total is null`
4. `formats label as Xk / Yk (Z%) for thousands` (45000 → 45k)
5. `formats label with raw integer for sub-1k numerator` (523 → "523")
6. `uses emerald-500 fill at 35%`
7. `uses amber-500 fill at 65%`
8. `uses amber-500 fill at exactly 60%` (boundary)
9. `uses rose-500 fill at 90%`
10. `uses rose-500 fill at exactly 80%` (boundary)
11. `width style scales with percentage`
12. `bar height uses h-1 (4px)`
13. `track has zinc-neutral background`
14. `label uses tabular-nums for stable digit width`
15. `clamps fill width at 100% when total exceeds contextWindow`

## Self-Check: PASSED

All 6 must_haves truths verified:
- Component is slim h-1 track + h-1 fill + label
- Mounted in MessageInput inside existing max-w-2xl (D-P12-07 honored)
- Hidden (returns null) when usage===null or partial state — does NOT take vertical space
- Bar denominator from usePublicSettings().contextWindow; null while loading → no render
- CTX-06: never appears when no usage data ever arrives — no error, no broken UI
- Numerator format: >= 1000 → 'Xk', < 1000 → raw integer
