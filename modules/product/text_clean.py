# ─── Product text cleaning (owner 2026-09-09) ───────────────────────────────
"""Clean messy TikTok Shop product titles/descriptions before they reach
Mimo/prompt writing:

- Strip promotional noise ("9.9 SALE [Hot]", "(ซื้อ 1 แถม 1)", "% off" ...)
- Translate/clean common Vietnamese field labels (returned by ACTOR_PRODUCT)
- Fix common broken/mixed-language spellings
- Keep result Thai-friendly and short

Used by:
  - modules/product/analyze_pipeline.enrich (cleans title_th/description_th)
  - modules/video/pipeline_affiliate._deepseek_product_prompts (cleans before user_text)
"""
import re

# ── Vietnamese field labels → Thai (returned inside specifications) ──
_VN_REPLACEMENTS = [
    (re.compile(r"Thương hiệu", re.I), "แบรนด์"),
    (re.compile(r"Mã số đăng ký mỹ phẩm của FDA Thái Lan trên nhãn sản phẩm", re.I), "เลขทะเบียน อย.ไทยบนฉลาก"),
    (re.compile(r"Thái Lan", re.I), "ไทย"),
    (re.compile(r"trên", re.I), ""),
    (re.compile(r"Xem P", re.I), ""),
    (re.compile(r"Mã số đăng ký mỹ phẩm", re.I), "เลขทะเบียนเครื่องสำอาง"),
    (re.compile(r"Nhãn sản phẩm", re.I), "ฉลากสินค้า"),
    (re.compile(r"Sản phẩm", re.I), "สินค้า"),
    (re.compile(r"Trọng lượng tịnh", re.I), "น้ำหนักสุทธิ"),
    (re.compile(r"Xuất xứ", re.I), "แหล่งผลิต"),
    (re.compile(r"Thành phần", re.I), "ส่วนประกอบ"),
    (re.compile(r"hạn sử dụng", re.I), "วันหมดอายุ"),
    (re.compile(r"Bảo quản", re.I), "การเก็บรักษา"),
    (re.compile(r"Hướng dẫn sử dụng", re.I), "วิธีใช้"),
    (re.compile(r"đăng ký", re.I), "ทะเบียน"),
    (re.compile(r"mỹ phẩm", re.I), "เครื่องสำอาง"),
    (re.compile(r"nước hoa", re.I), "น้ำหอม"),
]

# ── Common broken/mixed EN spellings → Thai ──
_WORD_FIXES = [
    # no \b before latin word when glued to a Thai char (Python exposes no boundary)
    (re.compile(r"barier|barrier", re.I), "บาเรียร์"),
    (re.compile(r"ฟื้นบาเรียร์ ของผิว"), "ฟื้นฟูเกราะผิว"),
    (re.compile(r"Niacinamide", re.I), "ไนอาซินาไมด์"),
    (re.compile(r"Teashell", re.I), "ทีเชลล์"),
    (re.compile(r"FDA", re.I), "อย."),
    (re.compile(r"Mela ?B3", re.I), "เมลาบีทรี"),
    (re.compile(r"Ketzuzu", re.I), "เคตซูซุ"),
    (re.compile(r"OUKEYA", re.I), "โอเกยะ"),
    (re.compile(r"JBL", re.I), "เจบีแอล"),
]

# ── Promotional prefixes/suffixes to drop ──
_PROMO_PATTERNS = [
    re.compile(r"\b\d+(?:\.\d+)?\s*SALE\b", re.I),
    re.compile(r"\bF[Ll]ash ?Sale\b", re.I),
    re.compile(r"\b[Hh]ot\b"),
    re.compile(r"\bSALE\b", re.I),
    re.compile(r"\bMEGA\b", re.I),
    re.compile(r"\bสุดคุ้ม\b"),
    re.compile(r"\bลด\s*\d+\s*%\b"),
    re.compile(r"\b\d+\s*%\s*(?:off|OFF)?\b"),
    re.compile(r"\bLIMITED\b", re.I),
    re.compile(r"\bNEW\b", re.I),
    re.compile(r"\bPRE[- ]?ORDER\b", re.I),
    re.compile(r"\bCOD\b", re.I),
    re.compile(r"\bพร้อมส่ง\b"),
    re.compile(r"\bส่งฟรี\b"),
]

_BRACKET_RE = re.compile(r"\[[^\]]*\]|\([^)]*(?:ซื้อ|แถม|ลด|sale|SALE|ชิ้น|%|off|OFF|2|3)[^)]*\)")


def clean_text(text: str, max_len: int = 200) -> str:
    """Clean a single product title/description (rule-based, no LLM)."""
    if not text:
        return ""
    t = str(text).strip()
    # Drop bracketed promo: "[Hot]", "(ซื้อ 1 แถม 1)"
    t = _BRACKET_RE.sub(" ", t)
    # Drop standalone promo tokens
    for pat in _PROMO_PATTERNS:
        t = pat.sub(" ", t)
    # Vietnamese field labels → Thai
    for pat, repl in _VN_REPLACEMENTS:
        t = pat.sub(repl, t)
    # Broken EN spellings → Thai/clean
    for pat, repl in _WORD_FIXES:
        t = pat.sub(repl, t)
    # Collapse whitespace + punctuation cleanup
    t = re.sub(r"\s{2,}", " ", t).strip()
    t = re.sub(r"\s*,\s*", ", ", t).strip(" ,:-")
    if max_len and len(t) > max_len:
        cut = t[:max_len]
        if " " in cut:
            cut = cut.rsplit(" ", 1)[0]
        t = cut.strip()
    return t


def clean_description(desc: str, fallback_title: str = "", max_len: int = 400) -> str:
    """Clean a description; if empty after cleaning fall back to cleaned title."""
    d = clean_text(desc, max_len=max_len)
    if not d and fallback_title:
        d = clean_text(fallback_title, max_len=max_len)
    return d