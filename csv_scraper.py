#!/usr/bin/env python3
"""
Parses bank CSV exports from csv_imports/ and generates a financial snapshot.

Place exports in csv_imports/ with these exact filenames:
  capital_one_checking.csv   — Capital One 360 Checking transactions
  capital_one_savings.csv    — Capital One 360 Performance Savings transactions
  discover.csv               — Discover It transactions
  chase.csv                  — Chase Sapphire transactions
  schwab_positions.csv       — Schwab brokerage positions
  fidelity_positions.csv     — Fidelity Roth IRA positions

Missing files are skipped and existing snapshot data is preserved for that account.
"""

import csv
import glob
import json
import os
import shutil
import time
import webbrowser
from datetime import date, datetime

CSV_DIR = "csv_imports"

BANK_URLS = {
    "capital_one": ("Capital One",  "https://myaccounts.capitalone.com/"),
    "discover":    ("Discover",     "https://www.discover.com/"),
    "chase":       ("Chase",        "https://secure.chase.com/web/auth/dashboard#/dashboard/overview"),
    "schwab":      ("Schwab",       "https://client.schwab.com/app/accounts/positions"),
    "fidelity":    ("Fidelity",     "https://digital.fidelity.com/ftgw/digital/portfolio/positions"),
}

# Column-first detection. Each entry: (snapshot_key, [required column substrings], [filename hints])
# Matched in order — first full column match wins; partial + filename is fallback.
# Column substrings are checked case-insensitively against the header row.
_DETECTORS = [
    # Capital One actual columns: Account Number, Transaction Description, Transaction Date,
    #   Transaction Type, Transaction Amount, Balance
    ("capital_one_checking", ["Transaction Amount", "Transaction Type", "Account Number"], ["360checking", "checking", "2657"]),
    ("capital_one_savings",  ["Transaction Amount", "Transaction Type", "Account Number"], ["360savings", "savings", "performance", "2125"]),
    # Discover actual columns: Trans. Date, Post Date, Description, Amount, Category
    ("discover_it",          ["Trans. Date", "Amount", "Category"],   ["discover"]),
    # Chase actual columns: Transaction Date, Post Date, Description, Category, Type, Amount, Memo
    # "Post Date" is unique to Chase (Cap One doesn't have it)
    ("chase_sapphire_preferred", ["Post Date", "Amount", "Description"], ["chase"]),
    # Fidelity actual columns: Account Number, Account Name, Symbol, Description, Quantity,
    #   Last Price, Current Value, Cost Basis Total, ...
    ("fidelity_roth_ira",    ["Current Value", "Cost Basis Total"],   ["fidelity", "portfolio_position"]),
    # Schwab actual columns: Symbol, Description, Qty (Quantity), Price, Mkt Val (Market Value),
    #   Cost Basis, Gain $ (Gain/Loss $), ...
    # "Mkt Val" appears as substring of "Mkt Val (Market Value)"
    ("schwab_brokerage",     ["Mkt Val", "Cost Basis", "Symbol"],     ["schwab", "custodial", "all-position"]),
]

DOWNLOADS_DIR = os.path.expanduser("~/Downloads")
STALE_HOURS   = 48


# ── Detection helpers ─────────────────────────────────────────────────────────

def _best_header_line(path: str) -> str:
    """
    Read the first few lines of a CSV and return the one most likely to be the
    column header row — i.e. the first line with 5+ short comma-separated fields.
    Handles Schwab's title row, Fidelity's BOM, etc.
    """
    try:
        with open(path, newline="", encoding="utf-8-sig") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                fields = [x.strip().strip('"') for x in line.split(",")]
                # A header row: many fields, each reasonably short, mostly alpha
                if len(fields) >= 5 and all(len(f) < 60 for f in fields if f):
                    return line
    except Exception:
        pass
    return ""


def _detect_bank(path: str) -> str | None:
    """Return the snapshot key for a CSV file, or None if unrecognised."""
    filename = os.path.basename(path).lower()
    headers  = _best_header_line(path)

    for key, col_hints, name_hints in _DETECTORS:
        col_match  = sum(1 for c in col_hints if c.lower() in headers.lower())
        name_match = any(h in filename for h in name_hints)
        if col_match == len(col_hints):        # all required columns present → definitive match
            return key
        if col_match >= 2 and name_match:      # partial columns + filename hint
            return key
    return None


def _cap_one_account_type(path: str) -> str:
    """Distinguish Capital One checking vs savings by Account Number in the data."""
    filename = os.path.basename(path).lower()
    # Filename hint first
    if "saving" in filename or "performance" in filename or "2125" in filename:
        return "capital_one_savings"
    if "checking" in filename or "2657" in filename:
        return "capital_one_checking"
    # Peek at first data row Account Number
    try:
        with open(path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            row = next(reader, {})
            acct = str(row.get("Account Number", "") or "").strip()
            if acct.endswith("2125") or "saving" in acct.lower():
                return "capital_one_savings"
    except Exception:
        pass
    return "capital_one_checking"


# ── Downloads ingestion ───────────────────────────────────────────────────────

def pull_from_downloads() -> dict[str, str]:
    """
    Scan ~/Downloads for CSVs downloaded in the last 48 hours.
    Detect which bank each belongs to, copy to csv_imports/, and return
    {snapshot_key: destination_path} for every file pulled.
    """
    os.makedirs(CSV_DIR, exist_ok=True)
    cutoff  = time.time() - STALE_HOURS * 3600
    found   = {}
    skipped = []

    candidates = sorted(
        glob.glob(os.path.join(DOWNLOADS_DIR, "*.csv")),
        key=os.path.getmtime,
        reverse=True,  # most recent first
    )

    _dest_names = {
        "capital_one_checking":     "capital_one_checking.csv",
        "capital_one_savings":      "capital_one_savings.csv",
        "discover_it":              "discover.csv",
        "chase_sapphire_preferred": "chase.csv",
        "schwab_brokerage":         "schwab_positions.csv",
        "fidelity_roth_ira":        "fidelity_positions.csv",
    }

    for src in candidates:
        if os.path.getmtime(src) < cutoff:
            continue

        key = _detect_bank(src)
        if not key:
            skipped.append(os.path.basename(src))
            continue

        if key in ("capital_one_checking", "capital_one_savings"):
            key = _cap_one_account_type(src)

        if key not in found:
            dest = os.path.join(CSV_DIR, _dest_names[key])
            shutil.copy2(src, dest)
            found[key] = dest
            print(f"  ✓ {key.replace('_', ' ').title()} ← {os.path.basename(src)}")

    if skipped:
        print(f"  – Skipped (unrecognised): {', '.join(skipped)}")
    if not found:
        print("  No recent bank CSVs found in ~/Downloads.")

    return found


def open_bank_sites() -> None:
    """Open each bank's transaction/positions page in the browser."""
    print("Opening bank sites — download the CSVs, then run: python main.py --csv\n")
    for key, (label, url) in BANK_URLS.items():
        print(f"  → {label}")
        webbrowser.open(url)
    print("\nThe script will auto-detect the downloaded files from ~/Downloads.")


# ── Category normalisation ────────────────────────────────────────────────────

CATEGORY_MAP = {
    "Dining":                 "Restaurants",
    "Groceries":              "Supermarkets",
    "Gas":                    "Gasoline",
    "Gas/Automotive":         "Gasoline",
    "Gasoline":               "Gasoline",
    "Travel":                 "Travel/Entertainment",
    "Travel/ Entertainment":  "Travel/Entertainment",
    "Entertainment":          "Travel/Entertainment",
    "Health/Medical":         "Medical Services",
    "Medical Services":       "Medical Services",
    "Shopping":               "Merchandise",
    "Merchandise":            "Merchandise",
    "Food & Drink":           "Restaurants",
    "Restaurants":            "Restaurants",
    "Supermarkets":           "Supermarkets",
    "Automotive":             "Automotive",
    "Home Improvement":       "Home Improvement",
    "Education":              "Education",
    "Services":               "Services",
    "Payments and Credits":   "Payments and Credits",
    "Fees":                   "Fees",
    "Transfer":               "Transfer",
    "Credit":                 "Transfer",
    "Debit":                  "Transfer",
}


def _norm_date(s: str) -> str:
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(s.strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return s.strip()


def _norm_cat(raw: str) -> str:
    return CATEGORY_MAP.get(raw.strip(), raw.strip())


def _find(pattern: str) -> str | None:
    matches = glob.glob(os.path.join(CSV_DIR, pattern))
    return matches[0] if matches else None


def _money(s: str) -> float:
    cleaned = (s or "0").replace("$", "").replace(",", "").replace("+", "").strip()
    try:
        return float(cleaned or 0)
    except ValueError:
        return 0.0


def _ci(row: dict, *keys: str) -> str:
    """Case-insensitive dict lookup across multiple key candidates."""
    row_lower = {k.lower(): v for k, v in row.items() if k is not None}
    for k in keys:
        v = row_lower.get(k.lower())
        if v is not None:
            return v
    return ""


# ── Bank parsers ──────────────────────────────────────────────────────────────

def parse_capital_one(pattern: str) -> dict:
    """
    Capital One CSV (checking + savings):
      Account Number, Transaction Description, Transaction Date,
      Transaction Type, Transaction Amount, Balance

    Transaction Type = "Credit" (money in, positive) or "Debit" (money out, negative).
    Snapshot convention: positive = inflow, negative = outflow.
    """
    path = _find(pattern)
    if not path:
        return {}

    transactions = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                raw    = _money(row.get("Transaction Amount") or "")
                tx_type = (row.get("Transaction Type") or "").strip().lower()
                amount  = raw if tx_type == "credit" else -raw
                transactions.append({
                    "date":        _norm_date(row.get("Transaction Date", "")),
                    "description": (row.get("Transaction Description") or "").strip(),
                    "category":    _norm_cat(row.get("Category") or tx_type.title()),
                    "amount":      round(amount, 2),
                })
            except (ValueError, KeyError):
                continue

    transactions.sort(key=lambda x: x["date"], reverse=True)
    # Most recent row has the current balance
    balance = None
    path2 = _find(pattern)
    if path2:
        try:
            with open(path2, newline="", encoding="utf-8-sig") as f:
                row0 = next(csv.DictReader(f), {})
                bal = _money(row0.get("Balance") or "")
                if bal:
                    balance = bal
        except Exception:
            pass
    result = {"transactions": transactions}
    if balance is not None:
        result["balance"] = balance
    return result


def parse_discover() -> dict:
    """
    Discover CSV:
      Trans. Date, Post Date, Description, Amount, Category

    Amount: positive = charge, negative = credit (matches snapshot convention).
    """
    path = _find("discover*.csv")
    if not path:
        return {}

    transactions = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                transactions.append({
                    "date":        _norm_date(row.get("Trans. Date", "")),
                    "description": (row.get("Description") or "").strip(),
                    "category":    _norm_cat(row.get("Category") or ""),
                    "amount":      round(_money(row.get("Amount") or ""), 2),
                })
            except (ValueError, KeyError):
                continue

    transactions.sort(key=lambda x: x["date"], reverse=True)
    return {"transactions": transactions}


def parse_chase() -> dict:
    """
    Chase CSV:
      Transaction Date, Post Date, Description, Category, Type, Amount, Memo

    Amount: negative = charge (matches snapshot convention).
    """
    path = _find("chase*.csv")
    if not path:
        return {}

    transactions = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                transactions.append({
                    "date":        _norm_date(row.get("Transaction Date", "")),
                    "description": (row.get("Description") or "").strip(),
                    "category":    _norm_cat(row.get("Category") or ""),
                    "amount":      round(_money(row.get("Amount") or ""), 2),
                })
            except (ValueError, KeyError):
                continue

    transactions.sort(key=lambda x: x["date"], reverse=True)
    return {"transactions": transactions}


def parse_schwab_positions() -> dict:
    """
    Schwab positions CSV.
    First line is a title row; second line is column headers.
    Actual column names: Symbol, Description, Qty (Quantity), Price,
      Mkt Val (Market Value), Cost Basis, Gain $ (Gain/Loss $), Asset Type
    """
    path = _find("schwab_positions*.csv")
    if not path:
        return {}

    with open(path, newline="", encoding="utf-8-sig") as f:
        raw_lines = f.read().splitlines()

    # Find the header row: first line with 5+ short fields containing "Symbol"
    start = 0
    for i, line in enumerate(raw_lines):
        fields = [x.strip().strip('"') for x in line.split(",")]
        if len(fields) >= 5 and any("symbol" in x.lower() for x in fields):
            start = i
            break

    reader = csv.DictReader(raw_lines[start:])

    positions = []
    total_value = total_cost = total_gain = 0.0
    cash = 0.0

    for row in reader:
        symbol = (row.get("Symbol") or "").strip().strip('"')
        skip = {"--", "Account Total", "Positions Total", ""}
        if not symbol or symbol in skip:
            continue

        mv_raw = row.get("Mkt Val (Market Value)") or row.get("Market Value") or row.get("Mkt Val") or ""
        mv = _money(mv_raw)

        # Cash row: track separately so it contributes to total_value but not positions
        if symbol == "Cash & Cash Investments":
            cash = mv
            total_value += mv
            continue

        if not any(c.isalpha() for c in symbol):
            continue

        # Schwab column names contain full names in parens: "Mkt Val (Market Value)"
        cost = _money(row.get("Cost Basis") or "")
        qty  = _money(row.get("Qty (Quantity)") or row.get("Quantity") or row.get("Qty") or "0")
        price = _money(row.get("Price") or "")
        gain  = round(mv - cost, 2)
        gain_pct = round((gain / cost * 100) if cost else 0, 2)

        if mv == 0:
            continue

        total_value += mv
        total_cost  += cost
        total_gain  += gain

        positions.append({
            "symbol":        symbol,
            "name":          (row.get("Description") or "").strip().strip('"'),
            "quantity":      round(qty, 4),
            "price":         round(price, 2),
            "market_value":  round(mv, 2),
            "cost_basis":    round(cost, 2),
            "gain_loss":     gain,
            "gain_loss_pct": gain_pct,
            "type":          (row.get("Asset Type") or row.get("Security Type") or "").strip(),
        })

    return {
        "positions":           sorted(positions, key=lambda x: -x["market_value"]),
        "cash":                round(cash, 2),
        "total_value":         round(total_value, 2),
        "total_cost_basis":    round(total_cost, 2),
        "total_gain_loss":     round(total_gain, 2),
        "total_gain_loss_pct": round((total_gain / total_cost * 100) if total_cost else 0, 2),
    }


def parse_fidelity_positions() -> dict:
    """
    Fidelity positions CSV.
    Columns: Account Number, Account Name, Symbol, Description, Quantity,
      Last Price, Current Value, Cost Basis Total, ...
    """
    path = _find("fidelity_positions*.csv")
    if not path:
        return {}

    with open(path, newline="", encoding="utf-8-sig") as f:
        raw_lines = f.read().splitlines()

    # Extract download date from footer line like "Date downloaded Jul-22-2026 ..."
    import re as _re
    value_date = str(date.today())
    for line in raw_lines:
        m = _re.search(r"Date downloaded\s+(\w+-\d+-\d+)", line)
        if m:
            try:
                value_date = str(datetime.strptime(m.group(1), "%b-%d-%Y").date())
            except ValueError:
                pass
            break

    start = next((i for i, l in enumerate(raw_lines) if "Symbol" in l and "Account" in l), 0)
    reader = csv.DictReader(raw_lines[start:])

    positions = []
    total_value = total_cost = total_gain = 0.0

    for row in reader:
        symbol = (row.get("Symbol") or "").strip()
        if not symbol or symbol in ("--", "", "Pending Activity"):
            continue
        if not any(c.isalpha() for c in symbol):
            continue

        mv    = _money(_ci(row, "Current Value", "Market Value"))
        cost  = _money(_ci(row, "Cost Basis Total", "Cost Basis"))
        qty   = _money(_ci(row, "Quantity") or "0")
        price = _money(_ci(row, "Last Price"))
        gain  = round(mv - cost, 2)
        gain_pct = round((gain / cost * 100) if cost else 0, 2)

        if mv == 0:
            continue

        total_value += mv
        total_cost  += cost
        total_gain  += gain

        positions.append({
            "symbol":        symbol,
            "name":          (row.get("Description") or "").strip(),
            "quantity":      round(qty, 4),
            "price":         round(price, 2),
            "market_value":  round(mv, 2),
            "cost_basis":    round(cost, 2),
            "gain_loss":     gain,
            "gain_loss_pct": gain_pct,
            "type":          (row.get("Type") or "").strip(),
        })

    return {
        "positions":           sorted(positions, key=lambda x: -x["market_value"]),
        "total_value":         round(total_value, 2),
        "total_cost_basis":    round(total_cost, 2),
        "total_gain_loss":     round(total_gain, 2),
        "total_gain_loss_pct": round((total_gain / total_cost * 100) if total_cost else 0, 2),
        "value_date":          value_date,
    }


# ── Snapshot assembly ─────────────────────────────────────────────────────────

def _infer_income(savings_txns: list) -> dict:
    deposits = []
    for tx in savings_txns:
        desc = tx["description"].upper()
        if tx["amount"] > 0 and any(k in desc for k in ("RIVIAN", "VW", "PAYROLL", "DIRECT DEP", "GUSTO", "ADP")):
            deposits.append({"date": tx["date"], "net_amount": tx["amount"]})
    deposits.sort(key=lambda x: x["date"], reverse=True)
    avg = round(sum(d["net_amount"] for d in deposits[:8]) / min(len(deposits), 8), 2) if deposits else 0
    ytd = round(sum(d["net_amount"] for d in deposits), 2)
    return {
        "source":           "Auto-detected from savings deposits",
        "deposits":         deposits[:10],
        "ytd_net_income":   ytd,
        "avg_biweekly_net": avg,
    }


def generate_snapshot(existing_snap: dict | None = None) -> dict:
    """Parse all CSVs and build a snapshot. Missing files keep existing account data."""
    existing          = existing_snap or {}
    existing_accounts = existing.get("accounts", {})

    print("Scanning ~/Downloads for recent bank exports...")
    pulled = pull_from_downloads()
    if not pulled:
        print("  (using files already in csv_imports/)")

    parsers = {
        "capital_one_checking":     lambda: parse_capital_one("capital_one_checking*.csv"),
        "capital_one_savings":      lambda: parse_capital_one("capital_one_savings*.csv"),
        "discover_it":              parse_discover,
        "chase_sapphire_preferred": parse_chase,
        "schwab_brokerage":         parse_schwab_positions,
        "fidelity_roth_ira":        parse_fidelity_positions,
    }

    accounts = {}
    found = 0
    for key, parser in parsers.items():
        label    = key.replace("_", " ").title()
        new_data = parser()
        if new_data:
            if key not in pulled:
                print(f"  ✓ {label}")
            merged = dict(existing_accounts.get(key, {}))
            merged.update(new_data)
            accounts[key] = merged
            found += 1
        else:
            if key not in pulled:
                print(f"  – {label}: no CSV found, keeping existing data")
            accounts[key] = existing_accounts.get(key, {})

    if "apple_card" in existing_accounts:
        accounts["apple_card"] = existing_accounts["apple_card"]

    if found == 0:
        raise RuntimeError(f"No CSVs found in {CSV_DIR}/. Download exports and re-run.")

    existing_nw  = existing.get("net_worth_summary", {})
    # Compute liquid cash from fresh CSV balances if available
    checking_bal = accounts.get("capital_one_checking", {}).get("balance")
    savings_bal  = accounts.get("capital_one_savings",  {}).get("balance")
    if checking_bal is not None and savings_bal is not None:
        liquid_cash = round(checking_bal + savings_bal, 2)
    elif checking_bal is not None or savings_bal is not None:
        liquid_cash = round((checking_bal or 0) + (savings_bal or 0), 2)
    else:
        liquid_cash = existing_nw.get("liquid_cash", 0)
    cc_liab      = existing_nw.get("total_liabilities", 0)
    # Use `or` so a zero parsed value falls back to existing snapshot rather than wiping net worth
    schwab_val   = accounts["schwab_brokerage"].get("total_value")  or existing_nw.get("taxable_investments", 0)
    fidelity_val = accounts["fidelity_roth_ira"].get("total_value") or existing_nw.get("tax_advantaged_investments", 0)

    income = _infer_income(accounts.get("capital_one_savings", {}).get("transactions", []))
    if not income["deposits"]:
        income = existing.get("income_summary", income)

    # ── Investment goals (migrate flat → nested if needed) ────────────────────
    existing_ig = existing.get("investment_goals", {})
    # Migrate legacy flat keys if nested keys not yet present
    if "roth_ira" not in existing_ig and "brokerage" not in existing_ig:
        existing_ig = {
            "roth_ira":  {"limit": 7000, "contributed": existing_ig.get("roth_ira_2026_contributed", 0)},
            "brokerage": {"monthly_target": existing_ig.get("monthly_brokerage_target", 3000), "invested_ytd": 0},
        }

    # Auto-calculate brokerage YTD from Schwab buy transactions
    schwab_buys_ytd = sum(
        abs(t["amount"]) for t in accounts.get("schwab_brokerage", {}).get("transactions_ytd", [])
        if t.get("action", "").lower() == "buy"
    )
    if schwab_buys_ytd > 0:
        existing_ig.setdefault("brokerage", {})["invested_ytd"] = round(schwab_buys_ytd, 2)

    # Auto-populate Chase signup bonus current_spend by summing all purchase transactions
    chase_acct = accounts.get("chase_sapphire_preferred", {})
    chase_bonus_src = chase_acct.get("signup_bonus")
    if chase_bonus_src:
        chase_spend = round(sum(
            abs(t["amount"]) for t in chase_acct.get("transactions", [])
            if t.get("amount", 0) < 0  # negative = purchase
        ), 2)
        existing_ig["chase_bonus"] = {
            **chase_bonus_src,
            "current_spend": chase_spend,
        }

    return {
        "snapshot_date": str(date.today()),
        "owner":         "Keller C. Hill",
        "net_worth_summary": {
            "total_assets":               round(liquid_cash + schwab_val + fidelity_val, 2),
            "total_liabilities":          round(cc_liab, 2),
            "true_net_worth":             round(liquid_cash + schwab_val + fidelity_val - cc_liab, 2),
            "liquid_cash":                round(liquid_cash, 2),
            "taxable_investments":        round(schwab_val, 2),
            "tax_advantaged_investments": round(fidelity_val, 2),
        },
        "accounts":           accounts,
        "income_summary":     income,
        "investment_goals":   existing_ig,
        "recurring_expenses": existing.get("recurring_expenses", {}),
    }


def save_snapshot(snap: dict) -> str:
    filename = f"financial_snapshot_{snap['snapshot_date']}.json"
    with open(filename, "w") as f:
        json.dump(snap, f, indent=2)
    return filename
