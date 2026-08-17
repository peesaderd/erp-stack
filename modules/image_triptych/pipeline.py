"""
Image Triptych Pipeline — Prodia-only (no local deps)
========================================================

Pipeline: 16:9 triptych → 2x upscale (Prodia) → 3 panels 9:16 → remove_background (Prodia)

All AI work goes through Prodia sync API:
  - inference.nano-banana.img2img.v2 (1 call, $0.039) — triptych 16:9
  - inference.upscale.v1 (sync, $0.0010) — 2x upscale
  - inference.remove-background.v1 (sync, $0.0025) — per-panel BG removal

NO local model deps (no rembg, no realesrgan, no Pillow Lanczos).
Pillow is used only for panel cropping (mechanical split, not AI).

Total cost per pipeline run:
  - 1 triptych (Nano Banana):     $0.039
  - 1 upscale (1344×768→2688×1536): $0.001
  - 3 remove_bg:                  $0.0025 × 3 = $0.0075 (or 0 if not requested)
  Default (all 3 panels):         ~$0.048
"""

from __future__ import annotations

import base64
import io
import json
import os
import re
import time
import uuid
from pathlib import Path
from typing import List, Optional, Tuple

import requests
from PIL import Image

# Use the existing prodia_client (commit caa0ec8f)
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from prodia_client import ProdiaV2Client


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _bytes_to_pil(data: bytes) -> Image.Image:
    return Image.open(io.BytesIO(data))


def _pil_to_bytes(img: Image.Image, fmt: str = "PNG", quality: int = 95) -> bytes:
    buf = io.BytesIO()
    if fmt.upper() == "JPEG":
        img.save(buf, "JPEG", quality=quality)
    else:
        img.save(buf, fmt)
    return buf.getvalue()


def _load_input_image(reference: str) -> bytes:
    """Load reference image from URL, file path, or data URL. Return PNG bytes."""
    if not reference:
        raise ValueError("reference_image is required")

    # data URL: data:image/png;base64,...
    if reference.startswith("data:"):
        b64 = reference.split(",", 1)[1]
        return base64.b64decode(b64)

    # file path
    if os.path.exists(reference):
        with open(reference, "rb") as f:
            return f.read()

    # URL
    if reference.startswith("http://") or reference.startswith("https://"):
        resp = requests.get(reference, timeout=30)
        resp.raise_for_status()
        return resp.content

    # else treat as base64
    try:
        return base64.b64decode(reference)
    except Exception as e:
        raise ValueError(f"Can't decode reference_image: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# Prodia sync wrappers (used by pipeline)
# ─────────────────────────────────────────────────────────────────────────────

def prodia_img2img(
    prompt: str,
    input_image: bytes,
    client: ProdiaV2Client,
    job_type: str = "inference.nano-banana.img2img.v2",
) -> bytes:
    """Generate triptych via Nano Banana img2img (SYNC, like upscale).
    
    VALIDATED 2026-08-17: nano-banana uses sync /v2/job endpoint (NOT async).
    Multipart: 'input' (image/jpeg) + 'job' JSON.
    Response: multipart with 'job' JSON + 'output' (image bytes).
    """
    import uuid as _uuid

    boundary = "----FormBoundary" + _uuid.uuid4().hex

    # Convert PNG → JPEG
    if input_image.startswith(b"\x89PNG"):
        im = Image.open(io.BytesIO(input_image)).convert("RGB")
        jpg_buf = io.BytesIO()
        im.save(jpg_buf, "JPEG", quality=95)
        img_bytes = jpg_buf.getvalue()
    else:
        img_bytes = input_image

    job_json = json.dumps({"type": job_type, "config": {"prompt": prompt}})

    body = (
        f"--{boundary}\r\n"
        f"Content-Disposition: form-data; name=\"input\"; filename=\"image.jpg\"\r\n"
        f"Content-Type: image/jpeg\r\n\r\n"
    ).encode() + img_bytes + b"\r\n"
    body += (
        f"--{boundary}\r\n"
        f"Content-Disposition: form-data; name=\"job\"; filename=\"job.json\"\r\n"
        f"Content-Type: application/json\r\n\r\n"
        f"{job_json}\r\n"
        f"--{boundary}--\r\n"
    ).encode()

    resp = client._session.post(
        f"{client.base_url}/job",
        data=body,
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Accept": "multipart/form-data",
        },
        timeout=180,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"img2img failed ({resp.status_code}): {resp.text[:300]}")

    ct = resp.headers.get("Content-Type", "")
    m = re.search(r'boundary=([^;]+)', ct)
    if not m:
        raise RuntimeError(f"No boundary in img2img response: {ct}")
    rb = m.group(1).strip().strip('"').encode()

    output_bytes = None
    for p in resp.content.split(b"--" + rb):
        head_end = p.find(b"\r\n\r\n")
        if head_end < 0:
            continue
        head = p[:head_end]
        data = p[head_end + 4:].rstrip(b"\r\n")
        if b'name="output"' in head:
            ct_m = re.search(rb'Content-Type:\s*([^\r\n]+)', head)
            if ct_m and b'image/' in ct_m.group(1).lower():
                output_bytes = data
                break

    if output_bytes is None:
        raise RuntimeError("No output in img2img response")
    return output_bytes


def prodia_upscale(
    input_image: bytes,
    factor: int,
    client: ProdiaV2Client,
) -> bytes:
    """Upscale image via Prodia sync API (inference.upscale.v1)."""
    return client.upscale_image(input_image, factor=factor)["output_bytes"]


def prodia_remove_background(
    input_image: bytes,
    client: ProdiaV2Client,
) -> Tuple[bytes, bytes]:
    """Remove background via Prodia sync API.
    Returns (foreground_rgba_png, mask_grayscale_png)."""
    import uuid as _uuid

    # Inline sync call (mirrors prodia_client.upscale_image pattern)
    boundary = "----FormBoundary" + _uuid.uuid4().hex

    # Convert PNG → JPEG (prodia-js assumes image/jpeg)
    if input_image.startswith(b"\x89PNG"):
        im = Image.open(io.BytesIO(input_image)).convert("RGB")
        jpg_buf = io.BytesIO()
        im.save(jpg_buf, "JPEG", quality=95)
        img_bytes = jpg_buf.getvalue()
    else:
        img_bytes = input_image

    job_json = '{"type":"inference.remove-background.v1","config":{}}'
    body = (
        f"--{boundary}\r\n"
        f"Content-Disposition: form-data; name=\"input\"; filename=\"image.jpg\"\r\n"
        f"Content-Type: image/jpeg\r\n\r\n"
    ).encode() + img_bytes + b"\r\n"
    body += (
        f"--{boundary}\r\n"
        f"Content-Disposition: form-data; name=\"job\"; filename=\"job.json\"\r\n"
        f"Content-Type: application/json\r\n\r\n"
        f"{job_json}\r\n"
        f"--{boundary}--\r\n"
    ).encode()

    resp = client._session.post(
        f"{client.base_url}/job",
        data=body,
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Accept": "multipart/form-data",
        },
        timeout=180,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"remove-bg failed ({resp.status_code}): {resp.text[:300]}")

    ct = resp.headers.get("Content-Type", "")
    m = re.search(r'boundary=([^;]+)', ct)
    if not m:
        raise RuntimeError(f"No boundary in response: {ct}")
    rb = m.group(1).strip().strip('"').encode()

    foreground = None
    mask = None
    parts = resp.content.split(b"--" + rb)
    for p in parts:
        head_end = p.find(b"\r\n\r\n")
        if head_end < 0:
            continue
        head = p[:head_end]
        data = p[head_end + 4:].rstrip(b"\r\n")
        if b'name="foreground"' in head or (b'name="output"' in head and b'image/png' in head):
            # First image/png part is foreground, second is mask
            if foreground is None:
                foreground = data
            else:
                mask = data

    if foreground is None:
        raise RuntimeError("No foreground output in remove-bg response")
    if mask is None:
        # some endpoints return only foreground; mask is optional
        mask = foreground  # fallback
    return foreground, mask


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline
# ─────────────────────────────────────────────────────────────────────────────

def run_triptych(
    prompt: str,
    reference_image: str,
    out_dir: str,
    aspect_ratio: str = "16:9",
    rembg_panels: Optional[List[int]] = None,
    n_panels: int = 3,
    upscale_factor: int = 2,
    client: Optional[ProdiaV2Client] = None,
) -> dict:
    """
    Full pipeline:
      1. Generate 16:9 triptych (Nano Banana, 1 call)
      2. Upscale 2x (Prodia sync)
      3. Cut to N vertical panels (Pillow — mechanical, not AI)
      4. Remove background from selected panels (Prodia sync)

    Args:
        prompt: text prompt for triptych
        reference_image: URL, file path, or base64/data URL of source
        out_dir: where to save outputs
        aspect_ratio: 16:9 (default), 9:16, 1:1
        rembg_panels: list of panel indices (1-based) to remove bg from
        n_panels: number of vertical panels (default 3)
        upscale_factor: 2, 4, or 8
        client: optional ProdiaV2Client (created from env if None)

    Returns:
        dict with paths, sizes, costs, durations
    """
    if client is None:
        token = os.environ.get("PRODIA_TOKEN", "")
        if not token:
            env_file = Path(__file__).parent.parent.parent / ".env"
            if env_file.exists():
                token = env_file.read_text().split("PRODIA_TOKEN=")[1].split()[0].strip('"').strip("'")
        client = ProdiaV2Client(token)

    out_dir_path = Path(out_dir)
    out_dir_path.mkdir(parents=True, exist_ok=True)

    rembg_panels = rembg_panels or []
    costs = []
    durations = {}

    # ── Step 1: Generate triptych (Nano Banana img2img, async job) ──
    t0 = time.time()
    input_bytes = _load_input_image(reference_image)
    triptych_bytes = prodia_img2img(prompt, input_bytes, client)
    durations["img2img"] = time.time() - t0
    costs.append({"step": "img2img", "usd": 0.039, "job_type": "inference.nano-banana.img2img.v2"})

    triptych_path = out_dir_path / "triptych.png"
    triptych_path.write_bytes(triptych_bytes)

    triptych_img = _bytes_to_pil(triptych_bytes).convert("RGB")
    w, h = triptych_img.size
    # Triptych may not be exact 16:9 due to model rounding; just warn, don't fail
    expected_ratio = 16 / 9
    actual_ratio = w / h
    if abs(actual_ratio - expected_ratio) > 0.1:
        print(f"WARNING: triptych not 16:9 — got {w}x{h} ratio={actual_ratio:.3f}")

    # ── Step 2: Upscale 2x (Prodia sync) ──
    t0 = time.time()
    upscaled_bytes = prodia_upscale(triptych_bytes, factor=upscale_factor, client=client)
    durations["upscale"] = time.time() - t0
    costs.append({"step": "upscale", "usd": 0.001, "job_type": "inference.upscale.v1"})

    upscaled_path = out_dir_path / "triptych_2x.png"
    upscaled_path.write_bytes(upscaled_bytes)
    upscaled_img = _bytes_to_pil(upscaled_bytes).convert("RGB")

    # ── Step 3: Cut to N vertical panels (Pillow — mechanical split) ──
    panel_w = upscaled_img.width // n_panels
    panels = []
    for i in range(n_panels):
        left = i * panel_w
        right = left + panel_w if i < n_panels - 1 else upscaled_img.width
        panel = upscaled_img.crop((left, 0, right, upscaled_img.height))
        panel_path = out_dir_path / f"panel_{i+1}_2x.png"
        panel.save(panel_path, "PNG")
        panels.append({"index": i + 1, "path": str(panel_path), "size": panel.size})

    # ── Step 4: Remove background from selected panels (Prodia sync) ──
    rembg_results = {}
    for panel_idx in rembg_panels:
        if panel_idx < 1 or panel_idx > n_panels:
            continue
        panel_path = out_dir_path / f"panel_{panel_idx}_2x.png"
        t0 = time.time()
        fg_bytes, mask_bytes = prodia_remove_background(panel_path.read_bytes(), client)
        durations[f"rembg_panel_{panel_idx}"] = time.time() - t0
        costs.append({"step": f"rembg_{panel_idx}", "usd": 0.0025, "job_type": "inference.remove-background.v1"})

        fg_path = out_dir_path / f"panel_{panel_idx}_rmbg.png"
        mask_path = out_dir_path / f"panel_{panel_idx}_mask.png"
        fg_path.write_bytes(fg_bytes)
        mask_path.write_bytes(mask_bytes)
        rembg_results[panel_idx] = {
            "foreground": str(fg_path),
            "mask": str(mask_path),
            "size": _bytes_to_pil(fg_bytes).size,
        }

    total_usd = sum(c["usd"] for c in costs)
    return {
        "triptych": str(triptych_path),
        "triptych_2x": str(upscaled_path),
        "panels": panels,
        "rembg": rembg_results,
        "costs": costs,
        "total_usd": round(total_usd, 4),
        "durations_sec": {k: round(v, 2) for k, v in durations.items()},
    }


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    import json

    ap = argparse.ArgumentParser(description="Run triptych pipeline (Prodia-only)")
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--reference", required=True, help="path/URL/base64/data URL")
    ap.add_argument("--out", default="/tmp/triptych_out", help="output directory")
    ap.add_argument("--aspect-ratio", default="16:9")
    ap.add_argument("--rembg-panels", default="1", help="comma-separated panel indices (1-based)")
    ap.add_argument("--n-panels", type=int, default=3)
    ap.add_argument("--upscale-factor", type=int, default=2, choices=[2, 4, 8])
    args = ap.parse_args()

    panels_list = [int(x) for x in args.rembg_panels.split(",") if x.strip()]

    result = run_triptych(
        prompt=args.prompt,
        reference_image=args.reference,
        out_dir=args.out,
        aspect_ratio=args.aspect_ratio,
        rembg_panels=panels_list,
        n_panels=args.n_panels,
        upscale_factor=args.upscale_factor,
    )

    print(json.dumps(result, indent=2))
