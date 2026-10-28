"""
Database management module for The Vulpix Vault.
Configures SQLite with WAL mode, auto-migrates schemas, creates master_set_catalog,
my_collection, market_sales, and ebay_sniper_watchlist tables with PriceCharting & Population support.
"""

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

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
    """Initialize or migrate database schema with PriceCharting and Population fields."""
    with get_db_connection(db_path) as conn:
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

        # 4. eBay Sniper Watchlist
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

        # 5. System Settings
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS system_settings (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Auto-migration columns for existing databases
        for col, ctype in [
            ("pricecharting_url", "TEXT"),
            ("pricecharting_raw", "REAL DEFAULT 0.0"),
            ("pricecharting_grade9", "REAL DEFAULT 0.0"),
            ("pricecharting_grade10", "REAL DEFAULT 0.0"),
            ("pop_total", "INTEGER DEFAULT 0"),
            ("pop_grade10", "INTEGER DEFAULT 0"),
            ("pop_pristine10", "INTEGER DEFAULT 0"),
            ("pokecottage_id", "TEXT"),
            ("pokecottage_url", "TEXT"),
            ("tcgplayer_url", "TEXT"),
            ("region", "TEXT DEFAULT 'International'"),
            ("is_cameo", "INTEGER DEFAULT 0"),
        ]:
            _add_column_if_missing(cursor, "master_set_catalog", col, ctype)

        for col, ctype in [
            ("pop_grade10", "INTEGER DEFAULT 0"),
            ("pop_pristine10", "INTEGER DEFAULT 0"),
        ]:
            _add_column_if_missing(cursor, "my_collection", col, ctype)

        for col, ctype in [
            ("edition", "TEXT DEFAULT 'Unlimited'"),
            ("grading_company", "TEXT DEFAULT 'RAW'"),
            ("grade", "REAL DEFAULT 0.0"),
            ("grade_label", "TEXT DEFAULT 'Raw Single'"),
            ("condition_type", "TEXT DEFAULT 'Raw'"),
            ("fair_market_value", "REAL DEFAULT 0.0"),
            ("max_bid_target", "REAL DEFAULT 0.0"),
            ("snipe_mode", "TEXT DEFAULT 'amazing_deal'"),
        ]:
            _add_column_if_missing(cursor, "ebay_sniper_watchlist", col, ctype)

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_master_search ON master_set_catalog(card_name, set_name, language, edition);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_market_lookup ON market_sales(card_name, grading_company, grade, condition_type);")

        # Purge legacy hallucinated/misnumbered cards from older seed data
        cursor.execute("""
            DELETE FROM master_set_catalog 
            WHERE card_name LIKE '%Erika%'
               OR (card_name LIKE '%Brock%Vulpix%' AND set_name LIKE '%Gym Challenge%' AND card_number LIKE '%73%')
               OR (card_name LIKE '%Light%Vulpix%' AND card_number LIKE '%80%');
        """)
        cursor.execute("DELETE FROM my_collection WHERE card_name LIKE '%Erika%' OR (card_name LIKE '%Light%Vulpix%' AND card_number LIKE '%80%');")

        # Heal broken / 404 / inaccurate image URLs across master set and user collection
        cursor.execute("""
            UPDATE my_collection 
            SET image_url = 'dashboard/static/cards/alolan-vulpix-sun-and-moon-promos-293-sm-p.jpg'
            WHERE card_name LIKE '%Alolan Vulpix%' AND (set_name LIKE '%Daiichi%' OR card_number LIKE '%293%');
        """)
        cursor.execute("""
            UPDATE master_set_catalog 
            SET image_url = 'dashboard/static/cards/alolan-vulpix-sun-and-moon-promos-293-sm-p.jpg'
            WHERE card_name LIKE '%Alolan Vulpix%' AND (set_name LIKE '%Daiichi%' OR card_number LIKE '%293%');
        """)
        cursor.execute("""
            UPDATE my_collection 
            SET image_url = 'dashboard/static/cards/alolan-vulpix-vstar-incandescent-arcana-023-068.jpg'
            WHERE set_name LIKE '%Incandescent Arcana%' AND card_number LIKE '%023%';
        """)
        cursor.execute("""
            UPDATE master_set_catalog 
            SET image_url = 'dashboard/static/cards/alolan-vulpix-vstar-incandescent-arcana-023-068.jpg'
            WHERE set_name LIKE '%Incandescent Arcana%' AND card_number LIKE '%023%';
        """)
        cursor.execute("""
            UPDATE master_set_catalog 
            SET image_url = 'dashboard/static/cards/vulpix-pokemon-card-151-037-165.jpg'
            WHERE image_url LIKE '%sv2a/37%';
        """)
        cursor.execute("""
            UPDATE master_set_catalog 
            SET image_url = 'https://pokecottagecdn.com/mastersets/images/cards/vulpix-master-set__2016-09-16__jpn_xyep__14__Vulpix__1st_Edition__large.webp'
            WHERE image_url LIKE '%cp6/14%';
        """)
        cursor.execute("""
            UPDATE master_set_catalog 
            SET image_url = 'dashboard/static/cards/playing_cards_korean.jpg'
            WHERE image_url LIKE '%playing_cards_korean_8%';
        """)
        cursor.execute("""
            UPDATE master_set_catalog 
            SET image_url = 'dashboard/static/cards/vulpix-mega-brave-067-063.jpg'
            WHERE image_url LIKE '%vulpix_mega_brave_067_066%';
        """)
        cursor.execute("""
            UPDATE master_set_catalog 
            SET image_url = 'https://images.pokemontcg.io/ru1/7_hires.png'
            WHERE (set_name LIKE '%Rumble%' OR set_name LIKE '%Scramble%') AND image_url LIKE '%minun%';
        """)

        # Fix EX Dragon Frontiers Vulpix (#70/101 not Trapinch #69/101)
        cursor.execute("""
            DELETE FROM master_set_catalog 
            WHERE set_name LIKE '%Dragon Frontiers%' AND (card_number LIKE '%69%' OR image_url LIKE '%ex15/69%')
              AND EXISTS (
                  SELECT 1 FROM master_set_catalog m2
                  WHERE m2.set_name LIKE '%Dragon Frontiers%' AND m2.card_number = '70/101'
                    AND m2.edition = master_set_catalog.edition
              );
        """)
        cursor.execute("""
            UPDATE OR IGNORE master_set_catalog 
            SET card_number = '70/101',
                image_url = 'dashboard/static/cards/ex_dragon_frontiers_70.jpg'
            WHERE set_name LIKE '%Dragon Frontiers%' AND (card_number LIKE '%69%' OR image_url LIKE '%ex15/69%');
        """)
        cursor.execute("""
            DELETE FROM master_set_catalog 
            WHERE set_name LIKE '%Dragon Frontiers%' AND (card_number LIKE '%69%' OR image_url LIKE '%ex15/69%');
        """)

        # Fix Sapporo's Pikachu (#005/SM-P not Snorlax-GX #05)
        cursor.execute("""
            DELETE FROM master_set_catalog 
            WHERE (card_name LIKE '%Sapporo%' OR (card_number LIKE '%005/SM-P%' AND (image_url LIKE '%SM05%' OR card_name LIKE '%Pikachu%')))
              AND EXISTS (
                  SELECT 1 FROM master_set_catalog m2
                  WHERE m2.card_name = 'Sapporo''s Pikachu (Vulpix Cameo)' AND m2.card_number = '005/SM-P'
                    AND m2.id != master_set_catalog.id
              );
        """)
        cursor.execute("""
            UPDATE OR IGNORE master_set_catalog 
            SET card_name = 'Sapporo''s Pikachu (Vulpix Cameo)',
                image_url = 'dashboard/static/cards/sapporo_s_pikachu__vulpix_cameo__promo_005_sm-p.jpg',
                is_cameo = 1
            WHERE card_name LIKE '%Sapporo%' OR (card_number LIKE '%005/SM-P%' AND (image_url LIKE '%SM05%' OR card_name LIKE '%Pikachu%'));
        """)

        # Fix Poncho-clad Pikachu (Alolan Vulpix Poncho #037/SM-P not Zapdos #37)
        cursor.execute("""
            DELETE FROM master_set_catalog 
            WHERE (card_number LIKE '%037/SM-P%' OR card_name LIKE '%Poncho%Alolan%' OR card_name LIKE '%Special Box%')
              AND EXISTS (
                  SELECT 1 FROM master_set_catalog m2
                  WHERE m2.card_name = 'Poncho-wearing Pikachu (Alolan Vulpix Poncho)' AND m2.card_number = '037/SM-P'
                    AND m2.id != master_set_catalog.id
              );
        """)
        cursor.execute("""
            UPDATE OR IGNORE master_set_catalog 
            SET card_name = 'Poncho-wearing Pikachu (Alolan Vulpix Poncho)',
                set_name = 'Promo',
                image_url = 'dashboard/static/cards/promo_037_smp.jpg',
                is_cameo = 1
            WHERE card_number LIKE '%037/SM-P%' OR card_name LIKE '%Poncho%Alolan%' OR card_name LIKE '%Special Box%';
        """)

        # Fix Poncho-wearing Pikachu (Vulpix Poncho #038/SM-P)
        cursor.execute("""
            DELETE FROM master_set_catalog 
            WHERE (card_number LIKE '%038/SM-P%' OR (card_name LIKE '%Poncho%' AND card_name NOT LIKE '%Alolan%'))
              AND EXISTS (
                  SELECT 1 FROM master_set_catalog m2
                  WHERE m2.card_name = 'Poncho-wearing Pikachu (Vulpix Poncho)' AND m2.card_number = '038/SM-P'
                    AND m2.id != master_set_catalog.id
              );
        """)
        cursor.execute("""
            UPDATE OR IGNORE master_set_catalog 
            SET card_name = 'Poncho-wearing Pikachu (Vulpix Poncho)',
                set_name = 'Promo',
                image_url = 'dashboard/static/cards/promo_038_smp.jpg',
                is_cameo = 1
            WHERE card_number LIKE '%038/SM-P%' OR (card_name LIKE '%Poncho%' AND card_name NOT LIKE '%Alolan%');
        """)

        # Fix Korean 059/XY-P Vulpix Promo image
        cursor.execute("""
            UPDATE master_set_catalog 
            SET image_url = 'dashboard/static/cards/promo_110_xyp.jpg'
            WHERE card_number LIKE '%059/XY-P%';
        """)

        # Fix Neo Destiny: drop duplicate 90/105 English rows, update others
        cursor.execute("""
            DELETE FROM master_set_catalog 
            WHERE set_name LIKE '%Neo Destiny%' AND card_number LIKE '%90%' AND language = 'English';
        """)
        cursor.execute("""
            UPDATE OR IGNORE master_set_catalog 
            SET card_number = '91/105',
                image_url = 'dashboard/static/cards/vulpix_neo_destiny_90_105.jpg'
            WHERE set_name LIKE '%Neo Destiny%' AND card_number LIKE '%90%';
        """)

        # Ensure all cameo cards are accurately flagged with is_cameo = 1
        cursor.execute("""
            UPDATE master_set_catalog 
            SET is_cameo = 1
            WHERE card_name LIKE '%cameo%'
               OR notes LIKE '%cameo%'
               OR card_name LIKE '%pikachu%'
               OR card_name LIKE '%poncho%'
               OR set_name LIKE '%Rumble%'
               OR set_name LIKE '%Scramble%'
               OR card_name NOT LIKE '%vulpix%';
        """)



# =============================================================
# Sniper Watchlist Database Queries
# =============================================================

def get_sniper_watchlist(db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieve all active items on the sniper watchlist."""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM ebay_sniper_watchlist ORDER BY auction_end_time ASC;")
        return [dict(row) for row in cursor.fetchall()]


def add_to_sniper_watchlist(item: Dict[str, Any], db_path: Optional[str] = None) -> int:
    """Add or update an eBay auction on the sniper watchlist."""
    with get_db_connection(db_path) as conn:
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
        """, item)
        return cursor.lastrowid or 0


def delete_from_sniper_watchlist(item_id: int, db_path: Optional[str] = None) -> None:
    """Remove an item from the sniper watchlist."""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM ebay_sniper_watchlist WHERE id = ?;", (item_id,))


# =============================================================
# Master Set & Collection Queries
# =============================================================

def bulk_upsert_master_catalog(cards: List[Dict[str, Any]], db_path: Optional[str] = None) -> int:
    """Bulk insert or update a list of master set cards with PriceCharting & Pop stats."""
    count = 0
    with get_db_connection(db_path) as conn:
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
                "pricecharting_url": str(card.get("pricecharting_url", "")).strip(),
                "pricecharting_raw": float(card.get("pricecharting_raw") or 0.0),
                "pricecharting_grade9": float(card.get("pricecharting_grade9") or 0.0),
                "pricecharting_grade10": float(card.get("pricecharting_grade10") or 0.0),
                "pop_total": int(card.get("pop_total") or 0),
                "pop_grade10": int(card.get("pop_grade10") or 0),
                "pop_pristine10": int(card.get("pop_pristine10") or 0),
                "image_url": str(card.get("image_url", "https://images.pokemontcg.io/base1/68_hires.png")).strip(),
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
                   edition, language, is_error, error_type, is_raw, pop_grade10, pop_pristine10,
                   master_card_id, image_url, notes
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
            "purchase_date": card.get("purchase_date", "2024-01-01"),
            "edition": card.get("edition", "Unlimited"),
            "language": card.get("language", "English"),
            "is_error": 1 if card.get("is_error") else 0,
            "error_type": card.get("error_type"),
            "is_raw": 1 if card.get("is_raw") else 0,
            "pop_grade10": int(card.get("pop_grade10") or 0),
            "pop_pristine10": int(card.get("pop_pristine10") or 0),
            "master_card_id": card.get("master_card_id"),
            "image_url": card.get("image_url", "https://images.pokemontcg.io/base1/68_hires.png"),
            "notes": card.get("notes", ""),
        })
        return cursor.lastrowid or 0


def get_system_setting(key: str, default: str = "", db_path: Optional[str] = None) -> str:
    """Retrieve persistent setting value from database."""
    init_db(db_path)
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM system_settings WHERE key = ? LIMIT 1;", (key,))
        row = cursor.fetchone()
        if row and row["value"]:
            return row["value"]
    return default


def get_existing_collection_identifiers(db_path: Optional[str] = None) -> Tuple[set, set]:
    """Returns set of notes/order numbers and set of card keys (card_name, set_name, card_number)."""
    init_db(db_path)
    existing_notes = set()
    existing_cards = set()
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT card_name, set_name, card_number, notes FROM my_collection;")
        for r in cursor.fetchall():
            if r["notes"]:
                existing_notes.add(str(r["notes"]))
            c_name = str(r["card_name"] or "").strip().lower()
            s_name = str(r["set_name"] or "").strip().lower()
            num = str(r["card_number"] or "").strip().lower()
            existing_cards.add((c_name, s_name, num))
    return existing_notes, existing_cards

