"""Recipe loading (Phase C split, move-only)."""
from ._shared import (  # noqa: F401
    os, re, sys, json, time, uuid, logging, random, subprocess, shutil, asyncio,
    Path, Optional, List, Dict, Any, requests,
    PRODIA_TOKEN, GEMINI_API_KEY, logger,
    IMAGE_GEN_URL, PROMPT_BUILDER_URL, STORAGE_DIR, TMP_DIR,
    get_default_style, get_style_config, validate_ugc_style, is_valid_style,
)

# ═══════════════════════════════════════════════════════════════════════════
# STEP 2: Load Recipe
# ═══════════════════════════════════════════════════════════════════════════

def load_recipe(recipe_name: str = "tus") -> dict:
    """
    Step 2: Load recipe → scenes structure

    Query จาก Schema Engine (services/schema-engine) เท่านั้น
    ถ้า Schema Engine ไม่ตอบ หรือ recipe ไม่มี → throw error ทันที
    (ไม่มี filesystem fallback เพื่อให้รู้ทันเมื่อ Schema Engine พัง)

    Args:
        recipe_name: ชื่อ recipe (tus_novoice_15s, tus_15s, etc.)

    Returns:
        dict: recipe { name, total_duration, image_generation, video_generation, tts, ... }
    """
    logger.info(f"Step 2/9: Load recipe ({recipe_name})")

    schema_url = os.environ.get("SCHEMA_ENGINE_URL", "http://localhost:8100")
    try:
        resp = requests.get(
            f"{schema_url}/api/v1/data/video_recipe",
            params={"search": recipe_name, "limit": 1},
            timeout=3,
        )
        
        if resp.status_code != 200:
            raise RuntimeError(f"Schema Engine returned {resp.status_code}: {resp.text[:200]}")

        data = resp.json()
        records = data.get("data", [])
        if not records:
            raise RuntimeError(f"Recipe '{recipe_name}' not found in Schema Engine (video_recipe schema)")
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
        logger.warning(f"Schema Engine unreachable ({e}) — using default recipe")
        # Fallback: return a default recipe with standard scenes
        default_recipe = {
            "name": recipe_name,
            "description": "Default recipe (Schema Engine offline)",
            "version": "1.0",
            "total_duration": 15,
            "language": "th",
            "default_style": "holding",
            "scenes": [
                {"name": "hook", "duration": 5, "function": "hook"},
                {"name": "value", "duration": 5, "function": "value"},
                {"name": "cta", "duration": 5, "function": "cta"},
            ],
            "video_model": "wan2.7",
            "video_count": 1,
            "ugc_styles": ["holding", "review", "usage", "talking"],
            "voice_tone": "friendly, authentic, enthusiastic",
            "target_audience": "Thai TikTok users",
            "image_generation": {},
            "video_generation": {},
            "tts": {"enabled": True},
        }
        logger.info(f"  Recipe (default fallback): {recipe_name}, {len(default_recipe['scenes'])} scenes, {default_recipe['total_duration']}s")
        return default_recipe

    record = records[0]
    row = record.get("data", record)
    # Schema Engine stores with double nesting: data.data.config
    inner = row.get("data", row) if isinstance(row, dict) and "config" not in row else row
    config = inner.get("config", row.get("config", {}))

    # Use `inner` for recipe-level fields (unwrap double-nesting)
    recipe = {
        "name": inner.get("name", recipe_name),
        "description": inner.get("description", ""),
        "version": inner.get("version", "1.0"),
        "total_duration": inner.get("total_duration", 15),
        "language": inner.get("language", "th"),
        "default_style": inner.get("default_style", "holding"),
        "scenes": config.get("scenes", []),
        "video_model": config.get("video_model", "wan2.7"),
        "video_count": config.get("video_count", 1),
        "ugc_styles": config.get("ugc_styles", ["holding", "review", "usage", "talking"]),
        "voice_tone": config.get("voice_tone", "friendly, authentic, enthusiastic"),
        "target_audience": config.get("target_audience", "Thai TikTok users"),
        "image_generation": config.get("image_generation", {}),
        "video_generation": config.get("video_generation", {}),
        "tts": config.get("tts"),  # None = no voiceover
    }

    scenes = recipe.get("scenes", [])
    logger.info(f"  Recipe (Schema Engine): {recipe_name}, {len(scenes)} scenes, {recipe.get('total_duration')}s")
    return recipe

