"""
refresh_data.py — One-command data refresh for production use.

Updates NAV data, enriches new funds, and optionally re-scrapes managers.
Designed to be run daily via cron job or manually.

Run:  python -m scripts.refresh_data
      python -m scripts.refresh_data --full     (includes fund managers)
"""

import sys
import os
import time
import subprocess

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def run_step(description: str, command: list[str]):
    """Run a pipeline step and report status."""
    print(f"\n{'─' * 50}")
    print(f"Step: {description}")
    print(f"{'─' * 50}")
    
    start = time.time()
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        )
        elapsed = time.time() - start
        
        if result.returncode == 0:
            # Print last 5 lines of output
            lines = result.stdout.strip().split("\n")
            for line in lines[-5:]:
                print(f"  {line}")
            print(f"  Done in {elapsed:.1f}s")
            return True
        else:
            print(f"  FAILED (exit code {result.returncode})")
            if result.stderr:
                print(f"  Error: {result.stderr[:300]}")
            return False
    except Exception as e:
        print(f"  ERROR: {e}")
        return False


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Refresh mutual fund data")
    parser.add_argument("--full", action="store_true",
                        help="Full refresh including fund manager re-scrape")
    parser.add_argument("--rebuild-vectors", action="store_true",
                        help="Rebuild FAISS vector store after data refresh")
    args = parser.parse_args()

    print("=" * 60)
    print("SID Chatbot — Data Refresh Pipeline")
    print("=" * 60)

    start = time.time()

    # Step 1: Refresh NAV data from AMFI
    ok = run_step(
        "Refreshing NAV data from AMFI India",
        [sys.executable, "-m", "scripts.scrape_nav"]
    )
    if not ok:
        print("\nNAV refresh failed. Check internet connection.")
        return

    # Step 2: Enrich new funds with returns data
    run_step(
        "Enriching new funds with returns data (top 500)",
        [sys.executable, "-m", "scripts.scrape_scheme_details", "--limit", "500", "--delay", "0.3"]
    )

    # Step 3: Optionally re-scrape fund managers
    if args.full:
        run_step(
            "Scraping fund manager data (this takes a while)",
            [sys.executable, "-m", "scripts.scrape_fund_managers", "--limit", "5000", "--delay", "1.0", "--skip-profiles"]
        )

    # Step 4: Optionally rebuild vector store
    if args.rebuild_vectors:
        run_step(
            "Rebuilding FAISS vector store",
            [sys.executable, "-m", "scripts.ingest_funds", "--texts-only"]
        )

    elapsed = time.time() - start
    print(f"\n{'=' * 60}")
    print(f"Data refresh complete in {elapsed:.1f}s")
    print(f"Run 'streamlit run app.py' to see updated data")


if __name__ == "__main__":
    main()
