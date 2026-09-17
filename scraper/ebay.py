"""
eBay scraping, title parser, and search URL generator module for Vulpix Pokémon cards.
Supports Raw singles, Grade 10 slabs, special grades, and auction detail parsing.
"""

import re
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime
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


def generate_ebay_search_url(
    card_name: str,
    set_name: str = "",
    card_number: str = "",
    edition: str = "",
    language: str = "English",
    grade_tier: Optional[str] = None,
    is_raw: bool = False,
    is_auction_only: bool = False,
    is_graded: bool = False,
    **kwargs: Any,
) -> str:
    """
    Generates a direct, highly-targeted eBay search URL for any Vulpix card.
    """
    if is_graded:
        grade_tier = grade_tier or "Gem Mint 10"
        is_raw = False

    query_parts = [card_name]

    # Clean set name (remove year parentheses)
    clean_set = re.sub(r"\([0-9]{4}\)", "", set_name).strip()
    if clean_set and clean_set.lower() not in ["unknown set", ""]:
        query_parts.append(f'"{clean_set}"')

    # Card number
    clean_num = card_number.replace("No Number", "").strip()
    if clean_num:
        query_parts.append(clean_num)

    # Edition keywords
    if edition and edition.lower() not in ["unlimited", "standard", ""]:
        query_parts.append(f'"{edition}"')

    # Language keywords
    if language and language.lower() not in ["english", ""]:
        query_parts.append(f'"{language}"')

    # Grade / Condition filter
    if is_raw:
        query_parts.append("(raw, ungraded)")
    elif grade_tier:
        if "Black Label" in grade_tier:
            query_parts.append('"Black Label"')
        elif "Pristine" in grade_tier:
            query_parts.append('"Pristine 10"')
        elif "Gem Mint" in grade_tier or "10" in grade_tier:
            query_parts.append("(PSA 10, CGC 10, BGS 10)")

    query_str = " ".join(query_parts)
    encoded = urllib.parse.quote_plus(query_str)

    # eBay search URL with sorting (newly listed / lowest price)
    base = f"https://www.ebay.com/sch/i.html?_nkw={encoded}&_sacat=0&_sop=10"
    if is_auction_only:
        base += "&LH_Auction=1"
    return base


def extract_special_grading_details(title: str) -> Tuple[str, Optional[str], Optional[float], str]:
    """Extracts condition, grading company, numerical grade, and grade tier label."""
    title_clean = title.upper()

    if "BLACK LABEL" in title_clean or "BGS 10 BLACK" in title_clean:
        return "Graded", "BGS", 10.0, "Black Label 10"

    if "PRISTINE" in title_clean or "PERFECT 10" in title_clean:
        co = "CGC" if "CGC" in title_clean else ("BGS" if "BGS" in title_clean else "PSA")
        return "Graded", co, 10.0, "Pristine 10"

    grading_co = None
    for co in GRADING_COMPANIES:
        if re.search(rf"\b{co}\b", title_clean):
            grading_co = "BGS" if co == "BECKETT" else co
            break

    if not grading_co:
        return "Raw", "RAW", None, "Raw Single"

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
    language = "English"
    for pattern, lang in LANGUAGES:
        if re.search(pattern, title):
            language = lang
            break

    edition = "Unlimited"
    for pattern, ed in EDITIONS:
        if re.search(pattern, title):
            edition = ed
            break

    is_error = 0
    error_desc = ""
    for pattern, err in ERROR_PATTERNS:
        if re.search(pattern, title):
            is_error = 1
            error_desc = err
            break

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
    """Scrapes eBay listings covering both Raw cards and Graded 10 slabs."""
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

            bids_elem = item.select_one(".s-item__bidCount, .s-item__bids, .s-item__dynamic")
            item_text = item.get_text()
            has_bids = bool(bids_elem) or bool(re.search(r"\b\d+\s*bids?\b", item_text, re.I))
            listing_type = "Auction" if has_bids else "Buy It Now"

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


KNOWN_VULPIX_SETS = [
    ("Gym Heroes", ["gym heroes"]),
    ("Gym Challenge", ["gym challenge"]),
    ("Base Set", ["base set", "base 1", "shadowless"]),
    ("Neo Destiny", ["neo destiny", "darkness, and to light"]),
    ("Silver Tempest", ["silver tempest"]),
    ("Pokémon Card 151", ["151", "pokemon 151", "sv2a"]),
    ("Mega Evolution", ["mega evolution", "meg en"]),
    ("Hidden Fates", ["hidden fates"]),
    ("Incandescent Arcana", ["incandescent arcana", "s11a"]),
    ("Mega Brave", ["mega brave", "m1l"]),
    ("Crimson Haze", ["crimson haze", "sv5a"]),
    ("EX Power Keepers", ["power keepers", "ex power keepers"]),
    ("Daiichi Pan Promo", ["daiichi", "daiichi pan"]),
    ("Playing Cards", ["playing cards", "ninety-nine", "paper safari", "black 2"]),
    ("Aquapolis", ["aquapolis"]),
    ("Expedition", ["expedition"]),
    ("Team Rocket", ["team rocket"]),
    ("Fates Collide", ["fates collide"]),
    ("Prismatic Evolutions", ["prismatic evolutions"]),
]


def detect_set_name(title: str) -> str:
    """Detects Pokémon card set name from listing title."""
    t_low = title.lower()
    for s_name, kws in KNOWN_VULPIX_SETS:
        if any(kw in t_low for kw in kws):
            return s_name
    return "Unknown Set"


def extract_card_number_from_title(title: str) -> str:
    """Extracts card number (e.g. 68/102, 037/165, #138, 4 of Diamonds) from title."""
    m = re.search(r"#?([0-9]{1,3}/[0-9]{1,3})", title)
    if m:
        return m.group(1)
    m_poker = re.search(r"\b([0-9]{1,2}|Jack|Queen|King|Ace)\s+of\s+(Diamonds|Hearts|Spades|Clubs)\b", title, re.IGNORECASE)
    if m_poker:
        return m_poker.group(0)
    m_single = re.search(r"#([0-9]{1,3}[a-zA-Z]?)\b", title)
    if m_single:
        return m_single.group(1)
    return ""


def sync_ebay_user_account_trading_api(
    user_token: str,
    app_id: str = "",
    dev_id: str = "",
    cert_id: str = "",
    db_path: Optional[str] = None,
) -> Tuple[bool, str, Dict[str, Any], List[Dict[str, Any]]]:
    """
    Automated eBay Trading API Sync:
    Calls GetMyeBayBuying to pull WonList (past purchases), WatchList, and BidList.
    Any new Vulpix won cards are automatically parsed and added to my_collection.
    Returns (success, message, stats_dict, list_of_new_cards).
    """
    from db import add_card_to_collection, add_to_sniper_watchlist, get_existing_collection_identifiers

    token = (user_token or "").strip()
    if not token:
        return False, "eBay Auth Token is empty. Please enter your User Token.", {}, []

    headers = {
        "X-EBAY-API-COMPATIBILITY-LEVEL": "967",
        "X-EBAY-API-CALL-NAME": "GetMyeBayBuying",
        "X-EBAY-API-SITEID": "0",
        "Content-Type": "text/xml",
    }
    if dev_id and app_id and cert_id:
        headers["X-EBAY-API-DEV-NAME"] = dev_id
        headers["X-EBAY-API-APP-NAME"] = app_id
        headers["X-EBAY-API-CERT-NAME"] = cert_id

    is_oauth = bool(token.startswith("v^1.1#") or len(token) > 500)
    if is_oauth:
        headers["X-EBAY-API-IAF-TOKEN"] = token

    cred_xml = f"<RequesterCredentials><eBayAuthToken>{token}</eBayAuthToken></RequesterCredentials>" if not is_oauth else ""

    xml_req = f"""<?xml version="1.0" encoding="utf-8"?>
<GetMyeBayBuyingRequest xmlns="urn:ebay:apis:eBLBaseComponents">
  {cred_xml}
  <WatchList>
    <Include>true</Include>
  </WatchList>
  <BidList>
    <Include>true</Include>
  </BidList>
  <WonList>
    <Include>true</Include>
    <DurationInDays>60</DurationInDays>
  </WonList>
</GetMyeBayBuyingRequest>"""

    try:
        resp = requests.post("https://api.ebay.com/ws/api.dll", data=xml_req, headers=headers, timeout=25.0)
        if resp.status_code != 200:
            return False, f"eBay API HTTP {resp.status_code}: {resp.text[:200]}", {}, []

        root = ET.fromstring(resp.content)
        ns = {"ebay": "urn:ebay:apis:eBLBaseComponents"}
        ack = root.findtext("ebay:Ack", "", ns)

        if ack not in ["Success", "Warning"]:
            err_msg = root.findtext(".//ebay:LongMessage", "", ns) or root.findtext(".//ebay:ShortMessage", "Unknown eBay API error", ns)
            return False, f"eBay API Error: {err_msg}", {}, []

        # 1. Process WatchList -> Sniper Watchlist
        watch_count = 0
        for item in root.findall(".//ebay:WatchList//ebay:Item", ns):
            item_id = item.findtext("ebay:ItemID", "", ns)
            title = item.findtext("ebay:Title", "", ns)
            price = float(item.findtext(".//ebay:CurrentPrice", "0.0", ns) or 0.0)
            end_time = item.findtext(".//ebay:EndTime", "", ns)
            url = item.findtext(".//ebay:ViewItemURL", f"https://www.ebay.com/itm/{item_id}", ns)
            img_url = item.findtext(".//ebay:GalleryURL", "", ns) or ""

            if item_id and title:
                t_lower = title.lower()
                is_vulpix = any(kw in t_lower for kw in ["vulpix", "rokon", "alolan vulpix"]) or ("pikachu" in t_lower and "poncho" in t_lower and "vulpix" in t_lower)
                if not is_vulpix:
                    continue

                add_to_sniper_watchlist({
                    "listing_id": item_id,
                    "card_name": "Vulpix",
                    "title": title,
                    "listing_url": url,
                    "image_url": img_url,
                    "auction_end_time": end_time[:19].replace("T", " ") if end_time else "",
                    "current_bid": price,
                    "shipping_cost": 0.0,
                    "target_bid_mode": "amazing_deal",
                    "custom_max_bid": None,
                    "max_calculated_bid": round(price * 1.1, 2),
                    "status": "watching",
                    "notes": "Auto-imported from personal eBay Watchlist.",
                }, db_path=db_path)
                watch_count += 1

        # Check existing collection to detect duplicates
        existing_notes, existing_cards = get_existing_collection_identifiers(db_path=db_path)

        # 2. Process WonList -> Vault Collection
        won_items = root.findall(".//ebay:WonList//ebay:Item", ns)
        total_won = len(won_items)
        won_added = 0
        skipped_dup = 0
        skipped_non_vulpix = 0
        newly_added_cards: List[Dict[str, Any]] = []

        for item in won_items:
            item_id = item.findtext("ebay:ItemID", "", ns)
            title = item.findtext("ebay:Title", "", ns) or ""
            price = float(item.findtext(".//ebay:CurrentPrice", "0.0", ns) or 0.0)
            end_time = item.findtext(".//ebay:EndTime", "", ns)
            end_date = end_time[:10] if end_time else datetime.today().strftime("%Y-%m-%d")
            img_url = item.findtext(".//ebay:GalleryURL", "", ns) or ""

            t_lower = title.lower()
            is_vulpix = any(kw in t_lower for kw in ["vulpix", "rokon", "alolan vulpix"]) or ("pikachu" in t_lower and "poncho" in t_lower and "vulpix" in t_lower)
            if not is_vulpix:
                skipped_non_vulpix += 1
                continue

            # Duplicate check by ItemID
            is_dup = False
            if item_id:
                for note_str in existing_notes:
                    if item_id in note_str:
                        is_dup = True
                        break

            if is_dup:
                skipped_dup += 1
                continue

            cond, grader, grade_val, grade_lbl = extract_special_grading_details(title)
            meta = extract_card_metadata(title)
            set_name = detect_set_name(title)
            card_num = extract_card_number_from_title(title)

            c_key = (meta["card_name"].strip().lower(), set_name.strip().lower(), card_num.strip().lower())
            if c_key in existing_cards:
                skipped_dup += 1
                continue

            new_card = {
                "card_name": meta["card_name"],
                "set_name": set_name,
                "card_number": card_num,
                "grading_company": grader,
                "grade": grade_val or 0.0,
                "grade_label": grade_lbl,
                "cert_number": "",
                "purchase_price": price,
                "purchase_date": end_date,
                "edition": meta["edition"],
                "language": meta["language"],
                "is_error": meta["is_error"],
                "error_type": meta.get("error_type", ""),
                "is_raw": 1 if cond == "Raw" else 0,
                "image_url": img_url,
                "notes": f"Imported from eBay Order #{item_id}" if item_id else "Imported via eBay Account Sync",
            }

            add_card_to_collection(new_card, db_path=db_path)
            newly_added_cards.append(new_card)
            existing_cards.add(c_key)
            if item_id:
                existing_notes.add(item_id)
            won_added += 1

        # 3. Active Bids Count
        bid_items = root.findall(".//ebay:BidList//ebay:Item", ns)
        bid_count = len(bid_items)

        parts = []
        if won_added > 0:
            parts.append(f"🎉 Added {won_added} new Vulpix card(s) to Vault")
        elif skipped_dup > 0:
            parts.append(f"All {skipped_dup} Vulpix card(s) in past 60-day purchases are already in your Vault")
        elif total_won > 0:
            parts.append(f"Found {total_won} eBay purchase(s), but 0 Vulpix cards ({skipped_non_vulpix} non-Vulpix items excluded)")
        else:
            parts.append("0 purchases found in past 60 days")

        if watch_count > 0:
            parts.append(f"{watch_count} watchlist item(s) tracked")
        if bid_count > 0:
            parts.append(f"{bid_count} active bid(s) tracked")

        summary_msg = "Synced with eBay! " + " • ".join(parts) + "."
        stats = {
            "watch_count": watch_count,
            "won_added": won_added,
            "skipped_dup": skipped_dup,
            "skipped_non_vulpix": skipped_non_vulpix,
            "bid_count": bid_count,
            "total_won": total_won,
        }
        return True, summary_msg, stats, newly_added_cards

    except Exception as e:
        return False, f"Connection or parsing error: {e}", {}, []

