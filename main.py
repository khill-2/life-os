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
import glob
import json
import os
import socket
import subprocess
import sys
import webbrowser
from datetime import date

from config import GMAIL_QUERIES, MAX_RESULTS_PER_QUERY
from gmail_scraper import fetch_emails, ACCOUNTS
from classifier import classify_recruiting, classify_school
from json_writer import write_recruiting, write_school, write_health_backfill

_PREVIEW_PORT = 4173

_CATEGORY_COLORS = {
    "Food & Dining":          "#e07b54",
    "Food & Drink":           "#e07b54",
    "Restaurants":            "#e07b54",
    "Supermarkets":           "#c8845e",
    "Travel/Entertainment":   "#5b8dd9",
    "Travel/ Entertainment":  "#5b8dd9",
    "Travel":                 "#5b8dd9",
    "Entertainment":          "#9b59b6",
    "Housing":                "#f0c040",
    "Insurance":              "#50c878",
    "Workspace":              "#80cbc4",
    "Gas":                    "#ff8c42",
    "Gasoline":               "#ff8c42",
    "Shopping":               "#f06292",
    "Merchandise":            "#f06292",
    "Health":                 "#26a69a",
    "Subscriptions":          "#78909c",
    "Education":              "#7ec8e3",
    "Other":                  "#999999",
}

_SPEND_SKIP_CATEGORIES = {
    "payments and credits", "payment", "transfer", "transfers",
    "fees & adjustments", "rewards", "cashback",
}

# Description substrings → override category (case-insensitive, checked before bank category)
import re as _re
_DESCRIPTION_OVERRIDES: list[tuple] = [
    (_re.compile(r"rent",       _re.I), "Housing"),
    (_re.compile(r"grocery|grocer|whole foods|trader joe|safeway|kroger|albertsons", _re.I), "Supermarkets"),
    (_re.compile(r"netflix|spotify|hulu|disney\+|apple\.com/bill|youtube premium|amazon prime", _re.I), "Subscriptions"),
    (_re.compile(r"lyft|uber(?! eats)|taxi|mta|lirr|bart|caltrain|amtrak", _re.I), "Travel/Entertainment"),
    (_re.compile(r"uber eats|doordash|grubhub|instacart", _re.I), "Restaurants"),
    (_re.compile(r"cvs|walgreens|rite aid|pharmacy", _re.I), "Health"),
]

def _override_category(description: str, category: str) -> str:
    for pattern, override in _DESCRIPTION_OVERRIDES:
        if pattern.search(description):
            return override
    return category


def _snapshot_to_finance(snap: dict) -> dict:
    """Convert csv_scraper snapshot → React Finance panel format."""
    nws = snap.get("net_worth_summary", {})
    net_worth = {
        "total":      nws.get("total_assets", 0),
        "liabilities": nws.get("total_liabilities", 0),
        "cash":       nws.get("liquid_cash", 0),
        "taxable":    nws.get("taxable_investments", 0),
        "ira":        nws.get("tax_advantaged_investments", 0),
    }

    inc = snap.get("income_summary", {})
    avg_biweekly = inc.get("avg_biweekly_net", 0)
    income = {
        "avg_monthly_net": round(avg_biweekly * 26 / 12, 2),
        "ytd_net":         inc.get("ytd_net_income", 0),
        "source":          inc.get("source", ""),
    }

    # Monthly spending from credit card transactions
    # Different banks use opposite sign conventions (Chase: negative=purchase; Discover: positive=purchase)
    # So we filter by category presence (payments have empty/skip categories) and take abs(amt).
    monthly_spending: dict[str, dict[str, float]] = {}
    skip_types = {"checking", "savings", "taxable_brokerage", "roth_ira"}
    for acct in snap.get("accounts", {}).values():
        if acct.get("type") in skip_types:
            continue
        for t in acct.get("transactions", []):
            cat = t.get("category", "")
            cat = _override_category(t.get("description", ""), cat)
            if not cat or cat.lower() in _SPEND_SKIP_CATEGORIES:
                continue
            amt = abs(t.get("amount", 0))
            if amt == 0:
                continue
            month = t["date"][:7]  # "YYYY-MM"
            monthly_spending.setdefault(month, {})
            monthly_spending[month][cat] = round(
                monthly_spending[month].get(cat, 0) + amt, 2
            )

    monthly_totals = {m: round(sum(v.values()), 2) for m, v in monthly_spending.items()}
    latest_month = max(monthly_spending) if monthly_spending else ""
    total_spend_latest = monthly_totals.get(latest_month, 0)

    # Portfolio — combine Schwab + Fidelity positions
    schwab = snap.get("accounts", {}).get("schwab_brokerage", {})
    fidelity = snap.get("accounts", {}).get("fidelity_roth_ira", {})
    positions = []
    for p in schwab.get("positions", []) + fidelity.get("positions", []):
        if p.get("market_value", 0) <= 0:
            continue
        positions.append({
            "symbol":    p["symbol"].rstrip("*"),
            "value":     p["market_value"],
            "gain":      p.get("gain_loss", 0),
            "gain_pct":  p.get("gain_loss_pct", 0),
        })
    portfolio_total = sum(p["value"] for p in positions)
    portfolio_gain  = sum(p["gain"]  for p in positions)
    portfolio = {
        "positions":  positions,
        "total":      round(portfolio_total, 2),
        "total_gain": round(portfolio_gain, 2),
    }

    # Build category_colors from whatever categories appear
    all_cats = {c for month in monthly_spending.values() for c in month}
    category_colors = {c: _CATEGORY_COLORS.get(c, "#999999") for c in all_cats}

    # Brokerage YTD invested — sum MoneyLink deposits into Schwab this year
    cur_year = str(date.today().year)
    bro_ytd = sum(
        t["amount"] for t in schwab.get("transactions_ytd", [])
        if t.get("action", "").startswith("MoneyLink Transfer")
        and t.get("amount", 0) > 0
        and t.get("date", "").startswith(cur_year)
    )

    goals = snap.get("investment_goals", {})
    investment_goals = {
        "roth_ira": {
            "contributed": goals.get("roth_ira_2026_contributed", 0),
            "limit":       7500,
        },
        "brokerage": {
            "invested_ytd":   round(bro_ytd, 2),
            "monthly_target": goals.get("monthly_brokerage_target", 3000),
        },
    }

    return {
        "net_worth":        net_worth,
        "income":           income,
        "monthly_spending": monthly_spending,
        "monthly_totals":   monthly_totals,
        "latest_month":     latest_month,
        "total_spend_latest": total_spend_latest,
        "portfolio":        portfolio,
        "category_colors":  category_colors,
        "investment_goals": investment_goals,
    }

_STAGE_COLORS = {
    "Applying":     "#888888",
    "Applied":      "#666666",
    "Phone Screen": "#999999",
    "OA":           "#bbbbbb",
    "Interview":    "#dddddd",
    "Offer":        "#ffffff",
    "Rejected":     "#3a2020",
    "Closed":       "#333333",
}
_STAGE_ORDER = list(_STAGE_COLORS)


def _merge_dashboard():
    """Sync data/*.json → public/data/dashboard.json so the React build is current."""
    dash_path = os.path.join("public", "data", "dashboard.json")
    existing = {}
    if os.path.exists(dash_path):
        with open(dash_path) as f:
            existing = json.load(f)

    # Finance: convert the latest snapshot if available, else preserve existing
    snaps = sorted(glob.glob("financial_snapshot_*.json"))
    finance = existing.get("finance", {})
    if snaps:
        with open(snaps[-1]) as f:
            snap = json.load(f)
        converted = _snapshot_to_finance(snap)
        if converted.get("net_worth", {}).get("total", 0) > 0:
            finance = converted

    # Load recruiting
    rec_path = os.path.join("data", "recruiting.json")
    rec_entries = []
    if os.path.exists(rec_path):
        with open(rec_path) as f:
            rec_entries = json.load(f).get("entries", [])
    by_stage = {s: 0 for s in _STAGE_ORDER}
    for e in rec_entries:
        s = e.get("stage", "Applied")
        if s in by_stage:
            by_stage[s] += 1
    active = sum(v for s, v in by_stage.items() if s != "Closed")
    recruiting = {
        "entries":      rec_entries,
        "stats":        {"by_stage": by_stage, "active": active},
        "stage_colors": _STAGE_COLORS,
    }

    # Load school
    sch_path = os.path.join("data", "school.json")
    sch_entries = []
    if os.path.exists(sch_path):
        with open(sch_path) as f:
            sch_entries = json.load(f).get("entries", [])

    # Load health
    health_path = os.path.join("data", "health.json")
    health_entries = []
    if os.path.exists(health_path):
        with open(health_path) as f:
            health_entries = json.load(f).get("entries", [])

    today = date.today()
    dashboard = {
        "updated":     today.isoformat(),
        "month_label": today.strftime("%B %Y"),
        "finance":     finance,
        "recruiting":  recruiting,
        "school":      {"entries": sch_entries},
        "health":      {"entries": health_entries},
    }

    os.makedirs(os.path.join("public", "data"), exist_ok=True)
    with open(dash_path, "w") as f:
        json.dump(dashboard, f, indent=2)


def _port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("localhost", port)) == 0


def _build_site():
    _merge_dashboard()
    subprocess.run(["npm", "run", "build"], check=True)
    if not _port_open(_PREVIEW_PORT):
        subprocess.Popen(
            ["npm", "run", "preview"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        import time; time.sleep(1)
    webbrowser.open(f"http://localhost:{_PREVIEW_PORT}")


def parse_args():
    p = argparse.ArgumentParser(description="Populate Life OS Notion databases from Gmail.")
    p.add_argument("--dry-run",   action="store_true", help="Print what would be written without calling Notion.")
    p.add_argument("--since",     type=int, default=None, metavar="DAYS",
                   help="Only look at emails from the last N days (default: all).")
    p.add_argument("--accounts",  nargs="+", default=None, metavar="ACCOUNT",
                   help=f"Which accounts to scrape (default: all). Choices: {list(ACCOUNTS)}")
    p.add_argument("--no-health", action="store_true", help="Skip Health Log backfill.")
    p.add_argument("--dashboard", action="store_true", help="Print terminal finance dashboard and exit.")
    p.add_argument("--csv",       action="store_true", help="Parse CSV exports from csv_imports/ and regenerate finance dashboard.")
    p.add_argument("--csv-open",  action="store_true", help="Open each bank's download page in the browser, then exit.")
    p.add_argument("--api",       action="store_true", help="Fetch live data from Teller + SnapTrade and regenerate dashboard.")
    p.add_argument("--api-link",  action="store_true", help="Link bank/brokerage accounts via Teller Connect + SnapTrade portal.")
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
        print("Dashboard has moved to React/Vite. Run: npm run dev")
        return

    if args.csv_open:
        from csv_scraper import open_bank_sites
        open_bank_sites()
        return

    if getattr(args, "api_link", False):
        from api_scraper import link_teller, link_snaptrade
        link_teller()
        link_snaptrade()
        return

    if getattr(args, "api", False):
        from api_scraper import generate_snapshot as api_generate, save_snapshot as api_save
        existing_snap = {}
        existing_files = sorted(glob.glob("financial_snapshot_*.json"))
        if existing_files:
            with open(existing_files[-1]) as f:
                existing_snap = json.load(f)
        snap = api_generate(existing_snap)
        filename = api_save(snap)
        print(f"\nSaved → {filename}")
        print("Regenerating site...")
        _build_site()
        return

    if args.csv:
        from csv_scraper import generate_snapshot, save_snapshot
        print("Parsing CSV exports from csv_imports/...")
        existing_snap = {}
        existing_files = sorted(glob.glob("financial_snapshot_*.json"))
        if existing_files:
            with open(existing_files[-1]) as f:
                existing_snap = json.load(f)
        snap = generate_snapshot(existing_snap)
        filename = save_snapshot(snap)
        print(f"\nSaved → {filename}")
        print("Regenerating site...")
        _build_site()
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
    _build_site()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nAborted.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
