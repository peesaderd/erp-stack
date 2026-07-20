# 🎯 Task Card — TikTok UGC Studio + Post For Me

## 🚀 Objective
สร้าง pipeline สร้างคลิป Affiliate (AI) → Auto Post ไปทุกแพลตฟอร์ม โดยใช้ Post For Me API เป็นตัวกลาง

---

## ✅ ขั้นตอน

### 📌 Phase 1: Connect Accounts @ Post For Me
- [ ] สมัคร Post For Me ($10/เดือน, 1,000 posts)
- [ ] เชื่อมต่อ TikTok account
- [ ] เชื่อมต่อ Instagram account
- [ ] เชื่อมต่อ Facebook Page
- [ ] เชื่อมต่อ YouTube channel
- [ ] เชื่อมต่อ Threads (optional)
- [ ] ทดสอบ `python3 postforme_integration.py accounts` → เห็นทุก platform

### 📌 Phase 2: Link Pipeline → Post
- [ ] สร้าง endpoint `/tiktok/auto-post` ใน main.py
  - รับ `video_path` + `caption` + `platforms` + `schedule_at`
  - เรียก Post For Me API → ส่งไปทุก platform
- [ ] ทดสอบ: รัน pipeline_affiliate → auto post
- [ ] ทดสอบ: รัน pipeline_cartoon → auto post

### 📌 Phase 3: Schedule & Batch
- [ ] สร้าง `/tiktok/batch-schedule`
  - สร้างคลิปหลายคลิป → กำหนดตารางโพสต์รายวัน/รายสัปดาห์
  - Pipeline → Post For Me schedule API
- [ ] เชื่อมกับ cron job ในระบบ

### 📌 Phase 4: Analytics (Future)
- [ ] ดึง analytics จาก Post For Me API
- [ ] Dashboard สรุปยอดคลิปที่โพสต์ + ยอดวิว
- [ ] A/B test caption

---

## 📊 ต้นทุน

### Post For Me
| Plan | Post/เดือน | Cost | ใช้กับเรา |
|---|---|---|---|
| $10/mo | 1,000 | **$10** | ~33 โพสต์/วัน (พอดี) |
| $30/mo | 5,000 | $30 | ~166 โพสต์/วัน |
| $50/mo | 15,000 | $50 | ~500 โพสต์/วัน |

### Pipeline + Post (16 วิ clip + 4 platforms)
| Component | Cost |
|---|---|
| 🎬 Video 2 scenes @ WaveSpeed | $0.32 |
| 🔊 Voice @ MiniMax Speech | $0.01 |
| 🎵 BGM @ Mixkit | $0 |
| 📤 Post For Me (4 platforms × 1 post) | $0.01 |
| **รวม** | **~$0.34/clip** |

---

## 📌 Platform IDs ที่ต้องจด

| Platform | Account ID (from API) |
|---|---|
| TikTok | `_____` |
| Instagram | `_____` |
| Facebook Page | `_____` |
| YouTube | `_____` |

---

## 🔗 API Reference

```
# Connect account (เปิด browser)
GET  https://api.postforme.dev/v1/accounts/connect?platform=tiktok

# List accounts
GET  https://api.postforme.dev/v1/accounts

# Post now
POST https://api.postforme.dev/v1/posts
{
  "account_id": "...",
  "text": "caption",
  "media_urls": ["https://..."],
  "platform_options": {}
}

# Schedule
POST https://api.postforme.dev/v1/posts
{
  ...,
  "schedule_at": "2026-06-11T09:00:00Z"
}

# Check post status
GET  https://api.postforme.dev/v1/posts/{post_id}
```
