"""
POD Wizard — Create Product Session Manager
============================================
State machine สำหรับสร้าง POD product ตั้งแต่ต้นจนจบ
"""

import json
import logging
import uuid
from datetime import datetime
from typing import Optional

from pod_data import (
    get_product_catalog,
    get_product_detail,
    get_categories,
    get_providers,
    get_mockup_prompt,
    get_profit_calculation,
    get_shipping_estimate,
)
from pod_sizes import validate_artwork

logger = logging.getLogger("pod-wizard")

# ─── Wizard State ───────────────────────────────────────────────────────────

WIZARD_STEPS = [
    {"id": "provider",     "title": "เลือก Provider",         "icon": "🏪", "description": "Printful / Printify / Gelato"},
    {"id": "category",     "title": "เลือกหมวดหมู่",          "icon": "📁", "description": "เสื้อผ้า / แก้วน้ำ / ของตกแต่งบ้าน"},
    {"id": "product",      "title": "เลือกสินค้า",            "icon": "🎯", "description": "เลือกประเภทสินค้า + ดู spec"},
    {"id": "variant",      "title": "สีและขนาด",             "icon": "🎨", "description": "เลือกสี/ขนาด/วัสดุ"},
    {"id": "artwork",      "title": "อัปโหลด Artwork",       "icon": "🖼️", "description": "อัปโหลด + ตรวจสอบขนาด"},
    {"id": "mockup",       "title": "สร้าง Mockup",           "icon": "✨", "description": "AI generate ตัวอย่างสินค้า"},
    {"id": "content",      "title": "สร้างคำอธิบาย",          "icon": "✍️", "description": "AI gen title + description + tags"},
    {"id": "pricing",      "title": "ตั้งราคา",              "icon": "💰", "description": "คำนวณต้นทุน + กำไร"},
    {"id": "summary",      "title": "สรุป + Checklist",       "icon": "✅", "description": "สรุปก่อนส่ง publish"},
]


class WizardSession:
    """Session ในการสร้าง POD product หนึ่งตัว"""
    
    def __init__(self):
        self.session_id = str(uuid.uuid4())[:8]
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
        self.status = "active"  # active | completed | cancelled
        self.current_step_idx = 0
        
        # User selections
        self.provider = None
        self.category = None
        self.product_id = None
        self.variant_color = None
        self.variant_size = None
        self.artwork_info = None          # upload result
        self.artwork_validation = None    # validate result
        self.mockup_image_url = None
        self.generated_content = None     # AI generated title/desc/tags
        self.pricing = None               # profit calculation
        self.selling_price = None
        
        # Completed steps
        self.completed_steps = []
        
        # AI analysis data
        self.product_analysis = None
    
    def to_dict(self) -> dict:
        """Serialize session state"""
        return {
            "session_id": self.session_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "status": self.status,
            "current_step": WIZARD_STEPS[self.current_step_idx]["id"] if self.current_step_idx < len(WIZARD_STEPS) else "completed",
            "current_step_idx": self.current_step_idx,
            "total_steps": len(WIZARD_STEPS),
            "completed_steps": self.completed_steps,
            "progress": f"{len(self.completed_steps)}/{len(WIZARD_STEPS)}",
            "provider": self.provider,
            "category": self.category,
            "product_id": self.product_id,
            "variant_color": self.variant_color,
            "variant_size": self.variant_size,
            "has_artwork": self.artwork_info is not None,
            "artwork_valid": self.artwork_validation.get("valid") if self.artwork_validation else None,
            "has_mockup": self.mockup_image_url is not None,
            "has_content": self.generated_content is not None,
            "has_pricing": self.pricing is not None,
            "selling_price": self.selling_price,
        }
    
    def get_current_step(self) -> dict:
        if self.current_step_idx < len(WIZARD_STEPS):
            step = dict(WIZARD_STEPS[self.current_step_idx])
            step["index"] = self.current_step_idx
            step["is_last"] = self.current_step_idx == len(WIZARD_STEPS) - 1
            return step
        return {"id": "completed", "title": "เสร็จสิ้น", "index": len(WIZARD_STEPS), "is_last": True}
    
    def advance_step(self) -> dict:
        """ข้ามไป step ถัดไป"""
        self.updated_at = datetime.now()
        if self.current_step_idx < len(WIZARD_STEPS):
            step_id = WIZARD_STEPS[self.current_step_idx]["id"]
            if step_id not in self.completed_steps:
                self.completed_steps.append(step_id)
            self.current_step_idx += 1
        
        if self.current_step_idx >= len(WIZARD_STEPS):
            self.status = "completed"
        
        return {
            "session_id": self.session_id,
            "previous_step": WIZARD_STEPS[min(self.current_step_idx - 1, len(WIZARD_STEPS) - 1)]["id"] if self.current_step_idx > 0 else None,
            "current_step": self.get_current_step(),
            "progress": self.to_dict()["progress"],
            "status": self.status,
        }
    
    def go_back(self) -> dict:
        """ย้อนกลับไป step ก่อน"""
        self.updated_at = datetime.now()
        if self.current_step_idx > 0:
            prev_id = WIZARD_STEPS[self.current_step_idx - 1]["id"]
            if prev_id in self.completed_steps:
                self.completed_steps.remove(prev_id)
            self.current_step_idx -= 1
        return {
            "session_id": self.session_id,
            "current_step": self.get_current_step(),
            "progress": self.to_dict()["progress"],
        }


# ─── Session Manager ─────────────────────────────────────────────────────────

class WizardSessionManager:
    """จัดการ Wizard sessions ทั้งหมด (in-memory)"""
    
    def __init__(self):
        self._sessions: dict[str, WizardSession] = {}
    
    def create_session(self) -> WizardSession:
        session = WizardSession()
        self._sessions[session.session_id] = session
        logger.info(f"Wizard session created: {session.session_id}")
        return session
    
    def get_session(self, session_id: str) -> Optional[WizardSession]:
        session = self._sessions.get(session_id)
        if not session:
            return None
        # Auto-cancel stale sessions (>24h)
        if session.status == "active" and (datetime.now() - session.updated_at).total_seconds() > 86400:
            session.status = "cancelled"
        return session
    
    def delete_session(self, session_id: str):
        self._sessions.pop(session_id, None)
    
    def list_sessions(self, status: str = None) -> list:
        sessions = list(self._sessions.values())
        if status:
            sessions = [s for s in sessions if s.status == status]
        return [s.to_dict() for s in sorted(sessions, key=lambda s: s.updated_at, reverse=True)]


# Singleton
_manager = None
def get_manager() -> WizardSessionManager:
    global _manager
    if _manager is None:
        _manager = WizardSessionManager()
    return _manager


# ─── Wizard Step Handlers ───────────────────────────────────────────────────

def handle_step_provider(session: WizardSession, provider_id: str) -> dict:
    """Step 1: เลือก POD provider"""
    providers = get_providers()
    provider = next((p for p in providers if p["id"] == provider_id), None)
    if not provider:
        return {"ok": False, "error": f"ไม่พบ provider: {provider_id}", "available": [p["id"] for p in providers]}
    
    session.provider = provider_id
    return {
        "ok": True,
        "provider": provider,
        "next_step": "category",
    }


def handle_step_category(session: WizardSession, category: str) -> dict:
    """Step 2: เลือกหมวดหมู่สินค้า"""
    categories = get_categories()
    if category not in categories:
        return {"ok": False, "error": f"ไม่พบหมวดหมู่: {category}", "available": categories}
    
    session.category = category
    products = get_product_catalog(provider_id=session.provider or "printful", category=category)
    
    return {
        "ok": True,
        "category": category,
        "products": products,
        "next_step": "product",
    }


def handle_step_product(session: WizardSession, product_id: str) -> dict:
    """Step 3: เลือกสินค้า"""
    product = get_product_detail(product_id, session.provider or "printful")
    if not product:
        return {"ok": False, "error": f"ไม่พบสินค้า: {product_id}"}
    
    session.product_id = product_id
    session.variant_color = None
    session.variant_size = None
    
    return {
        "ok": True,
        "product": product,
        "next_step": "variant",
    }


def handle_step_variant(session: WizardSession, color: str = None, size: str = None) -> dict:
    """Step 4: เลือกสีและขนาด"""
    if not session.product_id:
        return {"ok": False, "error": "ยังไม่ได้เลือกสินค้า"}
    
    product = get_product_detail(session.product_id)
    if not product:
        return {"ok": False, "error": "ไม่พบข้อมูลสินค้า"}
    
    if color:
        session.variant_color = color
    if size:
        session.variant_size = size
    
    return {
        "ok": True,
        "product_id": session.product_id,
        "selected_color": session.variant_color,
        "selected_size": session.variant_size,
        "colors": product.get("pf_colors", []),
        "sizes": product.get("pf_sizes", []),
        "pricing": product.get("pf_pricing", {}),
        "next_step": "artwork",
    }


def handle_step_artwork(session: WizardSession, width_px: int = 0, height_px: int = 0,
                         dpi: int = 0, file_size_mb: float = 0, file_type: str = "",
                         image_url: str = None) -> dict:
    """Step 5: ตรวจสอบ artwork"""
    if not session.product_id:
        return {"ok": False, "error": "ยังไม่ได้เลือกสินค้า"}
    
    # Store artwork info
    session.artwork_info = {
        "width_px": width_px,
        "height_px": height_px,
        "dpi": dpi,
        "file_size_mb": file_size_mb,
        "file_type": file_type,
        "image_url": image_url,
    }
    
    # Validate using pod_sizes
    image_info = {
        "width_px": width_px,
        "height_px": height_px,
        "dpi": dpi,
        "file_size_mb": file_size_mb,
        "file_type": file_type,
    }
    
    result = validate_artwork(image_info, session.product_id)
    session.artwork_validation = result
    
    # Also get artwork spec
    product = get_product_detail(session.product_id)
    artwork_spec = product.get("artwork_spec", {}) if product else {}
    
    return {
        "ok": result["valid"],
        "artwork_info": session.artwork_info,
        "validation": result,
        "artwork_spec": artwork_spec,
        "next_step": "mockup",
    }


def handle_step_mockup(session: WizardSession, product_image_desc: str = "") -> dict:
    """Step 6: สร้าง prompt สำหรับ mockup"""
    if not session.product_id:
        return {"ok": False, "error": "ยังไม่ได้เลือกสินค้า"}
    
    prompt = get_mockup_prompt(session.product_id, product_image_desc)
    
    return {
        "ok": True,
        "product_id": session.product_id,
        "mockup_prompt": prompt,
        "note": "ใช้ prompt นี้กับ Prodia / AI image generator เพื่อสร้าง mockup",
        "next_step": "content",
    }


def handle_step_content(session: WizardSession, product_name: str = "",
                         product_desc: str = "", style: str = "modern") -> dict:
    """Step 7: AI generate title + description + tags"""
    if not session.product_id:
        return {"ok": False, "error": "ยังไม่ได้เลือกสินค้า"}
    
    # Get product spec for context
    product = get_product_detail(session.product_id)
    spec = product.get("artwork_spec", {}) if product else {}
    
    # Build AI prompt
    prompt_context = f"""
Product Type: {product.get('name') if product else session.product_id}
Customer's Product Name: {product_name}
Description: {product_desc}
Style: {style}
Artwork Size: {spec.get('width_px','?')}x{spec.get('height_px','?')}px
Print Area: {spec.get('print_area','?')}
Technique: {spec.get('print_technique','?')}
"""
    
    session.generated_content = {
        "product_name": product_name,
        "product_desc": product_desc,
        "style": style,
        "ai_prompt_context": prompt_context,
        "note": "ใช้ Assistant AI (_call_gemini) เพื่อ generate title + description + tags ได้จาก prompt นี้",
    }
    
    return {
        "ok": True,
        "content": session.generated_content,
        "next_step": "pricing",
    }


def handle_step_pricing(session: WizardSession, selling_price: float, region: str = "US") -> dict:
    """Step 8: คำนวณราคาและกำไร"""
    if not session.product_id:
        return {"ok": False, "error": "ยังไม่ได้เลือกสินค้า"}
    
    session.selling_price = selling_price
    calculation = get_profit_calculation(session.product_id, selling_price, region)
    session.pricing = calculation
    
    return {
        "ok": True,
        "pricing": calculation,
        "next_step": "summary",
    }


def handle_step_summary(session: WizardSession) -> dict:
    """Step 9: สรุปทั้งหมด"""
    if not session.product_id:
        return {"ok": False, "error": "ยังไม่ได้เลือกสินค้า"}
    
    product = get_product_detail(session.product_id)
    spec = product.get("artwork_spec", {}) if product else {}
    
    return {
        "ok": True,
        "session": session.to_dict(),
        "summary": {
            "provider": session.provider,
            "category": session.category,
            "product_name": product.get("name") if product else session.product_id,
            "artwork_spec": spec,
            "variant": {
                "color": session.variant_color,
                "size": session.variant_size,
            },
            "artwork_valid": session.artwork_validation.get("valid") if session.artwork_validation else None,
            "artwork_score": session.artwork_validation.get("score") if session.artwork_validation else None,
            "has_mockup": session.mockup_image_url is not None,
            "has_content": session.generated_content is not None,
            "pricing": session.pricing,
            "selling_price": session.selling_price,
        },
        "next_steps": [
            "1. ✅ ใช้ Computer Use: login Printful → เลือก product + upload artwork",
            "2. ✅ หรือใช้ prompt mockup ข้างต้นกับ AI image generator",
            "3. ✅ publish ไป Etsy / Shopify โดยตรง",
        ],
    }


if __name__ == "__main__":
    # Test
    logging.basicConfig(level=logging.INFO)
    mgr = get_manager()
    
    # Create session
    s = mgr.create_session()
    print(f"\n=== Session {s.session_id} ===")
    print(json.dumps(s.to_dict(), indent=2, ensure_ascii=False))
    
    print(f"\n=== Steps ===")
    for i, step in enumerate(WIZARD_STEPS):
        print(f"  {i+1}. {step['icon']} {step['title']} — {step['description']}")
