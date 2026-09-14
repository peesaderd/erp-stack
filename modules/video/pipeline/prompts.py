"""Prompt builders & prompt sanitizers (Phase C split, move-only)."""
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

# owner 2026-09-14: shared wearable detector. Used both by _deepseek_product_prompts
# (to force a wear-style prompt) AND by the orchestrator (to route image placement to
# "wear" instead of "hold", so the appended hold directive does not re-introduce a held
# pose - the real cause of "model wears the jeans and still holds them").
_WEARABLE_SUB_TOKENS = ("clothing", "garment", "apparel", "fashion", "wear", "shirt", "blouse", "hoodie",
                        "sweater", "jacket", "coat", "jeans", "trousers", "pants",
                        "skirt", "dress", "top", "shoes", "shoe", "sneaker", "boots",
                        "sandal", "wearable")
_WEARABLE_NAME_TOKENS = ("เสื้อ", "กางเกง", "แจ็คเก็ต", "แจ็กเก็ต", "แจ็คเก็ท", "เดรส", "กระโปรง",
                         "รองเท้า", "กางเกงยีนส์", "แขนยาว", "ฮู้ด", "ฮู้ดดี้",
                         "jacket", "jeans", "trousers", "shirt", "dress", "skirt", "pants",
                         "hoodie", "sweater", "blouse")


def is_wearable(category: str = "", subcategory: str = "", product_name: str = "") -> bool:
    """True if the product is apparel/shoes that must be WORN, never placed or held."""
    sub_lc = str(subcategory or "").strip().lower()
    name_lc = str(product_name or "").lower()
    cat_lc = str(category or "").strip().lower()
    return (any(t in sub_lc for t in _WEARABLE_SUB_TOKENS) or
            any(t in cat_lc for t in _WEARABLE_SUB_TOKENS) or
            any(t in name_lc for t in _WEARABLE_NAME_TOKENS))


def _normalize_negative_prompt(neg: str) -> str:
    """owner 2026-09-10: EVERY comma item in the negative_prompt MUST carry an explicit
    negative word, otherwise the model renders the bare noun. Force 'no ' prefix where
    missing. NOTE (owner 2026-09-10 18:2x): removed the Vietnamese-language lock —
    mentioning 'Vietnamese' in the negative made Wan babble random speech (it is not
    Vietnamese, so the term had no effect and may have seeded noise). Only generic
    visual-flaw negatives should be used; the spoken-language guard lives in the script
    stop-rule (speak ONLY the Thai script), not in the negative prompt."""
    if not neg or not isinstance(neg, str):
        return neg or ""
    _NEG_PREFIX = ("no ", "don't ", "dont ", "not ", "never ", "without ", "avoid ")
    _tokens = []
    for _t in neg.split(","):
        _t = _t.strip()
        if not _t:
            continue
        if not _t.lower().startswith(_NEG_PREFIX):
            _t = "no " + _t
        _tokens.append(_t)
    # dedupe while preserving order
    _seen, _uniq = set(), []
    for _t in _tokens:
        _k = _t.lower()
        if _k not in _seen:
            _seen.add(_k)
            _uniq.append(_t)
    # owner 2026-09-10 18:2x: Vietnamese lock REMOVED (caused babbling, no benefit).
    return ", ".join(_uniq)

def _normalize_script_beats(beats) -> list:
    """owner 2026-09-11 (Fix C): normalize the Mimo-authored timed script beats.
    Returns a list of {'label','seconds','text'} with labels hook/value/cta/settle in order.
    Robust to missing/loose input: filters junk, coerces seconds to int, keeps empty-text
    settle beats. Empty list if nothing usable (caller then falls back to the flat script)."""
    if not isinstance(beats, list):
        return []
    _order = {"hook": 0, "value": 1, "cta": 2, "settle": 3}
    _out = []
    for _b in beats:
        if not isinstance(_b, dict):
            continue
        _label = str(_b.get("label") or "").strip().lower()
        if _label not in _order:
            continue
        try:
            _secs = int(round(float(_b.get("seconds") or 0)))
        except (TypeError, ValueError):
            _secs = 0
        _text = _b.get("text")
        _text = _text.strip() if isinstance(_text, str) else ""
        if _secs <= 0:
            continue
        _out.append({"label": _label, "seconds": _secs, "text": _text})
    _out.sort(key=lambda b: _order[b["label"]])
    return _out

def _sanitize_video_prompt(vp: str) -> str:
    """Owner 2026-09-13: set-down is now ALLOWED (rule 3b was relaxed) - we keep the legitimate
    ONE clean set-down + ONE re-lift beat. Only the *repeated* set-down/re-grab LOOP is stripped
    (that is what makes the pack animate by itself in Wan).

    Previously (2026-09-12) this stripped ALL set-down beats, which made Mimo/Wan keep a
    death-grip on the product for the whole clip -> hand melts / fingers distort.
    """
    if not vp:
        return vp
    import re as _re
    out = vp
    # ── owner 2026-09-13: KEEP the first legitimate set-down + re-lift ──────────────
    # Rule 3b is now relaxed (one clean set-down + one re-lift IS allowed). We must NOT
    # delete that beat any more - deleting it made Mimo/Wan hold the product in a dead
    # grip for the whole clip (hand melts, fingers distort, worn-garment vanishes).
    # We ONLY strip the *repeated* set-down -> re-grab LOOP (2nd+ handoff), which is what
    # makes an unheld pack animate/drift on its own.
    cleaned = out
    # Count the set-down / re-grab handoffs. If there is more than ONE handoff, the extra
    # ones (the loop) are the bug: keep the first set-down sentence, drop subsequent ones.
    _handoff = _re.compile(
        r"(?<=[.]\s)"
        r"[^.]*?\b(?:sets? (?:the |it |the product |the pack )?(?:product|pack|item|it)?\s*(?:back )?down|"
        r"set (?:it|the product|the pack) down|releases? (?:it|the product|the pack)|"
        r"lets go of (?:it|the product|the pack)|puts? (?:it|the product|the pack) back|"
        r"places? (?:it|the product|the pack) (?:back )?on|"
        r"picks? (?:the product|the pack|it) (?:back )?up again)[^.]*\.",
        _re.IGNORECASE,
    )
    _matches = list(_handoff.finditer(cleaned))
    if len(_matches) > 1:
        # Keep the FIRST handoff, remove the rest (the forbidden loop).
        for m in reversed(_matches[1:]):
            cleaned = cleaned[:m.start()] + cleaned[m.end():]
    # Owner 2026-09-12: 'revealing all four packs' triggers Wan to DRAW extra packs when the camera
    # pulls back. Replace with a count-preserving phrasing.
    cleaned = _re.sub(r"revealing all (?:four|4) packs", "the same packs remain on the table, unchanged, no new pack appears", cleaned, flags=_re.IGNORECASE)
    cleaned = _re.sub(r"revealing all (\w+) packs", r"the same packs remain on the table, unchanged, no new pack appears", cleaned, flags=_re.IGNORECASE)
    # Collapse any doubled spaces / stray ' .'
    cleaned = _re.sub(r"\s{2,}", " ", cleaned).replace(" .", ".").strip()
    # Guard: if the strip nuked too much, keep the original (safety).
    return cleaned if len(cleaned) > len(out) * 0.5 else out

def _deepseek_product_prompts(product_name: str, description: str, ugc_style: str = "holding",
                              category: str = "", subcategory: str = "",
                              special_target: str = "", usage_howto: str = "",
                              gender: str = "", target_age: str = "",
                              product_image: str = "", duration: int = 15,
                              product_images: list = None, features: str = "") -> Optional[dict]:
    """Have Mimo write the image/video prompts fresh from the actual product.

    Boss directive 2026-09-08: use Mimo exclusively (ไมใช่ DeepSeek).
    Mimo v2.5 / mimo-v2.5-pro (xiaomi) are the ONLY prompt-writers here; the previous
    DeepSeek fallback was removed. On total Mimo failure this returns None and the caller
    fails loudly (never falls back to the prompt-builder JSON bottle template).

    Returns {"image_prompt": str, "video_prompt": str} or None on any failure.
    """
    try:
        _mimo_key_ = _mimo_key()
        _providers = []
        if _mimo_key_:
            # Mimo v2.5 base tier first.
            _providers.append({
                "name": "mimo",
                "url": "https://token-plan-sgp.xiaomimimo.com/v1/chat/completions",
                "model": "mimo-v2.5",
                "key": _mimo_key_,
                "max_tokens": 8000,
            })
            # Mimo v2.5-pro tier = second shot when base returns empty (still 100% Mimo,
            # boss "ใช้ Mimo ทั้งหมดเลย"). pro+dropropriate budget reliably returns the JSON.
            _providers.append({
                "name": "mimo-pro",
                "url": "https://token-plan-sgp.xiaomimimo.com/v1/chat/completions",
                "model": "mimo-v2.5-pro",
                "key": _mimo_key_,
                "max_tokens": 8000,
            })
        # DeepSeek/Gemini/Mistral fallback REMOVED per boss "ใช้ Mimo ทั้งหมดเลย" (2026-09-08).
        if not _providers:
            logger.warning("_deepseek_product_prompts: no Mimo key available")
            return None
        # owner 2026-09-11: thai_script MUST fill the clip. vid_2134a3b0 (boat noodles) had a 102ch
        # script (~6-8s of Thai) against a 15s clip -> Wan ran out of script and improvised
        # gibberish for the last ~7s ('พูดเพี้ยน'). Make the char budget duration-aware so the
        # spoken line spans the whole clip with only a short settle tail.
        try:
            _dur = int(duration) if duration else 15
        except Exception:
            _dur = 15
        if _dur <= 8:
            _char_min, _char_max = 70, 100
        elif _dur <= 12:
            _char_min, _char_max = 110, 150
        else:
            # owner 2026-09-12: 15s clips still left a ~2s silent tail because 135-185ch ≈ 11-13.5s.
            # Raise the floor so the spoken line truly fills 15s (12-14 chars/sec), but keep a HARD
            # CEILING so Mimo doesn't overshoot into a rushed read (291ch was too long).
            _char_min, _char_max = 195, 215
        # owner 2026-09-14 (fixes vid_3f3ebb8b jacketed male rendered female): honor the
        # resolved target gender instead of silently defaulting the creator to female.
        # The analyzer/param gender is authoritative when it says male; when it is empty we
        # keep the neutral default line. Apparel/unisex products that read male must render a
        # male presenter, matching the product image.
        _g_lc = str(gender or "").strip().lower()
        # Wearable-aware gender (owner 2026-09-14 - fixes vid_3f3ebb8b male/unisex jacket
        # rendered female): the analyzer defaults to 'female' when the name/desc do not state
        # a gender, so a men's/unisex garment silently becomes a female presenter. For
        # wearables we do NOT trust that default - instead we tell Mimo (who can SEE the
        # product image) to match the gender of the model shown wearing the garment, and to
        # use a MALE creator for men's/unisex apparel.
        # owner 2026-09-14 v2 (fixes BOTH vid_3f3ebb8b AND a male-over-correction on women's
        # jeans): gender must be EVIDENCE-BASED, never a blanket apparel preference.
        #   * explicit male/unisex cue in name/desc  -> MALE creator
        #   * explicit female cue in name/desc       -> female creator
        #   * no cue / flat-lay with no wearer        -> MATCH the reference-image model if one is
        #                                                visible; if still unknown, KEEP the analyzer
        #                                                gender (do NOT force male or female).
        # The previous rule hard-preferred MALE for jackets/shirts/jeans/trousers, which wrongly
        # turned women's jeans into a male presenter. Jeans/trousers are commonly women's wear, so
        # they must never default to male.
        _name_lc_g = str(product_name or "").lower()
        _desc_lc_g = str(description or "").lower()
        _wear_g = ("เสื้อ", "กางเกง", "แจ็คเก็ต", "แจ็กเก็ต", "แจ็คเก็ท", "เดรส", "กระโปรง",
                   "รองเท้า", "แขนยาว", "ฮู้ด", "jacket", "jeans", "trousers", "shirt",
                   "dress", "skirt", "pants", "hoodie", "sweater", "blouse")
        _is_wearable_g = any(_t in _name_lc_g for _t in _wear_g)
        _gender_blob = _name_lc_g + " " + _desc_lc_g
        # owner 2026-09-14: explicit "for men and women" (ผู้ชาย…และ…ผู้หญิง / unisex wording) means
        # UNISEX, not female. The jacket test payload is "เสื้อแจ็คเก็ตบอมเบอร์ สำหรับผู้ชายและผู้หญิง"
        # (for men AND women) and the owner approved a MALE presenter for it (the product image shows a
        # man). Treat an explicit male mention on a UNISEX item as a male cue, and only let ผู้หญิง/หญิง
        # veto male when it appears WITHOUT an accompanying ผู้ชาย (i.e. a purely women's garment).
        _has_male_word = any(_k in _gender_blob for _k in ("ผู้ชาย", "ชาย", "หนุ่ม", "men's", "mens", " men", "man "))
        _has_female_word = any(_k in _gender_blob for _k in ("ผู้หญิง", "หญิง", "สาว", "สุภาพสตรี", "women's", "womens", "women", "ladies", "lady"))
        _unisex_word = (any(_k in _gender_blob for _k in ("unisex", "ผู้ชายและผู้หญิง", "ชายและหญิง", "ทั้งชายและหญิง")) or
                        ("ผู้ชาย" in _gender_blob and "ผู้หญิง" in _gender_blob) or
                        (_has_male_word and _has_female_word))
        _male_cue = _has_male_word or _unisex_word
        _female_cue = _has_female_word and not _has_male_word
        if _g_lc in ("male", "man", "men", "ชาย", "ผู้ชาย") or (_unisex_word and _has_male_word) or (_male_cue and not _female_cue):
            _gender_instr = (
                "- CREATOR GENDER (HARD RULE - owner 2026-09-14): this product targets a MALE audience "
                "(the name/description say so, or it is explicitly unisex). The creator MUST be a MALE "
                "Thai creator (a young man, early-to-mid 20s, stylish and believable). ALSO match the model "
                "gender shown actually wearing the garment in the reference image - if the reference image "
                "shows a man wearing it, use a man. Do NOT use a female creator. Write the person as a man "
                "('he') throughout image_prompt and video_prompt.\n"
            )
        elif _is_wearable_g:
            # Garment with no male cue: DO NOT assume male OR force female blindly - match the
            # reference image model; if none, keep the given/resolved gender as-is.
            _gender_instr = (
                "- CREATOR GENDER (owner 2026-09-14): set the creator's gender to MATCH the model shown "
                "wearing the garment in the reference image - if the image shows a man wearing it, use a "
                "MALE creator; if it shows a woman, use a female creator. If the reference image is a "
                "flat-lay / pack-shot with no visible wearer, KEEP the requested creator gender as given "
                "(do not switch it) and, when the description mentions women (ผู้หญิง/หญิง/สาว/women) prefer "
                "a female creator. NEVER change a clearly stated gender.\n"
            )
        else:
            _gender_instr = ""
        sysprompt = (
            "You are a top-tier Thai UGC creator making premium, beautiful, and hyper-authentic video concepts "
            "for TikTok Shop, Reels, and Shorts. Your goal is to make the audience feel: I have this problem -> "
            "this product solves it -> I need this now.\n\n"
            "Work directly from the provided product input and reference image (visual details, packaging, "
            "texture, color, real selling points). Ground everything in the real product.\n\n"
            "[STRICT OUTPUT FORMAT]\n"
            "Return ONLY a valid, raw JSON object. No markdown wrappers, no backticks, no conversational text.\n"
            "{\n"
            " \"thai_script\": \"<Natural spoken Thai hook + benefit + CTA, MUST fill ~" + str(_dur) + "s of speech (~" + str(_char_min) + "-" + str(_char_max) + " characters)>\",\n"
            " \"script_beats\": [\n"
            "   {\"label\": \"hook\", \"seconds\": <int>, \"text\": \"<spoken Thai, ~3-4s>\"},\n"
            "   {\"label\": \"value\", \"seconds\": <int>, \"text\": \"<spoken Thai, the main benefit, ~6-8s>\"},\n"
            "   {\"label\": \"cta\", \"seconds\": <int>, \"text\": \"<spoken Thai buy-push ending on a firm closing particle, ~2-3s>\"},\n"
            "   {\"label\": \"settle\", \"seconds\": <int>, \"text\": \"\"}\n"
            " ],\n"
            " \"image_prompt\": \"<Rich, concrete still-frame anchor, ~60-90 words>\",\n"
            " \"reference_image_index\": <int: 0-based index of the supplied reference image that BEST shows the product to copy - for a multi-variant set pick the image that shows the MOST variants/packs together>,\n"
            " \"video_prompt\": \"<ONE continuous shot. MOTION ONLY - do NOT mention speaking, talking, voice, audio or the script anywhere in the video_prompt (owner 2026-09-14: the system appends the speech directive itself; a speech instruction inside the video_prompt duplicates it and makes Wan hallucinate a SECOND speech line). START WITH the OPENING framing/camera. MAIN ACTION: ONE short flat sentence (NO numbered list of steps) - she simply HOLDS the product in her hand for the whole clip. No applying, no opening, no set-down, no extra gestures. No filler adjectives, no flowing prose. CLOSING: one short sentence ending on a calm fully-lit settle, holding the product steady to camera.>\"\n"
            " \"negative_prompt\": \"<comma-separated list where EVERY item MUST start with a negative word - 'no ...' or 'don't ...'. ~60-120 chars. Example: no distorted fingers, no extra hands, no warped product, no blurry label, no melted face>\"\n"
            "}\n\n"
            "[SCRIPT_BEATS - owner 2026-09-12] DO NOT write \"script_beats\" yourself. The SYSTEM splits your "
            "flat thai_script into timed beats automatically (hook/value/cta + a silent settle tail) - one flat script "
            "is the SINGLE SOURCE OF TRUTH, so the spoken timeline can never drift from the script shown on screen "
            "(root cause of Wan speaking words that were not in the script). Just write ONE clean flat thai_script and "
            "stop. Optional: you MAY still return \"script_beats\" but it will be IGNORED.\n\n"
            "[TARGET AUDIENCE & CREATOR]\n"
            "- Choose the youngest age in the target demographic (e.g. 25-35: use 25).\n"
            "- Creator: an attractive, youthful, believable Thai person matching the product audience - fresh "
            "glowing skin, pleasant, natural, relatable. Default: Thai female, mid-20s.\n"
            + _gender_instr +
            "- Setting: a stylish, lived-in Thai home (bright condo living room, aesthetic vanity, tidy kitchen) "
            "under warm, flattering natural light that makes her look great.\n\n"
            "[FORM FACTOR - HARD RULE - owner 2026-09-11]\n"
            "- If a reference product image is provided, you MUST read the product's EXACT FORM FACTOR and\n"
            "   physical shape from that image, and describe the product exactly as it appears. NEVER guess\n"
            "   the form factor from the product TITLE alone.\n"
            "- HEADPHONES/AUDIO: look at the image and decide - IN-EAR (small earbuds inserted into the ear\n"
            "   canal, usually shown with a charging case) vs OVER-EAR/ON-EAR (large cups on a headband worn\n"
            "   OVER the head). Use ONLY the form factor the image shows. If the title says only \"หูฟัง/headphones\",\n"
            "   the IMAGE decides - never default to over-ear.\n"
            "- Never mix two form factors in one shot (e.g. do NOT show over-ear cups AND a small case together\n"
            "   unless the real product genuinely is that). Match the image 1:1.\n"
            "[PRODUCT FOCUS MANDATE - HERO FIRST]\n"
            "- The product is the ABSOLUTE hero; the human demonstrator is strictly secondary. "
            "BOTH FACES AND PRODUCT SHARP (owner 2026-09-13 - fixes '\u0e2a\u0e34\u0e19\u0e04\u0e49\u0e32\u0e0a\u0e31\u0e14 \u0e04\u0e19\u0e40\u0e1a\u0e25\u0e2d'): the product AND the "
            "demonstrator must BOTH be in sharp, crisp focus - her face stays clear and natural (visible skin "
            "texture, sharp eyes) and does NOT go soft or blurry. Use a slightly deeper focus plane so face + "
            "product are sharp together; do NOT ask for a heavily blurred/bokeh background. Say 'her face and "
            "the product are both in crisp focus'. "
            "TIGHT FRAMING (owner 2026-09-13 - fixes '\u0e20\u0e32\u0e1e\u0e01\u0e27\u0e49\u0e32\u0e07\u0e40\u0e01\u0e34\u0e19\u0e44\u0e1b'): compose a CLOSE MEDIUM SHOT "
            "(waist-up to chest-up) where the product DOMINATES the lower-to-middle foreground and fills roughly "
            "40-50% of the frame. NEVER a wide full-room shot, NEVER the presenter small and distant. Crop in.\n"
            "- SCREEN SHARE: the product must occupy roughly 40-50% of the frame and stay in the "
            "lower-to-middle foreground through the whole clip, never tiny, off to one side, or out of frame.\n"
            "- HELD *OR* PLACED (owner 2026-09-12 - fixes 'Holding too strong, never puts it down'): being "
            "the hero does NOT mean the hand must grip it continuously. A product RESTING upright on a clean "
            "surface (table/vanity/counter) IS a valid hero presentation, as long as it stays in sharp focus "
            "in the lower-to-middle foreground and the label faces the lens. The demonstrator may PLACE the "
            "product DOWN and leave it sitting on the surface for a beat - or for the whole clip - and this is "
            "CORRECT, not a failure. Never force a continuous grip.\n"
            "- PACKAGED GOODS: the packaging/bottle/box is held upright, facing the lens, stabilized and centered - "
            "NEVER let it drift off-screen or get occluded by the hands. The real label of the reference product "
            "shows clearly.\n"
            "- PACKAGED FOOD = THE PACK IS THE HERO (owner 2026-09-12 - fixes 'a bowl of noodles keeps stealing the "
            "shot'): when the product is PACKAGED FOOD (instant noodles, snacks, drinks, sachets, boxes), the "
            "SEALED PACK / SACHET / BOX is the hero of the frame - NOT a cooked dish. The reference image shows the "
            "PRODUCT PACK; draw THE PACK as the clear hero, upright, label facing the lens, sharp and fully "
            "readable. For a MULTI-PACK set it is FINE (and encouraged) to lean/stack the packs against each other so "
            "all of them fit - keep each label readable. A bowl/cup of the PREPARED food may appear ONLY as a small secondary prop (never more than "
            "~15% of the frame, never in front of the pack, never the focus) OR may be omitted entirely. NEVER "
            "write an image_prompt where 'a bowl of noodles sits as the clear hero' or where the cooked dish "
            "dominates the frame - the SEALED PACK is the star. The script sells the PACK the viewer will buy.\n"
            "- MULTI-VARIANT / MULTI-FLAVOUR PACK (owner 2026-09-12 - fixes 'only one colour/scent shown, other "
            "variants never mentioned'): if the product is a set with MORE THAN ONE variant (flavours, scents, "
            "colours, sizes, noodle types), and the reference/description lists them, SHOW the different variants "
            "together (e.g. the differently-coloured packs standing side by side, labels readable) and MENTION "
            "the variety in the script. SCRIPT RULE (owner 2026-09-12 v2 - Mimo kept skipping the variety): the "
            "thai_script MUST ENUMERATE at least THREE real variants by name (e.g. 'เส้นเล็ก เส้นใหญ่ เส้นหมี่ญี่ปุ่น เส้นบุก') "
            "and, when the data lists spice/heat levels, NAME the spice range too (e.g. 'มีทั้งเผ็ดน้อย เผ็ดกลาง เผ็ดมาก'). "
            "Do NOT stop at two - cover the actual range. NEVER collapse a multi-variant set down to a single "
            "colour/flavour, and never invent variants that are not in the product data.\n"
            "COUNT-ALL-PACKS (owner 2026-09-12 v3 - fixes 'asked for 4 packs, the still rendered only 3'; \n"
            "   v4 2026-09-13 - still leaked, pin harder): the still "
            "   frame MUST show EVERY pack of the set, not a subset. When the data lists N variants you MUST place all N "
            "   packs in the frame - COUNT them literally in the prompt ('exactly four packs: 1 red, 2 brown/yellow, 3 blue, "
            "   4 green - ALL FOUR visible, none missing'). ARRANGE them so every pack is visible at once - a neat row "
            "   side by side is fine, but you may ALSO LEAN some packs back against others, STACK one on top of another, "
            "   or fan them out like a hand of cards; slight overlap is OK as long as every pack stays identifiable. "
            "   The bowl of prepared food (if used) is a SMALL secondary prop beside the packs - it must NEVER cover or "
            "   push a pack out of frame. Do NOT show only 3 of 4 packs, do NOT let packs merge into one blob, do NOT "
            "   hide a pack behind another.\n"
            "   COUNT VERIFICATION (owner 2026-09-13 v4 - fixes 'Mimo still rendered only 3 of 4'): BEFORE you "
            "   finish, RE-READ your image_prompt and count the packs you actually wrote - the number of packs "
            "   described MUST equal N from the data. If your draft shows fewer, ADD the missing packs (name each "
            "   one and its colour) until the count matches N. Do NOT stop at 3 when the data says 4. The number "
            "   word in the prompt must match the real variant count exactly (data says 4 -> write 'four packs', "
            "   not 'three').\n"
            "COLOUR FIDELITY (owner 2026-09-12 - fixes 'all packs render the same red'): the pack COLOURS in your "
            "image_prompt MUST MATCH the colours you actually SEE in the provided reference images - do NOT invent "
            "a colour per variant. If the references show a group shot with red + brown + yellow + blue packs, "
            "describe exactly those colours. When you cannot tell which colour goes with which variant, DESCRIBE "
            "THE COLOURS ONLY ('four packs in red, brown, yellow and blue standing side by side') and do NOT "
            "pair a colour to a named variant. HARD RULE: NEVER write a pack colour that does NOT appear in the "
            "reference images (owner 2026-09-12 - the model invented a 'green' pack that does not exist; the real "
            "set is red/yellow/blue/orange). Any colour you name MUST be literally visible in the references. "
            "ALSO: include the multi-pack GROUP SHOT reference as the primary "
            "composition - reproduce the whole coloured line together, not one pack repeated.\n"
            "- APPAREL / GARMENTS: the garment is the hero - frame torso-to-knee or a full-body mirror view so the "
            "cut, silhouette and drape dominate; never sacrifice garment visibility for an extreme face close-up. "
            "Model WEARS it and shows fit and drape with gentle turns and soft steps, hands relaxed, letting the "
            "fabric move naturally.\n"
            "- HELD / PRESENTED (skincare/cosmetics - owner 2026-09-13): the default is NOT to apply, and \n"
            "APPLYING IS FORBIDDEN (owner 2026-09-13: 'a apply ออกนั่นแหละ ... ถ้า wan สับสน เสียงจะเพี้ยนอีก'): \n"
            "never write that she squeezes, dispenses, dabs, spreads, smooths, rubs or applies the product - not \n"
            "to her face, arm, hand or anywhere. Show the presenter HOLDING and PRESENTING the product to camera \n"
            "while she presents it - that is the whole action (rule 2b). She may lift it, hold it, turn it, set it down \n"
            "and pick it up again - any natural gesture, but NEVER open, squeeze or apply it. The container stays \n"
            "CLOSED the whole clip; the cap stays on the container, in frame, the entire time.\n"
            "- THE ENDING BEAT: the final 2-3 seconds must stay BRIGHT and FULLY LIT with the product clearly "
            "presented AND the demonstrator still fully visible in frame - LIGHTING AND EXPOSURE STAY "
            "CONSTANT to the very last frame (owner 2026-09-13: never fade to black / never darken / never "
            "dim the image as the clip ends). The product may be HELD UP to camera OR RESTING "
            "on the surface (either is correct; do not force a grip) "
            "- never end on an empty product-only shot, never drop the person from frame, and never end "
            "on a bare face/bust close-up.\n"
            "- ENDING CAMERA - PULL OUT TO THE FULL PACKSHOT (owner 2026-09-12 v2 - fixes 'ending zoomed IN on "
            "just the held bag'): for a MULTI-ITEM / multi-variant product the last beat MUST be a slow "
            "PULL-BACK / ZOOM-OUT that REVEALS the WHOLE set - ALL packs together side by side - as the final "
            "packshot. NEVER zoom IN on the single item being held at the end. The pull-back is a CAMERA "
            "MOVE ONLY - the image stays fully lit and identical in exposure; it does NOT fade, dim or go "
            "black at any point. The final frame shows the complete product line, labels readable, person "
            "still in frame beside it, at full brightness.\n"
            "- Camera: vertical 9:16 smartphone, STEADY and stable (tripod-like) with at most ONE slow smooth "
            "move (a slow pull-back), crisp focus on the product "
            "while the person stays in frame with it. NEVER handheld wobble, shake, ripple or warp - the frame "
            "must stay rigid and photoreal. BOTH the person and the product are clearly visible in "
            "EVERY beat of the clip - never drop the person OR the product from frame.\n\n"
            "[STYLE - PRODUCT ON TABLETOP - owner 2026-09-12] If the requested UGC style is 'tabletop' (or the \n"
            "   brief asks for the product ON A TABLE), the product MUST be shown RESTING ON A CLEAN FLAT SURFACE \n"
            "   (a tidy table / vanity / counter top) for the still frame, and the shot ALTERNATES between the \n"
            "   product sitting on the surface and the person LIFTING it to present to camera. Rules: (a) the \n"
            "   surface is CLEAN, uncluttered, and matches the setting - a light wood or white tabletop, NO \n"
            "   clutter, NO extra objects beyond the product; (b) the product sits UPRIGHT on the surface, label \n"
            "   facing the lens, occupying a clear hero spot; (c) when the person lifts it, the spot where it sat \n"
            "   stays visibly the SAME surface (continuity), and when returned it goes back to the SAME spot; \n"
            "   (d) the surface must be present and visible in EVERY beat - never let it vanish or morph.\n"
            "   MANDATORY BEAT ORDER for tabletop (owner 2026-09-12 - fixes 'never puts it down'): the FIRST beat "
            "   must OPEN with the product SITTING ON THE SURFACE, untouched, hands away or resting beside it - the "
            "   video starts on a static tabletop hero shot. Only AFTER that may a hand reach in and pick it up. "
            "   Include at least one explicit PLACE-DOWN beat: the hand sets the product back DOWN on the same spot "
            "   and RELEASES it, leaving it resting on the surface (hands away) for the final settle. The clip must "
            "   contain a clear moment where NO hand is holding the product - it is visibly sitting on the table.\n"
            "[SELLING FLOW in thai_script]\n"
            "Write a punchy, easy-to-say Thai voice-over line: relatable pain point or desire -> how the product "
            "fixes it -> a quick believable result -> a soft push to buy/link. \n"
            "HARD LIMIT for this " + str(_dur) + "-second clip: " + str(_char_min) + "-" + str(_char_max) + " Thai characters TOTAL, counted exactly. "
            "FIRM CAP - never exceed " + str(_char_max) + ". A spoken Thai line takes roughly 12-14 chars per second read "
            "aloud, so this budget fills the clip. \n"
            "CRITICAL - FILL THE WHOLE CLIP: the voice-over MUST keep speaking for almost the entire " + str(_dur) + " seconds; "
            "if you write a SHORT script the video model runs out of words and IMPROVISES GIBBERISH for the remaining "
            "seconds (this is the known 'พูดเพี้ยน' bug). Write enough real Thai so there is at most a short 1-2s settle "
            "tail - never leave a long silent/gibberish gap. Do NOT pad with repeated or nonsense words; every word must "
            "be real, sane Thai that carries the sell. \n"
            "NO OVERCLAIM / NO CERTIFICATION WORDS (owner 2026-09-12): the spoken script must NOT contain "
            "certification or endorsement words taken from the product title/metadata - e.g. ฮาลาล (halal), "
            "รับรอง (guarantee), การันตี (warranty), อย. (FDA), มาตรฐาน (standard). The title may say '(มีฮาลาล)' "
            "but the VOICE-OVER must NEVER say it - speak only about real taste, texture, ingredients and how to use. "
            "Never invent a certification the customer did not ask to hear.\n"
            "ONE clear idea. Do NOT list specs or stack unrelated benefits, but DO give the single idea enough natural "
            "spoken detail to comfortably fill the time. If under " + str(_char_min) + " chars, expand the idea with real "
            "product-benefit wording until it reaches the range; if over " + str(_char_max) + " chars, delete the weakest clause.\n"
            "ENDING RULE (owner 2026-09-11 - fixes the CTA tail leak): the LAST word of the script must be a firm "
            "CLOSING word that shuts the sentence closed - end with a closing particle such as 'เลยค่ะ', 'เลยนะคะ', "
            "'นะครับ', 'ไว้เลย', 'เลย' - NEVER end on an open trailing word (a noun, a dangling benefit, a lone 'ค่ะ/นะ' "
            "after a soft word) because the video model then keeps mumbling a garbled tag right after the last word. "
            "Put the buy-push (CTA) in the SECOND-TO-LAST clause, and let the final 2-4 words be a clean closing "
            "phrase that ends the line. The whole script must read as ONE complete sentence that clearly finishes.\n"
            "[SPOKEN-SCRIPT RULES - owner 2026-09-10] The thai_script is READ ALOUD by a Thai TTS/Wan voice, so it \n"
            "must be written exactly how it should be pronounced:\n"
            "  * NEVER use abbreviations or short forms - always write the full spoken word. Examples: 'ชม.' -> \n"
            "    'ชั่วโมง', 'ก.' -> 'กรัม', 'ซ.ม.' -> 'เซนติเมตร', 'ม.ล.' -> 'มิลลิลิตร', 'บ.' -> 'บาท', \n"
            "    '%' -> 'เปอร์เซ็นต์', 'ANC' -> 'เอเอ็นซี'. Abbreviations are read letter-by-letter or wrong.\n"
            "  * Write out English words, brand names, and numbers in Thai phonetic spelling so the voice reads them \n"
            "    naturally (e.g. 'SPF50' -> 'เอสพีเอฟห้าสิบ', 'Vitamin C' -> 'วิตามินซี', '2 แถม 1' -> 'สองแถมหนึ่ง').\n"
            "  * Keep ONLY real Thai words and Thai phonetic spellings. NO Latin letters at all - not even brand \n"
            "    or tech words like Bluetooth, USB, LED, SPF, AAC. Transliterate them: Bluetooth -> บลูทูธ, \n"
            "    USB -> ยูเอสบี, LED -> แอลอีดี, AAC -> เอเอซี, SPF -> เอสพีเอฟ. No numbers, no symbols, \n"
            "    no slashes, no 'x' meaning 'แถม'. Every word must be readable Thai.\n"
            "  * BRAND NAME - MANDATORY: the product's brand name MUST be written in Thai phonetic spelling, \n"
            "    NEVER left as Latin letters. If you leave it in Latin (e.g. 'RUEATHONG'), the voice reads it \n"
            "    letter-by-letter and it comes out WRONG (e.g. 'รูอะทอง'). Spell the actual sound in Thai, e.g. \n"
            "    'RUEATHONG' -> 'เรือทอง', 'JBL' -> 'เจบีแอล', 'Love Angel' -> 'เลิฟแองเจิ้ล'. Use the real \n"
            "    Thai brand name if the product description already gives one.\n"
            "  * CLEAR-ARTICULATION / EASY-TO-PRONOUNCE (owner 2026-09-12 - fixes 'คำพูดเพี้ยน ลิ้นเปลี้ย'): \n"
            "    the script is read aloud fast, so EVERY word must be easy to say clearly in one breath. Obey:\n"
            "    (i) PREFER short common Thai words over long/formal/Pali-Sanskrit compounds - say 'อร่อย' not \n"
            "        'รสชาติอร่อยกลมกล่อม', say 'เข้มข้น' not 'รสสัมผัสอันลึกล้ำ'.\n"
            "    (ii) AVOID hard consonant clusters and tongue-twister pairs, and avoid jamming many long-vowel \n"
            "        words together (e.g. never write 'เส้นหมี่เส้นเล็ก' stuck together - break them with commas).\n"
            "    (iii) LIMIT enumerated lists to AT MOST 3-4 short items separated by commas, and never pile \n"
            "        technical/loan words one after another.\n"
            "    (iv) ADD natural commas (,) between every clause so the voice inserts a small pause - this is \n"
            "        the main fix for 'ลิ้นเปลี้ย': short comma-separated clauses read clean, long unbroken runs \n"
            "        get garbled.\n"
            "    (v) Keep the speakable length inside the char budget so the voice never has to rush - a calmer \n"
            "        pace at the right length always beats cramming extra words in.\n"
            "    (vi) THE VERY FIRST WORD MATTERS MOST (owner 2026-09-12 - fixes 'เพี้ยนตั้งแต่ต้น'): the voice has\n"
            "        no context for word #1, so NEVER open the script with a hard consonant cluster like 'ก๋วยเตี๋ยว' /\n"
            "        'ก๋วยจั๊บ'. Start with an easy, common cluster-free word instead - e.g. open with 'เบื่อ' 'หิว'\n"
            "        'อยาก' 'รส' 'ซอง' 'อร่อย' 'ทำไม' 'ใคร' (NOT 'ก๋วยเตี๋ยว...'). Write 'กวยเตี๋ยว' phonetically if the\n"
            "        word must appear later in the sentence.\n\n"
            "[VIDEO PROMPT - positive direction only - owner 2026-09-10]\n"
            "Think of the video_prompt as one continuous shot that EXTENDS the still frame you already described \n"
            "in image_prompt. Follow these rules:\n"
            "0. MOTION ONLY - NO SPEECH TEXT IN THE VIDEO PROMPT (owner 2026-09-14 - SINGLE SOURCE OF \n"
            "   SPEECH). The Thai voice-over and the instruction to speak are BOTH carried by the timeline \n"
            "   the system appends itself (the 'พูดตาม Thai script...' block). You must therefore NOT write \n"
            "   ANYTHING about speaking, talking, the voice-over, the script, 'mouth moving', facial delivery \n"
            "   or silence inside the video_prompt - not in the opening sentence, not in the action, not in \n"
            "   the closing. Do NOT open with 'She faces the camera and speaks...'. Writing a speech sentence \n"
            "   here DUPLICATES the system directive and makes Wan hallucinate a SECOND speech line (owner: \n"
            "   'บทพูดมี 2 เส้นซ้อนกัน'). Describe MOTION and FRAMING ONLY; keep the face expression natural \n"
            "   but do not name speech.\n"
            "1. CONTINUITY WITH THE IMAGE: keep the exact same subject, wardrobe, product, and setting from your \n"
            "   image_prompt. Start from the pose and framing the image establishes.\n"
            "1b. FASHION LOOK - ONE COHESIVE, MODERN ON-TREND STYLING (owner 2026-09-12 v4 - fixes \"เสื้อนางแบบเชย/แก่, ไม่แฟชั่น, ไม่ไปทางเดียวกัน\"): THIS IS A FASHION BRIEF. The presenter must look like a \n"
            "   stylish Thai creator aged 20-26 who is genuinely INTO fashion - never 'trying to look modern' on top of an \n"
            "   old frame. LOCK ONE single styling direction and carry it through the WHOLE clip: outfit + hair + makeup + \n"
            "   accessories + setting must all belong to the SAME look (\"ไปทางเดียวกัน\"). Choose exactly ONE look board:\n"
            "     * LOOK A 'streetwear Gen-Z': cropped oversized graphic tee or baby tee + wide-leg cargo/parachute trousers, \n"
            "        boxy overshirt worn open, chunky sneakers, claw-clip or slick middle-part hair, glossy lip. Setting: \n"
            "        a trendy cafe-style kitchen counter or loft corner with plants and neon-ish accents.\n"
            "     * LOOK B 'soft-girl aesthetic': fitted ribbed knit top or cropped cardigan in cream/pistachio/lilac, \n"
            "        pleated or flowy midi skirt, delicate thin gold jewellery, soft wavy hair + claw clip, dewy natural \n"
            "        makeup. Setting: bright pastel condo kitchen with soft daylight and small plants.\n"
            "     * LOOK C 'minimal clean-girl': oversized blazer or crisp linen overshirt over a fitted white tank-free \n"
            "        base, wide-leg tailored trousers, sleek straight or low-bun hair, satin-skin makeup, small gold hoops. \n"
            "        Setting: a minimal bright kitchen with stone countertop and one statement vase.\n"
            "   PICK ONE LOOK PER CLIP and stay inside it. NEVER mix eras (no lace blouse + cargo pants). NEVER the \n"
            "   following dated/cheesy choices: plain white tank top or plain sleeveless top, stiff buttoned office blouse, \n"
            "   floral 'auntie' print, ill-fitting classic shirt, old-fashioned cardigan sets, dated denim. The face reads \n"
            "   YOUNG and FRESH (early-to-mid 20s), current hair, current makeup - never middle-aged, tired, or dated.\n"
            "1c. PRESENTER FACES THE CAMERA - NO SPEECH TEXT (owner 2026-09-14, SINGLE SOURCE OF SPEECH): \n"
            "   the presenter LOOKS AT THE CAMERA with a warm, relaxed, believable expression (natural face, \n"
            "   NOT frozen/neutral, NOT exaggerated, eyes OPEN to the lens - never eyes-closed or gazing down). \n"
            "   Do NOT write 'she speaks' / 'her Thai line' / 'mouth moving' / the voice-over / the script \n"
            "   ANYWHERE - the system appends the speech directive itself; naming speech here duplicates it \n"
            "   and Wan invents a second speech line. Never turn her away from the camera.\n"
            "   Her EYES ARE OPEN and directed at the camera lens in the still frame too - never eyes-closed, never \n"
            "   mid-blink, never gazing down at the table.\n"
            "1d. PRODUCTS ARE STATIC OBJECTS - NO SELF-MOVING (MANDATORY - fixes 'ถุงสินค้าขยับเอง'): the packs/\n"
            "   bottles/boxes are INANIMATE. They NEVER move, slide, drift, rotate, float, or reposition on their own. \n"
            "   A pack only moves because a HAND is physically holding and moving it. Whenever a pack is at rest on the \n"
            "   table it stays EXACTLY where it is, perfectly still, until a hand touches it again. NEVER let the product \n"
            "   hover, glide, or animate by itself.\n"
            "1e. PREPARED-FOOD PROP (MANDATORY for food/instant-noodle products - fixes 'ไม่มีรูปก๋วยเตี๋ยวใส่ชามวางไว้'): your \n"
            "   image_prompt MUST include ONE bowl/cup of the PREPARED dish resting on the table beside the packs - appetising, \n"
            "   real, sharp focus, steam optional. It sits STILL on the surface. It is a small secondary prop (~10-20% of the \n"
            "   frame): it NEVER becomes the hero, NEVER dominates the frame, NEVER sits in front of the packs, and NEVER hides \n"
            "   the packs. It is REQUIRED - do NOT omit it. (For non-food products: choose one natural real-world prop that \n"
            "   suits the product and keep it small and static.)\n"
            "2. PHYSICAL GROUNDING: say which hand holds which object and where it touches (fingertip, palm, wrist). \n"
            "   Keep the hands and the product engaged through the whole motion - never let a hand drift off the \n"
            "   product or float unanchored.\n"
            "2b. CUT SCENE - DO NOT SHOW THE FULL PACKAGE-HANDLING (owner 2026-09-13 - decided the\n"
            "   open/use/close loop is too fragile: an over-detailed action makes the video model confused\n"
            "   AND drags the spoken audio off, so DROP the fiddly container mechanics). For ANY product that\n"
            "   comes in a cap/pump/dropper/lid/tube/jar/sachet, do NOT write a long open->squeeze->close->\n"
            "   place sequence. Keep it SIMPLE (owner 2026-09-13).\n"
            "   KEEP IT SIMPLE - NO BEAT LIST (owner 2026-09-13 - fixes 'สั่งเยอะมันมั่ว'): do NOT write a \n"
            "   numbered list of steps or actions. Write ONE short flat description instead (2-3 sentences max) \n"
            "   with a single idea: the presenter HOLDS the product to camera. Nothing else.\n"
            "   THE ACTION IS JUST: HOLD (owner 2026-09-14): she is holding the product in her hand \n"
            "   the whole clip. That is the whole visible action. She does NOT apply it, does NOT open it, \n"
            "   does NOT squeeze it, does NOT set it down - the product simply stays in her hand the entire \n"
            "   time.\n"
            "   DO NOT WRITE ANY SPEECH SIGNAL (owner 2026-09-14, SINGLE SOURCE OF SPEECH): do NOT write \n"
            "   'she speaks' / 'speaks her Thai line' / 'mouth moving' / 'still speaking' ANYWHERE in the \n"
            "   video_prompt - not as an opening sentence, not in the action, not in the closing. The system \n"
            "   appends the single speech directive (the Thai timeline) itself; a second speech sentence here \n"
            "   makes Wan drift and invent an extra line (owner: 'บทพูดมี 2 เส้นซ้อนกัน').\n"
            "   Keep her body and hands CALM and still. Do not describe extra gestures, extra hands, extra \n"
            "   objects, loose product on the surface, or any apply/open/close step.\n"
            "   HARD RULES: EXACTLY TWO hands (rule 6e); nothing floats or vanishes; the product stays in her \n"
            "   hand and visible through to the end.\n"

            "5b. ACTION = ONE SHORT FLAT DESCRIPTION, NO LIST (owner 2026-09-13 - fixes 'สั่งเยอะมันมั่ว'): \n"
            "   describe the single action in ONE short flat sentence or two (max 2-3 sentences). Do NOT write a \n"
            "   numbered list of beats or steps. For a packaged product the action is simply: she HOLDS the \n"
            "   product in her hand, staying calm and still, the product in hand the whole \n"
            "   time. Her free hand stays relaxed and still and holds nothing else (rule 6e - prevents extra hands). \n"
            "   Keep it simple and short - the model follows a short, clean description far better than a long \n"
            "   list of instructions.\n"

            "3. ONE MAIN ACTION ONLY - a single simple action with a clear start, middle, and end. NEVER chain a \n"
            "   sequence of steps (do not show open->pour->stir->lift). One action, described in full physical detail, \n"
            "   every beat grounded. End on a calm, settled beat. The product container stays CLOSED - never \n"
            "   show an open/use/close loop for a packaged product (owner 2026-09-13: apply removed).\n"
            "3b. SET-DOWN IS ALLOWED EXACTLY ONCE (owner 2026-09-13 - fixes 'holding too strong, never puts it \n"
            "   down, hand melts'): the presenter MAY set the product down on the clean surface ONE time as a real \n"
            "   physical beat, and MAY pick ONE pack back up to present. So these TWO beats ARE allowed: \n"
            "   'she sets the product down on the table and releases it' and 'she picks the product back up and \n"
            "   holds it to camera'. What is FORBIDDEN is the set-down + RE-GRAB LOOP: never set down and re-grab \n"
            "   the SAME pack more than once, never release-and-grab-repeatedly. A pack that is released and grabbed \n"
            "   over and over animates and drifts on its own (the bug being fixed). One clean set-down and at most one \n"
            "   re-lift is fine - after that the hand STAYS in contact with the product to the final settle.\n"
            "3b-ii. WEARABLE PRODUCTS (owner 2026-09-13 - fixes 'model wears the jeans and still holds them'): if \n"
            "   the product is WORN/APPLIED (jeans, shirt, dress, jacket, shoes, accessory, jewellery), the model \n"
            "   MUST NOT keep holding it after putting it on. Show the model WEARING the product and let BOTH hands \n"
            "   hang naturally at her sides (or rest on her hip) - NEVER hold the worn garment in her hand. It is \n"
            "   FORBIDDEN to write that she is wearing the garment AND holding the same garment at the same time. A \n"
            "   worn item that is also held in the hand makes the garment vanish/distort on any movement.\n"
            "3c. THAI SCRIPT ONLY - NO LATIN LETTERS, NO CJK, NO FOREIGN SCRIPT (hard rule): the thai_script \n"
            "   must contain ONLY Thai characters (U+0E00-U+0E7F) and spaces/commas. NO English words, NO Latin \n"
            "   letters, and NO CHINESE/JAPANESE/KOREAN characters (no 安心, no 认证, no 漢字 - these have leaked \n"
            "   in before and are read as garbage). Transliterate every borrowed word into Thai spelling \n"
            "   (Texture -> เทกซ์เจอร์, Halal -> ฮาลาล). If a word has no Thai form, DROP it entirely.\n"
            "4. CAMERA AND LIGHT: carry over the camera angle, lens feel, and light source from your image_prompt, \n"
            "   then add ONE subtle camera behaviour. PREFER a slow PULL-BACK / zoom-out that REVEALS the whole \n"
            "   product, or a gentle drift - AVOID ending on a tight close-up of the body (ear, skin, strap). The \n"
            "   whole product must stay clearly visible and PRESENTED to the very end.\n"
            "4a. TIGHT PRODUCT FRAMING - CLOSE, NEVER WIDE (owner 2026-09-13 - fixes 'ภาพกว้างเกินไป'): the \n"
            "   product is the SUBJECT and must DOMINATE the frame - it should fill roughly 40-50% of the frame \n"
            "   height and sit in the lower-to-middle foreground, close to the lens. Compose a MEDIUM CLOSE-UP \n"
            "   at roughly chest/shoulder level - NEVER a wide full-room shot, NEVER a distant full-body shot, \n"
            "   NEVER the person small in the middle of a big empty space. Say explicitly in the video_prompt: \n"
            "   'close medium shot, product fills the lower-to-middle foreground at roughly forty-five percent of \n"
            "   the frame, camera at chest height, person framed from the waist up'. The pull-back in rule 4 is a \n"
            "   SMALL move: write it as 'a very small slow pull-back' / 'a slight pull-back', NEVER a big wide \n"
            "   reveal of the whole room. The product must stay LARGE and close in EVERY beat.\n"
            "4c. SHARP FACE AND PRODUCT - BOTH IN FOCUS (owner 2026-09-13 - fixes 'สินค้าชัด คนเบลอ'): the \n"
            "   demonstrator's FACE must be as sharp and clean as the product - both the product label AND her \n"
            "   face are in crisp focus at the same time (a moderately deep focus plane, NOT a shallow one that \n"
            "   blurs the person). Say explicitly: 'both the product label and the person's face are in sharp, \n"
            "   crisp focus with natural skin detail and clear eyes'. NEVER let the person go soft/blurry while \n"
            "   the product is sharp. Do NOT use the word 'bokeh' or ask for a heavily blurred background.\n"
            "4b. STABILITY - NO WOBBLE / NO WARP (owner 2026-09-12 - fixes 'คลื่นไหว พริ้ว ๆ มั่ว ๆ'): the whole "
            "   shot MUST be STEADY and photoreal. Say explicitly in the video_prompt: 'camera locked and steady, "
            "   smooth slow movement only, no shake, no wobble, stable tripod-like framing'; the person moves "
            "   naturally but SLOWLY with no fast gestures; edges and lines stay straight and rigid (table, packs, "
            "   walls never bend or ripple); face and product labels stay SHARP and undistorted throughout. Never "
            "   ask for 'handheld', 'shaky', 'energetic', 'fast motion', 'quick zoom' or 'whip pan' - those make "
            "   the frame warp and the speech wobble with it. Maximum ONE smooth camera move per clip, performed slowly.\n"
            "5. MUST INCLUDE ALL FOUR DETAIL BLOCKS (this is what makes the shot full and physically sound):\n"
            "   (a) OPENING: the exact starting pose/framing carried over from image_prompt;\n"
            "   (b) MAIN ACTION: the one main action, naming WHICH HAND holds/does WHAT and where it touches;\n"
            "   (c) CAMERA: the single subtle camera behaviour from rule 4;\n"
            "   (d) SETTLE: the final beat settling calmly with the product presented to camera, "
            "the person still in frame, in a calm natural expression (mouth and face NEUTRAL - do NOT "
            "mention talking or speech; the system drives the voice). The framing stays CLOSE and full-lit "
            "to the last frame - never pull out to a wide shot and never fade or dim.\n"
            "   (e) SET-DOWN RULE (owner 2026-09-13 - aligned with holding fix): for the HOLDING style you may write "
            "EXACTLY ONE set-down beat and ONE re-lift ('sets the product down on the table and releases it' \n"
            "then 'picks the product back up and holds it to camera'). After that ONE re-lift, the SAME hand stays \n"
            "in contact with the product through to the settle. NEVER write a SECOND set-down/re-grab (the repeated \n"
            "loop makes the pack glide by itself), and NEVER write a set-down for a WEARABLE product (worn items are \n"
            "worn, not carried). For all other styles keep the same hand in contact from lift to settle.\n"
            "   (f) WORDING: NEVER write the words 'hero shot', 'hero hold', or 'product-only' in the "
            "video_prompt - the model then renders an empty product shot and the PERSON DISAPPEARS from the "
            "frame. Always describe the person and the product TOGETHER in the final beat.\n"
            "6. SCENE FIDELITY (hard rule) - the video_prompt may ONLY contain objects, tools, and setting that \n"
            "   image_prompt ALREADY shows (PLUS the single prepared-food/dish prop from rule 1e for food products). \n"
            "   It is FORBIDDEN to introduce ANY other new object of ANY kind - no kettle, \n"
            "   no chopsticks, no spoon, no extra bowls, no pans, no pots, no boxes, no sachets unless that exact \n"
            "   object is already visible in image_prompt. For FOOD: the dish is ALREADY plated/ready on the \n"
            "   surface - the action is presenting and/or eating the ready dish, NEVER preparing or cooking it. \n"
            "   If you cannot show the action with only the objects already in image_prompt, choose a simpler \n"
            "   action. Count the objects in image_prompt and use ONLY those.\n"
            "   THE KETTLE TRAP (very common): if the script mentions hot water / boiling / cooking, do NOT \n"
            "   invent a kettle, pot, or pouring action. The dish and bowl are ALREADY prepared and on the \n"
            "   table - the person simply PRESENTS and/or EATS the ready dish. NEVER write verbs like \n"
            "   'pours', 'boils', 'adds water', 'cooks', or 'prepares' in the video_prompt, and NEVER a \n"
            "   kettle or pot unless that exact object is already in image_prompt.\n"
            "6b. FOOD REALISM (when the product is food/drink): the dish must look REAL and appetizing - \n"
            "   noodles/strands are crisp and clearly defined, broth glistens, steam is natural. NEVER a \n"
            "   blurry, smeared, mushy, or plastic/CGI look. Say so in the video_prompt (e.g. 'noodles in \n"
            "   sharp natural focus with visible strand texture') and add negatives like 'no blurry noodles, \n"
            "   no smeared mushy food, no fake CGI food, no kettle, no pot, no pouring, no cooking'.\n"
            "6c. JAR / TUB / POT CREAM - DO NOT SCOOP (owner 2026-09-13 - apply removed): the container \n"
            "   stays CLOSED for the whole clip. Do NOT write that she opens the jar, dips a finger in, scoops \n"
            "   cream, or applies it - keep the lid ON and simply HOLD + PRESENT the closed jar to camera \n"
            "   (rule 2b).\n"
            "6d. TUBE / BOTTLE SCALE + NO SQUEEZE (owner 2026-09-13 - apply removed): the product is a normal \n"
            "   handheld size, roughly the length of the person's palm/forearm - NEVER oversized or giant in the \n"
            "   frame (no giant tube filling the shot). Do NOT write that she squeezes/pours/spreads the product \n"
            "   onto skin - the tube/bottle stays CLOSED and is simply HELD and PRESENTED to camera (rule 2b).\n"
            "6e. HAND COUNT - EXACTLY TWO HANDS (owner 2026-09-12 - LYSE extra-hands bug): across the WHOLE clip \n"
            "   show EXACTLY two hands (one left, one right) - never a third hand, never duplicated fingers. If the \n"
            "   product must be held throughout, ONE hand holds it and the OTHER hand does the single action; never \n"
            "   bring in an extra hand to hold. Name explicitly which hand holds the product and which hand acts.\n"
            "6f. EARBUDS / IN-EAR AUDIO - OBJECT PERMANENCE (owner 2026-09-12 - earbud stays-in-ear bug): describe \n"
            "   the earbud state at EVERY step and keep it CONSISTENT. If an earbud is put into an ear, say so; if \n"
            "   it is later taken OUT of the ear and returned to the case, you MUST show it LEAVING the ear first - \n"
            "   an earbud can NEVER be in the ear AND in the case at the same time. Give each earbud a clear state: \n"
            "   in-case -> in-hand -> in-ear -> back-in-hand -> back-in-case, and never skip a step. If the clip \n"
            "   shows one earbud used, say which ear and what the OTHER earbud is doing (still in the case). Never \n"
            "   add an earbud that was not already shown.\n"
            "   PICKUP vs INSERT must be TWO SEPARATE, EXPLICIT BEATS (owner 2026-09-12 - 'khip-insert' glitch): "
            "   do NOT compress 'pick up and put in ear' into one blurred motion. Write beat 1 as the hand "
            "   clearly PINCHING one earbud OUT of the open case (case steady in the other hand, the remaining "
            "   earbud STILL sitting in its case slot), then beat 2 as the earbud traveling to the ear and being "
            "   inserted. State the recipient EAR explicitly ('into her RIGHT ear'). At the instant of pickup the "
            "   case must still hold the second earbud; at the instant of insertion the first earbud must NO LONGER "
            "   be in the case. Never let a single earbud appear in the case and the hand at the same time during "
            "   the handoff - name the hand that holds the case (e.g. left) and the hand that picks and inserts "
            "   (e.g. right), and keep those roles fixed for the whole clip.\n"
            "7. SPEECH - NO SPEECH TEXT IN THE VIDEO PROMPT (owner 2026-09-12 11:3x): the voice-over is \n"
            "   ALREADY written and spoken by the system from thai_script (timeline). The video_prompt must \n"
            "   describe MOTION ONLY. Do NOT mention speech, talking, voice, audio, the script, \"word for \n"
            "   word\", silence, or facial delivery ANYWHERE in the video_prompt, and NEVER write sentences \n"
            "   like \"The person speaks ONLY the given script...\" / \"Audio: speak only...\" / \"silent, \n"
            "   no extra speech\". Owner feedback: repeating speech instructions confuses Wan (the audio model) \n"
            "   -> shaky voice + melting video. Keep the mouth and facial expression NEUTRAL.\n"
            "   Instead, end the video_prompt with a plain ACTION beat (no speech words at all), e.g. \"She \n"
            "   keeps presenting: a small confident smile to camera while holding the product steady and \n"
            "   showing the packs.\" The ONE closing silence directive is appended by the system, not you.\n"
            "[NEGATIVE PROMPT - owner 2026-09-10] The negative_prompt is a list of things the model MUST NOT do.\n"
            "   EVERY item MUST begin with a negative word - \"no ...\" or \"don't ...\". A bare noun\n"
            "   (e.g. \"distorted fingers\") is READ AS AN INSTRUCTION and the model WILL render it. So write\n"
            "   \"no distorted fingers, no extra hands, no warped product, no blurry label, no melted face\".\n"
            "   Keep it comma-separated, ~60-120 chars. Do NOT name ANY language in the negative prompt\n"
            "   (never write a language name) - naming a language seeds random speech; the spoken-\n"
            "   language guard is handled by the script rule instead. Only list visual flaws.\n"
            "   For any product with a cap/dropper/lid/pump, ALSO include these two items so the model does not\n"
            "   improvise the defect: \"no cap floating or inserted at the wrong spot\" and \"no second spot touched, \n"
            "   no double application\".\n"
            "   ALSO include, when relevant, these proven physical-defect negatives (owner 2026-09-12):\n"
            "   tabletop/holding-too-strong: \"no product gripped continuously the whole clip, no hand always "
            "covering the product, no product lifted off the table for the entire shot\";\n"
            "   jar/tub cream: \"no cream on a finger that never touched the jar, no vanishing lid, no floating lid\";\n"
            "   tube/bottle: \"no oversized product, no giant tube, no leftover product blobs, no stringy residue, \n"
            "   no messy uneven application\";\n"
            "   multi-variant set: \"no missing pack, no missing variant, no fewer packs than the real set\";\n"
            "   any held product: \"no third hand, no extra hand, no duplicated fingers, no extra arm\";\n"
            "   earbuds/in-ear: \"no earbud in the ear and in the case at once, no earbud appearing from nowhere, \n"
            "   no product teleporting\".\n"
            "TARGET LENGTH: 60-90 words, ONE paragraph, present tense. NEVER under 60 words - a short prompt \n"
            "drops physical detail and the model invents errors. Cover all four blocks above so the length fills \n"
            "itself. Vivid and specific, grounded in physical detail. Describe what the person DOES in plain \n"
            "positive words - no negative phrasing. Stable, physically-grounded motion reads as sharp and \n"
            "realistic (a busy, unanchored shot reads as blurry).\n\n"
            "[CTA RULE — owner 2026-09-10] NEVER end every script with the same canned line such as "
            "\"\u0e25\u0e2d\u0e07\u0e40\u0e25\u0e22\u0e04\u0e48\u0e30 \u0e21\u0e35\u0e42\u0e04\u0e49\u0e14\u0e25\u0e14\u0e43\u0e19\u0e04\u0e2d\u0e21\u0e40\u0e21\u0e19\u0e15\u0e4c\". Vary the closing EVERY job \u2014 write a fresh, "
            "product-specific CTA each time (e.g. \u0e02\u0e2d\u0e07\u0e2b\u0e21\u0e14\u0e44\u0e27\u0e01\u0e14\u0e40\u0e25\u0e22, \u0e42\u0e1b\u0e23\u0e43\u0e19\u0e15\u0e30\u0e01\u0e23\u0e49\u0e32\u0e23\u0e2d\u0e19\u0e30, \u0e23\u0e31\u0e1a\u0e44\u0e1b\u0e25\u0e2d\u0e07\u0e01\u0e48\u0e2d\u0e19\u0e43\u0e04\u0e23). "
            "Do NOT copy the example closing verbatim.\n"
            "[FREE TO THINK]\n"
            "You are free to decide the best framing, gesture, setting, and word choice for each product from its "
            "real details. Create fresh, lively, on-brand content every time.\n"
            "\nHIGH-VALUE EXAMPLE for beauty (the youngest target uses the product and speaks its real benefit):\n"
            "{\n"
            " \"thai_script\": \"หนูรู้ว่ามือใหม่หัดแต่งหน้าต้องเจอปัญหาครีมกันแดดเป็นคราบ ตัวนี้เนื้อบางเบาเกลี่ยง่าย ผิวไม่ขาววอก กันแดด SPF50 PA++++ ทาแล้วติดทนทั้งวัน ตุนไว้ก่อนของหมด\",\n"
            "}\n"
            "(Your thai_script IS the actual spoken voice-over — write it cleanly. Build image_prompt and video_prompt around the real product so image + motion + script all match.)"
        )
        _acted_instr = ""
        if (special_target or "").strip():
            _acted_instr += "\nACTION REQUIRED from creator: " + str(special_target).strip()
        if (usage_howto or "").strip():
            _acted_instr += "\nHOW the product/model should act/be used in the shot: " + str(usage_howto).strip()
        # Clean messy product text (promo labels / Vietnamese / broken EN) before
        # Mimo sees it — owner 2026-09-09 (Teashell: "9.9 SALE [Hot] ... ฟื้นบarier").
        # owner 2026-09-11 (C): use the combined helper so title+desc are cleaned with
        # the SAME rules as the router choke point — never send the raw title when desc is empty.
        try:
            from product.text_clean import clean_product_text
            _name_clean, _desc_clean = clean_product_text(
                product_name or "", description or ""
            )
        except Exception:
            _name_clean, _desc_clean = str(product_name or ""), str(description or "")
        # owner 2026-09-12 (plan A): the REAL structured features (variant list / noodle types /
        # flavours / spice levels / specs). This is what Mimo must use to name variants in the
        # script. Kept separate from Description so it is not buried inside a prose paragraph.
        _features_clean = str(features or "").strip()
        # owner 2026-09-12: styles that MUST change hand behaviour. A buried sysprompt rule
        # was ignored by Mimo, so hoist the requirement into the user_text (high attention).
        _style_instr = ""
        _style_lc = (ugc_style or "").strip().lower()
        # owner 2026-09-14 (fixes vid_66ebdc39 pants-placed-on-floor / vid_3f3ebb8b):
        # DETECT WEARABLE APPAREL FIRST. If the product is clothing/shoes/accessory the
        # selected positional style (holding/tabletop) must NOT apply - those styles force
        # the product to be laid down on a surface ("RESTING ON A CLEAN SURFACE ... NO hand
        # is holding it" / "sets the product down on the table and releases it"), which is
        # exactly what made the denim pants render flat on the floor and then drift when Wan
        # had to "put them on". Apparel is worn, never placed.
        _cat_lc = str(category or "").strip().lower()
        _sub_lc = str(subcategory or "").strip().lower()
        _name_lc = _name_clean.lower()
        # Garment/shoe subcategory tokens (NOT bags - a bag is legitimately held, not worn).
        _wearable_tokens = ("clothing", "garment", "apparel", "shirt", "blouse", "hoodie",
                            "sweater", "jacket", "coat", "jeans", "trousers", "pants",
                            "skirt", "dress", "top", "shoes", "shoe", "sneaker", "boots",
                            "sandal", "wearable")
        # Thai + EN garment words in the product name (fallback when subcategory is empty).
        _wearable_name = ("เสื้อ", "กางเกง", "แจ็คเก็ต", "แจ็กเก็ต", "แจ็คเก็ท", "เดรส", "กระโปรง",
                          "รองเท้า", "กางเกงยีนส์", "แขนยาว", "ฮู้ด", "ฮู้ดดี้",
                          "jacket", "jeans", "trousers", "shirt", "dress", "skirt", "pants",
                          "hoodie", "sweater", "blouse")
        _is_wearable = (any(_t in _sub_lc for _t in _wearable_tokens) or
                        any(_t in _name_lc for _t in _wearable_name))
        if _is_wearable:
            _style_instr = (
                "\n\n*** STYLE = WEARABLE APPAREL (HIGHEST PRIORITY, OVERRIDES HOLDING/TABLETOP) ***\n"
                "This product is a GARMENT/WEARABLE (clothing, shoes, or accessory). It is NEVER placed flat "
                "on a table/floor and NEVER simply held up as a loose object - the model WEARS it and shows the "
                "fit. This OVERRIDES any holding/tabletop instruction:\n"
                "  * image_prompt: the model is ALREADY WEARING the garment in the still frame. Frame torso-to-"
                "knee (or a full-body mirror view) so the cut, silhouette, colour and drape dominate - never an "
                "extreme face close-up, never the garment lying on a surface as the hero.\n"
                "  * video_prompt: the model WEARS the item the WHOLE clip and shows it off with gentle natural "
                "turns, small soft steps and fabric movement. BOTH hands are relaxed at her sides (or one hand "
                "rests on the hip) - she does NOT hold, lay down, lift, or carry the worn garment at any point.\n"
                "  * NEVER write 'resting on a clean surface', 'sets the product down on the table', 'picks it "
                "back up', or any place-down/re-lift beat for a wearable. There is NO tabletop hero shot.\n"
                "  * It is FORBIDDEN to show the model both WEARING the garment AND holding the same garment - a "
                "worn item that is also carried makes the garment vanish/distort on movement.\n"
            )
        elif _style_lc in ("holding", "holding_demo", "handheld"):
            # owner 2026-09-12: HOIST the holding behaviour into user_text (Mimo ignores the
            # buried sysprompt rule). 'Holding' must NOT mean a death-grip for the whole clip.
            _style_instr = (
                "\n\n*** STYLE = HOLDING (HIGHEST PRIORITY, MUST OBEY) ***\n"
                "The demonstrator presents the product by HOLDING it up at chest level, upright, label facing "
                "the lens, for the MAIN part of the clip. 'Holding' is the DEFAULT for this style.\n"
                "BUT the clip must NOT read as one rigid grip from the first frame to the last (owner 2026-09-12: "
                "fixes 'Holding too strong, never puts it down'). The video_prompt MUST contain BOTH of these "
                "literal phrases, each describing a real beat:\n"
                "  (1) 'sets the product down on the table and releases it' - one beat where the hand puts the "
                "product back on a clean surface and lets go;\n"
                "  (2) 'picks the product back up and holds it to camera' - then she lifts it again to present.\n"
                "Preserve this release-then-re-lift beat. The hand must look relaxed and real, never frozen "
                "gripping the product for all 15 seconds. The product stays clearly visible and centred in every "
                "beat whether held or resting. Do NOT describe the product as held by BOTH hands at chest level "
                "for the entire clip. After the ONE re-lift, the hand KEEPS contact with the product to the end "
                "- do not set it down and re-grab a second time (that loop makes the pack drift on its own).\n"
                "*** WEARABLE PRODUCT (owner 2026-09-13 - fixes 'model wears the jeans and still holds them', "
                "*** garment vanishes on movement) ***: if the product is WORN/APPLIED (jeans, trousers, shirt, "
                "dress, jacket, shoes, accessory, jewellery), the model puts it ON and then her BOTH hands hang "
                "naturally at her sides (or one hand rests on her hip) - she MUST NOT hold the worn garment in "
                "her hand. It is FORBIDDEN to write that she is wearing the garment AND holding the same garment "
                "at the same time; a worn item that is also held makes the garment vanish/distort on movement. "
                "Present a wearable by wearing it and moving naturally, not by carrying it.\n"
                "*** IMAGE / FIRST FRAME (owner 2026-09-12 - fixes 'the still frame shows her gripping it'): The "
                "image_prompt must describe a STILL frame in which the product is RESTING ON A CLEAN SURFACE "
                "(table/vanity/counter), sitting upright with the label facing the lens, and NO hand is holding it "
                "- the demonstrator's hands are relaxed beside it (or she is standing beside it). Do NOT write an "
                "image_prompt where she is holding the jar at chest level. The still frame is the tabletop hero "
                "shot; the hand only comes in to lift the product during the VIDEO beats."
            )
        elif _style_lc in ("tabletop", "tabletop_demo", "demo"):
            _style_instr = (
                "\n\n*** STYLE = TABLETOP (HIGHEST PRIORITY, MUST OBEY) ***\n"
                "The product must be RESTING ON A CLEAN FLAT TABLE/COUNTER for a real part of the clip - "
                "NOT held the whole time. Build the shot so that:\n"
                "  * The video OPENS with the product sitting alone on the table, no hand touching it.\n"
                "  * A hand then PICKs IT UP to present to camera for the middle.\n"
                "  * Near the end the hand SETS IT BACK DOWN on the same spot and RELEASES it, leaving it "
                "resting on the table for the final settle - hands away.\n"
                "The video_prompt MUST contain the words 'sitting on the table', 'sets it back down', and "
                "'leaves it resting' - and at least one beat where NO hand holds the product. "
                "Do NOT write a video_prompt where the product is gripped from start to finish."
            )
        # owner 2026-09-12: when MORE THAN ONE product image is supplied, the product is a
        # multi-variant set (flavours/colours/noodle types). HOIST this into user_text at high
        # attention - Mimo otherwise collapses the set to the single image[0] colour (the
        # "only one colour shown, other variants never mentioned" bug).
        _variant_instr = ""
        _n_imgs = len([u for u in (product_images or []) if isinstance(u, str) and u.strip()])
        if _n_imgs > 1:
            _variant_instr = (
                "\n\n*** MULTI-VARIANT SET (HIGHEST PRIORITY, MUST OBEY) ***\n"
                f"You are given {_n_imgs} reference images of the SAME product line - these are the DIFFERENT "
                "variants (flavours / colours / scents / noodle types). Look at ALL of them.\n"
                "Rules:\n"
                "  (1) The image_prompt MUST show MORE THAN ONE variant TOGETHER - the differently-coloured "
                "packs/bottles standing side by side on the surface, each label readable, as the hero group. "
                "Do NOT describe a single pack/colour only.\n"
                "  (2) In the thai_script, NAME at least two real variants actually shown in the images "
                "(e.g. the different noodle types / flavours / scents). Never mention variants not visible "
                "or not in the product data.\n"
                "  (3) The negative_prompt MUST include 'no single colour only, no missing variants'.\n"
            )
        # owner 2026-09-12 (plan A): surface the structured features as their own high-attention
        # line. Mimo must NAME these real features/variants in the script (fixes "Mimo never
        # mentions the flavours/spice levels even though the data exists").
        _feat_instr = ""
        if _features_clean:
            _feat_instr = (
                "\nProduct features (REAL, use these EXACTLY - never invent others): " + _features_clean + "\n"
                "*** FEATURE-DRIVEN SCRIPT (HIGHEST PRIORITY, MUST OBEY) ***\n"
                "The 'Product features' line above is authoritative. The thai_script MUST explicitly name the "
                "REAL variants/options/flavours/specs listed there (e.g. the actual noodle types / flavours / "
                "spice levels), not a generic subset and not invented ones. If it lists several variants, name "
                "at least three distinct ones. Also include any listed spice/heat range or key spec."
            )
        user_text = ("Product: " + _name_clean + "\nDescription: " + _desc_clean + _feat_instr +
                     _acted_instr + _style_instr + _variant_instr +
                     "\nWrite natural-realistic image and video prompts for this product. Base the visuals ONLY on the given "
                     "Product/Description — never invent brand names, logos, label text, ingredients, quantities, prices, or packaging "
                     "details not present. IMPORTANT: if a product image is provided, draw the product exactly as it appears "
                     "in that image — real color, real shape, sharp unblurred label — never generic and never blurred. Only if there is "
                     "no product image AND no useful description may you describe plain generic packaging with a soft-blurred/blank label. "
                     "Use real, lived-in settings and believable, natural faces. "
                     "Keep the shot in a real place, the face relaxed and true to life.")
        for _prov in _providers:
            # owner 2026-09-11: send the REAL product image to Mimo (vision) so it reads the
            # exact form factor/shape instead of guessing from the title (over-ear vs in-ear bug).
            _user_content = user_text
            # owner 2026-09-12: send ALL variant images (multi-flavour/colour) so Mimo can read
            # the full set (e.g. red/yellow/blue noodle packs) instead of only image[0].
            _imgs_raw = [u.strip() for u in (product_images or []) if isinstance(u, str) and u.strip()]
            if not _imgs_raw and (product_image or "").strip():
                _imgs_raw = [product_image.strip()]
            # owner 2026-09-13: Mimo only accepts http(s)/base64/data URLs. TUS products store
            # RELATIVE public paths ('/ugc/static/product_images/x.webp'), which Mimo rejects with
            # 'the provided url is not valid' -> hard failure. Normalize each ref (relative local
            # file -> base64 data URL); drop refs that cannot be normalized.
            _imgs_to_send = []
            for _u in _imgs_raw:
                _norm = _mimo_image_ref(_u)
                if _norm:
                    _imgs_to_send.append(_norm)
                else:
                    logger.warning(f"_deepseek_product_prompts: dropped unusable image ref: {_u[:80]}")
            # owner 2026-09-12: Mimo's media fetch is INTERMITTENT ("failed to download or process
            # media content" on some images / when too many are sent). Degrade gracefully:
            # try ALL images -> FIRST image only -> NO image, so the job never dies on vision.
            _image_sets = []
            if _imgs_to_send:
                _image_sets.append(_imgs_to_send[:6])
                if len(_imgs_to_send) > 1:
                    _image_sets.append(_imgs_to_send[:1])
            _image_sets.append([])  # last resort: text-only
            payload = {
                "model": _prov["model"],
                "messages": [{"role": "system", "content": sysprompt},
                              {"role": "user", "content": _user_content}],
                "max_tokens": _prov["max_tokens"],
                "temperature": 0.4,
            }
            headers = {"Content-Type": "application/json", "Authorization": "Bearer " + _prov["key"]}
            url = _prov["url"]
            for _istep, _iset in enumerate(_image_sets):
                if _iset:
                    _user_content = [{"type": "text", "text": user_text}]
                    for _u in _iset:
                        _user_content.append({"type": "image_url", "image_url": {"url": _u}})
                else:
                    _user_content = user_text
                payload["messages"] = [{"role": "system", "content": sysprompt},
                                       {"role": "user", "content": _user_content}]
                _media_fail = False
                for _attempt in range(3):
                    try:
                        _res = requests.post(url, headers=headers, json=payload, timeout=200)
                        if _res.status_code == 200:
                            _data = _res.json()
                            _content = ((_data["choices"][0]["message"].get("content") or "").strip() or "")
                            if not _content:
                                logger.warning(f"_deepseek_product_prompts [{_prov['name']}] empty content, retry")
                                continue
                            import re as _re
                            _obj = _extract_json_obj(_content)
                            # Accept either video_prompt (str) or video_prompts (list[str])
                            _vid = _obj.get("video_prompt")
                            _vid = _vid.strip() if isinstance(_vid, str) else ""
                            _prompts = _obj.get("video_prompts")
                            if not _vid and isinstance(_prompts, list) and _prompts and isinstance(_prompts[0], str):
                                _vid = _prompts[0].strip()
                            _img = _obj.get("image_prompt")
                            _img = _img.strip() if isinstance(_img, str) else ""
                            # owner 2026-09-12: Mimo may pick which supplied reference image to use
                            # (multi-variant sets -> the image showing the most packs together).
                            _ref_idx = _obj.get("reference_image_index")
                            try:
                                _ref_idx = int(_ref_idx) if _ref_idx is not None else None
                            except Exception:
                                _ref_idx = None
                            _tst = _obj.get("thai_script")
                            _tst = _tst.strip() if isinstance(_tst, str) else ""
                            _neg = _obj.get("negative_prompt")
                            _neg = _neg.strip() if isinstance(_neg, str) else ""
                            _neg = _normalize_negative_prompt(_neg)
                            # owner 2026-09-11: structured beats (Fix C) — timed script so Wan knows
                            # where the speech ends and the silent settle tail begins.
                            _beats = _normalize_script_beats(_obj.get("script_beats"))
                            if _tst:
                                # Normalize: Thai ตัวอักษร, ตัด wrap/quotes, ตัดเครื่องหมายคำพูดซ้ำที่อาจหลุดมา
                                _tst = _re.sub(r"[\u201c\u201d\"']+", "", _tst).strip()
                            if _img and _vid:
                                # (ข) owner 2026-09-09 23:0x: คืน thai_script ที่ Mimo เขียนด้วย (เดิมโดนทิ้ง) →
                                # ใช้เป็นตัวพูดจริง ให้คนเดียว author บท+ภาพ+วิดีโอ sync กัน (แก้ APPEND 15 conflict)
                                logger.info(f"_deepseek_product_prompts: got AI prompts from {_prov['name']} "
                                            f"({_prov['model']}, img {len(_img)}ch, vid {len(_vid)}ch, script {len(_tst)}ch, beats {len(_beats)})")
                                return {"image_prompt": _img, "video_prompt": _vid, "thai_script": _tst,
                                        "negative_prompt": _neg, "script_beats": _beats,
                                        "reference_image_index": _ref_idx}
                            logger.warning(f"_deepseek_product_prompts [{_prov['name']}] JSON missing image/video keys (img={bool(_img)}, vid={bool(_vid)})")
                            break
                        else:
                            logger.warning(f"_deepseek_product_prompts [{_prov['name']}] api {_res.status_code}: {_res.text[:150]}")
                            # media-download / bad-url 400 => drop images and retry with fewer/none
                            _low = _res.text.lower()
                            if _res.status_code == 400 and _iset and (
                                    "media" in _low or "url is not valid" in _low or "not valid" in _low
                                    or "unsupported" in _low or "download" in _low):
                                _media_fail = True
                            break
                    except Exception as _e:
                        logger.warning(f"_deepseek_product_prompts [{_prov['name']}] attempt {_attempt + 1} error: {_e}")
                if _media_fail:
                    logger.warning(f"_deepseek_product_prompts [{_prov['name']}] media fetch failed with {len(_iset)} image(s) - degrading")
                    continue
        return None
    except Exception as _e:
        logger.warning(f"_deepseek_product_prompts failed: {_e}")
        return None

