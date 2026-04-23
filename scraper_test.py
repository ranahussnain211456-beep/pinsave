"""
scraper_test.py — Standalone CLI test (no Flask needed)
Usage:  python scraper_test.py https://klickpin.com/some-post
"""

import asyncio
import sys
import json
from server import scrape_with_retries

async def main():
    url = sys.argv[1] if len(sys.argv) > 1 else "https://klickpin.com/"
    print(f"\n🔍 Scraping: {url}\n{'─'*60}")
    try:
        result = await scrape_with_retries(url)
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
