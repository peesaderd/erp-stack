"""
Post For Me Integration — Social Media Auto Post API
=====================================================
Base URL: https://api.postforme.dev
Docs: https://api.postforme.dev/docs
Pricing: $10/month (1,000 posts, unlimited accounts)

ติดตั้ง:
    pip install postforme  # official SDK (optional, use requests directly)

Platforms: TikTok, Instagram, Facebook, X, LinkedIn, YouTube, Threads, Pinterest, Bluesky
"""

import os
import json
import logging
import requests
from typing import Optional

logger = logging.getLogger("tiktok-ugc.postforme")

PFM_API_KEY = os.environ.get("PFM_API_KEY", "pfm_live_4qR2sT7hvEo6qFKMQssker")
PFM_BASE_URL = "https://api.postforme.dev/v1"

# Connected account IDs (from dashboard)
# Account IDs เริ่มต้นด้วย 'sa_' ตาม OpenAPI spec
PFM_ACCOUNTS = {
    "tiktok_putterfreshshop": "spc_i0Ly8cwH9vJml9VS6t4j",
    "facebook_kunyay": "spc_sffrL9Nul7Z2ms2rJELZ1",
    "facebook_putter_gaming": "spc_OdQDPsF5ZucdSgSIwQUJc",
}


# ─── Account Management ────────────────────────────────────────────────────

def get_accounts() -> list:
    """List all connected social accounts.
    Endpoint: GET /v1/social-accounts
    """
    resp = requests.get(
        f"{PFM_BASE_URL}/social-accounts",
        headers={"Authorization": f"Bearer {PFM_API_KEY}"}
    )
    resp.raise_for_status()
    data = resp.json()
    if isinstance(data, list):
        return data
    return data.get("data", [])


def get_auth_url(platform: str, permissions: list = None) -> str:
    """Get OAuth URL to connect a social account.

    Args:
        platform: Platform name (e.g. 'tiktok', 'facebook')
        permissions: List of permission scopes

    Returns:
        str: OAuth URL for user to open in browser

    Endpoint: POST /v1/social-accounts/auth-url
    """
    payload = {
        "platform": platform,
    }
    if permissions:
        payload["permissions"] = permissions

    resp = requests.post(
        f"{PFM_BASE_URL}/social-accounts/auth-url",
        headers={"Authorization": f"Bearer {PFM_API_KEY}"},
        json=payload,
    )
    resp.raise_for_status()
    data = resp.json()
    return data.get("url", "")


# ─── Post / Schedule ──────────────────────────────────────────────────────

def post_to_platform(
    social_accounts: list[str],
    caption: str = "",
    media: list[dict] = None,
    platform_configurations: dict = None,
    scheduled_at: str = None,
) -> dict:
    """
    Post content to social accounts.

    Args:
        social_accounts: List of social account IDs (from get_accounts())
        caption: Caption/text content
        media: List of media objects [{ "url": "...", "type": "video" }]
        platform_configurations: Platform-specific configurations
        scheduled_at: ISO 8601 datetime for scheduled post (None = post now)

    Returns:
        dict: Post result with id, status, platform, etc.

    Cost: 1 post = 1 of 1,000 monthly quota ($10/1K = $0.01/post)
    """
    payload = {
        "social_accounts": social_accounts,
        "caption": caption,
        "media": media or [],
    }
    if scheduled_at:
        payload["scheduled_at"] = scheduled_at
    if platform_configurations:
        payload["platform_configurations"] = platform_configurations

    resp = requests.post(
        f"{PFM_BASE_URL}/social-posts",
        headers={"Authorization": f"Bearer {PFM_API_KEY}"},
        json=payload,
    )
    resp.raise_for_status()
    return resp.json()


def post_to_multiple(
    account_ids: list[str],
    caption: str = "",
    media_urls: list[str] = None,
    scheduled_at: str = None,
    platform_configs: dict = None,
) -> dict:
    """Post same content to multiple accounts in a single API call.

    API รองรับการส่ง social_accounts เป็น list ได้ใน payload เดียว
    ไม่ต้อง loop ส่งทีละ account
    """
    media_objects = [{"url": u} for u in (media_urls or [])]
    return post_to_platform(
        social_accounts=account_ids,
        caption=caption,
        media=media_objects,
        scheduled_at=scheduled_at,
        platform_configurations=platform_configs,
    )


def get_post_status(post_id: str) -> dict:
    """Check the status of a post.
    Endpoint: GET /v1/social-posts/{post_id}
    """
    resp = requests.get(
        f"{PFM_BASE_URL}/social-posts/{post_id}",
        headers={"Authorization": f"Bearer {PFM_API_KEY}"}
    )
    resp.raise_for_status()
    return resp.json()


# ─── Full Automation: Pipeline → Post ─────────────────────────────────────

def auto_post_affiliate_clip(
    video_path: str,
    caption: str,
    account_ids: list[str],
    hashtags: str = "",
    scheduled_at: str = None,
    platform_configs: dict = None,
) -> dict:
    """
    Upload generated affiliate clip to social media.

    Args:
        video_path: Local path to final clip
        caption: Post caption
        account_ids: List of social account IDs
        hashtags: Hashtags
        scheduled_at: Optional schedule time (ISO 8601)
        platform_configs: Platform-specific configurations

    Returns:
        Post result with id, status, platforms, etc.
    """
    full_caption = f"{caption}\n\n{hashtags}" if hashtags else caption
    return post_to_multiple(
        account_ids=account_ids,
        caption=full_caption,
        media_urls=[video_path],  # Must be public URL
        scheduled_at=scheduled_at,
        platform_configs=platform_configs,
    )


def schedule_post_from_pipeline(
    caption: str,
    media_urls: list[str],
    account_ids: list[str],
    scheduled_at: str = None,
    platform_configs: dict = None,
) -> dict:
    """
    Schedule a post from the content pipeline with platform-specific configs.

    Args:
        caption: Post caption
        media_urls: List of public media URLs
        account_ids: List of social account IDs
        scheduled_at: ISO 8601 datetime (None = post immediately)
        platform_configs: Platform-specific configurations
                         e.g. { "tiktok": { "privacy_status": "public", "is_ai_generated": true } }

    Returns:
        dict: Post result with id, status, scheduled_at, etc.
    """
    media_objects = [{"url": u} for u in media_urls]
    return post_to_platform(
        social_accounts=account_ids,
        caption=caption,
        media=media_objects,
        scheduled_at=scheduled_at,
        platform_configurations=platform_configs,
    )


# ─── CLI ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Post For Me - Social Auto Post")
    sub = parser.add_subparsers(dest="cmd")

    # accounts
    p_accounts = sub.add_parser("accounts", help="List connected accounts")

    # connect
    p_connect = sub.add_parser("connect", help="Get OAuth URL for platform")
    p_connect.add_argument("--platform", required=True, help="Platform name")

    # post
    p_post = sub.add_parser("post", help="Post content")
    p_post.add_argument("--account", nargs="+", required=True, help="Account ID(s)")
    p_post.add_argument("--text", required=True, help="Caption")
    p_post.add_argument("--media", nargs="+", help="Media URLs")
    p_post.add_argument("--schedule", help="Schedule datetime (ISO 8601)")

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    if args.cmd == "accounts":
        accounts = get_accounts()
        print(f"Found {len(accounts)} connected accounts:")
        for acc in accounts:
            print(f"  [{acc['id']}] {acc.get('platform')} — {acc.get('username', '?')}")

    elif args.cmd == "connect":
        url = get_auth_url(args.platform)
        if url:
            print(f"Open this URL in your browser to connect {args.platform}:")
            print(url)
        else:
            print(f"Failed to get auth URL for '{args.platform}'")

    elif args.cmd == "post":
        result = post_to_platform(
            social_accounts=args.account,
            caption=args.text,
            media=[{"url": u} for u in (args.media or [])],
            scheduled_at=args.schedule,
        )
        print(json.dumps(result, indent=2))
        post_id = result.get("id", "")
        if post_id:
            print(f"\nPost ID: {post_id}")
            print(f"Status: {result.get('status', '?')}")
