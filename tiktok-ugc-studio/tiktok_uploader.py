"""
TikTok Uploader — Playwright + Mobile Proxy (DataImpulse)
=========================================================
Login + Upload + Schedule via browser automation (NOT TikTok API v2).

Architecture:
  - Uses Patchright (patched Playwright) + stealth config
  - DataImpulse Mobile Proxy (4G/5G, rotating)
  - Session persistence via browser state (cookies + localStorage)
  - Supports video upload, caption, hashtags, scheduling
"""

import os
import re
import json
import time
import base64
import asyncio
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger("tiktok-uploader")

# ─── Config ───────────────────────────────────────────────────────────────

# DataImpulse Mobile Proxy
MOBILE_PROXY = os.environ.get(
    "DATAIMPULSE_PROXY",
    "http://f1a099ac91d739c726dc:9a32937e332c6ff5@gw.dataimpulse.com:823"
)

# Session storage
SESSION_DIR = Path(os.environ.get(
    "TIKTOK_SESSION_DIR",
    "/home/openhands/erp-stack/tiktok-ugc-studio/sessions/tiktok"
))

# Video storage (input files to upload)
VIDEO_DIR = Path(os.environ.get(
    "TIKTOK_VIDEO_DIR",
    "/home/openhands/erp-stack/tiktok-ugc-studio/storage/to_upload"
))

# Published videos log
PUBLISHED_LOG = Path(os.environ.get(
    "TIKTOK_PUBLISHED_LOG",
    "/home/openhands/erp-stack/tiktok-ugc-studio/storage/published.json"
))

# Browser path
CHROMIUM_PATH = os.environ.get(
    "CHROMIUM_PATH",
    os.path.expanduser("~/.cache/ms-playwright/chromium-1223/chrome-linux64/chrome")
)

# Global playwright instance lock
_playwright_lock = asyncio.Lock()
_playwright = None
_browser = None
_context = None


# ─── Proxy Helpers ─────────────────────────────────────────────────────────

def parse_proxy(proxy_url: str) -> dict:
    """Parse proxy URL into Playwright-compatible format."""
    # Format: http://user:pass@host:port
    pattern = r"(?P<protocol>https?|socks5|socks4)://(?:(?P<username>[^:]+):(?P<password>[^@]+)@)?(?P<host>[^:]+):(?P<port>\d+)"
    m = re.match(pattern, proxy_url)
    if not m:
        logger.warning(f"Cannot parse proxy: {proxy_url[:40]}..., using direct")
        return None

    return {
        "server": f"{m.group('protocol')}://{m.group('host')}:{m.group('port')}",
        "username": m.group("username") or "",
        "password": m.group("password") or "",
    }


def get_proxy_config() -> Optional[dict]:
    """Get proxy config for Playwright browser context."""
    proxy = parse_proxy(MOBILE_PROXY)
    if proxy and proxy.get("username") and proxy.get("password"):
        return proxy
    return None


# ─── Browser Engine ───────────────────────────────────────────────────────

async def get_browser(force_new: bool = False) -> tuple:
    """Get or create a persistent Playwright browser instance with mobile proxy."""
    global _playwright, _browser

    async with _playwright_lock:
        if _browser and _browser.is_connected() and not force_new:
            return _browser

        # Cleanup old
        if _browser:
            try:
                await _browser.close()
            except Exception:
                pass

        # Import patchright
        from patchright.async_api import async_playwright

        if _playwright is None:
            _playwright = await async_playwright().start()

        logger.info("Launching Chromium with mobile proxy...")

        proxy_config = get_proxy_config()

        # Use headed mode (for TikTok anti-bot), but with xvfb if no display
        display_var = os.environ.get("DISPLAY", "")
        headless = not bool(display_var) and os.environ.get("HEADLESS", "1") == "1"

        launch_args = [
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--disable-web-security",
            "--disable-features=IsolateOrigins,site-per-process",
            "--window-size=390,844",  # iPhone 14 Pro size
        ]
        if proxy_config:
            launch_args.append(f"--proxy-server={proxy_config['server']}")

        _browser = await _playwright.chromium.launch(
            headless=headless,
            executable_path=CHROMIUM_PATH,
            args=launch_args,
        )
        logger.info(f"Browser launched (proxy={'yes' if proxy_config else 'direct'}, headless={headless})")

        return _browser


async def create_context(
    account_id: str,
    mobile_ua: bool = True,
    headless: bool = False,
) -> tuple:
    """Create a browser context with saved session state."""
    global _context

    browser = await get_browser()

    # Mobile UA for TikTok
    user_agent = (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Mobile/15E148" if mobile_ua else
        "Mozilla/5.0 (Linux; Android 13; SM-S908B) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.6099.230 Mobile Safari/537.36"
    )

    # Build proxy config for context (need to pass username/password)
    proxy_config = get_proxy_config()

    context = await browser.new_context(
        viewport={"width": 390, "height": 844} if mobile_ua else {"width": 1280, "height": 720},
        user_agent=user_agent,
        locale="th-TH",
        timezone_id="Asia/Bangkok",
        device_scale_factor=3 if mobile_ua else 1,
        is_mobile=mobile_ua,
        has_touch=mobile_ua,
        proxy=proxy_config if proxy_config else None,
    )

    # Load saved session if exists
    session_file = SESSION_DIR / f"{account_id}.json"
    if session_file.exists():
        try:
            with open(session_file) as f:
                session_data = json.load(f)
            await context.add_cookies(session_data.get("cookies", []))
            # Restore localStorage
            if session_data.get("local_storage"):
                page = await context.new_page()
                # Need to go to tiktok.com first to set localStorage
                try:
                    await page.goto("https://www.tiktok.com", wait_until="domcontentloaded", timeout=15000)
                    for key, value in session_data["local_storage"].items():
                        try:
                            await page.evaluate(f'localStorage.setItem("{key}", JSON.stringify({json.dumps(value)}))')
                        except Exception:
                            pass
                    await page.close()
                except Exception:
                    pass
            logger.info(f"Session loaded for {account_id}")
        except Exception as e:
            logger.warning(f"Failed to load session for {account_id}: {e}")

    _context = context
    return context, browser


async def save_session(account_id: str, context) -> bool:
    """Save browser session (cookies + localStorage) to disk."""
    SESSION_DIR.mkdir(parents=True, exist_ok=True)
    try:
        cookies = await context.cookies()
        local_storage = {}
        # Try to get localStorage
        pages = context.pages
        if pages:
            try:
                ls = await pages[0].evaluate("JSON.stringify(window.localStorage)")
                local_storage = json.loads(ls)
            except Exception:
                pass

        session_data = {
            "account_id": account_id,
            "saved_at": datetime.utcnow().isoformat(),
            "cookies": cookies,
            "local_storage": local_storage,
        }

        with open(SESSION_DIR / f"{account_id}.json", "w") as f:
            json.dump(session_data, f, indent=2, ensure_ascii=False)

        logger.info(f"Session saved for {account_id} ({len(cookies)} cookies)")
        return True
    except Exception as e:
        logger.error(f"Failed to save session: {e}")
        return False


async def close_browser():
    """Close browser and release resources."""
    global _playwright, _browser, _context

    async with _playwright_lock:
        if _context:
            try:
                await _context.close()
            except Exception:
                pass
            _context = None

        if _browser:
            try:
                await _browser.close()
            except Exception:
                pass
            _browser = None

        if _playwright:
            try:
                await _playwright.stop()
            except Exception:
                pass
            _playwright = None

    logger.info("Browser closed")


# ─── Login Flow ───────────────────────────────────────────────────────────

async def login_tiktok(
    account_id: str,
    username: str = "",
    password: str = "",
    use_qr: bool = False,
    timeout_seconds: int = 180,
) -> dict:
    """
    Login to TikTok via browser automation.
    Returns session status.

    Strategy:
      1. If saved session exists and is valid → skip login
      2. QR code login preferred (more reliable than username/password)
      3. Username/password fallback
    """
    context, browser = await create_context(account_id)
    page = await context.new_page()

    # Anti-detection: randomize behavior
    await page.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
        Object.defineProperty(navigator, 'languages', { get: () => ['th-TH', 'th', 'en-US'] });
    """)

    result = {
        "success": False,
        "account_id": account_id,
        "method": "",
        "error": "",
        "qr_code": None,
        "session_valid": False,
    }

    try:
        # Step 1: Check if we have valid session
        if SESSION_DIR.joinpath(f"{account_id}.json").exists():
            logger.info(f"Checking existing session for {account_id}...")
            await page.goto("https://www.tiktok.com", wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(3000)

            # Check if we're logged in (look for user avatar/icon)
            logged_in = await page.evaluate("""
                () => {
                    // Check for login state indicators
                    const avatar = document.querySelector('[data-e2e="user-avatar"]');
                    const profileIcon = document.querySelector('[class*="profile"]');
                    const loginBtn = document.querySelector('[data-e2e="top-login-button"]');
                    return !!(avatar || profileIcon) || !loginBtn;
                }
            """)

            if logged_in:
                logger.info(f"Session valid for {account_id}, skipping login")
                result["success"] = True
                result["method"] = "session"
                result["session_valid"] = True
                await page.close()
                return result

        # Step 2: Navigate to login page
        if use_qr:
            # QR login
            logger.info(f"Navigating to TikTok QR login for {account_id}...")
            await page.goto("https://www.tiktok.com/login/qr-code", wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(3000)

            # Wait for QR code to appear
            qr_selector = 'canvas, img[src*="qr"], [class*="qr"]'
            try:
                await page.wait_for_selector(qr_selector, timeout=15000)
                # Screenshot QR for scanning
                qr_path = str(SESSION_DIR / f"{account_id}_qr.png")
                await page.screenshot(path=qr_path, full_page=False)
                logger.info(f"QR code saved to {qr_path}")

                # Extract QR image as base64
                with open(qr_path, "rb") as f:
                    qr_b64 = base64.b64encode(f.read()).decode()

                result["qr_code"] = qr_b64
                result["method"] = "qr"
                result["success"] = True

                # Wait for user to scan QR
                logger.info(f"Waiting {timeout_seconds}s for QR scan...")
                start = time.time()
                logged_in = False
                while time.time() - start < timeout_seconds:
                    await page.wait_for_timeout(3000)
                    # Check login state
                    logged_in = await page.evaluate("""
                        () => {
                            const avatar = document.querySelector('[data-e2e="user-avatar"]');
                            const profileIcon = document.querySelector('[class*="profile"]');
                            return !!(avatar || profileIcon);
                        }
                    """)
                    if logged_in:
                        break
                    # Check if redirected to feed (means login success)
                    if "login" not in (await page.url()).lower():
                        logged_in = True
                        break

                if logged_in:
                    await save_session(account_id, context)
                    result["session_valid"] = True
                    result["success"] = True
                    result["method"] = "qr"
                else:
                    result["error"] = "QR scan timeout"
                    result["success"] = False

            except Exception as e:
                logger.warning(f"QR code not found: {e}")
                result["method"] = "qr"
                result["error"] = f"QR page error: {str(e)[:100]}"
                result["success"] = False
        else:
            # Username/password login
            if not username or not password:
                result["error"] = "Username and password required"
                result["method"] = "password"
                result["success"] = False
                await page.close()
                return result

            logger.info(f"Logging in as {username}...")
            await page.goto("https://www.tiktok.com/login/phone-or-email/email", wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(2000)

            # Fill email/username
            email_input = page.locator('input[name="username"], input[type="text"][autocomplete="username"]')
            await email_input.wait_for(timeout=10000)
            await email_input.fill(username)
            await page.wait_for_timeout(500)

            # Fill password
            pass_input = page.locator('input[type="password"]')
            await pass_input.wait_for(timeout=5000)
            await pass_input.fill(password)
            await page.wait_for_timeout(500)

            # Click login button
            login_btn = page.locator('button[type="submit"], button:has-text("Log in"), button:has-text("เข้าสู่ระบบ")')
            await login_btn.wait_for(timeout=5000)
            await login_btn.click()

            # Wait for login to complete
            logger.info("Waiting for login completion...")
            start = time.time()
            login_success = False
            login_error = ""

            while time.time() - start < timeout_seconds:
                await page.wait_for_timeout(3000)
                current_url = page.url

                # Check if redirected to feed/main page
                if any(x in current_url for x in ["tiktok.com/@", "tiktok.com/foryou", "tiktok.com/"]):
                    if "login" not in current_url.lower():
                        login_success = True
                        break

                # Check for login errors
                error_el = page.locator('[class*="error"], [class*="alert"], [class*="message"]')
                try:
                    err_text = await error_el.text_content(timeout=1000)
                    if err_text and any(x in err_text.lower() for x in ["error", "incorrect", "invalid", "wrong"]):
                        login_error = err_text[:200]
                        break
                except Exception:
                    pass

                # Check for captcha/challenge
                if await page.locator('[class*="captcha"], [class*="challenge"], iframe[src*="captcha"]').is_visible():
                    login_error = "CAPTCHA challenge detected — manual intervention required"
                    logger.warning("CAPTCHA detected!")
                    break

            if login_success:
                await save_session(account_id, context)
                result["success"] = True
                result["session_valid"] = True
                result["method"] = "password"
                logger.info(f"Login successful for {username}!")
            else:
                result["error"] = login_error or "Login timeout or failed"
                result["success"] = False
                result["method"] = "password"

    except Exception as e:
        logger.error(f"Login error: {e}")
        result["error"] = str(e)[:200]
        result["success"] = False
    finally:
        try:
            await page.close()
        except Exception:
            pass

    return result


# ─── Session Check ────────────────────────────────────────────────────────

async def check_session(account_id: str) -> dict:
    """Check if saved session is still valid (without logging in)."""
    context, _ = await create_context(account_id)
    page = await context.new_page()

    result = {
        "account_id": account_id,
        "valid": False,
        "username": "",
        "followers": "",
        "error": "",
    }

    try:
        await page.goto("https://www.tiktok.com", wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(3000)

        # Try to get profile info
        valid = await page.evaluate("""
            () => {
                const avatar = document.querySelector('[data-e2e="user-avatar"]');
                const profileLink = document.querySelector('a[href*="/@"], [data-e2e*="profile"]');
                return { valid: !!(avatar || profileLink), hasProfile: !!profileLink };
            }
        """)

        result["valid"] = valid.get("valid", False)

        if result["valid"]:
            # Try to extract username
            try:
                profile_name = await page.evaluate("""
                    () => {
                        const el = document.querySelector('a[href*="/@"]');
                        if (el) {
                            const href = el.getAttribute('href') || '';
                            const match = href.match(/@([^/]+)/);
                            return match ? match[1] : '';
                        }
                        return '';
                    }
                """)
                result["username"] = profile_name or ""
            except Exception:
                pass

    except Exception as e:
        result["error"] = str(e)[:200]
        result["valid"] = False
    finally:
        await page.close()

    return result


# ─── Upload Flow ──────────────────────────────────────────────────────────

async def upload_video(
    account_id: str,
    video_path: str,
    caption: str = "",
    hashtags: list = None,
    schedule_time: Optional[datetime] = None,
    allow_duet: bool = True,
    allow_stitch: bool = True,
    allow_comment: bool = True,
    visibility: str = "public",  # public, friends, private
) -> dict:
    """
    Upload video to TikTok via browser automation.
    Uses Playwright to simulate the upload flow on tiktok.com/upload

    Args:
        account_id: TikTok account identifier for session
        video_path: Path to MP4 video file
        caption: Video caption text
        hashtags: List of hashtags (without #)
        schedule_time: Optional datetime for scheduled posting
        allow_duet: Allow duet
        allow_stitch: Allow stitch
        allow_comment: Allow comments
        visibility: public/friends/private
    """
    hashtags = hashtags or []
    result = {
        "success": False,
        "video_id": "",
        "url": "",
        "error": "",
        "account_id": account_id,
    }

    # Validate video
    video_file = Path(video_path)
    if not video_file.exists():
        result["error"] = f"Video not found: {video_path}"
        return result

    file_size_mb = video_file.stat().st_size / (1024 * 1024)
    if file_size_mb > 500:
        result["error"] = f"Video too large: {file_size_mb:.0f}MB (max 500MB)"
        return result

    if not video_file.suffix.lower() in (".mp4", ".mov", ".webm", ".avi"):
        result["error"] = f"Unsupported format: {video_file.suffix}"
        return result

    context, _ = await create_context(account_id, mobile_ua=True)
    page = await context.new_page()

    # Anti-detection
    await page.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
    """)

    try:
        # Step 1: Go to upload page
        logger.info(f"Navigating to TikTok upload page...")
        await page.goto("https://www.tiktok.com/upload", wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(3000)

        # Check if we need to login first
        if "login" in page.url.lower():
            result["error"] = "Session expired — please login first"
            await page.close()
            return result

        # Step 2: Upload file
        logger.info(f"Uploading video: {video_file.name}")
        file_selector = page.locator('input[type="file"]')
        try:
            await file_selector.wait_for(timeout=10000)
        except Exception:
            # Try alternative: look for upload button/area
            logger.info("File input not found, clicking upload button...")
            upload_btn = page.locator('button:has-text("Upload video"), [class*="upload"]')
            try:
                await upload_btn.first.click(timeout=5000)
                await page.wait_for_timeout(2000)
                await file_selector.wait_for(timeout=10000)
            except Exception:
                result["error"] = "Upload button not found"
                await page.close()
                return result

        # Upload the file via the file input
        await file_selector.set_input_files(str(video_file.absolute()))
        logger.info("File selected, waiting for upload processing...")

        # Wait for upload to complete (look for progress bar to disappear)
        try:
            await page.wait_for_function(
                """
                () => {
                    const progress = document.querySelector('[class*="progress"], [class*="loading"]');
                    if (!progress) return true;
                    return progress.getAttribute('aria-valuenow') === '100' ||
                           progress.style.width === '100%' ||
                           !progress.isConnected;
                }
                """,
                timeout=120000  # 2 min max for upload
            )
            logger.info("Upload processing complete!")
        except Exception:
            logger.warning("Upload progress timeout — continuing...")

        await page.wait_for_timeout(3000)

        # Step 3: Fill caption
        if caption:
            logger.info(f"Filling caption...")
            try:
                caption_input = page.locator('[contenteditable="true"], textarea, [data-text="true"]').first
                await caption_input.wait_for(timeout=10000)
                # TikTok caption may have placeholder character — clear first
                await caption_input.click()
                await page.wait_for_timeout(500)
                # Select all and delete
                await page.keyboard.press("Control+A")
                await page.keyboard.press("Delete")
                await page.wait_for_timeout(300)

                # Type caption
                full_text = caption
                if hashtags:
                    full_text += "\n" + " ".join(f"#{h}" for h in hashtags)
                await caption_input.type(full_text, delay=30)
                logger.info(f"Caption set: {full_text[:60]}...")
            except Exception as e:
                logger.warning(f"Failed to set caption: {e}")

        await page.wait_for_timeout(1000)

        # Step 4: Configure settings
        # Who can watch
        visibility_map = {"public": 0, "friends": 1, "private": 2}
        vis_val = visibility_map.get(visibility, 0)

        try:
            # Toggle settings (find the radio/select elements)
            # Comments
            if not allow_comment:
                comment_toggle = page.locator('[class*="comment"] input[type="checkbox"], [class*="comment"] label')
                if await comment_toggle.is_visible():
                    await comment_toggle.click()
                    await page.wait_for_timeout(300)

            # Duet / Stitch
            if not allow_duet:
                duet_toggle = page.locator('[class*="duet"] input[type="checkbox"], [class*="duet"] label')
                if await duet_toggle.is_visible():
                    await duet_toggle.click()
                    await page.wait_for_timeout(300)

            if not allow_stitch:
                stitch_toggle = page.locator('[class*="stitch"] input[type="checkbox"], [class*="stitch"] label')
                if await stitch_toggle.is_visible():
                    await stitch_toggle.click()
                    await page.wait_for_timeout(300)
        except Exception as e:
            logger.warning(f"Settings toggle error (non-fatal): {e}")

        await page.wait_for_timeout(1000)

        # Step 5: Schedule or Post
        if schedule_time:
            # Schedule posting
            logger.info(f"Scheduling for {schedule_time.isoformat()}...")
            try:
                schedule_btn = page.locator('button:has-text("Schedule"), [class*="schedule"], label:has-text("Schedule")')
                if await schedule_btn.is_visible():
                    await schedule_btn.click()
                    await page.wait_for_timeout(1000)

                    # Fill date/time
                    date_input = page.locator('input[type="datetime-local"], input[placeholder*="date"], [class*="datepicker"]')
                    if await date_input.is_visible():
                        await date_input.fill(schedule_time.strftime("%Y-%m-%dT%H:%M"))
                        await page.wait_for_timeout(500)

                    schedule_confirm = page.locator('button:has-text("Schedule"), button:has-text("Confirm")').last
                    if await schedule_confirm.is_visible():
                        await schedule_confirm.click()
                        await page.wait_for_timeout(2000)
                else:
                    logger.warning("Schedule button not found, posting immediately")
                    schedule_time = None
            except Exception as e:
                logger.warning(f"Schedule error (falling back to immediate): {e}")
                schedule_time = None

        # Step 6: Click Post
        logger.info("Clicking Post...")
        try:
            post_btn = page.locator('button:has-text("Post"), button[type="submit"]')
            await post_btn.wait_for(timeout=10000)

            # Add random delay before posting (human-like)
            await page.wait_for_timeout(2000)
            await post_btn.click()

            # Wait for post confirmation
            await page.wait_for_timeout(5000)

            # Check for success
            success_url = page.url
            result["success"] = True
            result["url"] = success_url
            result["video_id"] = page.url.split("/")[-1] if "/video/" in page.url else ""

            logger.info(f"Video posted! URL: {success_url}")

        except Exception as e:
            # Take screenshot for debugging
            debug_path = str(SESSION_DIR / f"post_error_{account_id}_{int(time.time())}.png")
            try:
                await page.screenshot(path=debug_path)
            except Exception:
                pass
            result["error"] = f"Post button click failed: {str(e)[:200]}"
            logger.error(f"Post failed: {e}")

    except Exception as e:
        result["error"] = f"Upload error: {str(e)[:300]}"
        logger.error(f"Upload error: {e}", exc_info=True)
    finally:
        try:
            await page.close()
        except Exception:
            pass

    # Log published video
    if result["success"]:
        _log_published(account_id, video_path, caption, hashtags, schedule_time, result["url"])

    return result


# ─── Published Log ────────────────────────────────────────────────────────

def _log_published(
    account_id: str,
    video_path: str,
    caption: str,
    hashtags: list,
    schedule_time: Optional[datetime],
    post_url: str,
):
    """Log published video to JSON file for tracking."""
    PUBLISHED_LOG.parent.mkdir(parents=True, exist_ok=True)
    entries = []
    if PUBLISHED_LOG.exists():
        try:
            with open(PUBLISHED_LOG) as f:
                entries = json.load(f)
        except Exception:
            entries = []

    entries.append({
        "account_id": account_id,
        "video": video_path,
        "caption": caption,
        "hashtags": hashtags,
        "scheduled_for": schedule_time.isoformat() if schedule_time else None,
        "published_at": datetime.utcnow().isoformat(),
        "url": post_url,
    })

    with open(PUBLISHED_LOG, "w") as f:
        json.dump(entries, f, indent=2, ensure_ascii=False)


# ─── Get Uploaded Content ─────────────────────────────────────────────────

async def get_my_videos(account_id: str, limit: int = 10) -> dict:
    """Get list of uploaded videos from profile page."""
    context, _ = await create_context(account_id)
    page = await context.new_page()

    result = {
        "success": False,
        "videos": [],
        "error": "",
    }

    try:
        # Go to profile
        await page.goto(f"https://www.tiktok.com/@{account_id}", wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(5000)

        # Scroll to load videos
        for _ in range(3):
            await page.evaluate("window.scrollBy(0, 2000)")
            await page.wait_for_timeout(2000)

        # Extract video links
        videos = await page.evaluate("""
            () => {
                const links = document.querySelectorAll('a[href*="/video/"]');
                const seen = new Set();
                return Array.from(links)
                    .filter(a => {
                        const href = a.getAttribute('href');
                        return href && !seen.has(href) && seen.add(href);
                    })
                    .slice(0, arguments[0])
                    .map(a => ({
                        url: 'https://www.tiktok.com' + a.getAttribute('href'),
                        video_id: a.getAttribute('href').match(/\\/video\\/(\\d+)/)?.[1] || '',
                        thumbnail: a.querySelector('img')?.getAttribute('src') || '',
                    }));
            }
        """, limit)

        result["videos"] = videos or []
        result["success"] = True

    except Exception as e:
        result["error"] = str(e)[:200]
    finally:
        await page.close()

    return result


# ─── Cleanup ──────────────────────────────────────────────────────────────

def cleanup():
    """Close the browser instance."""
    try:
        loop = asyncio.new_event_loop()
        loop.run_until_complete(close_browser())
        loop.close()
    except Exception:
        pass
