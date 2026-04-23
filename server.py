"""
Pinterest Scraper - Railway Compatible Version
Uses requests + BeautifulSoup (no browser needed)
"""

import os
import re
import json
import logging
from urllib.parse import urlparse, unquote

import requests
from bs4 import BeautifulSoup
from flask import Flask, request, jsonify
from flask_cors import CORS

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("pinsave")

app = Flask(__name__)
CORS(app)

ALLOWED_DOMAINS = [
    "pinterest.com", "www.pinterest.com", "pin.it",
    "pinterest.co.uk", "pinterest.ca", "pinterest.com.au",
    "klickpin.com", "www.klickpin.com",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}


def validate_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        host = parsed.netloc.lower().replace("www.", "")
        return any(host in domain or domain in host for domain in ALLOWED_DOMAINS) \
               and parsed.scheme in ("http", "https")
    except Exception:
        return False


def error_response(message: str, code: int = 400):
    return jsonify({"success": False, "error": message}), code


def scrape_pinterest(url: str) -> dict:
    session = requests.Session()
    session.headers.update(HEADERS)

    # Follow redirects (for pin.it short URLs)
    resp = session.get(url, timeout=15, allow_redirects=True)
    resp.raise_for_status()
    html = resp.text
    final_url = resp.url

    soup = BeautifulSoup(html, "html.parser")
    video_sources = []
    image_sources = []

    # ── 1. Search JSON-LD structured data ────────────────────────────────────
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
            items = data if isinstance(data, list) else [data]
            for item in items:
                if item.get("contentUrl"):
                    video_sources.append({"url": item["contentUrl"], "quality": "1080p"})
                if item.get("embedUrl"):
                    video_sources.append({"url": item["embedUrl"], "quality": ""})
                for g in item.get("@graph", []):
                    if g.get("contentUrl"):
                        video_sources.append({"url": g["contentUrl"], "quality": "1080p"})
        except Exception:
            pass

    # ── 2. Search og:video meta tags ─────────────────────────────────────────
    for prop in ["og:video", "og:video:url", "og:video:secure_url"]:
        tag = soup.find("meta", property=prop)
        if tag and tag.get("content"):
            video_sources.append({"url": tag["content"], "quality": ""})

    # ── 3. Search inline JSON data (Pinterest embeds video in __PWS_DATA__) ──
    video_patterns = [
        r'"url"\s*:\s*"(https?://[^"]+\.mp4[^"]*)"',
        r'"contentUrl"\s*:\s*"(https?://[^"]+\.mp4[^"]*)"',
        r'"video_url"\s*:\s*"(https?://[^"]+\.mp4[^"]*)"',
        r'(https?://v1\.pinimg\.com/videos/[^"\'>\s]+\.mp4[^"\'>\s]*)',
        r'(https?://[^"\'>\s]+pinimg[^"\'>\s]+\.mp4[^"\'>\s]*)',
    ]
    for pattern in video_patterns:
        for match in re.findall(pattern, html):
            clean = match.replace("\\u002F", "/").replace("\\/", "/")
            if clean.startswith("http"):
                q = "1080p" if "1080" in clean else ("720p" if "720" in clean else "")
                video_sources.append({"url": clean, "quality": q})

    # ── 4. Extract images ─────────────────────────────────────────────────────
    og_img = soup.find("meta", property="og:image")
    if og_img and og_img.get("content"):
        image_sources.append(og_img["content"])

    # ── 5. Deduplicate ────────────────────────────────────────────────────────
    seen = set()
    unique = []
    for s in video_sources:
        u = s.get("url", "")
        if u and u not in seen:
            seen.add(u)
            unique.append(s)

    # ── 6. Pick best quality ──────────────────────────────────────────────────
    best = None
    for pref in ["1080", "720", "480", "360"]:
        for s in unique:
            if pref in s.get("url", "") or pref in s.get("quality", ""):
                best = s
                break
        if best:
            break
    if not best and unique:
        best = unique[0]

    # ── 7. Get metadata ───────────────────────────────────────────────────────
    title = soup.title.string if soup.title else ""
    desc_tag = soup.find("meta", attrs={"name": "description"})
    description = desc_tag["content"] if desc_tag and desc_tag.get("content") else ""

    if not best:
        raise ValueError("No video found. Make sure this is a public Pinterest video pin.")

    filename = os.path.basename(urlparse(best["url"]).path) or "video.mp4"
    if not filename.endswith((".mp4", ".webm", ".mov")):
        filename = "video.mp4"

    return {
        "success": True,
        "videoUrl": best["url"],
        "quality": best.get("quality") or "HD",
        "filename": filename,
        "images": image_sources[:5],
        "allVideoSources": unique,
        "metadata": {"title": title, "description": description},
    }


@app.route("/api/download", methods=["GET"])
def download():
    raw_url = request.args.get("url", "").strip()
    if not raw_url:
        return error_response("Please provide a 'url' parameter.")

    target_url = unquote(raw_url)
    if not validate_url(target_url):
        return error_response("Only Pinterest and KlickPin URLs are supported.")

    try:
        result = scrape_pinterest(target_url)
        return jsonify(result), 200
    except ValueError as e:
        return error_response(str(e), 404)
    except Exception as e:
        log.exception("Scrape error")
        return error_response(f"Server error: {e}", 500)


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "pinsave-scraper"}), 200


@app.route("/", methods=["GET"])
def index():
    return jsonify({"name": "PinSave Scraper API", "version": "3.0.0",
                    "usage": "GET /api/download?url=PINTEREST_URL"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    log.info(f"PinSave API running on http://localhost:{port}")
    app.run(host="0.0.0.0", port=port)
