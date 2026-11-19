"""
Real multi-source market pricing engine for The Vulpix Vault v2.
- NEVER writes fake $2/$45 or $5/$45 placeholders.
- Sources:
  1. PriceCharting live fetch (Ungraded / Raw, Grade 9, PSA 10 + direct product URL)
  2. TCGdex API v2 (live TCGPlayer USD + Cardmarket EUR raw variant pricing)
  3. Manual user overrides (protected by price_manual_lock=1)
"""

from __future__ import annotations

import asyncio
import re
import urllib.parse
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

import httpx
from bs4 import BeautifulSoup

from backend.catalog_builder import EUR_TO_USD, TCGDEX_BASE, TCGDEX_LANG_CODES, _extract_tcgdex_price
from backend.db import get_conn

PC_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def _parse_usd(text: str) -> Optional[float]:
    if not text:
        return None
    m = re.search(r"\$\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)", text)
    if not m:
        return None
    try:
        val = float(m.group(1).replace(",", ""))
        return round(val, 2) if val > 0 else None
    except ValueError:
        return None


def _build_pricecharting_query(card: Dict[str, Any]) -> str:
    parts = ["pokemon"]
    lang = (card.get("language") or "English").strip()
    if lang.lower() not in ("english", ""):
        parts.append("japanese" if lang.lower() == "japanese" else lang)

    parts.append(card.get("card_name") or "Vulpix")
    set_name = re.sub(r"\([0-9]{4}\)", "", card.get("set_name") or "").strip()
    if set_name and set_name.lower() not in ("promo", "unknown set"):
        # PriceCharting uses "Neo Destiny" even for Japanese Darkness and to Light
        if "darkness, and to light" in set_name.lower():
            parts.append("Neo Destiny")
        elif set_name.lower() == "expansion pack" and lang.lower() == "japanese":
            parts.append("Base Set")
        else:
            parts.append(set_name)

    base_num = str(card.get("base_number") or "").strip()
    cnum = str(card.get("card_number") or "").strip()
    if "/" in cnum and any(k in cnum.lower() for k in ("sm-p", "xy-p", "sv-p", "s-p")):
        parts.append(cnum)
    elif base_num and base_num != "0":
        parts.append(base_num)

    vk = (card.get("variant_key") or "").lower()
    ed = (card.get("edition") or "").lower()
    if vk == "1st_edition" or "1st" in ed:
        parts.append("1st edition")
    elif vk == "shadowless":
        parts.append("shadowless")
    elif vk == "no_rarity":
        parts.append("no rarity")
    elif vk == "master_ball":
        parts.append("master ball")
    elif vk == "poke_ball":
        parts.append("poke ball")
    elif vk == "reverse_holo":
        parts.append("reverse holo")
    elif vk == "w_stamp":
        parts.append("w stamp")

    return " ".join(parts)


def _score_pc_candidate(title: str, console: str, card: Dict[str, Any]) -> int:
    """Strictly verifies a PriceCharting search result matches the card's name, language, number, and variant."""
    hay = f"{title} {console}".lower()
    if "vulpix" not in hay and "rokon" not in hay:
        return -100

    score = 0
    cname = (card.get("card_name") or "").lower()
    for sub in ("alolan", "brock", "blaine", "vstar", "poncho"):
        if (sub in cname) != (sub in hay):
            return -50

    lang = (card.get("language") or "English").lower()
    if lang == "japanese":
        if "japanese" not in hay:
            return -40
        score += 10
    elif lang == "english":
        if any(f in hay for f in ("japanese", "chinese", "korean", "german", "french", "italian", "spanish")):
            return -40
        score += 10
    else:
        if lang.split()[-1] not in hay:
            return -30
        score += 10

    base_num = str(card.get("base_number") or "").strip()
    if base_num and re.search(rf"(?:#|no\.?\s*|0*){re.escape(base_num)}\b", hay):
        score += 15

    # Set-name keyword check (prevent matching wrong expansion with same card number)
    set_raw = (card.get("set_name") or "").lower()
    if "base set 2" in set_raw:
        if "base set 2" not in hay:
            return -45
    elif "base set 2" in hay:
        return -45

    if "darkness, and to light" in set_raw:
        set_words = ["neo", "destiny"]
    elif set_raw == "expansion pack" and lang == "japanese":
        set_words = ["base"]
    else:
        set_words = [w for w in re.findall(r"[a-z0-9]+", set_raw) if len(w) > 2 and w not in ("the", "and", "set", "pack", "pokemon")]
    if set_words:
        if any(w in hay for w in set_words):
            score += 12
        else:
            return -40

    vk = (card.get("variant_key") or "").lower()
    if vk == "1st_edition":
        if "1st" not in hay and "first" not in hay:
            return -50
        score += 20
    elif vk == "shadowless":
        if "shadowless" not in hay or "1st" in hay:
            return -50
        score += 20
    elif vk == "master_ball":
        if "master ball" not in hay:
            return -50
        score += 25
    elif vk == "poke_ball":
        if "poke ball" not in hay and "pokeball" not in hay:
            return -50
        score += 20
    elif vk == "reverse_holo":
        if "reverse" not in hay:
            return -50
        score += 18
    elif vk == "no_rarity":
        if "no rarity" not in hay:
            return -50
        score += 25
    elif vk == "w_stamp":
        if "w stamp" not in hay and "w-stamp" not in hay:
            return -50
        score += 25
    elif vk == "unlimited":
        if any(bad in hay for bad in ("1st edition", "shadowless", "reverse holo", "master ball", "poke ball", "no rarity", "w stamp", "staff", "prerelease")):
            return -50
        score += 10

    return score


def _extract_product_page_prices(soup: BeautifulSoup) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """Extracts (raw, grade9, psa10) from a PriceCharting individual product page."""
    raw = None
    g9 = None
    g10 = None

    # PriceCharting product page DOM IDs for Pokémon TCG:
    # #used_price = Ungraded, #graded_price / #grade9_price = Grade 9, #manual_only_price / #psa10_price = PSA 10
    for sel in ("#used_price .price", "#ungraded_price .price", "td#used_price span.price"):
        el = soup.select_one(sel)
        if el:
            raw = _parse_usd(el.get_text(" ", strip=True))
            if raw:
                break

    for sel in ("#graded_price .price", "#grade9_price .price", "td#graded_price span.price"):
        el = soup.select_one(sel)
        if el:
            g9 = _parse_usd(el.get_text(" ", strip=True))
            if g9:
                break

    for sel in ("#manual_only_price .price", "#psa10_price .price", "td#manual_only_price span.price"):
        el = soup.select_one(sel)
        if el:
            g10 = _parse_usd(el.get_text(" ", strip=True))
            if g10:
                break

    return raw, g9, g10


async def fetch_pricecharting_live(client: httpx.AsyncClient, card: Dict[str, Any]) -> Dict[str, Any]:
    """Queries PriceCharting for live Ungraded, Grade 9, and PSA 10 market prices."""
    result: Dict[str, Any] = {
        "price_raw": None,
        "price_grade9": None,
        "price_grade10": None,
        "pricecharting_url": card.get("pricecharting_url") or "",
        "source": None,
    }

    existing_pc_url = (card.get("pricecharting_url") or "").strip()
    try:
        # 1. If we already have a verified direct product URL, fetch it directly!
        if existing_pc_url and "/game/pokemon" in existing_pc_url:
            resp = await client.get(existing_pc_url)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                raw, g9, g10 = _extract_product_page_prices(soup)
                if any(v is not None for v in (raw, g9, g10)):
                    result.update({
                        "price_raw": raw,
                        "price_grade9": g9,
                        "price_grade10": g10,
                        "pricecharting_url": str(resp.url),
                        "source": "PriceCharting",
                    })
                    return result

        # 2. Otherwise search PriceCharting cleanly and verify best match
        q = _build_pricecharting_query(card)
        search_url = f"https://www.pricecharting.com/search-products?q={urllib.parse.quote_plus(q)}&type=prices"
        resp = await client.get(search_url)
        if resp.status_code != 200:
            return result

        soup = BeautifulSoup(resp.text, "html.parser")
        if "/game/pokemon" in str(resp.url):
            raw, g9, g10 = _extract_product_page_prices(soup)
            if any(v is not None for v in (raw, g9, g10)):
                result.update({
                    "price_raw": raw,
                    "price_grade9": g9,
                    "price_grade10": g10,
                    "pricecharting_url": str(resp.url),
                    "source": "PriceCharting",
                })
            return result

        # Parse search results table and pick highest-scoring verified row
        best_score = 5  # Require minimum positive verification score
        best_row = None
        for tr in soup.select("table#games_table tbody tr"):
            title_el = tr.select_one("td.title a")
            console_el = tr.select_one("td.console")
            if not title_el:
                continue
            t_txt = title_el.get_text(" ", strip=True)
            c_txt = console_el.get_text(" ", strip=True) if console_el else ""
            sc = _score_pc_candidate(t_txt, c_txt, card)
            if sc > best_score:
                best_score = sc
                best_row = tr

        if best_row is not None:
            link_el = best_row.select_one("td.title a")
            href = link_el.get("href", "") if link_el else ""
            prod_url = href if href.startswith("http") else (f"https://www.pricecharting.com{href}" if href else "")

            # Fetch product page for exact Grade 9 & PSA 10 slots
            if prod_url and "/game/pokemon" in prod_url:
                p_resp = await client.get(prod_url)
                if p_resp.status_code == 200:
                    p_soup = BeautifulSoup(p_resp.text, "html.parser")
                    raw, g9, g10 = _extract_product_page_prices(p_soup)
                    if any(v is not None for v in (raw, g9, g10)):
                        result.update({
                            "price_raw": raw,
                            "price_grade9": g9,
                            "price_grade10": g10,
                            "pricecharting_url": prod_url,
                            "source": "PriceCharting",
                        })
                        return result

            # Fallback to search row table prices
            raw_el = best_row.select_one("td.price.used_price, td.numeric.used_price")
            g9_el = best_row.select_one("td.price.cib_price, td.numeric.cib_price")
            g10_el = best_row.select_one("td.price.new_price, td.numeric.new_price")
            raw = _parse_usd(raw_el.get_text(" ", strip=True)) if raw_el else None
            g9 = _parse_usd(g9_el.get_text(" ", strip=True)) if g9_el else None
            g10 = _parse_usd(g10_el.get_text(" ", strip=True)) if g10_el else None
            if any(v is not None for v in (raw, g9, g10)):
                result.update({
                    "price_raw": raw,
                    "price_grade9": g9,
                    "price_grade10": g10,
                    "pricecharting_url": prod_url,
                    "source": "PriceCharting",
                })
    except Exception:
        pass

    return result


async def fetch_tcgdex_live_price(client: httpx.AsyncClient, card: Dict[str, Any]) -> Tuple[Optional[float], Optional[str], Optional[str]]:
    """Fetches real-time TCGPlayer (USD) or Cardmarket (EUR->USD) raw price from TCGdex."""
    tcgdex_id = (card.get("tcgdex_id") or "").strip()
    lang_code = TCGDEX_LANG_CODES.get(card.get("language") or "English", "en")

    try:
        if tcgdex_id and ":" in tcgdex_id:
            lc, cid = tcgdex_id.split(":", 1)
            resp = await client.get(f"{TCGDEX_BASE}/{lc}/cards/{cid}")
            if resp.status_code == 200:
                p, src = _extract_tcgdex_price(resp.json(), card.get("variant_key") or "unlimited")
                return p, src, tcgdex_id

        # Attempt lookup via set_id + base_number on TCGdex
        set_id = (card.get("set_id") or "").strip().lower()
        base_num = (card.get("base_number") or "").strip()
        if set_id and base_num and not set_id.startswith("jpn_") and not set_id.startswith("scn_"):
            candidate_id = f"{set_id}-{base_num}"
            resp = await client.get(f"{TCGDEX_BASE}/{lang_code}/cards/{candidate_id}")
            if resp.status_code == 200:
                p, src = _extract_tcgdex_price(resp.json(), card.get("variant_key") or "unlimited")
                return p, src, f"{lang_code}:{candidate_id}"
    except Exception:
        pass

    return None, None, None


async def refresh_single_card_price(catalog_key: str, db_path: Optional[str] = None, force: bool = False) -> Dict[str, Any]:
    """Refreshes real live pricing for one card (PriceCharting + TCGdex fallback) and records price_history."""
    with get_conn(db_path) as conn:
        row = conn.execute("SELECT * FROM catalog_cards WHERE catalog_key = ?;", (catalog_key,)).fetchone()
        if not row:
            return {"updated": False, "error": "Card not found"}
        card = dict(row)

    if card.get("price_manual_lock") and not force:
        return {"updated": False, "skipped": True, "reason": "Manually locked"}

    async with httpx.AsyncClient(timeout=12.0, follow_redirects=True, headers=PC_HEADERS) as client:
        pc_res = await fetch_pricecharting_live(client, card)
        tcg_raw, tcg_src, matched_tid = await fetch_tcgdex_live_price(client, card)

    price_raw = pc_res["price_raw"] if pc_res["price_raw"] is not None else tcg_raw
    price_g9 = pc_res["price_grade9"]
    price_g10 = pc_res["price_grade10"]
    source = pc_res["source"] or tcg_src

    if source is None:
        return {
            "updated": False,
            "catalog_key": catalog_key,
            "message": "No verified live price found on PriceCharting or TCGdex yet.",
        }

    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    with get_conn(db_path) as conn:
        conn.execute("""
            UPDATE catalog_cards
            SET price_raw = COALESCE(:raw, price_raw),
                price_grade9 = COALESCE(:g9, price_grade9),
                price_grade10 = COALESCE(:g10, price_grade10),
                price_source = :src,
                price_updated_at = :ts,
                pricecharting_url = CASE WHEN :pcurl != '' THEN :pcurl ELSE pricecharting_url END,
                tcgdex_id = CASE WHEN :tid != '' AND tcgdex_id = '' THEN :tid ELSE tcgdex_id END
            WHERE catalog_key = :ck;
        """, {
            "raw": price_raw,
            "g9": price_g9,
            "g10": price_g10,
            "src": source,
            "ts": now_iso,
            "pcurl": pc_res.get("pricecharting_url") or "",
            "tid": matched_tid or "",
            "ck": catalog_key,
        })
        conn.execute("""
            INSERT INTO price_history (catalog_key, price_raw, price_grade9, price_grade10, source)
            VALUES (?, ?, ?, ?, ?);
        """, (catalog_key, price_raw, price_g9, price_g10, source))

    return {
        "updated": True,
        "catalog_key": catalog_key,
        "price_raw": price_raw,
        "price_grade9": price_g9,
        "price_grade10": price_g10,
        "price_source": source,
        "price_updated_at": now_iso,
    }


async def refresh_catalog_prices_batch(
    only_unpriced: bool = True,
    limit: Optional[int] = None,
    progress_cb: Optional[Callable[[int, int, str], None]] = None,
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Batch live price refresh with polite throttling to avoid rate limits."""
    with get_conn(db_path) as conn:
        if only_unpriced:
            rows = conn.execute("""
                SELECT catalog_key, card_name, set_name FROM catalog_cards
                WHERE price_manual_lock = 0 AND (price_source IS NULL OR price_source = '')
                ORDER BY CASE WHEN language = 'English' THEN 0 WHEN language = 'Japanese' THEN 1 ELSE 2 END, release_year ASC;
            """).fetchall()
        else:
            rows = conn.execute("""
                SELECT catalog_key, card_name, set_name FROM catalog_cards
                WHERE price_manual_lock = 0
                ORDER BY CASE WHEN language = 'English' THEN 0 WHEN language = 'Japanese' THEN 1 ELSE 2 END, release_year ASC;
            """).fetchall()

    targets = [dict(r) for r in rows]
    if limit and limit > 0:
        targets = targets[:limit]

    total = len(targets)
    updated = 0
    not_found = 0

    for i, item in enumerate(targets, start=1):
        if progress_cb:
            progress_cb(i - 1, total, f"Pricing ({i}/{total}): {item['card_name']} — {item['set_name']}...")
        res = await refresh_single_card_price(item["catalog_key"], db_path=db_path)
        if res.get("updated"):
            updated += 1
        else:
            not_found += 1
        await asyncio.sleep(0.45)  # Polite throttle for PriceCharting / TCGdex

    if progress_cb:
        progress_cb(total, total, f"Price refresh complete: {updated} updated, {not_found} unpriced.")

    return {"total": total, "updated": updated, "not_found": not_found}
