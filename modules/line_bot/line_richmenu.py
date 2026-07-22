"""
LINE Rich Menu Manager
======================
สร้างและจัดการ Rich Menu สำหรับ LINE Bot
ให้มีปุ่มลัดสำหรับ:
  📋 เมนู — ดูเมนูทั้งหมด
  🛒 ตะกร้า — ดูรายการในตะกร้า
  🪑 โต๊ะ — เลือกโต๊ะ
  ✅ สั่ง — ยืนยันออเดอร์
  ❓ Help — วิธีใช้
"""

import os
import json
import io
import logging
from typing import Optional

from .line_client import line_client

logger = logging.getLogger("line-bot.richmenu")

# ── Rich Menu Configs ─────────────────────────────────────────────────────

# Full-size rich menu (2500x1686) — 6 areas (3×2 grid)
RICH_MENU_FULL = {
    "size": {"width": 2500, "height": 1686},
    "selected": True,
    "name": "Restaurant POS - Full",
    "chatBarText": "🍽️ สั่งอาหาร | 📋 เมนู | 🛒 ตะกร้า | ❓ Help",
    "areas": [
        # Row 1 — Col 1: Menu
        {
            "bounds": {"x": 0, "y": 0, "width": 833, "height": 843},
            "action": {
                "type": "postback",
                "data": "show_menu",
                "label": "เมนู",
                "displayText": "📋 ดูเมนู",
            },
        },
        # Row 1 — Col 2: Cart
        {
            "bounds": {"x": 833, "y": 0, "width": 834, "height": 843},
            "action": {
                "type": "postback",
                "data": "view_cart",
                "label": "ตะกร้า",
                "displayText": "🛒 ดูตะกร้า",
            },
        },
        # Row 1 — Col 3: Help
        {
            "bounds": {"x": 1667, "y": 0, "width": 833, "height": 843},
            "action": {
                "type": "postback",
                "data": "show_help",
                "label": "ช่วยเหลือ",
                "displayText": "❓ วิธีใช้",
            },
        },
        # Row 2 — Col 1: Tables
        {
            "bounds": {"x": 0, "y": 843, "width": 833, "height": 843},
            "action": {
                "type": "postback",
                "data": "show_tables",
                "label": "โต๊ะ",
                "displayText": "🪑 ดูโต๊ะ",
            },
        },
        # Row 2 — Col 2: Categories
        {
            "bounds": {"x": 833, "y": 843, "width": 834, "height": 843},
            "action": {
                "type": "postback",
                "data": "show_categories",
                "label": "หมวดหมู่",
                "displayText": "📂 ดูหมวดหมู่",
            },
        },
        # Row 2 — Col 3: Checkout
        {
            "bounds": {"x": 1667, "y": 843, "width": 833, "height": 843},
            "action": {
                "type": "postback",
                "data": "checkout",
                "label": "สั่งเลย",
                "displayText": "✅ ยืนยันออเดอร์",
            },
        },
    ],
}

# Compact rich menu (2500x843) — 4 areas (4×1)
RICH_MENU_COMPACT = {
    "size": {"width": 2500, "height": 843},
    "selected": True,
    "name": "Restaurant POS - Compact",
    "chatBarText": "🍽️ สั่งอาหาร | 📋 เมนู | 🛒 ตะกร้า | ❓ Help",
    "areas": [
        {
            "bounds": {"x": 0, "y": 0, "width": 625, "height": 843},
            "action": {
                "type": "postback",
                "data": "show_menu",
                "label": "เมนู",
                "displayText": "📋 ดูเมนู",
            },
        },
        {
            "bounds": {"x": 625, "y": 0, "width": 625, "height": 843},
            "action": {
                "type": "postback",
                "data": "view_cart",
                "label": "ตะกร้า",
                "displayText": "🛒 ดูตะกร้า",
            },
        },
        {
            "bounds": {"x": 1250, "y": 0, "width": 625, "height": 843},
            "action": {
                "type": "postback",
                "data": "show_tables",
                "label": "โต๊ะ",
                "displayText": "🪑 เลือกโต๊ะ",
            },
        },
        {
            "bounds": {"x": 1875, "y": 0, "width": 625, "height": 843},
            "action": {
                "type": "postback",
                "data": "show_help",
                "label": "Help",
                "displayText": "❓ วิธีใช้",
            },
        },
    ],
}


def _generate_rich_menu_image() -> bytes:
    """
    Generate a rich menu image with colored blocks and text labels.
    Creates a 2500x1686 PNG with 6 labeled buttons.
    """
    try:
        from PIL import Image, ImageDraw, ImageFont

        width, height = 2500, 1686
        img = Image.new("RGBA", (width, height), (255, 255, 255, 255))
        draw = ImageDraw.Draw(img)

        # Try to find a font
        font_paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
        ]
        font_small = None
        font_large = None
        for fp in font_paths:
            if os.path.exists(fp):
                font_large = ImageFont.truetype(fp, 60)
                font_small = ImageFont.truetype(fp, 40)
                break
        if not font_large:
            font_large = ImageFont.load_default()
            font_small = ImageFont.load_default()

        # ── Layout: 3 columns × 2 rows ──
        boxes = [
            {"label": "📋 เมนู", "color": "#E8F5E9", "x": 0, "y": 0, "w": 833, "h": 843},
            {"label": "🛒 ตะกร้า", "color": "#FFF3E0", "x": 833, "y": 0, "w": 834, "h": 843},
            {"label": "❓ Help", "color": "#E3F2FD", "x": 1667, "y": 0, "w": 833, "h": 843},
            {"label": "🪑 โต๊ะ", "color": "#F3E5F5", "x": 0, "y": 843, "w": 833, "h": 843},
            {"label": "📂 หมวดหมู่", "color": "#FBE9E7", "x": 833, "y": 843, "w": 834, "h": 843},
            {"label": "✅ สั่งเลย", "color": "#E8F5E9", "x": 1667, "y": 843, "w": 833, "h": 843},
        ]

        for box in boxes:
            # Parse hex color
            hex_color = box["color"].lstrip("#")
            r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

            # Draw background
            draw.rectangle(
                [box["x"], box["y"], box["x"] + box["w"], box["y"] + box["h"]],
                fill=(r, g, b, 255),
            )
            # Draw border
            draw.rectangle(
                [box["x"], box["y"], box["x"] + box["w"], box["y"] + box["h"]],
                outline=(200, 200, 200, 255), width=4,
            )

            # Draw label text
            label = box["label"]
            bbox = draw.textbbox((0, 0), label, font=font_large)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            tx = box["x"] + (box["w"] - tw) // 2
            ty = box["y"] + (box["h"] - th) // 2
            draw.text((tx, ty), label, fill=(50, 50, 50, 255), font=font_large)

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return buf.getvalue()

    except ImportError:
        logger.error("PIL not installed. Cannot generate rich menu image.")
        return b""
    except Exception as e:
        logger.error(f"Failed to generate rich menu image: {e}")
        return b""


async def setup_rich_menus(force: bool = False) -> Optional[str]:
    """
    Set up default rich menus.
    
    Returns:
        richMenuId of the default menu, or None on failure.
    """
    # Check existing
    menus = await line_client.get_rich_menus()
    existing_name = RICH_MENU_FULL["name"]
    existing_id = None

    for menu in menus:
        if menu.get("name") == existing_name:
            existing_id = menu.get("richMenuId")
            if not force:
                logger.info(f"Rich menu '{existing_name}' already exists (ID: {existing_id})")
                return existing_id
            # Delete old one
            await line_client.delete_rich_menu(existing_id)
            logger.info(f"Deleted existing rich menu: {existing_id}")

    # Create new
    rich_menu_id = await line_client.create_rich_menu(RICH_MENU_FULL)
    if not rich_menu_id:
        logger.error("Failed to create rich menu")
        return None

    logger.info(f"Created rich menu: {rich_menu_id}")

    # Upload image
    image_bytes = _generate_rich_menu_image()
    if image_bytes:
        # Save temp file
        tmp_path = "/tmp/line-richmenu.png"
        with open(tmp_path, "wb") as f:
            f.write(image_bytes)
        status = await line_client.upload_rich_menu_image(rich_menu_id, tmp_path)
        if status == 200:
            logger.info("Rich menu image uploaded successfully")
        else:
            logger.warning(f"Rich menu image upload returned {status}")

    # Set as default
    await line_client.set_default_rich_menu(rich_menu_id)
    logger.info(f"Set rich menu '{rich_menu_id}' as default")

    return rich_menu_id


async def list_and_cleanup():
    """List all rich menus and allow cleanup."""
    menus = await line_client.get_rich_menus()
    logger.info(f"Current rich menus: {len(menus)}")
    for m in menus:
        logger.info(f"  - {m.get('name')} (ID: {m.get('richMenuId')})")
    return menus
