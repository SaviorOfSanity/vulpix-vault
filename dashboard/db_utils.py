"""
Database utility module for Streamlit Dashboard.
Handles Master Set analytics, Google Sheets/CSV sync, portfolio valuations, and collection CRUD.
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

DEFAULT_DB_PATH = os.getenv("DB_PATH", os.path.join(os.path.dirname(__file__), "..", "data", "vulpix_vault.db"))


def get_db_path() -> str:
    path = os.getenv("DB_PATH", DEFAULT_DB_PATH)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    return path


@contextmanager
def get_db_connection():
    """Context manager for SQLite with WAL mode."""
    path = get_db_path()
    conn = sqlite3.connect(path, timeout=10.0)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA busy_timeout = 5000;")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def ensure_tables_exist():
    """Ensure database schema is initialized and migrated."""
    import sys
    sys.path.append(os.path.join(os.path.dirname(__file__), "..", "scraper"))
    try:
        from db import init_db
        from seed_data import seed_database_if_empty
        init_db(get_db_path())
        seed_database_if_empty(get_db_path())
    except Exception as e:
        print(f"[DB] Init error: {e}")


# =============================================================
# Master Set Progress & Catalog Queries
# =============================================================

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
        # Match by card_name, set_name, edition, language
        matched = df_col[
            (df_col["card_name"].str.strip().str.lower() == str(master_row["card_name"]).strip().lower()) &
            (df_col["set_name"].str.strip().str.lower() == str(master_row["set_name"]).strip().lower()) &
            (df_col["edition"].str.strip().str.lower() == str(master_row["edition"]).strip().lower())
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


def sync_master_catalog_from_df(df_input: pd.DataFrame) -> Tuple[int, str]:
    """
    Parses an uploaded CSV or Google Sheets dataframe, maps standard column headers,
    and bulk upserts them into master_set_catalog.
    """
    ensure_tables_exist()
    if df_input.empty:
        return 0, "Input table is empty."

    # Column Normalization Mapping
    col_map = {}
    for col in df_input.columns:
        c_clean = str(col).strip().lower().replace("_", " ").replace("-", " ")
        if any(k in c_clean for k in ["card name", "pokemon", "name"]):
            col_map["card_name"] = col
        elif any(k in c_clean for k in ["set name", "set", "expansion"]):
            col_map["set_name"] = col
        elif any(k in c_clean for k in ["card number", "number", "card #", "#"]):
            col_map["card_number"] = col
        elif any(k in c_clean for k in ["release year", "year"]):
            col_map["release_year"] = col
        elif any(k in c_clean for k in ["language", "lang"]):
            col_map["language"] = col
        elif any(k in c_clean for k in ["edition", "variant", "ed"]):
            col_map["edition"] = col
        elif any(k in c_clean for k in ["rarity"]):
            col_map["rarity"] = col
        elif any(k in c_clean for k in ["is error", "error"]):
            col_map["is_error"] = col
        elif any(k in c_clean for k in ["raw price", "est raw", "raw"]):
            col_map["est_raw_price"] = col
        elif any(k in c_clean for k in ["grade 10", "psa 10", "10 price", "est 10"]):
            col_map["est_grade10_price"] = col
        elif any(k in c_clean for k in ["image", "url", "image url"]):
            col_map["image_url"] = col
        elif any(k in c_clean for k in ["notes", "description"]):
            col_map["notes"] = col

    if "card_name" not in col_map and "set_name" not in col_map:
        # Fallback: assume column 0 is card_name, column 1 is set_name
        cols = list(df_input.columns)
        if len(cols) >= 2:
            col_map["card_name"] = cols[0]
            col_map["set_name"] = cols[1]

    cards_to_upsert = []
    for _, row in df_input.iterrows():
        c_name = str(row.get(col_map.get("card_name"), "Vulpix")).strip()
        if not c_name or c_name.lower() == "nan":
            continue

        raw_price_val = row.get(col_map.get("est_raw_price"), 0.0)
        grade10_price_val = row.get(col_map.get("est_grade10_price"), 0.0)

        # Clean prices
        def parse_price(v):
            if pd.isna(v):
                return 0.0
            s = re.sub(r"[^\d.]", "", str(v))
            try:
                return float(s)
            except ValueError:
                return 0.0

        raw_p = parse_price(raw_price_val)
        g10_p = parse_price(grade10_price_val)

        err_val = row.get(col_map.get("is_error"), 0)
        is_err = 1 if str(err_val).lower() in ["1", "true", "yes", "error"] else 0

        year_val = row.get(col_map.get("release_year"), 2000)
        try:
            year_int = int(re.sub(r"[^\d]", "", str(year_val))[:4]) if str(year_val) else 2000
        except ValueError:
            year_int = 2000

        card_dict = {
            "card_name": c_name,
            "set_name": str(row.get(col_map.get("set_name"), "Unknown Set")).strip(),
            "card_number": str(row.get(col_map.get("card_number"), "")).strip(),
            "release_year": year_int,
            "language": str(row.get(col_map.get("language"), "English")).strip(),
            "edition": str(row.get(col_map.get("edition"), "Unlimited")).strip(),
            "rarity": str(row.get(col_map.get("rarity"), "Common")).strip(),
            "is_error": is_err,
            "error_description": str(row.get(col_map.get("notes"), "")) if is_err else "",
            "est_raw_price": raw_p,
            "est_grade10_price": g10_p,
            "image_url": str(row.get(col_map.get("image_url"), "https://images.pokemontcg.io/base1/68_hires.png")).strip(),
            "notes": str(row.get(col_map.get("notes"), "")).strip(),
        }
        cards_to_upsert.append(card_dict)

    import sys
    sys.path.append(os.path.join(os.path.dirname(__file__), "..", "scraper"))
    from db import bulk_upsert_master_catalog
    count = bulk_upsert_master_catalog(cards_to_upsert, db_path=get_db_path())
    return count, f"Successfully imported and updated {count} cards in Master Set Catalog!"


def sync_from_google_sheets_url(sheet_url: str) -> Tuple[int, str]:
    """Downloads public Google Sheets CSV and syncs into database."""
    # Convert edit URL to CSV export URL
    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", sheet_url)
    if not match:
        return 0, "Invalid Google Sheets URL. Please provide a standard Google Sheets share link."

    doc_id = match.group(1)
    # Extract gid if present
    gid_match = re.search(r"[#&?]gid=([0-9]+)", sheet_url)
    gid = gid_match.group(1) if gid_match else "0"

    export_url = f"https://docs.google.com/spreadsheets/d/{doc_id}/export?format=csv&gid={gid}"

    try:
        req = urllib.request.Request(export_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=12) as response:
            csv_content = response.read().decode("utf-8")
        df = pd.read_csv(io.StringIO(csv_content))
        return sync_master_catalog_from_df(df)
    except urllib.error.HTTPError as e:
        if e.code == 401 or e.code == 403:
            return 0, "Google Sheets Access Error (401/403): The sheet is private. Please click 'Share' in Google Sheets and select 'Anyone with the link can view'."
        return 0, f"HTTP Error fetching Google Sheet: {e}"
    except Exception as e:
        return 0, f"Error processing Google Sheet: {e}"


# =============================================================
# Collection & Market Data Queries
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


def load_market_sales_df() -> pd.DataFrame:
    """Load historical and scraped market sales dataset."""
    ensure_tables_exist()
    with get_db_connection() as conn:
        df = pd.read_sql_query(
            """
            SELECT * FROM market_sales
            ORDER BY COALESCE(sale_date, scraped_at) DESC
            """,
            conn,
        )
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


def add_card_to_collection(card: Dict[str, Any]) -> int:
    """Add a new graded or raw card to personal collection."""
    import sys
    sys.path.append(os.path.join(os.path.dirname(__file__), "..", "scraper"))
    from db import insert_collection_card
    return insert_collection_card(card, db_path=get_db_path())


def delete_card_from_collection(card_id: int) -> None:
    """Remove a card from personal collection."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM my_collection WHERE id = ?", (card_id,))


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
