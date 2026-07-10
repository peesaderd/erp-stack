#!/usr/bin/env python3
"""
Recipe System — TikTok Affiliate Content Recipes
=================================================
Loads and manages content recipes from JSON files.
"""

import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List

logger = logging.getLogger("recipe-system")

RECIPES_DIR = Path(__file__).resolve().parent / "recipes"


def load_recipe(recipe_name: str = "tus") -> Dict[str, Any]:
    """Load recipe from JSON file.
    
    Args:
        recipe_name: Recipe name (e.g., "tus", "etsy")
    
    Returns:
        Recipe dict with scenes, prompts, etc.
    """
    recipe_path = RECIPES_DIR / f"{recipe_name}.json"
    if not recipe_path.exists():
        logger.warning(f"Recipe {recipe_name} not found, using default")
        return _default_recipe()
    
    try:
        with open(recipe_path, "r", encoding="utf-8") as f:
            recipe = json.load(f)
        logger.info(f"Loaded recipe: {recipe_name}")
        return recipe
    except Exception as e:
        logger.error(f"Failed to load recipe {recipe_name}: {e}")
        return _default_recipe()


def _default_recipe() -> Dict[str, Any]:
    """Default recipe structure."""
    return {
        "name": "default",
        "description": "Default TikTok affiliate content recipe",
        "scenes": [
            {
                "name": "Hook",
                "duration_range": [0.5, 1.0],
                "function": "Hook",
                "content": "เปิดมาสวยเลย สินค้าสวย เห็นชัด",
                "prompt": "Product showcase, clean background, professional lighting"
            }
        ],
        "total_duration": 8,
        "ugc_styles": ["holding", "review", "usage", "talking"],
    }


def get_scenes_for_duration(recipe: Dict[str, Any], duration: int = 8) -> List[Dict[str, Any]]:
    """Get scenes adjusted for target duration.
    
    Args:
        recipe: Recipe dict
        duration: Target video duration in seconds
    
    Returns:
        List of scene dicts with timing
    """
    scenes = recipe.get("scenes", [])
    if not scenes:
        return []
    
    # Calculate timing based on duration ranges
    result = []
    total_min = sum(s.get("duration_range", [0, 0])[0] for s in scenes)
    total_max = sum(s.get("duration_range", [0, 0])[1] for s in scenes)
    
    if total_max == 0:
        # No duration info, distribute evenly
        per_scene = duration / len(scenes)
        for i, scene in enumerate(scenes):
            result.append({
                **scene,
                "scene_index": i,
                "duration": per_scene,
            })
        return result
    
    # Scale durations to fit target
    scale = duration / total_max if total_max > 0 else 1
    current_time = 0.0
    
    for i, scene in enumerate(scenes):
        dur_range = scene.get("duration_range", [1, 2])
        scene_duration = min(dur_range[1], max(dur_range[0], dur_range[1] * scale))
        
        result.append({
            **scene,
            "scene_index": i,
            "duration": scene_duration,
            "start_time": current_time,
            "end_time": current_time + scene_duration,
        })
        current_time += scene_duration
    
    return result


def build_scene_prompts(scenes: List[Dict[str, Any]], product_name: str, ugc_style: str = "holding") -> List[str]:
    """Build video prompts for each scene.
    
    Args:
        scenes: List of scene dicts
        product_name: Product name
        ugc_style: UGC style (holding, review, usage, talking)
    
    Returns:
        List of video prompts (one per scene)
    """
    prompts = []
    
    for scene in scenes:
        base_prompt = scene.get("prompt", "")
        content = scene.get("content", "")
        
        # Enhance with product context
        if "{product}" in base_prompt:
            base_prompt = base_prompt.replace("{product}", product_name)
        
        prompt = f"{content}. {base_prompt}. Product: {product_name}"
        prompts.append(prompt)
    
    return prompts


def list_recipes() -> List[Dict[str, Any]]:
    """List all available recipes.
    
    Returns:
        List of recipe metadata
    """
    recipes = []
    
    if not RECIPES_DIR.exists():
        return recipes
    
    for recipe_file in RECIPES_DIR.glob("*.json"):
        try:
            with open(recipe_file, "r", encoding="utf-8") as f:
                recipe = json.load(f)
            recipes.append({
                "name": recipe.get("name", recipe_file.stem),
                "description": recipe.get("description", ""),
                "file": recipe_file.name,
            })
        except Exception as e:
            logger.error(f"Failed to load recipe {recipe_file}: {e}")
    
    return recipes


if __name__ == "__main__":
    # Test
    logging.basicConfig(level=logging.INFO)
    
    recipe = load_recipe("tus")
    print(f"Recipe: {recipe.get('name')}")
    print(f"Scenes: {len(recipe.get('scenes', []))}")
    
    scenes = get_scenes_for_duration(recipe, duration=8)
    print(f"\nAdjusted scenes for 8s:")
    for scene in scenes:
        print(f"  {scene['name']}: {scene['duration']:.1f}s - {scene.get('content', '')[:40]}")
    
    prompts = build_scene_prompts(scenes, "Test Product", "holding")
    print(f"\nScene prompts: {len(prompts)}")
