# 🚀 Viral Clone Pipeline — TikTok UGC Studio

## สถานการณ์ปัจจุบัน (2026-06-19)

| Component | สถานะ | หมายเหตุ |
|-----------|--------|----------|
| Scout Targets | ✅ manual | user กรอก username เอง |
| Scout Trends | ✅ rule-based | ไม่ได้ต่อ API จริง |
| Scout Analyze | ✅ LLM-based | วิเคราะห์ viral patterns |
| Script Gen | ✅ LLM | 5 template structures |
| TTS | ✅ gTTS | เสียงไทย |
| Video Gen (Wan 2.7) | ✅ Prodia/Fal.ai | img2vid + lip sync |
| FFmpeg Composer | ✅ | merge, overlay, effects |
| PFM AutoPost | ✅ | 7/10 platforms |
| **Facebook/IG Scout** | ❌ **ยังไม่มี** | **เป้าหมายใหม่** |

---

## 📋 แผนรวม — Viral Clone Pipeline

```
Facebook/IG API
     ↓ (1) รับ Viral Clip + Engagement Data
Scout Analyzer
     ↓ (2) วิเคราะห์โครงสร้างคลิป
Script Generator
     ↓ (3) สร้าง Script Clone
TTS (gTTS)
     ↓ (4) พากย์เสียงใหม่
SAM3 Quality Gate
     ↓ (5) ตรวจสอบรูป
Video Gen (Prodia/Fal.ai)
     ↓ (6) สร้างคลิปใหม่
FFmpeg Composer
     ↓ (7) ตัดต่อ + Effect
PFM AutoPost
     ↓ (8) โพสต์ข้ามแพลตฟอร์ม
```

---

## 🔨 Phase 1 — Facebook/Instagram Scout (WEEK 1)

### 1.1 Facebook Graph API Integration

**ไฟล์ใหม่:** `scout/facebook_scout.py`

```python
class FacebookScout:
    def __init__(self, access_token):
        self.api = "https://graph.facebook.com/v21.0"
        self.token = access_token

    async def search_viral_posts(self, niche: str, min_engagement: int = 1000):
        """
        ค้นหา Public Posts ที่มียอด Engagement สูงจาก Facebook/IG
        - ใช้ Facebook Content Library API / Posts Search
        - กรองตาม niche keywords + ภาษาไทย
        - ดึง: text, media_url, likes, shares, comments, created_time
        """
        pass

    async def get_post_insights(self, post_id: str):
        """
        ดึง insights เฉพาะของ post
        - reach, impressions, engagement_rate
        """
        pass

    async def download_video(self, video_url: str):
        """
        ดาวน์โหลดวิดีโอ viral มาวิเคราะห์ frame
        - ใช้ SAM3 quality gate ตรวจสอบ
        """
        pass

    async def detect_viral_patterns(self, post_data: dict):
        """
        วิเคราะห์ว่า ทำไมคลิปนี้ถึง viral:
        - Hook type (problem/question/result/shock)
        - Video length (15s/30s/60s)
        - Caption structure
        - CTA type
        """
        pass
```

### 1.2 API Routes (ใน main.py)

```python
@app.get("/scout/facebook/niches")
async def facebook_list_niches():
    """รายการ Niche ที่พร้อม Scout"""
    
@app.post("/scout/facebook/search")
async def facebook_search_viral(niche: str, min_engagement: int):
    """ค้นหา Viral Post จาก Facebook/IG"""

@app.get("/scout/facebook/post/{post_id}")
async def facebook_analyze_post(post_id: str):
    """วิเคราะห์ Post เดียว"""

@app.post("/scout/facebook/clone")
async def facebook_generate_clone(post_id: str, product_name: str):
    """
    Flow จบใน endpoint เดียว:
    1. ดึง post data จาก Facebook
    2. วิเคราะห์ viral structure
    3. สร้าง clone script
    4. ส่งเข้าพipeline (TTS → Video → Post)
    """
```

### 1.3 Frontend — Scout Tab ใหม่

เพิ่ม Tab "📱 Scout" ข้าง "📱 Post For Me":

```
┌──────────────────────────────┐
│ 📱 Scout   📱 Post For Me    │ ← Tab ใหม่
├──────────────────────────────┤
│ Facebook/IG Scout            │
│ ─────────────────────────── │
│ [Niche dropdown] [Search]    │
│                              │
│ ผลการค้นหา (Grid Cards):     │
│ ┌────┐ ┌────┐ ┌────┐        │
│ │vid1│ │vid2│ │vid3│        │
│ │🔥  │ │🔥  │ │🔥  │        │
│ │2.1K│ │5.3K│ │1.8K│        │
│ └────┘ └────┘ └────┘        │
│                              │
│ [Analyze] [Clone → Pipeline] │
└──────────────────────────────┘
```

---

## ⚙️ Phase 2 — Viral Analyzer Enhancement (WEEK 1-2)

### 2.1 Facebook → TikTok Mapping

วิเคราะห์ว่าคลิป Facebook ที่ viral มี pattern แบบไหน แล้วแปลงเป็น TikTok format:

| Factor | Facebook | TikTok |
|--------|----------|--------|
| Duration | 30-60s | 15-30s |
| Caption | Long text | Short + hashtags |
| Hook rate | 3-5s | 1-3s |
| Pacing | Medium | Fast |
| CTA | Share/Comment | Follow/Link in Bio |

### 2.2 Auto Clone Pipeline

เมื่อกด "Clone → Pipeline" จะวิ่ง workflow อัตโนมัติ:

1. **FacebookScout** → ดึง post + media
2. **Analyzer** → วิเคราะห์ viral score + pattern
3. **ScriptGen** → สร้าง script clone + ปรับเป็น TikTok style
4. **SAM3** → ตรวจสอบรูป quality
5. **TTS** → สร้างเสียงพากย์ไทย
6. **VideoGen** → Prodia Wan 2.7 img2vid + lip sync
7. **Composer** → FFmpeg merge + effect
8. **PFM** → AutoPost ข้าม platform (TikTok, FB, IG, YT)

---

## 📊 Phase 3 — Monitor & Optimization (WEEK 2-3)

### 3.1 Post Performance Tracking

```python
class ViralMonitor:
    """
    ติดตามผลหลังจากโพสต์:
    - views, likes, shares, comments
    - follower growth rate
    - engagement rate (%)
    - สรุปว่าคลิปไหน clone แล้วได้ผลดี
    """
    async def track_post(self, pfm_post_id: str): ...
    async def compare_clones(self, original_viral: dict, clone_result: dict): ...
    async def suggest_optimizations(self, post_stats: dict): ...
```

### 3.2 A/B Testing Loop

```
Original Viral Clip (จาก FB/IG)
         ↓
Clone A (Script A + Style A) → โพสต์ → Track Performance
Clone B (Script B + Style B) → โพสต์ → Track Performance
         ↓
วิเคราะห์ว่า Pattern ไหนเวิร์คที่สุด
         ↓
ปรับปรุง pipeline criteria
         ↓
วน loop
```

---

## 🏗️ Architecture Diagram

```
┌───────────────┐     ┌───────────────────┐     ┌────────────────┐
│  Facebook/IG   │────▶│   Scout Module    │────▶│  Script Gen    │
│  Graph API     │     │  (analyzer.py)    │     │  (templates.py)│
└───────────────┘     └───────────────────┘     └───────┬────────┘
                                                         │
                                                         ▼
┌───────────────┐     ┌───────────────────┐     ┌────────────────┐
│  PFM Post      │◀────│   FFmpeg Composer │◀────│  Video Gen     │
│  (7 platforms) │     │  (composer.py)    │     │  (pipeline*)   │
└───────────────┘     └───────────────────┘     └───────┬────────┘
                                                         │
                                                   ┌─────▼──────┐
                                                   │  SAM3 Gate  │
                                                   │ + TTS (gTTS)│
                                                   └────────────┘
```

---

## 🎯 Priority (What to build first)

### DO NOW (Phase 1):
1. [`scout/facebook_scout.py`] Facebook Graph API — search viral posts
2. [`main.py`] 4 endpoints: niches, search, analyze, clone
3. [Frontend] Scout tab + Viral Post Grid
4. Clone → Pipeline integration

### DO NEXT (Phase 2):
5. Facebook→TikTok pattern mapping
6. Auto clone workflow (end-to-end)
7. Multiple clone variants

### DO LATER (Phase 3):
8. Performance Monitor
9. A/B testing
10. Auto-optimization loop

---

## 🔐 Prerequisites

**Facebook Developer App ต้องมี:**
- App ID + App Secret
- Page Access Token (long-lived)
- API scopes: `pages_read_engagement`, `pages_read_user_content`, `instagram_basic`, `instagram_content_publish`
- เก็บใน `.env`: `FACEBOOK_APP_ID`, `FACEBOOK_APP_SECRET`, `FACEBOOK_PAGE_TOKEN`

**PFM (Post For Me):**
- ✅ มีแล้ว — `PFM_API_KEY` ใน `.env`

**Video Generation:**
- ✅ Prodia / Fal.ai keys มีแล้ว

---

## Files ที่ต้องสร้าง/แก้

### ใหม่:
- `scout/facebook_scout.py` — Facebook/IG API integration
- Frontend: Scout tab UI (ใน index.html)

### แก้ไข:
- `main.py` — เพิ่ม routes `/scout/facebook/*`
- `scout/analyzer.py` — รองรับ Facebook pattern analysis
- `pipeline_default.py` — รองรับ cloned script เข้า pipeline auto
