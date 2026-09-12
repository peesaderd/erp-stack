"""
TikTok UGC Studio - Affiliate Video Pipeline v6 (Structure-based)
================================================================
Pipeline: Analyze → Recipe → Script → Image Prompt → Image → Video Prompts → TTS → Video → Compose

Flow (9 Steps ตาม PIPELINE_STRUCTURE.md):
  Step 1: Product → Analyze (Mistral) → product_profile
  Step 2: Load Recipe → scenes structure
  Step 3: product_profile + recipe → Script (modules/video/script_gen.py)
  Step 4: product_profile + recipe → Image Prompt (prompt-builder-service)
  Step 5: image_prompt + product_image → Generate Image (Prodia Nano Banana)
  Step 6: product_profile + recipe + image → Video Prompts (prompt-builder-service)
  Step 7: script → TTS (Gemini)
  Step 8: image + video_prompts → Wan 2.7 → Video
  Step 9: Video + Voice + BGM → FFmpeg → Final

Cost Estimate:
  - 8s (Nano Banana + Gemini TTS + Wan 2.7): ~$0.038
  - 16s (2 scenes): ~$0.068

Changes from v5:
  - เพิ่ม Analyze step (Mistral)
  - เพิ่ม Recipe loading
  - เปลี่ยน Script generation จาก manual → Gemini
  - เปลี่ยน Image prompt จาก manual → Mistral
  - เพิ่ม Video prompts จาก recipe + image
  - ลบ endpoint calls ที่ถูกลบ
"""

import os
import re
import sys
import json
import time
import uuid
import logging
import random
import re
import subprocess
import shutil
import asyncio
from pathlib import Path
from typing import Optional, List, Dict, Any

import requests

def get_bgm_path(bgm_style: str) -> Path:
    """Helper to resolve BGM path from style name.

    The actual BGM mp3 files live in the TUS studio dir (tiktok-ugc-studio/bgm),
    NOT in modules/video/storage/sounds (which is empty). Map styles to the real
    filenames that exist there.
    """
    bgm_map = {
        "chill_loft": "kontraa_water.mp3",   # no bg_chill.mp3 — reuse upbeat_02
        "informative_jazz": "bg_jazz.mp3",
        "energetic_edm": "bg_edm.mp3",
        "upbeat_pop": "kontraa_water.mp3",
        "luxury_jazz": "bg_jazz.mp3",
        "asmr": "kontraa_water.mp3",          # no bg_ambient.mp3 — fallback
    }
    bgm_filename = bgm_map.get(bgm_style, "kontraa_water.mp3")
    # BGM lives in the TUS studio dir: erp-stack/tiktok-ugc-studio/bgm
    # (pipeline_affiliate.py is at erp-stack/modules/video/ -> up 3 = erp-stack)
    repo_root = Path(__file__).resolve().parent.parent.parent
    tus_studio_bgm = repo_root / "tiktok-ugc-studio" / "bgm"
    return tus_studio_bgm / bgm_filename

# Add erp-stack to path for shared_config
_erp_stack = Path(__file__).parent.parent.parent
if str(_erp_stack) not in sys.path:
    sys.path.insert(0, str(_erp_stack))

from shared_config import PRODIA_TOKEN, GEMINI_API_KEY

# ─── Schema Engine UGC Style Client ─────────────────────────────────
_ugc_client_dir = os.path.join(str(_erp_stack), "prompt-builder-service")
if _ugc_client_dir not in sys.path:
    sys.path.insert(0, _ugc_client_dir)
from ugc_schema_client import get_default_style, get_style_config, validate_ugc_style, is_valid_style

# Import pipeline logger (same directory)
from pipeline_logger import start_job, update_step, update_cost, complete_job, fail_job, update_prompts

logger = logging.getLogger("tiktok-ugc.pipeline_affiliate")

# ─── Config ────────────────────────────────────────────────────────────────

STORAGE_DIR = Path(__file__).parent / "storage"
TMP_DIR = STORAGE_DIR / "tmp"
TMP_DIR.mkdir(parents=True, exist_ok=True)

# Service URLs
IMAGE_GEN_URL = "http://localhost:8110/api/v1/image/generate"
PROMPT_BUILDER_URL = "http://localhost:8117"



def download_file(url: str, output_path: Path) -> Path:
    """Download from URL to local path."""
    if os.path.exists(url):
        shutil.copy2(url, output_path)
        return output_path
    resp = requests.get(url, stream=True, timeout=60)
    resp.raise_for_status()
    with open(output_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)
    return output_path


def concat_videos(video_paths: list, output_path: Path) -> Path:
    """Concat multiple videos with FFmpeg. Skip None entries."""
    valid_paths = [vp for vp in video_paths if vp is not None]

    if not valid_paths:
        raise RuntimeError("No valid videos to concat (all None)")

    if len(valid_paths) == 1:
        shutil.copy2(valid_paths[0], output_path)
        return output_path

    list_file = TMP_DIR / f"concat_{uuid.uuid4().hex}.txt"
    with open(list_file, "w") as f:
        for vp in valid_paths:
            f.write(f"file '{Path(vp).absolute()}'\n")
    cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
           "-i", str(list_file), "-c", "copy", str(output_path)]
    subprocess.run(cmd, check=True, capture_output=True)
    list_file.unlink(missing_ok=True)
    return output_path


# ═══════════════════════════════════════════════════════════════════════════
# STEP 1: Analyze Product (Mistral)
# ═══════════════════════════════════════════════════════════════════════════

def _extract_json_obj(_content: str):
    """Robustly pull a JSON object from an LLM reply that may contain prose / markdown fences
    / extra nested braces. Tries, in order: direct whole-string parse, ```json ... ``` fence,
    then a balanced outer-brace slice (tracks depth so prose braces don't truncate the object)."""
    import re as _re
    _content = (_content or "").strip()
    # 1) direct
    try:
        _o = json.loads(_content)
        if isinstance(_o, dict):
            return _o
    except Exception:
        pass
    # 2) fenced ```json ... ```
    _m = _re.search(r"```(?:json)?\s*([\s\S]*?)```", _content, _re.IGNORECASE)
    if _m:
        try:
            _o = json.loads(_m.group(1).strip())
            if isinstance(_o, dict):
                return _o
        except Exception:
            pass
    # 3) balanced outer braces: find first '{', then depth-scan for the matching final '}'
    _i = _content.find("{")
    while _i != -1:
        _depth = 0
        _in_str = False
        _esc = False
        for _j in range(_i, len(_content)):
            _ch = _content[_j]
            if _in_str:
                if _esc:
                    _esc = False
                elif _ch == "\\":
                    _esc = True
                elif _ch == '"':
                    _in_str = False
                continue
            if _ch == '"':
                _in_str = True
            elif _ch == "{":
                _depth += 1
            elif _ch == "}":
                _depth -= 1
                if _depth == 0:
                    _cand = _content[_i:_j + 1]
                    try:
                        _o = json.loads(_cand)
                        if isinstance(_o, dict):
                            return _o
                    except Exception:
                        pass
                    break
        _i = _content.find("{", _i + 1)
    return {}


# ═══════════════════════════════════════════════════════════════════════════
# Thai spoken-script safeguard (owner 2026-09-10)
# Wan reads thai_script ALOUD (Voice mode A) — abbreviations get mis-read
# (e.g. "ชม." -> "ชม" not "ชั่วโมง"). Normalize before the script reaches Wan.
# ═══════════════════════════════════════════════════════════════════════════
_THAI_ABBR = [
    (r"ชม\.", "ชั่วโมง"), (r"ชั่วโมง\.", "ชั่วโมง"),
    (r"ม\.ล\.", "มิลลิลิตร"), (r"ซ\.ม\.", "เซนติเมตร"),
    (r"ก\.ก\.", "กิโลกรัม"), (r"ก\.", "กรัม"),
    (r"บ\.", "บาท"), (r"น\.", "นาฬิกา"),
    (r"นาที\.", "นาที"), (r"วินาที\.", "วินาที"),
]
_THAI_SYM = [("%", "เปอร์เซ็นต์")]
# owner 2026-09-12: hard consonant clusters at the START of a clip come out garbled by Wan
# (real bug: "เบื่อก๋วยเตี๋ยว..." at pos-1 decoded as "Buer cuitit..." = the กล-ว cluster is
# unreadable with no preceding context). Fix the worst offenders phonetically + never OPEN the
# script with them. "ก๋วยเตี๋ยว" -> "กวยเตี๋ยว" reads cleanly.
_THAI_CLUSTER_FIX = [
    (r"ก๋วยเตี๋ยว", "กวยเตี๋ยว"),
    (r"ก๋วยจั๊บ", "กวยจับ"),
]
# Hard clusters that must NOT be the very first content word of the spoken script.
_THAI_HARD_OPENER = ("ก๋วย", "กวยเตี๋ยว", "ก๋วยเตี๋ยว", "ก๋วยจั๊บ")
# Latin tech/brand words that commonly slip through -> Thai phonetic spelling.
_THAI_LATIN = {
    "bluetooth": "บลูทูธ", "usb": "ยูเอสบี", "led": "แอลอีดี", "aac": "เอเอซี",
    "spf": "เอสพีเอฟ", "anc": "เอเอ็นซี", "hdmi": "เอชดีเอ็มไอ", "wifi": "ไวไฟ",
    "wi-fi": "ไวไฟ", "gps": "จีพีเอส", "type-c": "ไทป์ซี", "type c": "ไทป์ซี",
}

def normalize_thai_spoken_script(text: str) -> str:
    """Convert abbreviations + stray symbols in a Thai spoken script to full,
    pronounceable Thai words so the voice model reads them correctly."""
    if not text:
        return text
    out = text
    # owner 2026-09-12: phonetic fix for hard opening clusters (ก๋วยเตี๋ยว -> กวยเตี๋ยว) BEFORE
    # anything else, so the very first word Wan speaks is pronounceable.
    for pat, rep in _THAI_CLUSTER_FIX:
        out = re.sub(pat, rep, out)
    for pat, rep in _THAI_ABBR:
        out = re.sub(pat, rep, out)
    for sym, rep in _THAI_SYM:
        out = out.replace(sym, " " + rep + " ")
    # transliterate known Latin tech/brand words (case-insensitive, word-ish boundary)
    for lat, rep in _THAI_LATIN.items():
        out = re.sub(r"(?<![A-Za-z])" + re.escape(lat) + r"(?![A-Za-z])", rep, out, flags=re.IGNORECASE)
    # separate any remaining Latin/digit run glued to Thai (e.g. "น้อยBluetooth" handled above;
    # this inserts a space so leftover Latin never fuses into a Thai word)
    out = re.sub(r"([\u0E00-\u0E7F])([A-Za-z0-9])", r"\1 \2", out)
    out = re.sub(r"([A-Za-z0-9])([\u0E00-\u0E7F])", r"\1 \2", out)
    # tidy double spaces created by replacements
    out = re.sub(r"[ \t]{2,}", " ", out).strip()
    # owner 2026-09-12 (fixes 'เพี้ยนตั้งแต่ต้น'): the voice has NO context for word #1, so a hard
    # consonant cluster there comes out garbled (verified: 'เบื่อก๋วยเตี๋ยว...' at pos-1).
    # Deterministic guard - if the script OPENS with a hard cluster, keep the rest but re-open with
    # an easy common word derived from the sentence so the first syllable reads cleanly.
    try:
        # owner 2026-09-12 (rewritten): the voice garbles its FIRST syllable when a hard cluster
        # (กวยเตี๋ยว / กวยจั๊บ) sits within the opening words. Real bug 'ใครที่เบื่อกวยเตี๋ยว...' had the
        # cluster at pos ~9 - the old pos-1-only check missed it. New rule: if a hard cluster appears
        # inside the FIRST TWO whitespace-words, re-open the line with an easy hook ("หิวใช่ไหม")
        # followed by the (phonetic) noun, then the rest of the sentence with the cluster removed from
        # its leading position. Safe no-op when the opening is already clean.
        _CLUSTERS = ("กวยเตี๋ยว", "กวยจับ", "ก๋วยเตี๋ยว", "ก๋วยจั๊บ")
        _first2 = " ".join(out.split()[:2])
        _hit = next((_c for _c in _CLUSTERS if _c in _first2), None)
        # already opens with the easy hook -> nothing to do
        if _hit and not out.startswith("หิวใช่ไหม"):
            _noun = "กวยเตี๋ยว" if "เตี๋ยว" in _hit else "กวยจับ"
            # drop the FIRST cluster occurrence from the opening, then trim the leading filler
            # ("ใครที่เบื่อ" / "เบื่อ" / "อยากกิน" ...) so the sentence re-opens cleanly.
            _rest = out.replace(_hit, " ", 1)
            _rest = re.sub(r"^(?:ใครที่|ใคร|และ|ที่|ก็)?\s*(?:เบื่อ|ชอบ|อยาก|หิว|รสดี|กิน)?\s*", "", _rest, count=1)
            _rest = re.sub(r"^กิน\s*", "", _rest, count=1)
            _rest = re.sub(r"\s{2,}", " ", _rest).strip(" ,")
            if _rest:
                out = ("หิวใช่ไหม " + _noun + " " + _rest).strip()
    except Exception:
        pass
    return out


def _deepseek_key() -> str:
    """Resolve DeepSeek API key: env DEEPSEEK_API_KEY first, then openclaw.json."""
    k = os.environ.get("DEEPSEEK_API_KEY", "") or ""
    if not k:
        try:
            _p = os.path.expanduser("/home/openhands/.openclaw/openclaw.json")
            if os.path.exists(_p):
                _cfg = json.load(open(_p))
                k = _cfg.get("models", {}).get("providers", {}).get("deepseek", {}).get("apiKey") or ""
        except Exception:
            k = ""
    return k


def _mimo_key() -> str:
    """Resolve Mimo (xiaomi) API key.

    Order (2026-09-10 fix): os.environ -> shared_config .env files -> openclaw.json.
    openclaw.json is root-only (0600) so module services running as `openhands`
    cannot read it; the key must live in a readable .env (erp-stack/.env) or env.
    """
    k = os.environ.get("MIMO_API_KEY", "") or ""
    if not k:
        try:
            from shared_config import _env_dict  # type: ignore
            k = (_env_dict or {}).get("MIMO_API_KEY", "") or ""
        except Exception:
            k = ""
    if not k:
        try:
            _p = os.path.expanduser("/home/openhands/.openclaw/openclaw.json")
            if os.path.exists(_p):
                _cfg = json.load(open(_p))
                k = _cfg.get("models", {}).get("providers", {}).get("xiaomi", {}).get("apiKey") or ""
        except Exception:
            k = ""
    return k


def _hue_diverse_reference_index(images: list) -> Optional[int]:
    """owner 2026-09-12 (colour fidelity): deterministic fallback when Mimo vision can't pick.
    Downloads the candidate images and returns the index of the one with the MOST distinct
    saturated hues (the multi-colour GROUP SHOT), so the still frame reproduces the whole
    coloured line instead of one repeated single-colour pack. Returns None if unsure.
    """
    try:
        from PIL import Image
        import colorsys
        import io as _io
        _urls = [u for u in images if isinstance(u, str) and u.strip()][:6]
        if len(_urls) < 2:
            return None
        _scores = []
        for _u in _urls:
            try:
                _r = requests.get(_u, timeout=20)
                if _r.status_code != 200 or not _r.content:
                    _scores.append(-1)
                    continue
                _im = Image.open(_io.BytesIO(_r.content)).convert("RGB").resize((16, 16))
                _hues = set()
                for (_rr, _gg, _bb) in list(_im.getdata()):
                    _h, _s, _v = colorsys.rgb_to_hsv(_rr / 255, _gg / 255, _bb / 255)
                    if _s > 0.35 and _v > 0.25:
                        _hues.add(int(_h * 12))
                _scores.append(len(_hues))
            except Exception:
                _scores.append(-1)
        if not _scores or max(_scores) < 0:
            return None
        _best = max(range(len(_scores)), key=lambda _i: _scores[_i])
        # only trust it when the winner is meaningfully MORE colourful than the runner-up
        _sorted = sorted(_scores, reverse=True)
        if len(_sorted) > 1 and _sorted[0] < _sorted[1] + 2:
            return None
        return _best
    except Exception:
        return None


def _pick_variant_reference_index(images: list) -> Optional[int]:
    """owner 2026-09-12: for a multi-variant product set, ask Mimo (vision) which supplied
    reference image shows the MOST variants/packs together, so the still frame can show the
    full colour/flavour line instead of only image[0]. Returns an int index or None.
    """
    try:
        _k = _mimo_key()
        if not _k:
            return None
        _imgs = [u for u in images if isinstance(u, str) and u.strip()][:6]
        if len(_imgs) < 2:
            return None
        _content = [{"type": "text", "text": (
            f"There are {len(_imgs)} reference images of the SAME product line. Which single "
            "image shows the MOST packs/variants TOGETHER in one photo? "
            "Answer with ONLY the 0-based index number (0, 1, 2, ...)."
        )}]
        for _u in _imgs:
            _content.append({"type": "image_url", "image_url": {"url": _u}})
        _payload = {"model": "mimo-v2.5",
                    "messages": [{"role": "user", "content": _content}],
                    "max_tokens": 400, "temperature": 0.3}
        _r = requests.post("https://token-plan-sgp.xiaomimimo.com/v1/chat/completions",
                           headers={"Authorization": "Bearer " + _k, "Content-Type": "application/json"},
                           json=_payload, timeout=60)
        if _r.status_code != 200:
            return None
        _c = (_r.json()["choices"][0]["message"].get("content") or "").strip()
        import re as _re
        _m = _re.search(r"\d+", _c)
        if not _m:
            return _hue_diverse_reference_index(_imgs)
        _idx = int(_m.group(0))
        return _idx if 0 <= _idx < len(_imgs) else _hue_diverse_reference_index(_imgs)
    except Exception:
        try:
            return _hue_diverse_reference_index(images)
        except Exception:
            return None


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
            _char_min, _char_max = 175, 200
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
            " \"video_prompt\": \"<ONE continuous shot, ONE simple action + settle, grounded in physical detail, 60-90 words>\"\n"
            " \"negative_prompt\": \"<comma-separated list where EVERY item MUST start with a negative word - 'no ...' or 'don't ...'. ~60-120 chars. Example: no distorted fingers, no extra hands, no warped product, no blurry label, no melted face>\"\n"
            "}\n\n"
            "[SCRIPT_BEATS - owner 2026-09-11] You MUST also return \"script_beats\": an ordered array that splits "
            "the spoken script into timed beats. Rules: (a) labels are exactly hook, value, cta, settle in that order; "
            "(b) the seconds of hook+value+cta+settle must add up to ~" + str(_dur) + " total; (c) the cta beat MUST end on a "
            "firm closing particle (เลยค่ะ / เลยนะคะ / นะครับ / ไว้เลย / เลย); (d) the final \"settle\" beat has EMPTY text "
            "and holds the last 1-2 seconds - it is deliberate SILENCE where the person keeps presenting the product on "
            "camera but says nothing; (e) the concatenation hook+value+cta (ignoring settle) must equal thai_script exactly "
            "(same words, same order). This timed structure tells the video model exactly when the speech ends so it does "
            "not improvise a garbled tag into the silent tail.\n\n"
            "[TARGET AUDIENCE & CREATOR]\n"
            "- Choose the youngest age in the target demographic (e.g. 25-35: use 25).\n"
            "- Creator: an attractive, youthful, believable Thai person matching the product audience - fresh "
            "glowing skin, pleasant, natural, relatable. Default: Thai female, mid-20s.\n"
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
            "Product in sharp focus, background slightly softer.\n"
            "- SCREEN SHARE: the product must occupy roughly 30-40% of the frame and stay in the "
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
            "COUNT-ALL-PACKS (owner 2026-09-12 v3 - fixes 'asked for 4 packs, the still rendered only 3'): the still "
            "   frame MUST show EVERY pack of the set, not a subset. When the data lists N variants you MUST place all N "
            "   packs in the frame - COUNT them literally in the prompt ('exactly four packs: 1 red, 2 brown/yellow, 3 blue, "
            "   4 green - ALL FOUR visible, none missing'). ARRANGE them so every pack is visible at once - a neat row "
            "   side by side is fine, but you may ALSO LEAN some packs back against others, STACK one on top of another, "
            "   or fan them out like a hand of cards; slight overlap is OK as long as every pack stays identifiable. "
            "   The bowl of prepared food (if used) is a SMALL secondary prop beside the packs - it must NEVER cover or "
            "   push a pack out of frame. Do NOT show only 3 of 4 packs, do NOT let packs merge into one blob, do NOT "
            "   hide a pack behind another.\n"
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
            "- APPLIED (skincare/cosmetics): show a natural, correct application gesture on the right area, or hold "
            "the product cleanly at chest level facing the lens.\n"
            "- THE ENDING BEAT: the final 2-3 seconds must settle calmly with the product clearly presented "
            "AND the demonstrator still fully visible in frame - the product may be HELD UP to camera OR RESTING "
            "on the surface (either is correct; do not force a grip) "
            "- never end on an empty product-only shot, never drop the person from frame, and never end "
            "on a bare face/bust close-up.\n"
            "- ENDING CAMERA - PULL OUT TO THE FULL PACKSHOT (owner 2026-09-12 v2 - fixes 'ending zoomed IN on "
            "just the held bag'): for a MULTI-ITEM / multi-variant product the last beat MUST be a slow "
            "PULL-BACK / ZOOM-OUT that REVEALS the WHOLE set - ALL packs together side by side - as the final "
            "packshot. NEVER zoom IN on the single item being held at the end. The final frame shows the "
            "complete product line, labels readable, person still in frame beside it.\n"
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
            "in image_prompt. Follow these five rules:\n"
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
            "1c. PRESENTER ACTUALLY SPEAKS (MANDATORY - fixes 'นางแบบไม่พูด'): the presenter MUST be shown TALKING \n"
            "   TO CAMERA - mouth visibly moving, mouth-articulation throughout the shot, looking into the lens with \n"
            "   a natural warm expression. She is delivering the Thai sales script to the viewer the whole time. Never \n"
            "   render her silent, still-lipped, smiling-but-not-speaking, turned away, or looking down at the product.\n"
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
            "2b. CONTAINER HANDOFF LOOP (MANDATORY for any product with a cap, dropper, lid, pump, or sachet - \n"
            "   serum, cream, oil, lotion, tube, spray, food sachet): the part that opens and the part that closes are \n"
            "   ONE indivisible loop of the SAME single action - this is NOT the forbidden chaining of rule 3. \n"
            "   You MUST describe this loop in full, in this exact physical order, or the model improvises a broken \n"
            "   cap and a stray second touch:\n"
            "   (i) before the action, name WHICH hand holds the bottle/body and WHICH hand holds the cap/dropper;\n"
            "   (ii) the open: that cap-hand lifts the cap/dropper off and KEEPS HOLDING IT for the whole beat - \n"
            "        the cap/dropper NEVER leaves that hand and NEVER touches the skin or the face;\n"
            "   (iii) the use: the body-hand applies the product to ONE named spot (e.g. left cheek) - ONCE only;\n"
            "   (iv) the close: the same cap-hand puts the cap/dropper straight back onto the bottle body and it \n"
            "        sits closed and upright; then that hand holds the closed bottle with the other hand supporting it.\n"
            "   HARD RULES for this loop: apply to exactly ONE spot - NEVER touch, spread to, or re-dab a second spot \n"
            "   (no left cheek AND right cheek). The cap/dropper hand NEVER wanders to the face. The product is \n"
            "   CLOSED again before the settle beat - never leave the bottle open or the dropper lying loose.\n"
            "3. ONE MAIN ACTION ONLY - a single simple action with a clear start, middle, and end. NEVER chain a \n"
            "   sequence of steps (do not show open->pour->stir->lift). One action, described in full physical detail, \n"
            "   every beat grounded. End on a calm, settled beat. (Exception: the 2b container open/use/close loop is \n"
            "   part of the one action - keep it, it is required.)\n"
            "3b. NEVER SET DOWN + RE-GRAB (hard rule - owner 2026-09-12, fixes 'the pack moves by itself'): once the \n"
            "   presenter picks the product up, that hand STAYS in contact with it all the way to the final settle. It \n"
            "   is FORBIDDEN to write 'she sets it down', 'she releases it', 'she lets go', 'she puts it back', or \n"
            "   'she picks it up again'. If you want a two-product beat, KEEP THE FIRST PACK IN HER HAND and have her \n"
            "   bring the second pack up with her OTHER hand - never release and re-grab. A released pack animates and \n"
            "   drifts on its own (the exact bug being fixed).\n"
            "3c. THAI SCRIPT ONLY - NO LATIN LETTERS, NO CJK, NO FOREIGN SCRIPT (hard rule): the thai_script \n"
            "   must contain ONLY Thai characters (U+0E00-U+0E7F) and spaces/commas. NO English words, NO Latin \n"
            "   letters, and NO CHINESE/JAPANESE/KOREAN characters (no 安心, no 认证, no 漢字 - these have leaked \n"
            "   in before and are read as garbage). Transliterate every borrowed word into Thai spelling \n"
            "   (Texture -> เทกซ์เจอร์, Halal -> ฮาลาล). If a word has no Thai form, DROP it entirely.\n"
            "4. CAMERA AND LIGHT: carry over the camera angle, lens feel, and light source from your image_prompt, \n"
            "   then add ONE subtle camera behaviour. PREFER a slow PULL-BACK / zoom-out that REVEALS the whole \n"
            "   product, or a gentle drift - AVOID ending on a tight close-up of the body (ear, skin, strap). The \n"
            "   whole product must stay clearly visible and PRESENTED to the very end.\n"
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
            "the person still in frame, STILL TALKING to the lens.\n"
            "   (f) NO SET-DOWN/RE-PICK CHAIN (owner 2026-09-12 - fixes 'ถุงสินค้าขยับเอง', see rule 3b): NEVER write "
            "the presenter setting the product down, releasing it, or picking it back up. Keep the SAME hand in "
            "contact with each pack from the moment it is lifted through to the settle - the pack is never left to "
            "rest-and-then-re-grab, or it will glide by itself.\n"
            "   (g) WORDING: NEVER write the words 'hero shot', 'hero hold', or 'product-only' in the "
            "video_prompt - the model then renders an empty product shot and the PERSON DISAPPEARS from the "
            "frame. Always describe the person and the product TOGETHER in the final beat.\n"
            "6b. FOOD REALISM (when the product is food/drink): the dish must look REAL and appetizing - \n"
            "   noodles/strands are crisp and clearly defined, broth glistens, steam is natural. NEVER a \n"
            "   blurry, smeared, mushy, or plastic/CGI look. Say so in the video_prompt (e.g. 'noodles in \n"
            "   sharp natural focus with visible strand texture') and add negatives like 'no blurry noodles, \n"
            "   no smeared mushy food, no fake CGI food, no kettle, no pot, no pouring, no cooking'.\n"
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
            "6c. JAR / TUB / POT CREAM - SCOOP ANCHOR (owner 2026-09-12 - MYSO jar bug): if the product is a \n"
            "   cream in a jar/tub/pot, the fingertip MUST physically reach INTO the jar opening and touch the \n"
            "   cream surface before any cream can appear. NEVER let cream appear on a finger that never entered \n"
            "   the jar (the 'finger dabs but never reaches the jar yet has cream' bug). Describe: the fingertip \n"
            "   dips down past the jar rim, contacts the cream, scoops a small blob, then lifts OUT of the jar. \n"
            "   Apply the blob to ONE named spot ONCE. If a lid was removed, that same lid is EITHER held in the \n"
            "   other hand for the WHOLE clip (never vanishes mid-shot) OR set down flat on the surface and never \n"
            "   re-picked - pick ONE and keep it consistent to the end; the lid must NEVER disappear or float.\n"
            "6d. TUBE / BOTTLE SCALE + CLEAN WIPE (owner 2026-09-12 - SUN tube bug): the product is a normal \n"
            "   handheld size, roughly the length of the person's palm/forearm - NEVER oversized or giant in the \n"
            "   frame (no giant tube filling the shot). When product is squeezed/poured onto skin and then spread, \n"
            "   the spreading hand SMOOTHS the product fully into the skin - the skin ends EVEN and clean with NO \n"
            "   leftover blobs, strings, drips, or dabs of product. Say 'she smooths it in completely until the skin \n"
            "   is even with no leftover residue'.\n"
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
            "7b. HANDS - SIMPLE, ANATOMICAL, SMALL IN FRAME (owner 2026-09-12 11:5x): Wan melts/merges\n"
            "   hands when the prompt gives a hand two jobs at once or shoves the hand large into frame.\n"
            "   RULES: (i) at most ONE hand acts at a time; never two hands doing different things at once.\n"
            "   (ii) describe the grip POSITIVELY and anatomically - write the exact words: \"her hand holds\n"
            "   the pack with five clearly separated fingers, a visible thumb on the front edge, relaxed\n"
            "   knuckles, natural skin\". (iii) keep the hand SMALL in the frame - the pack is the hero, the\n"
            "   hand only supports it from the lower edge; never a close-up of the hand. (iv) the other hand\n"
            "   stays out of frame or still at her side. (v) NEVER say a hand grips the product AND rests on\n"
            "   the bowl/table simultaneously. One clear action per beat.\n"
            "[NEGATIVE PROMPT - owner 2026-09-10] The negative_prompt is a list of things the model MUST NOT do.\n"
            "   EVERY item MUST begin with a negative word - \"no ...\" or \"don't ...\". A bare noun\n"
            "   (e.g. \"distorted fingers\") is READ AS AN INSTRUCTION and the model WILL render it. So write\n"
            "   \"no distorted fingers, no extra hands, no warped product, no blurry label, no melted face\".\n"
            "   Keep it comma-separated, ~60-120 chars. Do NOT name any language in the negative prompt\n"
            "   (never write \"Vietnamese\" or any language) - it seeds random speech; the spoken-\n"
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
        if _style_lc in ("holding", "holding_demo", "handheld"):
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
                "for the entire clip.\n"
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
            _imgs_to_send = [u.strip() for u in (product_images or []) if isinstance(u, str) and u.strip()]
            if not _imgs_to_send and (product_image or "").strip():
                _imgs_to_send = [product_image.strip()]
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
                            # media-download 400 => drop images and retry with fewer/none
                            if _res.status_code == 400 and "media" in _res.text.lower() and _iset:
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
    for _lbl, _txt in (("hook", _hook), ("value", _value), ("cta", _cta)):
        if not _txt:
            continue
        _secs = max(1, round(_spoken_total * len(_txt) / max(1, len(_hook) + len(_value) + len(_cta))))
        _beats.append({"label": _lbl, "seconds": _secs, "text": _txt})
    if _beats:
        _beats.append({"label": "settle", "seconds": max(1, _dur - sum(b["seconds"] for b in _beats)), "text": ""})
    return _beats


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


def _sanitize_video_prompt(vp: str) -> str:
    """Owner 2026-09-12: strip the set-down / release / re-grab chain that makes the product
    animate by itself in Wan. Rewrites those clauses into a 'keeps holding it' beat.

    The LLM sysprompt forbids this (rule 3b) but Mimo drifts back to the pattern, so we also
    hard-clean the string here as belt-and-suspenders.
    """
    if not vp:
        return vp
    import re as _re
    out = vp
    # Owner 2026-09-12 (v2 tail fix): "ตอนท้ายเพี้ยน" came from a PARTIAL strip - we removed the
    # set-down sentence but LEFT the orphaned "Then she picks the pack back up ..." sentence right
    # after it, so Wan saw a re-grab with no set-down and improvised a physical break/garble at the
    # tail. Strip the WHOLE handoff chain in one pass (set-down/release/place-down + the orphaned
    # re-grab that follows) while KEEPING the legitimate first pick-up that comes before the set-down.
    cleaned = out
    # Strategy: find the FIRST set-down/release/put-back in the text. Everything from that point up to
    # the end of the FOLLOWING re-grab clause is the forbidden handoff chain - remove it in one shot,
    # but KEEP the legitimate first pick-up/hold that comes BEFORE the set-down.
    _chain = _re.compile(
        r"(?<=[.]\s)"  # start right after a sentence end (so we don't clip mid-sentence)
        r"[^.]*?\b(sets? (?:the |it |the product |the pack )?(?:product|pack|item|it)?\s*(?:back )?down|"
        r"set (?:it|the product|the pack) down|releases? (?:it|the product|the pack)|lets go of (?:it|the product|the pack)|"
        r"puts? (?:it|the product|the pack) back|places? (?:it|the product|the pack) (?:back )?on|"
        r"picks? (?:the product|the pack|it) (?:back )?up again)[^.]*\."
        r"(?:\s*(?:Then|After(?:wards| that| a brief pause)?|Next|Finally|Later|Subsequently|Again)?\s*,?\s*"
        r"(?:she|he|they|the (?:presenter|woman|man|model|person))?\s*"
        r"(?:picks?|picks? up|lifts?|lifts? up|grabs?|takes?)\s*"
        r"(?:the (?:same |red |blue |yellow |green |brown )?(?:product|pack|item)|it)?\s*"
        r"(?:back up|back|up again|again)?[^.]*\.)?",  # optional trailing re-grab (may be absent)
        _re.IGNORECASE,
    )
    cleaned = _chain.sub("", out)
    # Owner 2026-09-12 (second pass): a DANGLING re-grab can survive with no set-down before it
    # (Mimo emits "Beat 3: she picks the product back up ..." on its own). Wan then performs a
    # phantom second lift + adds an extra pack + extra speech at the tail. Strip any standalone
    # 'picks it back up / picks up again / lifts it again' sentence unconditionally.
    _regrab_only = _re.compile(
        r"(?<=[.]\s)"
        r"(?:Beat\s*\d+\s*:?\s*)?"
        r"(?:(?:she|he|they|the (?:presenter|woman|man|model|person))\s+)?"
        r"(?:picks?|lifts?|grabs?|takes?)\s+"
        r"(?:the |it |the (?:same |red |blue |yellow |orange |brown |gold )?(?:product|pack|item))?\s*"
        r"(?:back\s?up|back\s+up|up again|again)\b[^.]*\.",
        _re.IGNORECASE,
    )
    cleaned = _regrab_only.sub("", cleaned)
    # Owner 2026-09-12: 'revealing all four packs' triggers Wan to DRAW extra packs when the camera
    # pulls back. Replace with a count-preserving phrasing.
    cleaned = _re.sub(r"revealing all (?:four|4) packs", "the same packs remain on the table, unchanged, no new pack appears", cleaned, flags=_re.IGNORECASE)
    cleaned = _re.sub(r"revealing all (\w+) packs", r"the same packs remain on the table, unchanged, no new pack appears", cleaned, flags=_re.IGNORECASE)
    # Collapse any doubled spaces / stray ' .'
    cleaned = _re.sub(r"\s{2,}", " ", cleaned).replace(" .", ".").strip()
    # Guard: if the strip nuked too much, keep the original (safety).
    return cleaned if len(cleaned) > len(out) * 0.5 else out


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
            _beats = _ds.get("script_beats") or []
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
                _food_sig = any(k in (_cat_lc + " " + (product_name or "").lower()) for k in (
                    "food", "snack", "noodle", "drink", "beverage", "ก๋วยเตี๋ยว", "instant",
                    "บะหมี่", "มาม่า", "เครื่องดื่ม", "ขนม", "กาแฟ", "ชา", "นม", "เรือ",
                ))
                if _food_sig:
                    # owner 2026-09-12 (neg<=500): lean, VOICE-FREE negative list.
                    # (a) ALL speech/voice items REMOVED - we never instruct voice, so there is
                    #     nothing to counter-instruct (owner: "ถ้าเราไม่สั่ง voice ก็ไม่เสี่ยง").
                    # (b) no count-locking phrases (they contradict the story action -> model
                    #     materialises packs). Only neutral state guards remain.
                    # (c) keep it short so the combined negative stays well under Prodia's 500 cap.
                    _food_neg = ("no merged fingers, no melted hand, no extra hands, no third hand, "
                                 "no warped product, no blurry label, no melted face, "
                                 "no blurry noodles, no smeared mushy food, no fake CGI food, "
                                 "no multiple bowls, no self-moving product, no pack floating, "
                                 "no new pack added, no invented colour pack, no green pack, "
                                 "no camera wobble, no frame warp")
                    # owner 2026-09-12 12:0x: put the food safety guards FIRST so that when the
                    # 480ch cap trims from the END, it drops Mimo's lower-priority filler items -
                    # never our hand-anatomy / pack-colour / wobble safeguards.
                    _mimo_neg = _normalize_negative_prompt(_food_neg + ", " + _mimo_neg)
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
                    try:
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
# STEP 2: Load Recipe
# ═══════════════════════════════════════════════════════════════════════════

def load_recipe(recipe_name: str = "tus") -> dict:
    """
    Step 2: Load recipe → scenes structure

    Query จาก Schema Engine (services/schema-engine) เท่านั้น
    ถ้า Schema Engine ไม่ตอบ หรือ recipe ไม่มี → throw error ทันที
    (ไม่มี filesystem fallback เพื่อให้รู้ทันเมื่อ Schema Engine พัง)

    Args:
        recipe_name: ชื่อ recipe (tus_novoice_15s, tus_15s, etc.)

    Returns:
        dict: recipe { name, total_duration, image_generation, video_generation, tts, ... }
    """
    logger.info(f"Step 2/9: Load recipe ({recipe_name})")

    schema_url = os.environ.get("SCHEMA_ENGINE_URL", "http://localhost:8100")
    try:
        resp = requests.get(
            f"{schema_url}/api/v1/data/video_recipe",
            params={"search": recipe_name, "limit": 1},
            timeout=3,
        )
        
        if resp.status_code != 200:
            raise RuntimeError(f"Schema Engine returned {resp.status_code}: {resp.text[:200]}")

        data = resp.json()
        records = data.get("data", [])
        if not records:
            raise RuntimeError(f"Recipe '{recipe_name}' not found in Schema Engine (video_recipe schema)")
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
        logger.warning(f"Schema Engine unreachable ({e}) — using default recipe")
        # Fallback: return a default recipe with standard scenes
        default_recipe = {
            "name": recipe_name,
            "description": "Default recipe (Schema Engine offline)",
            "version": "1.0",
            "total_duration": 15,
            "language": "th",
            "default_style": "holding",
            "scenes": [
                {"name": "hook", "duration": 5, "function": "hook"},
                {"name": "value", "duration": 5, "function": "value"},
                {"name": "cta", "duration": 5, "function": "cta"},
            ],
            "video_model": "wan2.7",
            "video_count": 1,
            "ugc_styles": ["holding", "review", "usage", "talking"],
            "voice_tone": "friendly, authentic, enthusiastic",
            "target_audience": "Thai TikTok users",
            "image_generation": {},
            "video_generation": {},
            "tts": {"enabled": True},
        }
        logger.info(f"  Recipe (default fallback): {recipe_name}, {len(default_recipe['scenes'])} scenes, {default_recipe['total_duration']}s")
        return default_recipe

    record = records[0]
    row = record.get("data", record)
    # Schema Engine stores with double nesting: data.data.config
    inner = row.get("data", row) if isinstance(row, dict) and "config" not in row else row
    config = inner.get("config", row.get("config", {}))

    # Use `inner` for recipe-level fields (unwrap double-nesting)
    recipe = {
        "name": inner.get("name", recipe_name),
        "description": inner.get("description", ""),
        "version": inner.get("version", "1.0"),
        "total_duration": inner.get("total_duration", 15),
        "language": inner.get("language", "th"),
        "default_style": inner.get("default_style", "holding"),
        "scenes": config.get("scenes", []),
        "video_model": config.get("video_model", "wan2.7"),
        "video_count": config.get("video_count", 1),
        "ugc_styles": config.get("ugc_styles", ["holding", "review", "usage", "talking"]),
        "voice_tone": config.get("voice_tone", "friendly, authentic, enthusiastic"),
        "target_audience": config.get("target_audience", "Thai TikTok users"),
        "image_generation": config.get("image_generation", {}),
        "video_generation": config.get("video_generation", {}),
        "tts": config.get("tts"),  # None = no voiceover
    }

    scenes = recipe.get("scenes", [])
    logger.info(f"  Recipe (Schema Engine): {recipe_name}, {len(scenes)} scenes, {recipe.get('total_duration')}s")
    return recipe


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


# ═══════════════════════════════════════════════════════════════════════════
# STEP 4: Build Image Prompt (Mistral)
# ═══════════════════════════════════════════════════════════════════════════

def build_image_prompt(
    product_name: str,
    product_profile: dict,
    recipe: dict,
) -> str:
    """
    Step 4: Build image prompt via Mistral

    Args:
        product_name: ชื่อสินค้า
        product_profile: ผลจาก analyze_product()
        recipe: ผลจาก load_recipe()

    Returns:
        str: image_prompt
    """
    logger.info(f"Step 4/9: Build image prompt (Mistral)")

    # ใช้ image_prompt ที่ได้จาก analyze_product() (Step 1)
    image_prompt = product_profile.get("_image_prompt", "")

    if image_prompt:
        logger.info(f"  Image prompt: {image_prompt[:60]}...")
        return image_prompt

    # NO hardcoded fallback — image prompt must come from prompt-builder (JSON).
    # Breaking loudly beats silently generating with a generic hardcoded prompt.
    raise ValueError(
        "build_image_prompt: '_image_prompt' missing from product_profile — "
        "prompt-builder (JSON-driven) must supply it; refusing hardcoded fallback"
    )


# ═══════════════════════════════════════════════════════════════════════════
# STEP 5: Generate Image (Prodia Nano Banana)
# ═══════════════════════════════════════════════════════════════════════════

def generate_image(
    prompt: str,
    product_image: str = None,
    aspect_ratio: str = "9:16",
    model: str = "nano-banana",
    placement: str = "hold",
) -> tuple:
    """
    Step 5: Generate image via Prodia.

    Args:
        prompt: image_prompt จาก Step 4
        product_image: URL ของรูปสินค้า (reference)
        aspect_ratio: 9:16 (TikTok portrait — owner direction, always 9:16)
        model: "nano-banana" (default) or "flux-2-klein" (klein 4B img2img)
        placement: "hold" | "place" | "place_and_hold" — hold-vs-place (owner 2026-09-12)

    Returns:
        tuple: (image_url, cost_usd)
    """
    logger.info(f"Step 5/9: Generate image ({model}, {aspect_ratio}, placement={placement})")
    logger.info(f"  Prompt: {prompt[:40]}...")
    logger.info(f"  Reference: {product_image or 'None'}")

    payload = {
        "prompt": prompt,
        "count": 1,
        "upscale": False,
        "aspectRatio": aspect_ratio,
        "model": model,
        "placement": placement,
    }

    if product_image:
        # 8110 (image-module) request schema: inputImage + model + style.
        payload["inputImage"] = product_image
        payload["style"] = "thai_realistic"

    last_exc = None
    for attempt in range(3):
        try:
            resp = requests.post(IMAGE_GEN_URL, json=payload, timeout=300)
            resp.raise_for_status()
            data = resp.json()

            if not (data.get("success") or data.get("ok")) or not data.get("images"):
                raise RuntimeError(f"Image-gen service failed: {data}")

            img_info = data["images"][0]
            url = img_info.get("full_url") or img_info.get("url")

            if not url:
                raise RuntimeError(f"No URL in response: {data}")

            # Extract cost from image service response (real pricing from prodia_pricing)
            cost_data = data.get("cost", {}) or img_info.get("cost", {})
            cost_usd = float(cost_data.get("dollars", 0.039) if isinstance(cost_data, dict) else 0.039)

            logger.info(f"  Image OK: {url[:60]}... | cost=${cost_usd:.4f}")
            return url, cost_usd

        except Exception as e:
            last_exc = e
            logger.warning(f"  Image gen attempt {attempt+1}/3 failed: {e}")
            if attempt < 2:
                logger.info(f"  Retrying image gen...")
                import time
                time.sleep(2)

    logger.error(f"Image generation failed after 3 attempts: {last_exc}")
    raise RuntimeError(f"Image generation failed after 3 attempts: {last_exc}")


# ═══════════════════════════════════════════════════════════════════════════
# STEP 5b: Generate Last (end-scene) image via FLUX.2 [klein] 4B
# Separate pipeline (NOT PassportPhoto). Takes the Nano Banana first-frame as
# input → produces a fresh 9:16 end-scene (Last) image from the SSOT blueprint.
# ═══════════════════════════════════════════════════════════════════════════

def _build_klein_last_prompt(profile: dict, product_name: str) -> str:
    """Build a 9:16 END-scene prompt for FLUX klein — LOCK-SCENE pattern.

    Owner direction (2026-08-24 15:21): the Last frame must stay in the SAME
    scene as the Nano Banana first frame (same woman / clothes / room) and
    change ONLY the pose: product goes from "held toward camera" → "placed
    down on the table, label facing camera" so Wan FL2V interpolates a
    natural put-down motion.
    Per owner-approved klein lesson (2026-08-23): do NOT re-describe
    outfit/scene/camera — klein 4B drifts when over-described. Only
    expression/result_focus still come from the SSOT end_scene blueprint.
    """
    es = (profile or {}).get("_end_scene")
    if not isinstance(es, dict):
        # fallback to a clean pick (binding happens in build_video_prompt normally)
        try:
            from prompt_builder import _pick_end_scene  # type: ignore
            cat = (profile or {}).get("category", "other")
            sub = (profile or {}).get("subcategory", "")
            es = _pick_end_scene(cat, subcategory=sub, profile=profile) or {}
        except Exception:
            es = {}

    gender = "woman" if (profile or {}).get("target_gender") == "female" else "man"
    _expr = es.get("expression") or "a relaxed, content smile"

    return (
        f"Vertical 9:16 portrait. The exact same {gender} as in the input image: keep her "
        f"face, hairstyle, makeup, clothes and the entire room/background EXACTLY identical "
        f"to the input image — do not redesign anything about her or the scene. "
        f"The product from the input image MUST remain clearly visible in this frame "
        f"too — same jar/product, same size and colors as the input image. "
        f"Only a subtle expression change: she continues holding the product steady\n"
        f"toward the camera in the exact same pose, same framing, same hand position —\n"
        f"product facing the camera, crisp and unclipped, label visible. No putting down,\n"
        f"no hand release, no pose change. "
        f"Lighting identical to the input image. Full-frame 9:16, no border, no padding."
    )


def generate_klein_last_image(
    first_frame_local: str,
    profile: dict,
    product_name: str = "",
    aspect_ratio: str = "9:16",
    run_id: str = ""
) -> tuple:
    """Generate the Last (end-scene) image via FLUX.2 [klein] 4B img2img.

    Uses the Nano Banana first-frame as input + the SSOT end-scene prompt.
    Our own klein pipeline (separate from PassportPhoto).

    Returns:
        tuple: (local_path, cost_usd)
    """
    logger.info(f"  ▶ Generate Last image via FLUX.2 klein 4B (from first-frame)")
    prompt = _build_klein_last_prompt(profile, product_name)

    # Send the local first-frame as a self-contained data URL so the image-module
    # can read it without depending on a served URL.
    try:
        import base64 as _b64
        with open(first_frame_local, "rb") as f:
            b64 = _b64.b64encode(f.read()).decode()
        input_ref = f"data:image/png;base64,{b64}"
    except Exception as e:
        logger.warning(f"  ⚠️ ใช้ path ตรงๆ แทน data URL ({e})")
        input_ref = first_frame_local

    img_url, cost_last = generate_image(
        prompt, input_ref, aspect_ratio=aspect_ratio, model="flux-2-klein",
    )
    last_path = TMP_DIR / f"klein_last_{run_id or 'x'}.png"
    download_file(img_url, last_path)
    logger.info(f"  ▶ Klein Last OK: {last_path.name} | cost=${cost_last:.4f}")
    return last_path, cost_last


# ═══════════════════════════════════════════════════════════════════════════
# STEP 6: Build Video Prompts (Mistral)
# ═══════════════════════════════════════════════════════════════════════════

def _clean_product_name_for_video(product_name: str) -> str:
    """Return generic 'product' for video prompts.
    
    Wan 2.7 may interpret product names as instructions.
    The reference image already shows the actual product.
    """
    return "product"


# STEP 7: REMOVED — Gemini TTS stripped from TUS entirely (owner 2026-08-24).
# Voice = Wan 2.7 speaks thai_script directly (Voice mode A only).
# No Gemini TTS generation, no lip-sync audio, no voiceover merge.
# Prevents future Voice mode A/B confusion (owner directive).

# ═══════════════════════════════════════════════════════════════
# STEP 8: Generate Video (Prodia Wan 2.7 Sync API)
# ═══════════════════════════════════════════════════════════════════════════

# ── Shared Prodia v2 Async Client ──
from prodia_client import ProdiaV2Client, ProdiaV2Error, ProdiaValidationError




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
            f"(คำสุดท้ายคือ '{_last_word_hint}')\n"
            "พูดภาษาไทยชัดถ้อยชัดคำ ออกเสียงครบทุกพยางค์ วรรณยุกต์ถูกต้อง จังหวะหายใจเป็นธรรมชาติ "
            "ภาพนิ่งมั่นคง ไม่สั่น ไม่ไหว (steady shot, no wobble)"
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
                "อ่านครบทุกคำจนจบช่วงสุดท้าย แล้วปิดปาก เงียบสนิท\n"
                "พูดภาษาไทยชัดถ้อยชัดคำ ออกเสียงครบทุกพยางค์ วรรณยุกต์ถูกต้อง จังหวะหายใจเป็นธรรมชาติ"
            )
            logger.info(f"  🎙 Fix C beats: {len(_beats)} beats, spoken~{_spoken_secs}s + settle")
        # 🔴 owner 2026-09-11 00:54: Wan พูดแทรกก่อน CTA และหลัง CTA.
        # owner: "ใส่ไปใน video prompt ว่าให้พูดตาม Script" — Wan อ่าน video_prompt เป็นท่อนสุดท้าย
        # จึงต้องมีคำสั่ง speech-lock ปิดท้าย "หลัง" motion block ด้วย (ท่อนสุดท้ายที่ Wan เห็น)
        # owner 2026-09-12 11:3x: Pete - "เราบอกแค่พูด Thai script แหล่ะ ... อย่าไปเน้นซ้ำซ้อน
        # พร่ำเพรื่อ กลายเป็น Wan งง เสียงสั่น + video ละลาย". The speech instruction already lives
        # in _stop_rule; a second full speech-lock tail = duplicated ordering -> Wan gets confused.
        # Keep ONE short English closing directive only: keep silence after the script ends.
        _speech_tail = (
            "\n\nKeep silence after script end — after the last Thai word, stay completely "
            "silent for the ending scene (still present the product on camera, no speech)."
        )
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
                        # drop every speech clause inside the sentence, keep the action that remains
                        _frag = _SPEECH_RE.sub(" ", _x)
                        _frag = _re_mv.sub(r"\b(?:and|while|as|but|then|still)\b\s*", " ", _frag)
                        _frag = _re_mv.sub(r"[,;:]", " ", _frag)
                        _frag = _re_mv.sub(r"\s{2,}", " ", _frag).strip(" .-")
                        _frag = _re_mv.sub(r"\s+(?:to|at|towards?|into)\s+the\s+(?:lens|camera)\s*$", "", _frag, flags=_re_mv.I)
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
            except Exception as _e_mv:
                logger.warning(f"  motion speech-strip skipped: {_e_mv}")
            final_prompt = (
                f"{_stop_rule}\n\n"
                f"[MOVEMENT / การเคลื่อนไหว — ท่อนนี้เป็นคำสั่งการเคลื่อนไหวเท่านั้น อย่าอ่านออกเสียง]:\n{_motion_clean}"
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
def compose_video(
    video_paths: list,
    voice_path: Optional[str] = None,
    run_id: str = "",
    bgm_style: str = "chill_loft",
    target_duration: int = 0,
    voice_speed: float = 1.0,
) -> str:
    """
    Step 9: Compose final video (merge voice + BGM + concat scenes)

    Args:
---
# ─── Main TTS function ─────────────────────────────────────────────────────
        video_paths: list ของ video paths จาก Step 8
        voice_path: path ของ voice จาก Step 7 (None = ไม่มี voiceover)
        run_id: สำหรับสร้าง filename
        bgm_style: สไตล์เพลงพื้นหลัง
        voice_speed: ความเร็วเสียง 1.0=ปกติ (TTS speed จาก speaking_rate 1.2 แล้ว อย่าเร่งซ้ำ)

    Returns:
        str: path ของ final video
    """
    logger.info(f"Step 9/9: Compose (FFmpeg)")

    # Step 9a: Concat scenes (filter None, fallback gracefully)
    valid_paths = [vp for vp in video_paths if vp is not None]
    logger.info(f"  9a: {len(valid_paths)}/{len(video_paths)} valid scenes")

    if not valid_paths:
        raise RuntimeError("No valid videos to compose (all None)")

    concat_path = TMP_DIR / f"concat_{run_id}.mp4"
    if len(valid_paths) > 1:
        concat_videos(valid_paths, concat_path)
    else:
        shutil.copy2(valid_paths[0], concat_path)
    
    # Save raw concatenated video (no audio) for user download
    raw_path = STORAGE_DIR / f"affiliate_{run_id}_raw.mp4"
    shutil.copy2(concat_path, raw_path)
    logger.info(f"  9a: Raw video saved -> {raw_path}")

    # Step 9a.5: If video is shorter than target_duration, loop it to fill full duration
    if target_duration > 0:
        # Get actual duration of concat video
        try:
            probe_cmd = [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(concat_path)
            ]
            probe_result = subprocess.run(probe_cmd, capture_output=True, text=True, check=False)
            actual_duration = float(probe_result.stdout.strip()) if probe_result.stdout.strip() else 0
        except Exception:
            actual_duration = 0

        if actual_duration > 0 and actual_duration < target_duration - 1:
            logger.info(f"  9a.5: Video is {actual_duration:.1f}s, looping to {target_duration}s")
            looped_path = TMP_DIR / f"looped_{run_id}.mp4"
            # Calculate how many loops needed, with slight overlap for smoothness
            loop_count = int(target_duration / actual_duration) + 1
            try:
                cmd_loop = [
                    "ffmpeg", "-y",
                    "-stream_loop", str(loop_count),
                    "-i", str(concat_path),
                    "-c:v", "libx264",
                    "-c:a", "aac",
                    "-t", str(target_duration),
                    "-pix_fmt", "yuv420p",
                    str(looped_path)
                ]
                subprocess.run(cmd_loop, check=True, capture_output=True, timeout=120)
                if looped_path.exists() and looped_path.stat().st_size > 1000:
                    shutil.copy2(looped_path, concat_path)
                    logger.info(f"  9a.5: Looped video saved -> {concat_path}")
            except Exception as e:
                logger.warning(f"  9a.5: Loop failed ({e}), using original concat")

    # Step 9b: REMOVED — Gemini TTS voiceover stripped from TUS (owner 2026-08-24).
    final_path = concat_path


    # Step 9c: Add BGM
    if bgm_style:
        logger.info(f"  9c: Add BGM ({bgm_style})")
        # Resolve the real BGM file via get_bgm_path() (lives in tiktok-ugc-studio/bgm)
        bgm_path = get_bgm_path(bgm_style)
        if not bgm_path.exists():
            logger.warning(f"    BGM file not found: {bgm_path}, trying sibling names")
            bgm_filename = f"{bgm_style}.mp3" if not bgm_style.endswith((".mp3", ".wav")) else bgm_style
            bgm_path = STORAGE_DIR / "sounds" / bgm_filename

        if bgm_path.exists():
            bgm_output = STORAGE_DIR / f"affiliate_{run_id}_bgm.mp4"
            # Strategy: mix BGM under the narration with SIDECHAIN DUCKING (owner 2026-09-09
            # 16:3x — boss: "เสียงพากย์ซ้อน"). Root: the narration (Wan voice mode A, embedded in
            # video audio) is fully clean/single in the raw; the perceived "doubled/layered voice"
            # came from the BGM bed staying at full level UNDER/OVER the whole narration with no
            # ducking, so voiced/sustained music overlapped the Thai voice. Fix: BGM volume drops
            # sharply the moment the narration speaks (sidechaincompress) and only returns in
            # pauses/tail, so voice never overlaps music → clean single narration.
            try:
                # 🔴 FIX (owner 2026-09-10 11:39): "มีแทรกหลังคำว่า เชื่อมเร็ว" — ต้นตอ =
                # BGM (kontraa_water, speech-band ~-25dB) โผล่กลับมาใน "ช่องว่างระหว่างวลี"
                # เพราะ volume=0.5 สูงไป + release=650ms สั้นไป → จังหวะที่บทพูดหยุดพักหายใจ
                # ระหว่างวลี ดนตรีดีดกลับดัง → ฟังเป็น "เสียงแทรก". แก้: ลด BGM เป็น 0.18
                # (ดนตรีเป็นแค่เบด ไม่แข่งกับเสียงพูด) + ducking หนักขึ้น (threshold สูงขึ้น,
                # ratio สูง, release ยาว 1200ms ให้ดนตรีค้างลงนานระหว่างวลี ไม่งั้นมันเด้งกลับ)
                cmd_mix = [
                    "ffmpeg", "-y",
                    "-i", str(final_path),
                    "-stream_loop", "-1",
                    "-i", str(bgm_path),
                    "-filter_complex",
                    "[0:a]apad=pad_dur=20[va];"
                    "[1:a]volume=0.18[bg];"   # BGM as a soft bed only — never compete with narration
                    "[va]asplit=2[voice][side];"
                    "[bg][side]sidechaincompress=threshold=0.06:ratio=20:attack=20:release=1200[duck];"
                    "[voice][duck]amix=inputs=2:duration=longest:dropout_transition=0:normalize=0[out]",
                    "-map", "0:v",
                    "-map", "[out]",
                    "-c:v", "copy",
                    "-c:a", "aac",
                    "-t", str(target_duration),
                    str(bgm_output),
                ]
                subprocess.run(cmd_mix, check=True, capture_output=True, timeout=90)
                logger.info(f"    BGM mixed (sidechain ducked under narration)")
                final_path = bgm_output
            except Exception as e:
                logger.warning(f"    BGM mix failed ({e}), trying BGM-only")
                # Fallback: just copy video + BGM as sole audio
                try:
                    cmd_bgm = [
                        "ffmpeg", "-y",
                        "-i", str(concat_path),  # use original video with audio
                        "-i", str(bgm_path),
                        "-c:v", "copy",
                        "-c:a", "aac",
                        "-map", "0:v:0",
                        "-map", "1:a:0",
                        "-t", str(target_duration),
                        str(bgm_output),
                    ]
                    subprocess.run(cmd_bgm, check=True, capture_output=True, timeout=60)
                    logger.info(f"    BGM-only added")
                    final_path = bgm_output
                except Exception as e2:
                    logger.warning(f"    BGM-only also failed: {e2}")

    logger.info(f"  Final: {final_path}")
    return str(final_path), str(raw_path)


# ═══════════════════════════════════════════════════════════════════════════
# MAIN: Run Full Pipeline v6
# ═══════════════════════════════════════════════════════════════════════════

def run_pipeline(
    product_name: str,
    product_image: Optional[str] = None,
    recipe_name: str = "tus",
    voice: str = "Aoede",
    bgm_style: str = "chill_loft",
    description: Optional[str] = None,
    ugc_style: str = "holding",
    external_job_id: Optional[str] = None,
    product_images: Optional[list] = None,
    duration: int = 15,
    image_prompt: Optional[str] = None,
    video_prompt: Optional[str] = None,
    video_prompts: Optional[list] = None,
    negative_prompt: Optional[str] = None,
    script: Optional[str] = None,
    # ── First/Reference/Last frame + Thai script (Wan พูดเอง ไม่ใช้ TTS lip-sync ทับ) ──
    first_frame: Optional[str] = None,
    reference_image: Optional[str] = None,
    last_frame: Optional[str] = None,
    thai_script: Optional[str] = None,
    use_tus_voice: bool = True,
    audio_path: Optional[str] = None,
    prompt_extend: bool = False,
    gender: str = "female",
    age: str = "",
    **kwargs,
) -> dict:
    """
    Run full Affiliate Pipeline v6 (9 Steps ตาม PIPELINE_STRUCTURE.md)

    Args:
        product_name: ชื่อสินค้า
        product_image: URL ของรูปสินค้า (required!)
        recipe_name: ชื่อ recipe (tus, etsy)
        voice: ชื่อเสียง TTS
        bgm_style: สไตล์เพลงพื้นหลัง
        description: คําอธิบายสินค้า (optional)
        external_job_id: job_id จาก caller (ถ้ามี) — ใช้แทนการ gen เอง เพื่อให้ pipeline_logs.db
                         ตรงกับ pipeline.db ใน tiktok-ugc-studio
        image_prompt: รูป prompt ที่เตรียมมาแล้ว (ถ้ามีจะไม่ gen ใหม่)
        video_prompt: วิดีโอ prompt ที่เตรียมมาแล้ว (ใช้ fallback ถ้า video_prompts ไม่มี)
        video_prompts: รายการวิดีโอ prompts ต่อ scene (ถ้ามีจะไม่ gen ใหม่)
        negative_prompt: negative prompt ที่เตรียมมาแล้ว
        script: script ที่เตรียมมาแล้ว (ถ้ามีจะไม่ gen ใหม่)
        first_frame: path/URL ของ first frame image (ใช้แทน image ที่ gen สำหรับ Wan)
        reference_image: path/URL ของ reference image (ส่งให้ Wan เป็น reference)
        last_frame: path/URL ของ target last-frame image (Wan 2.7 start-end interpolation)
        thai_script: บทพูดภาษาไทยที่ให้ Wan พูดเองในคลิป (ไม่ใช้ TTS lip-sync ทับ)
        use_tus_voice: DEPRECATED (ทิศทางเก่า "ให้ Wan พูดเอง" ปิดแล้ว 2026-08-15) —
            เก็บไว้รับค่า backward-compat เท่านั้น ไม่มีผลต่อ pipeline แล้ว
            ทิศทางใหม่: ส่ง TTS audio ให้ Wan เสมอ (lip-sync) + TTS/BGM ทับที่ compose

    Returns:
        dict: {
            run_id, final_path, duration, cost_estimate, cost_breakdown,
            product_profile, recipe, script, image_path, video_paths
        }
    """
    run_id = uuid.uuid4().hex[:8]
    job_id = external_job_id or f"vid_{run_id}"

    logger.info(f"{'='*60}")
    logger.info(f"Pipeline v6 - Run {run_id}")
    logger.info(f"{'='*60}")
    logger.info(f"Product: {product_name}")
    logger.info(f"Image: {product_image}")
    logger.info(f"Recipe: {recipe_name}")
    logger.info(f"{'='*60}")

    # Initialize pipeline logger
    try:
        start_job(job_id, {
            'product_title': product_name,
            'product_image': product_image,
            'product_description': description,
            'recipe_name': recipe_name,
            'voice': voice,
            'ugc_style': ugc_style,
        })
    except Exception as e:
        logger.warning(f"Pipeline logger start failed: {e}")

    # ── Validate ugc_style from Schema Engine ──
    _orig_ugc = ugc_style
    ugc_style = validate_ugc_style(ugc_style)
    if ugc_style != _orig_ugc:
        logger.warning(f"  ugc_style '{_orig_ugc}' not valid, using '{ugc_style}'")

    pipeline_start = time.time()
    cost_image = 0.0
    cost_voice = 0.0
    cost_video = 0.0

    try:
        # ── STEP 1: Analyze ──
        step_start = time.time()
        product_profile = analyze_product(
            product_name, product_image, description, ugc_style=ugc_style,
            product_images=(product_images or []),
            gender=gender,
            target_age=age,
            body_part=kwargs.get("body_part", ""),
            special_target=kwargs.get("special_target", ""),
            usage_howto=kwargs.get("usage_howto", ""),
            ingredient_highlight=kwargs.get("ingredient_highlight", ""),
            category=kwargs.get("category", ""),
            subcategory=kwargs.get("subcategory", ""),
            duration=(duration if duration and duration > 0 else kwargs.get("duration", 15)),
            features=kwargs.get("features", "") or "",
        )

        # ── Wire prompt-builder (SSOT) outputs into pipeline args ──
        # The studio proxy (/api/v1/pipeline/full) sends NO pre-computed prompts,
        # and the legacy step6 builder lives in steps.disabled/ — so the prompts
        # from analyze_product() MUST be mapped here or Step 6/8 guards raise.
        # ("wire the prompt-builder output", never a hardcoded generic prompt.)
        if not video_prompts and not video_prompt:
            _vp = (product_profile or {}).get("_video_prompt") or ""
            if _vp:
                video_prompts = [_vp]
                logger.info(f"  Wired _video_prompt from prompt-builder ({len(_vp)} chars)")
        # 🔴 FIX 2026-09-10 (owner: "หลุด guard" from vid_179fcbda): the request may carry a
        # UI-supplied DEFAULT negative (frontend sends a 75-char generic text/watermark string
        # when the user leaves the field blank). That non-empty value used to short-circuit
        # `if not negative_prompt:` and DROP the superior Mimo-authored negative (~178ch with
        # distorted hands / extra fingers / warped product). Fix: the Mimo/prompt-builder
        # authored negative (product_profile["_negative_prompt"]) ALWAYS wins when present,
        # regardless of what the caller passed in.
        _authored_neg = (product_profile or {}).get("_negative_prompt") or ""
        if _authored_neg:
            if negative_prompt and negative_prompt.strip() != _authored_neg.strip():
                logger.info(
                    f"  🔁 override request negative_prompt ({len(negative_prompt)}ch) "
                    f"with authored Mimo/pb negative ({len(_authored_neg)}ch)"
                )
            negative_prompt = _authored_neg
        elif not negative_prompt:
            negative_prompt = _authored_neg
        analyze_duration = int((time.time() - step_start) * 1000)

        try:
            update_step(job_id, 'analyze', {'duration_ms': analyze_duration})
        except Exception:
            pass

        # ── STEP 2: Load Recipe ──
        step_start = time.time()
        recipe = load_recipe(recipe_name)
        recipe_duration = int((time.time() - step_start) * 1000)
        num_scenes = len(recipe.get("scenes", []))
        total_duration = duration if duration > 0 else recipe.get("total_duration", 8)

        try:
            update_step(job_id, 'recipe', {'duration_ms': recipe_duration, 'scenes': num_scenes})
        except Exception:
            pass

        # ── STEP 3: Generate Script (skip if pre-computed) ──
        if not script:
            step_start = time.time()
            # target_gender จาก product analyzer ชนะกว่า param (สินค้าผู้หญิง→female เสมอ)
            _gender = (product_profile or {}).get("target_gender") or gender
            script = generate_script(product_name, product_profile, recipe, ugc_style=ugc_style, gender=_gender)
            script_duration = int((time.time() - step_start) * 1000)
        else:
            script_duration = 0
            logger.info(f"Step 3/9: Skipped (using pre-computed script)")

        try:
            update_step(job_id, 'script', {'duration_ms': script_duration, 'script': script[:100]})
        except Exception:
            pass

        # ── VOICE MODE A ONLY (Gemini TTS removed from TUS — owner 2026-08-24) ──
        # Wan 2.7 พูด Thai script เองเสมอ: ถ้ามีบท (script/thai_script) →
        # auto ใช้บทนั้นเป็น thai_script + บังคับ use_tus_voice=True
        # ไม่มี Gemini TTS lip-sync แล้ว — เสียงในไฟล์จริงคือเสียงของ Wan เท่านั้น
        # 🔴 Owner 2026-09-02: งาน no-human ambient (indoor_projector/ambient_outdoor)
        # ไม่มีคนในคลิป → ห้ามฝังบทให้ Wan พูดเด็ดขาด (Wan จะสร้างปาก/พูดมั่ว ๆ แทรก
        # ทับคลิป เช่น vid_081ed2af พูด แอลอีดี ห้าสิบเมตร เพี้ยน) → ตัดบททิ้งเสมอ
        _nh_style = (ugc_style or "").strip().lower()
        if _nh_style in ("indoor_projector", "ambient_outdoor"):
            if thai_script or script:
                logger.warning(f"  No script for no-human style {_nh_style} — dropping thai_script/script (กัน Wan พูดมั่วแทรก)")
            thai_script = ""
            script = ""
        thai_script = (thai_script or script or "").strip()
        # 🔴 SAFETY NET (owner 2026-08-29): สุดท้ายก่อนฝังเข้า prompt ให้ Wan
        # ทับศัพท์ไทยล้วนเสมอ ไม่ว่าบทจะมาจากเส้นทางไหน (ลูกค้าส่งตรง / script_gen /
        # งานเก่า pre-computed) กันคำยากอังกฤษ (SPF50+ PA++++ 50g 30ml, Dr.PONG ฯลฯ)
        # หลุดเข้าบทที่ Wan พูด เพราะคำโรมันยาก ๆ Wan อ่านไม่ออกแล้วเพี้ยนช่วงท้าย
        if thai_script:
            try:
                from prompt_builder import _tts_product_name
                thai_script = _tts_product_name(thai_script) or thai_script
            except Exception as _e_safety:
                logger.warning(f"  ⚠ safety-net transliterate skipped: {_e_safety}")
        thai_script = thai_script.strip()
        # 🔴 Fix C: pull the timed beats for this job (if any) and apply the SAME transliteration
        # safety net to each spoken beat so the timeline text matches the flat thai_script.
        _beats_for_job = []
        try:
            _beats_for_job = list(product_profile.get("_script_beats") or [])
        except Exception:
            _beats_for_job = []
        if _beats_for_job and thai_script:
            try:
                from prompt_builder import _tts_product_name as _tts_pn
                _beats_for_job = [
                    {**b, "text": (_tts_pn(b.get("text") or "") or b.get("text") or "") if b.get("text") else ""}
                    for b in _beats_for_job
                ]
            except Exception as _e_beats:
                logger.warning(f"  ⚠ beats transliterate skipped: {_e_beats}")
        if thai_script and not use_tus_voice:
            # เจ้าสั่งให้ Wan พูด Thai script เสมอใน flow ปกติ → เปิดโหมด A อัตโนมัติ
            use_tus_voice = True
            logger.info(f"  🎙 Voice mode A: auto ใช้ script เป็น thai_script + เปิด use_tus_voice (Wan พูดเอง, ความยาว {len(thai_script)} ตัวอักษร)")
        if thai_script:
            # Verification aid (owner 2026-08-24): log the EXACT spoken lines
            logger.info(f"  🎙 thai_script spoken by Wan: {thai_script}")

        # ── STEP 4: Build Image Prompt (skip if pre-computed) ──
        if not image_prompt:
            step_start = time.time()
            image_prompt = build_image_prompt(product_name, product_profile, recipe)
            img_prompt_duration = int((time.time() - step_start) * 1000)
        else:
            img_prompt_duration = 0
            logger.info(f"Step 4/9: Skipped (using pre-computed image_prompt)")

        try:
            update_step(job_id, 'image_prompt', {'duration_ms': img_prompt_duration})
        except Exception:
            pass

        # ── STEP 5: Generate Image ──
        step_start = time.time()
        # Single 9:16 portrait (owner direction 2026-08-24).
        # Always portrait; do NOT switch to 16:9 landscape no matter what the
        # image_prompt text says.
        img_aspect = "9:16"
        # owner 2026-09-12: default placement = "place_and_hold" (product resting on the
        # surface with a hand reaching in) so the still frame is the "วางด้วย ถือด้วย" shot
        # the owner asked for. "holding"/"handheld" styles use place_and_hold; tabletop/demo
        # also place. Any other style falls back to hold.
        _plc_style = (ugc_style or "").strip().lower()
        if _plc_style in ("holding", "holding_demo", "handheld", "tabletop", "tabletop_demo", "demo", "review"):
            _placement = "place_and_hold"
        else:
            _placement = "hold"
        # owner 2026-09-12: when a multi-variant set was supplied and Mimo picked a reference
        # image (the one showing the most variants), use THAT as the img2img reference so the
        # still shows the full colour/flavour set instead of only image[0].
        _img_ref = product_image
        try:
            _ri = product_profile.get("_reference_image_index")
            _pimgs = [u for u in (product_images or []) if isinstance(u, str) and u.strip()]
            # owner 2026-09-12: Mimo's index refers to the ORIGINAL product_images order.
            # Determine the group-shot image (the one showing the most variants) and always use it
            # as the img2img anchor when available - this is what makes the still show the full
            # coloured line instead of a single repeated pack.
            _group_url = None
            if len(_pimgs) > 1:
                try:
                    _gi = _pick_variant_reference_index(_pimgs)
                    if _gi is not None and 0 <= _gi < len(_pimgs):
                        _group_url = _pimgs[_gi]
                except Exception:
                    pass
            if _group_url:
                _img_ref = _group_url
                logger.info(f"  🎨 reference image = group shot ({_group_url})")
            elif _ri is not None and _pimgs and 0 <= int(_ri) < len(_pimgs):
                _img_ref = _pimgs[int(_ri)]
                logger.info(f"  🎨 reference image from Mimo index {_ri}: {_img_ref}")
        except Exception as _e_ref:
            logger.warning(f"  reference image override skipped: {_e_ref}")
        img_url, cost_image = generate_image(
            image_prompt, _img_ref, aspect_ratio=img_aspect, placement=_placement
        )
        img_path = TMP_DIR / f"image_{run_id}.png"
        download_file(img_url, img_path)
        image_duration = int((time.time() - step_start) * 1000)

        try:
            update_step(job_id, 'image_gen', {'duration_ms': image_duration, 'output_path': str(img_path)})
            update_cost(job_id, 'image', cost_image)
        except Exception:
            pass

        # ── STEP 6: Build Video Prompts (skip if pre-computed) ──
        if not video_prompts and video_prompt:
            video_prompts = [video_prompt]
            vid_prompt_duration = 0
            logger.info(f"Step 6/9: Skipped (using pre-computed video_prompt)")
        elif not video_prompts:
            # NO hardcoded generic prompt. This exact fallback is what produced
            # the "speaks Vietnamese/gibberish" raw video (a generic English prompt
            # with no Thai script went to Wan). Prompts MUST come from the
            # JSON-driven prompt-builder — break loudly instead of regressing.
            # (docs-exact 2026-08-15: ห้ามฝัง script ลง prompt — ไปอยู่ TTS อย่างเดียว)
            raise ValueError(
                "pipeline: video_prompts missing and no video_prompt supplied — "
                "refusing hardcoded generic prompt; wire the prompt-builder output"
            )
        else:
            vid_prompt_duration = 0
            logger.info(f"Step 6/9: Skipped (using pre-computed video_prompts)")

        try:
            update_step(job_id, 'video_prompts', {'duration_ms': vid_prompt_duration, 'count': len(video_prompts)})
        except Exception:
            pass

        # Save all prompts + script to logger
        try:
            update_prompts(job_id, {
                'image_prompt': image_prompt,
                'video_prompts': video_prompts,
                'script': script,
                'negative_prompt': negative_prompt if negative_prompt else '',
                'hashtags': product_profile.get('hashtags', []),
            })
        except Exception as e:
            logger.warning(f"Logger update_prompts failed: {e}")

        # ── STEP 7: REMOVED (Gemini TTS stripped from TUS — owner 2026-08-24) ──
        voice_path = None
        cost_voice = 0.0
        logger.info("Step 7/9: REMOVED — Gemini TTS ถูกถอดออกจาก TUS (Wan พูด thai_script เอง)")

        # ── STEP 8: Generate 1 Video (Wan 2.7 Sync, 1 clip full duration) ──
        # WHY 1 clip: Wan 2.7 img2vid generates from a SINGLE image reference.
        # Multiple independent clips from the same static image = jarring cuts,
        # same product angle every scene, zero visual continuity.
        # 1 continuous generation = smooth motion, natural flow.
        step_start = time.time()
        video_paths = []
        
        vprompt = video_prompts[0] if video_prompts else ""
        if not vprompt:
            # No hardcoded video prompt — raise clearly. Prompts must come from
            # prompt-builder (JSON-driven). Breaking loudly beats a silent generic
            # fallback that diverges from the JSON prompt sources.
            raise ValueError("pipeline: video_prompts is empty/None — no prompt to generate video; refusing hardcoded fallback")
        logger.info(f"  Generating 1 continuous video ({total_duration}s): {vprompt[:80]}...")

        # ── Start/End frames (SINGLE image — owner 2026-08-26) ──
        # Owner direction: FL2V ใช้รูปเดียวคือรูปแรก (first frame) — ห้าม start-end
        # interpolation, ห้าม gen last frame (klein end-scene). เหตุผล: interpolation
        # ทำให้ตอนท้ายวิดีโอสินค้า/องค์ประกอบเพี้ยนไปจากต้น (พี่เจอ "ตอนท้ายผิด").
        # ff = first frame (Nano Banana img2img 9:16 gen จาก reference)
        # lf = ไม่ใช้ — single image เสมอ
        ff = first_frame or str(img_path)
        lf = None
        logger.info(f"  ▶ FL2V SINGLE image (owner rule 2026-08-26): first=({Path(ff).name}), last=None (no klein, no start-end)")

        # Gemini TTS removed from TUS (owner 2026-08-24): no lip-sync audio.
        logger.info("  🎙 SP8: Wan พูดเอง (Voice mode A เท่านั้น)")
        vid_path, cost_video = generate_video(
            image_path=str(img_path),
            prompt=vprompt,
            # 💬 REMARK 2026-08-24: duration รับได้แค่ [8, 15] เท่านั้น (ALLOWED_DURATIONS ใน config.py)
            # — อย่าส่ง 5/อื่นนอกจาก 8,15 → validator VideoRequest reject ทันที (ไม่เกี่ยวกับ Wan)
            # FIX 2026-08-25 (owner bug vid_2d9f4395): ใช้ total_duration จาก request
            # เดิม hardcode duration=8 (commit 48988d52) → user เลือก 15s ใน web UI
            # แต่ Wan gen แค่ 8s แล้ว compose stream_loop ยืดเป็น 15s = เสียง+ภาพวนซ้ำ
            duration=total_duration,
            negative_prompt=negative_prompt,
            # FL2V SINGLE image (owner 2026-08-26): ส่ง first frame รูปเดียว
            # ไม่มี last_frame ไม่มี reference (ห้ามส่ง reference แยก — Prodia จะเอาเป็นภาพหลัก)
            reference_image=None,
            first_frame=ff,
            last_frame=None,
            thai_script=thai_script,
            use_tus_voice=use_tus_voice,
            prompt_extend=prompt_extend,
            ugc_style=ugc_style,
            script_beats=_beats_for_job,
        )
        video_paths.append(vid_path)
        
        video_gen_duration = int((time.time() - step_start) * 1000)

        try:
            update_step(job_id, 'video_gen', {
                'duration_ms': video_gen_duration,
                'output_path': video_paths[-1] if video_paths else ''
            })
            update_cost(job_id, 'video', cost_video)
        except Exception:
            pass

        # ── STEP 9: Compose ──
        # Duration target: ใช้ค่า `total_duration` (ที่ user/request ระบุ เช่น 15s) เป็นเป้า
        # เสมอ — ถ้า Prodia Wan กลับมาสั้นกว่า (Wan 2.7 ทำได้ ~8s แม้ขอ 15s) ให้ 9a.5
        # -stream_loop ยืดให้เต็ม target (owner อยากได้ 15 วิ เพิ่มจาก 8 วิ)
        # เดิม forced ใช้ actual_video_duration → 15s job กลายเป็น 8s ไม่ง่าย target
        target_duration = total_duration if total_duration > 0 else recipe.get("total_duration", 0)
        final_duration = target_duration if target_duration > 0 else 0
        # Gemini TTS removed from TUS (owner 2026-08-24): compose mixes BGM
        # over Wan's own audio only — never a TTS voiceover.
        final_path, raw_path = compose_video(video_paths, None, run_id, bgm_style, target_duration=final_duration)

        # Preserve the TRUE Prodia output (before any compose/edit) permanently.
        # raw_path = affiliate_{run_id}_raw.mp4 is a POST-compose concat output.
        # The raw Wan 2.7 Prodia file is vid_path (img2vid_*.mp4) — copy it out of
        # TMP (which gets cleaned) so the UI "ไฟล์ที่สร้าง" can show what Prodia
        # actually generated, letting the user see the un-edited lip-sync source.
        prodia_src = vid_path if vid_path else (video_paths[-1] if video_paths else '')
        prodia_raw_path = ''
        if prodia_src and os.path.exists(prodia_src):
            prodia_raw_path = str(STORAGE_DIR / f"raw_prodia_{run_id}.mp4")
            shutil.copy2(prodia_src, prodia_raw_path)
            logger.info(f"  Prodia raw preserved -> {prodia_raw_path}")

        # Cost summary
        cost_total = cost_image + cost_voice + cost_video
        total_duration_ms = int((time.time() - pipeline_start) * 1000)

        logger.info(f"{'='*60}")
        logger.info(f"Pipeline v6 complete: {final_path}")
        logger.info(f"Cost: ${cost_total:.4f}")
        logger.info(f"Time: {total_duration_ms/1000:.1f}s")
        logger.info(f"{'='*60}")

        # Log completion — raw_video_path now points at the true Prodia output
        # (raw_prodia_{run_id}.mp4). The compose-concat output (raw_path) stays
        # on disk for reference but is no longer exposed as "Raw Video".
        try:
            complete_job(
                job_id,
                final_path=str(final_path),
                total_duration_ms=total_duration_ms,
                total_video_duration=total_duration,
                total_scenes=num_scenes,
                raw_video_path=prodia_raw_path or str(raw_path)
            )
        except Exception as e:
            logger.warning(f"Pipeline logger complete failed: {e}")

        return {
            "run_id": run_id,
            "final_path": str(final_path),
            "duration": total_duration,
            "cost_estimate": round(cost_total, 4),
            "cost_breakdown": {
                "image": round(cost_image, 4),
                "voice": round(cost_voice, 4),
                "video": round(cost_video, 4),
                "total": round(cost_total, 4),
            },
            "product_profile": {k: v for k, v in product_profile.items() if not k.startswith("_")},
            "hashtags": product_profile.get('hashtags', []),
            "recipe": recipe_name,
            "script": script,
            "image_path": str(img_path),
            "video_paths": video_paths,
            "job_id": job_id,
        }

    except Exception as e:
        try:
            fail_job(job_id, str(e), 'unknown')
        except Exception as e2:
            logger.warning(f"Pipeline logger fail failed: {e2}")
        raise


# ─── CLI ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Affiliate Video Pipeline v6")
    parser.add_argument("--product-name", required=True, help="ชื่อสินค้า")
    parser.add_argument("--product-image", required=True, help="รูปสินค้า (URL/path)")
    parser.add_argument("--recipe", default="tus", help="Recipe name")
    parser.add_argument("--voice", default="Aoede", help="TTS voice")
    parser.add_argument("--bgm", default="chill_loft", help="BGM style")
    parser.add_argument("--description", default="", help="คําอธิบายสินค้า")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    result = run_pipeline(
        product_name=args.product_name,
        product_image=args.product_image,
        recipe_name=args.recipe,
        voice=args.voice,
        bgm_style=args.bgm,
        description=args.description,
    )

    print("\n✅ Pipeline v6 Done!")
    print(f"  Final: {result['final_path']}")
    print(f"  Duration: {result['duration']}s")
    print(f"  Cost: ${result['cost_estimate']}")
    print(f"  Script: {result['script'][:80]}...")