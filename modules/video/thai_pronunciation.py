"""Thai spoken-script pronunciation library.

Central, deterministic post-processor for Thai TTS / Wan voice-over scripts.

WHY THIS EXISTS (owner 2026-09-13):
    The voice model (Wan 2.7 voice mode A / Thai TTS) reads the script ALOUD and
    mis-reads abbreviations and symbols (e.g. "ชม." -> "ชม" not "ชั่วโมง",
    "ดร." -> "ดอน"/"ดอรอ" instead of "ด็อกเตอร์"). We fix these with a
    DETERMINISTIC word-mapping library rather than by adding rules to the Mimo
    system prompt, because:
      1. A prompt instruction is only a soft hint - the AI can forget/vary it.
         A regex/dict replacement is 100% reproducible every single run.
      2. It covers EVERY script path (AI-authored, user-supplied, button-driven),
         not just when Mimo writes the text.
      3. LESS IS MORE - adding more rules to the system prompt makes Mimo drift;
         keeping pronunciation here keeps the prompt lean.

PRINCIPLE (owner 2026-09-13):
    * Fixed 1:1 Thai reading (ดร. -> ด็อกเตอร์, ชม. -> ชั่วโมง, SPF -> เอสพีเอฟ)
      -> put it in THIS library.
    * Style / word-choice / tone -> stays in the system prompt.

To add a word: append to the relevant table below and add a unit test.
"""

from __future__ import annotations

import re

# ─────────────────────────────────────────────────────────────────────────────
# 1. Abbreviations with a fixed Thai reading.
#    Order matters: longer / more specific patterns first. Note \u0E00-\u0E7F is
#    the Thai block, used to avoid matching inside a longer Thai word.
# ─────────────────────────────────────────────────────────────────────────────
THAI_ABBR = [
    # owner 2026-09-13: "ดร." / "ดร" must be spoken as "ด็อกเตอร์" (Wan read it
    # as "ดอน"/"ดอรอ"). Match with or without a trailing dot, but never inside a
    # Thai word (e.g. "ดราม่า" must be left untouched). The `\.\s*` branch eats a
    # spaced dot; the second branch catches the bare "ดร" form.
    (r"ดร\.\s*|ดร(?![\u0E00-\u0E7F])", "ด็อกเตอร์ "),
    (r"ชม\.", "ชั่วโมง"), (r"ชั่วโมง\.", "ชั่วโมง"),
    (r"ม\.ล\.", "มิลลิลิตร"), (r"ซ\.ม\.", "เซนติเมตร"),
    (r"ก\.ก\.", "กิโลกรัม"), (r"ก\.", "กรัม"),
    (r"บ\.", "บาท"), (r"น\.", "นาฬิกา"),
    (r"นาที\.", "นาที"), (r"วินาที\.", "วินาที"),
]

# 2. Symbols -> spoken Thai word.
THAI_SYM = [("%", "เปอร์เซ็นต์")]

# 3. Latin tech/brand words that commonly slip through -> Thai phonetic spelling.
THAI_LATIN = {
    "bluetooth": "บลูทูธ", "usb": "ยูเอสบี", "led": "แอลอีดี", "aac": "เอเอซี",
    "spf": "เอสพีเอฟ", "anc": "เอเอ็นซี", "hdmi": "เอชดีเอ็มไอ", "wifi": "ไวไฟ",
    "wi-fi": "ไวไฟ", "gps": "จีพีเอส", "type-c": "ไทป์ซี", "type c": "ไทป์ซี",
}

# 4. Hard consonant clusters at the START of a clip come out garbled by Wan
#    (owner 2026-09-12: "เบื่อก๋วยเตี๋ยว..." at pos-1 decoded as "Buer cuitit...").
#    Fix the worst offenders phonetically.
THAI_CLUSTER_FIX = [
    (r"ก๋วยเตี๋ยว", "กวยเตี๋ยว"),
    (r"ก๋วยจั๊บ", "กวยจับ"),
]

# Hard clusters that must NOT be the very first content word of the spoken script
# (after the phonetic rewrite above, these are the "กวย*" forms).
THAI_HARD_OPENER = ("ก๋วย", "กวยเตี๋ยว", "ก๋วยเตี๋ยว", "ก๋วยจั๊บ")

# 5. Whole-word / brand corrections (owner 2026-09-13). These are NOT plain
#    pronunciations - Mimo writes the brand lexeme wrong or glues a word to its
#    neighbour, which then reads back garbled:
#      * "ด็อกเตอร์ พงศ์..." -> "ด็อกเตอร์พงษ์..."  (brand name is ONE word, and
#        the surname is "พงษ์" not "พงศ์"). The lookahead is BOUNDED to the next
#        3 Thai letters so we never swallow a following word (e.g. "พงศ์อูรี..."
#        must keep "อูรี" intact).
#      * "อูรี..."/"ยูเรีย" -> "อูเรีย"  (urea = อูเรีย, not อูรียา).
#    Order: run AFTER the abbreviation pass (which already split ดร -> "ด็อกเตอร์ ").
THAI_WORD_FIX = [
    # "ด็อกเตอร์ พงศ์"/"ด็อกเตอร์ พงค์"/"ด็อกเตอร์พงค์" -> "ด็อกเตอร์พงษ์" (brand = ONE word,
    # surname spelled ษ). Owner 2026-09-14: Mimo also emits "พงค์" (ค) and a spaced variant;
    # cover all spellings + optionally absorb a following space so the brand stays one word.
    (r"ด็อกเตอร์\s*พง[ศค]์?(?=[\u0E00-\u0E7F]{0,3})", "ด็อกเตอร์พงษ์"),
    (r"ด็อกเตอร์\s*พงษ์์?(?=[\u0E00-\u0E7F]{0,3})", "ด็อกเตอร์พงษ์"),
    (r"อูรียา", "อูเรีย"),
    (r"ยูเรีย", "อูเรีย"),
]

# Clusters used by the opening-guard re-open logic.
_OPENING_CLUSTERS = ("กวยเตี๋ยว", "กวยจับ", "ก๋วยเตี๋ยว", "ก๋วยจั๊บ")


def _apply_abbr(text: str) -> str:
    for pat, rep in THAI_ABBR:
        text = re.sub(pat, rep, text)
    return text


def _apply_symbols(text: str) -> str:
    for sym, rep in THAI_SYM:
        text = text.replace(sym, " " + rep + " ")
    return text


def _apply_latin(text: str) -> str:
    for lat, rep in THAI_LATIN.items():
        text = re.sub(
            r"(?<![A-Za-z])" + re.escape(lat) + r"(?![A-Za-z])",
            rep, text, flags=re.IGNORECASE,
        )
    return text


def _apply_cluster_fix(text: str) -> str:
    for pat, rep in THAI_CLUSTER_FIX:
        text = re.sub(pat, rep, text)
    return text


def _apply_word_fix(text: str) -> str:
    for pat, rep in THAI_WORD_FIX:
        text = re.sub(pat, rep, text)
    return text


def _separate_glued_script(text: str) -> str:
    """Insert a space between Thai and adjacent Latin/digit runs so leftover
    Latin never fuses into a Thai word."""
    text = re.sub(r"([\u0E00-\u0E7F])([A-Za-z0-9])", r"\1 \2", text)
    text = re.sub(r"([A-Za-z0-9])([\u0E00-\u0E7F])", r"\1 \2", text)
    return text


def _tidy_spaces(text: str) -> str:
    return re.sub(r"[ \t]{2,}", " ", text).strip()


def _guard_hard_opening(text: str) -> str:
    """The voice garbles its FIRST syllable when a hard cluster (กวยเตี๋ยว /
    กวยจั๊บ) sits within the opening words. If it appears inside the first two
    whitespace-words, re-open the line with an easy hook ("หิวใช่ไหม") + the
    (phonetic) noun, then the rest. Safe no-op when the opening is already clean.
    """
    try:
        first2 = " ".join(text.split()[:2])
        hit = next((c for c in _OPENING_CLUSTERS if c in first2), None)
        if hit and not text.startswith("หิวใช่ไหม"):
            noun = "กวยเตี๋ยว" if "เตี๋ยว" in hit else "กวยจับ"
            rest = text.replace(hit, " ", 1)
            rest = re.sub(
                r"^(?:ใครที่|ใคร|และ|ที่|ก็)?\s*(?:เบื่อ|ชอบ|อยาก|หิว|รสดี|กิน)?\s*",
                "", rest, count=1,
            )
            rest = re.sub(r"^กิน\s*", "", rest, count=1)
            rest = re.sub(r"\s{2,}", " ", rest).strip(" ,")
            if rest:
                text = ("หิวใช่ไหม " + noun + " " + rest).strip()
    except Exception:
        pass
    return text


def normalize_thai_spoken_script(text: str) -> str:
    """Convert abbreviations + stray symbols in a Thai spoken script to full,
    pronounceable Thai words so the voice model reads them correctly."""
    if not text:
        return text
    out = text
    out = _apply_cluster_fix(out)       # phonetic fix BEFORE anything else
    out = _apply_abbr(out)              # ดร. -> ด็อกเตอร์, ชม. -> ชั่วโมง, ...
    out = _apply_symbols(out)           # % -> เปอร์เซ็นต์
    out = _apply_latin(out)             # spf -> เอสพีเอฟ, ...
    out = _apply_word_fix(out)          # ด็อกเตอร์พงศ์ -> ด็อกเตอร์พงษ์, อูรียา -> อูเรีย
    out = _separate_glued_script(out)   # keep Latin/digit from fusing to Thai
    out = _tidy_spaces(out)
    out = _guard_hard_opening(out)
    return out
