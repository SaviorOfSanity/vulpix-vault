"""
Database utility module for Streamlit Dashboard.
Handles cached queries, portfolio analytics, and collection updates.
"""

import os
import sqlite3
from contextlib import contextmanager
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd

DEFAULT_DB_PATH = os.getenv("DB_PATH", os.path.join(os.path.dirname(__file__), "..", "data", "vulpix_vault.db"))


def get_db_path() -> str:
    path = os.getenv("DB_PATH", DEFAULT_DB_PATH)
    # Ensure directory exists
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
    """Ensure database schema is created before dashboard queries."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS my_collection (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                card_name TEXT NOT NULL,
                set_name TEXT NOT NULL,
                card_number TEXT,
                grading_company TEXT NOT NULL,
                grade REAL NOT NULL,
                cert_number TEXT,
                purchase_price REAL NOT NULL,
                purchase_date TEXT NOT NULL,
                image_url TEXT,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS market_sales (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                listing_id TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL,
                card_name TEXT NOT NULL,
                grading_company TEXT,
                grade REAL,
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


def load_collection_df() -> pd.DataFrame:
    """Load user's graded slab collection with calculated market valuations."""
    ensure_tables_exist()
    with get_db_connection() as conn:
        df_col = pd.read_sql_query("SELECT * FROM my_collection ORDER BY purchase_date DESC", conn)
        df_market = pd.read_sql_query(
            "SELECT card_name, grading_company, grade, total_price, sale_date, scraped_at FROM market_sales ORDER BY COALESCE(sale_date, scraped_at) DESC",
            conn,
        )

    if df_col.empty:
        return df_col

    # Compute current estimated market value for each slab based on latest sales
    est_values = []
    gain_dollars = []
    roi_percents = []

    for _, row in df_col.iterrows():
        # Match latest market sales for same card, grading company, and grade
        matched = df_market[
            (df_market["card_name"].str.contains(row["card_name"][:12], case=False, na=False)) &
            (df_market["grading_company"].str.upper() == str(row["grading_company"]).upper()) &
            (df_market["grade"] == row["grade"])
        ]

        if not matched.empty:
            # Recent median price as current market value
            recent_prices = matched.head(5)["total_price"].tolist()
            current_val = round(sum(recent_prices) / len(recent_prices), 2)
        else:
            # Fallback to purchase price with modest appreciation baseline
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
            SELECT id, listing_id, title, card_name, grading_company, grade,
                   price, shipping_cost, total_price, listing_url, image_url,
                   listing_type, deal_rating, fair_value_estimate,
                   discount_percentage, ai_rationale, sale_date, scraped_at
            FROM market_sales
            ORDER BY COALESCE(sale_date, scraped_at) DESC
            """,
            conn,
        )
    return df


def load_deals_df(deal_filter: Optional[str] = None) -> pd.DataFrame:
    """Load AI-appraised deals."""
    df = load_market_sales_df()
    if df.empty:
        return df

    if deal_filter == "amazing_deal":
        return df[df["deal_rating"] == "amazing_deal"]
    elif deal_filter == "all_deals":
        return df[df["deal_rating"].isin(["amazing_deal", "good_deal"])]
    return df


def add_card_to_collection(card: Dict[str, Any]) -> int:
    """Add a new graded card to personal collection."""
    ensure_tables_exist()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO my_collection (
                card_name, set_name, card_number, grading_company,
                grade, cert_number, purchase_price, purchase_date,
                image_url, notes
            ) VALUES (
                :card_name, :set_name, :card_number, :grading_company,
                :grade, :cert_number, :purchase_price, :purchase_date,
                :image_url, :notes
            )
        """, card)
        return cursor.lastrowid or 0


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
            "amazing_deals_count": len(df_sales[df_sales["deal_rating"] == "amazing_deal"]) if not df_sales.empty else 0,
            "best_performer": None,
        }

    total_value = round(df_col["current_market_value"].sum(), 2)
    total_cost = round(df_col["purchase_price"].sum(), 2)
    net_gain = round(total_value - total_cost, 2)
    roi_percent = round((net_gain / total_cost) * 100, 1) if total_cost > 0 else 0.0

    best_row = df_col.sort_values(by="unrealized_gain", ascending=False).iloc[0] if not df_col.empty else None
    amazing_deals_count = len(df_sales[df_sales["deal_rating"] == "amazing_deal"]) if not df_sales.empty else 0

    return {
        "total_value": total_value,
        "total_cost": total_cost,
        "net_gain": net_gain,
        "roi_percent": roi_percent,
        "total_slabs": len(df_col),
        "amazing_deals_count": amazing_deals_count,
        "best_performer": f"{best_row['card_name']} ({best_row['grading_company']} {best_row['grade']})" if best_row is not None else "N/A",
    }
