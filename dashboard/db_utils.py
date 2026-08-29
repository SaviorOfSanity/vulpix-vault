"""
Database utility module for Streamlit Dashboard.
100% Self-contained: manages SQLite WAL mode, Master Set catalog, collection CRUD,
automatic card name verification and image enrichment via Pokemon.com & Pokecardex,
eBay search query generation, PriceCharting aggregated prices, PSA/CGC Population reports,
Gotify push dispatcher, sniper watchlist, Google Sheets sync, and CSV diagnostics.
"""

import io
import json
import os
import re
import sqlite3
import urllib.parse
import urllib.request
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd

from metadata_resolver import resolve_card_metadata

DEFAULT_DB_PATH = os.getenv("DB_PATH", "/data/vulpix_vault.db")


def get_db_path() -> str:
    path = os.getenv("DB_PATH", DEFAULT_DB_PATH)
    if not os.path.isabs(path):
        path = os.path.join(os.path.dirname(__file__), "..", "data", "vulpix_vault.db")
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    return path


@contextmanager
def get_db_connection():
    """Context manager for SQLite with WAL mode and row factory."""
    path = get_db_path()
    conn = sqlite3.connect(path, timeout=10.0)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA busy_timeout = 5000;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _add_column_if_missing(cursor: sqlite3.Cursor, table: str, column: str, col_type: str):
    """Safely adds a column to an existing table if it does not already exist."""
    cursor.execute(f"PRAGMA table_info({table});")
    existing = [row["name"] for row in cursor.fetchall()]
    if column not in existing:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type};")


def ensure_tables_exist():
    """Ensure database schema is created and auto-migrated with PriceCharting & Pop stats."""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # 1. Master Set Catalog
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS master_set_catalog (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                card_name TEXT NOT NULL,
                set_name TEXT NOT NULL,
                card_number TEXT,
                release_year INTEGER DEFAULT 2000,
                language TEXT DEFAULT 'English',
                edition TEXT DEFAULT 'Unlimited',
                rarity TEXT DEFAULT 'Common',
                is_error INTEGER DEFAULT 0,
                error_description TEXT,
                est_raw_price REAL DEFAULT 0.0,
                est_grade10_price REAL DEFAULT 0.0,
                pricecharting_url TEXT,
                pricecharting_raw REAL DEFAULT 0.0,
                pricecharting_grade9 REAL DEFAULT 0.0,
                pricecharting_grade10 REAL DEFAULT 0.0,
                pop_total INTEGER DEFAULT 0,
                pop_grade10 INTEGER DEFAULT 0,
                pop_pristine10 INTEGER DEFAULT 0,
                image_url TEXT,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(card_name, set_name, card_number, language, edition, is_error)
            );
        """)

        # 2. Personal Collection
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS my_collection (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                card_name TEXT NOT NULL,
                set_name TEXT NOT NULL,
                card_number TEXT,
                grading_company TEXT NOT NULL DEFAULT 'RAW',
                grade REAL NOT NULL DEFAULT 0.0,
                grade_label TEXT DEFAULT 'Gem Mint',
                cert_number TEXT DEFAULT '',
                purchase_price REAL NOT NULL DEFAULT 0.0,
                purchase_date TEXT NOT NULL,
                edition TEXT DEFAULT 'Unlimited',
                language TEXT DEFAULT 'English',
                is_error INTEGER DEFAULT 0,
                error_type TEXT,
                is_raw INTEGER DEFAULT 0,
                pop_grade10 INTEGER DEFAULT 0,
                pop_pristine10 INTEGER DEFAULT 0,
                master_card_id INTEGER,
                image_url TEXT,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 3. Market Sales
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS market_sales (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                listing_id TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL,
                card_name TEXT NOT NULL,
                grading_company TEXT,
                grade REAL,
                grade_label TEXT DEFAULT 'Gem Mint',
                condition_type TEXT DEFAULT 'Graded',
                edition TEXT DEFAULT 'Unlimited',
                language TEXT DEFAULT 'English',
                is_error INTEGER DEFAULT 0,
                price REAL NOT NULL,
                shipping_cost REAL DEFAULT 0.0,
                total_price REAL NOT NULL,
                listing_url TEXT NOT NULL,
                image_url TEXT,
                listing_type TEXT DEFAULT 'Buy It Now',
                deal_rating TEXT DEFAULT 'unrated',
                fair_value_estimate REAL,
                discount_percentage REAL,
                ai_rationale TEXT,
                sale_date TEXT,
                scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 4. Sniper Watchlist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ebay_sniper_watchlist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                listing_id TEXT UNIQUE NOT NULL,
                card_name TEXT NOT NULL,
                title TEXT NOT NULL,
                listing_url TEXT NOT NULL,
                image_url TEXT,
                auction_end_time TEXT,
                current_bid REAL NOT NULL DEFAULT 0.0,
                shipping_cost REAL DEFAULT 0.0,
                target_bid_mode TEXT DEFAULT 'amazing_deal',
                custom_max_bid REAL,
                max_calculated_bid REAL,
                status TEXT DEFAULT 'watching',
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Auto-migration columns
        for col, ctype in [
            ("pricecharting_url", "TEXT"),
            ("pricecharting_raw", "REAL DEFAULT 0.0"),
            ("pricecharting_grade9", "REAL DEFAULT 0.0"),
            ("pricecharting_grade10", "REAL DEFAULT 0.0"),
            ("pop_total", "INTEGER DEFAULT 0"),
            ("pop_grade10", "INTEGER DEFAULT 0"),
            ("pop_pristine10", "INTEGER DEFAULT 0"),
        ]:
            _add_column_if_missing(cursor, "master_set_catalog", col, ctype)

        for col, ctype in [
            ("pop_grade10", "INTEGER DEFAULT 0"),
            ("pop_pristine10", "INTEGER DEFAULT 0"),
        ]:
            _add_column_if_missing(cursor, "my_collection", col, ctype)

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_master_search ON master_set_catalog(card_name, set_name, language, edition);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_market_lookup ON market_sales(card_name, grading_company, grade, condition_type);")


# =============================================================
# URL & Aggregation Link Helpers
# =============================================================

def generate_ebay_search_url(
    card_name: str,
    set_name: str = "",
    card_number: str = "",
    edition: str = "",
    language: str = "English",
    grade_tier: Optional[str] = None,
    is_raw: bool = False,
    is_auction_only: bool = False,
) -> str:
    """Generates targeted eBay search URL for any Vulpix card."""
    query_parts = [card_name]

    clean_set = re.sub(r"\([0-9]{4}\)", "", set_name).strip()
    if clean_set and clean_set.lower() not in ["unknown set", ""]:
        query_parts.append(f'"{clean_set}"')

    clean_num = card_number.replace("No Number", "").strip()
    if clean_num:
        query_parts.append(clean_num)

    if edition and edition.lower() not in ["unlimited", "standard", ""]:
        query_parts.append(f'"{edition}"')

    if language and language.lower() not in ["english", ""]:
        query_parts.append(f'"{language}"')

    if is_raw:
        query_parts.append("(raw, ungraded, NM)")
    elif grade_tier:
        if "Black Label" in grade_tier:
            query_parts.append('"Black Label"')
        elif "Pristine" in grade_tier:
            query_parts.append('"Pristine 10"')
        elif "Gem Mint" in grade_tier or "10" in grade_tier:
            query_parts.append("(PSA 10, CGC 10, BGS 10)")

    query_str = " ".join(query_parts)
    encoded = urllib.parse.quote_plus(query_str)
    url = f"https://www.ebay.com/sch/i.html?_nkw={encoded}&_sacat=0&_sop=10"
    if is_auction_only:
        url += "&LH_Auction=1"
    return url


def get_pricecharting_search_url(card_name: str, set_name: str = "", card_number: str = "") -> str:
    """Generates PriceCharting search URL for card price aggregation."""
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


# =============================================================
# Gotify Notification Dispatcher (Self-Contained in Dashboard)
# =============================================================

def send_gotify_alert(
    listing: Dict[str, Any],
    appraisal: Dict[str, Any],
    gotify_url: Optional[str] = None,
    gotify_token: Optional[str] = None,
) -> bool:
    """Dispatches a push notification directly to Gotify server."""
    base_url = (gotify_url or os.getenv("GOTIFY_URL", "http://10.0.0.48")).rstrip("/")
    token = gotify_token or os.getenv("GOTIFY_APP_TOKEN", "")

    if not token or token == "your_gotify_app_token_here":
        print("[Dashboard Gotify] Warning: GOTIFY_APP_TOKEN not configured in .env.")
        return False

    rating = appraisal.get("deal_rating", "good_deal")
    priority = 8 if rating == "amazing_deal" else 6
    emoji = "🔥" if rating == "amazing_deal" else "⭐"
    title = f"{emoji} {rating.replace('_', ' ').title()}: {listing.get('card_name', 'Vulpix')}"

    message_body = (
        f"**Card:** {listing.get('title')}\n"
        f"**Price:** ${listing.get('total_price', 0.0):.2f}\n"
        f"**Est. Fair Value:** ${appraisal.get('fair_value_estimate', 0.0):.2f} ({appraisal.get('discount_percentage', 0.0):.1f}% OFF)\n"
        f"**Rationale:** {appraisal.get('rationale', '')}\n\n"
        f"[View Listing on eBay]({listing.get('listing_url', '')})"
    )

    payload_data = json.dumps({
        "title": title,
        "message": message_body,
        "priority": priority,
        "extras": {
            "client::notification": {"click": {"url": listing.get("listing_url", "")}},
            "client::display": {"contentType": "text/markdown"}
        }
    }).encode("utf-8")

    try:
        req = urllib.request.Request(
            f"{base_url}/message",
            data=payload_data,
            headers={
                "X-Gotify-Key": token,
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0"
            }
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status in [200, 201]
    except Exception as e:
        print(f"[Dashboard Gotify] Connection Error to {base_url}: {e}")
        return False


# =============================================================
# Automated Card Metadata & Image Enrichment
# =============================================================

def auto_enrich_master_catalog() -> Tuple[int, str]:
    """
    Iterates through all cards in master_set_catalog, resolves missing/generic names,
    and grabs official high-res card scans from Pokemon.com / Pokecardex.
    """
    ensure_tables_exist()
    updated = 0
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, card_name, set_name, card_number, release_year, rarity, image_url FROM master_set_catalog;")
        cards = [dict(r) for r in cursor.fetchall()]

        for c in cards:
            resolved = resolve_card_metadata(c["set_name"], c["card_number"], c["card_name"])
            new_name = resolved["card_name"] if (c["card_name"] == "Vulpix" and resolved["card_name"] != "Vulpix") else c["card_name"]
            new_img = resolved["image_url"] if (not c["image_url"] or c["image_url"] == "https://images.pokemontcg.io/base1/68_hires.png") else c["image_url"]
            new_year = resolved["release_year"] if c["release_year"] == 2000 and resolved["release_year"] != 2000 else c["release_year"]
            new_rarity = resolved["rarity"] if c["rarity"] == "Common" and resolved["rarity"] != "Common" else c["rarity"]

            if new_name != c["card_name"] or new_img != c["image_url"] or new_year != c["release_year"] or new_rarity != c["rarity"]:
                cursor.execute("""
                    UPDATE master_set_catalog SET
                        card_name = :new_name,
                        image_url = :new_img,
                        release_year = :new_year,
                        rarity = :new_rarity
                    WHERE id = :id;
                """, {
                    "new_name": new_name,
                    "new_img": new_img,
                    "new_year": new_year,
                    "new_rarity": new_rarity,
                    "id": c["id"],
                })
                updated += 1

    return updated, f"Successfully verified and updated metadata & high-res images for {updated} cards!"


# =============================================================
# Sniper Watchlist Operations
# =============================================================

def get_sniper_watchlist_df() -> pd.DataFrame:
    """Retrieve sniper watchlist items with formatted time status."""
    ensure_tables_exist()
    with get_db_connection() as conn:
        df = pd.read_sql_query("SELECT * FROM ebay_sniper_watchlist ORDER BY auction_end_time ASC", conn)
    return df


def add_to_sniper_watchlist(item: Dict[str, Any]) -> int:
    """Add or update an eBay auction on the sniper watchlist."""
    ensure_tables_exist()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO ebay_sniper_watchlist (
                listing_id, card_name, title, listing_url, image_url,
                auction_end_time, current_bid, shipping_cost, target_bid_mode,
                custom_max_bid, max_calculated_bid, status, notes
            ) VALUES (
                :listing_id, :card_name, :title, :listing_url, :image_url,
                :auction_end_time, :current_bid, :shipping_cost, :target_bid_mode,
                :custom_max_bid, :max_calculated_bid, :status, :notes
            )
            ON CONFLICT(listing_id) DO UPDATE SET
                current_bid = excluded.current_bid,
                auction_end_time = excluded.auction_end_time,
                target_bid_mode = excluded.target_bid_mode,
                custom_max_bid = excluded.custom_max_bid,
                max_calculated_bid = excluded.max_calculated_bid,
                status = excluded.status,
                notes = excluded.notes;
        """, {
            "listing_id": str(item.get("listing_id", "")).strip(),
            "card_name": str(item.get("card_name", "Vulpix")).strip(),
            "title": str(item.get("title", "eBay Auction")).strip(),
            "listing_url": str(item.get("listing_url", "")).strip(),
            "image_url": str(item.get("image_url", "https://images.pokemontcg.io/base1/68_hires.png")).strip(),
            "auction_end_time": str(item.get("auction_end_time", "")).strip(),
            "current_bid": float(item.get("current_bid", 0.0)),
            "shipping_cost": float(item.get("shipping_cost", 0.0)),
            "target_bid_mode": str(item.get("target_bid_mode", "amazing_deal")).strip(),
            "custom_max_bid": float(item.get("custom_max_bid", 0.0)) if item.get("custom_max_bid") else None,
            "max_calculated_bid": float(item.get("max_calculated_bid", 0.0)) if item.get("max_calculated_bid") else None,
            "status": str(item.get("status", "watching")).strip(),
            "notes": str(item.get("notes", "")).strip(),
        })
        return cursor.lastrowid or 0


def delete_from_sniper_watchlist(item_id: int) -> None:
    """Remove an auction from the sniper watchlist."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM ebay_sniper_watchlist WHERE id = ?", (item_id,))


# =============================================================
# Master Set Catalog Operations
# =============================================================

def bulk_upsert_master_catalog(cards: List[Dict[str, Any]]) -> int:
    """Bulk insert or update cards in master_set_catalog with PriceCharting & Pop stats."""
    ensure_tables_exist()
    count = 0
    with get_db_connection() as conn:
        cursor = conn.cursor()
        for card in cards:
            c_name = str(card.get("card_name", "Vulpix")).strip()
            s_name = str(card.get("set_name", "Unknown Set")).strip()
            c_num = str(card.get("card_number", "")).strip()

            # Automatic metadata resolution for variant names & images
            resolved = resolve_card_metadata(s_name, c_num, c_name)
            if c_name.lower() in ["vulpix", "", "none", "nan", "null"] and resolved["card_name"] != "Vulpix":
                c_name = resolved["card_name"]

            img_url = str(card.get("image_url") or "").strip()
            if (not img_url or img_url == "https://images.pokemontcg.io/base1/68_hires.png") and resolved.get("image_url"):
                img_url = resolved["image_url"]

            year_val = int(card.get("release_year") or 2000)
            if year_val == 2000 and resolved.get("release_year") != 2000:
                year_val = resolved["release_year"]

            rarity_val = str(card.get("rarity", "Common")).strip()
            if rarity_val == "Common" and resolved.get("rarity") != "Common":
                rarity_val = resolved["rarity"]

            pc_url = str(card.get("pricecharting_url") or "").strip()
            if not pc_url:
                pc_url = get_pricecharting_search_url(c_name, s_name, c_num)

            params = {
                "card_name": c_name,
                "set_name": s_name,
                "card_number": c_num,
                "release_year": year_val,
                "language": str(card.get("language", "English")).strip(),
                "edition": str(card.get("edition", "Unlimited")).strip(),
                "rarity": rarity_val,
                "is_error": 1 if card.get("is_error") in [1, True, "1", "true", "True", "yes"] else 0,
                "error_description": str(card.get("error_description", "")).strip(),
                "est_raw_price": float(card.get("est_raw_price") or 0.0),
                "est_grade10_price": float(card.get("est_grade10_price") or 0.0),
                "pricecharting_url": pc_url,
                "pricecharting_raw": float(card.get("pricecharting_raw") or 0.0),
                "pricecharting_grade9": float(card.get("pricecharting_grade9") or 0.0),
                "pricecharting_grade10": float(card.get("pricecharting_grade10") or 0.0),
                "pop_total": int(card.get("pop_total") or 0),
                "pop_grade10": int(card.get("pop_grade10") or 0),
                "pop_pristine10": int(card.get("pop_pristine10") or 0),
                "image_url": img_url or "https://images.pokemontcg.io/base1/68_hires.png",
                "notes": str(card.get("notes", "")).strip(),
            }
            cursor.execute("""
                INSERT INTO master_set_catalog (
                    card_name, set_name, card_number, release_year,
                    language, edition, rarity, is_error, error_description,
                    est_raw_price, est_grade10_price, pricecharting_url,
                    pricecharting_raw, pricecharting_grade9, pricecharting_grade10,
                    pop_total, pop_grade10, pop_pristine10, image_url, notes
                ) VALUES (
                    :card_name, :set_name, :card_number, :release_year,
                    :language, :edition, :rarity, :is_error, :error_description,
                    :est_raw_price, :est_grade10_price, :pricecharting_url,
                    :pricecharting_raw, :pricecharting_grade9, :pricecharting_grade10,
                    :pop_total, :pop_grade10, :pop_pristine10, :image_url, :notes
                )
                ON CONFLICT(card_name, set_name, card_number, language, edition, is_error)
                DO UPDATE SET
                    release_year = excluded.release_year,
                    rarity = excluded.rarity,
                    error_description = excluded.error_description,
                    est_raw_price = CASE WHEN excluded.est_raw_price > 0 THEN excluded.est_raw_price ELSE master_set_catalog.est_raw_price END,
                    est_grade10_price = CASE WHEN excluded.est_grade10_price > 0 THEN excluded.est_grade10_price ELSE master_set_catalog.est_grade10_price END,
                    pricecharting_url = CASE WHEN excluded.pricecharting_url != '' THEN excluded.pricecharting_url ELSE master_set_catalog.pricecharting_url END,
                    pricecharting_raw = CASE WHEN excluded.pricecharting_raw > 0 THEN excluded.pricecharting_raw ELSE master_set_catalog.pricecharting_raw END,
                    pricecharting_grade10 = CASE WHEN excluded.pricecharting_grade10 > 0 THEN excluded.pricecharting_grade10 ELSE master_set_catalog.pricecharting_grade10 END,
                    pop_grade10 = CASE WHEN excluded.pop_grade10 > 0 THEN excluded.pop_grade10 ELSE master_set_catalog.pop_grade10 END,
                    pop_pristine10 = CASE WHEN excluded.pop_pristine10 > 0 THEN excluded.pop_pristine10 ELSE master_set_catalog.pop_pristine10 END,
                    image_url = CASE WHEN excluded.image_url != '' THEN excluded.image_url ELSE master_set_catalog.image_url END,
                    notes = CASE WHEN excluded.notes != '' THEN excluded.notes ELSE master_set_catalog.notes END;
            """, params)
            count += 1
    return count


def update_master_card(card_id: int, updates: Dict[str, Any]) -> None:
    """Update details of a card in master_set_catalog."""
    ensure_tables_exist()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE master_set_catalog SET
                card_name = :card_name,
                set_name = :set_name,
                card_number = :card_number,
                release_year = :release_year,
                language = :language,
                edition = :edition,
                rarity = :rarity,
                is_error = :is_error,
                error_description = :error_description,
                est_raw_price = :est_raw_price,
                est_grade10_price = :est_grade10_price,
                pricecharting_raw = :pricecharting_raw,
                pricecharting_grade10 = :pricecharting_grade10,
                pop_grade10 = :pop_grade10,
                pop_pristine10 = :pop_pristine10,
                image_url = :image_url,
                notes = :notes
            WHERE id = :id
        """, {
            "id": card_id,
            "card_name": updates.get("card_name", "Vulpix"),
            "set_name": updates.get("set_name", "Unknown Set"),
            "card_number": updates.get("card_number", ""),
            "release_year": int(updates.get("release_year", 2000)),
            "language": updates.get("language", "English"),
            "edition": updates.get("edition", "Unlimited"),
            "rarity": updates.get("rarity", "Common"),
            "is_error": 1 if updates.get("is_error") else 0,
            "error_description": updates.get("error_description", ""),
            "est_raw_price": float(updates.get("est_raw_price", 0.0)),
            "est_grade10_price": float(updates.get("est_grade10_price", 0.0)),
            "pricecharting_raw": float(updates.get("pricecharting_raw", 0.0)),
            "pricecharting_grade10": float(updates.get("pricecharting_grade10", 0.0)),
            "pop_grade10": int(updates.get("pop_grade10", 0)),
            "pop_pristine10": int(updates.get("pop_pristine10", 0)),
            "image_url": updates.get("image_url", "https://images.pokemontcg.io/base1/68_hires.png"),
            "notes": updates.get("notes", ""),
        })


def load_master_catalog_df() -> pd.DataFrame:
    """Loads Master Set catalog with real-time user owned status."""
    ensure_tables_exist()
    with get_db_connection() as conn:
        df_master = pd.read_sql_query("SELECT * FROM master_set_catalog ORDER BY release_year ASC, set_name ASC, card_number ASC", conn)
        df_col = pd.read_sql_query("SELECT * FROM my_collection", conn)

    if df_master.empty:
        return df_master

    is_owned_list = []
    owned_copies_list = []
    owned_details_list = []

    for _, master_row in df_master.iterrows():
        m_id = master_row["id"]
        matched = df_col[df_col["master_card_id"] == m_id]

        if matched.empty:
            m_card = str(master_row["card_name"]).strip().lower()
            m_set = str(master_row["set_name"]).strip().lower()
            m_ed = str(master_row["edition"]).strip().lower()

            matched = df_col[
                (df_col["card_name"].str.strip().str.lower() == m_card) &
                (df_col["set_name"].str.strip().str.lower() == m_set) &
                (df_col["edition"].str.strip().str.lower() == m_ed)
            ]

        if not matched.empty:
            is_owned_list.append(True)
            owned_copies_list.append(len(matched))
            details = [
                f"{r['grading_company']} {r['grade_label']} ({r['grade'] if r['grade'] else 'Raw'})"
                for _, r in matched.iterrows()
            ]
            owned_details_list.append(", ".join(details))
        else:
            is_owned_list.append(False)
            owned_copies_list.append(0)
            owned_details_list.append("None")

    df_master["is_owned"] = is_owned_list
    df_master["owned_copies"] = owned_copies_list
    df_master["owned_details"] = owned_details_list
    return df_master


def get_master_set_metrics() -> Dict[str, Any]:
    """Calculates Master Set completion percentages and cost-to-complete estimates."""
    df_master = load_master_catalog_df()
    if df_master.empty:
        return {
            "total_cards": 0,
            "owned_cards": 0,
            "missing_cards": 0,
            "completion_pct": 0.0,
            "cost_to_complete_raw": 0.0,
            "cost_to_complete_grade10": 0.0,
            "total_raw_value": 0.0,
            "total_grade10_value": 0.0,
        }

    total_cards = len(df_master)
    owned_cards = int(df_master["is_owned"].sum())
    missing_cards = total_cards - owned_cards
    completion_pct = round((owned_cards / total_cards) * 100, 1) if total_cards > 0 else 0.0

    missing_df = df_master[~df_master["is_owned"]]
    cost_raw = round(missing_df["est_raw_price"].sum(), 2)
    cost_grade10 = round(missing_df["est_grade10_price"].sum(), 2)

    total_raw_val = round(df_master["est_raw_price"].sum(), 2)
    total_grade10_val = round(df_master["est_grade10_price"].sum(), 2)

    return {
        "total_cards": total_cards,
        "owned_cards": owned_cards,
        "missing_cards": missing_cards,
        "completion_pct": completion_pct,
        "cost_to_complete_raw": cost_raw,
        "cost_to_complete_grade10": cost_grade10,
        "total_raw_value": total_raw_val,
        "total_grade10_value": total_grade10_val,
    }


# =============================================================
# CSV & Google Sheets Import / Sync Engine
# =============================================================

def sync_master_catalog_from_df(
    df_input: pd.DataFrame, custom_col_map: Optional[Dict[str, str]] = None
) -> Tuple[int, str, List[str]]:
    """
    Parses any CSV or Google Sheets dataframe with dynamic or manual column mappings.
    Auto-enriches missing/generic card names (e.g. Blaine's Vulpix) and fetches high-res images.
    """
    ensure_tables_exist()
    if df_input.empty:
        return 0, "Uploaded spreadsheet is empty.", []

    col_map = {}
    if custom_col_map:
        col_map = {k: v for k, v in custom_col_map.items() if v and v != "None"}
    else:
        for col in df_input.columns:
            c = str(col).strip().lower().replace("_", " ").replace("-", " ")
            if any(k in c for k in ["card name", "pokemon", "name"]) and "set" not in c:
                col_map["card_name"] = col
            elif any(k in c for k in ["set name", "set", "expansion", "series"]):
                col_map["set_name"] = col
            elif any(k in c for k in ["card number", "number", "card #", "no", "#"]):
                col_map["card_number"] = col
            elif any(k in c for k in ["release year", "year"]):
                col_map["release_year"] = col
            elif any(k in c for k in ["language", "lang"]):
                col_map["language"] = col
            elif any(k in c for k in ["edition", "variant", "ed", "type"]):
                col_map["edition"] = col
            elif any(k in c for k in ["rarity"]):
                col_map["rarity"] = col
            elif any(k in c for k in ["is error", "error"]):
                col_map["is_error"] = col
            elif any(k in c for k in ["raw price", "est raw", "raw", "market price", "price"]):
                col_map["est_raw_price"] = col
            elif any(k in c for k in ["grade 10", "psa 10", "10 price", "est 10", "slab price"]):
                col_map["est_grade10_price"] = col
            elif any(k in c for k in ["pop", "population"]):
                col_map["pop_grade10"] = col
            elif any(k in c for k in ["pricecharting", "charting"]):
                col_map["pricecharting_grade10"] = col
            elif any(k in c for k in ["image", "url", "picture"]):
                col_map["image_url"] = col
            elif any(k in c for k in ["notes", "description", "details", "comments"]):
                col_map["notes"] = col
            elif any(k in c for k in ["owned", "have", "in collection", "collected", "status", "got"]):
                col_map["owned_status"] = col

    cols = list(df_input.columns)
    if "card_name" not in col_map and len(cols) >= 1:
        col_map["card_name"] = cols[0]
    if "set_name" not in col_map and len(cols) >= 2:
        col_map["set_name"] = cols[1]

    cards_to_upsert = []
    owned_to_add = []
    diagnostics = []

    def parse_float(v, default=0.0):
        if pd.isna(v):
            return default
        s = re.sub(r"[^\d.]", "", str(v))
        try:
            return float(s)
        except ValueError:
            return default

    def parse_int(v, default=0):
        if pd.isna(v):
            return default
        s = re.sub(r"[^\d]", "", str(v))
        try:
            return int(s)
        except ValueError:
            return default

    for idx, row in df_input.iterrows():
        raw_name = str(row.get(col_map.get("card_name"), "Vulpix")).strip()
        set_val = str(row.get(col_map.get("set_name"), "Unknown Set")).strip()
        card_num_val = str(row.get(col_map.get("card_number"), "")).strip()

        if (not raw_name or raw_name.lower() in ["nan", "null", "none", ""]) and not set_val:
            diagnostics.append(f"Row {idx+1}: Skipped because Card Name & Set were blank.")
            continue

        # Automated Metadata Resolution & Verification
        resolved = resolve_card_metadata(set_val, card_num_val, raw_name)
        c_name = resolved["card_name"] if (raw_name.lower() in ["vulpix", "", "none", "nan", "null"] and resolved["card_name"] != "Vulpix") else (raw_name or "Vulpix")

        raw_p = parse_float(row.get(col_map.get("est_raw_price")), 2.0)
        g10_p = parse_float(row.get(col_map.get("est_grade10_price")), 45.0)

        err_val = row.get(col_map.get("is_error"), 0)
        is_err = 1 if str(err_val).lower() in ["1", "true", "yes", "error"] else 0

        year_val = row.get(col_map.get("release_year"), resolved.get("release_year", 2000))
        try:
            year_int = int(re.sub(r"[^\d]", "", str(year_val))[:4]) if str(year_val) else resolved.get("release_year", 2000)
        except ValueError:
            year_int = resolved.get("release_year", 2000)

        lang_val = str(row.get(col_map.get("language"), "English")).strip()
        ed_val = str(row.get(col_map.get("edition"), "Unlimited")).strip()
        rarity_val = str(row.get(col_map.get("rarity"), resolved.get("rarity", "Common"))).strip()

        img_val = str(row.get(col_map.get("image_url"), "")).strip()
        if not img_val or img_val == "https://images.pokemontcg.io/base1/68_hires.png":
            img_val = resolved.get("image_url", "https://images.pokemontcg.io/base1/68_hires.png")

        notes_val = str(row.get(col_map.get("notes"), "")).strip()
        pop_10_val = parse_int(row.get(col_map.get("pop_grade10")), 0)

        card_dict = {
            "card_name": c_name,
            "set_name": set_val,
            "card_number": card_num_val,
            "release_year": year_int,
            "language": lang_val,
            "edition": ed_val,
            "rarity": rarity_val,
            "is_error": is_err,
            "error_description": notes_val if is_err else "",
            "est_raw_price": raw_p,
            "est_grade10_price": g10_p,
            "pop_grade10": pop_10_val,
            "pricecharting_url": get_pricecharting_search_url(c_name, set_val, card_num_val),
            "pricecharting_raw": raw_p,
            "pricecharting_grade10": g10_p,
            "image_url": img_val or "https://images.pokemontcg.io/base1/68_hires.png",
            "notes": notes_val,
        }
        cards_to_upsert.append(card_dict)

        owned_flag = str(row.get(col_map.get("owned_status"), "")).strip().lower()
        if owned_flag in ["yes", "true", "1", "owned", "x", "have", "checked"]:
            owned_to_add.append({
                "card_name": c_name,
                "set_name": set_val,
                "card_number": card_num_val,
                "grading_company": "RAW",
                "grade": 0.0,
                "grade_label": "Raw Single",
                "cert_number": "",
                "purchase_price": raw_p or 5.0,
                "purchase_date": datetime.today().strftime("%Y-%m-%d"),
                "edition": ed_val,
                "language": lang_val,
                "is_error": is_err,
                "error_type": notes_val if is_err else None,
                "is_raw": 1,
                "pop_grade10": pop_10_val,
                "image_url": img_val,
                "notes": notes_val,
            })

    upsert_count = bulk_upsert_master_catalog(cards_to_upsert)

    owned_added = 0
    if owned_to_add:
        for oc in owned_to_add:
            add_card_to_collection(oc)
            owned_added += 1

    msg = f"Successfully synced and verified {upsert_count} cards into Master Set Catalog!"
    if owned_added > 0:
        msg += f" (Also imported {owned_added} cards marked as Owned into your Vault)."
    return upsert_count, msg, diagnostics


def sync_from_google_sheets_url(sheet_url: str) -> Tuple[int, str, List[str]]:
    """Downloads public Google Sheets CSV export and syncs into database."""
    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", sheet_url)
    if not match:
        return 0, "Invalid Google Sheets URL format. Please provide a standard Google Sheets link.", []

    doc_id = match.group(1)
    gid_match = re.search(r"[#&?]gid=([0-9]+)", sheet_url)
    gid = gid_match.group(1) if gid_match else "0"

    export_url = f"https://docs.google.com/spreadsheets/d/{doc_id}/export?format=csv&gid={gid}"

    try:
        req = urllib.request.Request(export_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as response:
            csv_content = response.read().decode("utf-8")
        df = pd.read_csv(io.StringIO(csv_content))
        return sync_master_catalog_from_df(df)
    except urllib.error.HTTPError as e:
        if e.code in [401, 403]:
            return 0, "Google Sheets Permission Error (401/403): Sheet is Restricted. Please click 'Share' in Google Sheets and select 'Anyone with the link can view'.", []
        return 0, f"HTTP Error fetching Google Sheet: {e}", []
    except Exception as e:
        return 0, f"Error processing Google Sheet: {e}", []


def bulk_import_collection_from_df(df_input: pd.DataFrame) -> Tuple[int, str]:
    """Imports user's owned cards from a CSV directly into my_collection with metadata resolution."""
    ensure_tables_exist()
    if df_input.empty:
        return 0, "Uploaded CSV is empty."

    col_map = {}
    for col in df_input.columns:
        c = str(col).strip().lower().replace("_", " ").replace("-", " ")
        if any(k in c for k in ["card name", "pokemon", "name"]):
            col_map["card_name"] = col
        elif any(k in c for k in ["set name", "set"]):
            col_map["set_name"] = col
        elif any(k in c for k in ["number", "#"]):
            col_map["card_number"] = col
        elif any(k in c for k in ["company", "grader", "slab"]):
            col_map["grading_company"] = col
        elif any(k in c for k in ["grade"]):
            col_map["grade"] = col
        elif any(k in c for k in ["tier", "label", "grade label"]):
            col_map["grade_label"] = col
        elif any(k in c for k in ["price", "cost"]):
            col_map["purchase_price"] = col
        elif any(k in c for k in ["cert"]):
            col_map["cert_number"] = col
        elif any(k in c for k in ["date"]):
            col_map["purchase_date"] = col
        elif any(k in c for k in ["edition", "ed"]):
            col_map["edition"] = col
        elif any(k in c for k in ["lang"]):
            col_map["language"] = col
        elif any(k in c for k in ["pop"]):
            col_map["pop_grade10"] = col
        elif any(k in c for k in ["image"]):
            col_map["image_url"] = col
        elif any(k in c for k in ["notes"]):
            col_map["notes"] = col

    count = 0
    for _, row in df_input.iterrows():
        raw_name = str(row.get(col_map.get("card_name"), "Vulpix")).strip()
        set_val = str(row.get(col_map.get("set_name"), "Unknown Set")).strip()
        card_num_val = str(row.get(col_map.get("card_number"), "")).strip()

        if not raw_name and not set_val:
            continue

        resolved = resolve_card_metadata(set_val, card_num_val, raw_name)
        c_name = resolved["card_name"] if (raw_name.lower() in ["vulpix", "", "none", "nan", "null"] and resolved["card_name"] != "Vulpix") else (raw_name or "Vulpix")

        co = str(row.get(col_map.get("grading_company"), "RAW")).strip().upper()
        is_raw = 1 if co in ["RAW", "UNGRADED", ""] else 0

        def parse_num(v, default=0.0):
            if pd.isna(v):
                return default
            s = re.sub(r"[^\d.]", "", str(v))
            try:
                return float(s)
            except ValueError:
                return default

        grade_num = parse_num(row.get(col_map.get("grade")), 0.0) if not is_raw else 0.0
        price_num = parse_num(row.get(col_map.get("purchase_price")), 10.0)
        pop_num = int(parse_num(row.get(col_map.get("pop_grade10")), 0))

        img_val = str(row.get(col_map.get("image_url"), "")).strip()
        if not img_val or img_val == "https://images.pokemontcg.io/base1/68_hires.png":
            img_val = resolved.get("image_url", "https://images.pokemontcg.io/base1/68_hires.png")

        card_data = {
            "card_name": c_name,
            "set_name": set_val,
            "card_number": card_num_val,
            "grading_company": co if not is_raw else "RAW",
            "grade": grade_num,
            "grade_label": str(row.get(col_map.get("grade_label"), "Gem Mint" if not is_raw else "Raw Single")).strip(),
            "cert_number": str(row.get(col_map.get("cert_number"), "")).strip(),
            "purchase_price": price_num,
            "purchase_date": str(row.get(col_map.get("purchase_date"), datetime.today().strftime("%Y-%m-%d"))).strip()[:10],
            "edition": str(row.get(col_map.get("edition"), "Unlimited")).strip(),
            "language": str(row.get(col_map.get("language"), "English")).strip(),
            "is_error": 0,
            "error_type": None,
            "is_raw": is_raw,
            "pop_grade10": pop_num,
            "image_url": img_val or "https://images.pokemontcg.io/base1/68_hires.png",
            "notes": str(row.get(col_map.get("notes"), "")).strip(),
        }
        add_card_to_collection(card_data)
        count += 1

    return count, f"Successfully imported {count} cards into your Vault collection!"


def get_csv_template_bytes() -> bytes:
    """Generates a clean starter CSV template bytes."""
    df_template = pd.DataFrame([
        {
            "Card Name": "Vulpix",
            "Set Name": "Base Set",
            "Card Number": "68/102",
            "Release Year": 1999,
            "Language": "English",
            "Edition": "1st Edition",
            "Rarity": "Common",
            "Is Error": "No",
            "Est Raw Price": 8.00,
            "Est Grade 10 Price": 240.00,
            "Pop Grade 10": 185,
            "Owned": "Yes",
            "Image URL": "https://images.pokemontcg.io/base1/68_hires.png",
            "Notes": "1st Edition Base Set.",
        },
        {
            "Card Name": "Blaine's Vulpix",
            "Set Name": "Gym Heroes",
            "Card Number": "65/132",
            "Release Year": 2000,
            "Language": "English",
            "Edition": "1st Edition",
            "Rarity": "Common",
            "Is Error": "No",
            "Est Raw Price": 4.50,
            "Est Grade 10 Price": 85.00,
            "Pop Grade 10": 95,
            "Owned": "No",
            "Image URL": "https://images.pokemontcg.io/gym1/65_hires.png",
            "Notes": "Gym Heroes Blaine's Vulpix.",
        }
    ])
    output = io.StringIO()
    df_template.to_csv(output, index=False)
    return output.getvalue().encode("utf-8")


# =============================================================
# Collection CRUD Operations
# =============================================================

def load_collection_df() -> pd.DataFrame:
    """Load user's collection with calculated market valuations."""
    ensure_tables_exist()
    with get_db_connection() as conn:
        df_col = pd.read_sql_query("SELECT * FROM my_collection ORDER BY purchase_date DESC", conn)
        df_market = pd.read_sql_query(
            "SELECT card_name, grading_company, grade, grade_label, condition_type, total_price, sale_date, scraped_at FROM market_sales ORDER BY COALESCE(sale_date, scraped_at) DESC",
            conn,
        )

    if df_col.empty:
        return df_col

    est_values = []
    gain_dollars = []
    roi_percents = []

    for _, row in df_col.iterrows():
        is_raw = row.get("is_raw", 0)
        cond = "Raw" if is_raw == 1 else "Graded"

        matched = df_market[
            (df_market["card_name"].str.contains(str(row["card_name"]), case=False, na=False, regex=False)) &
            (df_market["condition_type"] == cond)
        ]

        if cond == "Graded" and not matched.empty:
            matched = matched[
                (matched["grading_company"].str.upper() == str(row["grading_company"]).upper()) &
                (matched["grade"] == row["grade"])
            ]

        if not matched.empty:
            recent_prices = matched.head(5)["total_price"].tolist()
            current_val = round(sum(recent_prices) / len(recent_prices), 2)
        else:
            current_val = round(float(row["purchase_price"]) * 1.05, 2)

        cost = float(row["purchase_price"])
        gain = round(current_val - cost, 2)
        roi = round((gain / cost) * 100, 1) if cost > 0 else 0.0

        est_values.append(current_val)
        gain_dollars.append(gain)
        roi_percents.append(roi)

    df_col["current_market_value"] = est_values
    df_col["unrealized_gain"] = gain_dollars
    df_col["roi_percent"] = roi_percents
    return df_col


def add_card_to_collection(card: Dict[str, Any]) -> int:
    """Add a new graded or raw card to personal collection."""
    ensure_tables_exist()
    with get_db_connection() as conn:
        cursor = conn.cursor()

        master_id = card.get("master_card_id")
        if not master_id:
            cursor.execute("""
                SELECT id FROM master_set_catalog
                WHERE card_name = :card_name AND set_name = :set_name
                LIMIT 1;
            """, {"card_name": card.get("card_name"), "set_name": card.get("set_name")})
            row = cursor.fetchone()
            if row:
                master_id = row["id"]

        cursor.execute("""
            INSERT INTO my_collection (
                card_name, set_name, card_number, grading_company,
                grade, grade_label, cert_number, purchase_price, purchase_date,
                edition, language, is_error, error_type, is_raw,
                pop_grade10, pop_pristine10, master_card_id, image_url, notes
            ) VALUES (
                :card_name, :set_name, :card_number, :grading_company,
                :grade, :grade_label, :cert_number, :purchase_price, :purchase_date,
                :edition, :language, :is_error, :error_type, :is_raw,
                :pop_grade10, :pop_pristine10, :master_card_id, :image_url, :notes
            )
        """, {
            "card_name": card.get("card_name", "Vulpix"),
            "set_name": card.get("set_name", "Unknown Set"),
            "card_number": card.get("card_number", ""),
            "grading_company": card.get("grading_company", "RAW"),
            "grade": card.get("grade", 0.0),
            "grade_label": card.get("grade_label", "Gem Mint"),
            "cert_number": card.get("cert_number", ""),
            "purchase_price": card.get("purchase_price", 0.0),
            "purchase_date": card.get("purchase_date", datetime.today().strftime("%Y-%m-%d")),
            "edition": card.get("edition", "Unlimited"),
            "language": card.get("language", "English"),
            "is_error": 1 if card.get("is_error") else 0,
            "error_type": card.get("error_type"),
            "is_raw": 1 if card.get("is_raw") else 0,
            "pop_grade10": int(card.get("pop_grade10") or 0),
            "pop_pristine10": int(card.get("pop_pristine10") or 0),
            "master_card_id": master_id,
            "image_url": card.get("image_url", "https://images.pokemontcg.io/base1/68_hires.png"),
            "notes": card.get("notes", ""),
        })
        return cursor.lastrowid or 0


def update_collection_card(card_id: int, updates: Dict[str, Any]) -> None:
    """Update details of a card in my_collection."""
    ensure_tables_exist()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE my_collection SET
                card_name = :card_name,
                set_name = :set_name,
                card_number = :card_number,
                grading_company = :grading_company,
                grade = :grade,
                grade_label = :grade_label,
                cert_number = :cert_number,
                purchase_price = :purchase_price,
                purchase_date = :purchase_date,
                edition = :edition,
                language = :language,
                is_error = :is_error,
                error_type = :error_type,
                is_raw = :is_raw,
                pop_grade10 = :pop_grade10,
                pop_pristine10 = :pop_pristine10,
                image_url = :image_url,
                notes = :notes
            WHERE id = :id
        """, {
            "id": card_id,
            "card_name": updates.get("card_name", "Vulpix"),
            "set_name": updates.get("set_name", "Unknown Set"),
            "card_number": updates.get("card_number", ""),
            "grading_company": updates.get("grading_company", "RAW"),
            "grade": float(updates.get("grade", 0.0)),
            "grade_label": updates.get("grade_label", "Gem Mint"),
            "cert_number": updates.get("cert_number", ""),
            "purchase_price": float(updates.get("purchase_price", 0.0)),
            "purchase_date": str(updates.get("purchase_date", "2024-01-01")),
            "edition": updates.get("edition", "Unlimited"),
            "language": updates.get("language", "English"),
            "is_error": 1 if updates.get("is_error") else 0,
            "error_type": updates.get("error_type"),
            "is_raw": 1 if updates.get("is_raw") else 0,
            "pop_grade10": int(updates.get("pop_grade10", 0)),
            "pop_pristine10": int(updates.get("pop_pristine10", 0)),
            "image_url": updates.get("image_url", "https://images.pokemontcg.io/base1/68_hires.png"),
            "notes": updates.get("notes", ""),
        })


def delete_card_from_collection(card_id: int) -> None:
    """Remove a card from personal collection."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM my_collection WHERE id = ?", (card_id,))


def update_card_image_override(table_name: str, record_id: int, new_image_url: str) -> None:
    """Updates image URL for either a master_set_catalog card or a my_collection card."""
    valid_table = "master_set_catalog" if table_name == "master_set_catalog" else "my_collection"
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(f"UPDATE {valid_table} SET image_url = ? WHERE id = ?", (new_image_url, record_id))


# =============================================================
# Market Data & KPI Queries
# =============================================================

def load_market_sales_df() -> pd.DataFrame:
    """Load historical and scraped market sales dataset."""
    ensure_tables_exist()
    with get_db_connection() as conn:
        df = pd.read_sql_query("SELECT * FROM market_sales ORDER BY COALESCE(sale_date, scraped_at) DESC", conn)
    return df


def load_deals_df(deal_filter: Optional[str] = None, condition_filter: Optional[str] = None) -> pd.DataFrame:
    """Load AI-appraised deals with multi-tier and condition filters."""
    df = load_market_sales_df()
    if df.empty:
        return df

    if condition_filter == "Grade 10 Slabs Only":
        df = df[(df["condition_type"] == "Graded") & (df["grade"] == 10.0)]
    elif condition_filter == "Raw Singles Only":
        df = df[df["condition_type"] == "Raw"]

    if deal_filter == "amazing_deal":
        return df[df["deal_rating"] == "amazing_deal"]
    elif deal_filter == "great_and_amazing":
        return df[df["deal_rating"].isin(["amazing_deal", "great_deal"])]
    elif deal_filter == "all_deals":
        return df[df["deal_rating"].isin(["amazing_deal", "great_deal", "good_deal"])]
    return df


def get_portfolio_metrics() -> Dict[str, Any]:
    """Calculate portfolio summary KPIs."""
    df_col = load_collection_df()
    df_sales = load_market_sales_df()

    if df_col.empty:
        return {
            "total_value": 0.0,
            "total_cost": 0.0,
            "net_gain": 0.0,
            "roi_percent": 0.0,
            "total_slabs": 0,
            "total_raw": 0,
            "amazing_deals_count": len(df_sales[df_sales["deal_rating"] == "amazing_deal"]) if not df_sales.empty else 0,
            "great_deals_count": len(df_sales[df_sales["deal_rating"] == "great_deal"]) if not df_sales.empty else 0,
        }

    total_value = round(df_col["current_market_value"].sum(), 2)
    total_cost = round(df_col["purchase_price"].sum(), 2)
    net_gain = round(total_value - total_cost, 2)
    roi_percent = round((net_gain / total_cost) * 100, 1) if total_cost > 0 else 0.0

    slabs_count = len(df_col[df_col["is_raw"] == 0])
    raw_count = len(df_col[df_col["is_raw"] == 1])

    amazing_deals_count = len(df_sales[df_sales["deal_rating"] == "amazing_deal"]) if not df_sales.empty else 0
    great_deals_count = len(df_sales[df_sales["deal_rating"] == "great_deal"]) if not df_sales.empty else 0

    return {
        "total_value": total_value,
        "total_cost": total_cost,
        "net_gain": net_gain,
        "roi_percent": roi_percent,
        "total_slabs": slabs_count,
        "total_raw": raw_count,
        "amazing_deals_count": amazing_deals_count,
        "great_deals_count": great_deals_count,
    }
