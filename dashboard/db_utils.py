"""
Database utility module for Streamlit Dashboard.
100% Self-contained: manages SQLite WAL mode, Master Set catalog, collection CRUD,
editing, Google Sheets sync, and CSV bulk import of owned and master cards.
"""

import io
import os
import re
import sqlite3
import urllib.parse
import urllib.request
from contextlib import contextmanager
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd

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
    """Ensure database schema is created and auto-migrated."""
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
                image_url TEXT,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(card_name, set_name, card_number, language, edition, is_error)
            );
        """)

        # 2. Personal Collection of Slabs & Raw Cards
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
                master_card_id INTEGER,
                image_url TEXT,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 3. Market Sales & Listing Tracking
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

        # Auto-migration for my_collection
        for col, ctype in [
            ("edition", "TEXT DEFAULT 'Unlimited'"),
            ("language", "TEXT DEFAULT 'English'"),
            ("is_error", "INTEGER DEFAULT 0"),
            ("error_type", "TEXT"),
            ("grade_label", "TEXT DEFAULT 'Gem Mint'"),
            ("is_raw", "INTEGER DEFAULT 0"),
            ("master_card_id", "INTEGER"),
        ]:
            _add_column_if_missing(cursor, "my_collection", col, ctype)

        # Auto-migration for market_sales
        for col, ctype in [
            ("grade_label", "TEXT DEFAULT 'Gem Mint'"),
            ("condition_type", "TEXT DEFAULT 'Graded'"),
            ("edition", "TEXT DEFAULT 'Unlimited'"),
            ("language", "TEXT DEFAULT 'English'"),
            ("is_error", "INTEGER DEFAULT 0"),
        ]:
            _add_column_if_missing(cursor, "market_sales", col, ctype)

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_master_search ON master_set_catalog(card_name, set_name, language, edition);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_market_lookup ON market_sales(card_name, grading_company, grade, condition_type);")


# =============================================================
# Master Set Catalog Operations
# =============================================================

def bulk_upsert_master_catalog(cards: List[Dict[str, Any]]) -> int:
    """Bulk insert or update cards in master_set_catalog."""
    ensure_tables_exist()
    count = 0
    with get_db_connection() as conn:
        cursor = conn.cursor()
        for card in cards:
            params = {
                "card_name": str(card.get("card_name", "Vulpix")).strip(),
                "set_name": str(card.get("set_name", "Unknown Set")).strip(),
                "card_number": str(card.get("card_number", "")).strip(),
                "release_year": int(card.get("release_year") or 2000),
                "language": str(card.get("language", "English")).strip(),
                "edition": str(card.get("edition", "Unlimited")).strip(),
                "rarity": str(card.get("rarity", "Common")).strip(),
                "is_error": 1 if card.get("is_error") in [1, True, "1", "true", "True", "yes"] else 0,
                "error_description": str(card.get("error_description", "")).strip(),
                "est_raw_price": float(card.get("est_raw_price") or 0.0),
                "est_grade10_price": float(card.get("est_grade10_price") or 0.0),
                "image_url": str(card.get("image_url", "https://images.pokemontcg.io/base1/68_hires.png")).strip(),
                "notes": str(card.get("notes", "")).strip(),
            }
            cursor.execute("""
                INSERT INTO master_set_catalog (
                    card_name, set_name, card_number, release_year,
                    language, edition, rarity, is_error, error_description,
                    est_raw_price, est_grade10_price, image_url, notes
                ) VALUES (
                    :card_name, :set_name, :card_number, :release_year,
                    :language, :edition, :rarity, :is_error, :error_description,
                    :est_raw_price, :est_grade10_price, :image_url, :notes
                )
                ON CONFLICT(card_name, set_name, card_number, language, edition, is_error)
                DO UPDATE SET
                    release_year = excluded.release_year,
                    rarity = excluded.rarity,
                    error_description = excluded.error_description,
                    est_raw_price = CASE WHEN excluded.est_raw_price > 0 THEN excluded.est_raw_price ELSE master_set_catalog.est_raw_price END,
                    est_grade10_price = CASE WHEN excluded.est_grade10_price > 0 THEN excluded.est_grade10_price ELSE master_set_catalog.est_grade10_price END,
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
            "image_url": updates.get("image_url", "https://images.pokemontcg.io/base1/68_hires.png"),
            "notes": updates.get("notes", ""),
        })


def load_master_catalog_df() -> pd.DataFrame:
    """Loads the Master Set catalog with real-time user owned status."""
    ensure_tables_exist()
    with get_db_connection() as conn:
        df_master = pd.read_sql_query(
            "SELECT * FROM master_set_catalog ORDER BY release_year ASC, set_name ASC, card_number ASC",
            conn,
        )
        df_col = pd.read_sql_query("SELECT * FROM my_collection", conn)

    if df_master.empty:
        return df_master

    is_owned_list = []
    owned_copies_list = []
    owned_details_list = []

    for _, master_row in df_master.iterrows():
        # Match by master_card_id if available, or normalized match
        m_id = master_row["id"]
        matched = df_col[df_col["master_card_id"] == m_id]

        if matched.empty:
            # Secondary smart match
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

def sync_master_catalog_from_df(df_input: pd.DataFrame) -> Tuple[int, str]:
    """
    Parses any CSV or Google Sheets dataframe with dynamic header detection.
    Also automatically adds cards to my_collection if an 'Owned' column indicates ownership!
    """
    ensure_tables_exist()
    if df_input.empty:
        return 0, "Uploaded spreadsheet is empty."

    # Dynamic Column Mapping
    col_map = {}
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
        elif any(k in c for k in ["image", "url", "picture"]):
            col_map["image_url"] = col
        elif any(k in c for k in ["notes", "description", "details", "comments"]):
            col_map["notes"] = col
        elif any(k in c for k in ["owned", "have", "in collection", "collected", "status", "got"]):
            col_map["owned_status"] = col

    # Fallback to column positions if names not found
    cols = list(df_input.columns)
    if "card_name" not in col_map and len(cols) >= 1:
        col_map["card_name"] = cols[0]
    if "set_name" not in col_map and len(cols) >= 2:
        col_map["set_name"] = cols[1]

    cards_to_upsert = []
    owned_to_add = []

    def parse_float(v, default=0.0):
        if pd.isna(v):
            return default
        s = re.sub(r"[^\d.]", "", str(v))
        try:
            return float(s)
        except ValueError:
            return default

    for _, row in df_input.iterrows():
        c_name = str(row.get(col_map.get("card_name"), "Vulpix")).strip()
        if not c_name or c_name.lower() in ["nan", "null", ""]:
            continue

        raw_p = parse_float(row.get(col_map.get("est_raw_price")), 2.0)
        g10_p = parse_float(row.get(col_map.get("est_grade10_price")), 45.0)

        err_val = row.get(col_map.get("is_error"), 0)
        is_err = 1 if str(err_val).lower() in ["1", "true", "yes", "error"] else 0

        year_val = row.get(col_map.get("release_year"), 2000)
        try:
            year_int = int(re.sub(r"[^\d]", "", str(year_val))[:4]) if str(year_val) else 2000
        except ValueError:
            year_int = 2000

        set_val = str(row.get(col_map.get("set_name"), "Unknown Set")).strip()
        card_num_val = str(row.get(col_map.get("card_number"), "")).strip()
        lang_val = str(row.get(col_map.get("language"), "English")).strip()
        ed_val = str(row.get(col_map.get("edition"), "Unlimited")).strip()
        rarity_val = str(row.get(col_map.get("rarity"), "Common")).strip()
        img_val = str(row.get(col_map.get("image_url"), "https://images.pokemontcg.io/base1/68_hires.png")).strip()
        notes_val = str(row.get(col_map.get("notes"), "")).strip()

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
            "image_url": img_val or "https://images.pokemontcg.io/base1/68_hires.png",
            "notes": notes_val,
        }
        cards_to_upsert.append(card_dict)

        # Check if row is flagged as owned in the user's sheet
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
                "purchase_date": "2024-01-01",
                "edition": ed_val,
                "language": lang_val,
                "is_error": is_err,
                "error_type": notes_val if is_err else None,
                "is_raw": 1,
                "image_url": img_val,
                "notes": notes_val,
            })

    upsert_count = bulk_upsert_master_catalog(cards_to_upsert)

    # If owned cards were detected, add them into collection
    owned_added = 0
    if owned_to_add:
        for oc in owned_to_add:
            add_card_to_collection(oc)
            owned_added += 1

    msg = f"Successfully synced {upsert_count} cards into Master Set Catalog!"
    if owned_added > 0:
        msg += f" (Also imported {owned_added} cards marked as Owned into your Vault)."
    return upsert_count, msg


def sync_from_google_sheets_url(sheet_url: str) -> Tuple[int, str]:
    """Downloads public Google Sheets CSV export and syncs into database."""
    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", sheet_url)
    if not match:
        return 0, "Invalid Google Sheets URL format. Please provide a standard Google Sheets link."

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
            return 0, "Google Sheets Permission Error (401/403): Sheet is Restricted. Please click 'Share' in Google Sheets and select 'Anyone with the link can view'."
        return 0, f"HTTP Error fetching Google Sheet: {e}"
    except Exception as e:
        return 0, f"Error processing Google Sheet: {e}"


def bulk_import_collection_from_df(df_input: pd.DataFrame) -> Tuple[int, str]:
    """Imports user's owned cards from a CSV directly into my_collection."""
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
        elif any(k in c for k in ["image"]):
            col_map["image_url"] = col
        elif any(k in c for k in ["notes"]):
            col_map["notes"] = col

    count = 0
    for _, row in df_input.iterrows():
        c_name = str(row.get(col_map.get("card_name"), "Vulpix")).strip()
        if not c_name or c_name.lower() in ["nan", "null", ""]:
            continue

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

        card_data = {
            "card_name": c_name,
            "set_name": str(row.get(col_map.get("set_name"), "Unknown Set")).strip(),
            "card_number": str(row.get(col_map.get("card_number"), "")).strip(),
            "grading_company": co if not is_raw else "RAW",
            "grade": grade_num,
            "grade_label": str(row.get(col_map.get("grade_label"), "Gem Mint" if not is_raw else "Raw Single")).strip(),
            "cert_number": str(row.get(col_map.get("cert_number"), "")).strip(),
            "purchase_price": price_num,
            "purchase_date": str(row.get(col_map.get("purchase_date"), "2024-01-01")).strip()[:10],
            "edition": str(row.get(col_map.get("edition"), "Unlimited")).strip(),
            "language": str(row.get(col_map.get("language"), "English")).strip(),
            "is_error": 0,
            "error_type": None,
            "is_raw": is_raw,
            "image_url": str(row.get(col_map.get("image_url"), "https://images.pokemontcg.io/base1/68_hires.png")).strip(),
            "notes": str(row.get(col_map.get("notes"), "")).strip(),
        }
        add_card_to_collection(card_data)
        count += 1

    return count, f"Successfully imported {count} cards into your Vault collection!"


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

        # Try to resolve master_card_id if not present
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
                master_card_id, image_url, notes
            ) VALUES (
                :card_name, :set_name, :card_number, :grading_company,
                :grade, :grade_label, :cert_number, :purchase_price, :purchase_date,
                :edition, :language, :is_error, :error_type, :is_raw,
                :master_card_id, :image_url, :notes
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
            "purchase_date": card.get("purchase_date", "2024-01-01"),
            "edition": card.get("edition", "Unlimited"),
            "language": card.get("language", "English"),
            "is_error": 1 if card.get("is_error") else 0,
            "error_type": card.get("error_type"),
            "is_raw": 1 if card.get("is_raw") else 0,
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
