"""
Database management module for The Vulpix Vault.
Configures SQLite with WAL mode, creates tables, and provides helper queries.
"""

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, List, Optional

DEFAULT_DB_PATH = os.getenv("DB_PATH", os.path.join(os.path.dirname(__file__), "..", "data", "vulpix_vault.db"))


def get_db_path(db_path: Optional[str] = None) -> str:
    path = db_path or os.getenv("DB_PATH", DEFAULT_DB_PATH)
    # Ensure directory exists
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    return path


@contextmanager
def get_db_connection(db_path: Optional[str] = None):
    """Context manager for SQLite connection with WAL mode and row factory."""
    path = get_db_path(db_path)
    conn = sqlite3.connect(path, timeout=10.0)
    conn.row_factory = sqlite3.Row
    try:
        # Enable Write-Ahead Logging for non-blocking concurrent reads/writes
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


def init_db(db_path: Optional[str] = None) -> None:
    """Initialize database schema with my_collection and market_sales tables."""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()

        # Table: Personal Collection of Graded Slabs
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

        # Table: Historical and Scraped Market Sales / Listings
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

        # Performance Indexes
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_market_lookup 
            ON market_sales(card_name, grading_company, grade);
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_market_scraped_at 
            ON market_sales(scraped_at);
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_market_deal 
            ON market_sales(deal_rating);
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_collection_grade 
            ON my_collection(card_name, grading_company, grade);
        """)


def is_listing_recorded(listing_id: str, db_path: Optional[str] = None) -> bool:
    """Check if an eBay listing has already been recorded in market_sales."""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM market_sales WHERE listing_id = ? LIMIT 1;", (listing_id,))
        return cursor.fetchone() is not None


def insert_market_sale(sale: Dict[str, Any], db_path: Optional[str] = None) -> int:
    """Insert or ignore a market sale / listing record."""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR IGNORE INTO market_sales (
                listing_id, title, card_name, grading_company, grade,
                price, shipping_cost, total_price, listing_url, image_url,
                listing_type, deal_rating, fair_value_estimate,
                discount_percentage, ai_rationale, sale_date
            ) VALUES (
                :listing_id, :title, :card_name, :grading_company, :grade,
                :price, :shipping_cost, :total_price, :listing_url, :image_url,
                :listing_type, :deal_rating, :fair_value_estimate,
                :discount_percentage, :ai_rationale, :sale_date
            )
        """, sale)
        return cursor.lastrowid or 0


def update_market_sale_appraisal(
    listing_id: str, appraisal: Dict[str, Any], db_path: Optional[str] = None
) -> None:
    """Update deal appraisal fields for an existing listing."""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE market_sales SET
                deal_rating = :deal_rating,
                fair_value_estimate = :fair_value_estimate,
                discount_percentage = :discount_percentage,
                ai_rationale = :ai_rationale
            WHERE listing_id = :listing_id
        """, {
            "listing_id": listing_id,
            "deal_rating": appraisal.get("deal_rating", "unrated"),
            "fair_value_estimate": appraisal.get("fair_value_estimate"),
            "discount_percentage": appraisal.get("discount_percentage"),
            "ai_rationale": appraisal.get("ai_rationale") or appraisal.get("rationale"),
        })


def get_recent_comparables(
    card_name: str,
    grading_company: Optional[str] = None,
    grade: Optional[float] = None,
    limit: int = 10,
    db_path: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Retrieve the last N comparable sales for appraisal context."""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        query = """
            SELECT card_name, grading_company, grade, total_price, sale_date, scraped_at, deal_rating
            FROM market_sales
            WHERE card_name LIKE ?
        """
        params: List[Any] = [f"%{card_name}%"]

        if grading_company:
            query += " AND UPPER(grading_company) = UPPER(?)"
            params.append(grading_company)

        if grade is not None:
            query += " AND grade = ?"
            params.append(grade)

        query += " ORDER BY COALESCE(sale_date, scraped_at) DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]


def get_collection(db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Fetch all cards in personal collection."""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, card_name, set_name, card_number, grading_company, 
                   grade, cert_number, purchase_price, purchase_date, image_url, notes
            FROM my_collection
            ORDER BY purchase_date DESC;
        """)
        return [dict(row) for row in cursor.fetchall()]


def insert_collection_card(card: Dict[str, Any], db_path: Optional[str] = None) -> int:
    """Add a new graded card to the personal collection."""
    with get_db_connection(db_path) as conn:
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


def get_market_sales(
    limit: int = 100, deal_filter: Optional[str] = None, db_path: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Fetch recent market sales with optional deal rating filter."""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        if deal_filter:
            cursor.execute("""
                SELECT * FROM market_sales
                WHERE deal_rating = ?
                ORDER BY scraped_at DESC LIMIT ?;
            """, (deal_filter, limit))
        else:
            cursor.execute("""
                SELECT * FROM market_sales
                ORDER BY scraped_at DESC LIMIT ?;
            """, (limit,))
        return [dict(row) for row in cursor.fetchall()]
