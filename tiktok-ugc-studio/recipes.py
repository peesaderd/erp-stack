"""
Recipe definitions for TikTok UGC Studio.
Each recipe maps to a pipeline template via UGC style.

Recipe = what content (mood, BGM, category, duration)
UGC Style = how to generate (audio, prompt template, video params)
Pipeline Template = Recipe × UGC Style → Wan 2.7 config
"""

# ═══════════════════════════════════════════════════════
# Recipe Catalog
# ═══════════════════════════════════════════════════════

RECIPES = [
    {
        "name": "skincare",
        "label": "🧴 Skincare Glow",
        "description": "Soft luxury vibes, calm music, slow transitions",
        "ugc_style": "product_usage",
        "sound_style": "luxury_jazz",
        "mood": "calm",
        "duration": 10,
        "bgm_style": "luxury_jazz",
        "prompt_context": {
            "category": "beauty",
            "vibe": "soft luxury",
            "lighting_preference": "warm natural",
        },
    },
    {
        "name": "gadget",
        "label": "📱 Gadget Unboxing",
        "description": "Fast-paced, energetic, quick cuts",
        "ugc_style": "holding_product",
        "sound_style": "upbeat_pop",
        "mood": "energetic",
        "duration": 8,
        "bgm_style": "upbeat_pop",
        "prompt_context": {
            "category": "tech",
            "vibe": "modern sleek",
            "lighting_preference": "bright clean",
        },
    },
    {
        "name": "fashion",
        "label": "👗 Fashion Lookbook",
        "description": "Elegant slow-mo, chic aesthetic",
        "ugc_style": "talking_head",
        "sound_style": "chill_loft",
        "mood": "luxurious",
        "duration": 8,
        "bgm_style": "chill_loft",
    },
    {
        "name": "food",
        "label": "🍜 Food Review",
        "description": "Warm ASMR-style close-up shots",
        "ugc_style": "ugc_review",
        "sound_style": "asmr",
        "mood": "fun",
        "duration": 10,
        "bgm_style": "asmr",
    },
    {
        "name": "asmr",
        "label": "🎧 ASMR Unboxing",
        "description": "Quiet ambient, gentle sounds, relaxing",
        "ugc_style": "product_usage",
        "sound_style": "asmr",
        "mood": "calm",
        "duration": 12,
        "bgm_style": "asmr",
    },
    {
        "name": "makeup",
        "label": "💄 Makeup Tutorial",
        "description": "Soft upbeat, beauty close-ups, trendy",
        "ugc_style": "talking_head",
        "sound_style": "upbeat_pop",
        "mood": "energetic",
        "duration": 10,
        "bgm_style": "upbeat_pop",
    },
    {
        "name": "fitness",
        "label": "💪 Fitness/Supplement",
        "description": "High energy, motivating, fast tempo",
        "ugc_style": "holding_product",
        "sound_style": "energetic_edm",
        "mood": "energetic",
        "duration": 8,
        "bgm_style": "energetic_edm",
    },
    {
        "name": "product_demo",
        "label": "📦 Product Demo",
        "description": "No person, just product on table, feature demo",
        "ugc_style": "product_demo",
        "sound_style": "none",
        "mood": "clean",
        "duration": 8,
        "bgm_style": "none",
        "prompt_context": {
            "category": "general",
            "vibe": "clean minimal",
            "lighting_preference": "bright even",
        },
    },
]


def get_recipe(name: str) -> dict:
    """Get a single recipe by name."""
    for r in RECIPES:
        if r["name"] == name:
            return r
    return RECIPES[0]  # fallback to first


def list_recipes() -> list:
    """List all recipes."""
    return RECIPES
