"""
Image Triptych Pipeline — 16:9 triptych → 3 panels 9:16 + rembg.

Pipeline:
  1. Generate wide triptych 16:9 via Prodia nano-banana.img2img.v2
     (3 panels side by side: cover + model+product + end scene)
  2. Upscale 2x via local Real-ESRGAN (or Lanczos fallback)
  3. Cut into 3 vertical 9:16 panels
  4. REMBG the requested panel(s) — keep only foreground

Usage:
    python3 modules/image_triptych/pipeline.py \
        --reference /path/to/cover.png \
        --rembg-panel 1 \
        --out-dir /path/to/output

API:
    POST /api/v1/triptych/generate
      body: { prompt, reference_image_url, aspect_ratio="16:9", rembg_panels=[1] }
      returns: { triptych_url, panels: [...], rembg: [...] }
"""
import os
import sys
import json
import argparse
import base64
import io
import uuid
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image

# ─── Config ────────────────────────────────────────────────────────────────

PRODIA_TOKEN = os.environ.get("PRODIA_TOKEN", "")
PRODIA_SYNC = "https://inference.prodia.com/v2/job"
PRODIA_MODEL = "inference.nano-banana.img2img.v2"
PRICE_PER_JOB = 0.039  # USD nano-banana v2

# ─── Prodia client (sync) ──────────────────────────────────────────────────

def prodia_img2img(prompt: str, input_image_b64: str, aspect_ratio: str = "16:9") -> bytes:
    """Call Prodia sync API for nano-banana.img2img.v2 → returns PNG bytes."""
    import requests

    body = {
        "type": PRODIA_MODEL,
        "config": {
            "prompt": prompt,
            "aspect_ratio": aspect_ratio,
        },
    }
    headers = {"Authorization": f"Bearer {PRODIA_TOKEN}", "Accept": "image/png"}

    # Decode b64 → bytes
    if "," in input_image_b64:
        input_image_b64 = input_image_b64.split(",", 1)[1]
    image_bytes = base64.b64decode(input_image_b64)

    files = [
        ("job", ("job.json", json.dumps(body), "application/json")),
        ("input", ("image.png", image_bytes, "image/png")),
    ]
    resp = requests.post(PRODIA_SYNC, headers=headers, files=files, timeout=120)
    resp.raise_for_status()
    return resp.content


# ─── Upscale ───────────────────────────────────────────────────────────────

def upscale_2x(img: Image.Image, use_realesrgan: bool = True) -> Image.Image:
    """Upscale image 2x. Tries Real-ESRGAN (if installed + cached) else Lanczos."""
    if use_realesrgan:
        try:
            from realesrgan import RealESRGANer
            from basicsr.archs.rrdbnet_arch import RRDBNet
            import torch

            model_path = os.environ.get(
                "REALESRGAN_MODEL",
                "/home/openhands/.cache/realesrgan/RealESRGAN_x4plus.pth",
            )
            if not os.path.exists(model_path):
                raise FileNotFoundError(model_path)

            rrdb = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64,
                            num_block=23, num_grow_ch=32, scale=4)
            upsampler = RealESRGANer(
                scale=4, model_path=model_path, model=rrdb,
                half=False, device="cpu",
            )
            arr = np.array(img.convert("RGB"))
            out, _ = upsampler.enhance(arr, outscale=0.5)  # 4x model * 0.5 = 2x
            return Image.fromarray(out)
        except Exception as e:
            print(f"  Real-ESRGAN unavailable ({e.__class__.__name__}) → Lanczos fallback")

    w, h = img.size
    return img.resize((w * 2, h * 2), Image.LANCZOS)


# ─── Cut to 3 panels ───────────────────────────────────────────────────────

def cut_to_panels(img: Image.Image, n: int = 3) -> list:
    """Cut wide image into N equal-width vertical panels."""
    w, h = img.size
    panel_w = w // n
    panels = []
    for i in range(n):
        p = img.crop((i * panel_w, 0, (i + 1) * panel_w, h))
        panels.append(p)
    return panels


# ─── REMBG (multiple models) ───────────────────────────────────────────────

# Available rembg models (verified 2026-08-16, rembg==2.0.76)
REMBG_MODELS = {
    "u2net": "176 MB — general purpose, fast",
    "u2netp": "4.7 MB — lightweight",
    "silueta": "43 MB — general, sharper edges",
    "isnet-general-use": "168 MB — high quality",
    "birefnet-general": "973 MB — BiRefNet 2 (highest quality)",
    "birefnet-general-lite": "224 MB — BiRefNet lite (fast + good)",
    "sam": "375 MB — SAM ViT-B (segment anything, slow)",
}


def rembg(img: Image.Image, model: str = "birefnet-general-lite") -> Image.Image:
    """Background removal → RGBA, foreground=opaque, background=transparent.

    Args:
        img: PIL Image (RGB).
        model: rembg model name. Default 'birefnet-general-lite' (fast + good).
    """
    from rembg import remove, new_session
    session = new_session(model)
    return remove(img.convert("RGB"), session=session)


# ─── Pipeline entry point ──────────────────────────────────────────────────

def run_triptych(
    prompt: str,
    reference_image_path: str,
    out_dir: str,
    aspect_ratio: str = "16:9",
    rembg_panels: list = None,
    rembg_model: str = "birefnet-general-lite",
    use_realesrgan: bool = False,
) -> dict:
    """
    Full pipeline:
      reference + prompt → Prodia triptych 16:9 → upscale 2x → 3 panels → rembg.

    Args:
        prompt: full scene description for the triptych (3 panels).
        reference_image_path: input image for img2img (the cover page).
        out_dir: where to write outputs.
        aspect_ratio: "16:9" (default).
        rembg_panels: list of panel indices (1,2,3) to rembg; default = [1].
        rembg_model: one of REMBG_MODELS; default = 'birefnet-general-lite'.
        use_realesrgan: try Real-ESRGAN first, fallback to Lanczos.

    Returns:
        dict with paths:
          {
            "triptych": "<path>.png",          # 16:9 wide
            "triptych_2x": "<path>_2x.png",    # 2x upscale
            "panels": ["p1.png", "p2.png", "p3.png"],
            "rembg": {1: "p1_rmbg.png", ...}   # if requested
          }
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rembg_panels = rembg_panels or [1]

    # ── 1. Prodia triptych ─────────────────────────────────────────────
    print(f"[1/4] Prodia img2img → 16:9 triptych (${PRICE_PER_JOB})", flush=True)
    with open(reference_image_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode()
    triptych_bytes = prodia_img2img(prompt, img_b64, aspect_ratio)
    triptych_path = out_dir / "triptych_16x9.png"
    triptych_path.write_bytes(triptych_bytes)
    print(f"  → {triptych_path} ({len(triptych_bytes)//1024} KB)", flush=True)

    # ── 2. Upscale 2x ─────────────────────────────────────────────────
    print(f"[2/4] Upscale 2x ({'Real-ESRGAN' if use_realesrgan else 'Lanczos'})", flush=True)
    img = Image.open(triptych_path).convert("RGB")
    img_2x = upscale_2x(img, use_realesrgan)
    triptych_2x_path = out_dir / "triptych_2x.png"
    img_2x.save(triptych_2x_path, "PNG", optimize=True)
    print(f"  → {triptych_2x_path} ({img_2x.size})", flush=True)

    # ── 3. Cut to 3 panels ────────────────────────────────────────────
    print(f"[3/4] Cut to 3 vertical panels (9:16)", flush=True)
    panels = cut_to_panels(img_2x, n=3)
    panel_paths = []
    for i, p in enumerate(panels, start=1):
        path = out_dir / f"panel_{i}.png"
        p.save(path, "PNG", optimize=True)
        panel_paths.append(str(path))
        print(f"  → panel {i}: {p.size} ({path})", flush=True)

    # ── 4. REMBG requested panels ──────────────────────────────────────
    rembg_paths = {}
    if rembg_panels:
        print(f"[4/4] REMBG panels: {rembg_panels} (model={rembg_model})", flush=True)
        for idx in rembg_panels:
            p = panels[idx - 1]
            rmbg = rembg(p, model=rembg_model)
            path = out_dir / f"panel_{idx}_rmbg.png"
            rmbg.save(path, "PNG")
            rembg_paths[idx] = str(path)
            print(f"  → panel {idx} rembg: {rmbg.size} mode={rmbg.mode}", flush=True)

    return {
        "triptych": str(triptych_path),
        "triptych_2x": str(triptych_2x_path),
        "panels": panel_paths,
        "rembg": rembg_paths,
        "price_usd": PRICE_PER_JOB,
    }


# ─── CLI ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Image triptych pipeline (Prodia + upscale + cut + rembg)")
    ap.add_argument("--prompt", required=True, help="triptych scene prompt")
    ap.add_argument("--reference", required=True, help="path to reference image")
    ap.add_argument("--out-dir", required=True, help="output directory")
    ap.add_argument("--aspect-ratio", default="16:9")
    ap.add_argument("--rembg-panel", type=int, action="append", default=None,
                    help="panel index(es) to rembg, can repeat (default: [1])")
    ap.add_argument("--no-realesrgan", action="store_true",
                    help="skip Real-ESRGAN, use Lanczos")
    ap.add_argument("--rembg-model", default="birefnet-general-lite",
                    choices=list(REMBG_MODELS.keys()),
                    help="rembg model to use (default: birefnet-general-lite)")
    args = ap.parse_args()

    result = run_triptych(
        prompt=args.prompt,
        reference_image_path=args.reference,
        out_dir=args.out_dir,
        aspect_ratio=args.aspect_ratio,
        rembg_panels=args.rembg_panel,
        rembg_model=args.rembg_model,
        use_realesrgan=not args.no_realesrgan,
    )
    print("\n=== RESULT ===")
    print(json.dumps(result, indent=2))
