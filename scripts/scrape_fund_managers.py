"""
scrape_fund_managers.py — Build rich fund manager profiles from Groww.

FIXED VERSION (v2): Uses Groww v3 search API for slug discovery + page
scraping for manager details. The v1 search API was broken (returned
Edelweiss results for every query).

Pipeline:
  1. v3 search API → get correct Groww slug + validate AMC from title
  2. Fetch Groww fund page → extract fund_manager from __NEXT_DATA__
  3. Validate AMC from page data before assigning
  4. Optionally build rich profiles (education, experience) with AI

Run:  python -m scripts.scrape_fund_managers --limit 5000
"""

import sys
import os
import re
import json
import time
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database import init_database, get_connection


HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml',
}

SEARCH_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'application/json',
}


# ── AMC name normalization ────────────────────────────────────────────
AMC_KEYWORDS = {
    "SBI Mutual Fund": ["sbi"],
    "ICICI Prudential Mutual Fund": ["icici"],
    "HDFC Mutual Fund": ["hdfc"],
    "Nippon India Mutual Fund": ["nippon"],
    "Kotak Mahindra Mutual Fund": ["kotak"],
    "Aditya Birla Sun Life Mutual Fund": ["aditya", "birla"],
    "UTI Mutual Fund": ["uti"],
    "Axis Mutual Fund": ["axis"],
    "Mirae Asset Mutual Fund": ["mirae"],
    "DSP Mutual Fund": ["dsp"],
    "Franklin Templeton Mutual Fund": ["franklin"],
    "Tata Mutual Fund": ["tata"],
    "Bandhan Mutual Fund": ["bandhan"],
    "Motilal Oswal Mutual Fund": ["motilal"],
    "Edelweiss Mutual Fund": ["edelweiss"],
    "Canara Robeco Mutual Fund": ["canara"],
    "HSBC Mutual Fund": ["hsbc"],
    "Baroda BNP Paribas Mutual Fund": ["baroda", "bnp"],
    "LIC Mutual Fund": ["lic"],
    "360 ONE Mutual Fund": ["360 one", "iifl one", "iifl mutual", "iifl"],
    "Bajaj Finserv Mutual Fund": ["bajaj"],
    "Navi Mutual Fund": ["navi"],
    "Quant Mutual Fund": ["quant"],
    "PPFAS Mutual Fund": ["ppfas", "parag parikh"],
    "JM Financial Mutual Fund": ["jm financial"],
    "Union Mutual Fund": ["union"],
    "Sundaram Mutual Fund": ["sundaram"],
    "Mahindra Manulife Mutual Fund": ["mahindra"],
    "IIFL Mutual Fund": ["iifl"],
    "WhiteOak Capital Mutual Fund": ["whiteoak"],
    "Trust Mutual Fund": ["trust"],
    "Invesco Mutual Fund": ["invesco"],
    "PGIM India Mutual Fund": ["pgim"],
    "Shriram Mutual Fund": ["shriram"],
    "Groww Mutual Fund": ["groww"],
    "Helios Mutual Fund": ["helios"],
}


LLM = None

def get_ai_style_summary(name: str, education: str, experience: str, funds: list[str]) -> str:
    """Use Groq LLM to generate a detailed investing style summary."""
    global LLM
    if LLM is None:
        try:
            from src.rag_chain import get_llm
            LLM = get_llm()
        except ImportError:
            return "Diversified mutual fund management approach."

    prompt = f"""You are an expert mutual fund analyst. Analyze the following mutual fund manager and write a professional, engaging 3-4 sentence summary of their likely investing style, expertise, and approach. Do NOT invent facts. Base it strictly on their education, past experience, and the types of funds they manage.

Manager Name: {name}
Education: {education or 'Not available'}
Experience: {experience or 'Not available'}
Funds Managed: {', '.join(funds[:15])}

Write ONLY the summary paragraph. No introductory text."""

    for attempt in range(3):
        try:
            response = LLM.invoke(prompt)
            return response.content.strip()
        except Exception as e:
            if "429" in str(e) or "rate limit" in str(e).lower():
                time.sleep(4)
            else:
                return f"Experienced fund manager with expertise in {', '.join(funds[:3])}."

    return "Diversified mutual fund management approach."


def get_funds_needing_managers(limit: int = 5000) -> list[dict]:
    """Get enriched funds that don't yet have fund manager info."""
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT f.scheme_code, f.scheme_name, f.fund_house, f.scheme_category,
                   f.isin_growth
            FROM funds f
            INNER JOIN fund_details fd ON f.scheme_code = fd.scheme_code
            WHERE (fd.fund_manager IS NULL OR fd.fund_manager = '')
              AND f.is_active = 1
              AND f.net_asset_value IS NOT NULL
            ORDER BY f.fund_house, f.scheme_name
            LIMIT ?
        """, (limit,)).fetchall()
        return [dict(row) for row in rows]


def validate_amc_from_title(fund_house: str, groww_title: str) -> bool:
    """Validate that a Groww search result title matches the expected AMC."""
    title_lower = groww_title.lower()

    # Check against known AMC keywords
    keywords = AMC_KEYWORDS.get(fund_house, [])
    if keywords:
        return any(kw in title_lower for kw in keywords)

    # Fallback: first significant word of AMC name must appear in title
    for word in fund_house.split():
        word_lower = word.lower()
        if len(word_lower) > 2 and word_lower not in ("mutual", "fund", "india"):
            return word_lower in title_lower

    return False


def find_groww_slug_v3(scheme_name: str, fund_house: str) -> str | None:
    """
    Find the Groww URL slug using the v3 global search API.
    
    The v1 search API is broken (returns Edelweiss for everything).
    The v3 API returns correct results with proper slug IDs.
    """
    search_term = scheme_name.split(" - ")[0].strip().replace("  ", " ")

    url = (
        f"https://groww.in/v1/api/search/v3/query/global/st_query"
        f"?page=0&query={requests.utils.quote(search_term)}&size=10&web=true"
    )
    try:
        r = requests.get(url, headers=SEARCH_HEADERS, timeout=10)
        if r.status_code != 200:
            return None

        data = r.json()
        results = data.get("data", {}).get("content", [])
        if not results:
            return None

        # Find first result that:
        # 1. Is a Scheme (not ETF/Stock)
        # 2. Matches our AMC
        for result in results:
            entity_type = result.get("sub_entity_type") or result.get("entity_type", "")
            if entity_type not in ("Scheme", "Nfo"):
                continue

            title = result.get("title", "")
            if validate_amc_from_title(fund_house, title):
                slug = result.get("search_id") or result.get("id")
                if slug:
                    # Remove "nfo-" prefix if present
                    if slug.startswith("nfo-"):
                        slug = slug[4:]
                    return slug

        # NO fallback — return None if no AMC match
        return None

    except (requests.RequestException, json.JSONDecodeError):
        return None


def fetch_groww_page_data(slug: str) -> dict | None:
    """Fetch and parse Groww fund page __NEXT_DATA__ for manager details."""
    url = f"https://groww.in/mutual-funds/{slug}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=10, allow_redirects=True)
        if r.status_code == 200:
            match = re.search(r'__NEXT_DATA__[^>]*>(.+?)</script', r.text, re.DOTALL)
            if match:
                data = json.loads(match.group(1))
                return data.get("props", {}).get("pageProps", {}).get("mfServerSideData", {})
    except (requests.RequestException, json.JSONDecodeError):
        pass
    return None


def extract_manager_info(server_data: dict) -> list[dict]:
    """Extract manager name(s) and detailed profiles from Groww page data."""
    profiles = []
    manager_details = server_data.get("fund_manager_details", [])

    for mgr in manager_details:
        name = mgr.get("person_name", "").strip()
        if not name:
            continue

        profiles.append({
            "name": name,
            "education": (mgr.get("education") or "").strip(),
            "experience": (mgr.get("experience") or "").strip(),
            "funds_managed": [f.get("scheme_name", "") for f in mgr.get("funds_managed", []) if f.get("scheme_name")],
            "fund_house": server_data.get("fund_house", ""),
            "date_from": mgr.get("date_from", ""),
        })

    # Fallback to primary fund_manager string
    if not profiles and server_data.get("fund_manager"):
        profiles.append({
            "name": server_data["fund_manager"].strip(),
            "education": "",
            "experience": "",
            "funds_managed": [],
            "fund_house": server_data.get("fund_house", ""),
            "date_from": "",
        })

    return profiles


def build_manager_profile_text(profile: dict, scheme_name: str) -> str:
    """Build a rich text profile for a fund manager."""
    name = profile["name"]
    education = profile["education"]
    experience = profile["experience"]
    funds = profile["funds_managed"]
    fund_house = profile["fund_house"]

    print(f"      Generating AI investing style for {name}...")
    style = get_ai_style_summary(name, education, experience, funds if funds else [scheme_name])

    text = f"""FUND MANAGER PROFILE
====================
Name: {name}
Fund House (AMC): {fund_house}
Currently Managing: {scheme_name}

EDUCATION & QUALIFICATIONS:
{education if education else '  Not available'}

PROFESSIONAL EXPERIENCE:
{experience if experience else '  Not available'}

INVESTING STYLE & APPROACH:
  {style}

FUNDS MANAGED BY {name.upper()}:
"""
    if funds:
        for f in funds[:15]:
            text += f"  - {f}\n"
    else:
        text += f"  - {scheme_name}\n"

    text += f"\nTotal funds managed: {len(funds) if funds else 1}\n"
    return text.strip()


# Track managers already profiled
seen_managers = {}


def update_fund_manager_db(scheme_code: int, managers: list[str]):
    """Update fund manager names in database."""
    manager_str = ", ".join(managers) if managers else None
    with get_connection() as conn:
        conn.execute("""
            UPDATE fund_details
            SET fund_manager = ?, updated_at = CURRENT_TIMESTAMP
            WHERE scheme_code = ?
        """, (manager_str, scheme_code))
        conn.commit()


def update_fund_text_file(scheme_code: int, manager_names: list[str],
                          texts_dir: str = "data/fund_texts"):
    """Add fund manager names to the fund text file."""
    filepath = os.path.join(texts_dir, f"{scheme_code}.txt")
    if not os.path.exists(filepath):
        return

    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    manager_str = ", ".join(manager_names)

    if "FUND MANAGER:" in content:
        content = re.sub(r'FUND MANAGER:.*?\n', f'FUND MANAGER: {manager_str}\n', content)
    else:
        content = content.replace(
            "\n\nCURRENT NAV:",
            f"\n\nFUND MANAGER: {manager_str}\n\nCURRENT NAV:"
        )

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)


def save_manager_profile(manager_name: str, profile_text: str,
                         output_dir: str = "data/manager_profiles"):
    """Save a fund manager profile text for vector store ingestion."""
    os.makedirs(output_dir, exist_ok=True)
    safe_name = re.sub(r'[^a-zA-Z0-9 ]', '', manager_name).strip().replace(' ', '_').lower()
    filepath = os.path.join(output_dir, f"{safe_name}.txt")

    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            existing = f.read()
        if len(profile_text) <= len(existing):
            return filepath

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(profile_text)
    return filepath


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Scrape fund manager profiles from Groww (v2 - fixed)")
    parser.add_argument("--limit", type=int, default=5000,
                        help="Max funds to process (default: 5000)")
    parser.add_argument("--delay", type=float, default=1.5,
                        help="Delay between page requests (default: 1.5)")
    parser.add_argument("--skip-profiles", action="store_true",
                        help="Skip rich profile generation (faster, managers only)")
    args = parser.parse_args()

    start = time.time()

    print("=" * 60)
    print("Fund Manager Scraper v2 (Fixed - v3 Search + AMC Validation)")
    print("=" * 60)

    init_database()

    funds = get_funds_needing_managers(limit=args.limit)
    print(f"Found {len(funds)} funds to process (limit: {args.limit})")

    if not funds:
        print("All funds already have manager info!")
        return

    managers_found = 0
    profiles_saved = 0
    unique_managers = set()
    not_found = 0
    page_errors = 0

    # Cache: slug -> page server_data (avoid re-fetching same page)
    slug_cache = {}

    for i, fund in enumerate(funds, 1):
        code = fund["scheme_code"]
        name = fund["scheme_name"]
        fund_house = fund["fund_house"] or ""

        print(f"\n[{i}/{len(funds)}] {name}")

        # Step 1: Find correct Groww slug via v3 search
        slug = find_groww_slug_v3(name, fund_house)
        if not slug:
            not_found += 1
            print(f"   -> No matching fund on Groww")
            time.sleep(0.3)
            continue

        # Step 2: Fetch page data (with caching)
        if slug in slug_cache:
            server_data = slug_cache[slug]
        else:
            server_data = fetch_groww_page_data(slug)
            slug_cache[slug] = server_data
            time.sleep(args.delay)

        if not server_data:
            page_errors += 1
            print(f"   -> Page fetch failed for slug: {slug}")
            continue

        # Step 3: Validate AMC from page data
        page_fund_house = server_data.get("fund_house", "")
        if not validate_amc_from_title(fund_house, page_fund_house):
            not_found += 1
            print(f"   -> AMC mismatch: expected '{fund_house}', got '{page_fund_house}'")
            continue

        # Step 4: Extract manager info
        manager_profiles = extract_manager_info(server_data)
        if not manager_profiles:
            not_found += 1
            print(f"   -> No manager data on page")
            continue

        manager_names = [p["name"] for p in manager_profiles]

        # Step 5: Update database + text files
        update_fund_manager_db(code, manager_names)
        update_fund_text_file(code, manager_names)
        managers_found += 1

        for m in manager_names:
            unique_managers.add(m)

        mgr_str = ", ".join(manager_names)
        print(f"   -> {mgr_str}")

        # Step 6: Build rich profiles for new managers
        if not args.skip_profiles:
            for profile in manager_profiles:
                pname = profile["name"]
                if pname not in seen_managers:
                    profile_text = build_manager_profile_text(profile, name)
                    save_manager_profile(pname, profile_text)
                    seen_managers[pname] = True
                    profiles_saved += 1

    elapsed = time.time() - start
    print(f"\n{'=' * 60}")
    print(f"Results:")
    print(f"  Funds with managers found: {managers_found}")
    print(f"  Funds not found on Groww:  {not_found}")
    print(f"  Page fetch errors:         {page_errors}")
    print(f"  Unique managers found:     {len(unique_managers)}")
    if not args.skip_profiles:
        print(f"  Profile texts saved:       {profiles_saved}")
    print(f"  Time: {elapsed:.1f} seconds")
    print(f"\nRun 'python -m scripts.ingest_funds' to rebuild the vector store")


if __name__ == "__main__":
    main()
