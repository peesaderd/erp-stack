#!/usr/bin/env python3
"""
Bridge: Prodia Images → TUS Video Pipeline
============================================
ดึงรูปที่มีอยู่แล้ว (จาก Prodia, URL, หรือ local path)
ส่งเข้า pipeline โดยไม่ต้อง gen รูปใหม่

Usage:
  # Single feed
  python feed_pipeline.py --image http://localhost:8110/storage/images/nano_xxx.png \\
                          --product "Vitamin C Serum"

  # Batch scan: หารูปใน image-gen storage ที่ยังไม่เคยเข้า pipeline
  python feed_pipeline.py --batch --product "Vitamin C" --description "Brightening serum"

  # Feed with full product info
  python feed_pipeline.py --image /path/to/image.png \\
                          --product "La Glace" \\
                          --description "Moisturizing cream" \\
                          --recipe tus --duration 10 --ugc-style holding
"""

import os
import sys
import json
import time
import uuid
import logging
import argparse
from pathlib import Path

# ─── Path setup — imports pipeline_affiliate โดยตรง ──
_this_dir = Path(__file__).resolve().parent
_modules_root = _this_dir  # modules/video/
_erp_stack = _modules_root.parent.parent  # erp-stack/
if str(_erp_stack) not in sys.path:
    sys.path.insert(0, str(_erp_stack))

from pipeline_affiliate import run_pipeline
from pipeline_logger import logger as pl_logger

# ─── Config ────────────────────────────────────────────────────────────────
TUS_STORAGE = _erp_stack / "tiktok-ugc-studio" / "storage"
TUS_IMAGES = TUS_STORAGE / "images"
STATE_FILE = _this_dir / ".feed_pipeline_state.json"

# image-gen storage (8110)
IMAGE_GEN_DIR = _erp_stack / "modules" / "image" / "storage" / "images"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [feed_pipeline] %(levelname)s: %(message)s",
)
logger = logging.getLogger("feed_pipeline")


# ═══════════════════════════════════════════════════════════════════════════
# State tracking — กันซ้ำ
# ═══════════════════════════════════════════════════════════════════════════

def _load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            pass
    return {"processed": []}

def _save_state(state: dict):
    STATE_FILE.write_text(json.dumps(state, indent=2))


# ═══════════════════════════════════════════════════════════════════════════
# Batch scan: หารูปใน image-gen storage ที่ยังไม่เคยเข้า pipeline
# ═══════════════════════════════════════════════════════════════════════════

def scan_unprocessed_images() -> list:
    """Scan image-gen storage, return list of (filename, url) ที่ยังไม่เคย process."""
    state = _load_state()
    processed = set(state.get("processed", []))
    
    candidates = []
    for f in sorted(IMAGE_GEN_DIR.glob("*.png")):
        if f.name in processed:
            continue
        url = f"http://localhost:8110/storage/images/{f.name}"
        candidates.append((f.name, str(f), url))
    
    return candidates


# ═══════════════════════════════════════════════════════════════════════════
# Feed single image
# ═══════════════════════════════════════════════════════════════════════════

def feed_single(
    image_url: str,
    product_name: str,
    description: str = "",
    recipe: str = "tus",
    duration: int = 8,
    ugc_style: str = "holding",
) -> dict:
    """ส่งรูปที่มีอยู่แล้วเข้า pipeline"""
    
    logger.info(f"Feeding image: {image_url}")
    logger.info(f"  Product: {product_name}")
    logger.info(f"  Recipe:  {recipe}, {duration}s, style={ugc_style}")
    
    start = time.time()
    
    result = run_pipeline(
        product_name=product_name,
        product_image="",  # ไม่ต้องใช้ reference image
        recipe_name=recipe,
        voice="Aoede",
        bgm_style="chill_loft",
        description=description,
        ugc_style=ugc_style,
        duration=duration,
        existing_image=image_url,  # ← bypass Step 5!
    )
    
    elapsed = time.time() - start
    logger.info(f"✅ Done in {elapsed:.1f}s")
    logger.info(f"   Final video: {result['final_path']}")
    logger.info(f"   Cost: ${result['cost_estimate']}")
    
    return result


# ═══════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Bridge: Prodia images → TUS Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # รูปเดียว
  python feed_pipeline.py --image http://localhost:8110/storage/images/nano_xxx.png --product "Vitamin C"

  # รูป local
  python feed_pipeline.py --image /path/to/image.png --product "La Glace" --duration 10

  # Batch: scan image-gen storage ทีเดียว
  python feed_pipeline.py --batch --product "Auto Feed" --recipe tus
        """
    )
    
    # Input
    parser.add_argument("--image", help="URL หรือ path ของรูปที่มีอยู่แล้ว")
    parser.add_argument("--batch", action="store_true", help="Scan image-gen storage หารูปที่ยังไม่ process")
    
    # Product info
    parser.add_argument("--product", default="สินค้า", help="ชื่อสินค้า")
    parser.add_argument("--description", default="", help="คำอธิบายสินค้า")
    parser.add_argument("--recipe", default="tus", choices=["tus", "etsy"], help="Recipe name")
    parser.add_argument("--duration", type=int, default=8, help="ความยาวคลิป (วินาที)")
    parser.add_argument("--ugc-style", default="holding", 
                        choices=["holding_product", "product_usage", "ugc_review", "talking_head", "holding"],
                        help="UGC style")
    
    # Behavior
    parser.add_argument("--no-state", action="store_true", help="ไม่บันทึก state (ใช้ใหม่ได้)")
    parser.add_argument("--limit", type=int, default=0, help="จำกัดจำนวนใน batch mode")
    
    args = parser.parse_args()
    
    if args.batch:
        # ── Batch Mode ──
        candidates = scan_unprocessed_images()
        if not candidates:
            logger.info("ไม่มีรูปใหม่ใน image-gen storage (หรือ process หมดแล้ว)")
            return
        
        logger.info(f"พบ {len(candidates)} รูปที่ยังไม่ process")
        
        limit = args.limit or len(candidates)
        state = _load_state()
        
        success = 0
        fail = 0
        for i, (fname, fpath, furl) in enumerate(candidates[:limit]):
            logger.info(f"[{i+1}/{limit}] {fname}")
            try:
                result = feed_single(
                    image_url=furl,
                    product_name=args.product,
                    description=args.description,
                    recipe=args.recipe,
                    duration=args.duration,
                    ugc_style=args.ugc_style,
                )
                success += 1
            except Exception as e:
                logger.error(f"  ❌ {fname}: {e}")
                fail += 1
            
            # Mark processed
            if not args.no_state:
                if fname not in state["processed"]:
                    state["processed"].append(fname)
                _save_state(state)
        
        logger.info(f"✅ Batch complete: {success} success, {fail} fail")
    
    elif args.image:
        # ── Single Mode ──
        result = feed_single(
            image_url=args.image,
            product_name=args.product,
            description=args.description,
            recipe=args.recipe,
            duration=args.duration,
            ugc_style=args.ugc_style,
        )
        
        print(json.dumps(result, indent=2, default=str))
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
