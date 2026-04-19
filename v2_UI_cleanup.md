# Joi v2 — UI Cleanup Plan

## Overview

Three phases ordered by impact-to-effort ratio. Phase 1 is pure polish with no architectural changes.
Phase 2 restructures the chat page layout. Phase 3 introduces deeper hologram and motion work.

---

## Phase 1 — Quick Wins (Low Risk, High Impact)

### 1.1 Collapse the page header
**Files:** `frontend/app/chat/page.tsx`, `frontend/app/globals.css`

The "PHASE 2.2 / CHAT SURFACE" header eats ~120px of vertical space and adds no runtime value.
- Replace the full `.page-header` block with a slim inline breadcrumb bar (~44px tall)
- Keep the three status cards (Transport / Source / Mode) but shrink them to compact chips
  aligned right in the same bar, matching the `.brand-chip` style already in globals.css
- Remove the `.page-copy` subtitle — it belongs in a tooltip or hover state, not permanent real estate
- Same treatment for all other page headers (Memory, Planner, Diagnostics, Settings)

**Result:** Immediate ~100px of recovered content space per page.

---

### 1.2 Nav sidebar — active state & icon dots
**Files:** `frontend/components/nav-link.tsx`, `frontend/app/globals.css`

Currently active and inactive nav items are hard to distinguish at a glance (only a subtle
background shift). Changes:
- Add a 6px cyan left-border accent on `.nav-link.active` (using `border-left: 3px solid var(--cyan)`)
- Add a small filled dot `●` before the label when active, empty `○` otherwise — purely CSS
  via `::before` pseudo-element, no JSX change needed
- Tighten the `.nav-link-copy` sub-label font-size from `0.82rem` to `0.75rem` and apply
  `display: none` on inactive links (show only label, reveal copy on hover/active)

**Result:** Navigation becomes scannable in < 1 second.

---

### 1.3 Remove the sidebar "Migration Window" card
**Files:** `frontend/components/app-shell.tsx`

The hero-card at the bottom of `app-shell.tsx` ("Streamlit is now a fallback client") is stale
internal scaffolding copy, not product UI. Delete the entire `<div style={{ marginTop: 28 }} ...>`
block. It's the only hardcoded content in the shell.

**Result:** Cleaner sidebar, removes confusing internal messaging from the product surface.

---

### 1.4 Chat empty state — welcome prompt suggestions
**Files:** `frontend/components/chat-client.tsx`

The current empty state is a dashed box with one static sentence. Replace it with a 2×2 grid of
suggested prompt chips (e.g. "What's on my calendar?", "Summarise my notes", "Set a reminder",
"How are you feeling?"). Clicking a chip populates the `draft` state.
- Chips use `.badge` style + a hover `background: var(--cyan-soft)` override
- No backend change needed — they just `setDraft(text)`

**Result:** Fills the visual void; gives new users an immediate on-ramp.

---

### 1.5 Typography cleanup
**Files:** `frontend/app/globals.css`

- `.page-title` is `clamp(2rem, 4vw, 3.4rem)` — cap it at `2rem` max now that headers are being
  collapsed (1.3 above). The Orbitron display font at 3.4rem is aggressive.
- `.panel h2, .panel h3` — add `font-size: 0.9rem` override so panel sub-headers don't compete
  with page hierarchy
- `.eyebrow` letter-spacing `0.18em` is correct; keep it

---

## Phase 2 — Layout Restructuring (Medium Effort)

### 2.1 Unified right-column "Joi Status" panel
**Files:** `frontend/components/chat-client.tsx`, `frontend/components/avatar-sync-panel.tsx`

The right column currently has four separate panels stacked independently:
1. `<PerceptionEngine>` (Presence Sensing)
2. "Session State / Live Status" list-rows
3. `<AvatarSyncPanel>` (Hologram + state badges)
4. "Realtime Feed / Event Stream"

Restructure into two zones:
- **Top zone — "Joi"**: `<AvatarSyncPanel>` (hologram first, full width), directly below it the
  3 state badges (default / neutral / ready) and the status rows (Status, Provider, Presence).
  This gives the avatar visual primacy and groups all Joi-state signals together.
- **Bottom zone — "Feed"**: Perception + Event stream collapsed into a `<details>` accordion,
  closed by default. Power-users expand it; casual users never see the noise.

CSS change: `.chat-layout` right column changes from `display: grid; gap: 18px` flat stack to
`display: flex; flex-direction: column; gap: 18px` with the two zones as explicit flex children.

---

### 2.2 Chat column — make message list fill available height
**Files:** `frontend/app/globals.css`

`.message-list` has a hardcoded `max-height: 640px`. This means on tall monitors the list stops
at 640px and the rest is blank. Replace with:
```css
.message-list {
  flex: 1;
  min-height: 0;
  max-height: calc(100vh - 420px);
  overflow: auto;
}
```
Also make the `.panel` containing the chat a flex column (`display: flex; flex-direction: column`)
so the message list grows to fill it.

---

### 2.3 Auto-scroll to latest message
**Files:** `frontend/components/chat-client.tsx`

The message list has no auto-scroll. Add a `bottomRef = useRef<HTMLDivElement>(null)` sentinel
div at the end of the message list and `bottomRef.current?.scrollIntoView({ behavior: "smooth" })`
in a `useEffect` triggered by `messages` and `streamingText` changes. Standard pattern, ~8 lines.

---

### 2.4 Streaming indicator
**Files:** `frontend/components/chat-client.tsx`, `frontend/app/globals.css`

The streaming message card currently shows "streaming" as plain text in the header timestamp slot.
Replace with a CSS-animated 3-dot pulse (`...` typing indicator) rendered below the last user
message instead of as a separate card. Use a `@keyframes typing-dot` that offsets each dot's
opacity by 0.2s.

---

## Phase 3 — Hologram & Motion Polish (Higher Effort)

### 3.1 Avatar panel — scanlines & idle CRT flicker
**Files:** `frontend/components/avatar-renderer.tsx`, `frontend/app/globals.css`

The `.avatar-hologram::before` already has CRT scanlines. Strengthen the effect:
- Increase scanline alpha from `0.04` to `0.07` (still subtle but visible at a glance)
- Add a second `::after` layer (when *not* `.speaking`) that animates a slow vertical scan-bar
  — a 4px-tall translucent cyan stripe that sweeps top→bottom every 8s using `@keyframes scan`
- The `.hologramGlow` box-shadow animation is already there and working; no change needed

---

### 3.2 Avatar panel — idle state shows static image fallback gracefully
**Files:** `frontend/components/avatar-sync-panel.tsx`

When no `sync` payload is present (fresh load, no TTS yet), `<AvatarRenderer>` renders but the
Three.js canvas shows the static `Joi_Neutral.png` correctly. Currently there's no frame around
it — the `<AvatarRenderer>` container has no label or context. Add:
- A thin `HOLOGRAM` eyebrow label above the canvas (matching the screenshot's existing label)
- A "JOI" display-font title below
- The three state badge chips (default / neutral / **ready** highlighted) that are already in
  `avatar-sync-panel.tsx` but currently detached from the hologram visually

This is mostly moving existing JSX into a wrapper — no new logic.

---

### 3.3 Page transitions
**Files:** `frontend/app/layout.tsx`, `frontend/app/globals.css`

Add a simple fade-in on route change using a CSS animation on `.content-frame`:
```css
@keyframes page-in {
  from { opacity: 0; transform: translateY(6px); }
  to   { opacity: 1; transform: translateY(0); }
}
.content-frame {
  animation: page-in 220ms ease forwards;
}
```
No JS router hook needed — Next.js remounts the layout's `children` on navigation, which
re-triggers the CSS animation naturally.

---

### 3.4 Responsive sidebar — collapse to icon rail on small viewports
**Files:** `frontend/components/app-shell.tsx`, `frontend/components/nav-link.tsx`,
`frontend/app/globals.css`

Below 1120px the current media query stacks everything to a single column which breaks the
sidebar into a long header block. Better: at ≤900px collapse `.app-nav` to a 64px icon rail
showing only first-letter initials (C / M / P / D / S / P) with tooltips on hover. The brand
chip and copy hide; the nav links show icon-only. At ≤640px replace the rail with a bottom
tab bar (4 primary items).

This is the largest change in the plan — scope it as its own sprint if needed.

---

---

## Sprint 7.2 — Focus & Breathing Room *(new)*

Addresses: avatar prominence, right-column clutter, collapsible sidebar.

---

### 7.2.A Collapsible sidebar
**Files:** `frontend/components/app-shell.tsx`, `frontend/components/nav-link.tsx`,
`frontend/app/globals.css`

Add a toggle button (chevron `‹`) at the bottom of `.app-nav`. When collapsed:
- `.app-nav` transitions from `280px` → `68px` width (CSS `transition: width 240ms ease`)
- Brand title, brand copy, and `.nav-link-copy` all `display: none`
- `.brand-chip` shrinks to a square icon-only pill showing just `J`
- Each `.nav-link` shows only the first letter of the label centred (via `data-initial` attribute
  on the link and a `content: attr(data-initial)` CSS rule)
- Toggle button flips to `›` when collapsed

State persisted in `localStorage` under `joi-nav-collapsed` so it survives page reloads.
No backend change. This is a `"use client"` wrapper around the existing `AppShell` — or
`AppShell` itself can be converted to a client component since it already uses `NavLink`
which is already `"use client"`.

**Result:** User can reclaim ~215px of content width whenever they want.

---

### 7.2.B Avatar as the page focal point
**Files:** `frontend/components/chat-client.tsx`, `frontend/components/avatar-sync-panel.tsx`,
`frontend/app/globals.css`

Currently the avatar (`AvatarSyncPanel`) is buried as one of six stacked panels in the right
column. The `chat-layout` grid is `1.5fr / 0.9fr`. Changes:

1. **Reorder the right column** — move `<AvatarSyncPanel>` to the top of the `<aside>`, before
   the Live Status panel. It should be the first thing the eye lands on.
2. **Give the avatar panel more height** — `.avatar-hologram` currently has `max-width: 400px;
   aspect-ratio: 1`. Remove the `max-width` cap so it fills the panel width. On the right
   column (~400–450px wide) this means the hologram is naturally larger.
3. **Compact the avatar panel chrome** — the `AvatarSyncPanel` section currently has an eyebrow
   ("Hologram"), an `h3` ("Joi"), then the renderer, then badges, then an audio player, then a
   full viseme phoneme track. Slim it down:
   - Remove the `eyebrow` + `h3` from inside the panel (the hologram speaks for itself)
   - Move the three state badges to a compact row directly overlaid at the bottom of the
     hologram container using `position: absolute; bottom: 8px` so they don't add height
   - Collapse the viseme phoneme track into a `<details>` element (closed by default) — it's
     a debug view, not a user-facing feature
   - Keep the `<audio>` controls but only render them when `sync` is present

**Result:** Avatar becomes visually dominant in the right column with no wasted chrome above it.

---

### 7.2.C Reduce right-column clutter
**Files:** `frontend/components/chat-client.tsx`, `frontend/app/globals.css`

The right `<aside>` in `chat-client.tsx` currently stacks these panels unconditionally:
1. `<PerceptionEngine>` — Presence Sensing
2. Live Status list-rows
3. `<AvatarSyncPanel>` — Hologram
4. Scene Analysis *(already conditional — good)*
5. Approvals — Pending Actions
6. Approval modal *(already conditional)*
7. Event Stream

Proposed changes:
- **Approvals**: already only renders cards when `approvals.length > 0` — but the panel heading
  and empty-state still occupy space. Wrap the entire `<section>` in `{approvals.length > 0 && …}`
  so it's fully invisible when nothing is pending.
- **Event Stream**: wrap the section in a `<details>` accordion with `<summary>` showing the
  event count. Closed by default. Expands in place for power-users.
- **Perception Engine**: the `<PerceptionEngine>` panel renders even when camera is off, showing
  an "off" toggle and a button. Move it below the avatar and wrap it in a `<details>` accordion
  too — most users won't interact with it during a chat session.
- **Live Status**: keep it visible but reduce the 4-row list to only "Status" and "Provider" rows;
  move Session ID and Presence count into a collapsed `<details>` inside the panel.

**Result:** Right column default view: Avatar → Live Status (2 rows) → Approvals (only when pending).
Everything else is one click away, not cluttering the viewport.

---

### 7.2.D Page breathing room
**Files:** `frontend/app/globals.css`, individual page `.tsx` files

A few targeted CSS changes to reduce density across all pages:
- **`.page-body` padding**: increase from `28px 32px` to `32px 36px` so panels don't crowd the
  content-frame edges
- **`.panel` padding**: increase from `22px` to `24px 26px` for more internal air
- **`.list-row` gap**: increase from `12px` to `14px`
- **Diagnostics page raw JSON**: the `<p>{JSON.stringify(details)}</p>` dump is unreadable.
  Replace with a small `<pre>` block styled with the existing `approval-raw pre` monospace style,
  capped at 3 lines with `overflow: hidden` and a "show more" toggle — or just display the
  top-level keys as individual rows instead of one blob.

---

## Suggested Execution Order *(updated)*

| Sprint | Items                  | Est. Time | Status     |
|--------|------------------------|-----------|------------|
| 7.1    | 1.1–1.5 Quick wins     | 1–2 hrs   | ✅ Done    |
| 7.2    | A–D Focus & breathing  | 2–3 hrs   | Planned    |
| 7.3    | 2.1–2.4 Layout restructure | 2–3 hrs | Planned  |
| 7.4    | 3.1–3.3 Hologram polish | 2–3 hrs  | Planned    |
| 7.5    | 3.4 Responsive sidebar  | 3–4 hrs  | Superseded by 7.2.A |

Phase 1 can be executed immediately without touching any backend or logic. Each item is
independently mergeable.
