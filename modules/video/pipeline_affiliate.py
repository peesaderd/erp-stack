"""
TikTok UGC Studio - Affiliate Video Pipeline v6 (Modular)
===========================================================
Pipeline: Analyze -> Recipe -> Script -> Image Prompt -> Image -> Video Prompts -> TTS -> Video -> Compose

Each step is a standalone module in steps/.
Orchestration logic lives here only.
"""

import os, sys, re, time, uuid, logging
from pathlib import Path
from typing import Optional

_erp_stack = Path(__file__).parent.parent.parent
if str(_erp_stack) not in sys.path:
    sys.path.insert(0, str(_erp_stack))

from shared_config import PRODIA_TOKEN
_ugc_client_dir = os.path.join(str(_erp_stack), "prompt-builder-service")
if _ugc_client_dir not in sys.path:
    sys.path.insert(0, _ugc_client_dir)
from ugc_schema_client import validate_ugc_style

from pipeline_logger import start_job, update_step, update_cost, complete_job, fail_job, update_prompts
from gemini_tts import get_voice_for_gender

# Ensure our local steps/ is found before prompt-builder-service/steps/
_this_dir = str(Path(__file__).parent)
if _this_dir not in sys.path:
    sys.path.insert(0, _this_dir)

from steps import (
    analyze_product,
    load_recipe,
    generate_script,
    build_image_prompt,
    generate_image,
    build_video_prompts,
    generate_voice,
    generate_video,
    compose_video,
)
from steps.common import TMP_DIR, download_file

logger = logging.getLogger("tiktok-ugc.pipeline_affiliate")

def run_pipeline(
    product_name: str,
    product_image: Optional[str] = None,
    recipe_name: str = "tus",
    voice: str = "Aoede",
    bgm_style: str = "chill_loft",
    description: Optional[str] = None,
    ugc_style: str = "holding",
    external_job_id: Optional[str] = None,
    duration: int = 15,
    image_prompt: Optional[str] = None,
    video_prompt: Optional[str] = None,
    video_prompts: Optional[list] = None,
    negative_prompt: Optional[str] = None,
    script: Optional[str] = None,
    **kwargs,
) -> dict:
    """
    Run full Affiliate Pipeline v6 (9 Steps ตาม PIPELINE_STRUCTURE.md)

    Args:
        product_name: ชื่อสินค้า
        product_image: URL ของรูปสินค้า (required!)
        recipe_name: ชื่อ recipe (tus, etsy)
        voice: ชื่อเสียง TTS
        bgm_style: สไตล์เพลงพื้นหลัง
        description: คําอธิบายสินค้า (optional)
        external_job_id: job_id จาก caller (ถ้ามี) — ใช้แทนการ gen เอง เพื่อให้ pipeline_logs.db
                         ตรงกับ pipeline.db ใน tiktok-ugc-studio
        image_prompt: รูป prompt ที่เตรียมมาแล้ว (ถ้ามีจะไม่ gen ใหม่)
        video_prompt: วิดีโอ prompt ที่เตรียมมาแล้ว (ใช้ fallback ถ้า video_prompts ไม่มี)
        video_prompts: รายการวิดีโอ prompts ต่อ scene (ถ้ามีจะไม่ gen ใหม่)
        negative_prompt: negative prompt ที่เตรียมมาแล้ว
        script: script ที่เตรียมมาแล้ว (ถ้ามีจะไม่ gen ใหม่)

    Returns:
        dict: {
            run_id, final_path, duration, cost_estimate, cost_breakdown,
            product_profile, recipe, script, image_path, video_paths
        }
    """
    run_id = uuid.uuid4().hex[:8]
    job_id = external_job_id or f"vid_{run_id}"

    logger.info(f"{'='*60}")
    logger.info(f"Pipeline v6 - Run {run_id}")
    logger.info(f"{'='*60}")
    logger.info(f"Product: {product_name}")
    logger.info(f"Image: {product_image}")
    logger.info(f"Recipe: {recipe_name}")
    logger.info(f"{'='*60}")

    # Clean double-prefix from image URL
    if product_image and "://" in product_image:
        import re
        clean = re.sub(r"https?://(https?://)", r"", product_image)
        if clean != product_image:
            logger.warning(f"Fixed double-prefix product_image: {product_image} -> {clean}")
            product_image = clean

    # Initialize pipeline logger
    try:
        start_job(job_id, {
            'product_title': product_name,
            'product_image': product_image,
            'product_description': description,
            'recipe_name': recipe_name,
            'voice': voice,
            'ugc_style': ugc_style,
        })
    except Exception as e:
        logger.warning(f"Pipeline logger start failed: {e}")

    # ── Validate ugc_style from Schema Engine ──
    _orig_ugc = ugc_style
    ugc_style = validate_ugc_style(ugc_style)
    if ugc_style != _orig_ugc:
        logger.warning(f"  ugc_style '{_orig_ugc}' not valid, using '{ugc_style}'")

    pipeline_start = time.time()
    cost_image = 0.0
    cost_voice = 0.0
    cost_video = 0.0

    try:
        # ── STEP 1: Analyze ──
        step_start = time.time()
        product_profile = analyze_product(product_name, product_image, description, ugc_style=ugc_style)
        analyze_duration = int((time.time() - step_start) * 1000)

        try:
            update_step(job_id, 'analyze', {'duration_ms': analyze_duration})
        except Exception:
            pass

        # ── STEP 2: Load Recipe ──
        step_start = time.time()
        recipe = load_recipe(recipe_name)
        recipe_duration = int((time.time() - step_start) * 1000)
        num_scenes = len(recipe.get("scenes", []))
        total_duration = duration if duration > 0 else recipe.get("total_duration", 8)

        try:
            update_step(job_id, 'recipe', {'duration_ms': recipe_duration, 'scenes': num_scenes})
        except Exception:
            pass

        # ── Resolve voice by gender (GEMINI TTS ONLY — EdgeTTS not used) ──
        target_gender = product_profile.get("target_gender", "female")
        from gemini_tts import get_voice_for_gender
        voice = get_voice_for_gender(target_gender)
        logger.info(f"  Voice: {voice} (gender={target_gender})")

        # ── STEP 3: Generate Script (skip if pre-computed) ──
        if not script:
            step_start = time.time()
            script = generate_script(product_name, product_profile, recipe, ugc_style=ugc_style)
            script_duration = int((time.time() - step_start) * 1000)
        else:
            script_duration = 0
            logger.info(f"Step 3/9: Skipped (using pre-computed script)")

        try:
            update_step(job_id, 'script', {'duration_ms': script_duration, 'script': script[:100]})
        except Exception:
            pass

        # ── STEP 4: Build Image Prompt (skip if pre-computed) ──
        if not image_prompt:
            step_start = time.time()
            image_prompt = build_image_prompt(product_name, product_profile, recipe)
            img_prompt_duration = int((time.time() - step_start) * 1000)
        else:
            img_prompt_duration = 0
            logger.info(f"Step 4/9: Skipped (using pre-computed image_prompt)")

        try:
            update_step(job_id, 'image_prompt', {'duration_ms': img_prompt_duration})
        except Exception:
            pass

        # ── STEP 5: Generate Image ──
        step_start = time.time()
        img_url, cost_image = generate_image(image_prompt, product_image)
        img_path = TMP_DIR / f"image_{run_id}.png"
        download_file(img_url, img_path)
        image_duration = int((time.time() - step_start) * 1000)

        try:
            update_step(job_id, 'image_gen', {'duration_ms': image_duration, 'output_path': str(img_path)})
            update_cost(job_id, 'image', cost_image)
        except Exception:
            pass

        # ── STEP 6: Build Video Prompts (skip if pre-computed) ──
        if not video_prompts and video_prompt:
            video_prompts = [video_prompt]
            vid_prompt_duration = 0
            logger.info(f"Step 6/9: Skipped (using pre-computed video_prompt)")
        elif not video_prompts:
            step_start = time.time()
            video_prompts = build_video_prompts(product_profile, recipe, str(img_path), ugc_style=ugc_style)
            vid_prompt_duration = int((time.time() - step_start) * 1000)
        else:
            vid_prompt_duration = 0
            logger.info(f"Step 6/9: Skipped (using pre-computed video_prompts)")

        try:
            update_step(job_id, 'video_prompts', {'duration_ms': vid_prompt_duration, 'count': len(video_prompts)})
        except Exception:
            pass

        # Save all prompts + script to logger
        try:
            update_prompts(job_id, {
                'image_prompt': image_prompt,
                'video_prompts': video_prompts,
                'script': script,
                'negative_prompt': negative_prompt if negative_prompt else '',
                'hashtags': product_profile.get('hashtags', []),
            })
        except Exception as e:
            logger.warning(f"Logger update_prompts failed: {e}")

        # ── STEP 7: TTS (ข้ามถ้าไม่มี voice หรือ recipe ไม่ได้ตั้งค่า tts) ──
        if script:
            step_start = time.time()
            voice_path = generate_voice(script, voice=voice, run_id=run_id)
            tts_duration = int((time.time() - step_start) * 1000)
            cost_voice = (len(script) / 1000) * 0.0001

            try:
                update_step(job_id, 'tts', {'duration_ms': tts_duration, 'output_path': voice_path})
                update_cost(job_id, 'voice', cost_voice)
            except Exception:
                pass
        else:
            logger.info(f"Step 7/9: Skipped (no voice)")
            voice_path = None
            cost_voice = 0.0

        # ── STEP 8: Generate 1 Video (Wan 2.7 Sync, 1 clip full duration) ──
        # WHY 1 clip: Wan 2.7 img2vid generates from a SINGLE image reference.
        # Multiple independent clips from the same static image = jarring cuts,
        # same product angle every scene, zero visual continuity.
        # 1 continuous generation = smooth motion, natural flow.
        step_start = time.time()
        video_paths = []
        
        vprompt = video_prompts[0] if video_prompts else "Product showcase, smooth motion, elegant presentation"
        logger.info(f"  Generating 1 continuous video ({total_duration}s): {vprompt[:80]}...")
        
        vid_path, cost_video = generate_video(
            image_path=str(img_path),
            prompt=vprompt,
            duration=total_duration,
            audio_path=voice_path,
            negative_prompt=negative_prompt,
        )
        video_paths.append(vid_path)
        
        video_gen_duration = int((time.time() - step_start) * 1000)

        try:
            update_step(job_id, 'video_gen', {
                'duration_ms': video_gen_duration,
                'output_path': video_paths[-1] if video_paths else ''
            })
            update_cost(job_id, 'video', cost_video)
        except Exception:
            pass

        # ── STEP 9: Compose ──
        final_duration = recipe.get("total_duration", 12)
        final_path = compose_video(video_paths, voice_path, run_id, bgm_style, target_duration=final_duration)

        # Cost summary
        cost_total = cost_image + cost_voice + cost_video
        total_duration_ms = int((time.time() - pipeline_start) * 1000)

        logger.info(f"{'='*60}")
        logger.info(f"Pipeline v6 complete: {final_path}")
        logger.info(f"Cost: ${cost_total:.4f}")
        logger.info(f"Time: {total_duration_ms/1000:.1f}s")
        logger.info(f"{'='*60}")

        # Log completion
        try:
            complete_job(
                job_id,
                final_path=str(final_path),
                total_duration_ms=total_duration_ms,
                total_video_duration=total_duration,
                total_scenes=num_scenes
            )
        except Exception as e:
            logger.warning(f"Pipeline logger complete failed: {e}")

        return {
            "run_id": run_id,
            "final_path": str(final_path),
            "duration": total_duration,
            "cost_estimate": round(cost_total, 4),
            "cost_breakdown": {
                "image": round(cost_image, 4),
                "voice": round(cost_voice, 4),
                "video": round(cost_video, 4),
                "total": round(cost_total, 4),
            },
            "product_profile": {k: v for k, v in product_profile.items() if not k.startswith("_")},
            "hashtags": product_profile.get('hashtags', []),
            "recipe": recipe_name,
            "script": script,
            "image_path": str(img_path),
            "video_paths": video_paths,
            "job_id": job_id,
        }

    except Exception as e:
        try:
            fail_job(job_id, str(e), 'unknown')
        except Exception as e2:
            logger.warning(f"Pipeline logger fail failed: {e2}")
        raise


# ─── CLI ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Affiliate Video Pipeline v6")
    parser.add_argument("--product-name", required=True, help="ชื่อสินค้า")
    parser.add_argument("--product-image", required=True, help="รูปสินค้า (URL/path)")
    parser.add_argument("--recipe", default="tus", help="Recipe name")
    parser.add_argument("--voice", default="Aoede", help="TTS voice")
    parser.add_argument("--bgm", default="chill_loft", help="BGM style")
    parser.add_argument("--description", default="", help="คําอธิบายสินค้า")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    result = run_pipeline(
        product_name=args.product_name,
        product_image=args.product_image,
        recipe_name=args.recipe,
        voice=args.voice,
        bgm_style=args.bgm,
        description=args.description,
    )

    print("\n✅ Pipeline v6 Done!")
    print(f"  Final: {result['final_path']}")
    print(f"  Duration: {result['duration']}s")
    print(f"  Cost: ${result['cost_estimate']}")
    print(f"  Script: {result['script'][:80]}...")