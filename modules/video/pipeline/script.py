"""Script analysis & generation (Phase C split, move-only)."""
from ._shared import (  # noqa: F401
    os, re, sys, json, time, uuid, logging, random, subprocess, shutil, asyncio,
    Path, Optional, List, Dict, Any, requests,
    PRODIA_TOKEN, GEMINI_API_KEY, logger,
    IMAGE_GEN_URL, PROMPT_BUILDER_URL, STORAGE_DIR, TMP_DIR,
    get_default_style, get_style_config, validate_ugc_style, is_valid_style,
)
from .providers import (
    _extract_json_obj, _deepseek_key, _mimo_key, _mimo_image_ref,
    _hue_diverse_reference_index, _pick_variant_reference_index,
)
from .prompts import (
    _deepseek_product_prompts, _normalize_negative_prompt, _sanitize_video_prompt,
)

# thai_pronunciation (owner 2026-09-13) — shared deterministic library
try:
    from ..thai_pronunciation import (
        normalize_thai_spoken_script, THAI_ABBR, THAI_SYM, THAI_LATIN,
        THAI_CLUSTER_FIX, THAI_HARD_OPENER,
    )
except ImportError:  # run as top-level script, not a package
    from thai_pronunciation import (
        normalize_thai_spoken_script, THAI_ABBR, THAI_SYM, THAI_LATIN,
        THAI_CLUSTER_FIX, THAI_HARD_OPENER,
    )

def _synthesize_script_beats(script: str, duration: int) -> list:
    """Fallback beat synthesis (Fix C) when the AI omits script_beats.
    Split the flat Thai script into hook/value/cta by sentence-ish boundaries and reserve a
    1-2s SILENT settle tail, so the Wan prompt still gets a timeline. Thai uses few spaces,
    so we split on common clause separators; if we cannot split cleanly we keep one spoken
    beat + settle (still gives Wan an explicit end + silent tail)."""
    if not script or not script.strip():
        return []
    _dur = int(duration or 15)
    _text = script.strip()
    # Split on whitespace and common Thai clause breaks; keep it simple + safe.
    import re as _re
    _parts = [p.strip() for p in _re.split(r"\s+", _text) if p.strip()]
    _spoken_total = max(1, _dur - 2)  # reserve ~2s silent settle
    if len(_parts) >= 3:
        _hook_w, _cta_w = 0.30, 0.25
        _hook_end = max(1, round(len(_parts) * _hook_w))
        _cta_start = max(_hook_end + 1, len(_parts) - max(1, round(len(_parts) * _cta_w)))
        _hook = " ".join(_parts[:_hook_end]).strip()
        _value = " ".join(_parts[_hook_end:_cta_start]).strip()
        _cta = " ".join(_parts[_cta_start:]).strip()
    else:
        _hook, _value, _cta = _text, "", ""
    _beats = []
    # owner 2026-09-12: allocate beat SECONDS by CHARACTER COUNT, not word count.
    # Thai has few spaces, so a word-count split gave value/cta more seconds than the
    # text needs -> Wan had to STRETCH the words to fill the beat -> "เสียงยืด/เพี้ยน".
    # Anchor on the real Thai read rate (12-14 chars/sec) and only use the beat text
    # length as the relative weight inside the spoken window.
    _total_chars = max(1, len(_hook) + len(_value) + len(_cta))
    for _lbl, _txt in (("hook", _hook), ("value", _value), ("cta", _cta)):
        if not _txt:
            continue
        _secs = max(1, round(_spoken_total * len(_txt) / _total_chars))
        _beats.append({"label": _lbl, "seconds": _secs, "text": _txt})
    if _beats:
        _beats.append({"label": "settle", "seconds": max(1, _dur - sum(b["seconds"] for b in _beats)), "text": ""})
    return _beats

def analyze_product(product_name: str, product_image: str = None, description: str = "", ugc_style: str = "holding", body_part: str = "", special_target: str = "", usage_howto: str = "", ingredient_highlight: str = "", category: str = "", subcategory: str = "", gender: str = "", target_age: str = "", duration: int = 15, product_images: list = None, features: str = "") -> dict:
    """
    Step 1: Analyze product via Mistral → product_profile

    Args:
        product_name: ชื่อสินค้า
        product_image: URL ของรูปสินค้า (optional)
        description: คําอธิบายสินค้า (optional)
        ugc_style: UGC style (holding/usage/review/etc.)

    Returns:
        dict: product_profile {
            category, target_gender, target_age, target_audience,
            customer_problem, main_benefit, hashtags, setting,
            _image_prompt, _video_prompt, _negative_prompt
        }
    """
    logger.info(f"Step 1/9: Analyze product (Mistral)")
    logger.info(f"  Product: {product_name}")
    logger.info(f"  Image: {product_image or 'None'}")
    logger.info(f"  UGC style: {ugc_style}")

    try:
        # Call Prompt Builder API
        url = f"{PROMPT_BUILDER_URL}/api/v1/build"
        payload = {
            "product_name": product_name,
            "description": description,
            "product_image": product_image or "",
            "ugc_style": ugc_style,
            "category": category or "",
            "subcategory": subcategory or "",
            # SSOT deep-analysis fields — ดึงจาก Product Analyzer (8106) ส่งตรงเข้า prompt-builder
            "body_part": body_part or "",
            "special_target": special_target or "",
            "usage_howto": usage_howto or "",
            "ingredient_highlight": ingredient_highlight or "",
            # owner 2026-09-12 (plan A): real structured features (variants/specs) → prompt-builder
            "features": features or "",
        }

        # timeout 300s per 2026-09-09 (prompt-builder วิเคราะห์ภาพ+vision ช้า และเมื่อคิวทับ single-worker
        # งานรอในคิวอาจเกิน 130s → เดิม 130 ถูกตัดทิ้งทั้งที่ 8117 ทำสำเร็จทีหลัง ขึ้นเป็น 300 กัน false-timeout)
        resp = requests.post(url, json=payload, timeout=300)
        resp.raise_for_status()
        data = resp.json()

        profile = data.get("analysis", {})
        logger.info(f"  Analyzed: {profile.get('category')} / {profile.get('target_gender')}")

        # Only the negative_prompt (exclusion keywords, not the bottle template) is safe to
        # keep from prompt-builder. image/video prompts are authored by Mimo below — we do
        # NOT install the pb JSON-template image/video_prompt anymore (boss 2026-09-08).
        profile["_image_prompt"] = ""
        profile["_video_prompt"] = ""
        profile["_negative_prompt"] = _normalize_negative_prompt(data.get("negative_prompt", ""))

        # ── Mimo AI-authored prompts (boss 2026-09-08): Mimo is the SOLE image/video prompt
        # author. pb /build is only used above for analysis (category/scenes/script), never for
        # authoring image/video prompts. The old fallback that kept the pb JSON template
        # (hold/bottle/label, caused jeans→bottles) is removed — if Mimo fails we fail loudly
        # rather than ship a wrong-template prompt ("break is break" owner note).
        _ds = _deepseek_product_prompts(
            product_name, description, ugc_style,
            product_image=(product_image or ""),
            product_images=(product_images or []),
            category=category or (profile or {}).get("category", ""),
            subcategory=subcategory or (profile or {}).get("subcategory", ""),
            special_target=special_target or "",
            usage_howto=usage_howto or "",
            gender=gender or (profile or {}).get("target_gender", ""),
            target_age=target_age or (profile or {}).get("target_age", ""),
            duration=duration,
            features=features or "",
        )
        if _ds and _ds.get("image_prompt") and _ds.get("video_prompt"):
            profile["_image_prompt"] = _ds["image_prompt"]
            # owner 2026-09-12: sanitize the video_prompt so a slipped-through set-down/re-grab
            # chain (which makes the pack animate by itself) is rewritten to a keep-in-hand beat.
            _vp_raw = _ds["video_prompt"]
            _vp_clean = _sanitize_video_prompt(_vp_raw)
            if _vp_clean != _vp_raw:
                logger.info(f"  🔧 sanitize video_prompt (set-down/re-grab): {_vp_raw!r} -> {_vp_clean!r}")
            profile["_video_prompt"] = _vp_clean
            # (ข) Mimo thai_script → ให้ generate_script ใช้เป็นตัวพูดจริง (คนเดียว author บท+ภาพ+วิดีโอ)
            # owner 2026-09-10: normalize คำย่อ/สัญลักษณ์ → คำเต็มก่อน (Wan พูดเอง อ่านผิดถ้าเป็นคำย่อ)
            _raw_ts = (_ds.get("thai_script") or "").strip()
            _norm_ts = normalize_thai_spoken_script(_raw_ts)
            # owner 2026-09-12: hard Thai-only filter - Mimo has leaked Chinese (\"认证放心\") and Latin.
            try:
                import re as _re_ts
                _ts_filt = _re_ts.sub(r"[^\u0E00-\u0E7F\s,]+", " ", _norm_ts)
                _ts_filt = _re_ts.sub(r"\s+", " ", _ts_filt).strip(" ,")
                if _ts_filt and _ts_filt != _norm_ts:
                    logger.info(f"  🧹 thai_script sanitized (non-Thai stripped): {_norm_ts[:50]!r} -> {_ts_filt[:50]!r}")
                    _norm_ts = _ts_filt
            except Exception as _e_ts:
                logger.warning(f"  thai_script sanitizer skipped: {_e_ts}")
            if _norm_ts != _raw_ts:
                logger.info(f"  🔧 normalize thai_script: {_raw_ts!r} -> {_norm_ts!r}")
            # owner 2026-09-12: HARD length cap - if Mimo overshoots the duration budget the voice
            # rushes. Trim the weakest trailing clauses (keep hook + the buy CTA) until it fits.
            try:
                _dur_cap = int(duration) if duration else 15
                _cap = 200 if _dur_cap > 12 else (150 if _dur_cap > 8 else 100)
                if len(_norm_ts) > _cap:
                    # 1) try comma-clause trimming (drop weakest middle clauses, keep hook + CTA)
                    _parts = [p.strip() for p in _norm_ts.split(",") if p.strip()]
                    while len(", ".join(_parts)) > _cap and len(_parts) > 2:
                        _parts.pop(len(_parts) - 2)
                    _trimmed = ", ".join(_parts)
                    # 2) if still over (script had few/no commas), trim WHOLE WORDS from the tail of
                    #    the middle, always preserving the final CTA clause (last ~4 words).
                    if len(_trimmed) > _cap:
                        _words = _trimmed.split()
                        _keep_tail = _words[-4:] if len(_words) > 5 else _words
                        _head = _words[:-4] if len(_words) > 5 else []
                        while len(" ".join(_head + _keep_tail)) > _cap and len(_head) > 3:
                            _head.pop()
                        _trimmed = " ".join(_head + _keep_tail)
                    if _trimmed and len(_trimmed) <= _cap:
                        logger.info(f"  ✂️ thai_script trimmed {len(_norm_ts)}ch -> {len(_trimmed)}ch (dur cap {_cap})")
                        _norm_ts = _trimmed
            except Exception as _e_cap:
                logger.warning(f"  thai_script cap skipped: {_e_cap}")
            profile["_mimo_thai_script"] = _norm_ts
            # owner 2026-09-12: which reference image Mimo picked (multi-variant sets).
            if _ds.get("reference_image_index") is not None:
                profile["_reference_image_index"] = _ds.get("reference_image_index")
            # owner 2026-09-12: robust fallback - if the set is multi-variant and the main call did
            # not return an index, ask Mimo a tiny dedicated vision question to choose the reference
            # image that shows the MOST variants together (verified: mimo picks the multi-pack shot).
            _pimgs_all = [u for u in (product_images or []) if isinstance(u, str) and u.strip()]
            if profile.get("_reference_image_index") is None and len(_pimgs_all) > 1:
                try:
                    _ri = _pick_variant_reference_index(_pimgs_all)
                    if _ri is not None:
                        profile["_reference_image_index"] = _ri
                        logger.info(f"  🎨 variant reference index (dedicated pick) = {_ri}")
                except Exception as _e_pick:
                    logger.warning(f"  variant reference pick skipped: {_e_pick}")
            # (C) owner 2026-09-11 (Fix C): structured timed beats from Mimo → passed to the Wan
            # prompt builder so the model sees a timeline and a SILENT settle tail (no gibberish).
            # owner 2026-09-12: FLAT = SOURCE OF TRUTH. Discard Mimo's own script_beats and ALWAYS
            # re-synthesize the timeline beats from the flat thai_script, so the spoken timeline
            # cannot drift from the script shown on screen (root cause: Mimo wrote "รับรองฮาลาล"
            # into a beat but NOT into the flat script -> Wan spoke words absent from the script).
            # One flat script -> beats -> Wan. Single source of truth.
            _beats = []
            # owner 2026-09-12: the TIMELINE (what Wan actually reads) came from Mimo's RAW beat
            # text, which bypassed normalize_thai_spoken_script -> the opening cluster fix + the
            # 'หิวใช่ไหม' re-open never applied to the spoken timeline (real bug: hook stayed
            # 'เบื่อก๋วยเตี๋ยวเรือ...'). Normalize each beat's text now and re-apply the opening guard
            # to the hook so the timeline matches the normalized flat script.
            if _beats:
                try:
                    for _bi, _b in enumerate(_beats):
                        if not isinstance(_b, dict):
                            continue
                        _bt = (_b.get("text") or "").strip()
                        if _bt:
                            _b["text"] = normalize_thai_spoken_script(_bt)
                    _hook_b = next((b for b in _beats if isinstance(b, dict) and b.get("label") == "hook"), None)
                    if _hook_b and _hook_b.get("text"):
                        logger.info(f"  🔧 normalized beat texts for timeline (hook now {_hook_b['text'][:40]!r})")
                except Exception as _e_nb:
                    logger.warning(f"  beat normalize skipped: {_e_nb}")
            if not _beats and _norm_ts:
                # Fallback: synthesize a 3-beat + settle split from the flat script so Fix C still
                # works even if the AI omits script_beats (duration-aware, 12-14 chars/second).
                _beats = _synthesize_script_beats(_norm_ts, duration)
                if _beats:
                    logger.info(f"  🔧 script_beats: synthesized {len(_beats)} beats from flat script (AI omitted them)")
            if _beats:
                profile["_script_beats"] = _beats
                logger.info(f"  ✅ script_beats ({len(_beats)}): " + ", ".join(f"{b['label']}={b['seconds']}s" for b in _beats))
            # (B) owner 2026-09-10: negative สั้น ๆ ที่ Mimo เขียน (เป็นคำ positive-style ไม่มีคำ "no")
            # ใช้แทน negative ยาวจาก prompt-builder ที่ wan อ่านแล้วเพี้ยน — ถ้า Mimo ไม่ส่งมา คงค่า pb ไว้
            _mimo_neg = _normalize_negative_prompt((_ds.get("negative_prompt") or "").strip())
            if _mimo_neg:
                # owner 2026-09-12 (food hero): for PACKAGED FOOD, the sealed pack must be the hero
                # and a cooked bowl must never dominate -> append proven negatives so the model can't
                # render "a bowl of noodles as the clear hero" (the bug the owner keeps seeing).
                _cat_lc = (profile.get("category") or category or "").strip().lower()
                # owner 2026-09-14 fix (vid_3f3ebb8b jacket got a noodle bowl): the short Thai token
                # "ชา" (tea) was substring-matched inside "ผู้ชาย" (man) -> a jacket job was
                # mis-flagged as food and had a bowl injected. Require a REAL food signal: category
                # is food, or an EN token with a word boundary, or a long unambiguous Thai token.
                _food_blob = _cat_lc + " " + (product_name or "").lower()
                _food_en = any(re.search(r"\b" + re.escape(k) + r"\b", _food_blob) for k in (
                    "food", "snack", "noodle", "noodles", "drink", "beverage", "instant",
                    "soup", "tea", "coffee", "milk", "dessert", "meal", "cereal",
                ))
                _food_th = any(k in _food_blob for k in (
                    "ก๋วยเตี๋ยว", "บะหมี่", "มาม่า", "เครื่องดื่ม", "ขนม", "กาแฟ", "ชาเขียว",
                    "นมสด", "นมเปรี้ยว", "อาหาร", "เส้นหมี่", "เส้นเล็ก", "เกี๊ยว", "โจ๊ก", "ข้าว",
                ))
                _food_sig = (_cat_lc == "food") or _food_en or _food_th
                if _food_sig:
                    # owner 2026-09-12 (neg<=500): lean, VOICE-FREE negative list.
                    # (a) ALL speech/voice items REMOVED - we never instruct voice, so there is
                    #     nothing to counter-instruct (owner: "ถ้าเราไม่สั่ง voice ก็ไม่เสี่ยง").
                    # (b) no count-locking phrases (they contradict the story action -> model
                    #     materialises packs). Only neutral state guards remain.
                    # (c) keep it short so the combined negative stays well under Prodia's 500 cap.
                    _food_neg = ("no distorted fingers, no extra hands, no third hand, "
                                 "no warped product, no blurry label, no melted face, "
                                 "no blurry noodles, no smeared mushy food, no fake CGI food, "
                                 "no bowl dominating the frame, no cooked dish as the hero, no multiple bowls, "
                                 "no self-moving product, no pack floating, no new pack added, "
                                 "no invented colour pack, no green pack, "
                                 "no camera wobble, no frame warp, no fade to black, no darkening, "
                                 "no dimming, no vignette, no gradual blackout, no fade out")
                    _mimo_neg = _normalize_negative_prompt(_mimo_neg + ", " + _food_neg)
                    # owner 2026-09-12 ('มีซองสีเขียวหลุดมาด้วย มันมีสีเขียวเหรอ'): Mimo invented a GREEN
                    # pack (real set = red/yellow/blue/orange). Deterministic guard: remove a 'green '
                    # colour attribution from the pack description so the still/wan never render a green pack.
                    try:
                        import re as _re_gr
                        _fields = []
                        _kmap = {"image_prompt": "_image_prompt", "video_prompt": "_video_prompt"}
                        for _k in ("image_prompt", "video_prompt"):
                            _v = _ds.get(_k) if isinstance(_ds, dict) else None
                            # only strip 'green' where it is a PACK colour (keep clothing green like
                            # "sage green ribbed top"). Pack-colour context = the word sits in a colour
                            # LIST with another pack colour nearby, or right after 'packs'/'colours'.
                            # a 'green' that sits next to another pack colour word (in either
                            # direction) is treated as a PACK colour and stripped; a lone 'green'
                            # (e.g. clothing 'sage green top') is left untouched.
                            _pack_green_re = (r"\bgreen\b[\s,()]*(?:and\b[\s,()]*)?(?:red|blue|yellow|orange|brown|gold)\b"
                                              r"|(?:red|blue|yellow|orange|brown|gold)\b[\s,()]*(?:and\b[\s,()]*)?\bgreen\b")
                            if isinstance(_v, str) and _re_gr.search(_pack_green_re, _v, _re_gr.I):
                                _nv = _re_gr.sub(r",?\s*\bgreen\b\s*(and\s+)?", "", _v, flags=_re_gr.I)
                                _nv = _re_gr.sub(r"\bgreen\b\s*(and\s+)?", "", _nv, flags=_re_gr.I)
                                # tidy dangling separators/connectives left by the removal
                                _nv = _re_gr.sub(r"[\s,()]*\band\b\s*\)", ")", _nv, flags=_re_gr.I)
                                _nv = _re_gr.sub(r",\s*and\s*\)", ")", _nv, flags=_re_gr.I)
                                _nv = _re_gr.sub(r",\s*and\b", "", _nv, flags=_re_gr.I)
                                _nv = _re_gr.sub(r"\s*,?(\s*,)+\s*", ", ", _nv)
                                _nv = _re_gr.sub(r",\s*(\)|[-.])", r"\1", _nv)
                                _nv = _re_gr.sub(r"\s{2,}", " ", _nv).strip()
                                if _nv != _v:
                                    _ds[_k] = _nv
                                    profile[_kmap[_k]] = _nv
                                    _fields.append(_k)
                        if _fields:
                            logger.info(f"  🎨 stripped invented 'green' pack colour from {_fields}")
                    except Exception as _e_gr:
                        logger.warning(f"  green-colour guard skipped: {_e_gr}")
                    # owner 2026-09-12 ("ควรจะมีก๋วยเตี๋ยว ใส่ชามวางไว้ด้วย"): rule 1e is MANDATORY but
                    # Mimo still drops the bowl from the image_prompt some runs -> the still has NO bowl,
                    # so Wan has none to work from. Hard-inject the prepared-dish prop deterministically.
                    # owner 2026-09-14 fix (vid_3f3ebb8b): this was nested under `if _mimo_neg:` only, so
                    # a jacket/shirt job got a "bowl of noodles" injected as a prop. Gate it on _food_sig.
                    try:
                        if _food_sig:
                            _bowl_words = ("bowl", "ชาม", "cup of", "ก๋วยเตี๋ยว", "noodles in", "dish of",
                                           "soup", "น้ำซุป", "พร้อมเสิร์ฟ", "prepared")
                            _ip_now = (profile.get("_image_prompt") or "")
                            _bowl_in_ip = any(w in _ip_now.lower() for w in _bowl_words)
                            if _ip_now and not _bowl_in_ip:
                                _bowl_clause = (" A small bowl of the prepared dish (a hot bowl of noodles/broth) "
                                                "rests on the table beside the packs as a secondary prop - "
                                                "appetising, sharp, in the lower foreground, NOT in front of the packs.")
                                profile["_image_prompt"] = _ip_now.rstrip().rstrip(".") + "." + _bowl_clause
                                logger.info("  🍜 image_prompt bowl injected (food prop mandatory - Mimo omitted it)")
                            _vp_now = (profile.get("_video_prompt") or "")
                            _bowl_in_vp = any(w in _vp_now.lower() for w in _bowl_words)
                            if _vp_now and not _bowl_in_vp:
                                profile["_video_prompt"] = (_vp_now.rstrip() + " A small bowl of the prepared "
                                                            "noodles sits still on the table beside the packs throughout the shot.")
                                logger.info("  🍜 video_prompt bowl injected (food prop mandatory - Mimo omitted it)")
                    except Exception as _e_bowl:
                        logger.warning(f"  bowl injection skipped: {_e_bowl}")
                # owner 2026-09-12 (HARD 500 CAP): Prodia wan2-7.img2vid.v1 accepts a negative
                # of at most 500 chars; anything longer is silently TRUNCATED (which dropped all
                # the tail safeguards). Enforce a 480-char ceiling here so the system never breaks.
                _HARD_NEG_CAP = 480
                # owner 2026-09-13: the fade/dark guard is a MUST-KEEP item - pin it to the
                # FRONT of the list so the trim can never drop it (the trim drops from the END).
                _FADE_GUARD = "no fade to black, no darkening, no dimming, no vignette, no gradual blackout"
                # owner 2026-09-13 (card 8c264f8b): the COUNT guard is ALSO a must-keep - pin it to the
                # FRONT too, so a long Mimo negative list can never trim away the 'no missing pack' item
                # (this is the fix for 'Mimo rendered only 3 of 4 packs').
                _COUNT_GUARD = "no missing pack, no missing variant, no missing colour"
                _items0 = [t.strip() for t in _mimo_neg.split(",") if t.strip()]
                _items0 = [t for t in _items0 if t.lower() not in ("no fade to black", "no darkening", "no dimming", "no vignette", "no gradual blackout", "no fade out")]
                _items0 = [t for t in _items0 if t.lower() not in ("no missing pack", "no missing variant", "no missing colour", "no fewer packs")]
                _mimo_neg = ", ".join([_FADE_GUARD, _COUNT_GUARD] + _items0)
                if len(_mimo_neg) > _HARD_NEG_CAP:
                    # keep whole comma items only, drop from the END until it fits
                    _items = [t.strip() for t in _mimo_neg.split(",") if t.strip()]
                    _kept = []
                    for _it in _items:
                        if len(", ".join(_kept + [_it])) > _HARD_NEG_CAP:
                            break
                        _kept.append(_it)
                    _trimmed = ", ".join(_kept)
                    logger.warning(f"  ⚠️ negative_prompt {len(_mimo_neg)}ch > {_HARD_NEG_CAP} → trimmed to {len(_trimmed)}ch (dropped {len(_items)-len(_kept)} items)")
                    _mimo_neg = _trimmed
                profile["_negative_prompt"] = _mimo_neg
                logger.info(f"  ✅ Mimo negative_prompt ({len(_mimo_neg)}ch) แทน pb negative")
            logger.info(f"  ✅ Mimo authored image/video/script prompts for {product_name!r} (script {len(profile['_mimo_thai_script'])}ch)")
        else:
            logger.error(f"  Mimo failed to author prompts for {product_name!r} — refusing prompt-builder JSON template fallback")
            raise RuntimeError(
                f"Mimo prompt authoring failed (no JSON-template fallback). Product={product_name!r}: prompt-builder returned no usable Mimo prompt"
            )

        # ── Beat-timed script จาก service (single source of truth) ──
        # timing_validation/scripts.full_script สร้างจาก router_config.scenes
        # (4-beat: hook→agitate→solve→cta) แล้ว → ใช้เป็น script หลักให้ sync กับ
        # 4-beat video prompt แทนการให้ Gemini gen ใหม่ที่หลุด beat
        _scripts = data.get("scripts", {}) or {}
        profile["_beat_timed_script"] = _scripts.get("full_script", "")
        profile["_script_tts_speed"] = (data.get("timing_validation", {}) or {}).get("tts_speed", 1.0)

        return profile

    except Exception as e:
        # NO hardcoded fallback profile. When the JSON-driven prompt-builder
        # fails we must fail loudly so it's fixable — a silently-substituted
        # hardcoded image/video/negative prompt would bypass your JSON prompt
        # sources and quietly produce off-brand output. ("break is break")
        logger.error(f"Analyze failed (prompt-builder unreachable/no prompt): {type(e).__name__}: {e}")
        raise RuntimeError(
            f"prompt-builder returned no usable prompt (refusing hardcoded fallback): {e}"
        ) from e

# ═══════════════════════════════════════════════════════════════════════════
# STEP 3: Generate Script (Gemini)
# ═══════════════════════════════════════════════════════════════════════════

def generate_script(
    product_name: str,
    product_profile: dict,
    recipe: dict,
    ugc_style: str = "holding",
    gender: str = "female",
) -> str:
    """
    Step 3: Generate script via Gemini

    Args:
        product_name: ชื่อสินค้า
        product_profile: ผลจาก analyze_product()
        recipe: ผลจาก load_recipe()
        ugc_style: สไตล์ UGC (holding, review, product_demo, ...)

    Returns:
        str: full_script
    """
    logger.info(f"Step 3/9: Generate script (Gemini, style={ugc_style})")

    # Owner 2026-09-02: no-person ambient styles (indoor_projector/ambient_outdoor)
    # have NO speaking person in the clip — skip Gemini sales script entirely so
    # Wan never reads a broken/boring Thai voiceover over the ambient scene.
    _nh = (ugc_style or "").strip().lower()
    if _nh in ("indoor_projector", "ambient_outdoor"):
        logger.info(f"  No script: style {_nh} is no-person ambient — empty script")
        return ""

    # ── (ข) Mimo-authored thai_script ชนะก่อน (owner 2026-09-09 23:0x) ──
    # Mimo เขียน image+video_prompt+thai_script พร้อมกันใน call เดียว → ใช้บทนั้นเป็นตัวพูด
    # จะได้ บท+ภาพ+วิดีโอ sync จากผู้เขียนคนเดียว (แก้ APPEND 15: เดิม Mimo เขียนบทแต่โดนทิ้ง
    # แล้วไปใช้ beat_timed 184ch ที่ภาพไม่ sync) — ถ้า Mimo ไม่ส่งบท ค่อยใช้ beat_timed
    mimo_script = normalize_thai_spoken_script((product_profile.get("_mimo_thai_script") or "").strip())
    if mimo_script:
        logger.info(f"  Script: Mimo-authored thai_script (sync ภาพ+วิดีโอ, {len(mimo_script)}ch): {mimo_script[:80]}...")
        return mimo_script

    # ── Beat-timed script จาก service (single source of truth) ──────────
    # timing_validation/scripts.full_script ถูก build จาก router_config.scenes
    # (4-beat: hook→agitate→solve→cta) แล้ว → ใช้เลยให้ sync กับ 4-beat video prompt
    # ไม่งั้น Gemini gen ใหม่จะหลุด beat ไม่ตรงกับ cut ของวิดีโอ
    beat_timed = product_profile.get("_beat_timed_script", "")
    if beat_timed:
        logger.info(f"  Script: beat-timed จาก prompt-builder-service (sync 4-beat): {beat_timed[:80]}...")
        return beat_timed

    try:
        sys.path.insert(0, str(Path(__file__).parent))
        from script_gen import generate_tiktok_review_script

        # product_demo style → use natural Thai narration template
        # other styles → use review template (Hook/Value/CTA)
        style = "product_demo" if ugc_style == "product_demo" else "review"

        result = generate_tiktok_review_script(
            product_name=product_name,
            customer_problem=product_profile.get("customer_problem", ""),
            main_benefit=product_profile.get("main_benefit", ""),
            target_audience=product_profile.get("target_audience", ""),
            tone="เป็นกันเอง พูดเร็ว",
            duration=f"{recipe.get('total_duration', 8)}s",
            features=product_profile.get("features", ""),
            product_appearance=product_profile.get("product_appearance", ""),
            style=style,
            gender=gender,
        )

        script = result.get("script", "")
        logger.info(f"  Script: {script[:100]}... (uses_llm={result.get('uses_llm')})")
        return script

    except Exception as e:
        # NO hardcoded Thai narration fallback. If script generation fails we
        # fail loudly so it's fixable — a hardcoded script would bypass the
        # JSON-driven content and could desync from the TTS/voiceover.
        logger.error(f"Script generation failed (refusing hardcoded fallback): {e}")
        raise RuntimeError(f"script generation failed (no fallback): {e}") from e

