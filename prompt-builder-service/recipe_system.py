#!/usr/bin/env python3
"""
Recipe System — Schema-Based Content Structure Loader
======================================================
โหลด 3 Core Schemas (pas, comparison, secret_hook) → คำนวณ scene durations
ตาม timing_ratio × total_seconds

Zero hardcoded durations — schema เดียวใช้ได้ทั้ง 8s, 15s, 30s
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger("recipe-system")

SCHEMAS_DIR = Path(__file__).resolve().parent / "schemas"

# ─── Schema Catalog ─────────────────────────────────────────────────────
SCHEMA_NAMES = {
    "pas": "Problem → Agitate → Solve",
    "comparison": "Us vs Them",
    "secret_hook": "Secret/Gatekeeping Hook",
}


def load_schema(recipe_type: str = "pas") -> Dict[str, Any]:
    """Load a schema JSON by recipe type.
    
    Args:
        recipe_type: "pas", "comparison", or "secret_hook"
    
    Returns:
        Schema dict with scenes, recommended styles/personas
    """
    schema_path = SCHEMAS_DIR / f"{recipe_type}_schema.json"
    
    if not schema_path.exists():
        logger.warning(f"Schema '{recipe_type}' not found, using default")
        return _default_schema()
    
    try:
        with open(schema_path, "r", encoding="utf-8") as f:
            schema = json.load(f)
        logger.info(f"Loaded schema: {schema.get('name', recipe_type)} (v{schema.get('schema_version', '?')})")
        return schema
    except Exception as e:
        logger.error(f"Failed to load schema {recipe_type}: {e}")
        return _default_schema()


def _default_schema() -> Dict[str, Any]:
    """Safe fallback schema."""
    return {
        "schema_version": 1,
        "name": "default",
        "label": "Default",
        "scenes": [
            {"id": "hook", "timing_ratio": 0.3, "purpose": "เปิด", "prompt": "เปิด"},
            {"id": "value", "timing_ratio": 0.5, "purpose": "เนื้อหา", "prompt": "เนื้อหาสินค้า"},
            {"id": "cta", "timing_ratio": 0.2, "purpose": "CTA", "prompt": "ชวนซื้อ"},
        ],
        "recommended": {"styles": ["holding", "review"], "personas": ["gen_z_trendy"]},
    }


def build_scenes_from_schema(recipe_type: str, duration: str = "8s") -> List[Dict[str, Any]]:
    """Load schema → calculate scene durations from timing_ratio.
    
    Args:
        recipe_type: "pas", "comparison", "secret_hook"
        duration: "8s", "15s", etc.
    
    Returns:
        List of scene dicts with actual durations in seconds
    """
    schema = load_schema(recipe_type)
    scenes_raw = schema.get("scenes", [])
    if not scenes_raw:
        return _default_scenes(duration)
    
    total_seconds = int(duration.replace("s", ""))
    result = []
    
    for scene in scenes_raw:
        ratio = scene.get("timing_ratio", 1.0 / len(scenes_raw))
        dur = round(total_seconds * ratio, 1)
        result.append({
            "id": scene["id"],
            "duration": dur,
            "purpose": scene.get("purpose", ""),
            "prompt_template": scene.get("prompt", ""),
        })
    
    return result


def _default_scenes(duration: str) -> List[Dict[str, Any]]:
    """Safe fallback scene list."""
    total = int(duration.replace("s", ""))
    return [
        {"id": "hook", "duration": round(total * 0.3, 1), "purpose": "เปิด", "prompt_template": ""},
        {"id": "value", "duration": round(total * 0.5, 1), "purpose": "เนื้อหา", "prompt_template": ""},
        {"id": "cta", "duration": round(total * 0.2, 1), "purpose": "CTA", "prompt_template": ""},
    ]


def get_recommended(recipe_type: str) -> Dict[str, list]:
    """Get recommended styles and personas for a recipe type."""
    schema = load_schema(recipe_type)
    return schema.get("recommended", {"styles": ["holding"], "personas": ["gen_z_trendy"]})


def list_schemas() -> List[Dict[str, Any]]:
    """List all available schemas with metadata."""
    schemas = []
    if not SCHEMAS_DIR.exists():
        return schemas
    
    for schema_file in sorted(SCHEMAS_DIR.glob("*_schema.json")):
        try:
            with open(schema_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            schemas.append({
                "name": data.get("name", schema_file.stem.replace("_schema", "")),
                "label": data.get("label", ""),
                "description": data.get("description", ""),
                "scenes": data.get("scenes", []),
                "recommended": data.get("recommended", {}),
            })
        except Exception as e:
            logger.error(f"Failed to load schema {schema_file}: {e}")
    
    return schemas


# ─── Backward Compat ────────────────────────────────────────────────────

def load_recipe(recipe_name: str = "tus") -> Dict[str, Any]:
    """Legacy — map old recipe names to new schema format.
    
    Old: "tus" → "pas" (default)
    Old: "etsy" → "comparison"  
    New: "pas", "comparison", "secret_hook"
    """
    legacy_map = {
        "tus": "pas",
        "etsy": "comparison",
        "tus_8s": "pas",
        "tus_15s": "pas",
        "tus_pas_8s": "pas",
        "tus_pas_15s": "pas",
        "tus_comparison_8s": "comparison",
        "tus_comparison_15s": "comparison",
        "tus_secret_8s": "secret_hook",
    }
    recipe_type = legacy_map.get(recipe_name, recipe_name)
    return load_schema(recipe_type)


def get_scenes_for_duration(recipe: Dict[str, Any], duration: int = 8) -> List[Dict[str, Any]]:
    """Legacy — build scenes from schema dict + target duration."""
    scenes_raw = recipe.get("scenes", [])
    if not scenes_raw:
        return _default_scenes(f"{duration}s")
    
    result = []
    for i, scene in enumerate(scenes_raw):
        ratio = scene.get("timing_ratio", 1.0 / len(scenes_raw))
        dur = round(duration * ratio, 1)
        result.append({
            **scene,
            "scene_index": i,
            "duration": dur,
        })
    return result


def build_scene_prompts(scenes: List[Dict[str, Any]], product_name: str, ugc_style: str = "holding") -> List[str]:
    """Legacy — fill scene prompt templates with product data."""
    prompts = []
    for scene in scenes:
        base = scene.get("prompt_template", "")
        content = scene.get("purpose", "")
        filled = base.replace("{product}", product_name) if "{product}" in base else base
        prompt = f"{content}. {filled}. Product: {product_name}" if base else f"{content}. Product: {product_name}"
        prompts.append(prompt)
    return prompts


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("=== Available Schemas ===")
    for s in list_schemas():
        print(f"  {s['name']}: {s['label']}")
    
    print("\n=== PAS Schema → 8s ===")
    scenes = build_scenes_from_schema("pas", "8s")
    for s in scenes:
        print(f"  {s['id']}: {s['duration']}s — {s['purpose'][:30]}")
    
    print("\n=== PAS Schema → 15s ===")
    scenes = build_scenes_from_schema("pas", "15s")
    for s in scenes:
        print(f"  {s['id']}: {s['duration']}s — {s['purpose'][:30]}")
    
    print("\n=== Backward Compat ===")
    recipe = load_recipe("tus_pas_8s")
    print(f"  load_recipe('tus_pas_8s') → {recipe.get('name')}")
