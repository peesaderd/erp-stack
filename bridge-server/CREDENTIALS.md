# ERP Stack — Centralized Credentials

> **Repo:** `peesaderd/erp-stack` (private)  
> **Server IP:** `89.167.82.205`  
> **Bridge Server Port:** `54517`  
> **Last Updated:** 2026-05-21

---

## 1. Plane (Project Management)

| Item | Value |
|------|-------|
| URL | http://89.167.82.205:54512 |
| Email | `admin@plane.local` |
| Password | `Plane@ERP2026` |
| Workspace Slug | `erp-company` |

> เปลี่ยน password ด้วย: `bash bridge-server/manage-password.sh <email> <new-password>`

---

## 2. Planka (Kanban Board)

| Item | Value |
|------|-------|
| URL | http://89.167.82.205:54513 |
| API Token | `U9lfSaJK_qAxYRrCrHd0ifzJGZJPEi6b9Sw3PvemM` |

> ใช้ API Token แทน login (ไม่มีระบบ user/password)

---

## 3. BookStack (Documentation / Wiki)

| Item | Value |
|------|-------|
| URL | http://89.167.82.205:54515 |
| Email | `admin@bookstack.local` |
| Password | `BookStack@ERP2026` |
| API Token ID | `bridge-server-v1` |
| API Token Secret | `ce09be093298d15b12534640cdef6c10f262da0df23e075dde8de5085441dae9` |

---

## 4. OpenObserve (Logging & Monitoring)

| Item | Value |
|------|-------|
| URL | http://89.167.82.205:54514 |
| Email | `admin@openobserve.local` |
| Password | `OpenObserve@2026` |
| Organization | `default` |

---

## 5. Bridge Server (Central API Gateway)

| Item | Value |
|------|-------|
| URL | http://89.167.82.205:54517 |
| Health Check | http://89.167.82.205:54517/api/health/full |
| PM2 Process | `bridge-server` (managed by PM2) |

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health/full` | Full health check (all services) |
| GET | `/api/plane/projects` | List Plane projects |
| GET | `/api/planka/projects` | List Planka projects |
| GET | `/api/bookstack/shelves` | List BookStack shelves |
| GET | `/api/openobserve/search` | Search OpenObserve logs |

---

## 6. OpenHands (AI Coding Agent)

| Item | Value |
|------|-------|
| URL | http://89.167.82.205:3002 |
| Login | ไม่มี (single-user tool, ใช้ตรงๆ ได้เลย) |

> ใช้สำหรับให้ AI ช่วยพัฒนาโค้ด แก้ไข bugs, สร้าง features ต่างๆ

---

## Quick Reference

```bash
# เปลี่ยน Plane password (DB + .env + restart + verify)
bash bridge-server/manage-password.sh admin@plane.local "NewPassword123"

# ดู health check ทุก service
curl http://89.167.82.205:54517/api/health/full

# SSH เข้า server
ssh openhands@89.167.82.205
```
