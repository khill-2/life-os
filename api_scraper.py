#!/usr/bin/env python3
"""
Fetches financial data from Teller (banking) and SnapTrade (brokerages)
and generates financial_snapshot_{date}.json in the same schema as csv_scraper.py.

Setup (one-time):
  1. Sign up at https://teller.io — get your Application ID
  2. Download teller_certificate.pem + teller_private_key.pem from teller.io/settings
  3. Sign up at https://snaptrade.com — get Client ID + Consumer Key
  4. Add to .env:
       TELLER_APP_ID=app_xxx
       SNAPTRADE_CLIENT_ID=xxx
       SNAPTRADE_CONSUMER_KEY=xxx
  5. Run: python main.py --api-link   (opens browser, links each bank + brokerage)

After setup:
  python main.py --api               (fetch live data, regenerate dashboard)
"""

import json
import os
import webbrowser
from datetime import date
from http.server import BaseHTTPRequestHandler, HTTPServer

import requests

# ── Credential files (all gitignored) ─────────────────────────────────────────
TELLER_TOKENS_FILE   = "teller_tokens.json"
TELLER_CERT_FILE     = "teller_certificate.pem"
TELLER_KEY_FILE      = "teller_private_key.pem"
SNAPTRADE_CREDS_FILE = "snaptrade_creds.json"

TELLER_BASE  = "https://api.teller.io"
_LINK_PORT   = 8765

# ── Teller → snapshot category map ────────────────────────────────────────────
_TELLER_CATEGORIES: dict[str, str] = {
    "accommodation":      "Travel/Entertainment",
    "bar":                "Restaurants",
    "charity":            "Services",
    "clothing":           "Merchandise",
    "coffee_shop":        "Restaurants",
    "dining":             "Restaurants",
    "education":          "Education",
    "electronics":        "Merchandise",
    "entertainment":      "Travel/Entertainment",
    "fast_food":          "Restaurants",
    "food_and_drink":     "Restaurants",
    "fuel":               "Gasoline",
    "general":            "Other",
    "groceries":          "Supermarkets",
    "health":             "Medical Services",
    "home":               "Home Improvement",
    "income":             "Transfer",
    "insurance":          "Services",
    "investment":         "Transfer",
    "loan":               "Transfer",
    "medical":            "Medical Services",
    "other":              "Other",
    "payment":            "Payments and Credits",
    "rent":               "Services",
    "restaurant":         "Restaurants",
    "service":            "Services",
    "shopping":           "Merchandise",
    "software":           "Services",
    "sport":              "Travel/Entertainment",
    "supermarket":        "Supermarkets",
    "tax":                "Fees",
    "transfer":           "Transfer",
    "transport":          "Travel/Entertainment",
    "travel":             "Travel/Entertainment",
    "utilities":          "Services",
}

# ── Teller Connect HTML (served locally for the link flow) ────────────────────
_CONNECT_HTML = """\
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Life OS — Link Bank Accounts</title>
  <style>
    body {{ font-family: -apple-system, sans-serif; max-width: 480px;
            margin: 60px auto; padding: 0 24px; color: #222; }}
    h2   {{ font-size: 20px; margin-bottom: 8px; }}
    p    {{ color: #555; }}
    button {{ padding: 12px 24px; background: #1a73e8; color: #fff; border: none;
              border-radius: 6px; font-size: 15px; cursor: pointer; margin-top: 8px; }}
    button:hover {{ background: #1557b0; }}
    #status {{ margin-top: 16px; font-size: 14px; }}
    .ok  {{ color: #1a7340; }}
    .err {{ color: #c0392b; }}
  </style>
</head>
<body>
  <h2>Life OS — Link Bank Account</h2>
  <p>Click below to connect a bank account. Repeat for each institution (Capital One, Chase, Discover).</p>
  <button id="btn">Connect Account</button>
  <p id="status"></p>
  <script src="https://cdn.teller.io/connect/connect.js"></script>
  <script>
    const handler = TellerConnect.setup({{
      applicationId: "{app_id}",
      onSuccess: async function(enrollment) {{
        document.getElementById("status").textContent = "Saving…";
        try {{
          const r = await fetch("/token", {{
            method: "POST",
            headers: {{"Content-Type": "application/json"}},
            body: JSON.stringify({{
              token:       enrollment.accessToken,
              institution: enrollment.institution ? enrollment.institution.name : "unknown"
            }})
          }});
          const el = document.getElementById("status");
          el.className = r.ok ? "ok" : "err";
          el.textContent = r.ok
            ? "✓ Linked! Connect another account or close this tab when done."
            : "Save failed — check the terminal.";
        }} catch(e) {{
          document.getElementById("status").className = "err";
          document.getElementById("status").textContent = "Error: " + e.message;
        }}
      }},
      onExit: function() {{
        document.getElementById("status").textContent = "Cancelled.";
      }},
    }});
    document.getElementById("btn").onclick = () => handler.open();
  </script>
</body>
</html>
"""


# ── Teller account linking ─────────────────────────────────────────────────────

def link_teller() -> None:
    """Serve Teller Connect locally and save each enrolled account's access token."""
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    app_id = os.environ.get("TELLER_APP_ID", "").strip()
    if not app_id:
        print("❌  TELLER_APP_ID not set in .env")
        print("    Sign up at https://teller.io → Settings → Application → copy Application ID")
        return

    tokens: list[dict] = []
    if os.path.exists(TELLER_TOKENS_FILE):
        with open(TELLER_TOKENS_FILE) as f:
            tokens = json.load(f)

    html = _CONNECT_HTML.format(app_id=app_id)

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html.encode())

        def do_POST(self):
            if self.path != "/token":
                self.send_response(404)
                self.end_headers()
                return
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length))
            token = body.get("token", "").strip()
            if token and not any(t.get("token") == token for t in tokens):
                institution = body.get("institution", "unknown")
                tokens.append({"token": token, "institution": institution})
                with open(TELLER_TOKENS_FILE, "w") as f:
                    json.dump(tokens, f, indent=2)
                print(f"  ✓ Linked: {institution}")
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")

        def log_message(self, *args):
            pass

    server = HTTPServer(("localhost", _LINK_PORT), _Handler)
    print(f"\nOpening http://localhost:{_LINK_PORT}")
    print("Connect Capital One, Chase, and Discover — one at a time.")
    print("Press Ctrl+C when all accounts are linked.\n")
    webbrowser.open(f"http://localhost:{_LINK_PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    server.server_close()
    print(f"\nSaved {len(tokens)} token(s) → {TELLER_TOKENS_FILE}")


# ── SnapTrade account linking ──────────────────────────────────────────────────

def link_snaptrade() -> None:
    """Register a SnapTrade user (once) and open the brokerage connection portal."""
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    try:
        from snaptrade_client import SnapTrade
    except ImportError:
        print("❌  snaptrade-python-sdk not installed. Run: pip install snaptrade-python-sdk")
        return

    client_id    = os.environ.get("SNAPTRADE_CLIENT_ID",    "").strip()
    consumer_key = os.environ.get("SNAPTRADE_CONSUMER_KEY", "").strip()
    if not client_id or not consumer_key:
        print("❌  SNAPTRADE_CLIENT_ID / SNAPTRADE_CONSUMER_KEY not set in .env")
        print("    Sign up at https://snaptrade.com → Dashboard → API credentials")
        return

    st = SnapTrade(consumer_key=consumer_key, client_id=client_id)

    creds: dict = {}
    if os.path.exists(SNAPTRADE_CREDS_FILE):
        with open(SNAPTRADE_CREDS_FILE) as f:
            creds = json.load(f)

    user_id     = creds.get("user_id")
    user_secret = creds.get("user_secret")

    if not user_id or not user_secret:
        user_id = "lifeos_keller"
        resp = st.authentication.register_snap_trade_user(body={"userId": user_id})
        user_secret = resp.body["userSecret"]
        creds = {"user_id": user_id, "user_secret": user_secret}
        with open(SNAPTRADE_CREDS_FILE, "w") as f:
            json.dump(creds, f, indent=2)
        print(f"  Registered SnapTrade user → {SNAPTRADE_CREDS_FILE}")

    resp = st.authentication.login_snap_trade_user(
        user_id=user_id,
        user_secret=user_secret,
    )
    portal_url = resp.body.get("redirectURI") or resp.body.get("redirect_uri", "")
    if not portal_url:
        print(f"❌  Could not get portal URL. Full response: {resp.body}")
        return

    print("\nOpening SnapTrade portal — connect Schwab and Fidelity.")
    print(f"URL: {portal_url}\n")
    webbrowser.open(portal_url)
    input("Press Enter when done linking brokerage accounts...")
    print(f"Credentials already saved → {SNAPTRADE_CREDS_FILE}")


# ── Teller API fetch ───────────────────────────────────────────────────────────

def _teller_get(path: str, token: str) -> list | dict:
    """Authenticated GET to Teller API using mutual TLS."""
    if not os.path.exists(TELLER_CERT_FILE) or not os.path.exists(TELLER_KEY_FILE):
        raise FileNotFoundError(
            f"Teller certificates missing.\n"
            f"  Download {TELLER_CERT_FILE} and {TELLER_KEY_FILE} from:\n"
            f"  https://teller.io/settings/application"
        )
    resp = requests.get(
        f"{TELLER_BASE}{path}",
        auth=(token, ""),
        cert=(TELLER_CERT_FILE, TELLER_KEY_FILE),
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def _identify_account(acct: dict) -> str | None:
    """Map a Teller account dict to a snapshot key, or None if unrecognised."""
    inst    = acct.get("institution", {}).get("id", "").lower().replace("-", "_")
    subtype = acct.get("subtype", "").lower()
    last4   = acct.get("last_four", "")

    if "capital_one" in inst:
        if last4 == "2657" or subtype == "checking":
            return "capital_one_checking"
        if last4 == "2125" or subtype == "savings":
            return "capital_one_savings"
    if "discover" in inst:
        return "discover_it"
    if "chase" in inst:
        return "chase_sapphire_preferred"
    return None


def _fetch_teller_account(acct: dict, token: str) -> dict:
    """Fetch transactions + balance for one Teller account."""
    acct_id  = acct["id"]
    acct_type = acct.get("type", "")      # "depository" | "credit"
    key       = _identify_account(acct)

    raw_txns = _teller_get(f"/accounts/{acct_id}/transactions", token)

    transactions = []
    for t in raw_txns:
        # Teller sign convention:
        #   depository: negative=withdrawal, positive=deposit
        #   credit:     positive=charge,     negative=payment
        #
        # Snapshot convention matches Teller for Cap One and Discover.
        # Chase CSVs historically used negative=charge, so we negate here
        # to keep the api_scraper output identical to the csv_scraper output.
        amount = float(t.get("amount", 0))
        if key == "chase_sapphire_preferred" and acct_type == "credit":
            amount = -amount

        cat_raw = ((t.get("details") or {}).get("category") or "")
        transactions.append({
            "date":        (t.get("date") or "").strip(),
            "description": (t.get("description") or "").strip(),
            "category":    _TELLER_CATEGORIES.get(cat_raw.lower(), cat_raw.title() or "Other"),
            "amount":      round(amount, 2),
        })

    transactions.sort(key=lambda x: x["date"], reverse=True)

    result: dict = {"transactions": transactions}

    try:
        bal = _teller_get(f"/accounts/{acct_id}/balances", token)
        ledger = float(bal.get("ledger") or 0)
        if acct_type == "depository":
            result["balance"] = round(ledger, 2)
        else:
            result["current_balance"] = round(ledger, 2)
    except Exception:
        pass

    return result


def fetch_all_teller() -> dict[str, dict]:
    """Pull all recognised accounts from every saved Teller token."""
    if not os.path.exists(TELLER_TOKENS_FILE):
        print("  No Teller tokens found. Run: python main.py --api-link")
        return {}

    with open(TELLER_TOKENS_FILE) as f:
        token_entries = json.load(f)

    results: dict[str, dict] = {}

    for entry in token_entries:
        token       = entry["token"] if isinstance(entry, dict) else entry
        institution = entry.get("institution", "?") if isinstance(entry, dict) else "?"
        try:
            accounts = _teller_get("/accounts", token)
            for acct in accounts:
                key = _identify_account(acct)
                if not key or key in results:
                    continue
                label = key.replace("_", " ").title()
                print(f"  ✓ {label} ← Teller ({institution})")
                results[key] = _fetch_teller_account(acct, token)
        except Exception as e:
            print(f"  ⚠  Teller error for {institution}: {e}")

    return results


# ── SnapTrade fetch ────────────────────────────────────────────────────────────

def fetch_snaptrade_positions() -> dict[str, dict]:
    """Fetch brokerage positions from SnapTrade for Schwab and Fidelity."""
    if not os.path.exists(SNAPTRADE_CREDS_FILE):
        print("  No SnapTrade credentials found. Run: python main.py --api-link")
        return {}

    try:
        from dotenv import load_dotenv
        load_dotenv()
        from snaptrade_client import SnapTrade
    except ImportError:
        print("  ⚠  snaptrade-python-sdk not installed. Run: pip install snaptrade-python-sdk")
        return {}

    with open(SNAPTRADE_CREDS_FILE) as f:
        creds = json.load(f)

    client_id    = os.environ.get("SNAPTRADE_CLIENT_ID",    "").strip()
    consumer_key = os.environ.get("SNAPTRADE_CONSUMER_KEY", "").strip()
    if not client_id or not consumer_key:
        print("  ⚠  SNAPTRADE_CLIENT_ID / SNAPTRADE_CONSUMER_KEY missing from .env")
        return {}

    st = SnapTrade(consumer_key=consumer_key, client_id=client_id)

    try:
        resp = st.account_information.get_all_user_holdings(
            user_id=creds["user_id"],
            user_secret=creds["user_secret"],
        )
    except Exception as e:
        print(f"  ⚠  SnapTrade error: {e}")
        return {}

    results: dict[str, dict] = {}

    for holding in (resp.body or []):
        acct      = holding.get("account", {}) if isinstance(holding, dict) else {}
        inst_name = (
            acct.get("institution_name") or acct.get("name") or ""
        ).lower()

        if "schwab" in inst_name:
            snap_key = "schwab_brokerage"
        elif "fidelity" in inst_name:
            snap_key = "fidelity_roth_ira"
        else:
            continue

        positions_raw = holding.get("positions", []) if isinstance(holding, dict) else []
        positions: list[dict] = []
        total_value = total_cost = total_gain = 0.0

        for pos in positions_raw:
            sym_obj = ((pos.get("symbol") or {}).get("symbol") or {}) if isinstance(pos, dict) else {}
            ticker  = (sym_obj.get("ticker") or "").strip()
            name    = (sym_obj.get("description") or "").strip()
            if not ticker:
                continue

            units    = float(pos.get("units") or 0)
            price    = float(pos.get("price") or 0)
            avg_cost = float(pos.get("average_purchase_price") or 0)
            mv       = round(units * price, 2)
            cost     = round(units * avg_cost, 2)
            gain     = round(mv - cost, 2)
            gain_pct = round((gain / cost * 100) if cost else 0, 2)

            if mv <= 0:
                continue

            total_value += mv
            total_cost  += cost
            total_gain  += gain

            positions.append({
                "symbol":        ticker,
                "name":          name,
                "quantity":      round(units, 4),
                "price":         round(price, 2),
                "market_value":  mv,
                "cost_basis":    cost,
                "gain_loss":     gain,
                "gain_loss_pct": gain_pct,
                "type":          "",
            })

        total_value = round(total_value, 2)
        total_cost  = round(total_cost, 2)
        total_gain  = round(total_gain, 2)

        results[snap_key] = {
            "positions":           sorted(positions, key=lambda x: -x["market_value"]),
            "total_value":         total_value,
            "total_cost_basis":    total_cost,
            "total_gain_loss":     total_gain,
            "total_gain_loss_pct": round((total_gain / total_cost * 100) if total_cost else 0, 2),
            "value_date":          str(date.today()),
        }
        acct_label = acct.get("name", inst_name)
        print(f"  ✓ {snap_key.replace('_', ' ').title()} ← SnapTrade ({acct_label})")

    return results


# ── Snapshot assembly ──────────────────────────────────────────────────────────

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
    """
    Fetch from Teller + SnapTrade and build a snapshot.
    Missing accounts fall back to existing data, same as csv_scraper.generate_snapshot.
    """
    existing          = existing_snap or {}
    existing_accounts = existing.get("accounts", {})

    print("Fetching from Teller (banking)...")
    banking   = fetch_all_teller()

    print("Fetching from SnapTrade (brokerages)...")
    brokerage = fetch_snaptrade_positions()

    fresh = {**banking, **brokerage}

    _known = {
        "capital_one_checking", "capital_one_savings", "discover_it",
        "chase_sapphire_preferred", "schwab_brokerage", "fidelity_roth_ira",
    }

    accounts: dict[str, dict] = {}
    for key in _known:
        if key in fresh:
            merged = dict(existing_accounts.get(key, {}))
            merged.update(fresh[key])
            accounts[key] = merged
        else:
            label = key.replace("_", " ").title()
            print(f"  – {label}: not fetched, keeping existing data")
            accounts[key] = existing_accounts.get(key, {})

    # Preserve accounts not covered by API (e.g. apple_card)
    for key, val in existing_accounts.items():
        if key not in accounts:
            accounts[key] = val

    existing_nw  = existing.get("net_worth_summary", {})
    checking_bal = accounts.get("capital_one_checking", {}).get("balance")
    savings_bal  = accounts.get("capital_one_savings",  {}).get("balance")
    if checking_bal is not None or savings_bal is not None:
        liquid_cash = round((checking_bal or 0) + (savings_bal or 0), 2)
    else:
        liquid_cash = existing_nw.get("liquid_cash", 0)

    cc_liab      = existing_nw.get("total_liabilities", 0)
    schwab_val   = accounts["schwab_brokerage"].get("total_value")  or existing_nw.get("taxable_investments", 0)
    fidelity_val = accounts["fidelity_roth_ira"].get("total_value") or existing_nw.get("tax_advantaged_investments", 0)

    income = _infer_income(accounts.get("capital_one_savings", {}).get("transactions", []))
    if not income["deposits"]:
        income = existing.get("income_summary", income)

    existing_ig = existing.get("investment_goals", {})
    if "roth_ira" not in existing_ig and "brokerage" not in existing_ig:
        existing_ig = {
            "roth_ira":  {"limit": 7000, "contributed": existing_ig.get("roth_ira_2026_contributed", 0)},
            "brokerage": {"monthly_target": existing_ig.get("monthly_brokerage_target", 3000), "invested_ytd": 0},
        }

    chase_acct      = accounts.get("chase_sapphire_preferred", {})
    chase_bonus_src = chase_acct.get("signup_bonus")
    if chase_bonus_src:
        # negative = charge (Chase convention maintained from CSV parser)
        chase_spend = round(sum(
            abs(t["amount"]) for t in chase_acct.get("transactions", [])
            if t.get("amount", 0) < 0
        ), 2)
        existing_ig["chase_bonus"] = {**chase_bonus_src, "current_spend": chase_spend}

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
