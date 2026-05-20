# ERP Stack

ERP Stack ประกอบด้วย 6 services หลัก: Plane, Planka, BookStack, OpenObserve, SiYuan, Brain Server
รันบนเซิร์ฟเวอร์เดียว

> **📖 ก่อนเริ่มทำงานอะไรก็ตาม อ่าน [ARCHITECTURE.md](ARCHITECTURE.md) ให้เข้าใจก่อน**
> เป็น Single Source of Truth สำหรับสถาปัตยกรรมและ workflow ทั้งหมด

## 🖥️ Server

| รายการ | ค่า |
|--------|-----|
| IP | `89.167.82.205` |
| SSH | `ssh openhands@89.167.82.205` |
| Password | `OpenHands@ERP2026` |
| Disk | 150G (ใช้ ~127G, เหลือ 17G) |

## 📦 Services

> ดูรายละเอียดทั้งหมดได้ใน [ARCHITECTURE.md](ARCHITECTURE.md#4-services-ทั้งหมด)

| Service | URL | บทบาท |
|---------|-----|--------|
| **Plane** | `http://89.167.82.205:54510` | Project Management (Task Manager หลัก) |
| **SiYuan** | `http://89.167.82.205:54511` | Knowledge Base |
| **Planka** | `http://89.167.82.205:54513` | Kanban Board |
| **OpenObserve** | `http://89.167.82.205:54514` | Logging & Monitoring |
| **BookStack** | `http://89.167.82.205:54515` | Documentation / Wiki |
| **Brain Server** | `http://89.167.82.205:8101` | AI Agent Gateway (15 tools) |

## 🐙 GitHub

| รายการ | ค่า |
|--------|-----|
| Repo | `https://github.com/peesaderd/erp-stack` |
| Branch | `master` |

## 🚀 การใช้งาน

### SSH เข้าเซิร์ฟเวอร์
```bash
ssh openhands@89.167.82.205
# Password: OpenHands@ERP2026
```

### ดูสถานะ services
```bash
cd /workspace
docker compose ps
```

### รีสตาร์ท service
```bash
cd /workspace
docker compose restart [service-name]
```

### ดู logs
```bash
cd /workspace
docker compose logs -f [service-name]
```

## 🗄️ Docker Compose Files

| File | Service |
|------|---------|
| `docker-compose.yml` | รวมทุก services |
| `docker-compose.network.yml` | Shared networks |
| `docker-compose.plane.yml` | Plane (Project Management) |
| `docker-compose.planka.yml` | Planka (Kanban) |
| `docker-compose.bookstack.yml` | BookStack (Documentation) |
| `docker-compose.siyuan.yml` | SiYuan (Knowledge Base) |
| `docker-compose.openobserve.yml` | OpenObserve (Logging) |

## 🧠 Brain Server

Brain Server เป็นโปรเจคใหม่สำหรับ AI-powered development automation
- **Plane**: Project "Brain Server" ใน workspace `erp-roadmap` — `http://89.167.82.205:54510`
- **Planka**: Project "Brain Server" Board "Brain Server Board" — `http://89.167.82.205:54513`
- ดูสถานะล่าสุดได้ใน [STATUS.md](STATUS.md)

## ⚠️ ข้อควรระวัง
- อย่า expose port services ตรงสู่ internet โดยไม่มีการป้องกัน
- ถ้า service ไหนพัก ให้ตรวจสอบ logs ก่อน: `docker compose logs [service-name]`
- Token ต่าง ๆ ควรเปลี่ยนเป็นประจำตามนโยบายความปลอดภัยขององค์กร
