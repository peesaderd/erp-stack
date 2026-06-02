# ERP Modular / Business OS

> AI-driven business management system — one platform for all operations.

## Who is this for?

| Role | Need |
|------|------|
| **SME Owner** | One place to manage sales, inventory, orders, customers |
| **Admin (Pete)** | Full control, multi-module orchestration |
| **Team Member** | Task-specific Mini Apps with role-based access |
| **AI Agent** | Programmatic access via ERP MCP (60+ tools) |

## Brand Voice

| Trait | Rule |
|-------|------|
| Tone | Professional, clean, confident |
| Language | Bilingual (TH/EN) — Thai primary UI, English for code/data |
| Personality | "A skilled backend engineer who also designs beautiful UIs" |
| What we DON'T say | "Empower", "Leverage", "Synergy", "Game-changer", "Next-gen" |
| What we DO say | Direct, functional, specific. "สร้างใบแจ้งหนี้" not "จัดการเอกสารทางธุรกิจของคุณอย่างชาญฉลาด" |

## Design Principles

1. **Utility over decoration** — Every pixel serves a purpose
2. **Dark-first** — Built for dark mode from day one
3. **Module-aware** — Each Mini App has its own visual identity but shares the system
4. **Agent-ready** — UI components expose semantic hooks for AI agents
5. **Fast and light** — No bloated UI libraries; minimal dependencies

## Anti-references (do NOT design like this)

- Purple gradients as backgrounds
- Glassmorphism / frosted glass
- "Boost your productivity" hero sections
- Generic stock photos of people smiling at laptops
- Over-animated micro-interactions
- "AI-powered" badges everywhere
- Dashboard with 50 charts and no actionable data

## Ecosystem

```
ERP MCP (port 3000)       ← Data / Logic / 60+ Tools
├── ERP Modular (8102)    ← Gateway / Micro-frontend Shell
├── Mini Apps (varies)    ← Individual business tools
└── Business OS           ← All-in-one AI-driven platform
```
