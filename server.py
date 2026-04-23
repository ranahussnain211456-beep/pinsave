"""
Pinterest / KlickPin Web Scraper - Production API Server
=========================================================
Flask + Playwright-based scraper with anti-bot measures,
retry logic, and structured JSON responses.
Supports: pinterest.com, pin.it, klickpin.com
"""

import asyncio
import os
import re
import random
import logging
from urllib.parse import urlparse, unquote

from flask import Flask, request, jsonify
from flask_cors import CORS
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

# ─── Logging Setup ────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("pinsave-scraper")

# ─── App Setup ────────────────────────────────────────────────────────────────
app = Flask(__name__)
CORS(app)  # Allow frontend to call this API

# ─── Constants ────────────────────────────────────────────────────────────────
MAX_RETRIES  = 1
RETRY_DELAY  = 1
NAV_TIMEOUT  = 12_000   # 12 seconds
WAIT_TIMEOUT = 5_000    # 5 seconds

# ✅ Supported domains
ALLOWED_DOMAINS = [
    "pinterest.com",
    "www.pinterest.com",
    "pin.it",
    "pinterest.co.uk",
    "pinterest.ca",
    "pinterest.com.au",
    "klickpin.com",
    "www.klickpin.com",
]

# Realistic browser headers — avoids bot detection
BROWSER_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
}

# Quality preference: highest first
QUALITY_PREFERENCE = ["2160", "1080", "720", "480", "360"]


# ─── Helper Functions ─────────────────────────────────────────────────────────

def validate_url(url: str) -> bool:
    """Check if URL is from an allowed domain."""
    try:
        parsed = urlparse(url)
        host = parsed.netloc.lower().replace("www.", "")
        return any(host in domain or domain in host for domain in ALLOWED_DOMAINS) \
               and parsed.scheme in ("http", "https")
    except Exception:
        return False


def error_response(message: str, code: int = 400):
    """Return a standard error JSON."""
    return jsonify({"success": False, "error": message}), code


def pick_best_quality(sources: list) -> dict | None:
    """Select the highest quality source from a list."""
    if not sources:
        return None
    # Try quality preference in order
    for preferred in QUALITY_PREFERENCE:
        for src in sources:
            q   = str(src.get("quality", "")).lower()
            url = src.get("url", "").lower()
            if preferred in q or preferred in url:
                return src
    # Fallback: return first available
    return sources[0]


async def human_delay(min_ms: int = 500, max_ms: int = 2500):
    """Wait a random human-like amount of time."""
    await asyncio.sleep(random.uniform(min_ms / 1000, max_ms / 1000))


async def simulate_scroll(page):
    """Quick scroll to trigger lazy loading."""
    try:
        await page.evaluate("window.scrollTo(0, 400)")
        await human_delay(100, 200)
        await page.evaluate("window.scrollTo(0, 0)")
    except Exception:
        pass


# ─── Core Scraper ─────────────────────────────────────────────────────────────

async def scrape_video(target_url: str) -> dict:
    """
    Launch a stealth Playwright browser, open the target page,
    extract all video/image media URLs, and return structured data.
    """
    captured_media: list[str] = []   # URLs caught from network requests
    video_sources:  list[dict] = []
    image_sources:  list[str]  = []

    async with async_playwright() as pw:

        # ── Step 1: Launch headless Chrome with stealth settings ───────────
        browser = await pw.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--disable-dev-shm-usage",
                "--disable-extensions",
                "--lang=en-US",
            ],
        )

        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
            locale="en-US",
            timezone_id="America/New_York",
            extra_http_headers=BROWSER_HEADERS,
        )

        # ── Step 2: Patch browser to hide automation fingerprints ──────────
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins',   { get: () => [1,2,3,4,5] });
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US','en'] });
        """)

        page = await context.new_page()

        # ── Step 3: Intercept network — grab any media URL the browser loads ─
        async def on_request(req):
            url  = req.url
            rtype = req.resource_type
            if rtype in ("media", "xhr", "fetch") or re.search(
                r"\.(mp4|m3u8|webm|mov|avi|mkv)(\?|$)", url, re.IGNORECASE
            ):
                captured_media.append(url)

        page.on("request", on_request)

        # ── Step 4: Navigate to the target page ────────────────────────────
        log.info(f"Opening: {target_url}")
        await page.goto(target_url, wait_until="domcontentloaded", timeout=NAV_TIMEOUT)
        await human_delay(200, 400)

        # Wait for page to fully settle
        try:
            await page.wait_for_load_state("networkidle", timeout=WAIT_TIMEOUT)
        except PlaywrightTimeout:
            log.warning("Network idle timeout — continuing anyway")

        # ── Step 5: Simulate human scrolling ──────────────────────────────
        await simulate_scroll(page)

        # ── Step 6: Try clicking play button to trigger video load ─────────
        play_selectors = [
            'button[aria-label*="play" i]',
            '[data-test-id="play-button"]',   # Pinterest specific
            '.play-button',
            '[class*="play"]',
            'video',
        ]
        for sel in play_selectors:
            try:
                el = await page.query_selector(sel)
                if el:
                    await el.click()
                    log.info(f"Clicked: {sel}")
                    await human_delay(300, 600)
                    break
            except Exception:
                pass

        # ── Step 7: Extract video sources from the DOM ─────────────────────
        dom_sources = await page.evaluate("""
            () => {
                const found = [];

                // <video src="..."> and <source src="..."> inside <video>
                document.querySelectorAll('video, video source').forEach(el => {
                    const src = el.src || el.getAttribute('src');
                    const q   = el.getAttribute('label') ||
                                el.getAttribute('data-quality') || '';
                    if (src && src.startsWith('http')) found.push({ url: src, quality: q });
                });

                // data-video-url, data-src attributes
                document.querySelectorAll('[data-video-url],[data-src],[data-video]').forEach(el => {
                    const src = el.dataset.videoUrl || el.dataset.src || el.dataset.video;
                    if (src && /\\.mp4|\\.m3u8|\\.webm/i.test(src)) {
                        found.push({ url: src, quality: '' });
                    }
                });

                // JSON-LD structured data (Pinterest uses this)
                document.querySelectorAll('script[type="application/ld+json"]').forEach(s => {
                    try {
                        const d = JSON.parse(s.textContent);
                        if (d.contentUrl) found.push({ url: d.contentUrl, quality: '1080p' });
                        if (d.embedUrl)   found.push({ url: d.embedUrl,   quality: '' });
                        // Handle @graph array
                        if (Array.isArray(d['@graph'])) {
                            d['@graph'].forEach(item => {
                                if (item.contentUrl) found.push({ url: item.contentUrl, quality: '1080p' });
                            });
                        }
                    } catch(_) {}
                });

                // og:video meta tag
                const ogv = document.querySelector('meta[property="og:video"]');
                if (ogv && ogv.content) found.push({ url: ogv.content, quality: '' });

                // og:video:url meta tag
                const ogvu = document.querySelector('meta[property="og:video:url"]');
                if (ogvu && ogvu.content) found.push({ url: ogvu.content, quality: '' });

                return found;
            }
        """)

        video_sources.extend(dom_sources)

        # ── Step 8: Add network-captured URLs with quality detection ───────
        for murl in captured_media:
            q = ""
            if "1080" in murl: q = "1080p"
            elif "720" in murl: q = "720p"
            elif "480" in murl: q = "480p"
            elif "360" in murl: q = "360p"
            video_sources.append({"url": murl, "quality": q})

        # ── Step 9: Extract images ─────────────────────────────────────────
        image_sources = await page.evaluate("""
            () => {
                const imgs = new Set();
                // og:image (best quality thumbnail)
                const og = document.querySelector('meta[property="og:image"]');
                if (og) imgs.add(og.content);
                // Large visible images
                document.querySelectorAll('img').forEach(img => {
                    const src = img.src || img.dataset.src || '';
                    if (src && src.startsWith('http') && img.naturalWidth > 150) {
                        imgs.add(src);
                    }
                });
                return [...imgs];
            }
        """)

        # ── Step 10: Get page title and description ────────────────────────
        metadata = await page.evaluate("""
            () => ({
                title: document.title || '',
                description: (document.querySelector('meta[name="description"]') || {}).content || '',
            })
        """)

        await browser.close()

    # ── Step 11: Deduplicate video sources ────────────────────────────────
    seen     = set()
    unique   = []
    for s in video_sources:
        u = s.get("url", "")
        if u and u not in seen:
            seen.add(u)
            unique.append(s)

    # ── Step 12: Pick the best quality video ──────────────────────────────
    best = pick_best_quality(unique)

    if not best and not image_sources:
        raise ValueError(
            "No video or image found. Make sure the URL is a public Pinterest video pin."
        )

    # ── Step 13: Build and return the response ────────────────────────────
    result = {
        "success":         True,
        "metadata":        metadata,
        "images":          image_sources[:10],
        "allVideoSources": unique,
    }

    if best:
        filename = os.path.basename(urlparse(best["url"]).path) or "video.mp4"
        if not filename.endswith((".mp4", ".webm", ".mov", ".m3u8")):
            filename = "video.mp4"
        result.update({
            "videoUrl": best["url"],
            "quality":  best.get("quality") or "HD",
            "filename": filename,
        })

    return result


# ─── Retry Wrapper ────────────────────────────────────────────────────────────

async def scrape_with_retries(url: str) -> dict:
    """Try scraping up to MAX_RETRIES times with exponential backoff."""
    last_error = "Unknown error"

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            log.info(f"Attempt {attempt}/{MAX_RETRIES}")
            return await scrape_video(url)

        except PlaywrightTimeout:
            last_error = "Page took too long to load. Try again."
            log.warning(f"Attempt {attempt}: timeout")

        except ValueError as e:
            raise  # Don't retry logical errors (no media found)

        except Exception as e:
            last_error = str(e)
            log.error(f"Attempt {attempt} error: {e}")

        if attempt < MAX_RETRIES:
            wait = RETRY_DELAY * (2 ** (attempt - 1))
            log.info(f"Retrying in {wait}s…")
            await asyncio.sleep(wait)

    raise RuntimeError(f"Failed after {MAX_RETRIES} attempts. {last_error}")


# ─── API Routes ───────────────────────────────────────────────────────────────

@app.route("/api/download", methods=["GET"])
def download():
    """
    Main endpoint.
    Usage: GET /api/download?url=https%3A%2F%2Fwww.pinterest.com%2Fpin%2F123456%2F
    Returns JSON with videoUrl, quality, filename, images, metadata.
    """
    raw_url = request.args.get("url", "").strip()

    if not raw_url:
        return error_response("Please provide a 'url' parameter.")

    target_url = unquote(raw_url)

    if not validate_url(target_url):
        return error_response(
            "Only Pinterest (pinterest.com, pin.it) and KlickPin URLs are supported."
        )

    try:
        result = asyncio.run(scrape_with_retries(target_url))
        return jsonify(result), 200

    except ValueError as e:
        return error_response(str(e), 404)

    except RuntimeError as e:
        return error_response(str(e), 503)

    except Exception as e:
        log.exception("Unexpected error")
        return error_response(f"Server error: {e}", 500)


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "pinsave-scraper"}), 200


@app.route("/", methods=["GET"])
def index():
    return jsonify({
        "name": "PinSave Scraper API",
        "version": "2.0.0",
        "usage": "GET /api/download?url=PINTEREST_URL",
    })


# ─── Start Server ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port  = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("DEBUG", "false").lower() == "true"
    log.info(f"PinSave API running on http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=debug)
