from bs4 import BeautifulSoup
from datetime import datetime, date
import json


def parse_products(html: str, keyword: str):
    scrape_date = date.today().isoformat()

    soup = BeautifulSoup(html, "html.parser")
    products = []
    seen_asins = set()

    items = soup.find_all("div", attrs={"data-component-type": "s-search-result"})

    for item in items:
        asin = item.get("data-asin", "").strip()
        if not asin or asin in seen_asins:
            continue

        title = item.find("h2")
        product_name = title.get_text(strip=True) if title else ""

        brand_name = product_name.split()[0] if product_name else ""  # renamed to avoid any collision

        price_tag = item.find("span", class_="a-offscreen")
        price = price_tag.get_text(strip=True) if price_tag else ""

        seen_asins.add(asin)

        products.append({
            "product_name": product_name,
            "asin": asin,
            "price": price,
            "brandName": brand_name,
            "date": scrape_date,
        })

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_keyword = keyword.replace(" ", "_")
    filename = f"amazon_{safe_keyword}_{timestamp}.json"

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(products, f, indent=2, ensure_ascii=False)

    return filename