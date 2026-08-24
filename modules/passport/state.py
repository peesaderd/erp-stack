"""
passport_state.py — Single Source of Truth for per-session image state (owner refactor 2026-08-24)

Problem this solves (today's recurring regressions):
    Multiple endpoints each GUESSED which stored file is "current"
    (_flux_raw/_passport/_transparent/_bg/_cropped) with different priority
    orders -> fixes kept silently undoing each other ("ดีๆ แล้วหาย").

Rule now:
    ONE ledger file `{sid}_state.json` records the current kind.
    Every write goes through save_current(); every read through load_current().
    No endpoint may touch state files directly anymore.

Kinds:
    raw         -> _passport.jpg        (fresh FLUX output / upload)
    transparent -> _transparent.png     (after remove-bg; alpha preserved)
    bg          -> _bg.jpg              (after apply-bg; color baked)

Consumer view:
    _passport.jpg is ALWAYS kept in sync as the RGB consumer copy
    (transparent -> white composite) so legacy readers (download URLs,
    frontend previews, gallery) never change.

Old sessions without a ledger are migrated ONCE by newest-mtime
(same rule shipped 2026-08-24 morning) and then behave deterministically.
"""
from __future__ import annotations

import json
import os
import time
import logging
from pathlib import Path
from typing import Optional, Tuple, Union

import cv2
import numpy as np

logger = logging.getLogger("passport.state")

VALID_KINDS = ("raw", "transparent", "bg")

# kind -> canonical filename
CANONICAL = {
    "raw": "{sid}_passport.jpg",
    "transparent": "{sid}_transparent.png",
    "bg": "{sid}_bg.jpg",
}

# migration candidates, newest-mtime wins (legacy compat, read-only)
_MIGRATION_ORDER = (
    "{sid}_bg.jpg",
    "{sid}_transparent.png",
    "{sid}_flux_raw.jpg",
    "{sid}_passport.jpg",
    "{sid}_cropped.jpg",   # very old sessions
)


def _storage(storage_dir: Union[str, Path]) -> Path:
    return Path(storage_dir)


def _ledger_path(sid: str, storage_dir: Union[str, Path]) -> Path:
    return _storage(storage_dir) / f"{sid}_state.json"


def _atomic_write_json(path: Path, data: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data), encoding="utf-8")
    os.replace(tmp, path)


def invalidate_recrop_base(sid: str, storage_dir: Union[str, Path]) -> None:
    """Drop the cached pristine snapshot whenever state changes."""
    (_storage(storage_dir) / f"{sid}_recrop_base.png").unlink(missing_ok=True)


def read_state(sid: str, storage_dir: Union[str, Path]) -> Optional[dict]:
    p = _ledger_path(sid, storage_dir)
    if not p.exists():
        return None
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        if d.get("kind") in VALID_KINDS:
            return d
    except Exception:
        pass
    return None


def write_state(sid: str, kind: str, storage_dir: Union[str, Path]) -> None:
    assert kind in VALID_KINDS, f"bad kind {kind}"
    _atomic_write_json(
        _ledger_path(sid, storage_dir),
        {"kind": kind, "ts": time.time(), "file": CANONICAL[kind].format(sid=sid)},
    )


def current_path(sid: str, storage_dir: Union[str, Path]) -> Optional[Path]:
    """Path of the canonical file for the CURRENT state (no reading of pixels)."""
    st = read_state(sid, storage_dir)
    if st:
        p = _storage(storage_dir) / st["file"]
        return p if p.exists() else None
    return _migrate(sid, storage_dir)[0]


def _migrate(sid: str, storage_dir: Union[str, Path]) -> Tuple[Optional[Path], Optional[str]]:
    """One-time migration for pre-ledger sessions: newest mtime wins."""
    sdir = _storage(storage_dir)
    cand = [(sdir / n.format(sid=sid)) for n in _MIGRATION_ORDER]
    cand = [p for p in cand if p.exists()]
    if not cand:
        return None, None
    newest = max(cand, key=lambda p: p.stat().st_mtime)
    kind = _kind_from_name(newest.name)
    write_state(sid, kind, storage_dir)
    logger.info(f"state migrated {sid} -> {kind} ({newest.name})")
    return newest, kind


def _kind_from_name(filename: str) -> str:
    if "_transparent" in filename:
        return "transparent"
    if "_bg." in filename or "_bg_" in filename:
        return "bg"
    return "raw"


def load_current(
    sid: str, storage_dir: Union[str, Path], flags: int = cv2.IMREAD_COLOR
) -> Tuple[Optional[np.ndarray], Optional[str]]:
    """Read CURRENT image honoring the ledger. flags=IMREAD_UNCHANGED keeps alpha."""
    p, kind = _resolve(sid, storage_dir)
    if p is None:
        return None, None
    img = cv2.imread(str(p), flags)
    if img is None:
        logger.error(f"unreadable current image {p}")
        return None, None
    return img, kind


def _resolve(sid: str, storage_dir: Union[str, Path]) -> Tuple[Optional[Path], Optional[str]]:
    st = read_state(sid, storage_dir)
    sdir = _storage(storage_dir)
    if st:
        p = sdir / st["file"]
        if p.exists():
            return p, st["kind"]
        # ledger points at missing file -> fall back to migration
    return _migrate(sid, storage_dir)


def _white_composite(rgba: np.ndarray) -> np.ndarray:
    """Flatten RGBA onto white -> BGR uint8."""
    if rgba.ndim == 2 or rgba.shape[2] < 4:
        return cv2.cvtColor(rgba, cv2.COLOR_BGR2RGB) if rgba.ndim == 3 else cv2.cvtColor(rgba, cv2.COLOR_GRAY2BGR)
    alpha = rgba[:, :, 3:4].astype(np.float32) / 255.0
    rgb = rgba[:, :, :3].astype(np.float32)
    comp = rgb * alpha + 255.0 * (1.0 - alpha)
    return np.clip(comp, 0, 255).astype(np.uint8)


def save_current(
    sid: str,
    data: Union[np.ndarray, bytes],
    kind: str,
    storage_dir: Union[str, Path],
    jpg_quality: int = 95,
) -> Path:
    """
    THE only way endpoints may persist session state.

    - data ndarray: BGR (or BGRA when kind=transparent)
    - data bytes  : encoded file content (png for transparent, jpg otherwise)
    Writes canonical file, syncs _passport.jpg consumer view,
    invalidates recrop base, updates ledger atomically.
    """
    assert kind in VALID_KINDS, f"bad kind {kind}"
    sdir = _storage(storage_dir)
    sdir.mkdir(parents=True, exist_ok=True)

    canon = sdir / CANONICAL[kind].format(sid=sid)

    if isinstance(data, bytes):
        canon.write_bytes(data)
    else:
        ok = cv2.imwrite(str(canon), data)
        if not ok:
            raise IOError(f"failed writing {canon}")

    # consumer view sync
    passport = sdir / f"{sid}_passport.jpg"
    if kind == "transparent":
        if isinstance(data, bytes):
            rgba = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_UNCHANGED)
        else:
            rgba = data
        if rgba is not None and rgba.ndim == 3 and rgba.shape[2] == 4:
            bgr = _white_composite(rgba)
            cv2.imwrite(str(passport), bgr, [cv2.IMWRITE_JPEG_QUALITY, jpg_quality])
        else:
            # not actually alpha -> just copy
            if isinstance(data, bytes):
                passport.write_bytes(data)
            else:
                cv2.imwrite(str(passport), data, [cv2.IMWRITE_JPEG_QUALITY, jpg_quality])
    elif kind == "raw":
        # raw IS the passport file already; nothing extra
        pass
    else:  # bg
        if isinstance(data, bytes):
            passport.write_bytes(data)
        else:
            cv2.imwrite(str(passport), data, [cv2.IMWRITE_JPEG_QUALITY, jpg_quality])

    invalidate_recrop_base(sid, storage_dir)
    write_state(sid, kind, storage_dir)
    return canon
