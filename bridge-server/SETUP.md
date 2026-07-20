# 🏗️ คู่มือการสร้าง Project ใหม่ใน ERP Stack

> สำหรับทีม: ขั้นตอนที่ต้องทำเมื่อเริ่ม Project ใหม่
> เพื่อให้ระบบทั้ง 4 ตัว (Plane + Planka + BookStack + OpenObserve) ทำงานสอดคล้องกัน

---

## 📋 ขั้นตอนการสร้าง Project ใหม่

### Step 1: สร้าง Project ใน Plane

```bash
# 1. Login เพื่อให้ได้ session cookie
curl -X POST "http://localhost:54512/api/sign-in/" \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@plane.local","password":"Plane@2026"}' \
  -c /tmp/plane-cookies.txt

# 2. สร้าง Project
curl -X POST "http://localhost:54512/api/workspaces/erp-roadmap/projects/" \
  -H "Content-Type: application/json" \
  -b /tmp/plane-cookies.txt \
  -d '{
    "name": "<ชื่อ Project>",
    "description": "<คำอธิบาย>"
  }'
```

### Step 2: สร้าง Project ใน Planka

```bash
# 1. Login เพื่อรับ JWT Token
TOKEN=$(curl -s -X POST "http://localhost:54513/api/access-tokens" \
  -H "Content-Type: application/json" \
  -d '{"usernameOrEmail":"admin@planka.local","password":"Planka@2026"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin).get('item','').get('accessToken',''))")

# 2. สร้าง Project
curl -X POST "http://localhost:54513/api/projects" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"<ชื่อ Project>","description":"<คำอธิบาย>"}'

# 3. สร้าง Board
PROJECT_ID="<project_id_from_step_2>"
curl -X POST "http://localhost:54513/api/projects/$PROJECT_ID/boards" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"<ชื่อ Board>","projectId":"'$PROJECT_ID'"}'
```

### Step 3: สร้าง Book ใน BookStack

```bash
curl -X POST "http://localhost:54515/api/books" \
  -H "Authorization: Token <TOKEN_ID>:<TOKEN_SECRET>" \
  -H "Content-Type: application/json" \
  -d '{"name":"<ชื่อ Book>","description":"<คำอธิบาย>"}'
```

### Step 4: ตั้งค่า Webhook ใน Bridge Server

```bash
# Planka Webhook
curl -X POST "http://localhost:54513/api/webhooks" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Bridge Server",
    "url": "http://localhost:54516/webhooks/planka",
    "events": "cardCreate,cardUpdate,cardDelete,cardMove"
  }'
```

### Step 5: ตรวจสอบ Bridge Server

```bash
curl http://localhost:54516/api/status
# ควรเห็นทุก service เป็น true
```

---

## 📝 Checklist ก่อนเริ่ม Project ใหม่

- [ ] **Plane**: สร้าง Project และ Cycle (Sprint) พร้อม States
- [ ] **Planka**: สร้าง Project และ Board พร้อม Lists
- [ ] **BookStack**: สร้าง Book และ Shelf (ถ้าต้องการ)
- [ ] **Bridge**: ตั้งค่า Webhook ให้ Bridge Server
- [ ] **OpenObserve**: ตรวจสอบว่า log เข้ามาหรือไม่
- [ ] **PM2**: ตรวจสอบว่า Bridge Server รันอยู่ (`pm2 status | grep bridge`)

---

## 🔄 Workflow การใช้งานประจำวัน

### นักพัฒนาทั่วไป
```
1. ดู Task ใน Plane (Sprint Backlog)
2. อัปเดตสถานะใน Plane → Bridge sync ไป Planka อัตโนมัติ
3. ดู Board ใน Planka (ภาพรวม Kanban)
4. เขียน Documentation ใน BookStack
5. ตรวจสอบ Log ใน OpenObserve
```

### Project Manager
```
1. ดูภาพรวม Sprint ใน Plane
2. ดูความคืบหน้าใน Planka Board
3. อ่าน Documentation ใน BookStack
```

### DevOps
```
1. ตรวจสอบ Bridge Server logs: pm2 logs bridge-server
2. ตรวจสอบ OpenObserve สำหรับ errors
3. รีสตาร์ท service เมื่อจำเป็น
```

---

## 🚨 การแก้ปัญหาเบื้องต้น

| ปัญหา | สาเหตุ | วิธีแก้ |
|-------|--------|--------|
| Bridge Server ไม่ทำงาน | PM2 หยุดทำงาน | `pm2 restart bridge-server` |
| Webhook ไม่เข้า | Secret ไม่ตรงกัน | ตรวจสอบ `X-Bridge-Secret` header |
| Sync ไม่ทำงาน | .env ไม่ถูกต้อง | ตรวจสอบ `.env` และ token |
| API 401 | Token หมดอายุ | สร้าง token ใหม่ |
| Planka API error | JWT หมดอายุ | Login ใหม่เพื่อรับ token |

---

## 💡 Tips

1. **ตั้งชื่อ Project ให้ตรงกัน** ทุกระบบเพื่อให้ค้นหาง่าย
2. **ใช้ Bridge Server** สำหรับ sync อัตโนมัติ — ไม่ต้อง manual สร้างงานซ้ำ
3. **ตรวจสอบ OpenObserve** เป็นประจำเพื่อดู activity ทุกระบบ
4. **อัปเดต STATUS.md** เมื่อมีความคืบหน้าสำคัญ
5. **อ่าน ARCHITECTURE.md** ก่อนเริ่มทำงานทุกครั้ง
