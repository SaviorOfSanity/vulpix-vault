"""
eBay scraping and title parser module for graded Vulpix Pokémon cards.
Extracts listing metadata, pricing, grading companies, and numerical grades.
"""

import re
import urllib.parse
from typing import Any, Dict, List, Optional, Tuple
import requests
from bs4 import BeautifulSoup

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
]

GRADING_COMPANIES = ["PSA", "CGC", "BGS", "BECKETT", "ARS", "ACE", "SGC"]

CARD_VARIANTS = [
    (r"(?i)1st\s+edition.*base\s*set", "Base Set 1st Edition Vulpix #68"),
    (r"(?i)shadowless.*base\s*set|base\s*set.*shadowless", "Base Set Shadowless Vulpix #68"),
    (r"(?i)base\s*set\s*(?:unlimited)?", "Base Set Unlimited Vulpix #68"),
    (r"(?i)erika['’]?s\s+vulpix", "Erika's Vulpix (Gym Heroes)"),
    (r"(?i)brock['’]?s\s+vulpix", "Brock's Vulpix (Gym Challenge)"),
    (r"(?i)light\s+vulpix", "Light Vulpix (Neo Destiny)"),
    (r"(?i)alolan\s+vulpix\s*vstar", "Alolan Vulpix VSTAR"),
    (r"(?i)alolan\s+vulpix\s*v", "Alolan Vulpix V"),
    (r"(?i)alolan\s+vulpix", "Alolan Vulpix"),
    (r"(?i)delta\s+species", "Vulpix Delta Species (Dragon Frontiers)"),
    (r"(?i)corocoro", "Vulpix Japanese CoroCoro Promo"),
    (r"(?i)vending", "Vulpix Japanese Vending Series"),
    (r"(?i)pokemon\s*151|151", "Vulpix (Pokémon 151)"),
    (r"(?i)obsidian\s*flames", "Vulpix (Obsidian Flames)"),
]


def extract_grading_details(title: str) -> Tuple[Optional[str], Optional[float]]:
    """Extract grading company (PSA, CGC, BGS, etc.) and numerical grade (e.g. 10, 9.5) from title."""
    title_clean = title.upper()
    grading_co = None
    grade_val = None

    # Identify grading company
    for co in GRADING_COMPANIES:
        pattern = rf"\b{co}\b"
        if re.search(pattern, title_clean):
            grading_co = "BGS" if co == "BECKETT" else co
            break

    # Extract numerical grade associated with company or standard keywords
    grade_match = re.search(
        r"(?:PSA|CGC|BGS|BECKETT|ARS|ACE|SGC|GRADE|GEM\s*MINT|MINT|NM-MT)?\s*([0-9]{1,2}(?:\.[0-9])?)\b",
        title_clean,
    )
    if grade_match:
        try:
            val = float(grade_match.group(1))
            if 1.0 <= val <= 10.0:
                grade_val = val
        except ValueError:
            pass

    # Alternative regex fallback if grade is formatted like "PSA 10" or "CGC 9.5"
    if grading_co and grade_val is None:
        co_grade_match = re.search(rf"{grading_co}\s*([0-9]{1,2}(?:\.[0-9])?)", title_clean)
        if co_grade_match:
            try:
                val = float(co_grade_match.group(1))
                if 1.0 <= val <= 10.0:
                    grade_val = val
            except ValueError:
                pass

    return grading_co, grade_val


def extract_card_name(title: str) -> str:
    """Normalize and categorize Vulpix card name from listing title."""
    for pattern, name in CARD_VARIANTS:
        if re.search(pattern, title):
            return name
    return "Vulpix (Graded)"


def clean_price(price_str: str) -> float:
    """Convert price strings like '$45.00', 'US $120.50' to float."""
    match = re.search(r"[\$£€]?\s*([0-9]+(?:\.[0-9]{2})?)", price_str.replace(",", ""))
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            return 0.0
    return 0.0


def extract_listing_id(url: str, default_title: str = "") -> str:
    """Extract unique eBay item number from URL or hash fallback."""
    match = re.search(r"/itm/(?:[a-zA-Z0-9\-_]+/)?([0-9]{9,15})", url)
    if match:
        return match.group(1)
    # Parameter fallback
    match_param = re.search(r"item=([0-9]{9,15})", url)
    if match_param:
        return match_param.group(1)
    import hashlib
    return hashlib.md5(f"{default_title}-{url}".encode("utf-8")).hexdigest()[:16]


def scrape_ebay_listings(query: str = "Vulpix graded (PSA, CGC, BGS)") -> List[Dict[str, Any]]:
    """
    Scrapes current Buy It Now and Auction listings for graded Vulpix cards on eBay.
    Returns a list of parsed item dictionaries.
    """
    encoded_query = urllib.parse.quote_plus(query)
    # LH_BIN=1 filters Buy It Now (or LH_All=1 for all listings)
    url = f"https://www.ebay.com/sch/i.html?_nkw={encoded_query}&_sacat=0&_sop=10"

    headers = {
        "User-Agent": USER_AGENTS[0],
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Referer": "https://www.google.com/",
    }

    results = []
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code != 200:
            print(f"[Scraper] Warning: eBay returned status {response.status_code}")
            return results

        soup = BeautifulSoup(response.text, "html.parser")
        items = soup.select(".s-item__wrapper, .s-item, .s-card")

        for item in items:
            title_elem = item.select_one(".s-item__title, .s-card__title")
            if not title_elem:
                continue

            title = title_elem.get_text(strip=True)
            if "Shop on eBay" in title or not title:
                continue

            # Must mention Vulpix
            if not re.search(r"(?i)vulpix", title):
                continue

            # Extract link
            link_elem = item.select_one(".s-item__link, a[href*='/itm/']")
            listing_url = link_elem["href"] if link_elem and link_elem.has_attr("href") else ""
            if not listing_url:
                continue

            listing_id = extract_listing_id(listing_url, default_title=title)

            # Price
            price_elem = item.select_one(".s-item__price")
            price_str = price_elem.get_text(strip=True) if price_elem else "$0.00"
            price = clean_price(price_str)
            if price <= 0:
                continue

            # Shipping
            shipping_elem = item.select_one(".s-item__shipping, .s-item__logisticsCost")
            shipping_str = shipping_elem.get_text(strip=True) if shipping_elem else "Free"
            shipping_cost = 0.0 if "Free" in shipping_str or "free" in shipping_str.lower() else clean_price(shipping_str)
            total_price = round(price + shipping_cost, 2)

            # Image
            img_elem = item.select_one(".s-item__image-img img, .s-item__image img, img")
            image_url = ""
            if img_elem:
                image_url = img_elem.get("src") or img_elem.get("data-src") or ""

            # Listing type
            listing_type = "Buy It Now"
            if item.select_one(".s-item__bids"):
                listing_type = "Auction"

            # Parse Grading & Card normalization
            grading_co, grade = extract_grading_details(title)
            card_name = extract_card_name(title)

            results.append({
                "listing_id": listing_id,
                "title": title,
                "card_name": card_name,
                "grading_company": grading_co or "PSA",
                "grade": grade or 9.0,
                "price": price,
                "shipping_cost": shipping_cost,
                "total_price": total_price,
                "listing_url": listing_url,
                "image_url": image_url,
                "listing_type": listing_type,
                "deal_rating": "unrated",
                "fair_value_estimate": None,
                "discount_percentage": None,
                "ai_rationale": None,
                "sale_date": None,
            })

    except Exception as e:
        print(f"[Scraper] Error during eBay scrape: {e}")

    return results
