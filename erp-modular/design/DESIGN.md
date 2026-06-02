# ERP Modular — Design System

> Google Stitch format. Readable by DESIGN.md-aware tools.

## Brand

| Token | Value |
|-------|-------|
| Primary | `#6366f1` (oklch(58% 0.18 280)) |
| Primary Hover | `#818cf8` (oklch(68% 0.16 270)) |
| Primary Subtle | `#312e81` (oklch(38% 0.24 280)) |
| Surface | `#1a1d27` |
| Surface Hover | `#242838` |
| Background | `#0f1117` |
| Border | `#2a2e3a` |
| Text Primary | `#e2e8f0` |
| Text Muted | `#94a3b8` |
| Text Dim | `#64748b` |
| Success | `#22c55e` |
| Warning | `#f59e0b` |
| Danger | `#ef4444` |

## Typography

| Role | Family | Weight | Size |
|------|--------|--------|------|
| Display | `-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Noto Sans Thai', sans-serif` | 800 | 24px |
| Title | same | 600 | 16px |
| Body | same | 400 | 14px |
| Small | same | 400 | 12px |
| Code | `'JetBrains Mono', 'Cascadia Code', 'Noto Sans Mono', monospace` | 400 | 13px |

## Spacing (px)

| Step | Value |
|------|-------|
| xs | 4 |
| sm | 8 |
| md | 12 |
| lg | 16 |
| xl | 20 |
| 2xl | 24 |
| 3xl | 32 |

## Radii

| Token | Value |
|-------|-------|
| Default | 8px |
| Large | 12px |
| Full | 9999px |

## Shadows

| Token | Value |
|-------|-------|
| Card | `0 4px 24px rgba(0,0,0,.3)` |
| Elevated | `0 8px 32px rgba(0,0,0,.4)` |
| Modal | `0 16px 48px rgba(0,0,0,.5)` |

## Components

### Button
| Variant | Style |
|---------|-------|
| Primary | `bg: primary, text: white, radius: 8px` |
| Secondary | `bg: surface-hover, text: text, border: border` |
| Ghost | `bg: transparent, text: text-muted` |
| Danger | `bg: danger, text: white` |

### Card
| Variant | Style |
|---------|-------|
| Default | `bg: surface, border: border, radius: 8px, pad: 16px` |
| Elevated | `+ shadow: card` |
| Bordered | `border-left: 3px solid primary` |

### Input
| State | Style |
|-------|-------|
| Default | `bg: surface, border: border, radius: 8px, text: text` |
| Focus | `border-color: primary, outline: 2px primary-subtle` |
| Error | `border-color: danger` |
| Disabled | `opacity: .5, cursor: not-allowed` |

## Layout

| Region | Width | Z-index |
|--------|-------|---------|
| Sidebar | 240px | 100 |
| Topbar | 56px height | 50 |
| Modal | center screen | 200 |
| Toast | top-right | 300 |

## Motion

| Token | Value |
|-------|-------|
| Default | `.2s ease` |
| Slow | `.3s ease` |
| Fast | `.1s ease` |

## Anti-pattern Detector (Slop Rules)

These should fail CI:

1. `gradient-text` — Don't use gradient on body text
2. `glassmorphism` — No frosted glass effects
3. `ai-color-palette` — No LLM-generated random colors
4. `side-stripe-border` — No decorative side borders on cards
5. `glow-effect` — No neon glows
6. `oversized-hero` — Hero section > 80vh
7. `auto-play-carousel` — No auto-rotating carousels
8. `generic-stock-image` — No stock photos
9. `font-size-below-12` — Minimum readable size 12px
10. `contrast-ratio-below-4.5` — WCAG AA for text
