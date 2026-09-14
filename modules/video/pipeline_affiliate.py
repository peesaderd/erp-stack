"""DEPRECATED shim — pipeline_affiliate is now a package (Phase C).

Kept so `from pipeline_affiliate import run_pipeline` (and every other helper)
keeps working unchanged. Real code lives in modules/video/pipeline/.
"""
# Work both as `video.pipeline_affiliate` (package) and as a top-level script.
try:
    from .pipeline import *  # noqa: F401,F403
    from .pipeline.providers import (  # noqa: F401 — underscore helpers
        _deepseek_key, _mimo_key, _mimo_image_ref, _extract_json_obj,
        _hue_diverse_reference_index, _pick_variant_reference_index,
    )
    from .pipeline.prompts import (  # noqa: F401
        _deepseek_product_prompts, _sanitize_video_prompt, _normalize_negative_prompt,
        _normalize_script_beats,
    )
    from .pipeline.script import _synthesize_script_beats  # noqa: F401
    from .pipeline.image import (  # noqa: F401
        _build_klein_last_prompt, _clean_product_name_for_video,
    )
    from .pipeline.video import _generate_fallback_video_from_image  # noqa: F401
except ImportError:  # run as a top-level script, not a package
    from pipeline import *  # noqa: F401,F403
    from pipeline.providers import (  # noqa: F401 — underscore helpers
        _deepseek_key, _mimo_key, _mimo_image_ref, _extract_json_obj,
        _hue_diverse_reference_index, _pick_variant_reference_index,
    )
    from pipeline.prompts import (  # noqa: F401
        _deepseek_product_prompts, _sanitize_video_prompt, _normalize_negative_prompt,
        _normalize_script_beats,
    )
    from pipeline.script import _synthesize_script_beats  # noqa: F401
    from pipeline.image import (  # noqa: F401
        _build_klein_last_prompt, _clean_product_name_for_video,
    )
    from pipeline.video import _generate_fallback_video_from_image  # noqa: F401

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
