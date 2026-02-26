"""
scrape_scheme_details.py — Enrich fund data using mfapi.in

For each fund in the database, fetches detailed scheme information from
the free mfapi.in API and stores it in the fund_details table.

Also creates text documents from the fund data that can be ingested
into the vector store for RAG querying.

Run:  python -m scripts.scrape_scheme_details

API: https://api.mfapi.in/mf/{scheme_code}
Response format:
{
  "meta": {
    "fund_house": "...",
    "scheme_type": "...",
    "scheme_category": "...",
    "scheme_code": 123,
    "scheme_name": "..."
  },
  "data": [
    {"date": "21-02-2025", "nav": "45.1234"},
    ...
  ]
}
"""

import sys
import os
import json
import time
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import MFAPI_BASE_URL, DATABASE_PATH
from src.database import init_database, get_connection


def get_schemes_to_enrich(limit: int = 500) -> list[dict]:
    """
    Get active funds that haven't been enriched yet.
    Prioritizes schemes with valid NAV (more likely to be active).
    """
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT f.scheme_code, f.scheme_name, f.fund_house
            FROM funds f
            LEFT JOIN fund_details fd ON f.scheme_code = fd.scheme_code
            WHERE f.is_active = 1
              AND f.net_asset_value IS NOT NULL
              AND fd.scheme_code IS NULL
            ORDER BY f.fund_house, f.scheme_name
            LIMIT ?
        """, (limit,)).fetchall()
        return [dict(row) for row in rows]


def fetch_scheme_details(scheme_code: int) -> dict | None:
    """Fetch scheme details from mfapi.in."""
    url = f"{MFAPI_BASE_URL}/{scheme_code}"
    try:
        response = requests.get(url, timeout=15)
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "SUCCESS" or "meta" in data:
                return data
        return None
    except (requests.RequestException, json.JSONDecodeError) as e:
        print(f"   ⚠️ Error fetching {scheme_code}: {e}")
        return None


def build_fund_text(fund_db: dict, api_data: dict) -> str:
    """
    Build a rich text document from fund metadata.
    This text will be chunked and embedded for RAG querying.
    """
    meta = api_data.get("meta", {})
    nav_history = api_data.get("data", [])

    # Calculate returns from NAV history
    returns_text = ""
    if len(nav_history) >= 2:
        try:
            latest_nav = float(nav_history[0]["nav"])

            # 1-month return (approx 22 trading days)
            if len(nav_history) > 22:
                nav_1m = float(nav_history[22]["nav"])
                ret_1m = ((latest_nav - nav_1m) / nav_1m) * 100
                returns_text += f"  - 1-Month Return: {ret_1m:+.2f}%\n"

            # 3-month return (approx 66 trading days)
            if len(nav_history) > 66:
                nav_3m = float(nav_history[66]["nav"])
                ret_3m = ((latest_nav - nav_3m) / nav_3m) * 100
                returns_text += f"  - 3-Month Return: {ret_3m:+.2f}%\n"

            # 6-month return (approx 132 trading days)
            if len(nav_history) > 132:
                nav_6m = float(nav_history[132]["nav"])
                ret_6m = ((latest_nav - nav_6m) / nav_6m) * 100
                returns_text += f"  - 6-Month Return: {ret_6m:+.2f}%\n"

            # 1-year return (approx 252 trading days)
            if len(nav_history) > 252:
                nav_1y = float(nav_history[252]["nav"])
                ret_1y = ((latest_nav - nav_1y) / nav_1y) * 100
                returns_text += f"  - 1-Year Return: {ret_1y:+.2f}%\n"

            # 3-year return (approx 756 trading days)
            if len(nav_history) > 756:
                nav_3y = float(nav_history[756]["nav"])
                ret_3y = ((latest_nav - nav_3y) / nav_3y) * 100
                cagr_3y = ((latest_nav / nav_3y) ** (1/3) - 1) * 100
                returns_text += f"  - 3-Year Return: {ret_3y:+.2f}% (CAGR: {cagr_3y:.2f}%)\n"

            # 5-year return (approx 1260 trading days)
            if len(nav_history) > 1260:
                nav_5y = float(nav_history[1260]["nav"])
                ret_5y = ((latest_nav - nav_5y) / nav_5y) * 100
                cagr_5y = ((latest_nav / nav_5y) ** (1/5) - 1) * 100
                returns_text += f"  - 5-Year Return: {ret_5y:+.2f}% (CAGR: {cagr_5y:.2f}%)\n"

        except (ValueError, ZeroDivisionError, IndexError):
            pass

    # Build comprehensive text document
    text = f"""
MUTUAL FUND SCHEME INFORMATION
================================
Scheme Name: {meta.get('scheme_name', fund_db.get('scheme_name', 'N/A'))}
Fund House (AMC): {meta.get('fund_house', fund_db.get('fund_house', 'N/A'))}
Scheme Code: {meta.get('scheme_code', fund_db.get('scheme_code', 'N/A'))}
Scheme Type: {meta.get('scheme_type', 'N/A')}
Scheme Category: {meta.get('scheme_category', fund_db.get('scheme_category', 'N/A'))}

CURRENT NAV:
  - NAV: ₹{fund_db.get('net_asset_value', 'N/A')}
  - Date: {fund_db.get('nav_date', 'N/A')}

PERFORMANCE / RETURNS:
{returns_text if returns_text else '  - Historical returns data not available.'}

NAV HISTORY:
  - Total NAV data points: {len(nav_history)}
  - Earliest NAV date: {nav_history[-1]['date'] if nav_history else 'N/A'}
  - Latest NAV date: {nav_history[0]['date'] if nav_history else 'N/A'}
""".strip()

    return text


def store_fund_details(scheme_code: int, api_data: dict, fund_text: str):
    """Store enriched details in the database."""
    meta = api_data.get("meta", {})

    with get_connection() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO fund_details (
                scheme_code, fund_manager, investment_objective,
                launch_date, raw_json, updated_at
            ) VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (
            scheme_code,
            None,  # mfapi doesn't provide fund manager
            None,  # mfapi doesn't provide objective
            None,  # mfapi doesn't provide launch date
            json.dumps({"meta": meta, "nav_count": len(api_data.get("data", []))}),
        ))

        # Also update the funds table with any new info from the API
        conn.execute("""
            UPDATE funds SET
                fund_house = COALESCE(?, fund_house),
                scheme_type = COALESCE(?, scheme_type),
                scheme_category = COALESCE(?, scheme_category),
                updated_at = CURRENT_TIMESTAMP
            WHERE scheme_code = ?
        """, (
            meta.get("fund_house"),
            meta.get("scheme_type"),
            meta.get("scheme_category"),
            scheme_code,
        ))

        conn.commit()


def save_fund_text(scheme_code: int, fund_text: str, output_dir: str = "data/fund_texts"):
    """Save the fund text document to disk for later ingestion."""
    os.makedirs(output_dir, exist_ok=True)
    filepath = os.path.join(output_dir, f"{scheme_code}.txt")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(fund_text)


def main():
    """Main enrichment pipeline."""
    import argparse
    parser = argparse.ArgumentParser(description="Enrich fund data from mfapi.in")
    parser.add_argument("--limit", type=int, default=100,
                        help="Max number of schemes to enrich (default: 100)")
    parser.add_argument("--delay", type=float, default=0.5,
                        help="Delay between API calls in seconds (default: 0.5)")
    args = parser.parse_args()

    start = time.time()

    print("=" * 60)
    print("🔍 Scheme Details Enricher — mfapi.in")
    print("=" * 60)

    init_database()

    # Get schemes that need enrichment
    schemes = get_schemes_to_enrich(limit=args.limit)
    print(f"📋 Found {len(schemes)} schemes to enrich (limit: {args.limit})")

    if not schemes:
        print("✅ All schemes already enriched! Run scrape_nav.py first if DB is empty.")
        return

    success = 0
    failed = 0
    texts_saved = 0

    for i, scheme in enumerate(schemes, 1):
        code = scheme["scheme_code"]
        name = scheme["scheme_name"]

        print(f"\n[{i}/{len(schemes)}] {name} (Code: {code})")

        # Fetch from API
        api_data = fetch_scheme_details(code)

        if api_data:
            # Build text document
            fund_text = build_fund_text(scheme, api_data)

            # Store in DB
            store_fund_details(code, api_data, fund_text)

            # Save text file
            save_fund_text(code, fund_text)
            texts_saved += 1

            success += 1
            print(f"   ✅ Enriched + text saved")
        else:
            failed += 1
            print(f"   ❌ API returned no data")

        # Rate limiting
        if i < len(schemes):
            time.sleep(args.delay)

    elapsed = time.time() - start
    print(f"\n{'=' * 60}")
    print(f"📊 Results: {success} enriched, {failed} failed, {texts_saved} texts saved")
    print(f"⏱️  Completed in {elapsed:.1f} seconds")


if __name__ == "__main__":
    main()
