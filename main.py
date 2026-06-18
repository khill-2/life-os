#!/usr/bin/env python3
"""
Life OS — cold-start population script.

Scrapes Gmail (personal + school) for recruiting, finance, and school signals,
then writes structured entries into the corresponding Notion databases.
Also backfills the Health Log with the past 7 days.

Usage:
    python main.py             # live run (writes to Notion)
    python main.py --dry-run   # preview only, no API writes
"""

import argparse
import sys

from config import GMAIL_QUERIES, MAX_RESULTS_PER_QUERY
from gmail_scraper import fetch_emails, ACCOUNTS
from classifier import classify_recruiting, classify_school
from json_writer import write_recruiting, write_school, write_health_backfill
from site_generator import generate_site


def parse_args():
    p = argparse.ArgumentParser(description="Populate Life OS Notion databases from Gmail.")
    p.add_argument("--dry-run",   action="store_true", help="Print what would be written without calling Notion.")
    p.add_argument("--since",     type=int, default=None, metavar="DAYS",
                   help="Only look at emails from the last N days (default: all).")
    p.add_argument("--accounts",  nargs="+", default=None, metavar="ACCOUNT",
                   help=f"Which accounts to scrape (default: all). Choices: {list(ACCOUNTS)}")
    p.add_argument("--no-health", action="store_true", help="Skip Health Log backfill.")
    p.add_argument("--dashboard", action="store_true", help="Print terminal finance dashboard and exit.")
    return p.parse_args()


def _build_query(base_query: str, since_days: int | None) -> str:
    if since_days:
        return f"({base_query}) newer_than:{since_days}d"
    return base_query


def _fetch_all_accounts(query: str, max_results: int, accounts: list[str]) -> list[dict]:
    """Fetch emails matching query across all configured accounts."""
    all_emails = []
    for account in accounts:
        try:
            emails = fetch_emails(query, max_results, account=account)
            all_emails.extend(emails)
        except FileNotFoundError as e:
            print(f"  ⚠️  Skipping {account} account: {e}")
        except Exception as e:
            print(f"  ⚠️  Error fetching from {account} account: {e}")
    return all_emails


def main():
    args     = parse_args()
    dry_run  = args.dry_run
    accounts = args.accounts or list(ACCOUNTS.keys())

    if args.dashboard:
        from site_generator import show_terminal_finance
        show_terminal_finance()
        return

    # Validate requested accounts
    invalid = [a for a in accounts if a not in ACCOUNTS]
    if invalid:
        print(f"❌ Unknown accounts: {invalid}. Valid: {list(ACCOUNTS)}")
        sys.exit(1)

    if dry_run:
        print("=== DRY RUN MODE — nothing will be written to Notion ===\n")
    if args.since:
        print(f"Looking back {args.since} days only.\n")

    # ------------------------------------------------------------------
    # Step 1 — Gmail scrape + classify
    # ------------------------------------------------------------------
    print(f"Fetching emails from Gmail ({', '.join(accounts)} account(s))...")

    recruiting_entries: list[dict] = []
    school_entries:     list[dict] = []

    print("  → Searching recruiting signals...")
    for email in _fetch_all_accounts(
        _build_query(GMAIL_QUERIES["recruiting"], args.since), MAX_RESULTS_PER_QUERY, accounts
    ):
        entry = classify_recruiting(email)
        if entry:
            recruiting_entries.append(entry)

    print("  → Searching school/deadline signals...")
    for email in _fetch_all_accounts(
        _build_query(GMAIL_QUERIES["school"], args.since), MAX_RESULTS_PER_QUERY, accounts
    ):
        entry = classify_school(email)
        if entry:
            school_entries.append(entry)

    # Deduplicate within each batch
    def _dedup(entries: list[dict], key: str) -> list[dict]:
        seen = set()
        out  = []
        for e in entries:
            k = e[key].lower().strip()
            if k not in seen:
                seen.add(k)
                out.append(e)
        return out

    recruiting_entries = _dedup(recruiting_entries, "company")
    school_entries     = _dedup(school_entries,     "assignment")

    print(f"\nClassified: {len(recruiting_entries)} recruiting, {len(school_entries)} school\n")

    # ------------------------------------------------------------------
    # Step 2 — Write to Notion
    # ------------------------------------------------------------------
    total_skipped = 0

    print("Writing to local data...")
    r_added, r_skipped = write_recruiting(recruiting_entries, dry_run=dry_run)
    total_skipped += r_skipped

    s_added, s_skipped = write_school(school_entries, dry_run=dry_run)
    total_skipped += s_skipped

    # ------------------------------------------------------------------
    # Step 3 — Health log backfill
    # ------------------------------------------------------------------
    h_added = h_skipped = 0
    if not args.no_health:
        print("Backfilling Health Log...")
        h_added, h_skipped = write_health_backfill(dry_run=dry_run)
        total_skipped += h_skipped

    # ------------------------------------------------------------------
    # Step 4 — Summary
    # ------------------------------------------------------------------
    print()
    print(f"✅ Recruiting: {r_added} new entries added")
    print(f"✅ School:     {s_added} new entries added")
    print(f"✅ Health Log: {h_added} days backfilled")
    if total_skipped:
        print(f"⚠️  Skipped:   {total_skipped} duplicates")

    # Regenerate site after every sync
    print("\nRegenerating site...")
    generate_site()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nAborted.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
