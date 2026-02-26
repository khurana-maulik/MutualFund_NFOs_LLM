"""
scrape_nav.py — Fetch daily NAV data from AMFI and store in SQLite.

Downloads the NAVAll.txt file from AMFI India which contains daily NAV
data for ALL mutual fund schemes (~20,000+). Parses and stores in the
funds database.

Run:  python -m scripts.scrape_nav

Format of NAVAll.txt:
  - Lines starting with a fund house name (no semicolons) = section header
  - Lines starting with "Scheme Code" = column headers
  - Lines with semicolons = data rows:
    SchemeCode;ISINGrowth;ISINReinv;SchemeName;NAV;Date
  - Blank lines or lines with just dashes = separators
"""

import sys
import os
import requests
import time

# Add project root to path so we can import src modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import AMFI_NAV_URL, TOP_AMCS
from src.database import init_database, get_connection, get_fund_count


def fetch_nav_data() -> str:
    """Download NAVAll.txt from AMFI India."""
    print(f"📡 Downloading NAV data from {AMFI_NAV_URL}...")
    response = requests.get(AMFI_NAV_URL, timeout=60)
    response.raise_for_status()
    print(f"   ✅ Downloaded {len(response.text):,} characters")
    return response.text


def parse_nav_data(raw_text: str) -> list[dict]:
    """
    Parse the semicolon-delimited NAV text into a list of fund records.

    The file is organized by fund house (AMC). Section headers look like:
        "Mutual Fund Name\n"
    Then sub-sections by scheme type:
        "Open Ended Schemes(Debt Scheme - Banking and PSU Fund)\n"
    Then column headers and data rows.
    """
    funds = []
    current_fund_house = None
    current_scheme_type = None
    current_category = None

    for line in raw_text.strip().split("\n"):
        line = line.strip()

        # Skip empty lines
        if not line:
            continue

        # Data row: has semicolons
        if ";" in line:
            parts = line.split(";")

            # Skip the header row
            if parts[0].strip() == "Scheme Code":
                continue

            if len(parts) >= 6:
                try:
                    scheme_code = int(parts[0].strip())
                except ValueError:
                    continue

                nav_str = parts[4].strip()
                try:
                    nav = float(nav_str) if nav_str and nav_str != "N.A." else None
                except ValueError:
                    nav = None

                funds.append({
                    "scheme_code": scheme_code,
                    "isin_growth": parts[1].strip() or None,
                    "isin_reinvestment": parts[2].strip() or None,
                    "scheme_name": parts[3].strip(),
                    "net_asset_value": nav,
                    "nav_date": parts[5].strip() or None,
                    "fund_house": current_fund_house,
                    "scheme_type": current_scheme_type,
                    "scheme_category": current_category,
                })
        else:
            # Non-data line: could be fund house name or scheme type
            # Scheme type lines contain parentheses like:
            # "Open Ended Schemes(Debt Scheme - Banking and PSU Fund)"
            if "(" in line and ")" in line:
                # Extract scheme type and category
                paren_start = line.index("(")
                current_scheme_type = line[:paren_start].strip()
                current_category = line[paren_start + 1 : line.rindex(")")].strip()
            elif line and not line.startswith("-"):
                # Plain text line without semicolons = fund house name
                current_fund_house = line.strip()

    return funds


def store_funds(funds: list[dict]):
    """Insert or update funds in the database."""
    print(f"💾 Storing {len(funds):,} fund records...")

    with get_connection() as conn:
        cursor = conn.cursor()

        inserted = 0
        updated = 0

        for fund in funds:
            # Check if scheme already exists
            existing = cursor.execute(
                "SELECT scheme_code FROM funds WHERE scheme_code = ?",
                (fund["scheme_code"],)
            ).fetchone()

            if existing:
                # Update NAV and metadata
                cursor.execute("""
                    UPDATE funds SET
                        scheme_name = ?,
                        isin_growth = COALESCE(?, isin_growth),
                        isin_reinvestment = COALESCE(?, isin_reinvestment),
                        net_asset_value = COALESCE(?, net_asset_value),
                        nav_date = COALESCE(?, nav_date),
                        fund_house = COALESCE(?, fund_house),
                        scheme_type = COALESCE(?, scheme_type),
                        scheme_category = COALESCE(?, scheme_category),
                        is_active = 1,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE scheme_code = ?
                """, (
                    fund["scheme_name"],
                    fund["isin_growth"],
                    fund["isin_reinvestment"],
                    fund["net_asset_value"],
                    fund["nav_date"],
                    fund["fund_house"],
                    fund["scheme_type"],
                    fund["scheme_category"],
                    fund["scheme_code"],
                ))
                updated += 1
            else:
                cursor.execute("""
                    INSERT INTO funds (
                        scheme_code, scheme_name, isin_growth, isin_reinvestment,
                        net_asset_value, nav_date, fund_house, scheme_type,
                        scheme_category, is_active
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                """, (
                    fund["scheme_code"],
                    fund["scheme_name"],
                    fund["isin_growth"],
                    fund["isin_reinvestment"],
                    fund["net_asset_value"],
                    fund["nav_date"],
                    fund["fund_house"],
                    fund["scheme_type"],
                    fund["scheme_category"],
                ))
                inserted += 1

        conn.commit()
        print(f"   ✅ Inserted: {inserted:,} | Updated: {updated:,}")


def print_summary():
    """Print a summary of what's in the database."""
    total = get_fund_count()
    print(f"\n📊 Database Summary:")
    print(f"   Total active funds: {total:,}")

    # Count by AMC
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT fund_house, COUNT(*) as cnt
            FROM funds
            WHERE is_active = 1 AND fund_house IS NOT NULL
            GROUP BY fund_house
            ORDER BY cnt DESC
            LIMIT 15
        """).fetchall()

        print(f"\n   Top 15 AMCs by scheme count:")
        for row in rows:
            print(f"     {row['fund_house']}: {row['cnt']} schemes")


def main():
    """Main scraping pipeline."""
    start = time.time()

    print("=" * 60)
    print("🏦 AMFI NAV Scraper — Fetching All Mutual Fund Data")
    print("=" * 60)

    # Step 1: Initialize database
    init_database()

    # Step 2: Fetch NAV data
    raw_data = fetch_nav_data()

    # Step 3: Parse
    funds = parse_nav_data(raw_data)
    print(f"📄 Parsed {len(funds):,} fund records from AMFI")

    # Step 4: Store
    store_funds(funds)

    # Step 5: Summary
    print_summary()

    elapsed = time.time() - start
    print(f"\n⏱️  Completed in {elapsed:.1f} seconds")


if __name__ == "__main__":
    main()
