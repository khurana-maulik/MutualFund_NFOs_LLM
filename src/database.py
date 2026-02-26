"""
database.py — SQLite database for storing mutual fund metadata.

Stores structured data from AMFI (NAV, scheme codes) and mfapi.in
(fund manager, category, etc.) so the chatbot has instant access
to fund details without scraping on every query.

Tables:
  - funds: All mutual fund schemes with NAV, category, AMC, etc.
  - fund_details: Enriched data from mfapi.in (fund manager, objective, etc.)
"""

import sqlite3
import os
from contextlib import contextmanager
from src.config import DATABASE_PATH


def init_database():
    """Create the database and tables if they don't exist."""
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)

    with get_connection() as conn:
        cursor = conn.cursor()

        # Main funds table — populated from NAVAll.txt
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS funds (
                scheme_code INTEGER PRIMARY KEY,
                scheme_name TEXT NOT NULL,
                isin_growth TEXT,
                isin_reinvestment TEXT,
                net_asset_value REAL,
                nav_date TEXT,
                fund_house TEXT,
                scheme_type TEXT,
                scheme_category TEXT,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Enriched details — populated from mfapi.in
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS fund_details (
                scheme_code INTEGER PRIMARY KEY,
                fund_manager TEXT,
                investment_objective TEXT,
                launch_date TEXT,
                benchmark TEXT,
                expense_ratio REAL,
                exit_load TEXT,
                min_investment REAL,
                risk_level TEXT,
                scheme_url TEXT,
                raw_json TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (scheme_code) REFERENCES funds(scheme_code)
            )
        """)

        # Indexes for fast lookups
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_funds_house
            ON funds(fund_house)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_funds_category
            ON funds(scheme_category)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_funds_active
            ON funds(is_active)
        """)

        conn.commit()
        print("✅ Database initialized at", DATABASE_PATH)


@contextmanager
def get_connection():
    """Context manager for database connections."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row  # Return dict-like rows
    try:
        yield conn
    finally:
        conn.close()


# ── Query Helpers ─────────────────────────────────────────────────────

def get_all_amcs() -> list[str]:
    """Get list of all unique AMCs (fund houses) in the database."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT DISTINCT fund_house FROM funds WHERE is_active = 1 ORDER BY fund_house"
        ).fetchall()
        return [row["fund_house"] for row in rows if row["fund_house"]]


def get_funds_by_amc(amc_name: str) -> list[dict]:
    """Get all active funds for a given AMC."""
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT f.*, fd.fund_manager, fd.investment_objective, fd.risk_level
               FROM funds f
               LEFT JOIN fund_details fd ON f.scheme_code = fd.scheme_code
               WHERE f.fund_house = ? AND f.is_active = 1
               ORDER BY f.scheme_name""",
            (amc_name,)
        ).fetchall()
        return [dict(row) for row in rows]


def get_fund_by_code(scheme_code: int) -> dict | None:
    """Get full fund details by scheme code."""
    with get_connection() as conn:
        row = conn.execute(
            """SELECT f.*, fd.fund_manager, fd.investment_objective,
                      fd.launch_date, fd.benchmark, fd.expense_ratio,
                      fd.exit_load, fd.min_investment, fd.risk_level
               FROM funds f
               LEFT JOIN fund_details fd ON f.scheme_code = fd.scheme_code
               WHERE f.scheme_code = ?""",
            (scheme_code,)
        ).fetchone()
        return dict(row) if row else None


def search_funds(query: str, limit: int = 20) -> list[dict]:
    """Search funds by name (case-insensitive partial match)."""
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT scheme_code, scheme_name, fund_house, scheme_category,
                      net_asset_value, nav_date
               FROM funds
               WHERE scheme_name LIKE ? AND is_active = 1
               ORDER BY scheme_name
               LIMIT ?""",
            (f"%{query}%", limit)
        ).fetchall()
        return [dict(row) for row in rows]


def get_fund_count() -> int:
    """Get total number of active funds."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM funds WHERE is_active = 1"
        ).fetchone()
        return row["cnt"]


def get_enriched_fund_count() -> int:
    """Get number of funds that have enriched details."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM fund_details"
        ).fetchone()
        return row["cnt"]
