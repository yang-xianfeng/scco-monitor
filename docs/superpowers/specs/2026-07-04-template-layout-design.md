# SCCO Monitor Template Layout Redesign

## Scope

Refine `scco_monitor/template.html` — CSS + HTML only, no JS/Plotly changes, no new features.
Zero new dependencies (no npm, no CDN libraries beyond Plotly.js).

## Current Layout

- Centered header: title + timestamp
- 3 equal stat cards (Cu, SCCO, Corr) in a flex row — labels inline with values
- Two chart cards (intraday K-line + 60D history) stacked vertically
- Responsive: stat cards wrap on mobile, chart heights shrink

## Problems

1. Stat cards: labels and values on same line → weak hierarchy
2. Overall spacing tight, limited "breathing room"
3. Mobile wrap is utilitarian, no deliberate breakpoint layout
4. Corr card signal (safe/watch/hot) not visually prominent enough

## Design Goals

- Clean, elegant, information-hierarchy-first (GitHub dark theme retained)
- Minimal CSS footprint — no classes added beyond existing patterns
- Every change must serve clarity, not decoration

## Changes

### 1. Header (`header`)
- Left-aligned title, right-aligned timestamp (flex between)
- Title slightly larger (18px), timestamp slightly larger (11px)

### 2. Stat cards (`.stats > .stat`)
- **Layout**: switch from `flex row` (label + value side-by-side) to `flex column` (label above, value below)
- **Label**: smaller (11px), uppercase, muted, centered
- **Value**: larger (24px), bold, centered
- **Corr card**: if signal tag present, place it below the value in its own row
- Remove inline `style="color:..."` — use CSS variables per card via class

### 3. Chart cards (`.chart-wrap`)
- Slightly larger padding (10px → 12px)
- Title bar: thicker bottom border, slightly larger font
- Badge (trade date) slightly more prominent

### 4. Responsive
- `max-width: 640px`: stat cards 2 columns (Cu+SCCO top, Corr full width)
- Chart heights: 300px/340px on mobile (kept from current)

### 5. Refinements
- Subtle top/bottom padding increase (20px → 24px)
- Card corner radius 10px→12px (slightly softer)
- Chart gap 14px→20px (more breathing room)

## Non-Goals

- No new JS, no interactivity, no animation
- No Plotly config changes
- No Python code changes
- No build step

## Exported Interface

Only `template.html` is modified. `chart.py`, `config.py`, core, storage, backtest, notifier — all untouched.
Generated `docs/index.html` will be identical in structure, rendered with different class/content.

## Verification

1. `python main.py` — must generate valid HTML without errors
2. Visual check: open `docs/index.html` in browser, verify layout at 1440px, 768px, 375px widths
