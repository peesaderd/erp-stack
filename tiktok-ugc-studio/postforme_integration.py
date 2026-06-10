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
    return data.get("data", [])


def get_connect_urls() -> dict:
    """Get OAuth URLs to connect social accounts.
    Returns dict like: { "tiktok": "https://...", "instagram": "..." }
    Endpoint: GET /v1/connect
    """
    resp = requests.get(
        f"{PFM_BASE_URL}/connect",
        headers={"Authorization": f"Bearer {PFM_API_KEY}"}
    )
    resp.raise_for_status()
    data = resp.json()
    return data.get("data", {})


# ─── Post / Schedule ──────────────────────────────────────────────────────

def post_to_platform(
    account_id: str,
    text: str = "",
    media_urls: list[str] = None,
    platform_options: dict = None,
    schedule_at: str = None,
) -> dict:
    """
    Post content to a social account.

    Args:
        account_id: Social account ID (from get_accounts())
        text: Caption/text content
        media_urls: List of media URLs (video/image)
        platform_options: Platform-specific options
        schedule_at: ISO 8601 datetime for scheduled post (None = post now)

    Returns:
        dict: Post result with id, status, platform, etc.

    Cost: 1 post = 1 of 1,000 monthly quota ($10/1K = $0.01/post)
    """
    payload = {
        "account_id": account_id,
        "text": text,
        "media_urls": media_urls or [],
    }
    if schedule_at:
        payload["schedule_at"] = schedule_at
    if platform_options:
        payload["platform_options"] = platform_options

    resp = requests.post(
        f"{PFM_BASE_URL}/posts",
        headers={"Authorization": f"Bearer {PFM_API_KEY}"},
        json=payload,
    )
    resp.raise_for_status()
    return resp.json().get("data", {})


def post_to_multiple(
    account_ids: list[str],
    text: str = "",
    media_urls: list[str] = None,
    schedule_at: str = None,
) -> list[dict]:
    """Post same content to multiple accounts at once."""
    results = []
    for aid in account_ids:
        result = post_to_platform(aid, text, media_urls, schedule_at=schedule_at)
        results.append(result)
    return results


def get_post_status(post_id: str) -> dict:
    """Check the status of a post.
    Endpoint: GET /v1/posts/:id
    """
    resp = requests.get(
        f"{PFM_BASE_URL}/posts/{post_id}",
        headers={"Authorization": f"Bearer {PFM_API_KEY}"}
    )
    resp.raise_for_status()
    return resp.json().get("data", {})


# ─── Full Automation: Pipeline → Post ─────────────────────────────────────

def auto_post_affiliate_clip(
    video_path: str,
    caption: str,
    account_ids: list[str],
    hashtags: str = "",
    schedule_at: str = None,
) -> list[dict]:
    """
    Upload generated affiliate clip to social media.

    Args:
        video_path: Local path to final clip
        caption: Post caption
        account_ids: List of social account IDs
        hashtags: Hashtags
        schedule_at: Optional schedule time

    Returns:
        List of post results per platform
    """
    full_caption = f"{caption}\n\n{hashtags}" if hashtags else caption
    return post_to_multiple(
        account_ids=account_ids,
        text=full_caption,
        media_urls=[video_path],  # Must be public URL
        schedule_at=schedule_at,
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
    p_post.add_argument("--account", required=True, help="Account ID")
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
        urls = get_connect_urls()
        target = args.platform.lower()
        found = False
        for key, url in urls.items():
            if target in key.lower():
                print(f"{key}: {url}")
                found = True
        if not found:
            print(f"No connect URL for '{target}'. Available:")
            for key in urls.keys():
                print(f"  - {key}")

    elif args.cmd == "post":
        result = post_to_platform(
            account_id=args.account,
            text=args.text,
            media_urls=args.media,
            schedule_at=args.schedule,
        )
        print(json.dumps(result, indent=2))
        post_id = result.get("id", "")
        if post_id:
            print(f"\nPost ID: {post_id}")
            print(f"Status: {result.get('status', '?')}")
