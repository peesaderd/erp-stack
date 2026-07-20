# 🌉 Bridge Server — ERP Stack Integration Layer

> ตัวกลางเชื่อมต่อ **Plane + Planka + BookStack + OpenObserve**
> ให้ทำงานร่วมกันแบบอัตโนมัติผ่าน Webhook

```
┌──────────────────────────────────────────────────────────────┐
│                     Bridge Server (:54516)                    │
│                                                              │
│  Plane Webhook ───▶ /webhooks/plane                          │
│  Planka Webhook ──▶ /webhooks/planka                         │
│  BookStack Webhook ▶ /webhooks/bookstack                     │
│  OpenObserve Alert ▶ /webhooks/openobserve                   │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐    │
│  │                 Sync Workflows                        │    │
│  │                                                      │    │
│  │  Plane Issue Created ──▶ Planka Card                  │    │
│  │  Plane Issue Updated ──▶ BookStack Page               │    │
│  │  Planka Card Moved ────▶ OpenObserve Log              │    │
│  │  OpenObserve Alert ────▶ (notify)                     │    │
│  └──────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────┘
```

---

## 📦 สิ่งที่ต้องมีก่อน

| ระบบ | พร้อมใช้? | พอร์ต |
|------|-----------|-------|
| Plane | ✅ | 54512 (API) / 54510 (Proxy) |
| Planka | ✅ | 54513 |
| BookStack | ✅ | 54515 |
| OpenObserve | ✅ | 54514 |
| Python 3.10+ | ✅ | — |
| PM2 | ✅ | — |

---

## 🚀 การติดตั้งและ Deploy

### 1. ติดตั้ง dependencies

```bash
cd /opt/bridge-server
pip install -r bridge-server/requirements.txt
```

### 2. ตั้งค่า .env

```bash
cp bridge-server/.env.example bridge-server/.env
# แล้วแก้ไขค่าต่าง ๆ ให้ตรงกับระบบ
```

### 3. Deploy ด้วย PM2

```bash
cd /opt/bridge-server
pm2 start ecosystem.config.js
pm2 save
```

### 4. ตรวจสอบ

```bash
# ดูสถานะ
pm2 status | grep bridge

# ดู logs
pm2 logs bridge-server

# ทดสอบ health
curl http://localhost:54516/health
# → {"status":"ok","service":"bridge-server"}
```

---

## 🔧 การตั้งค่า Webhook ในแต่ละระบบ

### Plane Webhook

```bash
# สร้าง webhook ใน Plane (ใช้ API)
curl -X POST "http://localhost:54512/api/workspaces/erp-roadmap/webhooks/" \
  -H "Cookie: sessionid=..." \
  -H "Content-Type: application/json" \
  -d '{
    "url": "http://localhost:54516/webhooks/plane",
    "secret": "<BRIDGE_SECRET_TOKEN>",
    "event_types": ["issue_created", "issue_updated", "issue_deleted"]
  }'
```

### Planka Webhook

```bash
# สร้าง webhook ใน Planka
curl -X POST "http://localhost:54513/api/webhooks" \
  -H "Authorization: Bearer <PLANKA_API_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Bridge Server",
    "url": "http://localhost:54516/webhooks/planka",
    "events": "cardCreate,cardUpdate,cardDelete,cardMove"
  }'
```

### BookStack Webhook

```bash
# สร้าง webhook ใน BookStack (ผ่าน Settings → Webhooks)
# URL: http://localhost:54516/webhooks/bookstack
```

### OpenObserve Alert Webhook

```bash
# ตั้งค่าใน OpenObserve Alerts
# URL: http://localhost:54516/webhooks/openobserve
```

---

## 🔄 Sync Workflows

### 1. Plane Issue → Planka Card

| เมื่อ | เกิดอะไรขึ้น |
|------|-------------|
| Plane Issue ถูกสร้าง | Bridge สร้าง Card ใน Planka Board "Task Status" |
| Plane Issue ถูกอัปเดต | Bridge อัปเดต Card ใน Planka |
| Plane Issue ถูกปิด (Done) | Bridge ย้าย Card ไป List "✅ เสร็จแล้ว" |

**การ Map State:**

| Plane State | Planka List |
|-------------|-------------|
| Backlog / Todo | 📋 รอทำ |
| In Progress | 🔄 กำลังทำ |
| Done / Cancelled | ✅ เสร็จแล้ว |

### 2. Plane Issue → BookStack Page

| เมื่อ | เกิดอะไรขึ้น |
|------|-------------|
| Plane Issue ถูกสร้าง | Bridge สร้าง Page ใน BookStack |
| Plane Issue ถูกอัปเดต | Bridge อัปเดต Page ใน BookStack |

### 3. ทุก Event → OpenObserve Log

| เมื่อ | เกิดอะไรขึ้น |
|------|-------------|
| Webhook จากระบบใดก็ตาม | Bridge ส่ง Log ไปยัง OpenObserve stream `bridge-logs` |

---

## 📡 API Endpoints

| Method | Path | คำอธิบาย |
|--------|------|----------|
| `GET` | `/health` | Health check |
| `GET` | `/api/status` | ดูว่าเชื่อมต่อระบบใดบ้าง |
| `POST` | `/webhooks/plane` | รับ webhook จาก Plane |
| `POST` | `/webhooks/planka` | รับ webhook จาก Planka |
| `POST` | `/webhooks/bookstack` | รับ webhook จาก BookStack |
| `POST` | `/webhooks/openobserve` | รับ alert จาก OpenObserve |
| `POST` | `/api/sync/plane-to-planka` | Manual sync Plane → Planka |
| `POST` | `/api/sync/plane-to-bookstack` | Manual sync Plane → BookStack |

---

## 🧪 การทดสอบ

### ทดสอบ Bridge Server ทำงาน

```bash
curl http://localhost:54516/health
# → {"status":"ok","service":"bridge-server"}
```

### ทดสอบ Manual Sync

```bash
# Plane → Planka
curl -X POST "http://localhost:54516/api/sync/plane-to-planka?issue_name=Test%20Issue"

# Plane → BookStack
curl -X POST "http://localhost:54516/api/sync/plane-to-bookstack?issue_name=Test%20Issue"
```

### ทดสอบ Webhook (จำลอง)

```bash
curl -X POST "http://localhost:54516/webhooks/plane" \
  -H "Content-Type: application/json" \
  -H "X-Bridge-Secret: <BRIDGE_SECRET_TOKEN>" \
  -d '{"event":"issue_created","payload":{"name":"Test Issue","state":{"name":"Backlog"}}}'
```

---

## 🐛 การ Debug

```bash
# ดู logs แบบ real-time
pm2 logs bridge-server

# รีสตาร์ท
pm2 restart bridge-server

# หยุด
pm2 stop bridge-server

# ดูสถานะ
pm2 status | grep bridge
```

---

## 📁 โครงสร้างไฟล์

```
bridge-server/
├── app.py                 # FastAPI main app
├── config.py              # Settings from .env
├── requirements.txt       # Python dependencies
├── ecosystem.config.js    # PM2 config
├── .env.example           # ตัวอย่าง .env
├── handlers/              # (future) แยก handler แต่ละระบบ
│   ├── __init__.py
└── README.md              # เอกสารนี้
```

---

## 🔐 ความปลอดภัย

- ทุก webhook ต้องมี header `X-Bridge-Secret` ตรงกับค่าที่ตั้งไว้
- ใช้ `.env` ในการเก็บ credentials — **ห้าม commit `.env` ขึ้น git**
- Planka API Token ควรเป็น token ที่สร้างเฉพาะสำหรับ Bridge Server
- ควรเปลี่ยน `BRIDGE_SECRET_TOKEN` เป็นค่าที่คาดเดายาก
