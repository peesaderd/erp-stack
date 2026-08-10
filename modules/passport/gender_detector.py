"""
Gender Detector using Gemini Vision
====================================
Detects gender from portrait photo for clothing selection.
"""

import os
import io
import logging
from pathlib import Path

from PIL import Image

logger = logging.getLogger("passport.gender")

# ── Config ─────────────────────────────────────────────
_erp_stack = Path(__file__).parent.parent.parent
_env_path = _erp_stack / ".env"

def _get_env(key):
    val = os.environ.get(key)
    if val:
        return val
    if _env_path.exists():
        for line in open(_env_path):
            if line.startswith(f"{key}="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None

GEMINI_KEY = _get_env("GEMINI_API_KEY") or _get_env("GOOGLE_API_KEY")


def detect_gender(image_bytes: bytes) -> dict:
    """
    Detect gender from portrait photo using Gemini Vision.
    
    Returns:
        {
            "gender": "male" | "female" | "unknown",
            "confidence": 0.0-1.0,
            "description": "brief description"
        }
    """
    if not GEMINI_KEY:
        logger.warning("No Gemini key, defaulting to male")
        return {"gender": "male", "confidence": 0.5, "description": "No Gemini API key"}
    
    try:
        import google.genai as genai
        client = genai.Client(api_key=GEMINI_KEY)
        
        prompt_text = (
            "Analyze this portrait photo and determine the person's gender. "
            "Reply with ONLY a JSON object in this exact format:\n"
            '{"gender": "male" or "female", "confidence": 0.0-1.0, "description": "brief note"}\n'
            "Do not include any other text."
        )
        
        img = Image.open(io.BytesIO(image_bytes))
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[prompt_text, img],
        )
        
        text = response.text.strip() if response.text else ""
        logger.info(f"Gemini gender response: {text[:200]}")
        
        # Parse JSON from response
        import json
        # Extract JSON from response (may have markdown code block)
        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()
        
        result = json.loads(text)
        gender = result.get("gender", "unknown").lower()
        confidence = float(result.get("confidence", 0.5))
        description = result.get("description", "")
        
        if gender not in ("male", "female"):
            gender = "unknown"
        
        return {
            "gender": gender,
            "confidence": confidence,
            "description": description,
        }
        
    except Exception as e:
        logger.error(f"Gemini gender detection failed: {e}")
        return {"gender": "male", "confidence": 0.5, "description": f"Detection failed: {e}"}
