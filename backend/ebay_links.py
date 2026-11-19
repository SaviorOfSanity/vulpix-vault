"""Targeted external verification & comps URL generators (eBay Active, eBay Sold, PriceCharting, TCGPlayer)."""

from __future__ import annotations

import re
import urllib.parse
from typing import Dict


def _build_query(
    card_name: str,
    set_name: str = "",
    card_number: str = "",
    edition: str = "",
    language: str = "English",
) -> str:
    parts = [card_name]
    clean_set = re.sub(r"\([0-9]{4}\)", "", set_name or "").strip()
    if clean_set and clean_set.lower() not in ("unknown set", "promo", ""):
        parts.append(clean_set)
    clean_num = (card_number or "").replace("No Number", "").strip()
    if clean_num:
        parts.append(clean_num)
    ed_low = (edition or "").lower()
    if edition and ed_low not in ("unlimited", "standard", "normal", ""):
        parts.append(edition)
    if language and language.lower() not in ("english", ""):
        parts.append(language)
    return " ".join(parts)


def get_verification_links(
    card_name: str,
    set_name: str = "",
    card_number: str = "",
    edition: str = "",
    language: str = "English",
    pricecharting_url: str = "",
    tcgplayer_url: str = "",
) -> Dict[str, str]:
    q = _build_query(card_name, set_name, card_number, edition, language)
    q_enc = urllib.parse.quote_plus(f"pokemon {q}")

    ebay_active = f"https://www.ebay.com/sch/i.html?_nkw={q_enc}&_sacat=0&_sop=1"
    ebay_sold = f"https://www.ebay.com/sch/i.html?_nkw={q_enc}&LH_Complete=1&LH_Sold=1&_sop=13"
    pc_url = pricecharting_url or f"https://www.pricecharting.com/search-products?q={q_enc}&type=prices"
    tcg_url = tcgplayer_url or f"https://www.tcgplayer.com/search/pokemon/product?productLineName=pokemon&q={urllib.parse.quote_plus(q)}"

    return {
        "ebay_active_url": ebay_active,
        "ebay_sold_url": ebay_sold,
        "pricecharting_url": pc_url,
        "tcgplayer_url": tcg_url,
    }
