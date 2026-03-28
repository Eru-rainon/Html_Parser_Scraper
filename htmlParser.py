"""
Amazon Product Scraper
======================
Searches Amazon.in for a keyword and extracts product details:
  - product_name
  - asin
  - price
  - brandName
  - date (scrape date)

Usage:
    python amazon_scraper.py --keyword "shoes" --output results.json
    python amazon_scraper.py --keyword "laptops" --pages 3
    python amazon_scraper.py --file amazon_shoes.txt   # parse a saved HTML file

Requirements:
    pip install requests beautifulsoup4
"""

import argparse
import json
import re
import sys
import time
import random
from datetime import date
from pathlib import Path

from bs4 import BeautifulSoup

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


# ─────────────────────────────────────────────
# HTTP headers that mimic a real browser
# ─────────────────────────────────────────────
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-IN,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,image/avif,image/webp,*/*;q=0.8"
    ),
    "Referer": "https://www.amazon.in/",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

BASE_URL = "https://www.amazon.in/s?k={keyword}&page={page}"


# ─────────────────────────────────────────────
# Parsing logic
# ─────────────────────────────────────────────

def clean_price(raw: str) -> str:
    """Normalise a price string like '₹1,799.00' → '₹1,799.00'."""
    if not raw:
        return ""
    return raw.strip()


def parse_products(html: str, scrape_date: str = None) -> list[dict]:
    """
    Parse an Amazon search-results HTML page and return a list of product dicts.

    Each dict has the keys:
        product_name, asin, price, brandName, date
    """
    if scrape_date is None:
        scrape_date = date.today().isoformat()

    soup = BeautifulSoup(html, "html.parser")
    products = []
    seen_asins = set()

    # ── Main search result cards ─────────────────────────────────────────────
    # Each product card is a <div> with data-component-type="s-search-result"
    # and a non-empty data-asin attribute.
    result_items = soup.find_all(
        "div",
        attrs={"data-component-type": "s-search-result"},
    )

    for item in result_items:
        asin = item.get("data-asin", "").strip()
        if not asin or asin in seen_asins:
            continue

        # ── Product name ─────────────────────────────────────────────────────
        # The product title is in an <h2 class="a-size-base-plus …"> (NOT the
        # brand mini-h2 which has class "a-size-mini").
        product_name = ""
        title_block = item.find(attrs={"data-cy": "title-recipe"})
        if title_block:
            # Try the full-title h2 (class contains a-size-base-plus)
            title_h2 = title_block.find(
                "h2",
                class_=lambda c: c and "a-size-base-plus" in c,
            )
            if title_h2:
                product_name = title_h2.get_text(separator=" ", strip=True)
                product_name = re.sub(r"^Sponsored Ad\s*-\s*", "", product_name)
            else:
                # Fallback: aria-label on the link
                link = title_block.find("a", attrs={"aria-label": True})
                if link:
                    product_name = re.sub(
                        r"^Sponsored Ad\s*-\s*", "", link["aria-label"]
                    )

        # ── Brand name ───────────────────────────────────────────────────────
        # Amazon places the brand in a small <h2 class="a-size-mini"> above
        # the product title.
        brand_name = ""
        brand_h2 = item.find("h2", class_="a-size-mini")
        if brand_h2:
            brand_span = brand_h2.find("span", class_="a-size-base-plus")
            if brand_span:
                brand_name = brand_span.get_text(strip=True)

        # ── Price ────────────────────────────────────────────────────────────
        # The current price is inside <span class="a-offscreen"> within an
        # <span class="a-price" data-a-color="base">.
        price = ""
        price_block = item.find(attrs={"data-cy": "price-recipe"})
        if price_block:
            price_tag = price_block.find(
                "span", attrs={"data-a-color": "base", "class": "a-price"}
            )
            if price_tag:
                offscreen = price_tag.find("span", class_="a-offscreen")
                if offscreen:
                    price = clean_price(offscreen.get_text(strip=True))

        # Fallback: any a-price in the item
        if not price:
            fallback = item.find(
                "span", attrs={"data-a-color": "base", "class": "a-price"}
            )
            if fallback:
                offscreen = fallback.find("span", class_="a-offscreen")
                if offscreen:
                    price = clean_price(offscreen.get_text(strip=True))

        seen_asins.add(asin)
        products.append(
            {
                "product_name": product_name,
                "asin": asin,
                "price": price,
                "brandName": brand_name,
                "date": scrape_date,
            }
        )

    return products


# ─────────────────────────────────────────────
# Fetching logic
# ─────────────────────────────────────────────

def fetch_page(keyword: str, page: int = 1) -> str:
    """Fetch one page of Amazon search results and return raw HTML."""
    if not REQUESTS_AVAILABLE:
        raise RuntimeError(
            "The 'requests' library is not installed. "
            "Run: pip install requests"
        )

    url = BASE_URL.format(
        keyword=requests.utils.quote(keyword), page=page
    )
    print(f"  → Fetching: {url}")

    session = requests.Session()
    resp = session.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    return resp.text


# ─────────────────────────────────────────────
# CLI entry point
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Scrape Amazon.in search results and save to JSON."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--keyword", "-k",
        help="Search keyword (e.g. 'shoes')",
    )
    group.add_argument(
        "--file", "-f",
        help="Path to a saved Amazon HTML file to parse (no network needed)",
    )
    parser.add_argument(
        "--pages", "-p",
        type=int,
        default=1,
        help="Number of result pages to scrape (default: 1). Only used with --keyword.",
    )
    parser.add_argument(
        "--output", "-o",
        default="amazon_products.json",
        help="Output JSON file path (default: amazon_products.json)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=2.0,
        help="Delay in seconds between page requests (default: 2.0)",
    )

    args = parser.parse_args()

    today = date.today().isoformat()
    all_products: list[dict] = []

    # ── Mode 1: parse a local HTML file ──────────────────────────────────────
    if args.file:
        html_path = Path(args.file)
        if not html_path.exists():
            print(f"[ERROR] File not found: {args.file}", file=sys.stderr)
            sys.exit(1)

        print(f"[INFO] Parsing local file: {args.file}")
        html = html_path.read_text(encoding="utf-8", errors="replace")
        products = parse_products(html, scrape_date=today)
        all_products.extend(products)
        print(f"[INFO] Found {len(products)} products.")

    # ── Mode 2: live scrape ───────────────────────────────────────────────────
    else:
        keyword = args.keyword
        print(f"[INFO] Searching Amazon.in for: '{keyword}'")

        for page_num in range(1, args.pages + 1):
            print(f"[INFO] Page {page_num}/{args.pages} …")
            try:
                html = fetch_page(keyword, page_num)
            except Exception as exc:
                print(f"[ERROR] Could not fetch page {page_num}: {exc}", file=sys.stderr)
                break

            products = parse_products(html, scrape_date=today)
            print(f"  → Found {len(products)} products on this page.")
            all_products.extend(products)

            if page_num < args.pages:
                wait = args.delay + random.uniform(0, 1)
                print(f"  → Waiting {wait:.1f}s before next page …")
                time.sleep(wait)

    # ── De-duplicate across pages ─────────────────────────────────────────────
    seen = set()
    unique_products = []
    for p in all_products:
        if p["asin"] not in seen:
            seen.add(p["asin"])
            unique_products.append(p)

    # ── Save results ──────────────────────────────────────────────────────────
    output_path = Path(args.output)
    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(unique_products, fh, ensure_ascii=False, indent=2)

    print(f"\n[DONE] Saved {len(unique_products)} unique products → {output_path}")


if __name__ == "__main__":
    main()