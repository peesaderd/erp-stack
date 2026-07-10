# TikTok UGC Pipeline Structure (v6)

**สถานะ:** Active Development  
**อัปเดตล่าสุด:** 2026-07-08  
**Refactor จาก:** 4,800 lines → 600+ lines  

---

## 🎯 เป้าหมาย

สร้างคลิป TikTok review อัตโนมัติจากข้อมูลสินค้า  
**Flow:** Product → Analyze → Script → Image → Video → Final

---

## 📊 Data Flow (9 Steps)

```
Step 1: Product → Analyze (Mistral) → product_profile
Step 2: Load Recipe → scenes structure
Step 3: product_profile + recipe → Script (modules/video/script_gen.py)
Step 4: product_profile + recipe → Image Prompt (prompt-builder-service)
Step 5: image_prompt + product_image → Generate Image (Prodia)
Step 6: product_profile + recipe + image → Video Prompts (prompt-builder-service)
Step 7: script → TTS (Gemini)
Step 8: image + video_prompts → Wan 2.7 → Video
Step 9: Video + Voice + BGM → FFmpeg → Final
```

---

## 🔧 Components & Responsibilities

### 1. **Analyze Layer** (Mistral)
```
File: prompt-builder-service/prompt_builder.py
Function: analyze_product()
Input: product_name, description, product_image
Output: product_profile (dict)
  - category: "beauty/fashion/electronics/..."
  - target_gender: "male/female/unisex"
  - target_age: "18-30"
  - target_audience: "สาววัยทำงานที่มีปัญหาตาคล้ำ"
  - customer_problem: "ปัญหาที่สินค้านี้แก้"
  - main_benefit: "ประโยชน์หลัก"
  - hashtags: [...]
  - setting: "สถานที่ถ่ายวิดีโอ"
```

### 2. **Recipe Layer**
```
File: prompt-builder-service/recipes/{recipe_name}.json
Recipes:
  - tus.json (8s, 6 scenes)
  - etsy.json (16s, 3 scenes)

Structure:
{
  "name": "tus",
  "total_duration": 8,
  "scenes": [
    {
      "name": "Hook",
      "duration_range": [0.5, 1.0],
      "prompt": "...",
      "visual_focus": "..."
    },
    ...
  ]
}
```

### 3. **Script Layer** (Gemini)
```
File: modules/video/script_gen.py
Function: generate_tiktok_review_script()
Input: product_name, customer_problem, main_benefit, target_audience, recipe
Output: {
  "script": "สคริปต์เต็ม",
  "hook": "...",
  "cta": "...",
  "uses_llm": true/false
}
```

### 4. **Image Prompt Layer** (Mistral)
```
File: prompt-builder-service/prompt_builder.py
Function: build_image_prompt()
Input: product_profile, product_name, ugc_style
Output: image_prompt, negative_prompt

Uses:
  - STYLE_MAP (holding, usage, review, talking)
  - LIGHTING_MAP (beauty, tools, electronics, ...)
  - UGC_prompts/{style}/templates
```

### 5. **Image Generation** (Prodia)
```
File: modules/video/pipeline_affiliate.py
Function: generate_image()
API: http://localhost:8110/api/v1/image/generate
Model: Nano Banana Img2Img
Input: image_prompt, product_image (reference)
Output: image_url → download → image_path
```

### 6. **Video Prompt Layer** (Mistral)
```
File: prompt-builder-service/prompt_builder.py
Function: build_video_prompts_from_recipe() [ต้องเพิ่ม]
Input: product_profile, recipe, generated_image_path
Output: video_prompts (list) — 1 prompt per scene

Note: ต้องสร้าง function ใหม่ — ปัจจุบันไม่มี
```

### 7. **TTS Layer** (Gemini)
```
File: modules/video/gemini_tts.py
Function: gemini_text_to_speech()
Model: gemini-3.1-flash-tts-preview
Input: script text, voice name
Output: audio_path (mp3)
```

### 8. **Video Generation** (Prodia Wan 2.7)
```
File: modules/video/pipeline_affiliate.py
Function: generate_video()
API: https://inference.prodia.com/v2/job
Model: Wan 2.7 img2vid
Input: image_path, video_prompt, duration
Output: video_path (mp4, silent)
```

### 9. **Compose Layer** (FFmpeg)
```
File: modules/video/pipeline_affiliate.py
Functions:
  - merge_voice_video()
  - concat_videos()
  - add_bgm()
Input: video_paths, voice_path, bgm_path
Output: final_path (mp4)
```

---

## 📁 File Structure

```
erp-stack/
├── prompt-builder-service/
│   ├── app.py                          # API endpoints (port 8117)
│   ├── prompt_builder.py               # Analyze + Image/Video Prompts
│   ├── recipe_system.py                # Recipe loader
│   ├── recipes/
│   │   ├── tus.json                    # 8s recipe
│   │   └── etsy.json                   # 16s recipe
│   └── UGC_prompts/                    # Templates
│       ├── Holding_Product/
│       ├── Product_Usage/
│       └── UGC_Review/
│
├── modules/video/
│   ├── main.py                         # API endpoints (port 8112)
│   ├── pipeline_affiliate.py           # Main pipeline orchestrator
│   ├── pipeline_logger.py              # Job tracking
│   ├── script_gen.py                   # Script generation (Gemini)
│   ├── gemini_tts.py                   # TTS (Gemini)
│   ├── composer.py                     # FFmpeg merge
│   ├── prompts/                        # Script templates
│   │   ├── system.prompt.txt
│   │   ├── master.prompt.txt
│   │   └── user.template.prompt.txt
│   └── storage/
│       └── tmp/                        # Temp files
│
├── shared_config.py                    # Centralized API keys
└── PIPELINE_STRUCTURE.md               # ← ไฟล์นี้
```

---

## 🔑 API Endpoints

### Prompt Builder Service (port 8117)
```
GET  /health
POST /api/v1/build
  Input: BuildRequest (product_name, description, ugc_style, product_image)
  Output: { analysis, image_prompt, video_prompt, negative_prompt }
```

### Video Module (port 8112)
```
GET  /health
POST /api/v1/scripts
POST /api/v1/pipeline/run
  Input: FullPipelineRequest (product_name, product_image, recipe_name, ...)
  Output: { final_path, cost_estimate, job_id }
```

---

## ⚠️ Critical Rules (ห้ามเปลี่ยน)

1. **Analyze ก่อน Script** — ต้องมี product_profile ก่อนสร้าง script
2. **Image ก่อน Video Prompts** — video prompts ต้องอ้างอิง image ที่สร้างแล้ว
3. **Recipe กำหนด structure** — scene_prompts มาจาก recipe ไม่ใช่ manual
4. **Script gen ใช้ Gemini** — ไม่ใช้ Mistral (Mistral ใช้สำหรับ analyze + prompts)
5. **Image gen ใช้ Nano Banana** — img2img จาก product_image (reference)
6. **Video gen ใช้ Wan 2.7** — img2vid จาก image_path
7. **TTS ใช้ Gemini** — ไม่ใช่ Fal.ai
8. **API keys ผ่าน shared_config.py** — ห้าม hardcode

---

## 🐛 Known Issues (ที่กำลังแก้)

1. ❌ `pipeline_affiliate.py` เรียก endpoint ที่ถูกลบไปแล้ว
   - `/api/v1/generate-script-after-image`
   - `/api/v1/generate-video-prompts-after-image`
   - **แก้:** เพิ่ม function ใน prompt_builder.py แทนการเรียก API

2. ❌ Recipe ไม่ได้ถูก load จริง
   - recipe_name เก็บใน logger แต่ไม่ได้ใช้ scenes
   - **แก้:** เพิ่ม `load_recipe()` ใน pipeline

3. ❌ Video prompts ไม่มี image context
   - ส่ง scene_prompts ตรงๆ ไม่ reference image
   - **แก้:** เพิ่ม `build_video_prompts_from_recipe()`

4. ❌ Script gen ไม่ได้ integrate
   - ต้องเรียก `generate_tiktok_review_script()` ก่อน image
   - **แก้:** เพิ่มใน pipeline flow

---

## 🚀 Next Steps

- [ ] แก้ `pipeline_affiliate.py` ให้ flow ถูกต้อง (9 steps)
- [ ] เพิ่ม `build_video_prompts_from_recipe()` ใน prompt_builder.py
- [ ] เพิ่ม recipe loading ใน pipeline
- [ ] ทดสอบ end-to-end
- [ ] (Phase 2) Autonomous decisions — AI เลือก recipe/style เอง

---

## 📞 Contact

ถ้ามีคำถาม หรืออยากเปลี่ยน structure → คุยกับเจ้าของ project ก่อน  
**ห้ามเปลี่ยน flow โดยไม่อัปเดตไฟล์นี้**
