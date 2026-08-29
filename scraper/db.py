"""
Database management module for The Vulpix Vault.
Configures SQLite with WAL mode, auto-migrates schemas, creates master_set_catalog,
and provides helper queries for Master Set completion and multi-tier pricing.
"""

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, List, Optional

DEFAULT_DB_PATH = os.getenv("DB_PATH", os.path.join(os.path.dirname(__file__), "..", "data", "vulpix_vault.db"))


def get_db_path(db_path: Optional[str] = None) -> str:
    path = db_path or os.getenv("DB_PATH", DEFAULT_DB_PATH)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    return path


@contextmanager
def get_db_connection(db_path: Optional[str] = None):
    """Context manager for SQLite connection with WAL mode and row factory."""
    path = get_db_path(db_path)
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


def init_db(db_path: Optional[str] = None) -> None:
    """Initialize or migrate database schema with master_set_catalog, my_collection, and market_sales."""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()

        # 1. Master Set Catalog (The definitive list of every known Vulpix card)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS master_set_catalog (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                card_name TEXT NOT NULL,
                set_name TEXT NOT NULL,
                card_number TEXT,
                release_year INTEGER,
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
                grading_company TEXT NOT NULL,
                grade REAL NOT NULL,
                cert_number TEXT,
                purchase_price REAL NOT NULL,
                purchase_date TEXT NOT NULL,
                image_url TEXT,
                notes TEXT,
                edition TEXT DEFAULT 'Unlimited',
                language TEXT DEFAULT 'English',
                is_error INTEGER DEFAULT 0,
                error_type TEXT,
                grade_label TEXT DEFAULT 'Gem Mint',
                is_raw INTEGER DEFAULT 0,
                master_card_id INTEGER,
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

        # Auto-migration for existing tables (ensure columns exist)
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

        for col, ctype in [
            ("grade_label", "TEXT DEFAULT 'Gem Mint'"),
            ("condition_type", "TEXT DEFAULT 'Graded'"),
            ("edition", "TEXT DEFAULT 'Unlimited'"),
            ("language", "TEXT DEFAULT 'English'"),
            ("is_error", "INTEGER DEFAULT 0"),
        ]:
            _add_column_if_missing(cursor, "market_sales", col, ctype)

        # Performance Indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_master_search ON master_set_catalog(card_name, set_name, language, edition);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_market_lookup ON market_sales(card_name, grading_company, grade, condition_type);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_market_deal ON market_sales(deal_rating);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_collection_lookup ON my_collection(card_name, grading_company, grade, language, edition);")


# =============================================================
# Master Set Catalog Queries
# =============================================================

def get_master_set_catalog(db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Fetch the full Master Set catalog."""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM master_set_catalog
            ORDER BY release_year ASC, set_name ASC, card_number ASC;
        """)
        return [dict(row) for row in cursor.fetchall()]


def upsert_master_card(card: Dict[str, Any], db_path: Optional[str] = None) -> int:
    """Insert or update a card in the master catalog."""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
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
                est_raw_price = COALESCE(NULLIF(excluded.est_raw_price, 0), master_set_catalog.est_raw_price),
                est_grade10_price = COALESCE(NULLIF(excluded.est_grade10_price, 0), master_set_catalog.est_grade10_price),
                image_url = COALESCE(excluded.image_url, master_set_catalog.image_url),
                notes = COALESCE(excluded.notes, master_set_catalog.notes);
        """, card)
        return cursor.lastrowid or 0


def bulk_upsert_master_catalog(cards: List[Dict[str, Any]], db_path: Optional[str] = None) -> int:
    """Bulk insert or update a list of master set cards."""
    count = 0
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        for card in cards:
            params = {
                "card_name": card.get("card_name", "Vulpix"),
                "set_name": card.get("set_name", "Unknown Set"),
                "card_number": str(card.get("card_number", "")),
                "release_year": int(card.get("release_year") or 2000),
                "language": card.get("language", "English"),
                "edition": card.get("edition", "Unlimited"),
                "rarity": card.get("rarity", "Common"),
                "is_error": 1 if card.get("is_error") in [1, True, "1", "true", "True", "yes"] else 0,
                "error_description": card.get("error_description", ""),
                "est_raw_price": float(card.get("est_raw_price") or 0.0),
                "est_grade10_price": float(card.get("est_grade10_price") or 0.0),
                "image_url": card.get("image_url", "https://images.pokemontcg.io/base1/68_hires.png"),
                "notes": card.get("notes", ""),
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
                    est_raw_price = COALESCE(NULLIF(excluded.est_raw_price, 0), master_set_catalog.est_raw_price),
                    est_grade10_price = COALESCE(NULLIF(excluded.est_grade10_price, 0), master_set_catalog.est_grade10_price),
                    image_url = COALESCE(excluded.image_url, master_set_catalog.image_url),
                    notes = COALESCE(excluded.notes, master_set_catalog.notes);
            """, params)
            count += 1
    return count


# =============================================================
# Collection & Market Queries
# =============================================================

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
                grade_label, condition_type, edition, language, is_error,
                price, shipping_cost, total_price, listing_url, image_url,
                listing_type, deal_rating, fair_value_estimate,
                discount_percentage, ai_rationale, sale_date
            ) VALUES (
                :listing_id, :title, :card_name, :grading_company, :grade,
                :grade_label, :condition_type, :edition, :language, :is_error,
                :price, :shipping_cost, :total_price, :listing_url, :image_url,
                :listing_type, :deal_rating, :fair_value_estimate,
                :discount_percentage, :ai_rationale, :sale_date
            )
        """, sale)
        return cursor.lastrowid or 0


def get_recent_comparables(
    card_name: str,
    grading_company: Optional[str] = None,
    grade: Optional[float] = None,
    condition_type: str = "Graded",
    limit: int = 10,
    db_path: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Retrieve the last N comparable sales for appraisal context."""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        query = """
            SELECT card_name, grading_company, grade, grade_label, condition_type,
                   total_price, sale_date, scraped_at, deal_rating
            FROM market_sales
            WHERE card_name LIKE ?
        """
        params: List[Any] = [f"%{card_name}%"]

        if condition_type:
            query += " AND condition_type = ?"
            params.append(condition_type)

        if condition_type == "Graded":
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
                   grade, grade_label, cert_number, purchase_price, purchase_date,
                   edition, language, is_error, error_type, is_raw, image_url, notes
            FROM my_collection
            ORDER BY purchase_date DESC;
        """)
        return [dict(row) for row in cursor.fetchall()]


def insert_collection_card(card: Dict[str, Any], db_path: Optional[str] = None) -> int:
    """Add a new graded or raw card to personal collection."""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO my_collection (
                card_name, set_name, card_number, grading_company,
                grade, grade_label, cert_number, purchase_price, purchase_date,
                edition, language, is_error, error_type, is_raw,
                image_url, notes
            ) VALUES (
                :card_name, :set_name, :card_number, :grading_company,
                :grade, :grade_label, :cert_number, :purchase_price, :purchase_date,
                :edition, :language, :is_error, :error_type, :is_raw,
                :image_url, :notes
            )
        """, card)
        return cursor.lastrowid or 0
