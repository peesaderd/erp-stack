"""
Etsy Rules Validator — Micro Service
ตรวจสอบ Listing / Shop Policy / Image ตามกฎของ Etsy
ไม่อิง API — ใช้ Knowledge Base + Logic ตรวจสอบก่อน push
"""

import yaml
import re
from pathlib import Path
from typing import Any

RULES_DIR = Path(__file__).parent


class EtsyValidationResult:
    """ผลการตรวจสอบ"""

    def __init__(self, category: str):
        self.category = category
        self.passed: list[str] = []
        self.failed: list[str] = []
        self.warnings: list[str] = []
        self.suggestions: list[str] = []

    @property
    def is_valid(self) -> bool:
        return len(self.failed) == 0

    def to_dict(self) -> dict:
        return {
            "category": self.category,
            "valid": self.is_valid,
            "passed": self.passed,
            "failed": self.failed,
            "warnings": self.warnings,
            "suggestions": self.suggestions,
        }


def _load_rules(name: str) -> dict:
    path = RULES_DIR / f"{name}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"ไม่พบไฟล์กฏ: {path}")
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


# ─── Listing Validator ─────────────────────────────────────────────────────


def validate_title(title: str) -> EtsyValidationResult:
    result = EtsyValidationResult("title")
    rules = _load_rules("listing-rules")["rules"]["title"]
    length = len(title)

    if not title or length < rules["min_length"]:
        result.failed.append(f"Title สั้นเกินไป ({length} chars, min {rules['min_length']})")
    elif length > rules["max_length"]:
        result.failed.append(f"Title ยาวเกินไป ({length} chars, max {rules['max_length']})")
    else:
        result.passed.append(f"Title {length} chars (ok)")

    for hint in rules.get("hints", []):
        result.suggestions.append(hint)

    return result


def validate_tags(tags: list[str]) -> EtsyValidationResult:
    result = EtsyValidationResult("tags")
    rules = _load_rules("listing-rules")["rules"]["tags"]
    count = len(tags)

    if count > rules["max_count"]:
        result.failed.append(f"Tags เกิน {rules['max_count']} tags (มี {count})")
    elif count < rules["min_tags_required"]:
        result.warnings.append(f"Tags มี {count}/{rules['min_tags_required']} tags — ใช้ให้ครบเพื่อ SEO")

    # เช็คความยาวแต่ละ tag
    for i, tag in enumerate(tags):
        if len(tag) > rules["max_length_per_tag"]:
            result.failed.append(f"Tag #{i+1} '{tag}' ยาวเกิน ({len(tag)}/{rules['max_length_per_tag']} chars)")

    # เช็ค duplicate
    duplicates = [t for t in tags if tags.count(t) > 1]
    if duplicates:
        result.failed.append(f"พบ Tags ซ้ำ: {set(duplicates)}")

    for hint in rules.get("hints", []):
        result.suggestions.append(hint)

    return result


def validate_description(desc: str) -> EtsyValidationResult:
    result = EtsyValidationResult("description")
    rules = _load_rules("listing-rules")["rules"]["description"]
    length = len(desc)

    if length < rules["min_length"]:
        result.failed.append(f"Description สั้นเกินไป ({length} chars, min {rules['min_length']})")
    elif length > rules["max_length"]:
        result.failed.append(f"Description ยาวเกินไป ({length} chars, max {rules['max_length']})")
    else:
        result.passed.append(f"Description {length} chars (ok)")

    # เช็ค prohibited content
    for item in rules.get("prohibited", []):
        if re.search(re.escape(item), desc, re.IGNORECASE):
            if item in desc or item.lower() in desc.lower():
                result.failed.append(f"พบเนื้อหาต้องห้ามใน Description: {item}")

    for hint in rules.get("hints", []):
        result.suggestions.append(hint)

    return result


def validate_price(price: float | int) -> EtsyValidationResult:
    result = EtsyValidationResult("price")
    rules = _load_rules("listing-rules")["rules"]["price"]

    if price < rules["min"]:
        result.failed.append(f"ราคาต่ำกว่าขั้นต่ำ ${rules['min']} (ราคา ${price})")
    else:
        result.passed.append(f"ราคา ${price} (ok)")

    return result


def validate_listing(listing: dict) -> dict:
    """ตรวจสอบ listing ทั้งหมด"""
    results = {}

    if "title" in listing:
        results["title"] = validate_title(listing["title"]).to_dict()
    if "tags" in listing:
        results["tags"] = validate_tags(listing["tags"]).to_dict()
    if "description" in listing:
        results["description"] = validate_description(listing["description"]).to_dict()
    if "price" in listing:
        results["price"] = validate_price(listing["price"]).to_dict()

    has_failures = any(r.get("failed") for r in results.values() if isinstance(r, dict))
    return {
        "valid": not has_failures,
        "results": results,
        "summary": {
            "total_checks": len(results),
            "failed": sum(1 for r in results.values() if r.get("failed")),
            "warnings": sum(1 for r in results.values() if r.get("warnings")),
        },
    }


# ─── Image Validator ───────────────────────────────────────────────────────


def validate_image_requirements(image: dict) -> EtsyValidationResult:
    """ตรวจสอบ image ก่อน upload (ใช้ metadata)"""
    result = EtsyValidationResult("image")
    rules = _load_rules("image-rules")["rules"]["main_image"]

    width = image.get("width", 0)
    height = image.get("height", 0)
    file_size_mb = image.get("file_size_mb", 0)

    if width < rules["min_width"]:
        result.failed.append(f"ภาพกว้าง {width}px (min {rules['min_width']}px)")
    else:
        result.passed.append(f"ความกว้าง {width}px (ok)")

    if height < rules["min_height"]:
        result.failed.append(f"ภาพสูง {height}px (min {rules['min_height']}px)")
    else:
        result.passed.append(f"ความสูง {height}px (ok)")

    if file_size_mb > rules["max_file_size_mb"]:
        result.failed.append(f"ไฟล์ใหญ่ {file_size_mb}MB (max {rules['max_file_size_mb']}MB)")
    else:
        result.passed.append(f"ขนาดไฟล์ {file_size_mb}MB (ok)")

    for hint in rules.get("hints", []):
        result.suggestions.append(hint)

    return result


# ─── Policy Validator ──────────────────────────────────────────────────────


def validate_policies(policies: dict) -> EtsyValidationResult:
    result = EtsyValidationResult("policies")
    rules = _load_rules("policy-rules")["rules"]

    # Shipping
    if policies.get("shipping") and policies["shipping"].get("required"):
        result.passed.append("Shipping policy ระบุแล้ว")
    else:
        result.failed.append("ต้องระบุ Shipping policy")

    # Returns
    if policies.get("returns") and policies["returns"].get("option"):
        result.passed.append(f"Return policy: {policies['returns']['option']}")
    else:
        result.failed.append("ต้องระบุ Returns & Exchanges policy")

    # Privacy
    if policies.get("privacy"):
        result.passed.append("Privacy policy ระบุแล้ว")
    else:
        result.failed.append("ต้องระบุ Privacy policy")

    # About
    if policies.get("about"):
        result.passed.append("ระบุ About section แล้ว")
    else:
        result.warnings.append("ควรมี About section เพื่อเพิ่มความน่าเชื่อถือ")

    for hint in rules.get("hints", []):
        result.suggestions.append(hint)

    return result


# ─── Quick Check (CLI) ─────────────────────────────────────────────────────


def check_listing_from_cli():
    """รันจาก CLI: python -m rules.validator check-listing"""
    import json

    test_listing = {
        "title": "Handmade Sterling Silver Ring with Cubic Zirconia",
        "description": "A beautiful handmade sterling silver ring. Perfect for any occasion.",
        "tags": ["silver ring", "handmade jewelry", "gift for her"],
        "price": 29.99,
    }

    result = validate_listing(test_listing)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return result


if __name__ == "__main__":
    check_listing_from_cli()
