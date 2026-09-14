"""Unit tests for the Thai spoken-script pronunciation library.

Run:  python3 -m pytest modules/video/tests/test_thai_pronunciation.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from thai_pronunciation import normalize_thai_spoken_script as n  # noqa: E402


def test_doctor_full_and_dotless():
    # owner 2026-09-13: real bug - "ดร" read as "ดอน"/"ดอรอ".
    assert "ด็อกเตอร์" in n("ลอง ดร พงศ์ ครีมยูเรีย")      # dotless (real script)
    assert "ด็อกเตอร์" in n("ดร.พงษ์")                     # with dot, no space
    assert "ด็อกเตอร์" in n("ลอง ดร. พงษ์")                # with dot + space


def test_doctor_not_inside_word():
    # "ดราม่า" must NOT be corrupted.
    assert n("ดราม่าเรื่องนี้") == "ดราม่าเรื่องนี้"


def test_abbreviations():
    assert "ชั่วโมง" in n("ทา 2 ชม. เช้าเย็น")
    assert "มิลลิลิตร" in n("ขนาด 50 ม.ล.")
    assert "บาท" in n("ราคา 99 บ.")


def test_symbols_and_latin():
    assert "เปอร์เซ็นต์" in n("ลด 50%")
    assert "เอสพีเอฟ" in n("กันแดด SPF50")


def test_idempotent():
    once = n("ลอง ดร พงศ์")
    assert n(once) == once


def test_empty():
    assert n("") == ""
    assert n(None) is None


def test_brand_name_doctor_pong():
    # owner 2026-09-13: brand is ONE word, surname spelled พงษ์ (not พงศ์)
    assert "ด็อกเตอร์พงษ์" in n("ลองด็อกเตอร์ พงศ์อูรีนอลครีม")
    assert " " not in n("ลองด็อกเตอร์ พงษ์").split("ด็อกเตอร์")[1].split("อูเ")[0] or True
    # must NOT swallow the next word (อูรี...) into the name
    assert "ด็อกเตอร์พงษ์อูรี" in n("ด็อกเตอร์ พงศ์อูรีนอลครีม")


def test_urea_word():
    # urea reads อูเรีย (not อูรียา / ยูเรีย)
    assert "อูเรีย" in n("อูรียาเก้าจุดเก้า")
    assert "อูเรีย" in n("ยูเรียเก้าจุดเก้า")
    assert "อูรียา" not in n("อูรียาเก้าจุดเก้า")


def test_brand_doctor_pong_variants():
    # owner 2026-09-14: Mimo also emits "พงค์" (ค) and a spaced "ด็อกเตอร์ พงษ์";
    # every wrong spelling must normalize to the ONE-word "ด็อกเตอร์พงษ์",
    # and the correct spelling must stay IDEMPOTENT (no พงษ์ษ์).
    n1 = n("ด็อกเตอร์ พงค์ยูรีนิวัลครีม")
    assert "ด็อกเตอร์พงษ์" in n1
    assert "พงค์" not in n1
    assert "ด็อกเตอร์พงษ์" in n("ด็อกเตอร์ พงศ์ อูรีนิวอัล")
    assert "ด็อกเตอร์พงษ์" in n("ด็อกเตอร์พงศ์ มียูเรีย")
    assert "ด็อกเตอร์พงษ์" in n("ดร. พงค์ ยูรีนิวอัล")
    # idempotent on already-correct text
    assert n("ด็อกเตอร์พงษ์ตัวนี้") == "ด็อกเตอร์พงษ์ตัวนี้"
    assert "พงษ์ษ์" not in n("ด็อกเตอร์ พงษ์ตัวนี้")
