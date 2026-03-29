from bs4 import BeautifulSoup
from datetime import datetime
import json
import os


def parse_reviews(html: str, asin: str):
    """
    Parses Amazon review HTML and extracts reviewer name + first 300 chars
    of review text for each review found.

    Args:
        html:         Raw HTML string containing the review list.
        source_label: A short label used to name the output file
                      (e.g. a product name or keyword).

    Returns:
        The path to the JSON file that was written.
    """
    soup = BeautifulSoup(html, "html.parser")
    reviews = []
    seen_review_ids = set()

    # Each review is a <li data-hook="review"> element
    items = soup.find_all("li", attrs={"data-hook": "review"})

    for item in items:
        review_id = item.get("id", "").strip()
        if not review_id or review_id in seen_review_ids:
            continue

        # Rating lives in <i data-hook="review-star-rating"><span class="a-icon-alt">
        rating_tag = item.find("i", attrs={"data-hook": "review-star-rating"})
        if rating_tag:
            alt_text = rating_tag.find("span", class_="a-icon-alt")
            # e.g. "5.0 out of 5 stars" → "5.0"
            rating = alt_text.get_text(strip=True).split()[0] if alt_text else ""
        else:
            rating = ""

        # Date lives in <span data-hook="review-date">
        date_tag = item.find("span", attrs={"data-hook": "review-date"})
        review_date = date_tag.get_text(strip=True) if date_tag else ""

        # Review body is inside <span data-hook="review-body">
        body_tag = item.find("span", attrs={"data-hook": "review-body"})
        if body_tag:
            raw_text = body_tag.get_text(separator=" ", strip=True)
            review_snippet = raw_text[:500]
        else:
            review_snippet = ""

        seen_review_ids.add(review_id)

        reviews.append({
            "rating": rating,
            "review_date": review_date,
            "review_snippet": review_snippet,
        })

        output_data = {
            "asin": asin,
            "reviews": reviews
        }

    # Build a unique filename: reviews_<label>_<YYYYMMDD_HHMMSS>.json
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    os.makedirs("ReviewFiles", exist_ok=True)
    filename = os.path.join("ReviewFiles", f"reviews_{timestamp}.json")

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    return filename
