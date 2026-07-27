"""
Passport Template Engine
========================
Loads templates from Schema Engine at startup.
Provides fallback built-in templates if Schema Engine is unavailable.
"""

import requests
import logging

logger = logging.getLogger("passport.templates")

SCHEMA_ENGINE_URL = "http://localhost:8100"

# ── Built-in Fallback Templates ───────────────────────────────────────
FALLBACK_TEMPLATES = {
    "us_passport": {"name": "US Passport", "country": "United States", "doc_type": "passport", "width_mm": 51, "height_mm": 51, "bg_color": "#FFFFFF", "dpi": 300, "head_height_pct": 0.7},
    "uk_passport": {"name": "UK Passport", "country": "United Kingdom", "doc_type": "passport", "width_mm": 35, "height_mm": 45, "bg_color": "#FFFFFF", "dpi": 300, "head_height_pct": 0.65},
    "eu_passport": {"name": "EU Passport", "country": "European Union", "doc_type": "passport", "width_mm": 35, "height_mm": 45, "bg_color": "#FFFFFF", "dpi": 300, "head_height_pct": 0.65},
    "thai_passport": {"name": "หนังสือเดินทางไทย", "country": "Thailand", "doc_type": "passport", "width_mm": 35, "height_mm": 45, "bg_color": "#FFFFFF", "dpi": 300, "head_height_pct": 0.65},
    "thai_id": {"name": "บัตรประชาชนไทย", "country": "Thailand", "doc_type": "id_card", "width_mm": 86, "height_mm": 54, "bg_color": "#FFFFFF", "dpi": 300, "head_height_pct": 0.6},
    "china_visa": {"name": "China Visa", "country": "China", "doc_type": "visa", "width_mm": 33, "height_mm": 48, "bg_color": "#FFFFFF", "dpi": 300, "head_height_pct": 0.6},
    "japan_visa": {"name": "Japan Visa", "country": "Japan", "doc_type": "visa", "width_mm": 45, "height_mm": 45, "bg_color": "#FFFFFF", "dpi": 300, "head_height_pct": 0.65},
    "canada_passport": {"name": "Canada Passport", "country": "Canada", "doc_type": "passport", "width_mm": 50, "height_mm": 70, "bg_color": "#FFFFFF", "dpi": 300, "head_height_pct": 0.6},
    "australia_passport": {"name": "Australia Passport", "country": "Australia", "doc_type": "passport", "width_mm": 35, "height_mm": 45, "bg_color": "#FFFFFF", "dpi": 300, "head_height_pct": 0.65},
    "india_passport": {"name": "India Passport", "country": "India", "doc_type": "passport", "width_mm": 35, "height_mm": 35, "bg_color": "#FFFFFF", "dpi": 300, "head_height_pct": 0.7},
    "singapore_passport": {"name": "Singapore Passport", "country": "Singapore", "doc_type": "passport", "width_mm": 35, "height_mm": 45, "bg_color": "#FFFFFF", "dpi": 300, "head_height_pct": 0.65},
}

# ── Template Colors ──────────────────────────────────────────────────
# Some countries require specific background colors
COUNTRY_BG_COLORS = {
    # US: white for passport, white for visa
    # China visa: white
    "china_visa": "#FFFFFF",
    "thai_id": "#FFFFFF",
    # Most are white; blue/red variants can be added per template
}

# Extra colors per doc type (common standards)
DOC_TYPE_BG_PALETTE = {
    "passport": ["#FFFFFF", "#F0F0F0"],
    "visa": ["#FFFFFF"],
    "id_card": ["#FFFFFF", "#E8E8E8"],
}


class TemplateEngine:
    """Loads passport templates from Schema Engine with fallback."""

    def __init__(self):
        self._templates = None
        self._loaded = False

    def load(self):
        """Load templates from Schema Engine. Falls back to built-in."""
        try:
            r = requests.get(
                f"{SCHEMA_ENGINE_URL}/api/v1/data/passport_template",
                params={"active": "true", "limit": "100"},
                timeout=5,
            )
            data = r.json()
            if data.get("success"):
                records = data.get("data", data.get("records", []))
                self._templates = {}
                for rec in records:
                    f = rec.get("data", {})
                    code = f.get("code", rec.get("id", ""))
                    self._templates[code] = {
                        "name": f.get("name", ""),
                        "country": f.get("country", ""),
                        "doc_type": f.get("doc_type", "passport"),
                        "width_mm": float(f.get("width_mm", 35)),
                        "height_mm": float(f.get("height_mm", 45)),
                        "bg_color": f.get("bg_color", "#FFFFFF"),
                        "dpi": int(f.get("dpi", 300)),
                        "head_height_pct": float(f.get("head_height_pct", 0.65)),
                    }
                logger.info(f"Loaded {len(self._templates)} templates from Schema Engine")
                self._loaded = True
                return
        except Exception as e:
            logger.warning(f"Schema Engine unavailable, using fallback: {e}")

        self._templates = dict(FALLBACK_TEMPLATES)
        self._loaded = True
        logger.info(f"Loaded {len(self._templates)} fallback templates")

    def get_all(self):
        if not self._loaded:
            self.load()
        # Return templates with their code key
        return [{"code": k, **v} for k, v in self._templates.items()]

    def get(self, code: str):
        if not self._loaded:
            self.load()
        return self._templates.get(code)

    def get_codes(self):
        if not self._loaded:
            self.load()
        return list(self._templates.keys())

    def pixel_dimensions(self, code: str):
        """Return (width_px, height_px) at template DPI."""
        t = self.get(code)
        if not t:
            return None
        w_px = int(round(t["width_mm"] / 25.4 * t["dpi"]))
        h_px = int(round(t["height_mm"] / 25.4 * t["dpi"]))
        return w_px, h_px


# Singleton
engine = TemplateEngine()
