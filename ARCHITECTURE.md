# 🏗️ ERP Stack — สถาปัตยกรรมระบบ

> เอกสารนี้คือ **Single Source of Truth** สำหรับทุกคนที่เข้ามาทำงานในระบบ
> อ่านให้เข้าใจก่อนลงมือทำอะไรก็ตาม

---

## 📋 สารบัญ

1. [ภาพรวมสถาปัตยกรรม](#1-ภาพรวมสถาปัตยกรรม)
2. [Microservice Architecture](#2-microservice-architecture)
3. [Mini MVP Approach](#3-mini-mvp-approach)
4. [Services ทั้งหมด](#4-services-ทั้งหมด)
5. [Workflow การทำงาน](#5-workflow-การทำงาน)
6. [การเชื่อมต่อระหว่าง Services](#6-การเชื่อมต่อระหว่าง-services)
7. [Development Workflow](#7-development-workflow)
8. [การ Debug](#8-การ-debug)
9. [Environment & Credentials](#9-environment--credentials)

---

## 1. ภาพรวมสถาปัตยกรรม

```
┌─────────────────────────────────────────────────────────────┐
│                     USER / TEAM                              │
│         (คน / AI Agent / OpenHands / Aider)                  │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                    🧠 BRAIN SERVER (:8101)                    │
│  ตัวกลางเชื่อมทุก service มี 15 tools                        │
│  - task_create / task_status / task_list                     │
│  - bookstack_search / bookstack_get_page / bookstack_list_books│
│  - siyuan_search / siyuan_get_doc / siyuan_create_doc        │
│  - ollama_chat / deepseek_chat                               │
│  - memory_get / memory_set / memory_list                     │
│  - server_check                                              │
└──┬──────────┬──────────┬──────────┬──────────┬──────────────┘
   │          │          │          │          │
   ▼          ▼          ▼          ▼          ▼
┌──────┐ ┌────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
│Plane │ │Planka  │ │BookStack │ │OpenObserve│ │ SiYuan   │
│:54510│ │:54513  │ │:54515    │ │:54514    │ │ :54511   │
│Task  │ │Kanban  │ │Docs/Wiki │ │Logging   │ │Knowledge │
│Mgmt  │ │Board   │ │          │ │Monitoring│ │ Base     │
└──────┘ └────────┘ └──────────┘ └──────────┘ └──────────┘
```

### หลักการสำคัญ

| หลักการ | คำอธิบาย |
|---------|----------|
| **Microservice** | แต่ละ service แยกอิสระจากกัน, มี DB ของตัวเอง, deploy แยกได้ |
| **Mini MVP** | เริ่มจากเล็กที่สุดที่ใช้งานได้ → ค่อย ๆ เพิ่มทีละส่วน |
| **API-First** | ทุก service สื่อสารผ่าน API เท่านั้น |
| **Single Source of Truth** | เอกสารนี้คือที่เดียวที่ใช้อ้างอิง |
| **Task-Driven** | ทุกอย่างเริ่มจาก Task ใน Task Manager เสมอ |

---

## 2. Microservice Architecture

### ทำไมต้อง Microservice?

1. **แยกอิสระ** — แต่ละ service มี DB, config, dependencies ของตัวเอง
2. **ล้มไม่โดนกัน** — service หนึ่งพัง ไม่กระทบตัวอื่น
3. **อัปเกรดทีละตัว** — ไม่ต้องหยุดทั้งระบบ
4. **เลือก tech stack ต่างกันได้** — Plane ใช้ Python, Planka ใช้ Node.js, ฯลฯ

### การสื่อสารระหว่าง Service

```
┌─────────────┐         HTTP/REST         ┌─────────────┐
│  Service A  │ ◄──────────────────────►  │  Service B  │
└─────────────┘                           └─────────────┘
       │                                        │
       │           HTTP/REST                    │
       └──────────────────┬─────────────────────┘
                          │
                   ┌──────▼──────┐
                   │ Brain Server │
                   │  (API Gateway)│
                   └─────────────┘
```

- **ไม่มี direct DB access** — ห้าม service หนึ่งอ่าน DB ของอีก service โดยตรง
- **สื่อสารผ่าน API เท่านั้น** — ใช้ REST API หรือ Brain Server เป็นตัวกลาง
- **Authentication** — ทุก service ใช้ API Token หรือ Basic Auth

---

## 3. Mini MVP Approach

### หลักการ

> "ทำเท่าที่จำเป็นให้ใช้งานได้ก่อน แล้วค่อยเพิ่ม"

### ขั้นตอนการพัฒนา

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│ 1. Core  │ ►  │ 2. Basic │ ►  │ 3. Test  │ ►  │ 4. Ship  │
│   Feature│    │   UI/API │    │          │    │         │
└──────────┘    └──────────┘    └──────────┘    └──────────┘
     │              │              │              │
     ▼              ▼              ▼              ▼
  ทำแค่พอใช้     ใช้งานได้     มี Bug? แก้     ใช้งานจริง
  ได้จริง ๆ      ไม่ต้องสวย                    ในทีม
```

### คำถามก่อนเริ่มทำอะไรก็ตาม

1. **อะไรคือ Minimum Viable?** — เล็กที่สุดที่ยังใช้งานได้
2. **จำเป็นต้องมีตอนนี้ไหม?** — หรือเอาไว้ทีหลังได้
3. **มี service อะไรที่ทำสิ่งนี้อยู่แล้ว?** — ใช้ของที่มีก่อน
4. **ถ้าไม่ทำตอนนี้จะเกิดอะไรขึ้น?** — ถ้าไม่ตาย ก็ไว้ก่อน

---

## 4. Services ทั้งหมด

### 4.1 Plane — Project Management (Task Manager หลัก)

| รายการ | ค่า |
|--------|-----|
| URL | `http://89.167.82.205:54510` |
| บทบาท | วางแผนงาน, จัดการ Project, Track ความคืบหน้า |
| API | REST API ที่ `/api/` |
| ใช้เมื่อ | เริ่มงานใหม่, วางแผน Sprint, มอบหมายงาน |

**การใช้งานใน workflow:**
1. เปิด Issue ใน GitHub หรือสร้าง Task ใน Plane
2. ระบุ Definition of Done ให้ชัดเจน
3. Brain Server อ่าน Task จาก Plane API
4. ทำงานเสร็จ → อัปเดตสถานะใน Plane

### 4.2 Planka — Kanban Board

| รายการ | ค่า |
|--------|-----|
| URL | `http://89.167.82.205:54513` |
| บทบาท | แสดงสถานะงานแบบ Real-time (To Do → Doing → Done) |
| API Token | ✅ สร้างไว้แล้ว |
| ใช้เมื่อ | ดูความคืบหน้ารายวัน, เห็นภาพรวมงาน |

### 4.3 BookStack — Documentation / Wiki

| รายการ | ค่า |
|--------|-----|
| URL | `http://89.167.82.205:54515` |
| บทบาท | เก็บเอกสารทั้งหมดของระบบ |
| API Token | ✅ สร้างไว้แล้ว |
| ใช้เมื่อ | เขียน Docs, อ่าน Spec, เก็บ Knowledge |

### 4.4 OpenObserve — Logging & Monitoring

| รายการ | ค่า |
|--------|-----|
| URL | `http://89.167.82.205:54514` |
| บทบาท | เก็บ Logs, Monitor การทำงาน, Alert |
| Auth | Basic Auth (Service Account) |
| ใช้เมื่อ | ดู Error, วิเคราะห์ Performance, Debug |

### 4.5 SiYuan — Knowledge Base

| รายการ | ค่า |
|--------|-----|
| URL | `http://89.167.82.205:54511` |
| บทบาท | เก็บความรู้, บันทึกการตัดสินใจ, Personal Notes |
| ใช้เมื่อ | จดบันทึก, ค้นหาข้อมูลเก่า, เก็บ Reference |

### 4.6 Brain Server — AI Agent Gateway

| รายการ | ค่า |
|--------|-----|
| URL | `http://89.167.82.205:8101` |
| บทบาท | ตัวกลางเชื่อมทุก service, มี tools ให้ AI เรียกใช้ |
| Tools | 15 tools (task, bookstack, siyuan, memory, chat, server) |
| ใช้เมื่อ | AI Agent ต้องการทำงานข้าม service |

**Tools ที่มี:**
```
📋 Task Management     : task_create, task_status, task_list
📚 BookStack           : bookstack_search, bookstack_get_page, bookstack_list_books
📝 SiYuan              : siyuan_search, siyuan_get_doc, siyuan_create_doc
🧠 AI Chat             : ollama_chat, deepseek_chat
💾 Memory              : memory_get, memory_set, memory_list
🔍 System              : server_check
```

### 4.7 OpenHands — AI Coding Agent

| รายการ | ค่า |
|--------|-----|
| บทบาท | เขียนโค้ด, แก้ Bug, ทำตาม Task |
| ทำงานใน | `/workspace` (runtime ปัจจุบัน) |
| เชื่อมต่อกับ | Brain Server API, GitHub, Terminal |

### 4.8 Aider — AI Pair Programmer

| รายการ | ค่า |
|--------|-----|
| สถานะ | ⏳ รอติดตั้ง (เมื่อจำเป็น) |
| บทบาท | AI pair programming ใน terminal |
| ใช้เมื่อ | ต้องการ AI ช่วยเขียนโค้ดแบบ interactive |

---

## 5. Workflow การทำงาน

### ⚠️ กฎเหล็ก: ก่อนเริ่ม Project ใหม่ ทุกครั้ง

> **ห้ามเริ่มทำงานใด ๆ ก่อนที่จะ Setup ทั้ง 4 ตัวนี้ให้ครบ**
> ไม่งั้นทีมจะงมกันคนละทิศคนละทาง — AI Agent ก็ไม่รู้จะหาข้อมูลจากไหน

```
┌──────────────────────────────────────────────────────────────────┐
│              🚀 ขั้นตอนบังคับก่อนเริ่ม Project ใหม่                │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  1. 📋 PLANE                                                      │
│     → สร้าง Project / Issue / Task                                │
│     → ระบุ: เป้าหมาย, Definition of Done, ผู้รับผิดชอบ            │
│     → เช็คว่ามี Task เก่าที่เกี่ยวข้องหรือไม่                      │
│                                                                   │
│  2. 📌 PLANKA                                                     │
│     → สร้าง Board (ถ้ายังไม่มี)                                    │
│     → สร้าง Card ในคอลัมน์ To Do                                   │
│     → ระบุ Due date, Members, Labels                              │
│                                                                   │
│  3. 📚 BOOKSTACK                                                  │
│     → สร้าง Shelf / Book / Page สำหรับ Project นี้                │
│     → เขียน Spec, Requirements, การตัดสินใจทางเทคนิค              │
│     → ถ้ามี Docs เก่า → ลิงก์มาให้ด้วย                            │
│                                                                   │
│  4. 📊 OPENOBSERVE                                                │
│     → เช็ค Logs ว่ามี Error เดิมอะไรบ้าง                          │
│     → ถ้าเป็น service ใหม่ → ตั้งค่า Log ingestion                │
│     → ดู Metrics ก่อนเริ่ม (เทียบหลังทำเสร็จ)                     │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

> **ถ้าข้อมูลใน 4 ตัวนี้ไม่พร้อม = ยังเริ่มทำงานไม่ได้**
> ให้แจ้งผู้รับผิดชอบมาทำให้ครบก่อน

---

### 5.1 เริ่มงานใหม่ (หลังจาก Setup ครบแล้ว)

```
┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐
│ 1. IDEA  │►  │ 2. TASK  │►  │ 3. PLAN  │►  │ 4. DO    │►  │ 5. DONE  │
│          │   │  ISSUE   │   │          │   │          │   │          │
└──────────┘   └──────────┘   └──────────┘   └──────────┘   └──────────┘
                    │              │              │              │
                    ▼              ▼              ▼              ▼
               เปิด Issue ใน  คุยให้จบ:     ลงมือทำ:     อัปเดตสถานะ
               GitHub/Plane   What? Why?   OpenHands/   ปิด Issue
                              How?         Aider        เขียน Docs
                              Definition
                              of Done
```

### 5.2 Task → Brain Server → Aider → Debug

```
┌──────────────────────────────────────────────────────────────────┐
│                    WORKFLOW COMPLETE                              │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────┐     ┌──────────────┐     ┌──────────┐              │
│  │ TASK     │────►│ BRAIN SERVER │────►│ AIDER /  │              │
│  │ MANAGER  │     │ (วิเคราะห์    │     │ OpenHands │              │
│  │ (Plane/  │     │  งาน, วางแผน) │     │ (ลงมือทำ) │              │
│  │  Planka) │     │              │     │          │              │
│  └──────────┘     └──────────────┘     └──────────┘              │
│       │                                      │                    │
│       │                                      ▼                    │
│       │                              ┌──────────────┐            │
│       └──────────────────────────────│ DEBUG / TEST │            │
│                                      │ (ตรวจสอบผล)  │            │
│                                      └──────────────┘            │
│                                             │                    │
│                                             ▼                    │
│                                      ┌──────────────┐            │
│                                      │   DOCS /     │            │
│                                      │   BOOKSTACK  │            │
│                                      └──────────────┘            │
└──────────────────────────────────────────────────────────────────┘
```

### 5.3 ขั้นตอนโดยละเอียด

| ขั้นตอน | ใครทำ | สิ่งที่ต้องทำ |
|---------|-------|-------------|
| **0. Setup Project** | ผู้รับผิดชอบ | ✅ **ตั้งค่าให้ครบ 4 อย่างก่อน**: Plane (Task) + Planka (Board) + BookStack (Docs) + OpenObserve (Logs) |
| **1. มี Idea** | ใครก็ได้ | คิดว่างานนี้คืออะไร, ทำไมต้องทำ |
| **2. เปิด Issue** | คน提议 | ใช้ GitHub Issue Template กรอกให้ครบ |
| **3. คุยให้จบ** | ทีม / AI | ตกลง Definition of Done, แนวทาง, ผลกระทบ |
| **4. วางแผน** | Brain Server | วิเคราะห์งาน, แตกเป็น subtasks, ตรวจสอบ docs |
| **5. ลงมือทำ** | OpenHands/Aider | เขียนโค้ด, แก้ไขไฟล์, ทดสอบ |
| **6. Debug** | ผู้ทำ | ตรวจสอบ Logs (OpenObserve), แก้ Bug |
| **7. เขียน Docs** | ผู้ทำ | อัปเดต BookStack / ARCHITECTURE.md |
| **8. ปิด Task** | ผู้ทำ | อัปเดตสถานะใน Plane/Planka, Push code |

---

## 6. การเชื่อมต่อระหว่าง Services

```
Service          ────เชื่อมต่อ────►  Service          หมายเหตุ
─────────────────────────────────────────────────────────────
Brain Server     ────HTTP API────►  Plane             จัดการ Task
Brain Server     ────HTTP API────►  BookStack         ค้นหา/อ่าน Docs
Brain Server     ────HTTP API────►  SiYuan            ค้นหา/อ่าน Knowledge
Brain Server     ────HTTP API────►  OpenObserve       ส่ง Log (future)
OpenHands        ────HTTP API────►  Brain Server      เรียก Tools
OpenHands        ────SSH───────►   Remote Server     รันคำสั่ง
OpenHands        ────Git───────►   GitHub            Push Code
Aider            ────Terminal────►  Local Files       แก้ไขโค้ด
Plane            ────Webhook────►  (future)          แจ้งเตือน
OpenObserve      ────Ingest────►   Logs จากทุก service
```

---

## 7. Development Workflow

### 7.1 Git Workflow

```
master ──────► ทำงานตรง master (Mini MVP → ไม่มี branch ซับซ้อน)
     │
     ├── 1. git pull
     ├── 2. ทำงาน / แก้ไข
     ├── 3. git add + git commit
     └── 4. git push
```

### 7.2 Commit Message Format

```
<type>: <คำอธิบายสั้น>

ประเภท: feat, fix, docs, chore, refactor, test
ตัวอย่าง:
  feat: Add user login API
  fix: Fix 401 error in OpenObserve auth
  docs: Update ARCHITECTURE.md with new service
```

### 7.3 ก่อน Commit ทุกครั้ง

- [ ] ทดสอบว่าใช้งานได้
- [ ] ไม่มีไฟล์ขยะ (__pycache__, .tmp, ฯลฯ)
- [ ] ไม่มี Token/Password ในโค้ด
- [ ] อัปเดต Docs ถ้ามีการเปลี่ยนแปลง

---

## 8. การ Debug

### 8.1 ขั้นตอนเมื่อเจอปัญหา

```
┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐
│ 1. ดู Log│►  │ 2. ตรวจ  │►  │ 3. แก้ไข  │►  │ 4. ยืนยัน │
│   ใน     │   │ สถานะ   │   │  ตาม     │   │  ว่าหาย  │
│ OpenObserve│  │ Service  │   │  สาเหตุ  │   │          │
└──────────┘   └──────────┘   └──────────┘   └──────────┘
```

### 8.2 คำสั่ง Debug

```bash
# เช็ค service ทำงานไหม
curl -s http://localhost:<PORT>/health

# ดู logs ของ service
docker compose logs -f <service-name>

# เช็ค disk
df -h

# เช็ค port ถูกใช้ไหม
ss -tlnp | grep <PORT>

# ทดสอบ API
curl -v http://localhost:<PORT>/api/...
```

### 8.3 ปัญหาที่พบบ่อย

| อาการ | สาเหตุที่เป็นไปได้ | วิธีแก้ |
|-------|-------------------|--------|
| Service ไม่ start | Port ซ้ำ / Config ผิด | ดู logs, เปลี่ยน port |
| API 401 | Token หมดอายุ / ผิด | สร้าง Token ใหม่ |
| Disk เต็ม | Logs / Docker images สะสม | `docker system prune` |
| Connection refused | Service ยังไม่พร้อม | รอสักครู่, เช็ค health |
| Brain Server Error | .env ไม่ถูกต้อง | เช็ค Token ใน .env |

---

## 9. Environment & Credentials

### 9.1 Server

| รายการ | ค่า |
|--------|-----|
| IP | `89.167.82.205` |
| SSH | `ssh openhands@89.167.82.205` |
| Password | `OpenHands@ERP2026` |
| Disk | 150G (ใช้ ~91G, เหลือ 54G) |

### 9.2 Services

| Service | URL | Username | Password |
|---------|-----|----------|----------|
| Plane | `http://89.167.82.205:54510` | `admin@plane.local` | `Plane@2026` |
| Planka | `http://89.167.82.205:54513` | `admin@planka.local` | `Admin@2026` |
| BookStack | `http://89.167.82.205:54515` | `admin@bookstack.local` | `BookStack@2026` |
| OpenObserve | `http://89.167.82.205:54514` | `admin@openobserve.local` | `OpenObserve@2026` |
| SiYuan | `http://89.167.82.205:54511` | — | — |

### 9.3 GitHub

| รายการ | ค่า |
|--------|-----|
| Repo | `https://github.com/peesaderd/erp-stack` |
| Branch | `master` |

---

## 🔄 การอัปเดตเอกสารนี้

เมื่อมีการเปลี่ยนแปลงสถาปัตยกรรม:

1. แก้ไข `/workspace/ARCHITECTURE.md`
2. Commit และ Push
3. แจ้งทีมให้รู้

> **ทุกคนมีสิทธิ์แก้ไขเอกสารนี้ได้ — แต่ต้องรับผิดชอบว่าข้อมูลถูกต้อง**

---

*เอกสารนี้เป็น Single Source of Truth สำหรับ ERP Stack*
*อัปเดตล่าสุด: 2026-05-19*
