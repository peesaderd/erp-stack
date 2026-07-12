"""
Print on Demand — Artwork Size Reference & Validator
อ้างอิงขนาดไฟล์งาน POD จาก Printful, Printify, Gelato
"""

# ─── POD Product Size Reference ──────────────────────────────────────────
# Source: Printful, Printify, Gelato standards (as of 2025-2026)
# All sizes in pixels @ 300 DPI (industry standard for print)

POD_PRODUCTS = [
    # ---- Apparel ----
    {
        "id": "tshirt_standard",
        "name": "เสื้อยืดมาตรฐาน (Standard T-Shirt)",
        "category": "apparel",
        "print_area": "หน้าอก (Chest)",
        "width_inch": 12,
        "height_inch": 16,
        "width_px_300": 3600,
        "height_px_300": 4800,
        "dpi_min": 150,
        "dpi_recommended": 300,
        "aspect_ratio": "3:4",
        "orientation": "portrait",
        "file_type": "PNG / JPEG",
        "max_file_size_mb": 25,
        "notes": "เว้นขอบ 0.5 นิ้วรอบด้าน (bleed) อย่าให้ text/logo ชิดขอบเกิน 1 นิ้ว",
        "providers": ["Printful", "Printify", "Gelato"],
        "print_technique": "DTG (Direct-to-Garment)",
    },
    {
        "id": "hoodie_standard",
        "name": "ฮู้ดดี้ (Standard Hoodie)",
        "category": "apparel",
        "print_area": "หน้าอก (Chest)",
        "width_inch": 13,
        "height_inch": 17,
        "width_px_300": 3900,
        "height_px_300": 5100,
        "dpi_min": 150,
        "dpi_recommended": 300,
        "aspect_ratio": "13:17",
        "orientation": "portrait",
        "file_type": "PNG / JPEG",
        "max_file_size_mb": 25,
        "notes": "เสื้อแขนยาว → พื้นที่พิมพ์ใหญ่กว่าเสื้อยืดเล็กน้อย อย่าให้ลายตกถึงตะเข็บ",
        "providers": ["Printful", "Printify"],
        "print_technique": "DTG / Embroidery",
    },
    {
        "id": "tank_top",
        "name": "เสื้อกล้าม (Tank Top)",
        "category": "apparel",
        "print_area": "หน้าอก (Chest)",
        "width_inch": 10,
        "height_inch": 14,
        "width_px_300": 3000,
        "height_px_300": 4200,
        "dpi_min": 150,
        "dpi_recommended": 300,
        "aspect_ratio": "5:7",
        "orientation": "portrait",
        "file_type": "PNG / JPEG",
        "max_file_size_mb": 25,
        "notes": "พื้นที่พิมพ์จำกัดกว่าเสื้อยืด เน้นลายขนาดกลาง",
        "providers": ["Printful", "Printify"],
        "print_technique": "DTG",
    },
    {
        "id": "leggings",
        "name": "เลกกิ้ง (Leggings)",
        "category": "apparel",
        "print_area": "All-over print (เต็มตัว)",
        "width_inch": 16,
        "height_inch": 36,
        "width_px_300": 4800,
        "height_px_300": 10800,
        "dpi_min": 150,
        "dpi_recommended": 300,
        "aspect_ratio": "4:9",
        "orientation": "portrait",
        "file_type": "PNG",
        "max_file_size_mb": 50,
        "notes": "Full-wrap print ต้อง seamless repeatable pattern หรือออกแบบให้ลายต่อกัน",
        "providers": ["Printful", "Printify"],
        "print_technique": "All-over sublimation",
    },

    # ---- Drinkware ----
    {
        "id": "mug_11oz",
        "name": "แก้ว Mug 11oz (มาตรฐาน)",
        "category": "drinkware",
        "print_area": "ด้านหน้าแก้ว",
        "width_inch": 8.5,
        "height_inch": 3.7,
        "width_px_300": 2550,
        "height_px_300": 1110,
        "dpi_min": 200,
        "dpi_recommended": 300,
        "aspect_ratio": "2.3:1",
        "orientation": "landscape",
        "file_type": "PNG / JPEG",
        "max_file_size_mb": 20,
        "notes": "โค้งตามแก้ว → text อย่าชิดขอบซ้าย-ขวาเกิน 1 ซม. ใช้ bleed 0.125 นิ้ว",
        "providers": ["Printful", "Printify", "Gelato"],
        "print_technique": "Sublimation",
    },
    {
        "id": "mug_15oz",
        "name": "แก้ว Mug 15oz (ใหญ่)",
        "category": "drinkware",
        "print_area": "ด้านหน้าแก้ว",
        "width_inch": 9.5,
        "height_inch": 4.2,
        "width_px_300": 2850,
        "height_px_300": 1260,
        "dpi_min": 200,
        "dpi_recommended": 300,
        "aspect_ratio": "2.26:1",
        "orientation": "landscape",
        "file_type": "PNG / JPEG",
        "max_file_size_mb": 20,
        "notes": "แก้วใหญ่ขึ้น → พื้นที่พิมพ์กว้างกว่า 11oz",
        "providers": ["Printful", "Printify"],
        "print_technique": "Sublimation",
    },
    {
        "id": "water_bottle",
        "name": "ขวดน้ำ (Water Bottle)",
        "category": "drinkware",
        "print_area": "Wrap-around",
        "width_inch": 10,
        "height_inch": 7.5,
        "width_px_300": 3000,
        "height_px_300": 2250,
        "dpi_min": 200,
        "dpi_recommended": 300,
        "aspect_ratio": "4:3",
        "orientation": "landscape",
        "file_type": "PNG",
        "max_file_size_mb": 25,
        "notes": "Wrap-around → ต้องเผื่อซ้าย-ขวา 0.25 นิ้ว ชดเชยความโค้ง",
        "providers": ["Printful", "Printify"],
        "print_technique": "Sublimation",
    },

    # ---- Home & Living ----
    {
        "id": "canvas_print",
        "name": "แคนวาส (Canvas Print) 8x10",
        "category": "home",
        "print_area": "เต็มพื้นที่",
        "width_inch": 8,
        "height_inch": 10,
        "width_px_300": 2400,
        "height_px_300": 3000,
        "dpi_min": 150,
        "dpi_recommended": 300,
        "aspect_ratio": "4:5",
        "orientation": "portrait",
        "file_type": "JPEG / PNG",
        "max_file_size_mb": 25,
        "notes": "Bleed 0.125 นิ้วรอบด้าน เผื่อ wrap-around ขอบ canvas",
        "providers": ["Printful", "Printify", "Gelato"],
        "print_technique": "Giclée",
    },
    {
        "id": "poster_18x24",
        "name": "โปสเตอร์ (Poster) 18x24",
        "category": "home",
        "print_area": "เต็มพื้นที่",
        "width_inch": 18,
        "height_inch": 24,
        "width_px_300": 5400,
        "height_px_300": 7200,
        "dpi_min": 150,
        "dpi_recommended": 300,
        "aspect_ratio": "3:4",
        "orientation": "portrait",
        "file_type": "JPEG / PNG",
        "max_file_size_mb": 50,
        "notes": "Bleed 0.125 นิ้ว สำหรับขนาดอื่น: 11x14, 12x18, 24x36",
        "providers": ["Printful", "Printify", "Gelato"],
        "print_technique": "Giclée",
    },
    {
        "id": "pillow_square",
        "name": "หมอนอิง (Throw Pillow) 18x18 นิ้ว",
        "category": "home",
        "print_area": "ด้านหน้า",
        "width_inch": 18,
        "height_inch": 18,
        "width_px_300": 5400,
        "height_px_300": 5400,
        "dpi_min": 150,
        "dpi_recommended": 300,
        "aspect_ratio": "1:1",
        "orientation": "square",
        "file_type": "PNG / JPEG",
        "max_file_size_mb": 25,
        "notes": "ถ้าซิปตรงกลาง → แยกดีไซน์ซ้าย-ขวาได้",
        "providers": ["Printful", "Printify"],
        "print_technique": "Sublimation",
    },
    {
        "id": "tote_bag",
        "name": "กระเป๋าผ้า (Tote Bag)",
        "category": "accessories",
        "print_area": "หน้ากระเป๋า",
        "width_inch": 12,
        "height_inch": 14,
        "width_px_300": 3600,
        "height_px_300": 4200,
        "dpi_min": 150,
        "dpi_recommended": 300,
        "aspect_ratio": "6:7",
        "orientation": "portrait",
        "file_type": "PNG / JPEG",
        "max_file_size_mb": 25,
        "notes": "พิมพ์หน้าเดียว เผื่อขอบ 0.5 นิ้ว",
        "providers": ["Printful", "Printify"],
        "print_technique": "DTG / Sublimation",
    },

    # ---- Phone Cases ----
    {
        "id": "phone_case_iphone",
        "name": "เคสโทรศัพท์ (Phone Case) — iPhone/Android",
        "category": "accessories",
        "print_area": "ด้านหลัง",
        "width_inch": 6,
        "height_inch": 10,
        "width_px_300": 1800,
        "height_px_300": 3000,
        "dpi_min": 200,
        "dpi_recommended": 300,
        "aspect_ratio": "3:5",
        "orientation": "portrait",
        "file_type": "PNG",
        "max_file_size_mb": 15,
        "notes": "ต้องใช้ template ตามรุ่นโทรศัพท์ เคสแต่ละรุ่นมี cutout ต่างกัน",
        "providers": ["Printful", "Printify"],
        "print_technique": "UV print / Sublimation",
    },

    # ---- Stationery ----
    {
        "id": "notebook",
        "name": "สมุดโน้ต (Notebook / Journal)",
        "category": "stationery",
        "print_area": "ปกหน้า",
        "width_inch": 8,
        "height_inch": 10,
        "width_px_300": 2400,
        "height_px_300": 3000,
        "dpi_min": 150,
        "dpi_recommended": 300,
        "aspect_ratio": "4:5",
        "orientation": "portrait",
        "file_type": "JPEG / PNG",
        "max_file_size_mb": 20,
        "notes": "ถ้า cover wrap → ต้องออกแบบรวมปกหน้า+ปกหลัง+สัน",
        "providers": ["Printful", "Printify", "Gelato"],
        "print_technique": "Offset / Digital",
    },
]


def get_product(product_id: str) -> dict:
    """ค้นหา POD product ตาม ID"""
    for p in POD_PRODUCTS:
        if p["id"] == product_id:
            return p
    return None


def list_products(category: str = None) -> list:
    """รายการ POD products ทั้งหมด หรือกรองตาม category"""
    if category:
        return [p for p in POD_PRODUCTS if p["category"] == category]
    return list(POD_PRODUCTS)


def get_categories() -> list:
    """รายการหมวดหมู่ POD products"""
    cats = set()
    for p in POD_PRODUCTS:
        cats.add(p["category"])
    return sorted(cats)


def validate_artwork(image_info: dict, product_id: str) -> dict:
    """
    ตรวจสอบ artwork ว่าพอดีกับ POD product หรือไม่

    image_info = {
        "width_px": 3000,
        "height_px": 2400,
        "dpi": 300,
        "file_size_mb": 3.5,
        "file_type": "PNG",
    }
    """
    product = get_product(product_id)
    if not product:
        return {"valid": False, "error": f"ไม่พบ Product ID: {product_id}"}

    errors = []
    warnings = []

    w = image_info.get("width_px", 0)
    h = image_info.get("height_px", 0)
    dpi = image_info.get("dpi", 0)
    file_size = image_info.get("file_size_mb", 0)
    file_type = image_info.get("file_type", "").upper()

    # 1. ตรวจสอบขนาด (px)
    pw = product["width_px_300"]
    ph = product["height_px_300"]

    if w == 0 or h == 0:
        errors.append("❌ ไม่สามารถอ่านขนาดรูปได้ (width/height = 0)")
    else:
        if w < pw * 0.5 or h < ph * 0.5:
            errors.append(f"❌ รูปเล็กเกินไป! ต้องการอย่างน้อย {pw}x{ph}px @300dpi (ได้ {w}x{h}px)")
        elif w < pw * 0.8 or h < ph * 0.8:
            warnings.append(f"⚠️ รูปอาจเล็กไปเล็กน้อย แนะนำ {pw}x{ph}px (ได้ {w}x{h}px)")
        else:
            # ตรวจสอบ aspect ratio
            img_ratio = w / h
            prod_ratio_str = product["aspect_ratio"]
            ratio_parts = [float(x) for x in prod_ratio_str.split(":")]
            prod_ratio = ratio_parts[0] / ratio_parts[1]

            ratio_diff = abs(img_ratio - prod_ratio) / prod_ratio * 100
            if ratio_diff > 15:
                warnings.append(f"⚠️ Aspect ratio ต่างจากที่แนะนำ ({prod_ratio_str}) อยู่ {ratio_diff:.0f}% — ต้อง crop หรือยืดรูป")

    # 2. ตรวจสอบ DPI
    if dpi > 0:
        if dpi < product["dpi_min"]:
            errors.append(f"❌ DPI ต่ำเกินไป! ได้ {dpi}dpi ต้องการอย่างน้อย {product['dpi_min']}dpi")
        elif dpi < product["dpi_recommended"] * 0.7:
            warnings.append(f"⚠️ DPI อาจต่ำไป แนะนำ {product['dpi_recommended']}dpi (ได้ {dpi}dpi)")
    else:
        # ประมาณ DPI จากขนาด pixel ถ้ารู้ขนาดจริง
        if w > 0 and h > 0:
            est_dpi_w = w / product["width_inch"]
            est_dpi_h = h / product["height_inch"]
            est_dpi = min(est_dpi_w, est_dpi_h)
            if est_dpi < product["dpi_min"]:
                warnings.append(f"⚠️ DPI โดยประมาณต่ำ ({est_dpi:.0f}dpi) — ใช้ความละเอียดสูงขึ้น")

    # 3. ตรวจสอบ file type
    if file_type:
        allowed = product["file_type"].replace(" ", "").split("/")
        if file_type not in allowed and file_type not in [x.upper() for x in allowed]:
            if file_type not in ["JPEG", "PNG", "SVG", "PDF", "PSD", "TIFF", "WEBP"]:
                warnings.append(f"⚠️ ไฟล์ {file_type} อาจไม่รองรับ แนะนำ {product['file_type']}")

    # 4. ตรวจสอบ file size
    if file_size > 0 and product["max_file_size_mb"] > 0:
        if file_size > product["max_file_size_mb"]:
            warnings.append(f"⚠️ ไฟล์ใหญ่ ({file_size:.1f}MB) อาจเกิน limit ({product['max_file_size_mb']}MB)")

    # 5. ตรวจสอบ orientation
    if w > 0 and h > 0:
        is_landscape = w > h
        prod_is_landscape = float(product["aspect_ratio"].split(":")[0]) > float(product["aspect_ratio"].split(":")[1])
        if is_landscape != prod_is_landscape:
            warnings.append(f"⚠️ รูปเป็น {'แนวนอน' if is_landscape else 'แนวตั้ง'} แต่สินค้า {'แนวนอน' if prod_is_landscape else 'แนวตั้ง'} — crop หรือ rotate ก่อนส่งพิมพ์")

    score = _calculate_score(errors, warnings)

    return {
        "valid": len(errors) == 0,
        "product_name": product["name"],
        "product_id": product_id,
        "image_size_px": f"{w}x{h}",
        "required_size_px": f"{pw}x{ph}",
        "required_size_inch": f'{product["width_inch"]}x{product["height_inch"]}',
        "dpi": dpi,
        "errors": errors,
        "warnings": warnings,
        "score": score,
        "score_label": "✅ สมบูรณ์" if score >= 80 else ("⚠️ พอใช้ได้" if score >= 50 else "❌ ต้องแก้ไข"),
        "recommendations": _generate_recommendations(errors, warnings, product, w, h, dpi),
    }


def _calculate_score(errors: list, warnings: list) -> int:
    """คำนวณคะแนน 0-100"""
    score = 100
    score -= len(errors) * 25
    score -= len(warnings) * 10
    return max(0, min(100, score))


def _generate_recommendations(errors: list, warnings: list, product: dict, w: int, h: int, dpi: int) -> list:
    """สร้างคำแนะนำที่ actionable"""
    recs = []

    if errors or warnings:
        if w < product["width_px_300"] or h < product["height_px_300"]:
            ratio = product["width_px_300"] / product["height_px_300"]
            if w > h:  # landscape
                new_w = max(product["width_px_300"], int(h * ratio))
                new_h = max(product["height_px_300"], int(w / ratio))
            else:
                new_h = max(product["height_px_300"], int(w / ratio))
                new_w = max(product["width_px_300"], int(h * ratio))
            recs.append(f"ปรับขนาดรูปเป็น {new_w}x{new_h}px @300dpi หรือใช้โปรแกรม resize")

        if dpi > 0 and (dpi < product["dpi_recommended"] * 0.7):
            recs.append(f"เพิ่ม DPI เป็น {product['dpi_recommended']} — ใน Photoshop: Image > Image Size > Resolution: {product['dpi_recommended']}")

        if w > 0 and h > 0:
            w_real = w / (dpi or 300)
            h_real = h / (dpi or 300)
            if w_real > product["width_inch"] * 1.5 or h_real > product["height_inch"] * 1.5:
                recs.append(f"รูปใหญ่เกินความจำเป็น ({w_real:.1f}x{h_real:.1f} นิ้ว) → resize ลงเพื่อลดขนาดไฟล์")

        recs.append(product.get("notes", ""))
    else:
        recs.append(f"✅ รูปพร้อมพิมพ์! ขนาดพอดีกับ {product['name']}")

    return [r for r in recs if r]


# ─── AI Artwork Review (Gemini) ─────────────────────────────────────────

def ai_review_artwork(product: dict, image_analysis: dict = None) -> dict:
    """
    ให้ AI (Gemini) วิเคราะห์ artwork design และแนะนำการปรับปรุง
    ถ้าไม่มี image_analysis จะแนะนำเฉยๆ ตาม product type
    """
    # This is called from the API endpoint which uses the assistant module
    # The actual Gemini call happens in the endpoint
    pass
