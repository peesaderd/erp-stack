# ERP Stack — คู่มือการใช้งานสำหรับทีม

> **⚠️ กฎเหล็ก: ก่อนเริ่มทำงานอะไรก็ตาม อ่านคู่มือนี้ให้จบก่อน**
> ปัญหาส่วนใหญ่ที่ทีมเจอคือ "ต่างคนต่างทำ คนละทาง" เพราะไม่เข้าใจภาพรวม
> ใช้เวลาอ่าน 10 นาที แล้วทุกคนจะเข้าใจตรงกัน

---

## 📖 สารบัญ

1. [ระบบนี้คืออะไร?](#1-ระบบนี้คืออะไร)
2. [ภาพรวม Services ทั้งหมด](#2-ภาพรวม-services-ทั้งหมด)
3. [Bridge Server คือหัวใจของระบบ](#3-bridge-server-คือหัวใจของระบบ)
4. [กฎเหล็ก: ก่อนเริ่ม Project ใหม่](#4-กฎเหล็กก่อนเริ่ม-project-ใหม่)
5. [วิธีใช้งานประจำวัน](#5-วิธีใช้งานประจำวัน)
6. [การทำงานร่วมกับ AI (OpenHands / Aider)](#6-การทำงานร่วมกับ-ai-openhands--aider)
7. [การ Debug เมื่อเจอปัญหา](#7-การ-debug-เมื่อเจอปัญหา)
8. [การ Push Code ขึ้น Git](#8-การ-push-code-ขึ้น-git)
9. [Reference: คำสั่งที่ใช้บ่อย](#9-reference-คำสั่งที่ใช้บ่อย)
10. [Credentials ทั้งหมด](#10-credentials-ทั้งหมด)

---

## 1. ระบบนี้คืออะไร?

ERP Stack คือชุดเครื่องมือบริหารงานและพัฒนาซอฟต์แวร์ที่ทำงานร่วมกันอัตโนมัติ:

```
┌──────────────────────────────────────────────────────────────────┐
│                    USER / TEAM (คน + AI)                          │
└──────────┬──────────┬──────────┬──────────┬──────────────────────┘
           │          │          │          │
           ▼          ▼          ▼          ▼
     ┌────────┐ ┌────────┐ ┌──────────┐ ┌──────────┐
     │ Plane  │ │ Planka │ │BookStack │ │OpenObserve│
     │:54510  │ │:54513  │ │:54515    │ │:54514    │
     │Task    │ │Kanban  │ │Docs/Wiki │ │Logging   │
     │Manager │ │Board   │ │          │ │Monitor   │
     └────┬───┘ └───┬────┘ └────┬─────┘ └────┬─────┘
          │         │          │            │
          └─────────┴──────────┴────────────┘
                    │
                    ▼
          ┌──────────────────┐
          │  🌉 Bridge Server │  ← ตัวเชื่อมทุกระบบให้ sync กัน
          │     (:54517)      │
          └──────────────────┘
```

**หลักการสำคัญ:**
- **Microservice** — แต่ละระบบแยกอิสระ มี DB ของตัวเอง
- **API-First** — ทุกอย่างสื่อสารผ่าน API เท่านั้น
- **Auto-Sync** — Bridge Server ทำให้ข้อมูลตรงกันทุกที่อัตโนมัติ
- **Mini MVP** — เริ่มจากเล็กที่สุดที่ใช้ได้ แล้วค่อยเพิ่ม

---

## 2. ภาพรวม Services ทั้งหมด

| ลำดับ | Service | URL | ใช้ทำอะไร | ใครใช้บ่อย |
|:----:|---------|-----|-----------|-----------|
| ① | **Plane** | [http://89.167.82.205:54510](http://89.167.82.205:54510) | วางแผนงาน, จัดการ Project, Track ความคืบหน้า | PM, ทุกคน |
| ② | **Planka** | [http://89.167.82.205:54513](http://89.167.82.205:54513) | Kanban Board ดูสถานะงานแบบ Real-time | ทุกคน |
| ③ | **BookStack** | [http://89.167.82.205:54515](http://89.167.82.205:54515) | เก็บเอกสาร, Spec, ความรู้ทั้งหมด | ทุกคน |
| ④ | **OpenObserve** | [http://89.167.82.205:54514](http://89.167.82.205:54514) | ดู Log, Monitor การทำงาน, Alert | DevOps |
| ⑤ | **Brain Server** | `http://89.167.82.205:8101` | AI Agent Gateway (15 tools) | AI Agent |
| ⑥ | **SiYuan** | `http://89.167.82.205:54511` | Knowledge Base ส่วนตัว | แต่ละคน |

> **💡 จำง่าย ๆ:** Plane = วางแผน, Planka = ดูสถานะ, BookStack = เก็บความรู้, OpenObserve = ดูข้อผิดพลาด

---

## 3. Bridge Server คือหัวใจของระบบ

Bridge Server เป็นตัวกลางที่ทำให้ข้อมูลจาก Plane ไปปรากฏที่ Planka และ BookStack โดยอัตโนมัติ

### มันทำงานยังไง?

```
Plane สร้าง Issue ──▶ Bridge Server ──▶ Planka (สร้าง Card)
                    │                 └──▶ BookStack (สร้าง Page)
                    │                 └──▶ OpenObserve (บันทึก Log)
```

### สิ่งที่ sync อัตโนมัติ

| เมื่อเกิดเหตุการณ์นี้ | ระบบจะทำอัตโนมัติ |
|---------------------|------------------|
| **Plane** สร้าง Issue ใหม่ | ✅ สร้าง Card ใน Planka |
| | ✅ สร้าง Page ใน BookStack |
| | ✅ บันทึก Log ใน OpenObserve |
| **Plane** อัปเดต Issue | ✅ อัปเดต Card ใน Planka |
| | ✅ อัปเดต Page ใน BookStack |
| **Plane** เปลี่ยนสถานะเป็น Done | ✅ ย้าย Card ไป List "✅ เสร็จแล้ว" |

### ตรวจสอบว่า Bridge Server ทำงานอยู่ไหม

```bash
# เรียกจากเครื่องไหนก็ได้ที่ต่อ network เดียวกัน
curl http://89.167.82.205:54517/health
# → {"status":"ok","service":"bridge-server"}

# ดูว่าระบบไหนเชื่อมต่ออยู่บ้าง
curl http://89.167.82.205:54517/api/status
# → {"plane":true,"planka":true,"bookstack":true,"openobserve":true}
```

---

## 4. กฎเหล็ก: ก่อนเริ่ม Project ใหม่

> **⛔ อย่าเริ่มทำงานใด ๆ ก่อนที่จะ Setup ทั้ง 4 ตัวนี้ให้ครบ**
>
> สาเหตุที่ทีมเคยเสียเวลาคือ: คนนึงสร้าง Task ใน Plane, อีกคนไปสร้าง Board ใน Planka,
> คนเขียน Docs ใน BookStack คนละที่กับที่ Plane อ้างถึง — พอ AI Agent มาช่วยก็งมไปคนละทาง

### ✅ Checklist ที่ต้องทำให้ครบก่อนเริ่ม

```
□ ① PLANE
   → สร้าง Project / Issue / Task
   → ระบุ: เป้าหมาย, Definition of Done, ผู้รับผิดชอบ
   → เช็คว่ามี Task เก่าที่เกี่ยวข้องหรือไม่

□ ② PLANKA
   → สร้าง Board (ถ้ายังไม่มี)
   → สร้าง Card ในคอลัมน์ To Do
   → ระบุ Due date, Members, Labels

□ ③ BOOKSTACK
   → สร้าง Shelf / Book / Page สำหรับ Project นี้
   → เขียน Spec, Requirements, การตัดสินใจทางเทคนิค
   → ถ้ามี Docs เก่า → ลิงก์มาให้ด้วย

□ ④ OPENOBSERVE
   → เช็ค Logs ว่ามี Error เดิมอะไรบ้าง
   → ถ้าเป็น service ใหม่ → ตั้งค่า Log ingestion
   → ดู Metrics ก่อนเริ่ม (เทียบหลังทำเสร็จ)
```

> **ถ้าข้อมูลใน 4 ตัวนี้ไม่พร้อม = ยังเริ่มทำงานไม่ได้**
> ให้แจ้ง PM หรือคนที่รับผิดชอบมาทำให้ครบก่อน

---

## 5. วิธีใช้งานประจำวัน

### 👨‍💻 นักพัฒนา (Developer)

```
1. เปิด Browser → ไปที่ Plane (:54510)
   → ดู Task ที่ได้รับมอบหมายใน Sprint Backlog

2. เริ่มทำงาน → อัปเดตสถานะใน Plane เป็น "In Progress"
   → Bridge Server จะ sync ไป Planka อัตโนมัติ

3. เขียนโค้ด / แก้ไขตาม Task

4. เสร็จแล้ว → อัปเดตสถานะใน Plane เป็น "Done"
   → Bridge Server จะย้าย Card ใน Planka ไป "✅ เสร็จแล้ว"

5. เขียน Documentation ใน BookStack (:54515)
   → สร้าง Page ใหม่ หรืออัปเดตของเดิม
```

### 📋 Project Manager

```
1. ดูภาพรวม Sprint ใน Plane (:54510)
   → เช็คความคืบหน้าของแต่ละ Task

2. ดู Kanban Board ใน Planka (:54513)
   → เห็นสถานะงานแบบ Real-time

3. อ่าน Documentation ใน BookStack (:54515)
   → เช็คว่า Docs อัปเดตครบหรือยัง
```

### 🔧 DevOps

```
1. ตรวจสอบ Bridge Server: pm2 logs bridge-server
2. ดู Error ใน OpenObserve (:54514)
3. รีสตาร์ท service เมื่อจำเป็น
4. เช็ค Disk: df -h
```

---

## 6. การทำงานร่วมกับ AI (OpenHands / Aider)

### หลักการ

```
┌──────────┐    ┌──────────────┐    ┌──────────┐
│  TASK    │───▶│ BRAIN SERVER │───▶│ OpenHands│
│  (Plane) │    │ (วิเคราะห์)   │    │ (ลงมือทำ)│
└──────────┘    └──────────────┘    └─────┬────┘
                                          │
                                    ┌─────▼────┐
                                    │ BookStack │
                                    │ (เขียนDocs)│
                                    └──────────┘
```

### วิธีบอกให้ AI ช่วยทำงาน

**ตัวอย่าง: สั่ง OpenHands ให้ทำงาน**
```
"ดู Task ID #123 ใน Plane แล้วช่วยทำให้เสร็จ 
 แล้วอัปเดต Docs ใน BookStack ด้วย"
```

**ตัวอย่าง: ให้ AI เช็คความคืบหน้า**
```
"เช็คสถานะ Project X ใน Plane ให้หน่อย 
 แล้วดูใน OpenObserve ว่ามี Error อะไรไหม"
```

### ข้อควรรู้เวลาใช้ AI

| เรื่อง | คำอธิบาย |
|-------|----------|
| AI รู้จักระบบผ่าน API | AI อ่าน Task จาก Plane, เขียน Docs ไป BookStack |
| AI ไม่เห็น UI | AI ทำงานผ่าน API เท่านั้น, ไม่ได้เห็นหน้า Web |
| AI ใช้ Bridge Server | Bridge Server เป็นตัวกลางให้ AI ส่งข้อมูลข้ามระบบ |
| ตรวจสอบงาน AI ได้ | ไปดูผลลัพธ์ใน Plane / Planka / BookStack ได้เลย |

---

## 7. การ Debug เมื่อเจอปัญหา

### ขั้นตอนเมื่อเจอปัญหา

```
┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐
│ 1. ดู Log│►  │ 2. ตรวจ  │►  │ 3. แก้ไข  │►  │ 4. ยืนยัน │
│   ใน     │   │ สถานะ   │   │  ตาม     │   │  ว่าหาย  │
│ OpenObserve│  │ Service  │   │  สาเหตุ  │   │          │
└──────────┘   └──────────┘   └──────────┘   └──────────┘
```

### ปัญหาที่พบบ่อยและวิธีแก้

| อาการ | สาเหตุ | วิธีแก้ |
|-------|--------|--------|
| **Bridge Server ไม่ทำงาน** | PM2 หยุดทำงาน | `pm2 restart bridge-server` |
| **Webhook ไม่เข้า** | Secret ไม่ตรงกัน | ตรวจสอบ `X-Bridge-Secret` header |
| **Sync ไม่ทำงาน** | .env ไม่ถูกต้อง | ตรวจสอบ `.env` และ token |
| **API 401** | Token หมดอายุ | สร้าง token ใหม่ |
| **Plane API error** | Session หมดอายุ | Bridge Server จะ refresh อัตโนมัติ |
| **Planka API error** | API Key ผิด | ตรวจสอบ `X-API-Key` header |
| **BookStack API error** | Token ผิด | ตรวจสอบ `Authorization: Token <id>:<secret>` |
| **Service ไม่ start** | Port ซ้ำ / Config ผิด | ดู logs, เปลี่ยน port |
| **Disk เต็ม** | Logs / Docker images สะสม | `docker system prune -f` |
| **Connection refused** | Service ยังไม่พร้อม | รอสักครู่, เช็ค health |

### คำสั่ง Debug ที่ใช้บ่อย

```bash
# เช็ค service ทำงานไหม
curl -s http://localhost:54517/health

# ดูสถานะการเชื่อมต่อทั้งหมด
curl -s http://localhost:54517/api/status

# ดู logs Bridge Server
pm2 logs bridge-server

# ดู logs Docker service
cd /workspace && docker compose logs -f plane-api

# เช็ค port ถูกใช้ไหม
ss -tlnp | grep 5451

# เช็ค disk
df -h
```

---

## 8. การ Push Code ขึ้น Git

```bash
# 1. ดูสถานะ
git status

# 2. เพิ่มไฟล์ที่ต้องการ commit
git add -A

# 3. Commit
git commit -m "feat: สิ่งที่ทำไปโดยย่อ"

# 4. Push
git push origin master
```

**รูปแบบ Commit Message:**
```
feat: เพิ่มฟีเจอร์ใหม่
fix: แก้บั๊ก
docs: อัปเดตเอกสาร
chore: งานบำรุงรักษา
refactor: ปรับโครงสร้างโค้ด
test: เพิ่ม tests
```

---

## 9. Reference: คำสั่งที่ใช้บ่อย

### SSH เข้าเซิร์ฟเวอร์
```bash
ssh openhands@89.167.82.205
# Password: OpenHands@ERP2026
```

### Bridge Server
```bash
# ดูสถานะ
pm2 status bridge-server

# ดู logs
pm2 logs bridge-server

# รีสตาร์ท
pm2 restart bridge-server

# ทดสอบ health
curl http://localhost:54517/health
```

### Docker Services
```bash
# ดูสถานะทั้งหมด
cd /workspace && docker compose ps

# ดู logs
docker compose logs -f <service-name>

# รีสตาร์ท
docker compose restart <service-name>
```

### ทดสอบ API แต่ละระบบ

```bash
# Plane (ใช้ session cookie)
curl -b "session-id=<SESSION_ID>" http://localhost:54512/api/workspaces/

# Planka (ใช้ API Key)
curl -H "X-API-Key: <API_KEY>" http://localhost:54513/api/users

# BookStack (ใช้ Token)
curl -H "Authorization: Token <TOKEN_ID>:<TOKEN_SECRET>" http://localhost:54515/api/books

# OpenObserve (ใช้ Basic Auth)
curl -u "admin@openobserve.local:OpenObserve@2026" http://localhost:54514/api/
```

---

## 10. Credentials ทั้งหมด

| Service | URL | Username | Password |
|---------|-----|----------|----------|
| **Plane** | `http://89.167.82.205:54510` | `admin@plane.local` | `Plane@2026` |
| **Planka** | `http://89.167.82.205:54513` | `admin@planka.local` | `admin` |
| **BookStack** | `http://89.167.82.205:54515` | `admin@bookstack.local` | `BookStack@2026` |
| **OpenObserve** | `http://89.167.82.205:54514` | `admin@openobserve.local` | `OpenObserve@2026` |
| **SiYuan** | `http://89.167.82.205:54511` | — | — |
| **Server SSH** | `89.167.82.205` | `openhands` | `OpenHands@ERP2026` |

### API Keys / Tokens (สำหรับ Developer)

| ระบบ | Token | ใช้ยังไง |
|------|-------|---------|
| **Plane** | Session Cookie (refresh อัตโนมัติ) | ใช้ผ่าน Bridge Server |
| **Planka** | `U9lfSaJK_qAxYRrCrHd0ifzJGZJPEi6b9Sw3PvemM` | Header: `X-API-Key: <key>` |
| **BookStack** | ID: `bridge-server-v1` / Secret: `ce09be093298d15b12534640cdef6c10f262da0df23e075dde8de5085441dae9` | Header: `Authorization: Token <id>:<secret>` |

---

## 📚 เอกสารอ้างอิงเพิ่มเติม

| เอกสาร | คำอธิบาย |
|--------|----------|
| [ARCHITECTURE.md](ARCHITECTURE.md) | สถาปัตยกรรมระบบแบบละเอียด |
| [STATUS.md](STATUS.md) | สถานะล่าสุดของแต่ละ service |
| [bridge-server/BRIDGE.md](bridge-server/BRIDGE.md) | รายละเอียด Bridge Server |
| [bridge-server/SETUP.md](bridge-server/SETUP.md) | วิธีตั้งค่า Project ใหม่ |

---

> **💡 Tip: ถ้าสงสัยหรือไม่แน่ใจ ให้ถามในทีมก่อนลงมือทำ**
> เสียเวลาถาม 5 นาที ดีกว่าเสียเวลาทำผิดคนละทาง 2 วัน
