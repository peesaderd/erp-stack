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
import sys
import inspect
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


# ─── Platform Constants ────────────────────────────────────────────────────

PLATFORMS = [
    "tiktok",
    "tiktok_business",
    "facebook",
    "instagram",
    "x",
    "linkedin",
    "youtube",
    "pinterest",
    "bluesky",
    "threads",
]

PLATFORM_NAMES = {
    "tiktok": "TikTok",
    "tiktok_business": "TikTok Business",
    "facebook": "Facebook",
    "instagram": "Instagram",
    "x": "X (Twitter)",
    "linkedin": "LinkedIn",
    "youtube": "YouTube",
    "pinterest": "Pinterest",
    "bluesky": "Bluesky",
    "threads": "Threads",
}

PLATFORM_NAMES_TH = {
    "tiktok": "ติ๊กต็อก",
    "tiktok_business": "ติ๊กต็อก ธุรกิจ",
    "facebook": "เฟซบุ๊ก",
    "instagram": "อินสตาแกรม",
    "x": "X (ทวิตเตอร์)",
    "linkedin": "ลิงก์อิน",
    "youtube": "ยูทูบ",
    "pinterest": "พินเทอเรสต์",
    "bluesky": "บลูสกาย",
    "threads": "เธรดส์",
}

PLATFORM_DEFAULTS = {
    "tiktok": {"privacy_status": "public", "is_ai_generated": True},
    "tiktok_business": {"privacy_status": "public", "is_ai_generated": True},
    "facebook": {"placement": "timeline", "privacy_status": "public"},
    "instagram": {"placement": "timeline", "is_ai_generated": True},
    "x": {},
    "linkedin": {"visibility": "public"},
    "youtube": {"privacy_status": "public"},
    "pinterest": {},
    "bluesky": {},
    "threads": {"placement": "timeline"},
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
    platform: str = None,
    platform_configs: dict = None,
) -> dict:
    if platform_configs is None and platform is not None:
        defaults = PLATFORM_DEFAULTS.get(platform, {})
        platform_configs = make_platform_config(platform, **defaults)
    media_objects = [{"url": u} for u in media_urls]
    return post_to_platform(
        social_accounts=account_ids,
        caption=caption,
        media=media_objects,
        scheduled_at=scheduled_at,
        platform_configurations=platform_configs,
    )


# ─── Platform Config Helpers ───────────────────────────────────────────────

def make_tiktok_config(
    privacy_status: str = "public",
    is_ai_generated: bool = True,
    brand_organic_toggle: bool = None,
    branded_content: bool = None,
    brand_partner_name: str = None,
    allow_duet: bool = None,
    allow_stitch: bool = None,
    disable_comment: bool = None,
) -> dict:
    config = {
        "privacy_status": privacy_status,
        "is_ai_generated": is_ai_generated,
    }
    if brand_organic_toggle is not None:
        config["brand_organic_toggle"] = brand_organic_toggle
    if branded_content is not None:
        config["branded_content"] = branded_content
    if brand_partner_name is not None:
        config["brand_partner_name"] = brand_partner_name
    if allow_duet is not None:
        config["allow_duet"] = allow_duet
    if allow_stitch is not None:
        config["allow_stitch"] = allow_stitch
    if disable_comment is not None:
        config["disable_comment"] = disable_comment
    return config


def make_tiktok_business_config(**kwargs) -> dict:
    return make_tiktok_config(**kwargs)


def make_facebook_config(
    placement: str = "timeline",
    privacy_status: str = "public",
    is_ai_generated: bool = None,
    tagged_user_ids: list[str] = None,
) -> dict:
    config = {
        "placement": placement,
        "privacy_status": privacy_status,
    }
    if is_ai_generated is not None:
        config["is_ai_generated"] = is_ai_generated
    if tagged_user_ids:
        config["tagged_user_ids"] = tagged_user_ids
    return config


def make_instagram_config(
    placement: str = "timeline",
    is_ai_generated: bool = True,
    branded_content: bool = None,
    brand_partner_name: str = None,
) -> dict:
    config = {
        "placement": placement,
        "is_ai_generated": is_ai_generated,
    }
    if branded_content is not None:
        config["branded_content"] = branded_content
    if brand_partner_name is not None:
        config["brand_partner_name"] = brand_partner_name
    return config


def make_x_config(
    is_ai_generated: bool = None,
    sensitive_content: bool = None,
    reply_settings: str = None,
) -> dict:
    config = {}
    if is_ai_generated is not None:
        config["is_ai_generated"] = is_ai_generated
    if sensitive_content is not None:
        config["sensitive_content"] = sensitive_content
    if reply_settings is not None:
        config["reply_settings"] = reply_settings
    return config


def make_linkedin_config(
    visibility: str = "public",
    is_ai_generated: bool = None,
    article_url: str = None,
) -> dict:
    config = {"visibility": visibility}
    if is_ai_generated is not None:
        config["is_ai_generated"] = is_ai_generated
    if article_url:
        config["article_url"] = article_url
    return config


def make_youtube_config(
    privacy_status: str = "public",
    is_ai_generated: bool = None,
    category_id: str = None,
    tags: list[str] = None,
    made_for_kids: bool = None,
) -> dict:
    config = {"privacy_status": privacy_status}
    if is_ai_generated is not None:
        config["is_ai_generated"] = is_ai_generated
    if category_id:
        config["category_id"] = category_id
    if tags:
        config["tags"] = tags
    if made_for_kids is not None:
        config["made_for_kids"] = made_for_kids
    return config


def make_pinterest_config(
    board_id: str = None,
    is_ai_generated: bool = None,
    link_url: str = None,
) -> dict:
    config = {}
    if board_id:
        config["board_id"] = board_id
    if is_ai_generated is not None:
        config["is_ai_generated"] = is_ai_generated
    if link_url:
        config["link_url"] = link_url
    return config


def make_bluesky_config(
    is_ai_generated: bool = None,
    reply_to: str = None,
) -> dict:
    config = {}
    if is_ai_generated is not None:
        config["is_ai_generated"] = is_ai_generated
    if reply_to:
        config["reply_to"] = reply_to
    return config


def make_threads_config(
    placement: str = "timeline",
    is_ai_generated: bool = None,
    allow_replies: bool = None,
) -> dict:
    config = {"placement": placement}
    if is_ai_generated is not None:
        config["is_ai_generated"] = is_ai_generated
    if allow_replies is not None:
        config["allow_replies"] = allow_replies
    return config


# ─── Account-Level Config Helper ───────────────────────────────────────────

PLATFORM_CONFIG_MAKERS = {
    "tiktok": make_tiktok_config,
    "tiktok_business": make_tiktok_business_config,
    "facebook": make_facebook_config,
    "instagram": make_instagram_config,
    "x": make_x_config,
    "linkedin": make_linkedin_config,
    "youtube": make_youtube_config,
    "pinterest": make_pinterest_config,
    "bluesky": make_bluesky_config,
    "threads": make_threads_config,
}


def make_platform_config(platform: str, **kwargs) -> dict:
    maker = PLATFORM_CONFIG_MAKERS.get(platform)
    if maker is None:
        raise ValueError(
            f"Unknown platform '{platform}'. "
            f"Valid: {', '.join(PLATFORMS)}"
        )
    return {platform: maker(**kwargs)}


def make_account_configs(accounts: dict[str, dict]) -> dict:
    configs = {}
    for platform, opts in accounts.items():
        configs.update(make_platform_config(platform, **opts))
    return configs


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

    # platform-list
    p_platform_list = sub.add_parser("platform-list", help="List supported platforms")

    # platform-info
    p_platform_info = sub.add_parser("platform-info", help="Show platform details")
    p_platform_info.add_argument("--platform", required=True, help="Platform name")

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

    elif args.cmd == "platform-list":
        print(f"Supported platforms ({len(PLATFORMS)}):")
        for p in PLATFORMS:
            name_en = PLATFORM_NAMES.get(p, p)
            name_th = PLATFORM_NAMES_TH.get(p, "")
            defaults = PLATFORM_DEFAULTS.get(p, {})
            print(f"  {p:24s} {name_en:20s} {name_th}")
            if defaults:
                print(f"  {'':24s} Defaults: {json.dumps(defaults, ensure_ascii=False)}")

    elif args.cmd == "platform-info":
        plat = args.platform
        if plat not in PLATFORMS:
            print(f"Unknown platform '{plat}'. Valid: {', '.join(PLATFORMS)}")
            sys.exit(1)
        print(f"Platform:        {plat}")
        print(f"Name (EN):       {PLATFORM_NAMES.get(plat, plat)}")
        print(f"Name (TH):       {PLATFORM_NAMES_TH.get(plat, '')}")
        print(f"Defaults:        {json.dumps(PLATFORM_DEFAULTS.get(plat, {}), ensure_ascii=False)}")
        maker = PLATFORM_CONFIG_MAKERS.get(plat)
        if maker:
            sig = inspect.signature(maker)
            print(f"\nParameters ({maker.__name__}):")
            for name, param in sig.parameters.items():
                default = param.default
                if default is inspect.Parameter.empty:
                    print(f"  {name} (required)")
                else:
                    default_repr = json.dumps(default) if isinstance(default, (dict, list, bool)) else repr(default)
                    print(f"  {name} (default: {default_repr})")
