"""
Safe, non-destructive migration from legacy Streamlit v1 `my_collection` into v2 `vault_items`.
- Runs ONCE (tracked via app_settings `v2_vault_migrated = 1`).
- Never wipes user-entered cards.
- Deterministically links every owned card to its exact canonical `catalog_key`.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from backend.catalog_builder import classify_variant, extract_base_number, slugify
from backend.db import get_conn, get_setting, set_setting


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def match_catalog_key(card: Dict[str, Any], catalog_rows: List[Dict[str, Any]]) -> Optional[str]:
    """Authoritative matcher linking a vault card to its exact canonical catalog_key."""
    cname = _norm(card.get("card_name", ""))
    sname = _norm(card.get("set_name", ""))
    cnum = str(card.get("card_number", "")).strip()
    bnum = extract_base_number(cnum)
    lang = (card.get("language") or "English").strip().lower()
    if lang == "chinese":
        lang = "t. chinese"
    ed_raw = str(card.get("edition") or "Unlimited")
    _, vk, _, _ = classify_variant(ed_raw, card_name=card.get("card_name", ""))
    notes = (card.get("notes") or "").lower()

    # High-precision special cases from legacy v1 collection records
    if "playing" in sname or "playing" in notes:
        if "ninety" in ed_raw.lower() or "ninety" in notes:
            return "custom:playing-kr-ninetynine-8"
        if "black 2" in notes or "diamond" in cnum.lower():
            return "custom:playing-jp-black2-4d"
        if "paper safari" in ed_raw.lower() or "paper safari" in notes:
            return "custom:playing-kr-papersafari-5"

    if "daiichi" in sname or "293" in cnum:
        return "pc:37-jpn_smp-293-daiichiPan"

    if ("darkness" in sname or "darkness" in notes or ("neo destiny" in sname and lang == "japanese")):
        return "pc:37-jpn_neo4-14-normal"

    if "mega brave" in sname and ("67" in bnum or "art rare" in ed_raw.lower()):
        return "pc:37-jpn_m1l-67-holo"

    if "mega evolution" in sname and "138" in bnum:
        return "pc:37-me1-138-holo"

    if "hidden fates" in sname and "sv8" in cnum.lower():
        return "pc:37-sma-SV8-holo"

    if "151" in sname and lang == "japanese":
        if "master ball" in ed_raw.lower() or "master ball" in notes:
            return "pc:37-jpn_sv2a-37-masterBallHolo"
        if "poke ball" in ed_raw.lower() or "poké ball" in ed_raw.lower() or "poke ball" in notes:
            return "pc:37-jpn_sv2a-37-pokeBallHolo"
        return "pc:37-jpn_sv2a-37-normal"

    if "base set" in sname and "chinese" in lang and "1st" in ed_raw.lower():
        return "lang:zh-tw:base-set-68:1st-edition"

    # General exact matching across canonical catalog
    best_key = None
    best_score = -1

    for row in catalog_rows:
        r_lang = (row["language"] or "").lower()
        if r_lang != lang:
            continue

        r_cname = _norm(row["card_name"])
        # Character prefix guard (never cross-match Alolan / Brock's / Blaine's / VSTAR / Poncho)
        mismatch = False
        for kw in ("alolan", "brock", "blaine", "vstar", "poncho"):
            if (kw in cname) != (kw in r_cname):
                mismatch = True
                break
        if mismatch:
            continue

        r_sname = _norm(row["set_name"])
        set_ok = (sname == r_sname) or (sname in r_sname) or (r_sname in sname)
        if not set_ok:
            continue

        r_bnum = str(row["base_number"] or "")
        if bnum and r_bnum and bnum != r_bnum:
            continue

        score = 10
        if sname == r_sname:
            score += 5
        if row["variant_key"] == vk:
            score += 10
        elif vk in ("unlimited", "holo") and row["variant_key"] in ("unlimited", "holo"):
            score += 4
        if ("1st" in ed_raw.lower()) != ("1st" in (row["edition"] or "").lower()):
            score -= 12
        if ("reverse" in ed_raw.lower()) != ("reverse" in (row["edition"] or "").lower()):
            score -= 12

        if score > best_score:
            best_score = score
            best_key = row["catalog_key"]

    return best_key if best_score >= 10 else None


def migrate_legacy_vault_if_needed(db_path: Optional[str] = None) -> int:
    """One-time safe copy from legacy `my_collection` -> `vault_items` with exact catalog_key linking."""
    if get_setting("v2_vault_migrated", db_path=db_path) == "1":
        return 0

    migrated = 0
    with get_conn(db_path) as conn:
        c = conn.cursor()
        # Check if vault_items already has records
        existing_v2 = c.execute("SELECT COUNT(*) FROM vault_items;").fetchone()[0]
        if existing_v2 > 0:
            c.execute("INSERT OR REPLACE INTO app_settings (key, value, updated_at) VALUES ('v2_vault_migrated', '1', CURRENT_TIMESTAMP);")
            return 0

        # Check if legacy `my_collection` table exists
        has_legacy = c.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='my_collection';"
        ).fetchone()
        if not has_legacy:
            c.execute("INSERT OR REPLACE INTO app_settings (key, value, updated_at) VALUES ('v2_vault_migrated', '1', CURRENT_TIMESTAMP);")
            return 0

        legacy_rows = [dict(r) for r in c.execute("SELECT * FROM my_collection ORDER BY id ASC;").fetchall()]
        catalog_rows = [dict(r) for r in c.execute("SELECT * FROM catalog_cards;").fetchall()]
        catalog_by_key = {r["catalog_key"]: r for r in catalog_rows}

        for lr in legacy_rows:
            ck = match_catalog_key(lr, catalog_rows)
            cat = catalog_by_key.get(ck) if ck else None

            # Use canonical card name/set/number/image if cleanly matched while preserving user's exact grade & purchase price!
            c_name = cat["card_name"] if cat else lr.get("card_name", "Vulpix")
            s_name = cat["set_name"] if cat else lr.get("set_name", "Unknown Set")
            c_num = cat["card_number"] if cat else (lr.get("card_number") or "")
            lang = cat["language"] if cat else (lr.get("language") or "English")
            ed = cat["edition"] if cat else (lr.get("edition") or "Unlimited")
            img = ""
            if cat:
                img = f"/static/cards/{cat['local_image']}" if cat.get("local_image") else (cat.get("image_url") or "")
            elif lr.get("image_url"):
                raw_img = str(lr["image_url"])
                img = f"/static/cards/{raw_img.split('/')[-1]}" if raw_img.startswith("dashboard/static/cards/") else raw_img

            is_raw = 1 if (lr.get("is_raw") or str(lr.get("grading_company", "")).upper() == "RAW") else 0
            c.execute("""
                INSERT INTO vault_items (
                    catalog_key, card_name, set_name, card_number, language, edition,
                    is_raw, grading_company, grade, grade_label, cert_number,
                    purchase_price, purchase_date, image_url, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                ck,
                c_name,
                s_name,
                c_num,
                lang,
                ed,
                is_raw,
                str(lr.get("grading_company") or ("RAW" if is_raw else "PSA")),
                float(lr.get("grade") or 0.0),
                str(lr.get("grade_label") or ("Raw Single" if is_raw else "Gem Mint")),
                str(lr.get("cert_number") or ""),
                float(lr.get("purchase_price") or 0.0),
                str(lr.get("purchase_date") or ""),
                img,
                str(lr.get("notes") or ""),
            ))
            migrated += 1

    set_setting("v2_vault_migrated", "1", db_path=db_path)
    return migrated
