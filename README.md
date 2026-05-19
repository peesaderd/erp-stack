# ERP Stack

ERP Stack ประกอบด้วย 4 services หลัก: Plane, Planka, BookStack, OpenObserve
รันบนเซิร์ฟเวอร์เดียวด้วย Docker Compose

## 🖥️ Server

| รายการ | ค่า |
|--------|-----|
| IP | `89.167.82.205` |
| SSH | `ssh openhands@89.167.82.205` |
| Password | `OpenHands@ERP2026` |
| Disk | 150G (ใช้ ~91G, เหลือ 54G) |

## 📦 Services

### 1. Plane — Project Management
| รายการ | ค่า |
|--------|-----|
| URL | `http://89.167.82.205:54510` |
| Status | ✅ Sign-in ใช้ได้, Workspace แรกสร้างแล้ว |

### 2. Planka — Kanban Board
| รายการ | ค่า |
|--------|-----|
| URL | `http://89.167.82.205:54511` |
| API Token | ✅ สร้างไว้แล้ว (Board + Task) |

### 3. BookStack — Documentation/Wiki
| รายการ | ค่า |
|--------|-----|
| URL | `http://89.167.82.205:54512` |
| API Token | ✅ สร้างไว้แล้ว |

### 4. OpenObserve — Logging & Monitoring
| รายการ | ค่า |
|--------|-----|
| URL | `http://89.167.82.205:54514` |
| Auth | Basic Auth (Service Account) |
| Username | `brain-server@openobserve.local` |
| Password | `sg7PFmXAIiG3W0Ny` |

**วิธีเรียก API:**
```bash
echo -n "brain-server@openobserve.local:sg7PFmXAIiG3W0Ny" | base64
# ได้: YnJhaW4tc2VydmVyQG9wZW5vYnNlcnZlLmxvY2FsOnNnN1BGbVhBSWlHM1cwTnk=

curl -H "Authorization: Basic YnJhaW4tc2VydmVyQG9wZW5vYnNlcnZlLmxvY2FsOnNnN1BGbVhBSWlHM1cwTnk=" \
  http://89.167.82.205:54514/api/default/users
```

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

## ⚠️ ข้อควรระวัง
- อย่า expose port services ตรงสู่ internet โดยไม่มีการป้องกัน
- ถ้า service ไหนพัก ให้ตรวจสอบ logs ก่อน: `docker compose logs [service-name]`
- Token ต่าง ๆ ควรเปลี่ยนเป็นประจำตามนโยบายความปลอดภัยขององค์กร
