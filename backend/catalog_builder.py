"""
Canonical Vulpix Master Set catalog compiler & multi-language TCGdex synchronizer.
- Single deterministic source of truth using stable string `catalog_key`s.
- Zero background cameos (Rumble/Scramble/Sapporo excluded); Vulpix-themed Poncho Pikachus INCLUDED.
- Supports all 14 official Pokémon TCG languages with authentic localized scans via TCGdex API v2.
"""

from __future__ import annotations

import csv
import json
import os
import re
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

import httpx

from backend.db import (
    get_cached_cards_dir,
    get_conn,
    get_data_dir,
    get_project_root,
    get_static_cards_dir,
)
from backend.error_annotations import get_visual_callouts
from backend.translations import translate_card_name, translate_set_name

POKECOTTAGE_DATA_JS_URL = "https://pokecottagecdn.com/mastersets/data/37-vulpix-data.js"
POKECOTTAGE_PAGE_URL = "https://pokecottage.com/pokemon-master-sets/vulpix"
TCGDEX_BASE = "https://api.tcgdex.net/v2"

# All 14 official TCGdex languages & their localized Vulpix search terms
TCGDEX_LANGUAGES: List[Tuple[str, str, str, List[str]]] = [
    # (tcgdex_code, display_language, region, fallback_search_names)
    ("en", "English", "International", ["Vulpix"]),
    ("ja", "Japanese", "Japan", ["ロコン"]),
    ("fr", "French", "Europe", ["Goupix"]),
    ("de", "German", "Europe", ["Vulpix"]),
    ("it", "Italian", "Europe", ["Vulpix"]),
    ("es", "Spanish", "Europe", ["Vulpix"]),
    ("pt", "Portuguese", "South America", ["Vulpix"]),
    ("nl", "Dutch", "Europe", ["Vulpix"]),
    ("ko", "Korean", "Korea", ["식스테일"]),
    ("zh-tw", "T. Chinese", "Taiwan / HK", ["六尾"]),
    ("zh-cn", "S. Chinese", "China", ["六尾"]),
    ("id", "Indonesian", "Indonesia", ["Vulpix"]),
    ("th", "Thai", "Thailand", ["โรคอน"]),
    ("pl", "Polish", "Europe", ["Vulpix"]),
]

# Known TCGdex localized series/set mappings for baseline European vintage cards
TCGDEX_KNOWN_SET_PATHS: Dict[str, Tuple[str, str]] = {
    "base set": ("base", "base1"),
    "neo destiny": ("neo", "neo4"),
    "expedition base set": ("ecard", "ecard1"),
    "aquapolis": ("ecard", "ecard2"),
    "ex hidden legends": ("ex", "ex5"),
    "ex emerald": ("ex", "ex9"),
    "xy evolutions": ("xy", "xy12"),
}

TCGDEX_LANG_CODES = {
    "English": "en",
    "Japanese": "ja",
    "French": "fr",
    "German": "de",
    "Italian": "it",
    "Spanish": "es",
    "Portuguese": "pt",
    "Dutch": "nl",
    "Korean": "ko",
    "T. Chinese": "zh-tw",
    "S. Chinese": "zh-cn",
    "Indonesian": "id",
    "Thai": "th",
    "Polish": "pl",
}

EUR_TO_USD = 1.09


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")


def extract_base_number(card_number: str) -> str:
    s = str(card_number or "").strip()
    if "/" in s:
        s = s.split("/")[0].strip()
    m = re.search(r"([A-Za-z]*[0-9]+)", s)
    if m:
        val = m.group(1)
        return str(int(val)) if val.isdigit() else val.lower()
    return s.lower()


def classify_variant(variant_str: str, rarity: str = "", card_name: str = "") -> Tuple[str, str, int, str]:
    """
    Maps raw variant/edition strings into:
      (clean_edition_label, variant_key, is_error, error_description)
    """
    raw = (variant_str or "").strip()
    low = raw.lower()
    rar_low = (rarity or "").lower()

    if "blue dot" in low:
        ed = "1st Ed Shadowless (Blue Dot Error)" if "1st" in low else "Shadowless (Blue Dot Error)"
        return ed, "error", 1, "Blue Dot Error: Distinct stray blue printer ink dot on the card surface."
    if "water symbol" in low:
        return "Water Symbol Error", "error", 1, "Water Symbol Error: Documented Base Set weakness symbol ink anomaly."
    if "ink error" in low:
        return "Ink Error", "error", 1, "Ink Error: Documented Base Set ink smudge / registration print defect."
    if "grey stamp" in low:
        return "1st Edition (Grey Stamp Error)", "error", 1, "Grey Stamp Error: Faded grey 1st Edition stamp from low black ink."
    if "no rarity" in low:
        return "No Rarity Symbol (1st Print)", "no_rarity", 0, ""
    if "wotc" in low or "wizards" in low or "w-stamp" in low or "w stamp" in low:
        return "W-Stamp Promo", "w_stamp", 0, ""
    if "4th print" in low or "1999-2000" in low:
        return "4th Print (©1999-2000)", "4th_print", 0, ""
    if "1st edition (shadowless)" in low or ("1st" in low and "shadowless" in low):
        return "1st Edition (Shadowless)", "1st_edition", 0, ""
    if "shadowless" in low:
        return "Shadowless (2nd Print)", "shadowless", 0, ""
    if "master ball" in low:
        return "Master Ball Holo", "master_ball", 0, ""
    if "poké ball" in low or "poke ball" in low or "pokeball" in low:
        return "Poké Ball Holo", "poke_ball", 0, ""
    if "1st edition (reverse" in low or ("1st" in low and "reverse" in low):
        return "1st Edition Reverse Holo", "reverse_holo", 0, ""
    if "1st" in low or "first edition" in low:
        return "1st Edition", "1st_edition", 0, ""
    if "expansion stamp" in low:
        return "Expansion Stamp (Reverse Holo)", "stamp", 0, ""
    if "holiday calendar" in low or "snowflake" in low:
        return "Holiday Calendar (Snowflake Stamp)", "stamp", 0, ""
    if "play! pokémon" in low or "play! pokemon" in low or "prize pack" in low:
        return "Play! Pokémon Stamp", "stamp", 0, ""
    if any(k in low for k in ("build-a-bear", "toys r us", "tcg gym", "daiichi", "stamp")):
        return raw, "stamp", 0, ""
    if "reverse" in low:
        return "Reverse Holo", "reverse_holo", 0, ""
    if "rainbow" in low or "hyper rare" in rar_low or "rainbow" in rar_low:
        return "Rainbow Rare", "rainbow", 0, ""
    if "illustration rare" in rar_low or "art rare" in rar_low or "special art" in rar_low:
        return rarity or "Illustration Rare", "art_rare", 0, ""
    if "shiny" in rar_low or "shiny" in low:
        return "Shiny Holo", "holo", 0, ""
    if "cosmos holo" in low:
        return "Cosmos Holo", "holo", 0, ""
    if "holo" in low:
        return "Holo", "holo", 0, ""
    if "glossy" in low:
        return "Glossy Promo", "promo", 0, ""
    if "promo" in low or "promo" in rar_low:
        return raw if raw and low != "standard" else "Promo", "promo", 0, ""
    if "playing" in low:
        return "Playing Card", "playing_card", 0, ""
    if low in ("standard", "normal", "3rd print (unlimited)", "unlimited", "non-holo", ""):
        return "Unlimited", "unlimited", 0, ""
    # Deck / Serial code / World Championships / Specialty
    if "world" in low or "championship" in low:
        return raw, "promo", 0, ""
    return raw, "stamp" if any(k in low for k in ("deck", "kit", "gift")) else "unlimited", 0, ""


def _resolve_pokecottage_json_path() -> Optional[str]:
    candidates = [
        os.path.join(get_data_dir(), "pokecottage_vulpix.json"),
        os.path.join(get_project_root(), "data", "pokecottage_vulpix.json"),
    ]
    for p in candidates:
        if os.path.isfile(p):
            return p
    return None


def _upsert_catalog_card(cursor, card: Dict[str, Any]) -> None:
    """Idempotent upsert that preserves existing live/manual pricing and cached local images."""
    card.setdefault("native_name", "")
    card.setdefault("native_set_name", "")
    cursor.execute("""
        INSERT INTO catalog_cards (
            catalog_key, card_group_key, card_name, native_name, set_name, native_set_name, set_id, series,
            card_number, base_number, release_year, release_date, language, region,
            edition, variant_key, rarity, artist, is_error, error_description,
            visual_callouts, image_url, local_image, image_is_localized,
            pokecottage_id, tcgdex_id, pricecharting_url, tcgplayer_url, notes, source
        ) VALUES (
            :catalog_key, :card_group_key, :card_name, :native_name, :set_name, :native_set_name, :set_id, :series,
            :card_number, :base_number, :release_year, :release_date, :language, :region,
            :edition, :variant_key, :rarity, :artist, :is_error, :error_description,
            :visual_callouts, :image_url, :local_image, :image_is_localized,
            :pokecottage_id, :tcgdex_id, :pricecharting_url, :tcgplayer_url, :notes, :source
        )
        ON CONFLICT(catalog_key) DO UPDATE SET
            card_group_key = excluded.card_group_key,
            card_name = excluded.card_name,
            native_name = CASE WHEN excluded.native_name != '' THEN excluded.native_name ELSE catalog_cards.native_name END,
            set_name = excluded.set_name,
            native_set_name = CASE WHEN excluded.native_set_name != '' THEN excluded.native_set_name ELSE catalog_cards.native_set_name END,
            set_id = CASE WHEN excluded.set_id != '' THEN excluded.set_id ELSE catalog_cards.set_id END,
            series = CASE WHEN excluded.series != '' THEN excluded.series ELSE catalog_cards.series END,
            card_number = CASE WHEN excluded.card_number != '' THEN excluded.card_number ELSE catalog_cards.card_number END,
            base_number = excluded.base_number,
            release_year = excluded.release_year,
            release_date = CASE WHEN excluded.release_date != '' THEN excluded.release_date ELSE catalog_cards.release_date END,
            language = excluded.language,
            region = excluded.region,
            edition = excluded.edition,
            variant_key = excluded.variant_key,
            rarity = excluded.rarity,
            artist = CASE WHEN excluded.artist != '' THEN excluded.artist ELSE catalog_cards.artist END,
            is_error = excluded.is_error,
            error_description = excluded.error_description,
            visual_callouts = excluded.visual_callouts,
            image_url = CASE
                WHEN excluded.image_is_localized = 1 AND excluded.image_url != '' THEN excluded.image_url
                WHEN catalog_cards.image_url = '' THEN excluded.image_url
                ELSE catalog_cards.image_url
            END,
            local_image = CASE
                WHEN catalog_cards.local_image != '' THEN catalog_cards.local_image
                ELSE excluded.local_image
            END,
            image_is_localized = MAX(catalog_cards.image_is_localized, excluded.image_is_localized),
            pokecottage_id = CASE WHEN excluded.pokecottage_id != '' THEN excluded.pokecottage_id ELSE catalog_cards.pokecottage_id END,
            tcgdex_id = CASE WHEN excluded.tcgdex_id != '' THEN excluded.tcgdex_id ELSE catalog_cards.tcgdex_id END,
            pricecharting_url = CASE WHEN catalog_cards.pricecharting_url != '' THEN catalog_cards.pricecharting_url ELSE excluded.pricecharting_url END,
            tcgplayer_url = CASE WHEN excluded.tcgplayer_url != '' THEN excluded.tcgplayer_url ELSE catalog_cards.tcgplayer_url END,
            notes = CASE WHEN excluded.notes != '' THEN excluded.notes ELSE catalog_cards.notes END;
    """, card)


def seed_canonical_catalog(db_path: Optional[str] = None) -> Dict[str, int]:
    """
    Deterministically builds the clean Vulpix Master Set catalog from:
      1. data/pokecottage_vulpix.json (251 verified EN/JA/S.CN variants with authentic variant photos)
      2. backend/data/custom_cards.json (Poncho Pikachus, Grey Stamp Errors, Playing Cards, KR/ID promos)
      3. data/vulpix_master_set_cleaned.csv (Verified official EU/KR/T.CN language variants)
    """
    counts = {"pokecottage": 0, "custom": 0, "foreign_baseline": 0}
    static_dir = get_static_cards_dir()
    static_files = set(os.listdir(static_dir)) if os.path.isdir(static_dir) else set()

    with get_conn(db_path) as conn:
        c = conn.cursor()

        # 1. PokeCottage Canonical 251 variants
        pc_path = _resolve_pokecottage_json_path()
        if pc_path:
            with open(pc_path, "r", encoding="utf-8") as f:
                pc_cards = json.load(f).get("cards", [])

            for item in pc_cards:
                pc_id = item.get("id", "")
                if not pc_id:
                    continue
                region = item.get("region", "International")
                language = "Japanese" if region == "Japan" else ("S. Chinese" if region == "China" else "English")
                set_obj = item.get("set", {}) or {}
                set_name = set_obj.get("name", "Unknown Set")
                set_id = set_obj.get("id", "")
                series = set_obj.get("series", "")
                rel_date = item.get("releaseDate") or set_obj.get("releaseDate") or ""
                year = int(rel_date[:4]) if len(rel_date) >= 4 and rel_date[:4].isdigit() else 2000
                card_name = item.get("name", "Vulpix")
                card_num = str(item.get("displayCardNumber") or item.get("cardNumber") or "").strip()
                base_num = extract_base_number(str(item.get("cardNumber") or card_num))
                rarity = item.get("rarity") or "Common"
                artist = (item.get("artist") or {}).get("name") or ""
                raw_variant = item.get("variant") or "Standard"
                edition, variant_key, is_error, err_desc = classify_variant(raw_variant, rarity, card_name)
                img_url = item.get("imageUrl") or item.get("originalImageUrl") or ""
                tcg_url = item.get("tcgplayerUrl") or ""

                callouts = get_visual_callouts(
                    set_name=set_name,
                    language=language,
                    edition=edition,
                    variant_key=variant_key,
                    is_error=bool(is_error),
                    error_description=err_desc,
                    pokecottage_id=pc_id,
                )

                # Clean educational collector note (never "Variant: Non-Holo")
                if is_error and err_desc:
                    note = err_desc
                elif variant_key == "w_stamp":
                    note = 'Distributed August 2000 in TopDeck Magazine (Issue #9) with gold foil Wizards "W" stamp.'
                elif variant_key == "no_rarity":
                    note = "Original October 1996 Japanese Expansion Pack first printing without the bottom-right ● rarity symbol."
                elif variant_key == "4th_print":
                    note = 'Late 1999–2000 UK/4th Base Set print run — the ONLY English Base Set Vulpix correcting "HP 50" to "50 HP".'
                elif variant_key == "master_ball":
                    note = "Scarce Japanese 151 Master Ball mirror-holo reverse (only 1 Master Ball card per booster box)."
                else:
                    note = f"{language} {set_name} ({year})" + (f" • Illustrated by {artist}." if artist else ".")

                card_record = {
                    "catalog_key": f"pc:{pc_id}",
                    "card_group_key": item.get("cardId") or f"{slugify(set_name)}|{base_num}|{slugify(language)}",
                    "card_name": card_name,
                    "set_name": set_name,
                    "set_id": set_id,
                    "series": series,
                    "card_number": card_num,
                    "base_number": base_num,
                    "release_year": year,
                    "release_date": rel_date,
                    "language": language,
                    "region": region,
                    "edition": edition,
                    "variant_key": variant_key,
                    "rarity": rarity,
                    "artist": artist,
                    "is_error": is_error,
                    "error_description": err_desc,
                    "visual_callouts": json.dumps(callouts),
                    "image_url": img_url,
                    "local_image": "",
                    "image_is_localized": 1,
                    "pokecottage_id": pc_id,
                    "tcgdex_id": "",
                    "pricecharting_url": "",
                    "tcgplayer_url": tcg_url,
                    "notes": note,
                    "source": "pokecottage",
                }
                _upsert_catalog_card(c, card_record)
                counts["pokecottage"] += 1

        # 2. Curated Custom Vulpix Additions (Poncho Pikachus, Grey Stamp Errors, Playing Cards, KR/ID Promos)
        custom_path = os.path.join(os.path.dirname(__file__), "data", "custom_cards.json")
        if os.path.isfile(custom_path):
            with open(custom_path, "r", encoding="utf-8") as f:
                custom_cards = json.load(f)
            for item in custom_cards:
                local_img = item.get("local_image", "")
                if local_img and local_img not in static_files:
                    local_img = ""
                callouts = get_visual_callouts(
                    set_name=item.get("set_name", ""),
                    language=item.get("language", "English"),
                    edition=item.get("edition", "Unlimited"),
                    variant_key=item.get("variant_key", "unlimited"),
                    is_error=bool(item.get("is_error")),
                    error_description=item.get("error_description", ""),
                )
                record = {
                    "catalog_key": item["catalog_key"],
                    "card_group_key": item.get("card_group_key", item["catalog_key"]),
                    "card_name": item["card_name"],
                    "set_name": item["set_name"],
                    "set_id": item.get("set_id", ""),
                    "series": item.get("series", ""),
                    "card_number": item.get("card_number", ""),
                    "base_number": item.get("base_number", extract_base_number(item.get("card_number", ""))),
                    "release_year": int(item.get("release_year", 2000)),
                    "release_date": item.get("release_date", ""),
                    "language": item.get("language", "English"),
                    "region": item.get("region", "International"),
                    "edition": item.get("edition", "Unlimited"),
                    "variant_key": item.get("variant_key", "unlimited"),
                    "rarity": item.get("rarity", "Common"),
                    "artist": item.get("artist", ""),
                    "is_error": int(item.get("is_error", 0)),
                    "error_description": item.get("error_description", ""),
                    "visual_callouts": json.dumps(callouts),
                    "image_url": item.get("image_url", ""),
                    "local_image": local_img,
                    "image_is_localized": int(item.get("image_is_localized", 1)),
                    "pokecottage_id": "",
                    "tcgdex_id": item.get("tcgdex_id", ""),
                    "pricecharting_url": item.get("pricecharting_url", ""),
                    "tcgplayer_url": item.get("tcgplayer_url", ""),
                    "notes": item.get("notes", ""),
                    "source": "custom",
                }
                _upsert_catalog_card(c, record)
                counts["custom"] += 1

        # 3. Official Non-EN/JP/S.CN Baseline Language Variants (from curated cleaned CSV)
        csv_path = os.path.join(get_project_root(), "data", "vulpix_master_set_cleaned.csv")
        if os.path.isfile(csv_path):
            with open(csv_path, "r", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))

            for r in rows:
                lang = (r.get("Language") or "").strip()
                if lang in ("English", "Japanese", "S. Chinese", ""):
                    continue
                set_name = (r.get("Set / Source") or "").strip()
                # Skip items already cleanly defined in custom_cards.json
                if set_name in ("Playing Cards", "20th Anniversary", "Promo", "Random Constructed Half Decks"):
                    continue
                card_num = (r.get("Card #") or "").strip()
                if set_name == "Neo Destiny" and card_num.startswith("90"):
                    card_num = "91/105"  # Correct legacy CSV typo
                base_num = extract_base_number(card_num)
                year_str = (r.get("Release Date") or "2000").strip()
                year = int(year_str[:4]) if year_str[:4].isdigit() else 2000
                is_1st = (r.get("1st Ed?") or "").strip().lower() == "yes"
                raw_var = (r.get("Variant / Stamp / Code") or "").strip()

                if is_1st and "1999-2000" in raw_var:
                    ed_label, vk = "1st Edition (©1999-2000)", "1st_edition"
                elif is_1st:
                    ed_label, vk = "1st Edition", "1st_edition"
                elif "1999-2000" in raw_var:
                    ed_label, vk = "4th Print (©1999-2000)", "4th_print"
                elif "©1999" in raw_var:
                    ed_label, vk = "Unlimited (©1999)", "unlimited"
                elif "reverse" in raw_var.lower():
                    ed_label, vk = "Reverse Holo", "reverse_holo"
                elif raw_var and raw_var.lower() not in ("non-holo", "standard"):
                    ed_label, vk, _, _ = classify_variant(raw_var)
                else:
                    ed_label, vk = "Unlimited", "unlimited"

                lang_code = TCGDEX_LANG_CODES.get(lang, slugify(lang))
                set_slug = slugify(set_name)
                ed_slug = slugify(ed_label)
                catalog_key = f"lang:{lang_code}:{set_slug}-{base_num}:{ed_slug}"

                # Use real TCGdex localized scan when language/set is on TCGdex CDN!
                img_url = ""
                tcgdex_id = ""
                is_localized = 0
                set_path = TCGDEX_KNOWN_SET_PATHS.get(set_name.lower())
                if set_path and lang_code in ("fr", "de", "it", "es", "pt"):
                    serie_id, s_id = set_path
                    img_url = f"https://assets.tcgdex.net/{lang_code}/{serie_id}/{s_id}/{base_num}/high.webp"
                    tcgdex_id = f"{lang_code}:{s_id}-{base_num}"
                    is_localized = 1
                else:
                    # Reference artwork clearly tagged as image_is_localized = 0 until synced
                    ref_map = {
                        "base set": "/static/cards/vulpix_base_set_68_102.jpg",
                        "neo destiny": "/static/cards/vulpix_neo_destiny_90_105.jpg",
                        "expedition base set": "/static/cards/vulpix-expedition-base-set-136-165.jpg",
                        "aquapolis": "/static/cards/vulpix-aquapolis-116-147.jpg",
                        "ex hidden legends": "/static/cards/ex_hidden_legends_81.jpg",
                        "ex emerald": "/static/cards/ex_emerald_72.jpg",
                        "ex trainer kit 2": "/static/cards/vulpix-ex-trainer-kit-2-minun-7-12.jpg",
                        "xy evolutions": "/static/cards/vulpix-evolutions-14-108.jpg",
                    }
                    img_url = ref_map.get(set_name.lower(), "/static/cards/vulpix_base_set_68_102.jpg")
                    is_localized = 0

                region = "Europe" if lang in ("German", "French", "Italian", "Spanish", "Dutch", "Polish") else (
                    "South America" if lang == "Portuguese" else (
                        "Korea" if lang == "Korean" else "Taiwan / HK"
                    )
                )
                artist = "Masako Yamashita" if set_name == "Neo Destiny" else (
                    "Midori Harada" if set_name in ("EX Hidden Legends", "EX Emerald") else "Ken Sugimori"
                )
                callouts = get_visual_callouts(
                    set_name=set_name,
                    language=lang,
                    edition=ed_label,
                    variant_key=vk,
                )
                record = {
                    "catalog_key": catalog_key,
                    "card_group_key": f"{set_slug}-{base_num}-{lang_code}",
                    "card_name": "Vulpix",
                    "set_name": set_name,
                    "set_id": set_path[1] if set_path else set_slug,
                    "series": set_path[0].upper() if set_path else "",
                    "card_number": card_num,
                    "base_number": base_num,
                    "release_year": year,
                    "release_date": f"{year}-01-01",
                    "language": lang,
                    "region": region,
                    "edition": ed_label,
                    "variant_key": vk,
                    "rarity": "Common",
                    "artist": artist,
                    "is_error": 0,
                    "error_description": "",
                    "visual_callouts": json.dumps(callouts),
                    "image_url": img_url,
                    "local_image": "",
                    "image_is_localized": is_localized,
                    "pokecottage_id": "",
                    "tcgdex_id": tcgdex_id,
                    "pricecharting_url": "",
                    "tcgplayer_url": "",
                    "notes": f"Official {lang} {set_name} ({year}) release.",
                    "source": "csv_lang",
                }
                _upsert_catalog_card(c, record)
                counts["foreign_baseline"] += 1

    return counts


async def refresh_pokecottage_remote(
    progress_cb: Optional[Callable[[int, int, str], None]] = None,
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Downloads latest official PokeCottage Vulpix dataset and re-seeds deterministically."""
    if progress_cb:
        progress_cb(0, 2, "Downloading latest Vulpix checklist from PokeCottage CDN...")
    headers = {"User-Agent": "VulpixVault/2.0 (Personal Collector App)"}
    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
        resp = await client.get(POKECOTTAGE_DATA_JS_URL, headers=headers)
        resp.raise_for_status()
        raw = resp.text

    marker = 'window.PokeCottageMastersetInline["37-vulpix"] ='
    idx = raw.find(marker)
    if idx == -1:
        raise ValueError("Unexpected format from PokeCottage CDN.")
    json_str = raw[idx + len(marker):].strip().rstrip(";").strip()
    data = json.loads(json_str)

    if progress_cb:
        progress_cb(1, 2, f"Merging {len(data.get('cards', []))} PokeCottage entries into SQLite...")

    dest = os.path.join(get_data_dir(), "pokecottage_vulpix.json")
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    counts = seed_canonical_catalog(db_path)
    if progress_cb:
        progress_cb(2, 2, f"Updated PokeCottage catalog ({counts.get('pokecottage', 0)} variants synced).")
    return {
        "cards_fetched": len(data.get("cards", [])),
        "seeded": counts,
    }


def _extract_tcgdex_price(detail: Dict[str, Any], variant_key: str) -> Tuple[Optional[float], Optional[str]]:
    """Extracts live raw market price from TCGdex embedded TCGplayer (USD) or Cardmarket (EUR)."""
    pricing = detail.get("pricing") or {}

    tcgp = pricing.get("tcgplayer") or {}
    if isinstance(tcgp, dict):
        # Match exact variant first
        preferred_buckets = {
            "1st_edition": ["1st-edition-normal", "1st-edition-holofoil", "1st-edition"],
            "reverse_holo": ["reverse-holofoil", "reverse"],
            "holo": ["holofoil", "unlimited-holofoil"],
            "rainbow": ["holofoil"],
            "art_rare": ["holofoil"],
        }.get(variant_key, ["normal", "unlimited-normal", "unlimited", "holofoil"])
        for bucket in preferred_buckets:
            b = tcgp.get(bucket)
            if isinstance(b, dict):
                val = b.get("marketPrice") or b.get("midPrice") or b.get("lowPrice")
                if val and float(val) > 0:
                    return round(float(val), 2), "TCGPlayer"

    cm = pricing.get("cardmarket") or {}
    if isinstance(cm, dict):
        if variant_key in ("reverse_holo", "holo", "stamp", "poke_ball", "master_ball"):
            val = cm.get("trend-holo") or cm.get("avg-holo") or cm.get("low-holo") or cm.get("trend") or cm.get("avg")
        else:
            val = cm.get("trend") or cm.get("avg") or cm.get("low")
        if val and float(val) > 0:
            return round(float(val) * EUR_TO_USD, 2), "Cardmarket"

    return None, None


async def sync_tcgdex_all_languages(
    languages: Optional[List[str]] = None,
    progress_cb: Optional[Callable[[int, int, str], None]] = None,
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Syncs all official Vulpix & Alolan Vulpix cards across up to 14 official TCGdex languages.
    - Pulls authentic localized high-res scans (`assets.tcgdex.net/{lang}/.../high.webp`)
    - Pulls live TCGPlayer / Cardmarket pricing embedded in TCGdex
    - Deduplicates cleanly against existing PokeCottage/baseline rows without creating duplicates.
    """
    selected = [
        row for row in TCGDEX_LANGUAGES
        if not languages or row[0] in languages or row[1] in languages
    ]
    total_langs = len(selected)
    added = 0
    updated = 0
    priced = 0
    errors: List[str] = []

    headers = {"User-Agent": "VulpixVault/2.0 (Official TCGdex Sync)"}

    with get_conn(db_path) as conn:
        existing_rows = [
            dict(r) for r in conn.execute(
                "SELECT catalog_key, language, set_id, set_name, base_number, variant_key, price_manual_lock FROM catalog_cards;"
            ).fetchall()
        ]

    # Build fast dedupe index: (lang_lower, set_id_or_slug, base_num, variant_key) -> catalog_key
    existing_by_set_id: Dict[Tuple[str, str, str, str], str] = {}
    existing_by_set_name: Dict[Tuple[str, str, str, str], str] = {}
    locked_keys = {r["catalog_key"] for r in existing_rows if r.get("price_manual_lock")}
    for r in existing_rows:
        ll = r["language"].lower()
        bn = r["base_number"]
        vk = r["variant_key"]
        if r["set_id"]:
            existing_by_set_id[(ll, r["set_id"].lower(), bn, vk)] = r["catalog_key"]
        existing_by_set_name[(ll, slugify(r["set_name"]), bn, vk)] = r["catalog_key"]

    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True, headers=headers) as client:
        # Fetch official TCGdex English set catalog once so EVERY international set_id resolves to English!
        en_set_lookup: Dict[str, str] = {}
        try:
            en_sets_resp = await client.get(f"{TCGDEX_BASE}/en/sets")
            if en_sets_resp.status_code == 200 and isinstance(en_sets_resp.json(), list):
                for s_item in en_sets_resp.json():
                    if s_item.get("id") and s_item.get("name"):
                        en_set_lookup[str(s_item["id"]).lower()] = str(s_item["name"]).strip()
        except Exception:
            pass

        for idx, (lang_code, lang_name, region, fallback_names) in enumerate(selected, start=1):
            if progress_cb:
                progress_cb(idx - 1, total_langs, f"Fetching {lang_name} ({lang_code}) cards from TCGdex...")

            brief_cards: Dict[str, Dict[str, Any]] = {}
            # Primary query: Pokédex #37 (Vulpix + Alolan Vulpix + Blaine's/Brock's Vulpix)
            try:
                resp = await client.get(f"{TCGDEX_BASE}/{lang_code}/cards", params={"dexId": "37"})
                if resp.status_code == 200 and isinstance(resp.json(), list):
                    for item in resp.json():
                        if item.get("id"):
                            brief_cards[item["id"]] = item
            except Exception as e:
                errors.append(f"{lang_code} dexId: {e}")

            # Fallback localized name queries (catches cards missing dexId metadata)
            for fname in fallback_names:
                try:
                    resp = await client.get(f"{TCGDEX_BASE}/{lang_code}/cards", params={"name": fname})
                    if resp.status_code == 200 and isinstance(resp.json(), list):
                        for item in resp.json():
                            if item.get("id"):
                                brief_cards[item["id"]] = item
                except Exception:
                    continue

            if not brief_cards:
                continue

            # Fetch card details & missing set release dates BEFORE opening SQLite transaction
            # so database write locks are never held across network awaits.
            fetched_details: List[Tuple[str, Dict[str, Any], Dict[str, Any]]] = []
            set_meta_cache: Dict[str, Tuple[str, str]] = {}

            for card_id, brief in brief_cards.items():
                try:
                    d_resp = await client.get(f"{TCGDEX_BASE}/{lang_code}/cards/{card_id}")
                    if d_resp.status_code != 200:
                        continue
                    detail = d_resp.json()
                except Exception:
                    continue

                set_info = detail.get("set") or {}
                sid = str(set_info.get("id") or card_id.split("-")[0])
                if sid and not set_info.get("releaseDate"):
                    if sid not in set_meta_cache:
                        rel_d = ""
                        ser_n = ""
                        try:
                            s_resp = await client.get(f"{TCGDEX_BASE}/{lang_code}/sets/{sid}")
                            if s_resp.status_code == 200:
                                s_json = s_resp.json()
                                rel_d = str(s_json.get("releaseDate") or "")
                                ser_n = str((s_json.get("serie") or {}).get("name") or "")
                        except Exception:
                            pass
                        set_meta_cache[sid] = (rel_d, ser_n)
                    cached_rel, cached_ser = set_meta_cache[sid]
                    if cached_rel:
                        set_info["releaseDate"] = cached_rel
                    if cached_ser:
                        set_info["_seriesName"] = cached_ser
                    detail["set"] = set_info

                fetched_details.append((card_id, brief, detail))

            if not fetched_details:
                continue

            with get_conn(db_path) as conn:
                c = conn.cursor()
                for card_id, brief, detail in fetched_details:
                    # Confirm card belongs to Vulpix (dexId 37) and isn't a non-Vulpix cameo
                    dex_ids = detail.get("dexId") or []
                    cname = str(detail.get("name") or brief.get("name") or "").strip()
                    if dex_ids and 37 not in dex_ids:
                        continue
                    if not cname:
                        continue

                    set_info = detail.get("set") or {}
                    set_id = str(set_info.get("id") or card_id.split("-")[0])
                    raw_set_name = str(set_info.get("name") or set_id)
                    en_name, native_name = translate_card_name(cname, lang_name)
                    en_set_name, native_set_name = translate_set_name(raw_set_name, set_id, en_set_lookup)
                    series_name = str(set_info.get("_seriesName") or "")
                    local_id = str(detail.get("localId") or brief.get("localId") or "")
                    card_total = (set_info.get("cardCount") or {}).get("official") or ""
                    card_num = f"{local_id}/{card_total}" if (local_id and card_total and "/" not in local_id) else local_id
                    base_num = extract_base_number(local_id)
                    rarity = str(detail.get("rarity") or "Common")
                    artist = str(detail.get("illustrator") or "")
                    img_base = detail.get("image") or brief.get("image") or ""
                    img_url = f"{img_base}/high.webp" if img_base else ""

                    # Release year via set metadata
                    rel_date = str(set_info.get("releaseDate") or "")
                    year = int(rel_date[:4]) if len(rel_date) >= 4 and rel_date[:4].isdigit() else 2000

                    # Determine official print variants for this card
                    v_flags = detail.get("variants") or {}
                    variant_specs: List[Tuple[str, str]] = []
                    if v_flags.get("firstEdition"):
                        variant_specs.append(("1st Edition", "1st_edition"))
                    if v_flags.get("normal"):
                        variant_specs.append(("Unlimited", "unlimited"))
                    if v_flags.get("reverse"):
                        variant_specs.append(("Reverse Holo", "reverse_holo"))
                    if v_flags.get("holo"):
                        variant_specs.append(("Holo", "holo"))
                    if not variant_specs:
                        ed_lbl, vk, _, _ = classify_variant("Standard", rarity, en_name)
                        variant_specs.append((ed_lbl, vk))

                    safe_card_id = str(card_id).replace("/", "-")
                    for ed_label, vk in variant_specs:
                        # Check if this exact language+set+number+variant already exists (matching translated English set name too!)
                        match_key = (
                            existing_by_set_id.get((lang_name.lower(), set_id.lower(), base_num, vk))
                            or existing_by_set_name.get((lang_name.lower(), slugify(en_set_name), base_num, vk))
                            or existing_by_set_name.get((lang_name.lower(), slugify(raw_set_name), base_num, vk))
                        )
                        raw_p, p_src = _extract_tcgdex_price(detail, vk)

                        if match_key:
                            # Enrich existing card with tcgdex_id, native subtitle, localized image (if missing), and live raw price
                            c.execute("""
                                UPDATE catalog_cards
                                SET tcgdex_id = :tid,
                                    native_name = CASE WHEN native_name = '' AND :nname != '' THEN :nname ELSE native_name END,
                                    native_set_name = CASE WHEN native_set_name = '' AND :nset != '' THEN :nset ELSE native_set_name END,
                                    image_url = CASE WHEN (image_is_localized = 0 OR image_url = '') AND :img != '' THEN :img ELSE image_url END,
                                    image_is_localized = CASE WHEN :img != '' THEN 1 ELSE image_is_localized END,
                                    artist = CASE WHEN artist = '' AND :art != '' THEN :art ELSE artist END
                                WHERE catalog_key = :ck;
                            """, {
                                "tid": f"{lang_code}:{card_id}",
                                "nname": native_name,
                                "nset": native_set_name,
                                "img": img_url,
                                "art": artist,
                                "ck": match_key,
                            })
                            if raw_p and match_key not in locked_keys:
                                c.execute("""
                                    UPDATE catalog_cards
                                    SET price_raw = :pr,
                                        price_source = CASE WHEN price_source = 'PriceCharting' THEN price_source ELSE :ps END,
                                        price_updated_at = :ts
                                    WHERE catalog_key = :ck AND price_manual_lock = 0;
                                """, {"pr": raw_p, "ps": p_src, "ts": now_iso, "ck": match_key})
                                priced += 1
                            updated += 1
                        else:
                            # Do not create redundant EN/JA/S.CN duplicates if PokeCottage already owns that language+set+num
                            if lang_name in ("English", "Japanese", "S. Chinese"):
                                exists_any = c.execute(
                                    """SELECT catalog_key FROM catalog_cards
                                       WHERE language = ?
                                         AND (LOWER(set_id) = ? OR LOWER(set_name) = ? OR (release_year = ? AND release_year > 1995))
                                         AND base_number = ?
                                       LIMIT 1;""",
                                    (lang_name, set_id.lower(), en_set_name.lower(), year, base_num),
                                ).fetchone()
                                if exists_any:
                                    # Still enrich matched canonical card's price if unpriced
                                    target_ck = exists_any["catalog_key"]
                                    if raw_p and target_ck not in locked_keys:
                                        c.execute("""
                                            UPDATE catalog_cards
                                            SET price_raw = COALESCE(price_raw, :pr),
                                                price_source = COALESCE(NULLIF(price_source, ''), :ps),
                                                price_updated_at = COALESCE(NULLIF(price_updated_at, ''), :ts),
                                                native_name = CASE WHEN native_name = '' AND :nname != '' THEN :nname ELSE native_name END,
                                                native_set_name = CASE WHEN native_set_name = '' AND :nset != '' THEN :nset ELSE native_set_name END
                                            WHERE catalog_key = :ck AND price_manual_lock = 0;
                                        """, {"pr": raw_p, "ps": p_src, "ts": now_iso, "nname": native_name, "nset": native_set_name, "ck": target_ck})
                                        priced += 1
                                    continue
                                # Also skip imageless vintage JP/EN/S.CN stub entries from TCGdex when PokeCottage covers them
                                if not img_url:
                                    continue

                            ck = f"tcgdex:{lang_code}:{safe_card_id}:{vk}"
                            callouts = get_visual_callouts(
                                set_name=en_set_name,
                                language=lang_name,
                                edition=ed_label,
                                variant_key=vk,
                            )
                            _upsert_catalog_card(c, {
                                "catalog_key": ck,
                                "card_group_key": f"{slugify(en_set_name)}-{base_num}-{lang_code}",
                                "card_name": en_name,
                                "native_name": native_name,
                                "set_name": en_set_name,
                                "native_set_name": native_set_name,
                                "set_id": set_id,
                                "series": series_name,
                                "card_number": card_num,
                                "base_number": base_num,
                                "release_year": year,
                                "release_date": rel_date,
                                "language": lang_name,
                                "region": region,
                                "edition": ed_label,
                                "variant_key": vk,
                                "rarity": rarity,
                                "artist": artist,
                                "is_error": 0,
                                "error_description": "",
                                "visual_callouts": json.dumps(callouts),
                                "image_url": img_url,
                                "local_image": "",
                                "image_is_localized": 1 if img_url else 0,
                                "pokecottage_id": "",
                                "tcgdex_id": f"{lang_code}:{card_id}",
                                "pricecharting_url": "",
                                "tcgplayer_url": "",
                                "notes": f"Official {lang_name} {en_set_name} release synced via TCGdex.",
                                "source": "tcgdex",
                            })
                            if raw_p:
                                c.execute(
                                    "UPDATE catalog_cards SET price_raw = ?, price_source = ?, price_updated_at = ? WHERE catalog_key = ?;",
                                    (raw_p, p_src, now_iso, ck),
                                )
                                priced += 1
                            existing_by_set_id[(lang_name.lower(), set_id.lower(), base_num, vk)] = ck
                            existing_by_set_name[(lang_name.lower(), slugify(en_set_name), base_num, vk)] = ck
                            added += 1

    if progress_cb:
        progress_cb(total_langs, total_langs, f"Complete: +{added} new localized cards, {updated} enriched, {priced} live prices updated.")

    return {
        "languages_scanned": total_langs,
        "added": added,
        "updated": updated,
        "priced": priced,
        "errors": errors[:10],
    }


async def cache_images_locally(
    progress_cb: Optional[Callable[[int, int, str], None]] = None,
    db_path: Optional[str] = None,
) -> Dict[str, int]:
    """Downloads remote card scans to /data/cached_cards/ and ACTUALLY links local_image in SQLite."""
    cache_dir = get_cached_cards_dir()
    with get_conn(db_path) as conn:
        rows = conn.execute(
            "SELECT catalog_key, image_url FROM catalog_cards WHERE image_url LIKE 'http%' AND (local_image IS NULL OR local_image = '');"
        ).fetchall()

    total = len(rows)
    downloaded = 0
    failed = 0
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    async with httpx.AsyncClient(timeout=12.0, follow_redirects=True, headers=headers) as client:
        for i, row in enumerate(rows, start=1):
            ck = row["catalog_key"]
            url = row["image_url"]
            ext = ".webp" if ".webp" in url.lower() else (".png" if ".png" in url.lower() else ".jpg")
            fname = slugify(ck) + ext
            dest = os.path.join(cache_dir, fname)

            if not os.path.isfile(dest):
                try:
                    resp = await client.get(url)
                    if resp.status_code == 200 and len(resp.content) > 1000:
                        with open(dest, "wb") as f:
                            f.write(resp.content)
                        downloaded += 1
                    else:
                        failed += 1
                        continue
                except Exception:
                    failed += 1
                    continue
            else:
                downloaded += 1

            with get_conn(db_path) as conn:
                conn.execute(
                    "UPDATE catalog_cards SET local_image = ? WHERE catalog_key = ?;",
                    (f"cached/{fname}", ck),
                )

            if progress_cb and (i % 5 == 0 or i == total):
                progress_cb(i, total, f"Cached {downloaded}/{total} card scans locally...")

    return {"total": total, "downloaded": downloaded, "failed": failed}


def translate_and_dedupe_existing_catalog(db_path: Optional[str] = None) -> Dict[str, int]:
    """
    Fast startup pass that:
      1. Translates any already-synced foreign card titles & set names into readable English
         (preserving the original native text in native_name / native_set_name).
      2. Re-applies pixel-calibrated visual_callouts to every card.
      3. Merges & removes duplicate TCGdex entries (e.g. imageless Japanese Leaders' Stadium duplicates)
         into their canonical PokeCottage counterparts while preserving prices & Vault links.
    """
    stats = {"translated": 0, "callouts_updated": 0, "deduped": 0}
    with get_conn(db_path) as conn:
        c = conn.cursor()
        rows = [dict(r) for r in c.execute("SELECT * FROM catalog_cards;").fetchall()]

        # Pass 1: Translate foreign titles/sets + refresh calibrated visual callouts
        for r in rows:
            ck = r["catalog_key"]
            en_name, nat_name = translate_card_name(r["card_name"], r["language"])
            en_set, nat_set = translate_set_name(r["set_name"], r.get("set_id") or "")

            final_native_name = r.get("native_name") or nat_name
            final_native_set = r.get("native_set_name") or nat_set

            new_callouts = json.dumps(get_visual_callouts(
                set_name=en_set,
                language=r["language"],
                edition=r["edition"],
                variant_key=r["variant_key"],
                is_error=bool(r.get("is_error")),
                error_description=r.get("error_description") or "",
                pokecottage_id=r.get("pokecottage_id") or "",
            ))

            changed_text = (
                en_name != r["card_name"]
                or en_set != r["set_name"]
                or final_native_name != (r.get("native_name") or "")
                or final_native_set != (r.get("native_set_name") or "")
            )
            changed_callouts = new_callouts != (r.get("visual_callouts") or "[]")

            if changed_text or changed_callouts:
                c.execute("""
                    UPDATE catalog_cards
                    SET card_name = ?, native_name = ?, set_name = ?, native_set_name = ?, visual_callouts = ?
                    WHERE catalog_key = ?;
                """, (en_name, final_native_name, en_set, final_native_set, new_callouts, ck))
                r["card_name"] = en_name
                r["native_name"] = final_native_name
                r["set_name"] = en_set
                r["native_set_name"] = final_native_set
                if changed_text:
                    stats["translated"] += 1
                if changed_callouts:
                    stats["callouts_updated"] += 1

        # Pass 2: Merge duplicate tcgdex: rows that overlap canonical pc:/curated:/csv_lang: entries
        canonical_exact: Dict[Tuple[str, str, str, str], Dict[str, Any]] = {}
        canonical_loose: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
        canonical_year_num: Dict[Tuple[str, int, str], Dict[str, Any]] = {}

        for r in rows:
            if r["source"] != "tcgdex":
                ll = r["language"].lower()
                sn = slugify(r["set_name"])
                bn = r["base_number"]
                vk = r["variant_key"]
                canonical_exact.setdefault((ll, sn, bn, vk), r)
                canonical_loose.setdefault((ll, sn, bn), r)
                if r.get("release_year") and int(r["release_year"]) > 1995 and bn:
                    canonical_year_num.setdefault((ll, int(r["release_year"]), bn), r)

        for r in rows:
            if r["source"] != "tcgdex":
                continue
            ll = r["language"].lower()
            sn = slugify(r["set_name"])
            bn = r["base_number"]
            vk = r["variant_key"]
            has_img = bool((r.get("image_url") or "").strip() or (r.get("local_image") or "").strip())

            target = canonical_exact.get((ll, sn, bn, vk))
            if not target and ll in ("english", "japanese", "s. chinese"):
                target = canonical_loose.get((ll, sn, bn))
                if not target and not has_img and r.get("release_year"):
                    target = canonical_year_num.get((ll, int(r["release_year"]), bn))

            if target:
                tkey = target["catalog_key"]
                # Preserve any fetched prices, native titles, or tcgdex_id on the canonical card before removal
                c.execute("""
                    UPDATE catalog_cards
                    SET price_raw = COALESCE(price_raw, ?),
                        price_grade9 = COALESCE(price_grade9, ?),
                        price_grade10 = COALESCE(price_grade10, ?),
                        price_source = COALESCE(NULLIF(price_source, ''), ?),
                        price_updated_at = COALESCE(NULLIF(price_updated_at, ''), ?),
                        native_name = CASE WHEN native_name = '' AND ? != '' THEN ? ELSE native_name END,
                        native_set_name = CASE WHEN native_set_name = '' AND ? != '' THEN ? ELSE native_set_name END,
                        tcgdex_id = CASE WHEN tcgdex_id = '' AND ? != '' THEN ? ELSE tcgdex_id END
                    WHERE catalog_key = ?;
                """, (
                    r.get("price_raw"), r.get("price_grade9"), r.get("price_grade10"),
                    r.get("price_source"), r.get("price_updated_at"),
                    r.get("native_name") or "", r.get("native_name") or "",
                    r.get("native_set_name") or "", r.get("native_set_name") or "",
                    r.get("tcgdex_id") or "", r.get("tcgdex_id") or "",
                    tkey,
                ))
                c.execute("UPDATE vault_items SET catalog_key = ? WHERE catalog_key = ?;", (tkey, r["catalog_key"]))
                c.execute("DELETE FROM catalog_cards WHERE catalog_key = ?;", (r["catalog_key"],))
                stats["deduped"] += 1
            elif ll in ("english", "japanese", "s. chinese") and not has_img:
                # Drop imageless orphan TCGdex stubs for languages already fully cataloged by PokeCottage
                # (only if no vault item links to it)
                linked = c.execute("SELECT 1 FROM vault_items WHERE catalog_key = ? LIMIT 1;", (r["catalog_key"],)).fetchone()
                if not linked:
                    c.execute("DELETE FROM catalog_cards WHERE catalog_key = ?;", (r["catalog_key"],))
                    stats["deduped"] += 1

    return stats
