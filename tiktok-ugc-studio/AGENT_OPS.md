# TikTok UGC Studio (TUS) — Agent Operations Manual

> **⚠️ อ่านก่อนทำงานทุกครั้ง** — ระบบนี้มีประวัติเสียเวลาเพราะ Agent ไม่เข้าใจระบบ

---

## 1. ระบบนี้คืออะไร

TikTok UGC Studio = Web UI (Content Wizard) + API Backend + Pipeline สำหรับสร้างวิดีโอ UGC Affiliate อัตโนมัติ
- Frontend: https://openhands.m2igen.com/tiktok/
- API: tiktok-ugc-studio (port 8105)
- Image Gen: image-gen (port 8110)

## 2. Pipeline Flow (Pipeline v4.6)

```
SAM3x2 ($0.0022) → Klein 9B ($0.005) → MiniMax 2.8 HD ($0.054) → Wan 2.7 ($0.03) → FFmpeg Voice Merge + BGM ($0)
                                                                                             ↑ bgm_fetcher auto-downloads
```

**Cost: ~$0.09/clip** (8s, 1 scene)

**Files:**
- `pipeline_affiliate.py` — Main pipeline logic
- `main.py` — FastAPI backend (endpoints)
- `bgm_fetcher.py` — Auto-download BGM from Mixkit CDN
- `image_prompt_builder.py` — Dynamic image prompt builder (มีอยู่แล้ว!)
- `script_gen.py` — AI script generator (มีอยู่แล้ว!)
- `bgm/` — BGM files (git tracked, ไม่หาย)

## 3. 🔴 RED LINES — ห้ามทำเด็ดขาด!

| # | กฎ | เพราะ |
|---|---|---|
| 1 | **ห้าม hardcode image prompt** | ระบบมี `image_prompt_builder.py` ที่สร้าง prompt dynamic ตามสินค้าอยู่แล้ว — ใช้ `scene_prompts` จาก Web UI แทน |
| 2 | **ห้าม bypass Web UI** | ห้ามส่ง curl/API โดยตรง — ทดสอบผ่าน Web UI เท่านั้น |
| 3 | **ห้าม fabricate features** | ถ้าไม่แน่ใจว่า feature มีจริง → เช็ค code ก่อน, ไม่ใช่เดา |
| 4 | **ห้าม test/generate โดยไม่ถาม** | ถาม owner ก่อนทุกครั้งก่อนกด Generate |
| 5 | **ห้ามส่ง output โดยไม่เช็ค** | ต้อง inspect output ก่อนส่งให้ user ดู |
| 6 | **ห้ามเปลี่ยน TTS voice โดยไม่ verify** | เช็คให้ชัวร์ว่า voice ID มีจริง |
| 7 | **ห้ามเสียตังค์โดยไม่จำเป็น** | ใช้ฟรีก่อน (Mixkit, Pixabay) — Fal.ai gen มีค่าใช้จ่าย |
| 8 | **ห้ามแก้ของที่มีอยู่แล้วโดยไม่เข้าใจ** | ก่อนแก้ ต้องรู้ว่าระบบมีอะไรอยู่แล้ว (เช่น image_prompt_builder) |

## 4. 🔧 ระบบที่มีอยู่แล้ว (ห้ามเขียนใหม่!)

### Image Prompt Builder (`image_prompt_builder.py`)
✅ วิเคราะห์สินค้า → category → gender → age → setting → lighting → camera → mood
✅ Dynamic prompt ตามประเภทสินค้า
✅ หลาย UGC style: holding / usage / review / talking
**ใช้ endpoint:** `POST /images/build-prompt` หรือ `from image_prompt_builder import build_prompt`

### Script Generator (`script_gen.py`)
✅ ใช้ LLM (ถ้ามี key) หรือ fallback เป็น template
✅ Generate hook, body, cta, scene, voice
**ใช้ endpoint:** `POST /scripts/generate`

### BGM Fetcher (`bgm_fetcher.py`)
✅ Auto-download จาก Mixkit CDN ถ้าไม่มีไฟล์
✅ 6-8 tracks ต่อ style (random ทุกรอบ)
✅ Git tracked — deploy ใหม่ไม่หาย
**ใช้:** `from bgm_fetcher import fetch_bgm`

### SAM3 Analyzer
✅ วิเคราะห์ภาพสินค้า → object detection + safe zones + prompt insights
✅ ใช้ทั้งกับ product image และ generated UGC image
**เปิด/ปิด:** `enable_sam3=True` ใน `affiliate_run()`

## 5. 🎵 BGM System

**Source:** Mixkit Free Stock Music (assets.mixkit.co)
**Files:** `tiktok-ugc-studio/bgm/*.mp3` (git tracked)
**Volume:** 0.50 (ปรับตอน pipeline เรียก FFmpeg amix)

**Track IDs ต่อ Style:**
```
chill_loft:     494, 16, 25, 256, 1077, 510
jazz:           493, 39, 24, 752, 644, 89
edm:            371, 113, 124, 181, 157, 629
upbeat_pop:     644, 528, 652, 820
asmr:           16, 494, 510, 1077
```

**เพิ่ม track ID:** เปิด Mixkit → คัดลอก ID จาก URL → ใส่ใน `bgm_fetcher.py`

## 6. 🎤 TTS (Text-to-Speech)

| Provider | Voice | Cost | Status |
|---|---|---|---|
| MiniMax 2.8 HD | lovely_girl + language_boost=Thai | ~$0.054/คลิป | ✅ ปัจจุบันใช้ |
| ~~Edge TTS~~ | ~~th-TH-PremwadeeNeural~~ | ~~$0~~ | ❌ Reverted (user ไม่เอา) |
| ~~MiniMax 2.8 HD~~ | ~~thai_female~~ | ~~$0.10~~ | ❌ voice ID ไม่มีจริง |

## 7. 💰 Cost Breakdown

| Component | Cost | Provider |
|---|---|---|
| SAM3 (product image) | $0.0011 | Prodia |
| SAM3 (UGC image) | $0.0011 | Prodia |
| Klein 9B (img2img) | $0.005 | Prodia |
| MiniMax 2.8 HD (voice) | ~$0.0542 | Fal.ai |
| Wan 2.7 (video 8s) | $0.03 | Fal.ai |
| BGM | $0 | Mixkit (ฟรี) |
| **Total** | **~$0.09** | |

## 8. 🧪 วิธี Test

1. เปิด Web UI: https://openhands.m2igen.com/tiktok/
2. ไป Products → คลิก "🎬 Create Video" บนสินค้าที่ต้องการ
3. Content Wizard จะเปิด:
   - Step 2: Generate Script → ปรับ hook/value/cta
   - Step 3: Summary → ดู scene prompt, sound style
   - Step 4: 🚀 Generate Video
4. รอ pipeline ทำงาน (~1-2 นาที)
5. เช็ค output: ลิงก์ URL จะขึ้นใน UI

**ก่อนส่งให้ user:** inspect รูป + วิดีโอทุกครั้ง!

## 9. 📜 History

| Commit | v | Change | Cost |
|---|---|---|---|
| `60ffb4c` | 4.2 | Pipeline แรก (Prodia only) | - |
| `055d727` | - | Klein 9B route | - |
| `2801129` | - | Cleanup services | - |
| `a28b567` | - | Disable WaveSpeed/Fal chain | - |
| `8a0b762` | - | MiniMax 2.8 HD | - |
| `1fbc430` | 4.3 | lovely_girl, BGM=0.80 | $0.077 |
| `24b83e2` | 4.4 | Edge TTS Thai | $0.037 |
| `4715bc0` | 4.5 | Revert to MiniMax, lovely_girl | $0.077 |
| `561cda3` | - | BGM volume=3.0 fix | - |
| `faed2c6` | 4.6 | Dynamic prompts, no double BGM | $0.09 |
| `d25f459` | - | Real BGM from Mixkit | - |
| `7b0bb43` | - | BGM to git-tracked bgm/ dir | - |
| `a311ace` | - | bgm_fetcher auto-download | - |

## 10. 🔮 Next Steps (สิ่งที่ต้องทำต่อ)

1. ✅ ~~SAM3x2 integration~~
2. ✅ ~~Klein 9B image~~
3. ✅ ~~MiniMax TTS + revert from Edge~~
4. ✅ ~~BGM real music from Mixkit~~
5. ⬜ Config/template system for pipeline recipes
6. ⬜ Re-evaluate GPT Image 2 + SAM3 inpaint approach (optional)
7. ⬜ Add more BGM track IDs for variety
8. ⬜ Script shortening (บทพูดยาวเกินไป)

---

*Document updated: 2026-06-16*
*Read this before ANY modification to the pipeline*
