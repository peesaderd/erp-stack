"""
LINE Messaging API Client Wrapper
=================================
Provides a unified interface for LINE Messaging API operations:
  - Send messages (text, flex, image, sticker)
  - Reply to webhook events
  - Push messages to users
  - Manage rich menus
  - Get user profiles
"""

import os
import json
import logging
from typing import Optional
from dataclasses import dataclass, field

import httpx

logger = logging.getLogger("line-bot.client")

# ── Credentials ──────────────────────────────────────────────────────────

CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
CHANNEL_SECRET = os.environ.get("LINE_BOT_CHANNEL_SECRET", "")

# ── API Endpoints ────────────────────────────────────────────────────────

API_BASE = "https://api.line.me/v2/bot"
DATA_BASE = "https://api-data.line.me/v2/bot"

HEADERS = {
    "Authorization": f"Bearer {CHANNEL_ACCESS_TOKEN}",
    "Content-Type": "application/json",
}


# ── Models ───────────────────────────────────────────────────────────────

@dataclass
class LineProfile:
    user_id: str
    display_name: str
    picture_url: str = ""
    status_message: str = ""


# ── Client ───────────────────────────────────────────────────────────────

class LineClient:
    """Thin async wrapper around LINE Messaging API."""

    def __init__(self):
        self._client = httpx.AsyncClient(timeout=15.0)

    async def close(self):
        await self._client.aclose()

    # ── Verification ────────────────────────────────────────────────────

    async def verify(self) -> dict:
        """Check if access token is valid."""
        resp = await self._client.post(
            "https://api.line.me/v2/oauth/verify",
            data={"access_token": CHANNEL_ACCESS_TOKEN},
        )
        if resp.status_code == 200:
            return resp.json()
        return {"error": resp.text, "status": resp.status_code}

    # ── Reply ────────────────────────────────────────────────────────────

    async def reply(self, reply_token: str, messages: list[dict]):
        """Reply to a webhook event."""
        payload = {"replyToken": reply_token, "messages": messages}
        resp = await self._client.post(
            f"{API_BASE}/message/reply",
            headers=HEADERS,
            json=payload,
        )
        if resp.status_code != 200:
            logger.error(f"Reply failed ({resp.status_code}): {resp.text}")
        return resp.status_code, resp.json() if resp.text else {}

    # ── Push ─────────────────────────────────────────────────────────────

    async def push(self, user_id: str, messages: list[dict]):
        """Push message to a user (no reply token needed)."""
        payload = {"to": user_id, "messages": messages}
        resp = await self._client.post(
            f"{API_BASE}/message/push",
            headers=HEADERS,
            json=payload,
        )
        if resp.status_code != 200:
            logger.error(f"Push failed ({resp.status_code}): {resp.text}")
        return resp.status_code, resp.json() if resp.text else {}

    # ── Multicast ────────────────────────────────────────────────────────

    async def multicast(self, user_ids: list[str], messages: list[dict]):
        """Send to multiple users (max 500)."""
        payload = {"to": user_ids, "messages": messages}
        resp = await self._client.post(
            f"{API_BASE}/message/multicast",
            headers=HEADERS,
            json=payload,
        )
        if resp.status_code != 200:
            logger.error(f"Multicast failed ({resp.status_code}): {resp.text}")

    # ── Profile ──────────────────────────────────────────────────────────

    async def get_profile(self, user_id: str) -> Optional[LineProfile]:
        """Get user profile from LINE."""
        resp = await self._client.get(
            f"{API_BASE}/profile/{user_id}",
            headers=HEADERS,
        )
        if resp.status_code == 200:
            data = resp.json()
            return LineProfile(
                user_id=data.get("userId", user_id),
                display_name=data.get("displayName", ""),
                picture_url=data.get("pictureUrl", ""),
                status_message=data.get("statusMessage", ""),
            )
        logger.error(f"Get profile failed ({resp.status_code}): {resp.text}")
        return None

    # ── Rich Menu ────────────────────────────────────────────────────────

    async def create_rich_menu(self, body: dict) -> Optional[str]:
        """Create a rich menu. Returns richMenuId."""
        resp = await self._client.post(
            f"{API_BASE}/richmenu",
            headers=HEADERS,
            json=body,
        )
        if resp.status_code == 200:
            return resp.json().get("richMenuId")
        logger.error(f"Create rich menu failed ({resp.status_code}): {resp.text}")
        return None

    async def upload_rich_menu_image(self, rich_menu_id: str, image_path: str):
        """Upload a rich menu image (2500x1686 or 2500x843 PNG)."""
        headers = {
            "Authorization": f"Bearer {CHANNEL_ACCESS_TOKEN}",
            "Content-Type": "image/png",
        }
        with open(image_path, "rb") as f:
            resp = await self._client.post(
                f"{API_BASE}/richmenu/{rich_menu_id}/content",
                headers=headers,
                content=f.read(),
            )
        if resp.status_code != 200:
            logger.error(f"Upload rich menu image failed ({resp.status_code}): {resp.text}")
        return resp.status_code

    async def set_default_rich_menu(self, rich_menu_id: str):
        """Set rich menu as default for all users."""
        resp = await self._client.post(
            f"{API_BASE}/richmenu/{rich_menu_id}/default",
            headers=HEADERS,
        )
        if resp.status_code != 200:
            logger.error(f"Set default rich menu failed ({resp.status_code}): {resp.text}")
        return resp.status_code

    async def get_rich_menus(self) -> list[dict]:
        """List all rich menus."""
        resp = await self._client.get(
            f"{API_BASE}/richmenu/list",
            headers=HEADERS,
        )
        if resp.status_code == 200:
            return resp.json().get("richmenus", [])
        return []

    async def delete_rich_menu(self, rich_menu_id: str):
        """Delete a rich menu."""
        resp = await self._client.delete(
            f"{API_BASE}/richmenu/{rich_menu_id}",
            headers=HEADERS,
        )
        if resp.status_code != 200:
            logger.error(f"Delete rich menu failed ({resp.status_code}): {resp.text}")

    async def link_rich_menu_to_user(self, user_id: str, rich_menu_id: str):
        """Link a rich menu to a specific user."""
        resp = await self._client.post(
            f"{API_BASE}/user/{user_id}/richmenu/{rich_menu_id}",
            headers=HEADERS,
        )
        if resp.status_code != 200:
            logger.error(f"Link rich menu failed ({resp.status_code}): {resp.text}")

    async def unlink_rich_menu(self, user_id: str):
        """Unlink rich menu from a user."""
        resp = await self._client.delete(
            f"{API_BASE}/user/{user_id}/richmenu",
            headers=HEADERS,
        )
        if resp.status_code != 200:
            logger.error(f"Unlink rich menu failed ({resp.status_code}): {resp.text}")

    # ── Message Helpers ──────────────────────────────────────────────────

    @staticmethod
    def text(text: str) -> dict:
        return {"type": "text", "text": text}

    @staticmethod
    def flex(alt_text: str, contents: dict) -> dict:
        return {
            "type": "flex",
            "altText": alt_text,
            "contents": contents,
        }

    @staticmethod
    def image(original_url: str, preview_url: str = "") -> dict:
        return {
            "type": "image",
            "originalContentUrl": original_url,
            "previewImageUrl": preview_url or original_url,
        }

    @staticmethod
    def sticker(package_id: str, sticker_id: str) -> dict:
        return {
            "type": "sticker",
            "packageId": package_id,
            "stickerId": sticker_id,
        }

    @staticmethod
    def location(title: str, address: str, lat: float, lon: float) -> dict:
        return {
            "type": "location",
            "title": title,
            "address": address,
            "latitude": lat,
            "longitude": lon,
        }

    @staticmethod
    def quick_reply(text: str, items: list[dict]) -> dict:
        """Text message with quick reply buttons."""
        return {
            "type": "text",
            "text": text,
            "quickReply": {"items": items},
        }

    @staticmethod
    def quick_reply_item(label: str, data: str, text: str = "") -> dict:
        """A single quick reply button."""
        return {
            "type": "action",
            "action": {
                "type": "postback",
                "label": label,
                "data": data,
                "displayText": text or label,
            },
        }

    # ── Flex Template Builders ───────────────────────────────────────────

    @staticmethod
    def flex_bubble(body_boxes: list[dict], header: Optional[list[dict]] = None,
                    footer: Optional[list[dict]] = None) -> dict:
        """Build a flex bubble container."""
        bubble = {"type": "bubble"}
        if header:
            bubble["header"] = {"type": "box", "layout": "vertical", "contents": header}
        bubble["body"] = {"type": "box", "layout": "vertical", "contents": body_boxes}
        if footer:
            bubble["footer"] = {"type": "box", "layout": "vertical", "contents": footer}
        return bubble

    @staticmethod
    def flex_text(text: str, **kwargs) -> dict:
        """Flex text component."""
        box = {"type": "text", "text": text}
        box.update(kwargs)
        return box

    @staticmethod
    def flex_button(label: str, action_type: str, **action_kwargs) -> dict:
        """Flex button component."""
        return {
            "type": "button",
            "action": {"type": action_type, "label": label, **action_kwargs},
            "style": "primary",
        }

    @staticmethod
    def flex_separator() -> dict:
        return {"type": "separator"}

    @staticmethod
    def flex_spacer(size: str = "md") -> dict:
        return {"type": "spacer", "size": size}

    @staticmethod
    def flex_carousel(bubbles: list[dict]) -> dict:
        """Flex carousel container."""
        return {
            "type": "carousel",
            "contents": bubbles,
        }


# ── Global instance ──────────────────────────────────────────────────────

line_client = LineClient()
