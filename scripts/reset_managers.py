"""
reset_managers.py — Reset corrupted fund manager data.

The previous scraper assigned wrong managers (Bhavesh Jain, Bharat Lahoti)
to 5,132 funds due to a Groww search API slug-matching bug.

This script:
  1. Resets all fund_manager fields in the database to NULL
  2. Deletes wrong manager profile files
  3. Removes FUND MANAGER lines from fund text files

Run:  python -m scripts.reset_managers
"""

import sys
import os
import re
import glob

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database import init_database, get_connection


def main():
    print("=" * 60)
    print("Resetting corrupted fund manager data")
    print("=" * 60)

    init_database()

    # Step 1: Check current state
    with get_connection() as conn:
        total = conn.execute("SELECT COUNT(*) FROM fund_details").fetchone()[0]
        with_mgr = conn.execute(
            "SELECT COUNT(*) FROM fund_details WHERE fund_manager IS NOT NULL AND fund_manager != ''"
        ).fetchone()[0]
        print(f"\nBefore reset:")
        print(f"  Total fund_details rows: {total}")
        print(f"  Rows with fund_manager:  {with_mgr}")

    # Step 2: Reset fund_manager to NULL
    with get_connection() as conn:
        conn.execute("UPDATE fund_details SET fund_manager = NULL")
        conn.commit()
        print(f"\n  Reset {with_mgr} fund_manager entries to NULL")

    # Step 3: Delete wrong manager profile files
    profiles_dir = os.path.join("data", "manager_profiles")
    if os.path.exists(profiles_dir):
        files = glob.glob(os.path.join(profiles_dir, "*.txt"))
        for f in files:
            os.remove(f)
            print(f"  Deleted: {os.path.basename(f)}")
        print(f"  Removed {len(files)} manager profile files")
    else:
        print("  No manager_profiles directory found")

    # Step 4: Remove FUND MANAGER lines from fund text files
    texts_dir = os.path.join("data", "fund_texts")
    if os.path.exists(texts_dir):
        cleaned = 0
        for txt_file in glob.glob(os.path.join(texts_dir, "*.txt")):
            with open(txt_file, "r", encoding="utf-8") as f:
                content = f.read()

            if "FUND MANAGER:" in content:
                content = re.sub(r'\nFUND MANAGER:.*?\n', '\n', content)
                with open(txt_file, "w", encoding="utf-8") as f:
                    f.write(content)
                cleaned += 1

        print(f"  Cleaned FUND MANAGER from {cleaned} text files")

    # Step 5: Verify
    with get_connection() as conn:
        remaining = conn.execute(
            "SELECT COUNT(*) FROM fund_details WHERE fund_manager IS NOT NULL AND fund_manager != ''"
        ).fetchone()[0]
        print(f"\nAfter reset:")
        print(f"  Rows with fund_manager: {remaining}")

    print("\nDone! Run 'python -m scripts.scrape_fund_managers --limit 5000' to re-scrape correctly.")


if __name__ == "__main__":
    main()
