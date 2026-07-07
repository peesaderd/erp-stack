"""
SAM3 Client — Prodia Segment Anything Model 3 Integration

Use cases:
  - segment_image: แยก object จากรูปสินค้า (for Carousel / I2V)
  - segment_and_inpaint: แยก object + เปลี่ยน Background
  - track_video_object: Track object ในคลิป (frame-by-frame)

Cost: $0.0011/call
"""

import os
import io
import json
import time
import sys
import logging
import requests
from pathlib import Path
from typing import Optional, List
from PIL import Image

_erp_stack = Path(__file__).parent.parent.parent
if str(_erp_stack) not in sys.path:
    sys.path.insert(0, str(_erp_stack))
from shared_config import PRODIA_TOKEN

logger = logging.getLogger("sam3.client")

PRODIA_BASE = "https://inference.prodia.com/v2"

# ─── Helpers ───────────────────────────────────────────────────────────────

def _headers():
    return {"Authorization": f"Bearer {PRODIA_TOKEN()}"}


def _poll_generic(url: str, headers: dict, max_polls: int = 60, sleep_s: int = 2) -> dict:
    """Poll a Prodia job URL (supports both JSON and binary outputs)."""
    for _ in range(max_polls):
        time.sleep(sleep_s)
        resp = requests.get(url, headers=headers, timeout=30)
        # SAM3 returns multipart/form-data (binary masks)
        ct = resp.headers.get("content-type", "")
        if "multipart" in ct or "image" in ct:
            return {"_raw_multipart": True, "_response": resp}
        try:
            data = resp.json()
        except:
            return {"_raw_binary": True, "_response": resp}
        status = data.get("status", "")
        if status == "completed":
            return data
        elif status in ("failed", "error"):
            raise RuntimeError(f"Prodia job failed: {data}")
    raise TimeoutError(f"Prodia job timed out")


# ─── 1. Segment Image — แยก object ตาม text prompt ────────────────────────

def segment_image(image_path: str, prompt: str = "product",
                  confidence: float = 0.5) -> List[bytes]:
    """
    Segment objects from an image using SAM3 text prompt.

    Args:
        image_path: Path to input image
        prompt: Text describing what to segment ("product", "person", "fish", etc.)
        confidence: Confidence threshold (0.0-1.0, default 0.5)

    Returns:
        List of mask PNG bytes (one per detected instance)

    Cost: ~$0.0011/call
    """
    logger.info(f"SAM3 segment: prompt='{prompt}' confidence={confidence}")

    # Read image
    with open(image_path, "rb") as f:
        image_data = f.read()

    # SAM3 requires multipart upload — image + config
    files = {
        "input": ("image.png", image_data, "image/png"),
        "config": (None, json.dumps({
            "type": "inference.sam3.segment.v1",
            "config": {
                "prompt": prompt,
                "confidence_threshold": confidence,
            }
        }), "application/json"),
    }

    resp = requests.post(f"{PRODIA_BASE}/job", headers=_headers(), files=files, timeout=60)
    resp.raise_for_status()

    # Parse multipart response — returns PNG masks
    # Content-Type: multipart/form-data; boundary=...
    masks = []
    ct = resp.headers.get("content-type", "")

    if "multipart" in ct:
        # Parse boundary
        from email.parser import BytesParser
        from email import policy

        msg = BytesParser(policy=policy.default).parsebytes(resp.content)
        for part in msg.walk():
            if part.get_content_maintype() == "image":
                masks.append(part.get_payload(decode=True))
    else:
        # Single binary response = single mask
        masks.append(resp.content)

    logger.info(f"  SAM3: {len(masks)} mask(s) detected")
    return masks


def mask_to_rgba(image_path: str, masks: List[bytes], output_path: str,
                 mask_index: int = 0) -> str:
    """
    Apply SAM3 mask to original image — returns RGBA with transparent BG.

    Args:
        image_path: Original image path
        masks: List of mask PNG bytes from segment_image()
        output_path: Output PNG path
        mask_index: Which mask to use (default 0 = first detected instance)

    Returns:
        Path to output RGBA image
    """
    original = Image.open(image_path).convert("RGBA")
    mask_img = Image.open(io.BytesIO(masks[mask_index])).convert("L")

    # Resize mask to match original if needed
    if mask_img.size != original.size:
        mask_img = mask_img.resize(original.size, Image.NEAREST)

    # Create transparent image
    result = Image.new("RGBA", original.size, (0, 0, 0, 0))
    result.paste(original, mask=mask_img)
    result.save(output_path, "PNG")

    logger.info(f"  Mask applied -> {output_path}")
    return output_path


# ─── 2. Segment + Track in Video (frame-by-frame) ──────────────────────────

def track_object_in_video(video_path: str, prompt: str = "person",
                          interval_frames: int = 5,
                          max_frames: int = 20) -> List[dict]:
    """
    Track an object type across video frames using SAM3.

    Extracts frames from video, runs SAM3 on each, returns position data.

    Args:
        video_path: Path to video file
        prompt: Object to track ("person", "product", etc.)
        interval_frames: Process every Nth frame (default 5)
        max_frames: Max frames to process (default 20)

    Returns:
        List of {frame, mask_count, masks, timestamp_sec}
        Can be used later for FFmpeg overlay positioning.

    Cost: ~$0.0011/frame
    """
    import subprocess
    import tempfile

    logger.info(f"SAM3 track: '{prompt}' in {video_path} (every {interval_frames}f, max {max_frames})")

    tmp_dir = Path(tempfile.mkdtemp())
    results = []

    try:
        # Get video info
        probe = subprocess.run([
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=width,height,r_frame_rate,nb_frames",
            "-of", "json", video_path
        ], capture_output=True, text=True, check=True)
        info = json.loads(probe.stdout)
        stream = info.get("streams", [{}])[0]
        fps_str = stream.get("r_frame_rate", "30/1")
        fps_num, fps_den = map(int, fps_str.split("/"))
        fps = fps_num / fps_den if fps_den else 30
        width = stream.get("width", 0)
        height = stream.get("height", 0)

        # Extract key frames
        frame_idx = 0
        while frame_idx < max_frames:
            timestamp = (frame_idx * interval_frames) / fps
            frame_path = tmp_dir / f"frame_{frame_idx:04d}.png"

            subprocess.run([
                "ffmpeg", "-y", "-ss", str(timestamp), "-i", video_path,
                "-vframes", "1", "-q:v", "2", str(frame_path)
            ], capture_output=True, check=True)

            if not frame_path.exists():
                break

            # Segment
            try:
                masks = segment_image(str(frame_path), prompt)
                # Get bounding box from first mask
                mask_data = {}
                if masks:
                    mask_img = Image.open(io.BytesIO(masks[0])).convert("L")
                    bbox = mask_img.getbbox()
                    if bbox:
                        mask_data = {
                            "bbox": list(bbox),
                            "center": [(bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2],
                            "width_pct": (bbox[2] - bbox[0]) / width * 100 if width else 0,
                            "height_pct": (bbox[3] - bbox[1]) / height * 100 if height else 0,
                        }

                results.append({
                    "frame": frame_idx,
                    "timestamp_sec": round(timestamp, 2),
                    "mask_count": len(masks),
                    "center": mask_data.get("center", [0, 0]),
                    "bbox": mask_data.get("bbox", []),
                    "width_pct": mask_data.get("width_pct", 0),
                    "height_pct": mask_data.get("height_pct", 0),
                })
                logger.info(f"  Frame {frame_idx} @ {timestamp:.1f}s: {len(masks)} mask(s)")
            except Exception as e:
                logger.warning(f"  Frame {frame_idx} SAM3 error: {e}")

            frame_idx += 1

    finally:
        # Cleanup temp frames
        import shutil
        try:
            shutil.rmtree(tmp_dir)
        except:
            pass

    logger.info(f"  Tracked {len(results)} frames")
    return results


# ─── 3. Typo — Replace object texture/color ────────────────────────────────

def segment_and_typo(image_path: str, object_prompt: str,
                     typo_prompt: str,
                     output_path: str,
                     confidence: float = 0.5) -> str:
    """
    SAM3 + FLUX inpaint: Segment object then change its texture/color.

    Args:
        image_path: Original image
        object_prompt: What to segment ("product", "bag", "shirt")
        typo_prompt: What to change it to ("red", "wooden texture", "metallic")
        output_path: Output image path
        confidence: SAM3 confidence threshold

    Returns:
        Path to output image

    Cost: ~$0.0011 (SAM3) + $0.001-0.003 (FLUX inpaint)
    """
    from prodia_client import generate_inpaint

    logger.info(f"SAM3 typo: '{object_prompt}' -> '{typo_prompt}'")

    # Step 1: Segment
    masks = segment_image(image_path, object_prompt, confidence)
    if not masks:
        raise RuntimeError(f"SAM3: no '{object_prompt}' found in image")

    # Step 2: Use the largest mask
    largest_idx = 0
    largest_area = 0
    for i, m in enumerate(masks):
        mask_img = Image.open(io.BytesIO(m)).convert("L")
        area = mask_img.getbbox()
        if area:
            a = (area[2] - area[0]) * (area[3] - area[1])
            if a > largest_area:
                largest_area = a
                largest_idx = i

    # Step 3: Save mask temporarily
    mask_path = f"/tmp/sam3_mask_{os.urandom(4).hex()}.png"
    with open(mask_path, "wb") as f:
        f.write(masks[largest_idx])

    # Step 4: FLUX inpaint — change object
    # This requires a Prodia inpaint job
    inpaint_type = "inference.flux-fast.schnell.inpaint.v2"
    headers = _headers()

    with open(mask_path, "rb") as img_f, open(mask_path, "rb") as mask_f:
        # Actually we need the image and mask as separate files
        # Read original image
        with open(image_path, "rb") as orig_f:
            image_data = orig_f.read()

        files = {
            "input": ("image.png", image_data, "image/png"),
            "mask": ("mask.png", masks[largest_idx], "image/png"),
            "config": (None, json.dumps({
                "type": inpaint_type,
                "config": {
                    "prompt": f"change to {typo_prompt}, keep original shape",
                    "strength": 0.8,
                }
            }), "application/json"),
        }

        resp = requests.post(f"{PRODIA_BASE}/job", headers=headers, files=files, timeout=120)
        resp.raise_for_status()

        # Poll for result
        ct = resp.headers.get("content-type", "")
        if "multipart" in ct or "image" in ct:
            image_data = resp.content
        elif resp.headers.get("content-type", "").startswith("application/json"):
            data = resp.json()
            job_id = data.get("job", {}).get("id", "") or data.get("id", "")
            if job_id:
                result = _poll_generic(f"{PRODIA_BASE}/job/{job_id}", headers, max_polls=60, sleep_s=3)

    # Cleanup
    try:
        os.unlink(mask_path)
    except:
        pass

    result_path = output_path or image_path.replace(".", "_typo.")
    with open(output_path, "wb") as f:
        f.write(resp.content)

    logger.info(f"  Typo result: {output_path}")
    return output_path


# ─── CLI ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="SAM3 Prodia Client")
    parser.add_argument("action", choices=["segment", "track", "typo"], help="Action")
    parser.add_argument("--image", help="Image path")
    parser.add_argument("--video", help="Video path")
    parser.add_argument("--prompt", default="product", help="SAM3 text prompt")
    parser.add_argument("--typo", help="Typo prompt (for typo action)")
    parser.add_argument("--output", default="./output", help="Output dir")
    parser.add_argument("--confidence", type=float, default=0.5, help="Confidence threshold")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)

    if args.action == "segment":
        masks = segment_image(args.image, args.prompt, args.confidence)
        print(f"{len(masks)} mask(s) detected")
        for i, m in enumerate(masks):
            p = output / f"mask_{i}.png"
            with open(p, "wb") as f:
                f.write(m)
            print(f"  Saved: {p}")

    elif args.action == "track":
        results = track_object_in_video(args.video, args.prompt)
        print(f"Tracked {len(results)} frames")
        with open(output / "track_data.json", "w") as f:
            json.dump(results, f, indent=2)

    elif args.action == "typo":
        result = segment_and_typo(args.image, args.prompt, args.typo, str(output / "typo_result.png"), args.confidence)
        print(f"Saved: {result}")
