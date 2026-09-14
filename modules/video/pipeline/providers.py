"""Provider helpers & reference pickers (Phase C split, move-only)."""
from ._shared import (  # noqa: F401
    os, re, sys, json, time, uuid, logging, random, subprocess, shutil, asyncio,
    Path, Optional, List, Dict, Any, requests,
    PRODIA_TOKEN, GEMINI_API_KEY, logger,
)

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

def _mimo_image_ref(u: str) -> Optional[str]:
    """owner 2026-09-13 (card 8c264f8b verify): turn a product-image reference into something
    Mimo's vision endpoint accepts. Mimo rejects ANY non-http(s)/base64 URL (error:
    'the provided url is not valid, only base64, http or https URLs allowed'), but TUS products
    store images as RELATIVE public paths like '/ugc/static/product_images/x.webp'.

    Resolution order:
      1) already http(s) / data:  -> use as-is
      2) relative public path / bare filename -> resolve to the on-disk file under
         tiktok-ugc-studio/storage/product_images/ and inline it as a base64 data URL
         (base64 is host-independent; the service is also reachable over the tus.m2igen.com
         domain in the browser, so we cannot rely on an internal http:// host/port here)
      3) anything else -> None (drop it; caller degrades to fewer/no images)
    """
    if not isinstance(u, str):
        return None
    s = u.strip()
    if not s:
        return None
    if s.startswith("http://") or s.startswith("https://") or s.startswith("data:"):
        return s
    # protocol-relative
    if s.startswith("//"):
        return "https:" + s
    # relative public paths -> map to the on-disk product_images dir
    _fn = s.rsplit("/", 1)[-1]
    if not _fn:
        return None
    _base = Path(__file__).resolve().parent.parent.parent / "tiktok-ugc-studio" / "storage" / "product_images"
    _fp = _base / _fn
    try:
        if not _fp.is_file():
            return None
        import base64 as _b64
        _mime = "image/png"
        _ext = _fp.suffix.lower()
        if _ext in (".jpg", ".jpeg"):
            _mime = "image/jpeg"
        elif _ext == ".webp":
            _mime = "image/webp"
        elif _ext == ".gif":
            _mime = "image/gif"
        _raw = _fp.read_bytes()
        # guard against huge files (base64 inflates ~33%); Mimo caps media size
        if len(_raw) > 6_000_000:
            return None
        return "data:%s;base64,%s" % (_mime, _b64.b64encode(_raw).decode("ascii"))
    except Exception:
        return None

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

