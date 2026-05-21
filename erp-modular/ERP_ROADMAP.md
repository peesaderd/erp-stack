# ERP Modular — Roadmap

> วางแผนโดย Inner Monologue Agent
> วันที่: 2026-05-21

---

## ภาพรวม

ERP Core แบบ Modular ที่ Mini App สามารถ reuse module/template จาก ERP Core ได้โดยตรงผ่าน API โดยไม่กระทบโครงสร้างหลัก ใช้ Plugin System / API Gateway Layer / Micro-frontend / Sidecar Pattern

### สิ่งที่มีอยู่แล้ว
- **Bridge Server** (port 54517) — เชื่อมต่อ Plane, Planka, BookStack, OpenObserve, Siyuan
- **inner-monologue-agent** — ReAct Loop + Memory + Heartbeat + Self-Reflection
- **Server** 89.167.82.205 — tools ทั้งหมดรันอยู่แล้ว

---

## Phase 1: Foundation — Core Data Model & API Layer (issues 1-3)

**ทำไมต้องมาก่อน:** ทุกอย่างต่อยอดจาก Data Model ถ้าไม่มีโครงสร้างข้อมูล จะเขียน Plugin, Gateway, หรือ Integration ไม่ได้

| Issue | สิ่งที่ต้องทำ |
|-------|--------------|
| 1. Core Data Model | ออกแบบ Entity: `Module`, `Template`, `Entity`, `Plugin`, `App` — ใช้ Pydantic + SQLModel |
| 2. API Layer | สร้าง FastAPI CRUD สำหรับ Module/Template — ใช้ Bridge Server pattern |
| 3. Plugin Interface | Abstract Base Class สำหรับ Plugin — `load()`, `execute()`, `unload()` |

**Dependencies:** ไม่มี (เริ่มต้น)
**เทคโนโลยี:** Python 3.12+, FastAPI, Pydantic v2, SQLModel, PostgreSQL
**สถานะเป้าหมาย:** มี Data Model + API ให้ Mini App เรียกใช้ Module/Template ได้

---

## Phase 2: Plugin System (issues 4-5)

**ทำไมต้องมาก่อน:** Plugin System คือหัวใจของ Modular — ถ้าไม่มีระบบ Plugin จะแทรกความสามารถใหม่ๆ ไม่ได้

| Issue | สิ่งที่ต้องทำ |
|-------|--------------|
| 4. Template Engine | ระบบ render template ที่ Module ต่างๆ reuse ร่วมกัน — Jinja2 + custom loader |
| 5. Plugin Registry | ลงทะเบียน plugin, ควบคุม lifecycle (install, activate, deactivate, uninstall) |

**Dependencies:** ต่อจาก Phase 1 (ต้องมี Data Model ก่อน)
**เทคโนโลยี:** Jinja2, importlib.metadata, Entry Points pattern
**สถานะเป้าหมาย:** เพิ่ม Plugin ใหม่ได้โดยไม่ต้องแก้ Core

---

## Phase 3: API Gateway (issues 6-8)

**ทำไมต้องมาก่อน:** Mini App ต้องมี Gateway เป็นทางเข้าออกเดียว — ควบคุม Auth, Rate Limit, Routing

| Issue | สิ่งที่ต้องทำ |
|-------|--------------|
| 6. API Gateway | Reverse proxy สำหรับ Mini App — ใช้ FastAPI Sub-Application หรือ Traefik |
| 7. Auth/Authorization | JWT + RBAC — Mini App แต่ละตัวมีสิทธิ์ไม่เท่ากัน |
| 8. Rate Limiting | Token bucket algorithm — ป้องกัน Mini App ตัวหนึ่งเรียก API จนล่ม |

**Dependencies:** ต่อจาก Phase 2 (Gateway ต้องรู้จัก Plugin)
**เทคโนโลยี:** FastAPI middleware, python-jose, slowapi/redis
**สถานะเป้าหมาย:** Mini App เชื่อมต่อ Gateway ได้ มี Auth + Rate Limit

---

## Phase 4: Micro-frontend & Sidecar (issues 9-11)

**ทำไมต้องมาก่อน:** เมื่อ Backend พร้อม ต้องมี Frontend Shell ที่รวม Mini App ต่างๆ

| Issue | สิ่งที่ต้องทำ |
|-------|--------------|
| 9. Micro-frontend Shell | Container App ที่โหลด Mini App แต่ละตัว — Module Federation (Webpack 5) |
| 10. Sidecar Proxy | Proxy ข้างๆ Mini App แต่ละตัว — จัดการ Auth, Log, Metrics |
| 11. Event Bus | ส่ง event ข้าม Mini App — เช่น "สร้างโปรเจคใน Plane" → แจ้ง BookStack |

**Dependencies:** ต่อจาก Phase 3 (ต้องมี Gateway + Auth ก่อน)
**เทคโนโลยี:** Webpack Module Federation, iframe + postMessage, Redis Pub/Sub หรือ NATS
**สถานะเป้าหมาย:** Mini App หลายตัวรันพร้อมกันใน Shell เดียวกัน ส่ง event ถึงกันได้

---

## Phase 5: Shared Component Library (issue 12)

**ทำไมต้องมาที่นี่:** Components ต้องออกแบบจากความต้องการจริงของ Mini App — ถ้าทำก่อนจะเดาว่าใช้ไม่ครบ

| Issue | สิ่งที่ต้องทำ |
|-------|--------------|
| 12. Shared Component Lib | UI Components ที่ Mini App ใช้ร่วมกัน — Data Table, Form, Chart, Sidebar |

**Dependencies:** ต่อจาก Phase 4 (รู้แล้วว่า Mini App ต้องการ UI อะไรบ้าง)
**เทคโนโลยี:** React + TypeScript, Storybook, TailwindCSS
**สถานะเป้าหมาย:** Mini App ใช้ Component ร่วมกัน หน้าตาเป็นเอกภาพ

---

## Phase 6: Mini App Integrations (issues 13-17)

**ทำไมต้องมาที่นี่:** Integration ต้องมี Gateway + Auth + Event Bus พร้อมก่อน — ไม่งั้นเชื่อมต่อแล้วจัดการไม่ได้

| Issue | สิ่งที่ต้องทำ | Port |
|-------|--------------|:----:|
| 13. Plane Integration | ดึง/สร้าง Project, Issue, Cycle ผ่าน Plane API | 54512 |
| 14. Planka Integration | ดึง/สร้าง Board, Card ผ่าน Planka API | 54513 |
| 15. BookStack Integration | ดึง/สร้าง Shelf, Book, Page ผ่าน BookStack API | 54515 |
| 16. OpenObserve Integration | ส่ง Log, Metrics, Alert จาก ERP ไป OpenObserve | 54514 |
| 17. Siyuan Integration | ดึง/สร้าง Notes, Docs ผ่าน Siyuan API | 54511 |

**Dependencies:** ต่อจาก Phase 3-4 (ต้องมี Gateway + Event Bus)
**เทคโนโลยี:** httpx, Bridge SDK (ของทีม Bridge), Webhook
**สถานะเป้าหมาย:** ข้อมูลไหลระหว่าง ERP Core ↔ Tools อัตโนมัติ

---

## Phase 7: AI Agent Framework (issues 18-19)

**ทำไมต้องมาที่นี่:** AI Agent ต้องมีข้อมูลจาก Tools ต่างๆ ก่อน — ต้องรอให้ Integration เสร็จ

| Issue | สิ่งที่ต้องทำ |
|-------|--------------|
| 18. AI Agent Framework | นำ inner-monologue-agent มาเป็น Agent กลางของระบบ — เพิ่ม Tool สำหรับเรียก API Gateway |
| 19. Autonomous Task Scheduler | Agent ดูตารางงานใน Plane แล้วจัดลำดับความสำคัญเอง — ทำงานตามตารางโดยไม่ต้องรอคนสั่ง |

**Dependencies:** ต่อจาก Phase 6 (Agent ต้องเข้าถึง Tools ต่างๆ ได้)
**เทคโนโลยี:** inner-monologue-agent (ของเรา), cron/APScheduler, Mistral API
**สถานะเป้าหมาย:** Agent ตรวจสอบงานใน Plane และดำเนินการเองได้

---

## Phase 8: Advanced AI (issues 20-22)

**ทำไมต้องมาที่สุดท้าย:** ต้องมี Data + Tools + Agent Framework พร้อมก่อน ถึงจะทำ Self-Healing และ Multi-Agent ได้

| Issue | สิ่งที่ต้องทำ |
|-------|--------------|
| 20. Knowledge Graph | เชื่อมข้อมูลจาก BookStack + Siyuan + Plane — Agent รู้ว่าอะไรเกี่ยวข้องกับอะไร |
| 21. Self-Healing & Auto-Recovery | Agent ดู Log จาก OpenObserve → วิเคราะห์ → แก้ไขอัตโนมัติ |
| 22. Multi-Agent Collaboration | Agent หลายตัวทำงานร่วมกัน — ตัวหนึ่งดู Plane, ตัวหนึ่งดู OpenObserve, ตัวหนึ่งเขียน Docs |

**Dependencies:** ต่อจาก Phase 7 (ต้องมี Agent Framework + Tools)
**เทคโนโลยี:** Neo4j/NetworkX, LangChain/LlamaIndex, Vector Database (Qdrant)
**สถานะเป้าหมาย:** ระบบซ่อมแซมตัวเองได้, Agent หลายตัวทำงานประสานกัน

---

## สรุป Timeline

```
Phase 1: Core Data Model & API Layer     ─── 1-2 สัปดาห์
Phase 2: Plugin System                   ─── 1 สัปดาห์
Phase 3: API Gateway                     ─── 1-2 สัปดาห์
Phase 4: Micro-frontend & Sidecar        ─── 2 สัปดาห์
Phase 5: Shared Component Library        ─── 1 สัปดาห์
Phase 6: Mini App Integrations           ─── 2-3 สัปดาห์
Phase 7: AI Agent Framework              ─── 2 สัปดาห์
Phase 8: Advanced AI                     ─── 2-3 สัปดาห์
─────────────────────────────────────────────────────
รวมประมาณ: 12-16 สัปดาห์ (3-4 เดือน)
```

## Dependencies Diagram

```
Phase 1 (Data Model) ──→ Phase 2 (Plugin) ──→ Phase 3 (Gateway) ──→ Phase 4 (Micro-frontend) ──→ Phase 5 (UI Lib)
                                                      │                                              │
                                                      └──→ Phase 6 (Integrations) ←──────────────────┘
                                                                  │
                                                                  └──→ Phase 7 (AI Agent) ──→ Phase 8 (Advanced AI)
```
