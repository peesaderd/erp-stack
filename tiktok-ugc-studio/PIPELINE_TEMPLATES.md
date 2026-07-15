# Pipeline Templates — Recipe × UGC Style System

> **TL;DR**: Recipe บอก mood/BGM/duration, UGC Style บอกวิธี generate  
> `build_pipeline_config(recipe, ugc_style, product)` → พร้อมยิง Wan 2.7

---

## Concept

```
Recipe (skincare, gadget, ...)  ×  UGC Style (holding, talking, ...)
              ↓                                  ↓
         mood, bgm,                    generation method,
         duration, vibe                audio y/n, prompt template
              └──────────┬──────────┘
                         ↓
              build_pipeline_config()
                         ↓
                   PipelineConfig
                         ↓
                   Wan 2.7 API
```

---

## 4 Pipeline Templates

| Template | Audio | Image | ใช้เมื่อ |
|----------|-------|-------|---------|
| 🎤 **talking_head** | ✅ TTS lip-sync | คน + สินค้า | ต้องการพูดหน้ากล้อง sync ปาก |
| 🤳 **holding_product** | ❌ | สินค้า | ถือสินค้าโชว์ |
| 📱 **product_usage** | ❌ | สินค้าใช้จริง | สาธิตวิธีใช้ |
| ⭐ **ugc_review** | ❌ | คน + สินค้า | รีวิว authentic |

---

## Usage

```python
from pipelines import build_pipeline_config

config = build_pipeline_config(
    recipe={"name": "skincare", "mood": "calm", "bgm_style": "luxury_jazz", "duration": 10},
    ugc_style="talking_head",
    product={"title": "Vitamin C Serum", "description": "..."},
)

# config พร้อมใช้:
config.job_type        # "wan2-7.img2vid.v1"
config.needs_audio     # True/False
config.prompts.hook    # full prompt text with variations
config.prompts.value
config.prompts.cta
config.cta             # selected CTA text
config.duration        # 8, 10, or 15
config.variations_used # {lighting, angle, model, ...}
```

---

## File Structure

```
pipelines/
├── __init__.py
├── runner.py                    # build_pipeline_config() + variation/CTA engine
├── cta_pool.yaml               # CTA templates per mood
└── templates/
    ├── talking_head.yaml       # 🎤 Wan 2.7 + audio lip-sync
    ├── holding_product.yaml    # 🤳 Product showcase
    ├── product_usage.yaml      # 📱 Demo/usage
    └── ugc_review.yaml         # ⭐ Authentic review
```

---

## Adding a New Template

1. Create `pipelines/templates/your_style.yaml` with:
   - `generation` block (job_type, needs_audio, image_requirement)
   - `scene_prompts` (hook, value, cta — use `{product}` and `{variation}` placeholders)
   - `variations` (lighting, angle, color_palette, model, background)
   - `video_params` (duration, resolution, ratio)
   - `cta_strategy` (which mood pools to use)

2. Add CTA templates to `cta_pool.yaml` if needed

3. Done — `list_templates()` auto-discovers all YAML files

---

## Variation Engine

ทุกครั้งที่ generate → สุ่ม 1 ตัวเลือกจากแต่ละหมวด:

```yaml
variations:
  lighting: [soft natural, ring light, golden hour, ...]
  angle: [eye-level, close-up, 45°, ...]
  model: [Thai woman casual, young creator, ...]
  color_palette: [warm beige, pastel, clean white, ...]
  background: [minimalist room, cozy home, ...]
```

ทำให้คลิปไม่ซ้ำกัน — ทุก run ได้ prompt ต่างกัน

---

## Integration with main.py

```python
# main.py — ใช้ pipeline template system
from pipelines import build_pipeline_config

@app.post("/pipeline/run")
async def run_pipeline(req: PipelineRequest):
    # Build config from recipe + UGC style
    recipe = get_recipe(req.recipe)
    config = build_pipeline_config(recipe, req.ugc_style, req.product)
    
    # Generate TTS (เฉพาะ talking_head)
    if config.needs_audio:
        tts = await _proxy("POST", "video", "/api/v1/tts/generate", ...)
    
    # Generate image
    image = await _proxy("POST", "image-gen", "/api/v1/generate", ...)
    
    # Generate video (ส่ง config ไปให้ video module)
    video = await _proxy("POST", "video", "/api/v1/video/generate", {
        "config": config.to_dict(),
        "image": image,
        "audio": tts if config.needs_audio else None,
    })
    
    return video
```
