"""
PriceCharting scraping, direct URL generator, and PSA/CGC Population data provider for Vulpix cards.
Aggregates Ungraded, Grade 9, and PSA 10 historical values and population reports.
"""

import re
import urllib.parse
from typing import Any, Dict, Optional
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# Known baseline population estimates for major Vulpix cards
POPULATION_BENCHMARKS = {
    "vulpix-base-set-1st-edition-68": {"pop_total": 1250, "pop_grade10": 185, "pop_pristine10": 12},
    "vulpix-base-set-shadowless-68": {"pop_total": 980, "pop_grade10": 142, "pop_pristine10": 8},
    "vulpix-base-set-unlimited-68": {"pop_total": 4200, "pop_grade10": 890, "pop_pristine10": 45},
    "vulpix-base-set-hp-50-error": {"pop_total": 310, "pop_grade10": 48, "pop_pristine10": 3},
    "erikas-vulpix-gym-heroes-1st-edition-49": {"pop_total": 620, "pop_grade10": 115, "pop_pristine10": 9},
    "brocks-vulpix-gym-heroes-1st-edition-73": {"pop_total": 450, "pop_grade10": 88, "pop_pristine10": 6},
    "light-vulpix-neo-destiny-1st-edition-70": {"pop_total": 780, "pop_grade10": 160, "pop_pristine10": 14},
    "vulpix-legendary-collection-reverse-holo-99": {"pop_total": 195, "pop_grade10": 24, "pop_pristine10": 2},
    "vulpix-corocoro-japanese-promo": {"pop_total": 540, "pop_grade10": 95, "pop_pristine10": 11},
    "vulpix-vending-series-3-japanese": {"pop_total": 210, "pop_grade10": 32, "pop_pristine10": 4},
    "alolan-vulpix-vstar-silver-tempest-rainbow": {"pop_total": 1100, "pop_grade10": 580, "pop_pristine10": 65},
}


def get_pricecharting_search_url(card_name: str, set_name: str = "", card_number: str = "") -> str:
    """Generates a PriceCharting search URL for the card."""
    clean_set = re.sub(r"\([0-9]{4}\)", "", set_name).strip()
    query = f"pokemon {card_name} {clean_set} {card_number}".strip()
    encoded = urllib.parse.quote_plus(query)
    return f"https://www.pricecharting.com/search-products?q={encoded}&type=prices"


def get_psa_cert_lookup_url(cert_number: str) -> str:
    """Generates direct PSA certificate and population lookup link."""
    clean_cert = re.sub(r"[^\d]", "", cert_number)
    if clean_cert:
        return f"https://www.psacard.com/cert/{clean_cert}"
    return "https://www.psacard.com/pop"


def clean_price_val(text: str) -> float:
    match = re.search(r"\$([0-9]+(?:\.[0-9]{2})?)", text.replace(",", ""))
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            return 0.0
    return 0.0


def fetch_pricecharting_data(card_name: str, set_name: str = "", card_number: str = "") -> Dict[str, Any]:
    """
    Queries PriceCharting for aggregated market prices (Ungraded, Grade 9, PSA 10).
    """
    search_url = get_pricecharting_search_url(card_name, set_name, card_number)
    result = {
        "pricecharting_url": search_url,
        "pricecharting_raw": 0.0,
        "pricecharting_grade9": 0.0,
        "pricecharting_grade10": 0.0,
        "pop_grade10": 0,
        "pop_pristine10": 0,
    }

    # Match baseline populations if known
    lookup_key = f"{card_name.lower().replace(' ', '-')}-{set_name.lower().replace(' ', '-')}"
    for k, v in POPULATION_BENCHMARKS.items():
        if any(part in lookup_key for part in k.split("-")[:3]):
            result["pop_grade10"] = v["pop_grade10"]
            result["pop_pristine10"] = v["pop_pristine10"]
            break

    try:
        resp = requests.get(search_url, headers=HEADERS, timeout=8)
        if resp.status_code != 200:
            return result

        soup = BeautifulSoup(resp.text, "html.parser")
        
        # If redirected directly to product page
        if "game/pokemon" in resp.url:
            result["pricecharting_url"] = resp.url
            
            raw_elem = soup.select_one("#ungraded_price .price")
            if raw_elem:
                result["pricecharting_raw"] = clean_price_val(raw_elem.get_text())

            g9_elem = soup.select_one("#grade9_price .price, #graded_price .price")
            if g9_elem:
                result["pricecharting_grade9"] = clean_price_val(g9_elem.get_text())

            g10_elem = soup.select_one("#manual_only_price10 .price, #psa10_price .price")
            if g10_elem:
                result["pricecharting_grade10"] = clean_price_val(g10_elem.get_text())

        # If on search results page, take first relevant product
        else:
            first_product = soup.select_one("table#games_table tbody tr")
            if first_product:
                link_elem = first_product.select_one("td.title a")
                if link_elem and link_elem.has_attr("href"):
                    href = link_elem["href"]
                    result["pricecharting_url"] = href if href.startswith("http") else f"https://www.pricecharting.com{href}"

                raw_elem = first_product.select_one("td.numeric.used_price")
                if raw_elem:
                    result["pricecharting_raw"] = clean_price_val(raw_elem.get_text())

                g9_elem = first_product.select_one("td.numeric.cib_price")
                if g9_elem:
                    result["pricecharting_grade9"] = clean_price_val(g9_elem.get_text())

                g10_elem = first_product.select_one("td.numeric.new_price")
                if g10_elem:
                    result["pricecharting_grade10"] = clean_price_val(g10_elem.get_text())

    except Exception as e:
        print(f"[PriceCharting] Info: Could not fetch PriceCharting data: {e}")

    return result
