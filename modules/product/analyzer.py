"""AI Vision fallback analyzer for product images.
Uses Mistral Pixtral to analyze product images when Playwright fails."""
import os, json, logging, httpx, base64, re
from typing import Optional, Dict, List

logger = logging.getLogger("product_analyzer")


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
            # Download image
            resp = await client.get(image_url)
            if resp.status_code != 200:
                logger.warning(f"Cannot fetch image: {image_url}")
                return None

            # Call Mistral Pixtral with direct image URL
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

            # Parse JSON from response
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
