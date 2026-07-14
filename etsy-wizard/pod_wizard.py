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
    get_profit_calculation,
    get_shipping_estimate,
    get_printful_api,
    get_printful_printfiles,
    get_printful_mockup_templates,
    create_printful_mockup,
    check_mockup_task,
)
from pod_sizes import validate_artwork

logger = logging.getLogger("pod-wizard")

# ─── Wizard State ───────────────────────────────────────────────────────────

WIZARD_STEPS = [
    {"id": "provider",     "title": "เลือก Provider",         "icon": "🏪", "description": "Printful / Printify / Gelato"},
    {"id": "category",     "title": "เลือกหมวดหมู่",          "icon": "📁", "description": "เสื้อผ้า / แก้วน้ำ / ของตกแต่งบ้าน"},
    {"id": "product",      "title": "เลือกสินค้า",            "icon": "🎯", "description": "เลือกประเภทสินค้า + ดู spec"},
    {"id": "variant",      "title": "สีและขนาด",             "icon": "🎨", "description": "เลือกสี/ขนาด/วัสดุ"},
    {"id": "print_info",   "title": "พื้นที่พิมพ์",           "icon": "📐", "description": "ดู print area + placements จาก Printful"},
    {"id": "artwork",      "title": "สร้าง Artwork",          "icon": "🎨", "description": "AI gen design ตามขนาด print area"},
    {"id": "mockup",       "title": "สร้าง Mockup",           "icon": "✨", "description": "Printful Mockup API — สร้างรูปสินค้าจริง"},
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
        self.variant_colors = []
        self.variant_sizes = []
        
        # Print area from Printful templates
        self.print_info = None            # printful templates + printfiles data
        self.selected_placements = []     # placements ที่ user เลือก (front, back...)
        
        # Artwork
        self.artwork_info = None          # generated/uploaded artwork info
        self.artwork_validation = None    # validate result
        self.artwork_image_url = None     # URL ของ artwork ที่ gen/upload
        
        # Mockup
        self.mockup_image_url = None
        self.mockup_task_key = None       # Printful task key สำหรับ polling
        self.mockup_task_status = None    # pending | completed | failed
        self.mockup_results = []          # list of mockup image URLs
        
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
            "variant_colors": getattr(self, 'variant_colors', []),
            "variant_sizes": getattr(self, 'variant_sizes', []),
            "has_print_info": self.print_info is not None,
            "selected_placements": getattr(self, 'selected_placements', []),
            "has_artwork": self.artwork_image_url is not None,
            "artwork_valid": self.artwork_validation.get("valid") if self.artwork_validation else None,
            "has_mockup": self.mockup_image_url is not None,
            "mockup_task_status": self.mockup_task_status,
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


def handle_step_variant(session: WizardSession, colors: list = None, sizes: list = None,
                         color: str = None, size: str = None) -> dict:
    """Step 4: เลือกสีและขนาด (multi-select)"""
    if not session.product_id:
        return {"ok": False, "error": "ยังไม่ได้เลือกสินค้า"}
    
    product = get_product_detail(session.product_id)
    if not product:
        return {"ok": False, "error": "ไม่พบข้อมูลสินค้า"}
    
    # Accept both multi-select (colors/sizes arrays) and legacy single-select
    if colors:
        session.variant_colors = colors
    elif color:
        session.variant_colors = [color]
    if sizes:
        session.variant_sizes = sizes
    elif size:
        session.variant_sizes = [size]
    
    return {
        "ok": True,
        "product_id": session.product_id,
        "selected_colors": getattr(session, 'variant_colors', []),
        "selected_sizes": getattr(session, 'variant_sizes', []),
        "colors": product.get("pf_colors", []),
        "sizes": product.get("pf_sizes", []),
        "pricing": product.get("pf_pricing", {}),
        "next_step": "print_info",
    }


def handle_step_print_info(session: WizardSession, **kwargs) -> dict:
    """Step 5: ดึง print area + placements จาก Printful"""
    if not session.product_id:
        return {"ok": False, "error": "ยังไม่ได้เลือกสินค้า"}
    
    # Get product detail to find Printful product ID
    product = get_product_detail(session.product_id)
    pf_id = product.get("pf_product_id") if product else None
    if not pf_id:
        return {"ok": False, "error": "Printful product ID ไม่พร้อมใช้งาน"}
    
    # Fetch Printful templates
    pf = get_printful_printfiles(pf_id)
    templates = get_printful_mockup_templates(pf_id)
    
    if not pf:
        return {"ok": False, "error": "ไม่สามารถดึงข้อมูล print area จาก Printful"}
    
    placements = pf.get("available_placements", {})
    printfiles = pf.get("printfiles", [])
    
    session.print_info = {
        "pf_product_id": pf_id,
        "placements": placements,
        "printfiles": printfiles,
        "variant_printfiles": pf.get("variant_printfiles", {}),
        "templates_count": len(templates.get("templates", [])) if templates else 0,
        "min_dpi": templates.get("min_dpi") if templates else 150,
    }
    
    return {
        "ok": True,
        "product_id": session.product_id,
        "print_info": {
            "pf_product_id": pf_id,
            "placements": placements,
            "printfiles": printfiles,
        },
        "note": f"เลือก placements ที่ต้องการ แล้วไป Step ถัดไปเพื่อสร้าง artwork",
        "next_step": "artwork",
    }


def handle_step_artwork(session: WizardSession, prompt: str = "",
                         image_url: str = None, width_px: int = 0, height_px: int = 0, **kwargs) -> dict:
    """
    Step 6: สร้าง artwork / อัปโหลด
    
    ถ้ามี prompt → ส่งไป AI gen artwork ตามขนาด print area
    ถ้ามี image_url → ใช้อัปโหลดที่ upload แล้ว
    """
    if not session.product_id:
        return {"ok": False, "error": "ยังไม่ได้เลือกสินค้า"}
    
    artwork_spec = {}
    product = get_product_detail(session.product_id)
    if product:
        artwork_spec = product.get("artwork_spec", {})
    
    session.artwork_info = {
        "prompt": prompt,
        "image_url": image_url,
        "width_px": width_px,
        "height_px": height_px,
        "artwork_spec": artwork_spec,
    }
    
    if image_url:
        session.artwork_image_url = image_url
    elif not session.artwork_image_url:
        # Preserve existing artwork URL from AI gen step if not overwritten
        pass
    
    return {
        "ok": True,
        "artwork_info": session.artwork_info,
        "artwork_spec": artwork_spec,
        "print_info": session.print_info,
        "ai_generate_hint": prompt or "ใช้ prompt นี้กับ /ai/generate-image",
        "next_step": "mockup",
    }


def handle_step_mockup(session: WizardSession, placements: list = None) -> dict:
    """
    Step 7: สร้าง mockup ผ่าน Printful Mockup API
    
    placements = ["front", "back"] — placements ที่ user เลือก
    ต้องมี artwork_image_url ก่อน
    """
    if not session.product_id:
        return {"ok": False, "error": "ยังไม่ได้เลือกสินค้า"}
    if not session.artwork_image_url and not session.artwork_info.get("image_url"):
        return {"ok": False, "error": "ยังไม่มี artwork — ไปสร้าง artwork ก่อน"}
    
    artwork_url = session.artwork_image_url or session.artwork_info.get("image_url", "")
    if not artwork_url:
        return {"ok": False, "error": "ไม่พบ artwork URL"}
    
    # Convert relative URL to absolute for Printful API
    if artwork_url.startswith("/"):
        artwork_url = "https://m2igen.com" + artwork_url
    
    # หา Printful product ID
    product = get_product_detail(session.product_id)
    pf_id = product.get("pf_product_id") if product else None
    if not pf_id:
        return {"ok": False, "error": "Printful product ID ไม่พร้อมใช้งาน"}
    
    # ใช้ placements ที่เลือก หรือทั้งหมด
    session.selected_placements = placements or ["front"]
    
    # ดึง variant IDs ที่ตรงกับสี/ขนาดที่เลือก
    variant_ids = []
    pf_data = product.get("pf_data") if product else None
    if product and product.get("pf_data_available"):
        api = get_printful_api()
        pf_data = api.fetch_product(pf_id)
        if pf_data:
            variants = pf_data.get("variants", [])
            for v in variants:
                color = v.get("color", "")
                size = v.get("size", "")
                # Match variant โดยใช้สี/ขนาดที่ user เลือก
                if session.variant_colors and color in session.variant_colors:
                    if not session.variant_sizes or size in session.variant_sizes:
                        variant_ids.append(v["id"])
    
    if not variant_ids:
        variant_ids = [9575]  # fallback: first variant
    
    # Build files payload
    files = []
    # Build placement-to-printfile mapping from printfiles data
    pf_data = get_printful_printfiles(pf_id)
    placement_printfile = {}
    if pf_data:
        available = pf_data.get("available_placements", {})
        # Printful auto-selects printfile when we omit printfile_id
        pass  # We'll omit printfile_id and let Printful auto-select
    
    # Use printfile dimensions for position if available
    pf_list = pf_data.get("printfiles", []) if pf_data else []
    # Default position: match the printfile area for front
    default_width = 1800
    default_height = 2400
    for pf_entry in pf_list:
        if pf_entry.get("printfile_id") == 1:
            default_width = pf_entry.get("width", 1800)
            default_height = pf_entry.get("height", 2400)
            break
    
    for placement in session.selected_placements:
        # Look for matching printfile size for this placement
        p_width = default_width
        p_height = default_height
        if placement == "front_large":
            for pf_entry in pf_list:
                if pf_entry.get("printfile_id") == 333:
                    p_width = pf_entry.get("width", 2250)
                    p_height = pf_entry.get("height", 2700)
                    break
        elif placement in ("back", "sleeve_left", "sleeve_right"):
            for pf_entry in pf_list:
                if pf_entry.get("printfile_id") == 71:
                    p_width = pf_entry.get("width", 450)
                    p_height = pf_entry.get("height", 450)
                    break
        elif "label" in placement:
            for pf_entry in pf_list:
                if pf_entry.get("printfile_id") == 130:
                    p_width = pf_entry.get("width", 600)
                    p_height = pf_entry.get("height", 525)
                    break
        
        # Printful position format: area_width/area_height = printfile bounds,
        # width/height = artwork size within area, top/left = offset
        files.append({
            "placement": placement,
            "image_url": artwork_url,
            "position": {
                "area_width": p_width,
                "area_height": p_height,
                "width": p_width,
                "height": p_height,
                "top": 0,
                "left": 0
            }
        })
    
    # Create mockup task
    result = create_printful_mockup(
        product_id=pf_id,
        variant_ids=variant_ids[:5],  # limit เพื่อป้องกัน timeout
        files=files,
    )
    
    if not result:
        # Mockup failed — allow skip, mark as "skipped" so wizard can continue
        session.mockup_task_status = "skipped"
        return {
            "ok": True,
            "task_key": None,
            "mockup_skipped": True,
            "variant_ids": variant_ids[:5],
            "placements": session.selected_placements,
            "note": "⚠️ Mockup API ล้มเหลว — ข้ามไปก่อนได้ (สร้าง mockup ทีหลังที่ Printful)",
            "next_step": "content",
        }
    
    task_key = result.get("task_key", "")
    session.mockup_task_key = task_key
    session.mockup_task_status = "pending"
    
    return {
        "ok": True,
        "task_key": task_key,
        "variant_ids": variant_ids[:5],
        "placements": session.selected_placements,
        "note": f"Mockup task กำลังสร้าง — ใช้ task_key={task_key} เพื่อตรวจสอบสถานะ",
        "next_step": "content",
    }


def handle_step_mockup_status(session: WizardSession) -> dict:
    """ตรวจสอบสถานะ mockup task"""
    if not session.mockup_task_key:
        return {"ok": False, "error": "ไม่มี mockup task"}
    
    result = check_mockup_task(session.mockup_task_key)
    if not result:
        return {"ok": False, "error": "ตรวจสอบสถานะไม่ได้"}
    
    status = result.get("status", "unknown")
    session.mockup_task_status = status
    
    if status == "completed":
        mockups = result.get("mockups", [])
        session.mockup_results = mockups
        if mockups:
            session.mockup_image_url = mockups[0].get("mockup_url", "")
    
    return {
        "ok": True,
        "task_key": session.mockup_task_key,
        "status": status,
        "mockups": result.get("mockups", [])[:3] if status == "completed" else [],
        "has_mockup": session.mockup_image_url is not None,
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
                "colors": getattr(session, 'variant_colors', []),
                "sizes": getattr(session, 'variant_sizes', []),
            },
            "artwork_valid": session.artwork_validation.get("valid") if session.artwork_validation else None,
            "has_artwork": session.artwork_image_url is not None,
            "print_info": session.print_info is not None,
            "selected_placements": session.selected_placements,
            "mockup_task": session.mockup_task_key is not None,
            "mockup_status": session.mockup_task_status,
            "mockup_images": len(session.mockup_results),
            "has_content": session.generated_content is not None,
            "pricing": session.pricing,
            "selling_price": session.selling_price,
        },
        "next_steps": [
            "1. ✅ Artwork พร้อม ขนาดตรง print area",
            "2. ✅ Mockup จาก Printful วัสดุและตำแหน่งถูกต้อง",
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
