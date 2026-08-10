"""
📚 Story Coloring Book Module
==============================
AI Brain + AI Artist Pipeline สำหรับสร้าง Coloring Book แบบมีเรื่องราว
แยกจาก TUS (TikTok UGC Studio) อย่างชัดเจน
"""

import os
import json
import time
import logging
import requests
from pathlib import Path
from typing import Optional, List, Dict

logger = logging.getLogger("story-coloring")

# ═══════════════════════════════════════════════════════════════════
# Config
# ═══════════════════════════════════════════════════════════════════

# Load env from parent .env
_env_path = Path(__file__).parent.parent / '.env'
if _env_path.exists():
    with open(_env_path) as f:
        for line in f:
            if '=' in line and not line.startswith('#'):
                key, value = line.strip().split('=', 1)
                if key not in os.environ:
                    os.environ[key] = value

# Cloudflare (AI Brain - Free)
CF_TOKEN = os.environ.get('CLOUDFLARE_AI_TOKEN')
CF_ACCOUNT = os.environ.get('CLOUDFLARE_ACCOUNT_ID')
CF_MODEL = '@cf/meta/llama-3.3-70b-instruct-fp8-fast'
CF_BASE = f'https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT}/ai/run'

# Prodia (AI Artist)
PRODIA_TOKEN = os.environ.get('PRODIA_TOKEN')

# Output directories
DESIGNS_DIR = Path('/var/www/podwizard/designs')
DESIGNS_DIR.mkdir(parents=True, exist_ok=True)

BASE_URL = 'https://podwizard.m2igen.com/designs'


# ═══════════════════════════════════════════════════════════════════
# 🧠 AI Brain — Story Generation
# ═══════════════════════════════════════════════════════════════════

def ask_cloudflare(messages: list, temperature: float = 0.8) -> str:
    """Call Cloudflare Workers AI (Free)."""
    headers = {
        'Authorization': f'Bearer {CF_TOKEN}',
        'Content-Type': 'application/json'
    }
    payload = {
        'messages': messages,
        'temperature': temperature,
        'max_tokens': 2048
    }
    
    resp = requests.post(f'{CF_BASE}/{CF_MODEL}', headers=headers, json=payload, timeout=60)
    resp.raise_for_status()
    
    return resp.json()['result']['choices'][0]['message']['content']


def generate_story_ideas(
    theme: str = "animals",
    audience: str = "kids 3-6 years old",
    num_pages: int = 6,
    style: str = "kawaii cute"
) -> dict:
    """
    🧠 AI Brain: คิดไอเดีย story สำหรับ coloring book
    """
    prompt = f"""Create {num_pages} coloring book pages telling a story.

Theme: {theme}
Target: {audience}
Style: {style}

Output JSON:
{{
  "title": "Catchy story title",
  "pages": [
    {{"page_num": 1, "scene": "scene description", "prompt": "detailed prompt 80 words with FULL background"}}
  ]
}}

Rules:
- Each prompt: 80+ words with FULL background scene
- End each prompt: "coloring book page, line art, thick black outlines, white background, no shading, kawaii cute"
- Output ONLY valid JSON"""

    messages = [
        {"role": "system", "content": "You are a children's coloring book designer. Output ONLY valid JSON."},
        {"role": "user", "content": prompt}
    ]
    
    response = ask_cloudflare(messages, temperature=0.9)
    
    # Parse JSON
    try:
        start = response.find('{')
        end = response.rfind('}') + 1
        if start >= 0 and end > start:
            return json.loads(response[start:end])
    except json.JSONDecodeError as e:
        logger.error(f"JSON parse error: {e}")
    
    return {"error": "Failed to generate story", "raw": response[:500]}


# ═══════════════════════════════════════════════════════════════════
# 🎨 AI Artist — Image Generation
# ═══════════════════════════════════════════════════════════════════

def generate_image(prompt: str, filename: str) -> dict:
    """
    🎨 AI Artist: Generate line art from prompt using FLUX Schnell (Free).
    """
    headers = {
        'Authorization': f'Bearer {PRODIA_TOKEN}',
        'Content-Type': 'application/json'
    }
    
    payload = {
        'type': 'inference.flux-fast.schnell.txt2img.v2',
        'config': {'prompt': prompt}
    }
    
    resp = requests.post(
        'https://inference.prodia.com/v2/job',
        headers=headers,
        json=payload,
        timeout=120
    )
    resp.raise_for_status()
    
    # Save image
    filepath = DESIGNS_DIR / filename
    with open(filepath, 'wb') as f:
        f.write(resp.content)
    
    size_kb = len(resp.content) / 1024
    logger.info(f"Generated: {filename} ({size_kb:.1f} KB)")
    
    return {
        'file': str(filepath),
        'filename': filename,
        'url': f"{BASE_URL}/{filename}",
        'size_kb': round(size_kb, 1)
    }


# ═══════════════════════════════════════════════════════════════════
# 🚀 Full Pipeline — Story Coloring Book
# ═══════════════════════════════════════════════════════════════════

# Default story templates
DEFAULT_STORIES = {
    "bunny_farm": {
        "title": "Bunny's First Day at the Farm",
        "theme": "cute bunny visiting a farm",
        "pages": [
            {"page_num": 1, "scene": "Bunny arrives at the farm gate",
             "prompt": "A cute little bunny with big eyes standing at a wooden farm gate, looking excited, a big red barn in the background, green grass, white fence, tall trees, blue sky with fluffy clouds, colorful flowers along the fence, a winding dirt path leading to the barn, children's coloring book page, full page illustration, line art, thick black outlines, pure white background, no shading, no gray tones, kawaii cute style"},
            {"page_num": 2, "scene": "Bunny meets a friendly cow",
             "prompt": "A cute little bunny standing next to a big friendly cow in a green meadow, the cow has spots and a bell, butterflies flying around, tall trees in the background, flowers on the grass, a small pond with ducks, rolling hills, sunny day with clouds, children's coloring book page, full page illustration, line art, thick black outlines, pure white background, no shading, no gray tones, kawaii cute style"},
            {"page_num": 3, "scene": "Bunny collects eggs",
             "prompt": "A cute little bunny holding a basket with eggs inside, standing next to a cozy chicken coop, a mother hen watching, fluffy chicks playing, straw on the ground, wooden fence, sunflowers growing nearby, blue sky, children's coloring book page, full page illustration, line art, thick black outlines, pure white background, no shading, no gray tones, kawaii cute style"},
            {"page_num": 4, "scene": "Bunny plays with piglets",
             "prompt": "A cute little bunny jumping in a mud puddle with three happy piglets, mud splashing, a pig pen with wooden fence, hay bales stacked, a big oak tree, flowers growing, green grass, happy sunny day, children's coloring book page, full page illustration, line art, thick black outlines, pure white background, no shading, no gray tones, kawaii cute style"},
            {"page_num": 5, "scene": "Bunny picks apples",
             "prompt": "A cute little bunny reaching up to pick a red apple from a big apple tree, a basket of apples on the ground, green leaves, more fruit trees in the orchard, a ladder leaning on the tree, blue sky, birds flying, children's coloring book page, full page illustration, line art, thick black outlines, pure white background, no shading, no gray tones, kawaii cute style"},
            {"page_num": 6, "scene": "Bunny says goodbye at sunset",
             "prompt": "A cute little bunny waving goodbye at the farm gate, the sun setting in the background with orange and pink sky, silhouettes of farm buildings, the cow and piglets watching from the field, a beautiful sunset scene, warm colors, children's coloring book page, full page illustration, line art, thick black outlines, pure white background, no shading, no gray tones, kawaii cute style"}
        ]
    },
    "kitty_ocean": {
        "title": "Kitty's Ocean Adventure",
        "theme": "cute kitty exploring the ocean",
        "pages": [
            {"page_num": 1, "scene": "Kitty arrives at the beach",
             "prompt": "A cute little kitty wearing a sun hat standing on a sandy beach, looking at the ocean, waves crashing, seashells on the sand, a lighthouse in the distance, palm trees, blue sky with clouds, children's coloring book page, full page illustration, line art, thick black outlines, pure white background, no shading, kawaii cute style"},
            {"page_num": 2, "scene": "Kitty meets a friendly dolphin",
             "prompt": "A cute little kitty on a small boat meeting a smiling dolphin jumping out of the water, ocean waves, fish swimming below, coral visible, sunny sky, birds flying, children's coloring book page, full page illustration, line art, thick black outlines, pure white background, no shading, kawaii cute style"},
            {"page_num": 3, "scene": "Kitty explores coral reef",
             "prompt": "A cute little kitty snorkeling underwater, colorful coral reef, tropical fish swimming around, sea plants, bubbles, sunlight filtering from above, children's coloring book page, full page illustration, line art, thick black outlines, pure white background, no shading, kawaii cute style"},
            {"page_num": 4, "scene": "Kitty finds treasure",
             "prompt": "A cute little kitty on the ocean floor finding a treasure chest, golden coins spilling out, starfish, seahorse watching, underwater cave, children's coloring book page, full page illustration, line art, thick black outlines, pure white background, no shading, kawaii cute style"},
            {"page_num": 5, "scene": "Kitty plays with octopus",
             "prompt": "A cute little kitty playing with a friendly octopus, the octopus has eight smiling tentacles, underwater garden, colorful seaweed, tropical fish watching, children's coloring book page, full page illustration, line art, thick black outlines, pure white background, no shading, kawaii cute style"},
            {"page_num": 6, "scene": "Kitty watches sunset at beach",
             "prompt": "A cute little kitty sitting on the beach watching a beautiful sunset over the ocean, orange and pink sky, waves gently lapping, seashells nearby, calm peaceful scene, children's coloring book page, full page illustration, line art, thick black outlines, pure white background, no shading, kawaii cute style"}
        ]
    }
}


def create_story_coloring_book(
    story_key: Optional[str] = None,
    custom_story: Optional[dict] = None,
    delay_between: float = 1.0
) -> dict:
    """
    🚀 Full Pipeline: สร้าง Story Coloring Book
    
    Args:
        story_key: Key from DEFAULT_STORIES (e.g., "bunny_farm", "kitty_ocean")
        custom_story: Custom story dict with title and pages
        delay_between: Delay between image generations (seconds)
    
    Returns:
        dict: { title, pages: [...], metadata_path }
    """
    
    # Select story
    if custom_story:
        story = custom_story
    elif story_key and story_key in DEFAULT_STORIES:
        story = DEFAULT_STORIES[story_key]
    else:
        story = DEFAULT_STORIES["bunny_farm"]  # Default
    
    title = story.get('title', 'Coloring Book')
    pages = story.get('pages', [])
    
    logger.info(f"📚 Starting: {title} ({len(pages)} pages)")
    
    generated = []
    
    for page in pages:
        page_num = page['page_num']
        scene = page['scene'].lower().replace(' ', '_')[:25]
        filename = f"{title.lower().replace(' ', '_')}_{scene}_{page_num:02d}.png"
        
        logger.info(f"📖 Page {page_num}: {page['scene']}")
        
        try:
            result = generate_image(page['prompt'], filename)
            generated.append({
                'page_num': page_num,
                'scene': page['scene'],
                'filename': filename,
                'url': result['url'],
                'size_kb': result['size_kb']
            })
            
            if delay_between > 0:
                time.sleep(delay_between)
                
        except Exception as e:
            logger.error(f"❌ Error page {page_num}: {e}")
            generated.append({
                'page_num': page_num,
                'scene': page['scene'],
                'error': str(e)
            })
    
    # Save metadata
    safe_title = title.lower().replace(' ', '_')
    meta_filename = f"{safe_title}_metadata.json"
    meta_path = DESIGNS_DIR / meta_filename
    
    metadata = {
        'title': title,
        'theme': story.get('theme', ''),
        'pages': generated,
        'created_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        'base_url': BASE_URL
    }
    
    with open(meta_path, 'w') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
    
    logger.info(f"✅ Complete: {len(generated)}/{len(pages)} pages")
    
    return metadata


def get_available_stories() -> list:
    """List available story templates."""
    return [
        {
            'key': key,
            'title': story['title'],
            'theme': story.get('theme', ''),
            'pages': len(story['pages'])
        }
        for key, story in DEFAULT_STORIES.items()
    ]


# ═══════════════════════════════════════════════════════════════════
# API Endpoints สำหรับ POD Wizard
# ═══════════════════════════════════════════════════════════════════

def register_story_routes(app):
    """Register story coloring book routes with FastAPI app."""
    
    from fastapi import HTTPException
    
    @app.get("/api/pod/story/templates")
    def list_story_templates():
        """List available story templates."""
        return get_available_stories()
    
    @app.post("/api/pod/story/generate")
    def generate_story(
        story_key: str = None,
        custom_story: dict = None
    ):
        """Generate a story coloring book."""
        try:
            result = create_story_coloring_book(
                story_key=story_key,
                custom_story=custom_story
            )
            return result
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/api/pod/story/{story_key}")
    def get_story(story_key: str):
        """Get a specific story template."""
        if story_key not in DEFAULT_STORIES:
            raise HTTPException(status_code=404, detail="Story not found")
        return DEFAULT_STORIES[story_key]
    
    logger.info("📚 Story routes registered: /api/pod/story/*")


# ═══════════════════════════════════════════════════════════════════
# Standalone Test
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("=" * 60)
    print("📚 Story Coloring Book — Test Run")
    print("=" * 60)
    
    # Run default story
    result = create_story_coloring_book(story_key="bunny_farm")
    
    print(f"\n📊 Result:")
    print(f"Title: {result['title']}")
    print(f"Pages: {len(result['pages'])}")
    print(f"Metadata: {result.get('metadata_path', 'N/A')}")
    
    for page in result['pages']:
        if 'url' in page:
            print(f"  {page['page_num']}. {page['scene']} → {page['url']}")
    
    print("=" * 60)
