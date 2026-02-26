"""
scrape_fund_managers.py — Build rich fund manager profiles from Groww.

This is what makes this platform DIFFERENT from Groww/Moneycontrol:
Instead of just showing fund manager names, we build detailed text profiles
with investing style, education, experience, and fund track records —
then store them in a vector DB so users can ask natural language questions
like "Which managers follow a value investing approach?" or
"What is Roshi Jain's experience with midcap stocks?"

Groww's __NEXT_DATA__ contains:
  - fund_manager_details[].person_name
  - fund_manager_details[].education
  - fund_manager_details[].experience
  - fund_manager_details[].funds_managed[{scheme_name, scheme_code}]
  - fund_manager (primary manager string)
  - scheme_category, investment_objective (for style analysis)

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


LLM = None

def get_ai_style_summary(name: str, education: str, experience: str, funds: list[str]) -> str:
    """Use Groq LLM to generate a detailed investing style summary based on the manager's profile."""
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
                time.sleep(4)  # Wait if rate limited
            else:
                return f"Experienced fund manager holding expertise in {', '.join(funds[:3])}."
    
    return "Diversified mutual fund management approach based on their portfolio of funds."


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


def find_groww_slug(scheme_name: str) -> str | None:
    """Find the Groww URL slug using their search API."""
    search_term = scheme_name.split(" - ")[0].strip()
    search_term = search_term.replace("  ", " ")

    url = f"https://groww.in/v1/api/search/v1/derived/scheme?q={search_term}&page=0&size=5"
    try:
        r = requests.get(url, headers=SEARCH_HEADERS, timeout=10)
        if r.status_code == 200:
            data = r.json()
            results = data.get("content", [])
            if results:
                name_lower = scheme_name.lower()
                for result in results:
                    search_id = result.get("direct_search_id") or result.get("search_id") or result.get("id", "")
                    result_name = (result.get("scheme_name") or "").lower()
                    base_search = search_term.lower()
                    if base_search in result_name or result_name in base_search:
                        return search_id
                first = results[0]
                return first.get("direct_search_id") or first.get("search_id") or first.get("id")
    except (requests.RequestException, json.JSONDecodeError):
        pass
    return None


def fetch_groww_page_data(slug: str) -> dict | None:
    """Fetch and parse Groww fund page __NEXT_DATA__."""
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


def extract_manager_profiles(server_data: dict) -> list[dict]:
    """
    Extract detailed fund manager profiles from Groww server data.

    Returns list of dicts with keys:
      - name, education, experience, funds_managed, categories
    """
    profiles = []
    manager_details = server_data.get("fund_manager_details", [])

    for mgr in manager_details:
        name = mgr.get("person_name", "").strip()
        if not name:
            continue

        education = mgr.get("education", "").strip()
        experience = mgr.get("experience", "").strip()

        # Extract funds managed
        funds_managed = []
        categories = []
        for fund in mgr.get("funds_managed", []):
            fund_name = fund.get("scheme_name", "")
            if fund_name:
                funds_managed.append(fund_name)

        # Get the scheme category for style inference
        cat = server_data.get("scheme_category", "")
        sub_cat = server_data.get("sub_category", "")
        if cat:
            categories.append(cat)
        if sub_cat:
            categories.append(sub_cat)

        profiles.append({
            "name": name,
            "education": education,
            "experience": experience,
            "funds_managed": funds_managed,
            "categories": categories,
            "fund_house": server_data.get("fund_house", ""),
            "date_from": mgr.get("date_from", ""),
        })

    # Fallback to primary fund_manager field
    if not profiles and server_data.get("fund_manager"):
        profiles.append({
            "name": server_data["fund_manager"].strip(),
            "education": "",
            "experience": "",
            "funds_managed": [],
            "categories": [server_data.get("scheme_category", "")],
            "fund_house": server_data.get("fund_house", ""),
            "date_from": "",
        })

    return profiles


def build_manager_profile_text(profile: dict, scheme_name: str) -> str:
    """
    Build a rich text profile for a fund manager.
    This is the KEY differentiator — enables RAG questions about investing style.
    """
    name = profile["name"]
    education = profile["education"]
    experience = profile["experience"]
    funds = profile["funds_managed"]
    fund_house = profile["fund_house"]
    categories = profile["categories"]

    # Generate rich investing style using AI
    print(f"      🤖 Generating AI investing style for {name}...")
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
        for f in funds[:15]:  # Limit to 15 funds
            text += f"  - {f}\n"
    else:
        text += f"  - {scheme_name}\n"

    text += f"\nTotal funds managed: {len(funds) if funds else 1}\n"

    return text.strip()


# ── Seen manager tracker (avoid duplicate profiles) ───────────────────
seen_managers = {}  # name -> profile_text


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
        content = re.sub(
            r'FUND MANAGER:.*?\n',
            f'FUND MANAGER: {manager_str}\n',
            content
        )
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

    # If profile already exists, append new fund info
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            existing = f.read()
        # Don't overwrite if already has richer content
        if len(profile_text) <= len(existing):
            return filepath

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(profile_text)

    return filepath


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Scrape rich fund manager profiles from Groww")
    parser.add_argument("--limit", type=int, default=5000,
                        help="Max number of funds to process (default: 5000)")
    parser.add_argument("--delay", type=float, default=1.5,
                        help="Delay between page requests (default: 1.5)")
    args = parser.parse_args()

    start = time.time()

    print("=" * 60)
    print("Fund Manager Profile Builder - Groww")
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

    # Group funds by base name to avoid redundant Groww fetches
    # (e.g., HDFC Flexi Cap Direct Growth + HDFC Flexi Cap Regular Growth share managers)
    processed_slugs = {}

    for i, fund in enumerate(funds, 1):
        code = fund["scheme_code"]
        name = fund["scheme_name"]

        print(f"\n[{i}/{len(funds)}] {name}")

        # Step 1: Find Groww slug
        slug = find_groww_slug(name)
        if not slug:
            not_found += 1
            print(f"   -> Groww slug not found")
            continue

        # Step 2: Check if we already fetched this slug's page
        if slug in processed_slugs:
            # Reuse cached profiles
            profiles = processed_slugs[slug]
        else:
            # Fetch page data
            server_data = fetch_groww_page_data(slug)
            if not server_data:
                not_found += 1
                print(f"   -> Page fetch failed")
                processed_slugs[slug] = []
                time.sleep(args.delay)
                continue

            profiles = extract_manager_profiles(server_data)
            processed_slugs[slug] = profiles
            time.sleep(args.delay)

        if not profiles:
            not_found += 1
            print(f"   -> No manager data on page")
            continue

        # Step 3: Process each manager
        manager_names = []
        for profile in profiles:
            manager_name = profile["name"]
            manager_names.append(manager_name)
            unique_managers.add(manager_name)

            # Build and save rich profile text
            if manager_name not in seen_managers:
                profile_text = build_manager_profile_text(profile, name)
                save_manager_profile(manager_name, profile_text)
                seen_managers[manager_name] = True
                profiles_saved += 1

        # Step 4: Update database and fund text file
        update_fund_manager_db(code, manager_names)
        update_fund_text_file(code, manager_names)
        managers_found += 1

        mgr_str = ", ".join(manager_names)
        print(f"   -> {mgr_str}")

    elapsed = time.time() - start
    print(f"\n{'=' * 60}")
    print(f"Results:")
    print(f"  Funds with managers found: {managers_found}")
    print(f"  Funds not found on Groww:  {not_found}")
    print(f"  Unique managers profiled:  {len(unique_managers)}")
    print(f"  Profile texts saved:       {profiles_saved}")
    print(f"  Time: {elapsed:.1f} seconds")
    print(f"\nProfiles saved to: data/manager_profiles/")
    print(f"Run 'python -m scripts.ingest_funds' to rebuild the vector store")


if __name__ == "__main__":
    main()
