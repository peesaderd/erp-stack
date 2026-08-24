"""
Regression suite for passport SSOT state (owner refactor 2026-08-24).

Guards the EXACT bug class from 2026-08-24 morning:
    endpoints guessing "current image" from scattered files with different
    priority orders -> fixes silently undoing each other.

Run:  cd /home/openhands/erp-stack && python3 -m pytest modules/passport/test_state.py -q
"""
import os
import time

import cv2
import numpy as np
import pytest

from state import (
    VALID_KINDS,
    current_path,
    invalidate_recrop_base,
    load_current,
    read_state,
    save_current,
)


def mk_bgr(w=40, h=50, color=(200, 100, 50)):
    return np.full((h, w, 3), color[::-1], dtype=np.uint8)  # BGR


def mk_bgra(w=40, h=50, alpha=255):
    img = np.zeros((h, w, 4), dtype=np.uint8)
    img[:, :, :3] = (50, 100, 200)
    img[:, :, 3] = alpha
    return img


# ── roundtrip per kind ──
@pytest.mark.parametrize("kind,file", [
    ("raw", "s_passport.jpg"),
    ("transparent", "s_transparent.png"),
    ("bg", "s_bg.jpg"),
])
def test_roundtrip(tmp_path, kind, file):
    img = mk_bgra() if kind == "transparent" else mk_bgr()
    save_current("s", img, kind, tmp_path)
    p = current_path("s", tmp_path)
    assert p is not None and p.name == file
    st = read_state("s", tmp_path)
    assert st["kind"] == kind
    out, k = load_current("s", tmp_path)
    assert k == kind and out is not None and out.shape[:2] == img.shape[:2]


# ── consumer view: _passport.jpg always synced ──
def test_bg_syncs_passport(tmp_path):
    bgr = mk_bgr(color=(10, 20, 30))
    save_current("c1", bgr, "bg", tmp_path)
    pp = tmp_path / "c1_passport.jpg"
    assert pp.exists()
    assert np.abs(cv2.imread(str(pp)).astype(int) - bgr.astype(int)).max() <= 3


def test_transparent_white_composite(tmp_path):
    rgba = mk_bgra(alpha=0)          # fully transparent -> passport must be white
    rgba[10:20, 10:20, 3] = 255      # opaque patch
    save_current("c2", rgba, "transparent", tmp_path)
    pp = cv2.imread(str(tmp_path / "c2_passport.jpg"))
    assert pp[5, 5].min() >= 250                 # white outside subject
    assert int(pp[15, 15][2]) >= 195 and abs(int(pp[15, 15][0]) - 50) <= 3   # BGR(50,100,200)


# ── recrop base invalidation centralized ──
def test_save_invalidates_recrop_base(tmp_path):
    base = tmp_path / "x_recrop_base.png"
    cv2.imwrite(str(base), mk_bgr())
    save_current("x", mk_bgr(), "raw", tmp_path)
    assert not base.exists()


# ── one-time legacy migration: newest mtime wins ──
def test_migration_newest_mtime(tmp_path):
    cv2.imwrite(str(tmp_path / "m_transparent.png"), mk_bgra())
    time.sleep(0.01)
    cv2.imwrite(str(tmp_path / "m_bg.jpg"), mk_bgr())
    p, kind = current_path("m", tmp_path), None
    st = read_state("m", tmp_path)
    assert st["kind"] == "bg" and p.name == "m_bg.jpg"


# ── 🔴 THE GUARD: ledger BEATS mtime after migration ──
# (today's bug: newer transparent silently replaced applied bg)
def test_ledger_overrides_mtime(tmp_path):
    save_current("g", mk_bgr(color=(5, 5, 240)), "bg", tmp_path)
    time.sleep(0.01)
    # sneaky newer transparent file appears AFTER state was set
    cv2.imwrite(str(tmp_path / "g_transparent.png"), mk_bgra())
    p = current_path("g", tmp_path)
    assert p.name == "g_bg.jpg"          # ledger wins, NOT newest mtime
    _, kind = load_current("g", tmp_path)
    assert kind == "bg"


# ── invalid kind rejected ──
def test_bad_kind(tmp_path):
    with pytest.raises(AssertionError):
        save_current("z", mk_bgr(), "cropped", tmp_path)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
