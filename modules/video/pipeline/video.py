"""Video generation via Wan 2.7 (Phase C split, move-only)."""
from ._shared import (  # noqa: F401
    os, re, sys, json, time, uuid, logging, random, subprocess, shutil, asyncio,
    Path, Optional, List, Dict, Any, requests,
    PRODIA_TOKEN, GEMINI_API_KEY, logger,
    IMAGE_GEN_URL, PROMPT_BUILDER_URL, STORAGE_DIR, TMP_DIR,
    get_default_style, get_style_config, validate_ugc_style, is_valid_style,
)

# ── Shared Prodia v2 Async Client ──
from prodia_client import ProdiaV2Client, ProdiaV2Error, ProdiaValidationError

def has_audio_track(video_path: str) -> bool:
    """Check if video contains an audio stream using ffprobe.
    Returns False on any error.
    """
    try:
        cmd = [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "a",
            "-show_entries",
            "stream=codec_type",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            video_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        return bool(result.stdout.strip())
    except Exception as e:
        logger.warning(f"Failed to probe audio track for {video_path}: {e}")
        return False

def _generate_fallback_video_from_image(image_path: str, duration: int = 15) -> str:
    """Generate a high-quality 1080x1920 video with smooth zoompan from a still image via FFmpeg."""
    fallback_path = TMP_DIR / f"img2vid_fallback_{uuid.uuid4().hex[:8]}.mp4"
    logger.info(f"Generating FFmpeg video fallback from image: {image_path}")
    
    local_img = image_path
    if str(image_path).startswith("http://") or str(image_path).startswith("https://"):
        local_img = TMP_DIR / f"temp_img_{uuid.uuid4().hex[:8]}.png"
        r = requests.get(image_path, timeout=30)
        with open(local_img, "wb") as f:
            f.write(r.content)
            
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1",
        "-i", str(local_img),
        "-c:v", "libx264",
        "-t", str(duration),
        "-pix_fmt", "yuv420p",
        "-vf", f"scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,zoompan=z='min(zoom+0.0015,1.2)':d={duration*25}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1080x1920",
        "-r", "25",
        str(fallback_path)
    ]
    subprocess.run(cmd, check=True, capture_output=True, timeout=60)
    logger.info(f"FFmpeg Video Fallback Created OK -> {fallback_path}")
    return str(fallback_path)

def generate_video(
    image_path: str,
    prompt: str,
    duration: int = 8,
    resolution: str = "720P",
    negative_prompt: Optional[str] = None,
    reference_image: Optional[str] = None,
    first_frame: Optional[str] = None,
    last_frame: Optional[str] = None,
    thai_script: Optional[str] = None,
    use_tus_voice: bool = True,
    prompt_extend: bool = False,
    ugc_style: str = "holding",
    script_beats: Optional[list] = None,
) -> tuple:
    """
    Step 8: Generate video via Wan 2.7 Async API (shared ProdiaV2Client)
    """
    logger.info(f"Step 8/9: Generate video (Wan 2.7, {resolution})")
    logger.info(f"  Prompt: {prompt[:80]}...")

    # First frame หลัก: ใช้ first_frame (ถ้าระบุ) แทน image_path
    main_img = first_frame or image_path
    if not main_img:
        raise RuntimeError("generate_video: ต้องมี image_path หรือ first_frame")
    if first_frame:
        logger.info(f"  ▶ first_frame: {first_frame}")

    # Helper อ่าน bytes จาก path หรือ URL
    def _read_bytes(src: Optional[str]) -> Optional[bytes]:
        if not src:
            return None
        try:
            if src.startswith("http://") or src.startswith("https://"):
                r = requests.get(src, timeout=30)
                r.raise_for_status()
                return r.content
            with open(src, "rb") as f:
                return f.read()
        except Exception as e:
            logger.warning(f"  อ่านภาพผิดพลาด ({src}): {e}")
            return None

    # Read first frame bytes
    image_data = _read_bytes(main_img)
    if not image_data:
        raise RuntimeError(f"generate_video: อ่าน first frame ไม่ได้: {main_img}")

    # FL2V SINGLE image (owner 2026-08-26): ไม่มี last_frame/reference
    # Wan 2.7 สร้างจาก input_image (first frame) รูปเดียวเท่านั้น

    # ── Voice mode A ONLY (owner 2026-08-24: Gemini TTS removed from TUS) ──
    # Wan 2.7 speaks thai_script directly. No lip-sync audio is ever sent.
    thai_voice_mode = bool(thai_script and use_tus_voice)

    audio_bytes = None
    if thai_voice_mode:
        logger.info("  🎙 Voice mode A: thai_script ให้ Wan พูดเอง (Gemini TTS ถูกถอดออกจาก TUS แล้ว)")

        # 🔴 REMOVED padding tail (commit 8de880b0 ถูก revert 2026-08-26 00:42).
        # เหตุผล: padding ทำให้ "จุดจบ" ของ script หายไป ซึ่่ prompt "พูดจบแล้วหยุดพูดทันที"
        # หยุดไม่ได้ เพราะ Wan ไม่รู้ว่าจบตรวงไหน ซึ่่ พูดต่อจนจบ 15s แล้วมั่วเพิ่มปลาย
        # แก้: ส่ง script ตามจริงของพี่ + prompt สั่งหยุดเมื่อพูดจบ + negative ห้ามพูดนอก script

    # ── Thai script (Thai-voice mode): ฝังบทพูดไทยใน prompt เพื่อให้ Wan ขยับปาก
    # ตรงตามเสียง Thai voiceover จริง (ไม่ใช่เดาเสียงจาก audio อย่างเดียว)
    # thai_script = บทภาษาไทย; มีเมื่อ client เปิดโหมดให้ Wan พูดเองตามบท
    final_prompt = prompt
    if thai_voice_mode:
        # 🔴 RULE (owner อธิบายครั้งที่ 3, 2026-08-25): Wan 2.7 พูด Thai script
        # ได้ดีและชัดที่สุด เมื่อคำสั่งพูดใน prompt เป็นภาษาไทยทั้งหมด
        # 🔴 FIX (owner 2026-08-29): owner ยืนยันชัด "ใส่ script เข้าไปเลย" —
        # อย่าเอา video_prompt (ภาษาอังกฤษ สัญญา Thai lines + Scene ฉาก + never moving camera)
        # มาเรียงไว้หน้บทไทย เพราะทำให้ prompt ภาษาแปนขัดแย้งตัวมันเอง Wan งง
        # แล้วพูดออกมาช่วงแรกได้ หลัง ๆ เพี้ยน ต้องใส่บทไทยลงไปตรง ๆ เป็นภาษาไทยล้วน
        # ใน prompt เดียว ไม่ปนสองภาษา (Wan รับ ~2500 คำ ไม่เกินแน่นอน)
        # รูปทั้งหมดบรรยายเป็นภาษาไทยล้วน ประกอบบทเดียว
        # 🔴 FIX (owner 2026-09-06 12:0x): owner เจอต้นตอ "พูดเพี้ยน/มั่ว" = คำสั่ง
        # "พูดช้า ๆ ยืดจังหวะทุกประโยค / ให้เสียงพูดยาวเต็ม N วินาที / ห้ามพูดจบเร็ว"
        # (เพิ่ม commit 7c1a04c8 29-08) ทำให้ Wan ยืดคำ/เดิมแต่งเนื้อมั่ว ให้ยาวจนครบเวลา
        # เมื่อ script สั้น → เอาคำสั่งยืดเวลา/ยาวเต็ม N วิออกทั้งหมด ให้พูดตาม script เท่านั้น
        # ชัดเจน คำต่อคำ ไม่เดิมแต่ง เมื่อจบ script ให้หยุดยิ้มนิ่ง ไม่พูดต่อ (พี่สั่ง 11:57)
        # 🔴 FIX (owner 2026-09-09 03:35): ลบท่อน "ยิ้มนิ่ง/ไม่ขยับ/กล้องนิ่ง" ออก
        # ตามพี่สั่ง (ตอนนี้ prompt_extend=False แล้ว Wan ไม่เสริมการเคลื่อนไหวเอง)
        # → ท่อนนี้ทำให้ภาพแทบขยับ (ที่พี่เจอ = นิ่งแค่ยิ้ม) เพราะสั่ง freeze ทั้งตัว+กล้อง
        # เหลือแค่คำสั่งพูดไทยล้วน: ออกเสียงชัด พูดจบแล้วหยุด ห้ามแต่งประโยค.
        # (บังคับท่าทาง/โชว์สินค้า ว่ารอ step ใหม่ที่แทรก motion เป็นไทยล้วนทีหลัง)
        # 🔴 FIX (owner 2026-09-09 12:5x): Wan พูดจบ script แล้วยังพึมำ/พูดต่ออีก ~5 วิ (RAW audio ยืนยัน
        # เสียงดัง 64-70dB ถึง 14.4 วิ ทั้งที่บท ~9 วิ) เพราะ Wan เป็น video model สั่งให้สร้าง 15 วิของคนพูด
        # แล้วมีเวลาว่าง → แต่งเสียงปิดช่องว่าง แม้ prompt_extend=False ก็ไม่หยุดเสียง
        # พี่สั่ง: ใส่คำสั่ง "พูดจบแล้วไม่ต้องพูดต่อ" เข้าไปใน prompt ให้ชัดเจน (enclose) แล้วลองใหม่
        # เทคนิค: (1) กันขอบเขตบทด้วยเครื่องหมาย "«»" ให้ Wan เห็นชัดว่าบทจบตรงไหน (2) เน้นว่าหยุดได้/เงียบได้
        # ไม่ต้องพูดให้เต็มความยาววิดีโอ (กันมัน "อยากทำให้เต็มเวลา") (3) ตอกย้ำจบ = ปิดปาก พยุดเสียง
        # ไม่เพิ่มคำ/เสียง/ต่อบท (4) ห้ามใส่ "ยิ้มนิ่ง/ไม่ขยับ/กล้องนิ่ง" (พี่ 09-09 03:35 เอาออกเพราะทำภาพนิ่งเกิน)
        # 🔴 FIX (owner 2026-09-10 03:5x): "prompt ขยับแต่คลิปนิ่ง" — ต้นตอ = ท่อนนี้เดิม **ทับ**
        # video_prompt (action 688ch) ด้วยคำสั่งพูดไทยล้วน ⇒ Wan ไม่มี motion direction เลย → นิ่ง
        # แก้: คงบทพูดไทยเป็นหลัก (กันพูดเพี้ยน) แต่ **ต่อ motion/action กลับเข้าไป** ให้ Wan รู้ว่าต้องขยับอะไร
        #   - toggle ได้ด้วย env WAN_VOICE_MOTION (default เปิด) เผื่อ owner อยากเทียบก่อน/หลัง
        # 🔴 FIX#2 (owner 2026-09-10 05:38): "พูดเพี้ยนปลาย" — motion block เดิมวาง **ก่อน** บท
        #   + เป็นอังกฤษยาว 606ch แทรกกลาง ทำให้ Wan อ่าน EN ปน TH แล้วจังหวะท้ายเพี้ยน
        #   แก้: (1) **ย้าย motion block ไปไว้ "หลัง" บทพูด** — ให้ Wan อ่านบทไทยจบก่อน แล้วค่อยเจอ
        #        action (บทพูดนำหน้า = จังหวะพูดนิ่งขึ้น) (2) ห่อ motion เป็นคำสั่งไทยสั้น + คง action
        #        อังกฤษไว้ (เป็น directive ของ action ไม่ใช่บทพูด → Wan แยกได้ว่าห้ามอ่านท่อนนี้)
        import os as _os
        _motion_on = _os.getenv("WAN_VOICE_MOTION", "1").strip().lower() not in ("0", "false", "no", "off")
        _motion_txt = (prompt or "").strip()
        # 🔴 FIX#3 (owner 2026-09-10 05:52): "ยังเพี้ยนปลาย + อย่ามี hard-code"
        #   ต้นตอ: final_prompt เดิมยัดคำสั่งพร่ำเพรื่อ ~800ch (persona + forbid ซ้ำ ๆ + "เงียบสนิท")
        #   → Wan ปนคำสั่งพวกนี้เข้าไปกับบทพูด = ท้ายเพี้ยน
        #   แก้: ใช้คำสั่งสั้น ชัด "พูดตาม script นี้เท่านั้น" — เนื้อบทพูดเป็น DATA (thai_script) ล้วน
        #   ไม่มี hard-code ข้อความ script ใด ๆ ในนี้; motion ก็เป็น DATA (prompt) เช่นกัน
        # 🔴 FIX (owner 2026-09-10 10:44): "ท้ายคลิปมีเสียงหลุด" — Wan พูด script จบ (~10.9s)
        # แล้วยัง "พูดต่อ/พึมพำ" ในเวลาที่เหลือจนถึง 15s (วัดจริง: 11.3-12.4s และ 13.1-15s
        # ยังมีเสียงพูดดัง -7.8dB) เพราะ prompt ไม่เคยสั่ง "พูดจบแล้วหยุดพูด" เลย (ท่อนนั้นถอดออก
        # หลายรอบก่อนหน้าแต่ไม่เคยใส่กลับเป็นคำสั่งบวก) → ใส่ STOP RULE ชัดเจนเป็นภาษาไทย
        # 🔴 FIX#2 (owner 2026-09-10 11:39): "มีแทรกหลังคำว่า เชื่อมเร็ว" — Wan ใส่คำ/เสียง
        # แทรกกลางบท ตรงรอยต่อระหว่างวลี (หลัง 'เชื่อมเร็ว' ก่อนวลีสุดท้าย) เพราะมันเติมเสียง
        # ในช่องว่างระหว่างวลี → สั่งเพิ่ม: อ่านทุกวลีตามจริง ห้ามเติมคำ/เสียงคั่นระหว่างวลี
        # 555 เว้นจังหวะได้แค่หายใจสั้น ๆ; ห้ามพูดคำที่ไม่ปรากฏใน «» รวมทั้งกลางบท
        # 🔴 owner 2026-09-11 00:01: "สั่งให้มันพูดตาม script เท่านั้น ใส่ใน positive prompt"
        # owner rule: เลี่ยงคำสั่งห้ามซ้อนหลายชั้น — ใช้คำสั่งเชิงบวกที่ชัด วางต้น+ท้ายของบล็อก
        # วลีเดี่ยว "พูดตาม script เท่านั้น" ทั้งขึ้นต้นและลงท้าย เพื่อโฟกัสสูงสุด
        _script_clean = (thai_script or "").strip()
        # owner 2026-09-12 (speech polish belt-and-suspenders): hard-strip ANY non-Thai script from the
        # spoken line - Mimo leaked Chinese ('认证放心') and Latin transliterations before, which the voice
        # reads as garbage. Keep Thai (U+0E00-U+0E7F), spaces, and commas only.
        try:
            import re as _re_th
            _th_only = _re_th.sub(r"[^\u0E00-\u0E7F\s,]+", " ", _script_clean)
            _th_only = _re_th.sub(r"\s+", " ", _th_only).strip(" ,")
            if _th_only and _th_only != _script_clean:
                logger.info(f"  🧹 script sanitized (non-Thai stripped): {_script_clean[:40]}... -> {_th_only[:40]}...")
                _script_clean = _th_only
            elif not _th_only and _script_clean:
                logger.warning("  script sanitizer: all non-Thai -> keeping original")
        except Exception as _e_th:
            logger.warning(f"  script sanitizer skipped: {_e_th}")
        # owner 2026-09-11 07:2x: "ช่วง CTA มีปัญหา ตชอด" — leak ตรงรอยต่อหลัง CTA.
        # CTA เป็นวลีสุดท้ายของบท -> พอ Wan พูดจบ ยังมีเวลาวิดีโอเหลือ ~2-3s ที่ไม่มีบท
        # -> Wan ต่อเสียงมั่วตรงรอยต่อนั้น (vid_62b4ea4c ท้ายได้ 'phai hay pier, bri khiba, oi').
        # FIX A: ใส่เครื่องหมายจบบทให้ Wan เห็นขอบเขตจริงใน «» — เพิ่ม "[จบบท]" ต่อท้ายบท
        # + สั่งย้ำว่าคำสุดท้ายคือคำก่อนเครื่องหมาย ห้ามมีเสียงหลังคำนั้น.
        _last_word_hint = ""
        if _script_clean:
            _flat = _script_clean.replace("\n", " ").strip()
            # Thai has few spaces; a whitespace split gives the whole final clause.
            # Take the trailing ~3 words (or the last ~20 chars) as the end pointer.
            _tail_words = _flat.split()
            if _tail_words and len(_tail_words[-1]) <= 20:
                _last_word_hint = _tail_words[-1]
            else:
                _last_word_hint = _flat[-20:]
        _stop_rule = (
            "พูดตาม Thai script นี้เท่านั้น:\n"
            f"«{_script_clean}»\n"
            "อ่านเฉพาะข้อความใน «» ครบทุกคำตามที่เขียน แล้วปิดปาก เงียบสนิท "
            f"(คำสุดท้ายคือ '{_last_word_hint}')"
        )
        # 🔴 owner 2026-09-11 08:0x (Fix C): STRUCTURED BEATS — send the script as a TIMED timeline
        # instead of one blob. Root cause of the CTA tail leak = a TIME-BUDGET problem: Wan must
        # fill N seconds of audio, so when the flat script ends it improvises a garbled tag into
        # the leftover seconds. Fix: tell Wan each beat's window AND give the last 1-2s an explicit
        # SILENT settle beat (it generates motion, not speech, exactly where it used to babble).
        _beats = script_beats or []
        if _beats:
            _lines = []
            _spoken_secs = 0
            for _b in _beats:
                _lbl = _b.get("label", "")
                _secs = _b.get("seconds", 0)
                _txt = (_b.get("text") or "").strip()
                if _lbl == "settle" or not _txt:
                    _lines.append(f"  - [SETTLE {_secs}s]: เงียบสนิท ไม่มีเสียงพูด — ยังขยับตัว นำเสนอสินค้า และยิ้มให้กล้อง")
                else:
                    _spoken_secs += _secs
                    _lines.append(f"  - [{_lbl} ~{_secs}s]: «{_txt}»")
            _timeline = "\n".join(_lines)
            _stop_rule = (
                "พูดตาม Thai script นี้เท่านั้น ตามลำดับเวลา (timeline) ด้านล่าง:\n"
                f"{_timeline}\n"
                "อ่านเฉพาะข้อความใน «» ตามลำดับ — ห้ามออกเสียงป้ายกำกับ [ ] ใด ๆ\n"
                "อ่านครบทุกคำจนจบช่วงสุดท้าย แล้วปิดปาก เงียบสนิท"
            )
            logger.info(f"  🎙 Fix C beats: {len(_beats)} beats, spoken~{_spoken_secs}s + settle")
        # 🔴 owner 2026-09-11 00:54: Wan พูดแทรกก่อน CTA และหลัง CTA.
        # owner: "ใส่ไปใน video prompt ว่าให้พูดตาม Script" — Wan อ่าน video_prompt เป็นท่อนสุดท้าย
        # จึงต้องมีคำสั่ง speech-lock ปิดท้าย "หลัง" motion block ด้วย (ท่อนสุดท้ายที่ Wan เห็น)
        # owner 2026-09-12 11:3x: Pete - "เราบอกแค่พูด Thai script แหล่ะ ... อย่าไปเน้นซ้ำซ้อน
        # พร่ำเพรื่อ กลายเป็น Wan งง เสียงสั่น + video ละลาย". The speech instruction already lives
        # in _stop_rule; a second full speech-lock tail = duplicated ordering -> Wan gets confused.
        # Keep ONE short English closing directive only: keep silence after the script ends.
        # owner 2026-09-12 14:2x: _speech_tail REMOVED — the silence is already stated once
        # (flat: "ปิดปาก เงียบสนิท"; beats: the [SETTLE] line). A second English "stay silent"
        # was the duplicate "คำสั่งซ้อน" that confused Wan. One speech source only.
        _speech_tail = ""
        final_prompt = _stop_rule + _speech_tail
        if _motion_on and _motion_txt:
            # owner 2026-09-12 (speech-source leak): the [MOVEMENT] block came from Mimo's English
            # video_prompt, which OPENS with "The person speaks ONLY the given Thai script, word for
            # word..." and CLOSES with "Audio: speak only the provided Thai script...". Those English
            # SPEECH directives sit right before the final speech-lock and contain NO Thai text, so
            # Wan generates speech from the English description itself -> it 'thinks up its own words'
            # and the opening diverges from the Thai script. Strip EVERY speech/audio sentence from
            # the movement block so it is PURE ACTION; the Thai «» timeline is the ONLY speech source.
            _motion_clean = _motion_txt
            try:
                import re as _re_mv
                # owner 2026-09-12 11:3x: Pete saw the movement block STILL carried speech text
                # ("...nothing before it, nothing between its phrases, and nothing after it." and
                # "Audio: speak only the provided Thai script... silent, no extra speech, no new
                # sound."). Those English speech directives duplicate the Thai ordering above and
                # make Wan "งง" -> shaky voice + melting video. Strip EVERY speech/audio/script
                # mention from the movement block, unconditionally, so it is 100% action only.
                _SPEECH_RE = _re_mv.compile(
                    r"\b(?:speaks?|speaking|spoken|says?|saying|talks?|talking|voice|voice[- ]?over|"
                    r"audio|word for word|given Thai script|provided Thai script|Thai script|"
                    r"script|lip[- ]?sync|narration|no further sound|no extra speech|no new sound|"
                    r"stay silent|silent|after the last word)\b",
                    _re_mv.IGNORECASE)
                _sents = _re_mv.split(r"(?<=[.!?])\s+", _motion_txt)
                _kept = []
                _LEAD = _re_mv.compile(
                    r"^\s*[,;:]?\s*(?:the person|audio|voice|keep silence|silent|only the|she (?:speaks|says|talks))\b",
                    _re_mv.IGNORECASE)
                for _x in _sents:
                    if not _x.strip():
                        continue
                    if _SPEECH_RE.search(_x):
                        if _LEAD.search(_x):  # pure speech directive -> drop whole sentence
                            continue
                        # owner 2026-09-13 17:0x (fixes 'faces the camera HER THAI LINE ALOUD' garbage
                        # -> Wan improvises a SECOND speech line = 'พูดเพี้ยน / 2 เส้นซ้อน'):
                        # the plain _SPEECH_RE.sub only removes the speech VERB, leaving its object
                        # phrase ('her Thai line aloud', 'her line', 'the given script') stuck to the
                        # action clause. Wan reads that dangling fragment and invents speech from it.
                        # Pre-strip the WHOLE speech clause (verb + its line/script object) first.
                        _frag = _x
                        _SPEECH_CLAUSE = _re_mv.compile(
                            r"\b(?:speaks?|speaking|spoken|says?|saying|talks?|talking|delivers?|delivering|reads?|reading|narrates?|narrating)\b"
                            r"[^.!?]{0,60}?\b(?:her|his|their|the|a)?\s*"
                            r"(?:thai\s+)?(?:line|lines|script|dialogue|words?|voice[- ]?over|narration|audio)\b"
                            r"(?:\s+(?:aloud|out\s+loud|naturally|word\s+for\s+word))?",
                            _re_mv.IGNORECASE)
                        _frag = _SPEECH_CLAUSE.sub(" ", _frag)
                        # then drop any remaining bare speech keywords
                        _frag = _SPEECH_RE.sub(" ", _frag)
                        # owner 2026-09-13 17:0x: even with no speech verb left, a dangling OBJECT
                        # phrase like 'her Thai line aloud' / 'her line' / 'the given script' / 'the
                        # provided audio' survives and Wan invents a second speech line from it.
                        # Remove those standalone object phrases too (idempotent, safe).
                        _ORPHAN_OBJ = _re_mv.compile(
                            r"\b(?:her|his|their|the|a)?\s*(?:thai\s+)?"
                            r"(?:line|lines|script|dialogue|voice[- ]?over|narration|audio)\b"
                            r"(?:\s+(?:aloud|out\s+loud|word\s+for\s+word|naturally,\s+mouth\s+moving[^.!?]*))?",
                            _re_mv.IGNORECASE)
                        _frag = _ORPHAN_OBJ.sub(" ", _frag)
                        # owner 2026-09-13 17:0x: also drop leftover 'mouth moving naturally' fragments
                        # (the 'she is speaking' fact already lives once in the opening directive).
                        _frag = _re_mv.sub(
                            r"[,\s]*(?:,\s*)?mouth\s+(?:moving|open|moving\s+naturally)[^.!?]*?(?=\.|$)",
                            "", _frag, flags=_re_mv.IGNORECASE)
                        _frag = _re_mv.sub(r"\b(?:and|while|as|but|then|still)\b\s*", " ", _frag)
                        _frag = _re_mv.sub(r"[,;:]", " ", _frag)
                        _frag = _re_mv.sub(r"\s{2,}", " ", _frag).strip(" .-")
                        _frag = _re_mv.sub(r"\s+(?:to|at|towards?|into)\s+the\s+(?:lens|camera)\s*$", "", _frag, flags=_re_mv.I)
                        # owner 2026-09-12 13:5x: also drop any dangling ", to the camera/lens" that
                        # survives mid-sentence (e.g. "wearing the jeans to the camera with a natural
                        # expression" after the speech verb was removed) so no speech-address fragment stays.
                        _frag = _re_mv.sub(r"[,;]?\s+(?:to|at|towards?|into)\s+the\s+(?:lens|camera)\b", "", _frag, flags=_re_mv.I)
                        _frag = _re_mv.sub(r"\s{2,}", " ", _frag)
                        if _LEAD.search(_frag):  # leftover stub -> drop
                            continue
                        if len(_frag.split()) >= 5:
                            _kept.append(_frag + ".")
                        continue
                    _kept.append(_x)
                _motion_clean = " ".join(_kept).strip()
                _motion_clean = _re_mv.sub(r"\s{2,}", " ", _motion_clean).strip()
                if not _motion_clean:
                    _motion_clean = _motion_txt  # safety: never blank the motion block
                elif _motion_clean != _motion_txt:
                    logger.info(f"  🧹 motion block: removed ALL speech/audio text ({len(_motion_txt)}ch -> {len(_motion_clean)}ch) - action only")
                # owner 2026-09-12 13:5x (fixes 'talking to the lens.' leaking into the positive prompt):
                # even after the sentence/clause strip, a trailing speech phrase like ", talking to the
                # lens." / "speaking to the camera" can survive as a fragment. Scrub those deterministically
                # so the video_prompt NEVER ends on a speech directive that fights the silent settle tail.
                _TAIL_SPEECH = _re_mv.compile(
                    r"[,\s]*(?:and\s+|while\s+|then\s+|still\s+)?"
                    r"(?:talking|speaking|speaks|talk|speak|says|saying)\s+"
                    r"(?:to|at|into|towards?)\s+the\s+(?:lens|camera|viewer|audience)\s*[.!]?\s*$",
                    _re_mv.IGNORECASE)
                _before_tail = _motion_clean
                for _ in range(4):  # loop: strip nested trailing speech fragments
                    _motion_clean = _TAIL_SPEECH.sub("", _motion_clean).strip()
                    if _motion_clean == _before_tail:
                        break
                    _before_tail = _motion_clean
                if _motion_clean and _motion_clean[-1] not in ".!?":
                    _motion_clean += "."
                _motion_clean = _re_mv.sub(r"\s{2,}", " ", _motion_clean).strip()
                if _motion_clean != _before_tail:
                    logger.info("  🧹 stripped trailing 'talking/speaking to the lens/camera' from video_prompt")
            except Exception as _e_mv:
                logger.warning(f"  motion speech-strip skipped: {_e_mv}")
            final_prompt = (
                f"{_stop_rule}\n\n"
                f"[MOVEMENT / การเคลื่อนไหว]:\n{_motion_clean}"
                f"{_speech_tail}"
            )
        logger.info(f"  🎙 Voice mode A: speak-only-script + motion {'AFTER-script' if (_motion_on and _motion_txt) else 'OFF'} (owner fix 2026-09-10 05:52, len={len(final_prompt)}, motion={len(_motion_txt)}ch)")

# ลบ comment เดิม "ห้ามฝัง" แล้วแทนด้วยโหมดฝังเมื่อเปิด


    # ── Generate via shared client ──
    client = ProdiaV2Client(token=PRODIA_TOKEN())

    try:
        # negative_prompt must come from the JSON-driven prompt-builder.
        # No hardcoded fallback: if missing we raise clearly (single source of truth).
        if not negative_prompt:
            raise ValueError("generate_video: negative_prompt is required — supply it from prompt-builder (JSON-driven); refusing hardcoded fallback")
        # 🔴 HARD CAP 500 — Prodia wan2-7.img2vid.v1 schema รับ negative_prompt ได้สูงสุด 500 chars เป๊ะ
        # (len=500 ผ่าน / len=501 → failed: error ปลอม type must be txt2img + field not allowed)
        # ห้ามเกิน 500 เด็ดขาด ระบบพัง. ต้นทาง build_negative_prompt ควรแก้ให้สั้นเองด้วย.
        if len(negative_prompt) > 500:
            logger.warning(f"generate_video: negative_prompt len={len(negative_prompt)} > 500 → truncating to 500 (Prodia cap)")
        neg_p = negative_prompt[:500]
        # owner 2026-09-12 (debug): dump the EXACT prompt + config sent to Prodia so we can
        # see word-for-word what Wan reads (incl. the «» timeline + [MOVEMENT] block).
        try:
            _dbg = TMP_DIR / f"wan_prompt_{uuid.uuid4().hex[:8]}.txt"
            _dbg.write_text(
                "=== PROMPT (" + str(len(final_prompt)) + "ch) ===\n" + final_prompt +
                "\n\n=== NEGATIVE (" + str(len(neg_p)) + "ch) ===\n" + neg_p +
                "\n\n=== META ===\nprompt_extend=" + str(prompt_extend) +
                "\naudio_bytes=" + str(len(audio_bytes) if audio_bytes else None) +
                "\nduration=" + str(duration) + "\nresolution=" + str(resolution) + "\n",
                encoding="utf-8")
            logger.info(f"  🧾 Wan prompt dumped: {_dbg}")
        except Exception as _e_dbg:
            logger.warning(f"  prompt dump skipped: {_e_dbg}")
        result = client.generate_video(
            prompt=final_prompt,
            input_image=image_data,
            duration=duration,
            resolution=resolution,
            audio_bytes=audio_bytes,
            job_type="inference.wan2-7.img2vid.v1",
            negative_prompt=neg_p,
            # FL2V SINGLE image (owner 2026-08-26): ส่งแค่ input_image รูปเดียว
            # ต้องไม่ส่ง last_frame/reference — ไม่งั้น Wan ใช้เป็น start-end/ภาพหลัก
            last_frame=None,
            reference=None,
            # prompt_extend: default True (VALIDATED 2026-08-19 job 26ae0b8f ต้อง True)
            # แต่ให้ owner  override เป็น False ได้ (v10 ท้ายเปลี่ยนมุมกล้อง/ลิ้นชักขยับเอง
            # = prompt_extend เติมเอง → ลองปิด 2026-08-21)
            prompt_extend=prompt_extend,
        )

        output_url = result.get("output_url", "")
        price = result.get("price", {})
        cost_video = float(price.get("dollars", 0))

        if not output_url:
            raise RuntimeError(f"No output URL in result: {result.get('result_raw', {})}")

        # Download the video (Prodia output needs auth)
        auth_headers = {"Authorization": f"Bearer {PRODIA_TOKEN()}"} if "prodia.com" in (output_url or "") else {}
        video_resp = requests.get(output_url, headers=auth_headers, timeout=60)
        video_resp.raise_for_status()

        result_path = TMP_DIR / f"img2vid_{uuid.uuid4().hex[:8]}.mp4"
        with open(result_path, "wb") as f:
            f.write(video_resp.content)

        file_size = result_path.stat().st_size
        logger.info(f"  Video OK ({file_size} bytes, {resolution}): {result_path}")
        logger.info(f"  Cost: ${cost_video:.4f}")
        # Docs-exact: audio ส่งให้ Wan แล้ว → วิดีโอควรมี audio track (TTS ที่ส่งไป)
        # ยังไง compose Step 9b ก็จะแทนที่ด้วย TTS+BGM อยู่ดี (กันเสียงสองชั้น)
        if not has_audio_track(str(result_path)):
            logger.info("  Wan video has no audio track (compose Step 9b จะใส่ TTS+BGM ให้)")

        return str(result_path), cost_video
    except Exception as e:
        logger.error(f"  Prodia Wan 2.7 Video generation failed: {e}")
        raise RuntimeError(f"Prodia Wan 2.7 Video generation failed: {e}")

