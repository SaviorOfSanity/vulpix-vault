"""
Clean, versioned SQLite database layer for The Vulpix Vault v2.
- Single source of truth (no duplicated DB modules, no per-click migrations, no hardcoded row IDs).
- Deterministic string `catalog_key` primary keys so dev and Docker DBs are 100% consistent.
"""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from typing import Iterator, Optional

SCHEMA_VERSION = 4


def get_project_root() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def get_data_dir() -> str:
    env_db = os.getenv("DB_PATH")
    if env_db:
        return os.path.dirname(os.path.abspath(env_db))
    if os.name != "nt" and os.path.isdir("/data"):
        return "/data"
    return os.path.join(get_project_root(), "data")


def get_db_path() -> str:
    env_db = os.getenv("DB_PATH")
    if env_db:
        os.makedirs(os.path.dirname(os.path.abspath(env_db)), exist_ok=True)
        return os.path.abspath(env_db)
    data_dir = get_data_dir()
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, "vulpix_vault.db")


def get_cached_cards_dir() -> str:
    path = os.path.join(get_data_dir(), "cached_cards")
    os.makedirs(path, exist_ok=True)
    return path


def get_static_cards_dir() -> str:
    root = get_project_root()
    for candidate in (
        os.path.join(root, "static", "cards"),
        os.path.join(root, "dashboard", "static", "cards"),
    ):
        if os.path.isdir(candidate):
            return candidate
    fallback = os.path.join(root, "static", "cards")
    os.makedirs(fallback, exist_ok=True)
    return fallback


@contextmanager
def get_conn(db_path: Optional[str] = None) -> Iterator[sqlite3.Connection]:
    path = db_path or get_db_path()
    conn = sqlite3.connect(path, timeout=15.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA busy_timeout = 10000;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        conn.execute("PRAGMA foreign_keys = ON;")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_schema(db_path: Optional[str] = None) -> None:
    """Initializes v2 schema once at startup. Never mutates user records on read."""
    with get_conn(db_path) as conn:
        c = conn.cursor()

        c.execute("""
            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS catalog_cards (
                catalog_key TEXT PRIMARY KEY,
                card_group_key TEXT NOT NULL,
                card_name TEXT NOT NULL,
                native_name TEXT DEFAULT '',
                set_name TEXT NOT NULL,
                native_set_name TEXT DEFAULT '',
                set_id TEXT DEFAULT '',
                series TEXT DEFAULT '',
                card_number TEXT DEFAULT '',
                base_number TEXT DEFAULT '',
                release_year INTEGER DEFAULT 2000,
                release_date TEXT DEFAULT '',
                language TEXT NOT NULL DEFAULT 'English',
                region TEXT DEFAULT 'International',
                edition TEXT NOT NULL DEFAULT 'Unlimited',
                variant_key TEXT NOT NULL DEFAULT 'unlimited',
                rarity TEXT DEFAULT 'Common',
                artist TEXT DEFAULT '',
                is_error INTEGER DEFAULT 0,
                error_description TEXT DEFAULT '',
                visual_callouts TEXT DEFAULT '[]',
                image_url TEXT DEFAULT '',
                local_image TEXT DEFAULT '',
                image_is_localized INTEGER DEFAULT 1,
                price_raw REAL,
                price_grade9 REAL,
                price_grade10 REAL,
                price_source TEXT,
                price_updated_at TEXT,
                price_manual_lock INTEGER DEFAULT 0,
                pokecottage_id TEXT DEFAULT '',
                tcgdex_id TEXT DEFAULT '',
                pricecharting_url TEXT DEFAULT '',
                tcgplayer_url TEXT DEFAULT '',
                notes TEXT DEFAULT '',
                source TEXT DEFAULT 'pokecottage',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS vault_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                catalog_key TEXT,
                card_name TEXT NOT NULL,
                set_name TEXT NOT NULL,
                card_number TEXT DEFAULT '',
                language TEXT DEFAULT 'English',
                edition TEXT DEFAULT 'Unlimited',
                is_raw INTEGER DEFAULT 0,
                grading_company TEXT DEFAULT 'RAW',
                grade REAL DEFAULT 0.0,
                grade_label TEXT DEFAULT 'Raw Single',
                cert_number TEXT DEFAULT '',
                purchase_price REAL DEFAULT 0.0,
                purchase_date TEXT DEFAULT '',
                image_url TEXT DEFAULT '',
                notes TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (catalog_key) REFERENCES catalog_cards(catalog_key) ON DELETE SET NULL
            );
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS price_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                catalog_key TEXT NOT NULL,
                price_raw REAL,
                price_grade9 REAL,
                price_grade10 REAL,
                source TEXT NOT NULL,
                recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (catalog_key) REFERENCES catalog_cards(catalog_key) ON DELETE CASCADE
            );
        """)

        # Phase 2: eBay Auction Radar tables
        c.execute("""
            CREATE TABLE IF NOT EXISTS ebay_listings (
                ebay_item_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                url TEXT NOT NULL,
                image_url TEXT DEFAULT '',
                buying_option TEXT NOT NULL DEFAULT 'AUCTION',
                current_price REAL NOT NULL DEFAULT 0.0,
                shipping_cost REAL NOT NULL DEFAULT 0.0,
                total_cost REAL NOT NULL DEFAULT 0.0,
                bid_count INTEGER DEFAULT 0,
                end_time TEXT DEFAULT '',
                seller_username TEXT DEFAULT '',
                seller_feedback_pct REAL,
                condition TEXT DEFAULT '',
                detected_grader TEXT DEFAULT 'RAW',
                detected_grade REAL DEFAULT 0.0,
                detected_grade_label TEXT DEFAULT 'Raw Single',
                catalog_key TEXT,
                match_confidence INTEGER DEFAULT 0,
                market_comp REAL,
                deal_tier TEXT DEFAULT 'UNPRICED',
                discount_pct REAL,
                is_watched INTEGER DEFAULT 0,
                is_dismissed INTEGER DEFAULT 0,
                alert_sent INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                source_query TEXT DEFAULT '',
                first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (catalog_key) REFERENCES catalog_cards(catalog_key) ON DELETE SET NULL
            );
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS radar_queries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query TEXT NOT NULL UNIQUE,
                label TEXT NOT NULL DEFAULT '',
                buying_filter TEXT NOT NULL DEFAULT 'ALL',
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        c.execute("CREATE INDEX IF NOT EXISTS idx_cat_lang ON catalog_cards(language);")
        c.execute("CREATE INDEX IF NOT EXISTS idx_cat_group ON catalog_cards(card_group_key);")
        c.execute("CREATE INDEX IF NOT EXISTS idx_cat_year ON catalog_cards(release_year, set_name);")
        c.execute("CREATE INDEX IF NOT EXISTS idx_cat_pc ON catalog_cards(pokecottage_id);")
        c.execute("CREATE INDEX IF NOT EXISTS idx_cat_tcgdex ON catalog_cards(tcgdex_id);")
        c.execute("CREATE INDEX IF NOT EXISTS idx_vault_catkey ON vault_items(catalog_key);")
        c.execute("CREATE INDEX IF NOT EXISTS idx_ebay_active_end ON ebay_listings(is_active, is_dismissed, end_time);")
        c.execute("CREATE INDEX IF NOT EXISTS idx_ebay_catkey ON ebay_listings(catalog_key);")

        # Safe additive schema upgrade for existing v2 SQLite DBs
        existing_cols = {row["name"] for row in c.execute("PRAGMA table_info(catalog_cards);").fetchall()}
        if "native_name" not in existing_cols:
            c.execute("ALTER TABLE catalog_cards ADD COLUMN native_name TEXT DEFAULT '';")
        if "native_set_name" not in existing_cols:
            c.execute("ALTER TABLE catalog_cards ADD COLUMN native_set_name TEXT DEFAULT '';")

        c.execute(
            "INSERT OR REPLACE INTO app_settings (key, value) VALUES ('schema_version', ?);",
            (str(SCHEMA_VERSION),),
        )


def get_setting(key: str, default: str = "", db_path: Optional[str] = None) -> str:
    with get_conn(db_path) as conn:
        row = conn.execute("SELECT value FROM app_settings WHERE key = ?;", (key,)).fetchone()
        return str(row["value"]) if row else default


def set_setting(key: str, value: str, db_path: Optional[str] = None) -> None:
    with get_conn(db_path) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO app_settings (key, value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP);",
            (key, value),
        )
