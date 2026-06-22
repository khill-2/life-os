# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project does

Cold-start population script for Keller's Notion-based Life OS. Scrapes Gmail (personal + school accounts) for recruiting, finance, and school signals, classifies them, deduplicates against existing Notion entries, and writes structured rows into four databases. Also backfills the Health Log with the past 7 days.

## Running the script

```bash
# Activate venv first (always required)
source venv/bin/activate

# Dry run — preview without writing to Notion
python main.py --dry-run

# Live run
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
| `.env` | `NOTION_TOKEN` — Notion internal integration token |
| `credentials.json` | Google OAuth client for personal Gmail |
| `credentials_school.json` | Google OAuth client for school Gmail (separate GCP OAuth client required) |
| `token_personal.json` | Auto-generated after first personal Gmail auth |
| `token_school.json` | Auto-generated after first school Gmail auth |

All credential and token files are gitignored. On first run, `token.json` (legacy name) is auto-migrated to `token_personal.json`.

**Important:** Both Gmail accounts require separate OAuth Desktop client IDs in Google Cloud Console — reusing the same client for two accounts invalidates the first token.

## Architecture

```
main.py          orchestrates steps; handles CLI flags; calls _fetch_all_accounts() across both
gmail_scraper.py OAuth2 auth per account (separate token files); ACCOUNTS dict maps name → (creds, token)
classifier.py    pure functions: email dict → recruiting/finance/school dict (or None if ambiguous/promo)
notion_writer.py Notion API writes + full deduplication before every insert; archive via pages.update(archived=True)
config.py        all constants: DB IDs, Gmail search queries, stage keywords, target companies
```

Data flow: `main.py` → `gmail_scraper.fetch_emails(query, account=...)` → `classifier.*` → `notion_writer.*`

## Notion database IDs

| Database | ID |
|---|---|
| Recruiting Pipeline | `58e58f54-eb83-43ab-85f4-54b4d76071dd` |
| School Deadlines | `123cdb23-81a2-48e1-8a29-6c86233dd8b6` |
| Finance Tracker | `d5633f55-03a9-47a6-8c7d-18af61c9c689` |
| Health Log | `a3c1a3cc-b9fd-45d6-ab8d-6b05408ca461` |

## Classifier design

Three-tier filter applied in order for every email:
1. **Blocklist** — domain/root in `_RECRUITING_BLOCKLIST`, finance domain, or promo/generic-outreach subject → skip
2. **Signal check** — recruiting requires strong subject keyword or sender in `TARGET_COMPANIES`; school requires 1 strong keyword OR 2+ weak keywords AND an academic subject
3. **Field extraction** — company from domain root (with override map), role from subject-line patterns first then body, stage from `STAGE_KEYWORDS` priority order, dates via regex

To clean up Notion entries (e.g. after a bad run):
```python
from notion_client import Client
from config import NOTION_TOKEN, DB_RECRUITING
notion = Client(auth=NOTION_TOKEN)
resp = notion.databases.query(database_id=DB_RECRUITING)
notion.pages.update(page_id="<page-id>", archived=True)
```

## Git rules

- Never add `Co-Authored-By: Claude` or any AI co-author trailer to commits. Ever.

## Key behaviors to preserve

- Script is idempotent — safe to re-run; dedup queries Notion before every insert.
- `--dry-run` must never call any Notion write endpoint.
- Classifiers return `None` for ambiguous emails rather than creating noisy entries (quality > quantity).
- Recruiting stage inference priority: Offer → Interview → OA → Phone Screen → Applied (default).
- `notion-client` must stay pinned to `==2.2.1` — v3 changed the `databases.query()` API.
