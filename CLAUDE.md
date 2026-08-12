# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project does

Gmail scraper and dashboard builder for Keller's Life OS. Scrapes Gmail (personal + school accounts) for recruiting, finance, and school signals, classifies them, deduplicates against local JSON files, and writes structured entries into `data/*.json`. A React/Vite site reads from `public/data/dashboard.json` and is deployed on Vercel.

## Running the script

```bash
# Activate venv first (always required)
source venv/bin/activate

# Dry run — preview without writing anything
python main.py --dry-run

# Live run — scrape Gmail, update data/*.json, rebuild site
python main.py

# Only look at emails from the last 30 days
python main.py --since 30

# Scrape only one account
python main.py --accounts personal
python main.py --accounts school

# Skip health log backfill
python main.py --no-health

# Combine flags
python main.py --dry-run --since 7 --accounts personal
```

First run for each account triggers a browser OAuth flow and writes a token file. Subsequent runs use cached tokens.

## Refreshing the finance dashboard

```bash
# Step 1 — open all bank sites at once
venv/bin/python main.py --csv-open

# Step 2 — download CSVs from each bank (no need to move them, script finds them in ~/Downloads)

# Step 3 — parse and regenerate
venv/bin/python main.py --csv
```

Supported accounts: Capital One Checking (2657), Capital One Savings (2125), Discover It, Chase Sapphire Preferred, Schwab Custodial Brokerage, Fidelity Roth IRA. Missing CSVs keep their last-known values from the previous snapshot.

## Required credentials

| File | Purpose |
|---|---|
| `credentials.json` | Google OAuth client for personal Gmail |
| `credentials_school.json` | Google OAuth client for school Gmail (separate GCP OAuth client required) |
| `token_personal.json` | Auto-generated after first personal Gmail auth |
| `token_school.json` | Auto-generated after first school Gmail auth |

All credential and token files are gitignored. On first run, `token.json` (legacy name) is auto-migrated to `token_personal.json`.

**Important:** Both Gmail accounts require separate OAuth Desktop client IDs in Google Cloud Console — reusing the same client for two accounts invalidates the first token.

## Architecture

```
main.py          orchestrates steps; handles CLI flags; calls _fetch_all_accounts() across both accounts
gmail_scraper.py OAuth2 auth per account (separate token files); ACCOUNTS dict maps name → (creds, token)
classifier.py    pure functions: email dict → recruiting/finance/school dict (or None if ambiguous/promo)
json_writer.py   writes to data/*.json with deduplication; replaces old Notion writer
csv_scraper.py   parses bank CSV exports → financial_snapshot_YYYY-MM-DD.json
config.py        Gmail search queries, stage keywords, target companies
```

Data flow: `main.py` → `gmail_scraper.fetch_emails(query, account=...)` → `classifier.*` → `json_writer.*` → `_merge_dashboard()` → `public/data/dashboard.json` → Vercel

## Data files

| File | Purpose |
|---|---|
| `data/recruiting.json` | Canonical source for recruiting pipeline entries |
| `data/school.json` | School deadlines |
| `data/health.json` | Health log entries |
| `financial_snapshot_YYYY-MM-DD.json` | Finance snapshot (gitignored) |
| `public/data/dashboard.json` | Generated — do not edit directly; rebuilt by `_merge_dashboard()` |

**Always edit `data/*.json`, never `public/data/dashboard.json` directly** — the latter is overwritten on every run.

## Classifier design

Three-tier filter applied in order for every email:
1. **Blocklist** — domain/root in `_RECRUITING_BLOCKLIST`, finance domain, or promo/generic-outreach subject → skip
2. **Signal check** — recruiting requires strong subject keyword or sender in `TARGET_COMPANIES`; school requires 1 strong keyword OR 2+ weak keywords AND an academic subject
3. **Field extraction** — company from domain root (with override map), role from subject-line patterns first then body, stage from `STAGE_KEYWORDS` priority order, dates via regex

## Git rules

- Never add `Co-Authored-By: Claude` or any AI co-author trailer to commits. Ever.

## Key behaviors to preserve

- Script is idempotent — safe to re-run; dedup checks `data/*.json` before every insert.
- `--dry-run` must never write to any file.
- Classifiers return `None` for ambiguous emails rather than creating noisy entries (quality > quantity).
- Recruiting stage inference priority: Offer → Interview → OA → Phone Screen → Applied (default).
