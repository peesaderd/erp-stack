"""
mimo_vision.py — Mimo v2.5 vision helper for passport lighting analysis
=======================================================================
Owner request (2026-09-11): "A+D" for key-light adaptive.

A — Hybrid classification: statistical key_detect runs first (fast/free); only when
    the result is borderline/ambiguous do we call Mimo vision to confirm the key.
D — Context-aware lighting prompt: Mimo writes the FLUX lighting prompt that matches
    the ACTUAL context of the photo (backlit / hard side light / shadow under eyes /
    flat phone flash ...) instead of one of 3 hardcoded prompts.

Mimo v2.5 is multimodal (accepts image_url) — proven 2026-09-11 on a real portrait.
Key resolution mirrors modules/video/pipeline_affiliate._mimo_key():
    os.environ -> shared_config .env -> openclaw.json (root-only fallback).

Never fatal: every function has a timeout and returns None on any failure so the
caller keeps the pure-statistical result.
"""

import base64
import json
import logging
import os
import urllib.request

logger = logging.getLogger("passport.mimo")

MIMO_URL = "https://token-plan-sgp.xiaomimimo.com/v1/chat/completions"
MIMO_MODEL = "mimo-v2.5"


def _mimo_key() -> str:
    """Resolve Mimo API key: env -> shared_config .env -> openclaw.json."""
    k = os.environ.get("MIMO_API_KEY", "") or ""
    if not k:
        try:
            from shared_config import _env_dict  # type: ignore
            k = (_env_dict or {}).get("MIMO_API_KEY", "") or ""
        except Exception:
            k = ""
    if not k:
        try:
            p = os.path.expanduser("/home/openhands/.openclaw/openclaw.json")
            if os.path.exists(p):
                cfg = json.load(open(p))
                k = (cfg.get("models", {}).get("providers", {})
                        .get("xiaomi", {}).get("apiKey") or "")
        except Exception:
            k = ""
    return k


def _b64_jpeg(image_bytes: bytes, max_side: int = 768) -> str:
    """Downscale + base64-encode a JPEG so the vision call stays cheap."""
    try:
        import cv2
        import numpy as np
        arr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("decode failed")
        h, w = img.shape[:2]
        scale = min(1.0, max_side / max(h, w))
        if scale < 1.0:
            img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
        ok, buf = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), 88])
        if not ok:
            raise ValueError("encode failed")
        return base64.b64encode(buf.tobytes()).decode()
    except Exception:
        return base64.b64encode(image_bytes).decode()


def _call_mimo(image_bytes: bytes, prompt_text: str, max_tokens: int = 3000,
               timeout: int = 120) -> str:
    """Send one vision request to Mimo; return the text content or '' on failure.

    NOTE: Mimo v2.5 runs a thinking pass by default; a small max_tokens is consumed by
    the reasoning and the content comes back EMPTY with finish_reason='length'. So we
    both request a generous budget and ask to disable thinking for speed.
    """
    key = _mimo_key()
    if not key:
        logger.warning("mimo_vision: no API key available")
        return ""
    b64 = _b64_jpeg(image_bytes)
    payload = {
        "model": MIMO_MODEL,
        "max_tokens": max_tokens,
        "temperature": 0.2,
        "chat_template_kwargs": {"enable_thinking": False},
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt_text},
                {"type": "image_url",
                 "image_url": {"url": "data:image/jpeg;base64," + b64}},
            ],
        }],
    }
    try:
        req = urllib.request.Request(
            MIMO_URL, data=json.dumps(payload).encode(),
            headers={"Authorization": "Bearer " + key,
                     "Content-Type": "application/json"},
            method="POST")
        resp = urllib.request.urlopen(req, timeout=timeout)
        data = json.load(resp)
        content = (data.get("choices", [{}])[0].get("message", {}) or {}).get("content") or ""
        return content.strip()
    except Exception as e:
        body = ""
        try:
            body = (getattr(e, "read", lambda: b"")() or b"").decode()[:300]
        except Exception:
            pass
        logger.warning(f"mimo_vision: call failed: {e} {body}")
        return ""


def _extract_json(text: str) -> dict:
    """Pull the first {...} JSON object out of a model reply."""
    if not text:
        return {}
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return {}
    try:
        return json.loads(text[start:end + 1])
    except Exception:
        return {}


# Words that OVER-BEAUTIFY the face (plastic skin / identity drift). We still want
# the model to produce a tidy, symmetric ID portrait, so we only strip the worst
# beauty/retouch triggers from a model-authored lighting prompt — NOT generic
# words like 'studio' or 'high quality' (v3 used those and the result was fine).
_FORBIDDEN_PROMPT_WORDS = (
    "beauty filter", "beautify", "flawless", "perfect skin", "poreless",
    "smooth skin", "skin smoothing", "airbrush", "airbrushed", "retouch",
    "retouched", "glamour", "plastic", "wax", "porcelain", "doll",
    "slim the face", "slim face", "reshape the face", "reshape face",
    "brighten the eyes", "whiten the eyes", "v-shaped face",
)


def _sanitize_lighting_prompt(prompt: str) -> str:
    """Strip OVER-BEAUTIFY trigger words from a model-authored lighting prompt.

    Keeps lighting/contrast/tone instructions; removes only beautification words
    that cause plastic skin / identity drift. Does NOT force 'same face' (v4 did
    that and it made FLUX copy the source's asymmetry -> lost the ID format).
    Returns '' if nothing usable remains.
    """
    if not prompt:
        return ""
    import re as _re
    out = prompt
    removed = []
    for w in _FORBIDDEN_PROMPT_WORDS:
        if _re.search(_re.escape(w), out, flags=_re.IGNORECASE):
            removed.append(w)
            out = _re.sub(_re.escape(w), "", out, flags=_re.IGNORECASE)
    out = _re.sub(r"\s*,\s*,\s*", ", ", out)
    out = _re.sub(r"^[\s,]+|[\s,]+$", "", out).strip(" ,")
    if removed:
        logger.warning(f"mimo_vision: stripped over-beautify words from prompt: {removed}")
    return out


def analyze_lighting(image_bytes: bytes, stat_hint: dict = None) -> dict:
    """
    Ask Mimo to (A) confirm the exposure key and (D) write a context-aware prompt.

    Returns {} on failure (caller keeps statistical result). Otherwise:
        {
          "key": "low"|"normal"|"high",
          "confidence": 0-1,
          "context": "<what kind of light: backlit, hard side light, flat flash...>",
          "highlight_risk": "none"|"mild"|"severe",
          "shadow_risk": "none"|"mild"|"severe",
          "lighting_strength": float,
          "lighting_prompt": "<positive FLUX prompt to even the light>",
          "negative_prompt": "<optional negative, or ''>",
          "reason": "..."
        }
    """
    hint = ""
    if stat_hint:
        hint = (f"\nStatistical pre-analysis (may be wrong near thresholds): "
                f"key={stat_hint.get('key')}, "
                f"face_mean={stat_hint.get('face_mean')}, "
                f"frame_mean={stat_hint.get('frame_mean')}, "
                f"clipped_high={stat_hint.get('clipped_high_pct')}%, "
                f"clipped_low={stat_hint.get('clipped_low_pct')}%.")
    prompt_text = (
        "You are an expert ID-photo lighting technician. Look at this portrait and "
        "judge its exposure so we can normalise the lighting to a clean, evenly lit "
        "ID photo WITHOUT distorting the face.\n" + hint + "\n\n"
        "Decide:\n"
        "- key: low (dark/underexposed) | normal (well exposed) | high (bright/overexposed)\n"
        "- context: the ACTUAL light situation in words (e.g. backlit window behind, "
        "hard side light from the left, flat phone flash, warm tungsten, shadow under "
        "the eyes, blown forehead highlight, low-key moody).\n"
        "- highlight_risk / shadow_risk: none|mild|severe\n"
        "- lighting_strength: 0.05-0.45 (FLUX img2img strength for the lighting pass; "
        "LOWER = gentler. Already-bright photos need lower; dark photos need higher.)\n"
        "- lighting_prompt: a SHORT positive English prompt telling FLUX how to fix the "
        "lighting for THIS photo specifically. Must keep the same person, same clothes, "
        "same background. If already bright, ask to tame highlights / not wash out. If "
        "backlit, ask for soft frontal fill on the face. If hard side light, ask to "
        "soften and even out. Do NOT ask for beauty retouching (no 'flawless', "
        "'smooth skin', 'airbrush', 'beauty filter', 'slim the face', 'brighten the "
        "eyes', 'v-shaped face') — we want a tidy, natural, symmetric ID portrait, "
        "not a plastic beautified one. Only talk about LIGHT, contrast and colour "
        "balance.\n"
        "- negative_prompt: optional short English negatives (e.g. overexposed, blown "
        "highlights, washed out) or empty string.\n"
        "- reason: one short sentence.\n\n"
        "Reply with ONLY a JSON object, no markdown:\n"
        '{"key":"...","confidence":0.0-1.0,"context":"...","highlight_risk":"...",'
        '"shadow_risk":"...","lighting_strength":0.0,"lighting_prompt":"...",'
        '"negative_prompt":"...","reason":"..."}'
    )
    raw = _call_mimo(image_bytes, prompt_text, max_tokens=3000)
    if not raw:
        return {}
    data = _extract_json(raw)
    if not data or "lighting_strength" not in data:
        logger.warning(f"mimo_vision: unparseable reply: {raw[:160]!r}")
        return {}
    # Sanitize the model-authored prompt: never let face-repaint words through.
    if data.get("lighting_prompt"):
        data["lighting_prompt"] = _sanitize_lighting_prompt(data["lighting_prompt"])
    # sanitise strength
    try:
        s = float(data.get("lighting_strength", 0.2))
        data["lighting_strength"] = round(max(0.05, min(0.45, s)), 3)
    except Exception:
        data["lighting_strength"] = 0.2
    try:
        data["confidence"] = round(float(data.get("confidence", 0.7)), 2)
    except Exception:
        data["confidence"] = 0.7
    logger.info(f"mimo_vision: key={data.get('key')} strength={data['lighting_strength']} "
                f"ctx={data.get('context','')!r}")
    return data
