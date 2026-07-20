"""AI Vision fallback analyzer for product images.
Uses Mistral Pixtral to analyze product images when Playwright fails.
Also provides enrichment via OpenCode API for product analysis."""
import os, json, logging, httpx, base64, re, asyncio
from typing import Optional, Dict, List, Any

logger = logging.getLogger("product_analyzer")

OPENDCODE_API_KEY = "sk-LTP2Z9x9adJjxgzUfcWjoQS9lxekHw5xMhKUs5NkCCULT9jhCryWgCFOPdwfngi0"
OPENDCODE_API_URL = "https://api.opencode.ai/v1/chat/completions"
OPENDCODE_MODEL = "opencode-go/deepseek-v4-flash"


async def analyze_with_vision(image_url: str) -> Optional[Dict]:
    """Send product image to Mistral Pixtral for analysis"""

    mistral_key = os.environ.get("MISTRAL_API_KEY", "")
    if not mistral_key:
        logger.warning("No MISTRAL_API_KEY set, skipping vision analysis")
        return None

    prompt = (
        'Analyze this product image. Return JSON: '
        '{"name": "product name", "price": "price or null", '
        '"description": "physical description", '
        '"brand": "brand name", "sku": "product code"}. '
        'Return ONLY valid JSON.'
    )

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(image_url)
            if resp.status_code != 200:
                logger.warning(f"Cannot fetch image: {image_url}")
                return None

            payload = {
                "model": "pixtral-large-2501",
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": image_url}
                    ]
                }],
                "temperature": 0.1,
                "max_tokens": 500,
            }

            resp = await client.post(
                "https://api.mistral.ai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {mistral_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )

            if resp.status_code != 200:
                logger.error(f"Mistral error: {resp.status_code} {resp.text[:200]}")
                return None

            result = resp.json()
            text = result.get("choices", [{}])[0].get("message", {}).get("content", "")

            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]

            text = text.strip()
            start = text.find("{")
            end = text.rfind("}")
            if start >= 0 and end > start:
                text = text[start:end+1]

            data = json.loads(text)
            return {
                "name": data.get("name"),
                "price": _parse_price(data.get("price")),
                "description": data.get("description"),
                "brand": data.get("brand"),
                "sku": data.get("sku"),
            }
    except Exception as e:
        logger.error(f"Vision analysis error: {e}")
        return None


def _parse_price(text) -> Optional[float]:
    if not text:
        return None
    cleaned = re.sub(r'[\u0e3f$\u20ac\u00a5,\\.\s]', '', str(text).strip())
    try:
        return float(cleaned) if cleaned else None
    except ValueError:
        return None


# ─── OpenCode AI Enrichment ───────────────────────────────────────────────────

async def _call_opencode(prompt: str, max_tokens: int = 500, temperature: float = 0.3) -> str:
    """Call OpenCode AI API (OpenAI-compatible)."""
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                OPENDCODE_API_URL,
                headers={
                    "Authorization": f"Bearer {OPENDCODE_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": OPENDCODE_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                },
            )
            if resp.status_code == 200:
                return resp.json()["choices"][0]["message"]["content"].strip()
            logger.warning(f"OpenCode error: {resp.status_code} {resp.text[:200]}")
            return ""
    except Exception as e:
        logger.error(f"OpenCode call failed: {e}")
        return ""


async def translate_to_thai(text: str) -> str:
    """Translate product title to Thai using OpenCode API."""
    if not text:
        return ""
    prompt = f"Translate this product title to Thai naturally (keep brand names, return only the translation):\n\n{text}"
    result = await _call_opencode(prompt, max_tokens=200)
    return result if result else text


async def extract_keywords(title: str, desc: str) -> List[str]:
    """Extract Thai keywords for TikTok using OpenCode API."""
    if not title:
        return []
    prompt = (
        f"Extract 5-10 Thai keywords for TikTok caption from this product. "
        f"Return ONLY a JSON array of strings.\n"
        f"Title: {title}\n"
        f"Description: {desc}\n"
    )
    result = await _call_opencode(prompt, max_tokens=200)
    if result:
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            words = re.findall(r'"([^"]+)"', result)
            return words[:10] if words else []
    return []


def score_viral_potential(product_data: dict) -> float:
    """Rule-based viral potential scoring (0-100). No AI needed."""
    score = 0.0
    sold_total = float(product_data.get("sold_total", product_data.get("historical_sold", 0)))
    rating = float(product_data.get("rating", product_data.get("product_rating", 0)))
    sold_week = float(product_data.get("sold_week", product_data.get("week_sold_count", 0)))
    review_count = float(product_data.get("review_count", 0))
    commission = float(product_data.get("commission_rate", 0))
    influencer_count = float(product_data.get("influencer_count", 0))

    score += min(1.0, sold_total / 10000) * 30
    score += min(1.0, rating / 5.0) * 25
    if sold_total > 0:
        score += min(1.0, sold_week / sold_total) * 20
    score += min(1.0, review_count / 500) * 10
    score += min(1.0, commission / 50) * 10
    score += min(1.0, influencer_count / 100) * 5

    return round(min(100, max(0, score)), 2)


async def enrich_product(product_data: dict) -> dict:
    """Enrich product data using OpenCode API:
    - Translate title to Thai
    - Extract Thai keywords
    - Detect category
    """
    enriched = dict(product_data)
    title = enriched.get("title", enriched.get("name", ""))
    description = enriched.get("description", "")

    enriched["title_th"] = await translate_to_thai(title)
    enriched["keywords"] = await extract_keywords(title, description)
    enriched["viral_score"] = score_viral_potential(enriched)

    category_prompt = (
        f"Detect product category from: {title}. "
        f"Options: beauty, fashion, electronics, home, food, sports, pets, health, kids, accessories. "
        f"Return single word only."
    )
    cat_result = await _call_opencode(category_prompt, max_tokens=20, temperature=0.1)
    if cat_result and cat_result.lower() in ("beauty", "fashion", "electronics", "home", "food", "sports", "pets", "health", "kids", "accessories"):
        enriched["category"] = cat_result.lower()
    else:
        enriched["category"] = enriched.get("category", "อื่นๆ")

    enriched["enriched"] = True
    return enriched
