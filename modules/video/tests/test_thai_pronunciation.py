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
