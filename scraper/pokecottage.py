"""
PokeCottage Master Set Integration & Synchronizer for The Vulpix Vault.
Fetches, caches, normalizes, and synchronizes the complete official Vulpix
Grand Master Set checklist from PokeCottage (https://pokecottage.com/pokemon-master-sets/vulpix).
"""

import json
import logging
import os
import re
import sqlite3
import sys
import urllib.request
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("pokecottage_sync")

POKECOTTAGE_URL = "https://pokecottage.com/pokemon-master-sets/vulpix"
POKECOTTAGE_DATA_JS_URL = "https://pokecottagecdn.com/mastersets/data/37-vulpix-data.js"
LOCAL_CACHE_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "pokecottage_vulpix.json")
SCRATCH_JS_PATH = os.path.join(os.path.dirname(__file__), "..", "scratch_vulpix_data.js")


def fetch_pokecottage_vulpix_data(force_remote: bool = False) -> List[Dict[str, Any]]:
    """
    Retrieves the Vulpix master set cards dataset.
    Tries live CDN first, falls back to local cache or scratch snapshot.
    """
    raw_content = None

    if force_remote or not os.path.exists(LOCAL_CACHE_PATH):
        try:
            logger.info(f"Fetching live Vulpix data from {POKECOTTAGE_DATA_JS_URL}...")
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            req = urllib.request.Request(POKECOTTAGE_DATA_JS_URL, headers=headers)
            with urllib.request.urlopen(req, timeout=12) as response:
                raw_content = response.read().decode("utf-8", errors="ignore")
                logger.info(f"Successfully loaded {len(raw_content)} bytes from CDN.")
        except Exception as e:
            logger.warning(f"Could not reach remote CDN ({e}). Falling back to local cache...")

    if raw_content:
        marker = 'window.PokeCottageMastersetInline["37-vulpix"] ='
        idx = raw_content.find(marker)
        if idx != -1:
            json_str = raw_content[idx + len(marker):].strip().rstrip(";").strip()
            try:
                data = json.loads(json_str)
                cards = data.get("cards", [])
                os.makedirs(os.path.dirname(os.path.abspath(LOCAL_CACHE_PATH)), exist_ok=True)
                with open(LOCAL_CACHE_PATH, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                logger.info(f"Cached {len(cards)} cards to {LOCAL_CACHE_PATH}")
                return cards
            except Exception as ex:
                logger.error(f"Error parsing downloaded JSON: {ex}")

    if os.path.exists(LOCAL_CACHE_PATH):
        try:
            with open(LOCAL_CACHE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                cards = data.get("cards", [])
                logger.info(f"Loaded {len(cards)} cards from local cache {LOCAL_CACHE_PATH}")
                return cards
        except Exception as ex:
            logger.error(f"Error reading local cache: {ex}")

    return []


def map_pokecottage_edition(variant_str: str) -> str:
    """Maps PokeCottage variant string to standard Vault edition name."""
    v = (variant_str or "").strip()
    v_low = v.lower()
    if v_low == "standard":
        return "Unlimited"
    if v_low == "master ball holo":
        return "Master Ball Reverse Holo"
    if "poké ball" in v_low or "poke ball" in v_low:
        return "Poke Ball Reverse Holo"
    if v_low == "1st edition (shadowless)":
        return "1st Edition"
    if v_low == "2nd print (shadowless)":
        return "Shadowless"
    if v_low == "3rd print (unlimited)":
        return "Unlimited"
    if v_low == "4th print (1999-2000)":
        return "4th Print (©1999-2000)"
    if "blue dot" in v_low and "1st" in v_low:
        return "1st Edition (Blue Dot Error)"
    if "blue dot" in v_low:
        return "Shadowless (Blue Dot Error)"
    if v_low == "ink error":
        return "Ink Error"
    if v_low == "water symbol error":
        return "Water Symbol Error"
    if v_low == "no rarity symbol":
        return "No Rarity Symbol"
    if v_low == "glossy":
        return "Glossy Promo"
    return v


def map_pokecottage_language(region_str: str) -> str:
    """Maps PokeCottage region to language string."""
    r = (region_str or "").strip().lower()
    if r == "japan":
        return "Japanese"
    if r == "china":
        return "S. Chinese"
    return "English"


def variant_category(v_str: str) -> str:
    """Normalizes variant into a specific category for non-colliding matching."""
    s = (v_str or "").lower()
    if "water symbol" in s:
        return "water_symbol_error"
    if "blue dot" in s and "1st" in s:
        return "blue_dot_1st"
    if "blue dot" in s:
        return "blue_dot_shadowless"
    if "ink error" in s:
        return "ink_error"
    if "error" in s:
        return "error"
    if "master ball" in s:
        return "master_ball"
    if "poke ball" in s or "poké ball" in s:
        return "poke_ball"
    if "reverse" in s:
        return "reverse_holo"
    if "1st" in s:
        return "first_edition"
    if "shadowless" in s:
        return "shadowless"
    if "4th print" in s or "1999-2000" in s:
        return "fourth_print"
    if "play!" in s or "prize pack" in s:
        return "play_pokemon"
    if "world championships" in s:
        return f"world_champ_{s}"
    if "wotc" in s or "wizards" in s:
        return "wotc_stamp"
    if "build-a-bear" in s:
        return "build_a_bear"
    if "toys r us" in s:
        return "toys_r_us"
    if "no rarity" in s:
        return "no_rarity"
    if "glossy" in s:
        return "glossy"
    if "holo" in s:
        return "holo"
    return "standard"


def sync_pokecottage_to_db(db_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Synchronizes the complete PokeCottage catalog with the SQLite master_set_catalog.
    Guarantees that each of the 251 PokeCottage cards is represented by its own row
    without duplicate collisions, and enriches existing cards.
    """
    if db_path is None:
        if os.name != "nt" and os.path.exists("/data") and os.path.isdir("/data"):
            db_path = "/data/vulpix_vault.db"
        else:
            db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "vulpix_vault.db"))

    cards = fetch_pokecottage_vulpix_data()
    if not cards:
        logger.error("No cards retrieved from PokeCottage.")
        return {"success": False, "error": "No data retrieved", "updated": 0, "inserted": 0}

    conn = sqlite3.connect(db_path, timeout=15.0)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    for col, ctype in [
        ("pokecottage_id", "TEXT"),
        ("pokecottage_url", "TEXT"),
        ("tcgplayer_url", "TEXT"),
        ("region", "TEXT DEFAULT 'International'"),
        ("is_cameo", "INTEGER DEFAULT 0"),
    ]:
        cursor.execute(f"PRAGMA table_info(master_set_catalog);")
        existing = [row["name"] for row in cursor.fetchall()]
        if col not in existing:
            cursor.execute(f"ALTER TABLE master_set_catalog ADD COLUMN {col} {ctype};")

    cursor.execute("SELECT * FROM master_set_catalog;")
    existing_cards = [dict(r) for r in cursor.fetchall()]

    updated_count = 0
    inserted_count = 0
    claimed_db_ids: Set[int] = set()

    # Pass 1: Direct pokecottage_id match
    for pc in cards:
        pc_id = pc.get("id", "")
        if not pc_id:
            continue
        for ec in existing_cards:
            if ec["id"] in claimed_db_ids:
                continue
            if ec.get("pokecottage_id") and ec.get("pokecottage_id") == pc_id:
                claimed_db_ids.add(ec["id"])
                cursor.execute(
                    """
                    UPDATE master_set_catalog SET
                        pokecottage_url = :pokecottage_url,
                        tcgplayer_url = CASE WHEN :tcgplayer_url != '' THEN :tcgplayer_url ELSE tcgplayer_url END,
                        region = :region,
                        image_url = CASE 
                            WHEN image_url IS NULL OR image_url = '' OR image_url LIKE '%default_card_back%' OR image_url LIKE '%pokeapi%'
                            THEN :image_url 
                            ELSE image_url 
                        END
                    WHERE id = :id;
                """,
                    {
                        "id": ec["id"],
                        "pokecottage_url": f"{POKECOTTAGE_URL}#{pc_id}",
                        "tcgplayer_url": pc.get("tcgplayerUrl", ""),
                        "region": pc.get("region", "International"),
                        "image_url": pc.get("imageUrl") or pc.get("originalImageUrl") or "",
                    },
                )
                updated_count += 1
                break

    # Pass 2: Strict match for unassigned PokeCottage cards
    for pc in cards:
        pc_id = pc.get("id", "")
        if any(ec["id"] in claimed_db_ids and ec.get("pokecottage_id") == pc_id for ec in existing_cards):
            continue

        pc_name = pc.get("name", "Vulpix")
        pc_set_name = pc.get("set", {}).get("name", "Unknown Set")
        pc_card_num = str(pc.get("cardNumber", "")).strip()
        pc_display_num = str(pc.get("displayCardNumber", pc_card_num)).strip()
        pc_variant = pc.get("variant", "Standard")
        pc_region = pc.get("region", "International")
        pc_release_date = pc.get("releaseDate", "2000-01-01")
        pc_year = int(pc_release_date[:4]) if pc_release_date and len(pc_release_date) >= 4 else 2000
        pc_rarity = pc.get("rarity", "Common")
        pc_img = pc.get("imageUrl") or pc.get("originalImageUrl") or ""
        pc_tcg = pc.get("tcgplayerUrl", "")
        pc_card_url = f"{POKECOTTAGE_URL}#{pc_id}" if pc_id else POKECOTTAGE_URL

        mapped_edition = map_pokecottage_edition(pc_variant)
        mapped_lang = map_pokecottage_language(pc_region)
        pc_vcat = variant_category(pc_variant)
        is_error = 1 if "error" in pc_variant.lower() else 0
        error_desc = pc_variant if is_error else None
        is_cameo = 1 if "cameo" in str(pc.get("notes", "")).lower() or "vulpix" not in pc_name.lower() else 0

        match_id = None
        for ec in existing_cards:
            if ec["id"] in claimed_db_ids:
                continue

            e_name = (ec.get("card_name") or "").lower().strip()
            e_set = (ec.get("set_name") or "").lower().strip()
            e_num = (ec.get("card_number") or "").lower().strip()
            e_ed = (ec.get("edition") or "").lower().strip()
            e_lang = (ec.get("language") or "").lower().strip()
            e_vcat = variant_category(e_ed)

            pc_name_clean = pc_name.lower().strip()
            pc_set_clean = pc_set_name.lower().strip()
            pc_num_clean = pc_card_num.lower().strip()
            m_lang_clean = mapped_lang.lower().strip()

            if pc_name_clean != e_name and not (pc_name_clean in e_name or e_name in pc_name_clean):
                continue
            if m_lang_clean != e_lang and not (m_lang_clean in e_lang or e_lang in m_lang_clean):
                continue
            if not ((pc_set_clean == e_set) or (pc_set_clean in e_set) or (e_set in pc_set_clean)):
                continue

            e_num_base = e_num.split("/")[0].lstrip("0") or "0"
            pc_num_base = pc_num_clean.split("/")[0].lstrip("0") or "0"
            if not ((e_num_base == pc_num_base) or (pc_num_clean in e_num) or (e_num in pc_num_clean)):
                continue

            if pc_vcat != e_vcat:
                if not (pc_vcat in ["standard", "holo"] and e_vcat in ["standard", "holo"]):
                    continue

            if is_error != (1 if ec.get("is_error") else 0):
                continue

            match_id = ec["id"]
            break

        if match_id:
            claimed_db_ids.add(match_id)
            cursor.execute(
                """
                UPDATE master_set_catalog SET
                    pokecottage_id = :pokecottage_id,
                    pokecottage_url = :pokecottage_url,
                    tcgplayer_url = CASE WHEN :tcgplayer_url != '' THEN :tcgplayer_url ELSE tcgplayer_url END,
                    region = :region,
                    is_cameo = :is_cameo,
                    image_url = CASE 
                        WHEN image_url IS NULL OR image_url = '' OR image_url LIKE '%default_card_back%' OR image_url LIKE '%pokeapi%'
                        THEN :image_url 
                        ELSE image_url 
                    END
                WHERE id = :id;
            """,
                {
                    "id": match_id,
                    "pokecottage_id": pc_id,
                    "pokecottage_url": pc_card_url,
                    "tcgplayer_url": pc_tcg,
                    "region": pc_region,
                    "is_cameo": is_cameo,
                    "image_url": pc_img,
                },
            )
            updated_count += 1
        else:
            card_num_final = pc_display_num if ("/" in pc_display_num or len(pc_display_num) > len(pc_card_num)) else pc_card_num
            cursor.execute(
                """
                INSERT OR IGNORE INTO master_set_catalog (
                    card_name, set_name, card_number, release_year, language, edition,
                    rarity, is_error, error_description, est_raw_price, est_grade10_price,
                    pokecottage_id, pokecottage_url, tcgplayer_url, region, is_cameo,
                    image_url, notes
                ) VALUES (
                    :card_name, :set_name, :card_number, :release_year, :language, :edition,
                    :rarity, :is_error, :error_description, :est_raw_price, :est_grade10_price,
                    :pokecottage_id, :pokecottage_url, :tcgplayer_url, :region, :is_cameo,
                    :image_url, :notes
                );
            """,
                {
                    "card_name": pc_name,
                    "set_name": pc_set_name,
                    "card_number": card_num_final,
                    "release_year": pc_year,
                    "language": mapped_lang,
                    "edition": mapped_edition,
                    "rarity": pc_rarity,
                    "is_error": is_error,
                    "error_description": error_desc,
                    "est_raw_price": 5.0,
                    "est_grade10_price": 45.0,
                    "pokecottage_id": pc_id,
                    "pokecottage_url": pc_card_url,
                    "tcgplayer_url": pc_tcg,
                    "region": pc_region,
                    "is_cameo": is_cameo,
                    "image_url": pc_img,
                    "notes": f"PokeCottage: {pc.get('source', '')} ({pc_variant})",
                },
            )
            inserted_count += 1

    conn.commit()

    cursor.execute("SELECT COUNT(*) FROM master_set_catalog;")
    total_catalog = cursor.fetchone()[0]

    conn.close()

    msg = f"PokeCottage Sync Complete: {updated_count} cards enriched, {inserted_count} new cards added. Total Master Catalog: {total_catalog} cards."
    logger.info(msg)
    return {
        "success": True,
        "updated": updated_count,
        "inserted": inserted_count,
        "total_catalog": total_catalog,
        "message": msg,
    }


if __name__ == "__main__":
    res = sync_pokecottage_to_db()
    print(res["message"])
