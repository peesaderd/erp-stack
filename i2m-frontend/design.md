# I2M Frontend — Design Spec

> **Product:** I2M (Image-to-Market) — AI-powered content creation studio for Thai creators
> **Stack:** React 18 + Vite + Tailwind CSS v4 + TypeScript
> **Font:** Inter (sans-serif), IBM Plex Sans Thai (fallback for Thai text)
> **Target:** Mobile-first (iOS-style), responsive tablet/desktop
> **Design Vibe:** Clean, modern, card-based, minimal chrome

---

## 🎨 Design System

### Colors (iOS-style)

```
Primary:   #6366F1 (Indigo-500)
Secondary: #8B5CF6 (Violet-500)
Accent:    #F59E0B (Amber-500)
Success:   #10B981 (Emerald-500)
Danger:    #EF4444 (Red-500)

Background: #F8FAFC (Slate-50)
Surface:    #FFFFFF
Surface-2:  #F1F5F9 (Slate-100)
Border:     #E2E8F0 (Slate-200)

Text:      #0F172A (Slate-900)
Text-2:    #475569 (Slate-600)
Text-3:    #94A3B8 (Slate-400)

Dark Mode:
  Background: #0F172A
  Surface:    #1E293B
  Surface-2:  #334155
  Border:     #475569
  Text:       #F1F5F9
  Text-2:     #94A3B8
```

### Typography

```css
/* iOS-style type scale */
h1: text-2xl font-semibold tracking-tight  (title)
h2: text-xl font-semibold                   (section)
h3: text-base font-medium                   (card title)
body: text-sm leading-relaxed               (content)
caption: text-xs text-slate-400              (metadata)
```

### Components

#### Bottom Tab Bar
```json
{
  "type": "fixed bottom-0 inset-x-0 bg-white/80 backdrop-blur-xl",
  "height": "64px",
  "items": [
    {"icon": "sparkles", "label": "Studio", "route": "/"},
    {"icon": "photo", "label": "Gallery", "route": "/gallery"},
    {"icon": "user", "label": "Profile", "route": "/profile"}
  ],
  "style": "Glassmorphism with top border, active tab = indigo-500"
}
```

#### Card Component
```
rounded-xl bg-white p-4 shadow-sm border border-slate-100
Dark: bg-slate-800 border-slate-700

Image: rounded-lg w-full aspect-square object-cover
Title: text-sm font-medium (line-clamp-2)
Label: text-xs text-slate-400 uppercase tracking-wider
```

#### Button Styles
```
Primary:   bg-indigo-500 text-white rounded-xl py-3 px-6 font-medium active:scale-95 transition
Secondary: bg-slate-100 text-slate-900 rounded-xl py-3 px-6 font-medium dark:bg-slate-700
Ghost:     text-indigo-500 font-medium
Icon:      w-10 h-10 rounded-full bg-slate-100 flex items-center justify-center
Skeleton:  animate-pulse bg-slate-200 rounded-xl
```

#### Input Fields
```
rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm
Focus: ring-2 ring-indigo-500/20 border-indigo-500
Dark: bg-slate-800 border-slate-700 text-white
Label: text-xs font-medium text-slate-600 mb-1.5
Error: border-red-500 text-red-500
```

---

## 📱 Page Layouts

### 1. Product Studio (/)

```
┌──────────────────────────────┐
│      Product Studio          │ ← Header (text-base font-semibold)
│      Create content in sec   │ ← Subtitle (text-xs text-slate-400)
├──────────────────────────────┤
│                              │
│  ┌────────────────────────┐  │
│  │  📷 Upload Photo       │  │ ← Large area (tap to upload)
│  │  or drag & drop        │  │ ← Dashed border, rounded-xl bg-slate-50
│  │                        │  │
│  │  [image thumbnail]     │  │ ← If image selected, show preview
│  └────────────────────────┘  │
│                              │
│  Product Name               │ ← Label
│  ┌────────────────────────┐  │
│  │ BOYA Mini 2            │  │ ← Input (rounded-xl)
│  └────────────────────────┘  │
│                              │
│  Description                │ ← Label
│  ┌────────────────────────┐  │
│  │ ไมค์ไร้สายตัด...         │  │ ← Textarea, 3 rows
│  └────────────────────────┘  │
│                              │
│  ┌────────────────────────┐  │
│  │ ✨ Analyze Product     │  │ ← Primary button, full-width
│  └────────────────────────┘  │
│                              │
│  ── Loading State ──         │
│  ┌────────────────────────┐  │
│  │ [skeleton 1]           │  │ ← 3 skeleton cards, animate-pulse
│  │ [skeleton 2]           │  │
│  │ [skeleton 3]           │  │
│  └────────────────────────┘  │
│                              │
│  ── Results ──               │
│  Choose your style          │ ← Section header
│                              │
│  ┌──────┐ ┌──────┐ ┌──────┐│
│  │ 🖐️  │ │ 🎬  │ │ 🌅  ││ ← Preset cards (3-column grid)
│  │ Hold │ │ Use  │ │ Life ││
│  └──────┘ └──────┘ └──────┘│
│  ┌──────┐ ┌──────┐         │
│  | 🔍  │ │ ⭐  │         │ ← Row 2 (2-column)
│  │Close │ │Review│         │
│  └──────┘ └──────┘         │
│                              │
│  ── Selected Preset ──       │
│  Prompt preview              │ ← Card with editable prompt text
│  ┌────────────────────────┐  │
│  │ "A content creator...  │  │ ← text-xs text-slate-600
│  │ 🖼️ Generate Image     │  │ ← Primary button
│  └────────────────────────┘  │
│                              │
│  ── Generated Image ──       │
│  ┌────────────────────────┐  │
│  │   [generated image]    │  │ ← aspect-square rounded-xl
│  │   Download · Regenerate│  │ ← ghost buttons row
│  └────────────────────────┘  │
│                              │
│  ── Video Section ──         │
│  ┌────────────────────────┐  │
│  │ 🎬 Generate Video     │  │ ← Secondary button
│  │ From this image       │  │
│  └────────────────────────┘  │
│                              │
│  ── AI Hooks + Copy ──       │
│  ┌────────────────────────┐  │
│  │ 💡 Hook Suggestions    │  │ ← Card with list
│  │ • 24ชม. แบตอึด!...    │  │ ← text-sm, tap to copy
│  │ • ไมค์ตัดเสียง...      │  │
│  └────────────────────────┘  │
│                              │
└──────────────────────────────┘
│  [Studio] [Gallery] [Profile]│ ← Bottom tab bar (fixed)
└──────────────────────────────┘
```

### 2. Image Gallery (/gallery)

```
┌──────────────────────────────┐
│  ← Back    Image Gallery     │
├──────────────────────────────┤
│                              │
│  ┌────┐ ┌────┐ ┌────┐       │
│  │img │ │img │ │img │       │ ← 3-column grid masonry
│  └────┘ └────┘ └────┘       │
│  ┌────┐ ┌────┐ ┌────┐       │
│  │img │ │img │ │img │       │
│  └────┘ └────┘ └────┘       │
│                              │
│  Empty state:                │
│  📷 No images yet             │
│  Your generated images       │
│  will appear here            │
│  [Create your first image]   │ ← Button
│                              │
└──────────────────────────────┘
```

### 3. Profile (/profile)

```
┌──────────────────────────────┐
│         Profile              │
├──────────────────────────────┤
│                              │
│  ┌────────────────────────┐  │
│  |  👤 Avatar             │  │ ← Circle, w-20 h-20, centered
│  |  Creator Name          │  │ ← text-lg font-semibold
│  |  @handle               │  │ ← text-sm text-slate-400
│  └────────────────────────┘  │
│                              │
│  Shop Settings              │ ← Section header
│  ┌────────────────────────┐  │
│  │ 🏪 Shop Name          │  │ ← Input row
│  └────────────────────────┘  │
│  ┌────────────────────────┐  │
│  | 🎯 Target Audience    │  │ ← Input row
│  └────────────────────────┘  │
│  ┌────────────────────────┐  │
│  │ 🔗 Affiliate Link     │  │ ← Input row
│  └────────────────────────┘  │
│                              │
│  Stats                      │ ← Section header
│  ┌────┐ ┌────┐ ┌────┐      │
│  │ 12 │ │ 45 │ │ 3  │      │ ← Stat cards row
│  │ Img│ │Vid │ │Cmpg│      │
│  └────┘ └────┘ └────┘      │
│                              │
│  Appearance                 │ ← Section header
│  ┌────────────────────────┐  │
│  │ 🌙 Dark Mode          │  │ ← Toggle row
│  └────────────────────────┘  │
│                              │
└──────────────────────────────┘
```

### 4. Scripts (/scripts)

```
┌──────────────────────────────┐
│  ← Back    Scripts           │
├──────────────────────────────┤
│                              │
│  ┌────────────────────────┐  │
│  | Capture hook ideas     │  │ ← Textarea
│  | for your content...    │  │
│  └────────────────────────┘  │
│                              │
│  ┌────────────────────────┐  │
│  │ ✨ Generate Script    │  │ ← Primary button
│  └────────────────────────┘  │
│                              │
│  ── Generated Scripts ──     │
│  ┌────────────────────────┐  │
│  │ 🎥 Script #1          │  │ ← Card
│  │ "เปิดกล่องมาเจอ..."   │  │ ← text-sm
│  │ 📋 Copy                │  │ ← ghost button
│  └────────────────────────┘  │
│                              │
└──────────────────────────────┘
```

### 5. Video Gallery (/video-gallery)

```
┌──────────────────────────────┐
│  ← Back    Video Gallery     │
├──────────────────────────────┤
│                              │
│  ┌────┐ ┌────┐ ┌────┐       │
│  │vid │ │vid │ │vid │       │ ← 3-column grid
│  └────┘ └────┘ └────┘       │
│                              │
│  Each card:                  │
│  ┌────────────────────────┐  │
│  │   [thumbnail]          │  │ ← aspect-[9/16]
│  │   ► Play               │  │ ← overlay on hover
│  |   Duration: 5s         │  |
│  └────────────────────────┘  │
│                              │
└──────────────────────────────┘
```

---

## 📐 Layout Grid

```
Mobile:   1 col, px-4 (16px padding), max-w-lg mx-auto
Tablet:   2 col grid, max-w-2xl
Desktop:  3 col grid, max-w-5xl

Content width: full-width with 16px padding (mobile)
Breakpoints: sm:640px md:768px lg:1024px
```

## 🌀 Animations & Transitions

```
Page transition: fade + slide-up (200ms ease-out)
Card press: scale-95 (active state)
Tab switch: instant (no animation)
Modal: fade in + scale (150ms)
Skeleton: animate-pulse (1.5s cycle)
Toast: slide down from top (300ms ease-out)
```

## 📦 States

Every component needs:

```
1. Loading: skeleton shimmer (animate-pulse)
2. Empty: illustration + message + CTA button
3. Error: icon + message + retry button (text-red-500)
4. Success: content with normal styling
5. Edge: long text → line-clamp, lots of items → scroll
```

### API Call Pattern

```typescript
// Loading state
{loading && <Skeleton />}

// Empty state
{!loading && results.length === 0 && <EmptyState />}

// Error state
{error && <ErrorAlert message={error} onRetry={refetch} />}

// Success state
{results.map(item => <Card {...item} />)}
```

---

## 🧭 User Flow

```
                    ┌──────────────┐
                    │  Launch App  │
                    └──────┬───────┘
                           ▼
                    ┌──────────────┐
                    │ Product Studio│ ← Default screen
                    │  (Tab 1)     │
                    └──────┬───────┘
                           │
                     ┌─────┴──────┐
                     ▼            ▼
              ┌──────────┐ ┌──────────┐
              │ Upload   │ │ Enter    │
              │ Photo    │ │ Product  │
              └────┬─────┘ │ Details  │
                   │       └────┬─────┘
                   └──────┬─────┘
                          ▼
                  ┌──────────────┐
                  │ AI Analysis  │ ← Loading spinner
                  │ Analyzing... │
                  └──────┬───────┘
                         ▼
                  ┌──────────────┐
                  │ 5 Presets    │ ← Card grid
                  │ Choose style │
                  └──────┬───────┘
                         ▼
                  ┌──────────────┐
                  │ Image Gen    │ ← Fal.ai
                  │ [generated]  │
                  └──────┬───────┘
                         ▼
                  ┌──────────────┐
                  │ Video Gen    │ ← WaveSpeed
                  │ or Gallery   │
                  └──────────────┘

            Tab 2: Gallery ← History of images/videos
            Tab 3: Profile ← Settings, stats, dark mode
```

---

## 💡 Key UX Principles

1. **Show don't tell** — use skeleton loaders, not spinners
2. **Feedback every action** — toast on success, alert on error
3. **One primary action per screen** — the main button should be obvious
4. **Optimistic UI** — show result immediately, update in background
5. **Offline resilience** — cache gallery in localStorage, show stale data
6. **Thai + English** — UI labels in English, content in Thai
7. **iOS gestures** — swipe back, pull to refresh, long-press for context menu

---

## 🎯 Vibe & Feel

> *"Like a professional creative studio, but it fits in your pocket and speaks Thai."*

- Clean backgrounds (white/slate-50)
- Generous whitespace (p-4 to p-6)
- Cards have subtle shadows (shadow-sm)
- Indigo accent for interactive elements
- Rounded corners (rounded-xl = 12px)
- Thai text uses adequate line-height (leading-relaxed = 1.625)
- No heavy borders — use shadows and spacing for hierarchy
- Bottom tab bar with glassmorphism (backdrop-blur-xl)
- Dark mode that actually looks good (slate-800 surfaces, not pure black)
