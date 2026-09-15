# SPEECH_SSOT — จุดสั่งให้นางแบบพูด (Voice mode A / Wan 2.7)

> owner (2026-09-15): "คำสั่งพูดมันอยู่อีกไฟล์ ไม่ได้อยู่ใน prompt — เราทำ SSOT ว่าเราจะสั่งให้พูดได้จริงๆ ที่ไหน"
> คำตอบ: **คำสั่งพูดถูกประกอบในโค้ด (video.py) แล้วฝังเข้า final prompt ที่ส่ง Wan จริงทุกครั้ง** — พิสูจน์ได้จาก dump ไฟล์ `wan_prompt_*.txt`

---

## 1. ภาพรวม (1 หน้า)

```
Mimo/DeepSeek เขียน script
        │  (script.py: _deepseek_product_prompts)
        ▼
thai_script (flat, ภาษาไทย)
        │  (script.py: normalize_thai_spoken_script + dur-cap + script_beats)
        ▼
script_beats [hook/value/cta/settle พร้อมวินาที]
        │
        ▼
video.py: generate_video() Voice mode A  ← ★ จุดเดียวที่ประกอบคำสั่งพูด ★
        │  (สร้าง _stop_rule: timeline + «บท» + [SETTLE] )
        │  (+ ต่อ [MOVEMENT] จาก video_prompt = ไว้ขยับ/โชว์สินค้า ห้ามมีคำพูด)
        ▼
final_prompt ──► Prodia Wan 2.7 (img2vid)
        │
        └─ dump บันทึกไว้ที่ modules/video/storage/tmp/wan_prompt_<hash8>.txt
           (พิสูจน์ได้เสมอว่า "Wan เห็นคำสั่งอะไร" — owner debug 2026-09-12)
```

## 2. จุดสั่งพูดจริง = `video.py` (ไฟล์เดียว)

| ชิ้น | ไฟล์:บรรทัด | เนื้อหา |
|---|---|---|
| **สุดท้ายที่ Wan อ่าน** | `pipeline/video.py` `final_prompt` | `_stop_rule` + `[MOVEMENT]` |
| **คำสั่งพูด** (`_stop_rule`) | `video.py` (~L283-322) | "พูดตาม Thai script นี้เท่านั้น ตามลำดับเวลา..." + timeline `«...»` + `[SETTLE]` |
| **เงื่อนไขเปิด** | `video.py` `thai_voice_mode` | `bool(thai_script and use_tus_voice)` — Voice mode A |
| **SETTLE (ห้ามพูดต่อ)** | `video.py` (~L307) | `[SETTLE Ns]: เงียบสนิท ไม่พูด ไม่มีเสียง — ขยับร่างกายได้ตามปกติ` (2026-09-15 ตัด "นำเสนอสินค้า" ออก) |
| **ปิดจบ** | `video.py` (~L315) | "อ่านครบทุกคำจนจบช่วงสุดท้าย แล้วปิดปาก เงียบสนิท" |

**กติกา (owner สั่ง, กัน Wan มั่ว):**
1. 🔴 ใส่บทไทยใน `«»` เท่านั้น อย่าใส่บทไว้นอก `«»` (Wan อ่านนอก `«»` เป็นคำสั่ง + ปนภาษา → เพี้ยน)
2. 🔴 อย่าเพิ่มคำสั่งพูดซ้ำใน `[MOVEMENT]` — motion block ถูกกรองคำพูดออกอัตโนมัติ (regex strip speech ใน video.py) ถ้าอยากให้ motion มีคำพูด → ถูกตัดทิ้ง
3. 🔴 อย่าสั่ง "พูดช้า ๆ/ยืด/ยาวเต็ม N วิ" — ทำให้ Wan ยืดคำมั่ว (fix 2026-09-06)
4. 🔴 อย่าเขียนบทซ้ำ 2 ที่ — flat thai_script = source of truth → beats สังเคราะห์จาก flat เสมอ (2026-09-12)

## 3. ต้นทางข้อมูล (ไม่ใช่คำสั่งพูด แต่เป็น "บท")

| ชิ้น | ไฟล์ | หมายเหตุ |
|---|---|---|
| thai_script | `script.py` (`_deepseek_product_prompts` ผ่าน Mimo) | ถูก normalize + dur-cap (150-200ch) |
| script_beats | `script.py` `_synthesize_script_beats` | สังเคราะห์จาก flat เสมอ (กัน drift) |
| video_prompt (motion) | `prompts.py` / prompt-builder | **ห้าม**มีคำสั่งพูด — โดน strip ทิ้งถ้ามี |

## 4. จะแก้ "คำสั่งพูด" ต้องแก้อะไร

- **อยากเปลี่ยนถ้อยคำสั่งพูด** (เช่น เพิ่ม/ลดความเข้ม) → แก้ที่ `video.py` `_stop_rule` (ส่วนเดียว)
- **อยากเปลี่ยนบท** → แก้ที่ `script.py` / prompt ที่ส่งให้ Mimo (หรือ thai_script ที่ client ส่ง)
- **อยากเปลี่ยนจังหวะ (beat วินาที)** → `script.py` `_synthesize_script_beats`
- **พิสูจน์ว่า Wan เห็นอะไร** → เปิด `storage/tmp/wan_prompt_<hash8>.txt` ของ job นั้น

## 5. ประวัติแก้พูด (สั้น)

- 2026-08-24: Gemini TTS ถอดออกจาก TUS → Wan พูดเอง (Voice mode A)
- 2026-08-29: ใส่ thai_script ตรง ๆ ใน prompt เป็นภาษาไทยล้วน
- 2026-09-06: ลบคำสั่ง "ยืด/ยาวเต็ม N วิ" (ต้นตอพูดมั่ว)
- 2026-09-10~11: timeline beats + [SETTLE] + «» + "ปิดปากเงียบ" (กันพูดต่อท้าย)
- 2026-09-12: flat script = SSOT ของบท; ลบคำสั่งซ้อน/คำสั่งพูดใน motion
- **2026-09-15**: SETTLE ตัด "นำเสนอสินค้า/ยิ้มให้กล้อง" (Wan แปลว่าให้พูดต่อ) → "เงียบสนิท ไม่พูด ไม่มีเสียง — ขยับร่างกายได้ตามปกติ" (commit 697aa449)