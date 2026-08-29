"""
eBay scraping and title parser module for Vulpix Pokémon cards.
Extracts condition (Raw vs Graded), grading companies, numerical grades,
special grade labels (Pristine 10, Black Label 10, Gem Mint 10), editions,
languages, and error card attributes.
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

LANGUAGES = [
    (r"(?i)\b(japanese|jpn|japan|nihon)\b", "Japanese"),
    (r"(?i)\b(german|deutsch)\b", "German"),
    (r"(?i)\b(french|français|francais)\b", "French"),
    (r"(?i)\b(italian|italiano)\b", "Italian"),
    (r"(?i)\b(spanish|español|espanol)\b", "Spanish"),
    (r"(?i)\b(korean|kor)\b", "Korean"),
    (r"(?i)\b(chinese|chn|taiwan)\b", "Chinese"),
]

EDITIONS = [
    (r"(?i)\b(1st\s*edition|1st\s*ed|first\s*edition)\b", "1st Edition"),
    (r"(?i)\b(shadowless)\b", "Shadowless"),
    (r"(?i)\b(reverse\s*holo|rev\s*holo|reverse\s*foil)\b", "Reverse Holo"),
    (r"(?i)\b(promo|black\s*star\s*promo|corocoro|vending)\b", "Promo"),
    (r"(?i)\b(unlimited)\b", "Unlimited"),
]

ERROR_PATTERNS = [
    (r"(?i)\b(hp\s*50|50\s*hp\s*error)\b", "HP 50 Error"),
    (r"(?i)\b(no\s*rarity|no\s*rarity\s*symbol)\b", "No Rarity Symbol"),
    (r"(?i)\b(misprint|error\s*card|miscut|square\s*cut|crimp|crimped)\b", "Print/Cut Error"),
]


def extract_special_grading_details(title: str) -> Tuple[str, Optional[str], Optional[float], str]:
    """
    Extracts condition_type ('Graded' or 'Raw'), grading company, grade, and grade_label.
    Detects special grades like Pristine 10, Black Label 10, Gem Mint 10.
    """
    title_clean = title.upper()

    # Detect Black Label
    if "BLACK LABEL" in title_clean or "BGS 10 BLACK" in title_clean:
        return "Graded", "BGS", 10.0, "Black Label 10"

    # Detect Pristine 10
    if "PRISTINE" in title_clean or "PERFECT 10" in title_clean:
        co = "CGC" if "CGC" in title_clean else ("BGS" if "BGS" in title_clean else "PSA")
        return "Graded", co, 10.0, "Pristine 10"

    # Detect Standard Grading Companies
    grading_co = None
    for co in GRADING_COMPANIES:
        if re.search(rf"\b{co}\b", title_clean):
            grading_co = "BGS" if co == "BECKETT" else co
            break

    if not grading_co:
        # Check if explicitly Raw or Ungraded
        if any(term in title_clean for term in ["RAW", "UNGRADED", "NM", "LP", "MINT / NM", "SINGLE"]):
            return "Raw", "RAW", None, "Raw Single"
        # If no grading company mentioned, assume Raw Single
        return "Raw", "RAW", None, "Raw Single"

    # Extract numerical grade
    grade_val = 10.0
    grade_match = re.search(
        rf"(?:{grading_co}|GRADE|GEM\s*MINT|MINT|NM-MT)?\s*([0-9]{{1,2}}(?:\.[0-9])?)\b",
        title_clean,
    )
    if grade_match:
        try:
            val = float(grade_match.group(1))
            if 1.0 <= val <= 10.0:
                grade_val = val
        except ValueError:
            pass

    grade_label = "Gem Mint" if grade_val >= 9.5 else ("Mint" if grade_val >= 9.0 else f"Grade {grade_val}")
    return "Graded", grading_co, grade_val, grade_label


def extract_card_metadata(title: str) -> Dict[str, Any]:
    """Extracts card name, language, edition, and error information from title."""
    # Language
    language = "English"
    for pattern, lang in LANGUAGES:
        if re.search(pattern, title):
            language = lang
            break

    # Edition
    edition = "Unlimited"
    for pattern, ed in EDITIONS:
        if re.search(pattern, title):
            edition = ed
            break

    # Error
    is_error = 0
    error_desc = ""
    for pattern, err in ERROR_PATTERNS:
        if re.search(pattern, title):
            is_error = 1
            error_desc = err
            break

    # Card Name Normalization
    card_name = "Vulpix"
    if re.search(r"(?i)alolan\s+vulpix\s*vstar", title):
        card_name = "Alolan Vulpix VSTAR"
    elif re.search(r"(?i)alolan\s+vulpix\s*v", title):
        card_name = "Alolan Vulpix V"
    elif re.search(r"(?i)alolan\s+vulpix", title):
        card_name = "Alolan Vulpix"
    elif re.search(r"(?i)erika['’]?s\s+vulpix", title):
        card_name = "Erika's Vulpix"
    elif re.search(r"(?i)brock['’]?s\s+vulpix", title):
        card_name = "Brock's Vulpix"
    elif re.search(r"(?i)light\s+vulpix", title):
        card_name = "Light Vulpix"
    elif re.search(r"(?i)delta\s+species", title):
        card_name = "Vulpix (Delta Species)"
    elif re.search(r"(?i)shadowless", title):
        card_name = "Vulpix (Shadowless)"

    return {
        "card_name": card_name,
        "language": language,
        "edition": edition,
        "is_error": is_error,
        "error_type": error_desc,
    }


def clean_price(price_str: str) -> float:
    match = re.search(r"[\$£€]?\s*([0-9]+(?:\.[0-9]{2})?)", price_str.replace(",", ""))
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            return 0.0
    return 0.0


def extract_listing_id(url: str, default_title: str = "") -> str:
    match = re.search(r"/itm/(?:[a-zA-Z0-9\-_]+/)?([0-9]{9,15})", url)
    if match:
        return match.group(1)
    match_param = re.search(r"item=([0-9]{9,15})", url)
    if match_param:
        return match_param.group(1)
    import hashlib
    return hashlib.md5(f"{default_title}-{url}".encode("utf-8")).hexdigest()[:16]


def scrape_ebay_listings(query: str = "Vulpix Pokemon card (graded, PSA 10, raw, 1st edition)") -> List[Dict[str, Any]]:
    """
    Scrapes eBay listings covering both Raw cards and Graded 10 slabs.
    Returns structured listing dictionaries.
    """
    encoded_query = urllib.parse.quote_plus(query)
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
            if "Shop on eBay" in title or not title or not re.search(r"(?i)vulpix", title):
                continue

            link_elem = item.select_one(".s-item__link, a[href*='/itm/']")
            listing_url = link_elem["href"] if link_elem and link_elem.has_attr("href") else ""
            if not listing_url:
                continue

            listing_id = extract_listing_id(listing_url, default_title=title)

            # Price & Shipping
            price_elem = item.select_one(".s-item__price")
            price_str = price_elem.get_text(strip=True) if price_elem else "$0.00"
            price = clean_price(price_str)
            if price <= 0:
                continue

            shipping_elem = item.select_one(".s-item__shipping, .s-item__logisticsCost")
            shipping_str = shipping_elem.get_text(strip=True) if shipping_elem else "Free"
            shipping_cost = 0.0 if "Free" in shipping_str or "free" in shipping_str.lower() else clean_price(shipping_str)
            total_price = round(price + shipping_cost, 2)

            img_elem = item.select_one(".s-item__image-img img, .s-item__image img, img")
            image_url = img_elem.get("src") or img_elem.get("data-src") or "" if img_elem else ""

            listing_type = "Auction" if item.select_one(".s-item__bids") else "Buy It Now"

            # Parse Grading, Special Label, Edition, Language & Errors
            condition_type, grading_co, grade, grade_label = extract_special_grading_details(title)
            meta = extract_card_metadata(title)

            results.append({
                "listing_id": listing_id,
                "title": title,
                "card_name": meta["card_name"],
                "grading_company": grading_co,
                "grade": grade,
                "grade_label": grade_label,
                "condition_type": condition_type,
                "edition": meta["edition"],
                "language": meta["language"],
                "is_error": meta["is_error"],
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
