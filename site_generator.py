#!/usr/bin/env python3
"""
Generates index.html — the full KCH OS site (Finance, Recruiting, School, Health).
Reads from data/*.json and financial_snapshot_*.json.

Usage:
    python site_generator.py           # generate index.html
    python site_generator.py --finance # terminal finance view only
"""

import glob
import json
import os
import sys
from collections import defaultdict
from datetime import date, datetime

DATA_DIR = "data"

# ── Category config (finance) ────────────────────────────────────────────────

CATEGORY_MAP = {
    "Restaurants":          "Food & Dining",
    "Supermarkets":         "Food & Dining",
    "Food & Drink":         "Food & Dining",
    "Gasoline":             "Transportation",
    "Travel/Entertainment": "Entertainment",
    "Education":            "Entertainment",
    "Automotive":           "Auto",
    "Medical Services":     "Health",
    "Merchandise":          "Shopping",
    "Home Improvement":     "Shopping",
    "Services":             "Other",
}

CATEGORY_COLORS = {
    "Food & Dining":  "#ffffff",
    "Housing":        "#d4d4d4",
    "Transportation": "#a3a3a3",
    "Entertainment":  "#8a8a8a",
    "Auto":           "#737373",
    "Health":         "#606060",
    "Shopping":       "#525252",
    "Workspace":      "#404040",
    "Insurance":      "#333333",
    "Investments":    "#e5e5e5",
    "Fees":           "#1f1f1f",
    "Trading":        "#b0b0b0",
    "Other":          "#2a2a2a",
}

STAGE_COLORS = {
    "Applied":      "#666666",
    "Phone Screen": "#999999",
    "OA":           "#bbbbbb",
    "Interview":    "#dddddd",
    "Offer":        "#ffffff",
    "Closed":       "#333333",
    "Applying":     "#888888",
}

# ── Loaders ──────────────────────────────────────────────────────────────────

def _load_json(filename: str) -> list:
    path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return json.load(f).get("entries", [])


def _load_snapshot() -> dict | None:
    files = sorted(glob.glob("financial_snapshot_*.json"))
    if not files:
        return None
    with open(files[-1]) as f:
        return json.load(f)

# ── Finance computation ──────────────────────────────────────────────────────

def _compute_monthly_spending(snap: dict) -> dict:
    monthly: dict = defaultdict(lambda: defaultdict(float))

    for tx in snap["accounts"]["discover_it"]["transactions"]:
        if tx["category"] in ("Payments and Credits", "Fees"):
            continue
        if tx["amount"] <= 0:
            continue
        cat = CATEGORY_MAP.get(tx["category"], tx["category"])
        monthly[tx["date"][:7]][cat] += tx["amount"]

    for tx in snap["accounts"]["chase_sapphire_preferred"]["transactions"]:
        if tx["amount"] >= 0:
            continue
        cat = CATEGORY_MAP.get(tx["category"], tx["category"])
        monthly[tx["date"][:7]][cat] += abs(tx["amount"])

    for tx in snap["accounts"]["capital_one_savings"]["transactions"]:
        if "OHANA" in tx["description"]:
            monthly[tx["date"][:7]]["Housing"] += abs(tx["amount"])

    for tx in snap["accounts"]["capital_one_checking"]["transactions"]:
        desc = tx["description"].upper()
        amt  = tx["amount"]
        if "EMBARC" in desc:
            monthly[tx["date"][:7]]["Workspace"] += abs(amt)
        elif "USAA" in desc and amt < 0:
            monthly[tx["date"][:7]]["Insurance"] += abs(amt)
        elif "KALSHI" in desc and amt < 0:
            monthly[tx["date"][:7]]["Trading"] += abs(amt)

    return {
        m: {k: round(v, 2) for k, v in sorted(cats.items(), key=lambda x: -x[1])}
        for m, cats in sorted(monthly.items())
    }


def _compute_portfolio(snap: dict) -> dict:
    positions = []
    for p in snap["accounts"]["schwab_brokerage"]["positions"]:
        positions.append({
            "symbol":   p["symbol"],
            "value":    p["market_value"],
            "gain":     p["gain_loss"],
            "gain_pct": p["gain_loss_pct"],
            "account":  "Schwab",
        })
    for p in snap["accounts"]["fidelity_roth_ira"]["positions"]:
        if p.get("symbol") == "SPAXX":
            continue
        positions.append({
            "symbol":   p["symbol"],
            "value":    p["market_value"],
            "gain":     p.get("gain_loss", 0),
            "gain_pct": p.get("gain_loss_pct", 0),
            "account":  "Fidelity Roth",
        })
    schwab   = snap["accounts"]["schwab_brokerage"]
    fidelity = snap["accounts"]["fidelity_roth_ira"]
    return {
        "total":      schwab["total_value"] + fidelity["total_value"],
        "total_gain": schwab["total_gain_loss"] + fidelity["total_gain_loss"],
        "positions":  sorted(positions, key=lambda x: -x["value"]),
    }

# ── Health computation ────────────────────────────────────────────────────────

def _compute_health_stats(entries: list) -> dict:
    if not entries:
        return {"streak_workout": 0, "streak_ate_well": 0, "pct_workout_30": 0, "pct_ate_well_30": 0}

    sorted_entries = sorted(entries, key=lambda e: e["date"], reverse=True)

    def streak(field: str) -> int:
        count = 0
        today = date.today()
        for e in sorted_entries:
            d = date.fromisoformat(e["date"])
            delta = (today - d).days
            if delta != count:
                break
            if e.get(field):
                count += 1
            else:
                break
        return count

    recent_30 = sorted_entries[:30]
    pct_w  = round(sum(1 for e in recent_30 if e.get("worked_out")) / len(recent_30) * 100) if recent_30 else 0
    pct_aw = round(sum(1 for e in recent_30 if e.get("ate_well"))   / len(recent_30) * 100) if recent_30 else 0

    return {
        "streak_workout":  streak("worked_out"),
        "streak_ate_well": streak("ate_well"),
        "pct_workout_30":  pct_w,
        "pct_ate_well_30": pct_aw,
    }

# ── Recruiting computation ────────────────────────────────────────────────────

def _compute_recruiting_stats(entries: list) -> dict:
    stage_order = ["Applying", "Applied", "Phone Screen", "OA", "Interview", "Offer", "Closed"]
    counts = defaultdict(int)
    for e in entries:
        counts[e.get("stage", "Applied")] += 1
    return {
        "by_stage": {s: counts.get(s, 0) for s in stage_order},
        "active":   sum(counts[s] for s in stage_order if s not in ("Closed",)),
    }

# ── Site data assembly ────────────────────────────────────────────────────────

def build_site_data() -> dict:
    snap        = _load_snapshot()
    recruiting  = _load_json("recruiting.json")
    school      = _load_json("school.json")
    health      = _load_json("health.json")

    updated = date.today().isoformat()

    finance_data: dict = {}
    if snap:
        updated          = snap["snapshot_date"]
        monthly_spending = _compute_monthly_spending(snap)
        portfolio        = _compute_portfolio(snap)
        nw               = snap["net_worth_summary"]
        income           = snap["income_summary"]
        months           = list(monthly_spending.keys())
        latest_month     = months[-1] if months else None
        latest_spend     = monthly_spending.get(latest_month, {})

        finance_data = {
            "net_worth": {
                "total":   nw["total_assets"],
                "cash":    nw["liquid_cash"],
                "taxable": nw["taxable_investments"],
                "ira":     nw["tax_advantaged_investments"],
            },
            "income": {
                "avg_monthly_net": round(income["avg_biweekly_net"] * 26 / 12, 2),
                "ytd_net":         income["ytd_net_income"],
                "source":          income["source"],
            },
            "monthly_spending":   monthly_spending,
            "monthly_totals": {
                m: round(sum(cats.values()), 2)
                for m, cats in monthly_spending.items()
            },
            "latest_month":       latest_month,
            "total_spend_latest": round(sum(latest_spend.values()), 2),
            "portfolio":          portfolio,
            "category_colors":    CATEGORY_COLORS,
        }

    month_label = ""
    if finance_data.get("latest_month"):
        dt = datetime.strptime(finance_data["latest_month"], "%Y-%m")
        month_label = dt.strftime("%B %Y")

    school_sorted = sorted(
        school,
        key=lambda e: (e.get("due_date") or "9999-99-99"),
    )

    return {
        "updated":      updated,
        "month_label":  month_label,
        "finance":      finance_data,
        "recruiting": {
            "entries": sorted(recruiting, key=lambda e: e.get("last_contact") or "", reverse=True),
            "stats":   _compute_recruiting_stats(recruiting),
            "stage_colors": STAGE_COLORS,
        },
        "school": {
            "entries": school_sorted,
            "today":   date.today().isoformat(),
        },
        "health": {
            "entries": sorted(health, key=lambda e: e["date"], reverse=True)[:30],
            "stats":   _compute_health_stats(health),
            "today":   date.today().isoformat(),
        },
    }

# ── HTML template ─────────────────────────────────────────────────────────────

_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Life OS</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
:root {
  --bg:      #0c0c0c;
  --surface: #141414;
  --surface2:#1a1a1a;
  --border:  #242424;
  --border2: #2e2e2e;
  --text:    #f5f5f5;
  --muted:   #666666;
  --muted2:  #444444;
  --accent:  #ffffff;
  --pos:     #e5e5e5;
  --neg:     #666666;
  --amber:   #aaaaaa;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  background: var(--bg);
  color: var(--text);
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  font-size: 13px;
  line-height: 1.5;
  min-height: 100vh;
  -webkit-font-smoothing: antialiased;
}
/* ── Nav ───────────────────────────────────────────────────── */
.topnav {
  display: flex;
  align-items: center;
  border-bottom: 1px solid var(--border);
  background: rgba(12,12,12,0.97);
  backdrop-filter: blur(12px);
  position: sticky;
  top: 0;
  z-index: 100;
  padding: 0 32px;
}
.logo {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 5px;
  text-transform: uppercase;
  color: var(--muted);
  padding: 18px 28px 18px 0;
  border-right: 1px solid var(--border);
  margin-right: 4px;
  white-space: nowrap;
}
.logo span { color: var(--text); }
.nav-tab {
  background: none;
  border: none;
  color: var(--muted2);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 2px;
  text-transform: uppercase;
  padding: 18px 20px;
  cursor: pointer;
  border-bottom: 1px solid transparent;
  transition: color 0.1s, border-color 0.1s;
}
.nav-tab:hover  { color: var(--muted); }
.nav-tab.active { color: var(--text); border-bottom-color: var(--text); }
.nav-right { margin-left: auto; font-size: 10px; color: var(--muted2); font-family: 'SF Mono', monospace; letter-spacing: 1px; }
/* ── Layout ────────────────────────────────────────────────── */
.section { display: none; max-width: 1280px; margin: 0 auto; padding: 40px 32px 80px; }
.section.active { display: block; }
/* ── Shared components ─────────────────────────────────────── */
.hero { margin-bottom: 48px; }
.hero-eyebrow {
  font-size: 10px; letter-spacing: 3px; text-transform: uppercase;
  color: var(--muted); margin-bottom: 10px; font-weight: 500;
}
.hero-value {
  font-size: 64px; font-weight: 800; letter-spacing: -4px;
  color: var(--text); line-height: 1;
}
.nw-row { display: flex; align-items: center; gap: 16px; }
.nw-toggle {
  background: none; border: 1px solid var(--border2); color: var(--muted);
  cursor: pointer; padding: 6px 8px; display: flex; align-items: center;
  transition: color 0.1s, border-color 0.1s; flex-shrink: 0; margin-top: 4px;
}
.nw-toggle:hover { color: var(--text); border-color: var(--muted); }
.hero-sub {
  margin-top: 14px; font-size: 12px; color: var(--muted);
  display: flex; gap: 28px; flex-wrap: wrap; letter-spacing: 0.3px;
}
.hero-sub span { color: var(--text); }
.grid-4 {
  display: grid; grid-template-columns: repeat(4, 1fr);
  gap: 1px; background: var(--border);
  border: 1px solid var(--border); margin-bottom: 20px;
}
.grid-3 {
  display: grid; grid-template-columns: repeat(3, 1fr);
  gap: 1px; background: var(--border);
  border: 1px solid var(--border); margin-bottom: 20px;
}
.stat-card { background: var(--surface); padding: 22px; }
.stat-label {
  font-size: 10px; letter-spacing: 2px; text-transform: uppercase;
  color: var(--muted2); margin-bottom: 10px; font-weight: 500;
}
.stat-value {
  font-size: 26px; font-weight: 700; letter-spacing: -0.5px;
  font-variant-numeric: tabular-nums; color: var(--text);
}
.stat-sub { font-size: 11px; color: var(--muted); margin-top: 5px; }
.pos { color: var(--pos); }
.neg { color: var(--neg); }
.amb { color: var(--amber); }
.charts-row {
  display: grid; grid-template-columns: 1fr 1fr;
  gap: 1px; background: var(--border);
  border: 1px solid var(--border); margin-bottom: 20px;
}
.chart-card { background: var(--surface); padding: 28px; }
canvas { max-height: 240px; }
.panel { border: 1px solid var(--border); background: var(--surface); margin-bottom: 20px; }
.panel-header {
  padding: 14px 22px; border-bottom: 1px solid var(--border);
  font-size: 10px; letter-spacing: 2px; text-transform: uppercase;
  color: var(--muted); display: flex; align-items: center; gap: 12px; font-weight: 500;
}
.panel-header .count {
  background: var(--surface2); color: var(--muted2);
  font-size: 10px; padding: 2px 7px; border: 1px solid var(--border);
}
table { width: 100%; border-collapse: collapse; }
th {
  text-align: left; padding: 10px 22px;
  font-size: 10px; letter-spacing: 1.5px; text-transform: uppercase;
  color: var(--muted2); border-bottom: 1px solid var(--border); font-weight: 500;
}
td { padding: 13px 22px; border-bottom: 1px solid var(--border); font-variant-numeric: tabular-nums; }
tr:last-child td { border-bottom: none; }
tr:hover td { background: rgba(255,255,255,0.02); }
.mono { font-family: 'SF Mono', 'Fira Code', 'Consolas', monospace; font-size: 12px; }
.badge {
  display: inline-block; font-size: 10px; letter-spacing: 1px; font-weight: 600;
  padding: 2px 8px; text-transform: uppercase; border-radius: 1px;
}
.tag {
  display: inline-block; font-size: 10px; letter-spacing: 1px;
  padding: 2px 7px; border: 1px solid var(--border2); color: var(--muted); text-transform: uppercase;
}
.section-eyebrow {
  font-size: 10px; letter-spacing: 2px; text-transform: uppercase;
  color: var(--muted2); margin-bottom: 20px; font-weight: 500;
}
.empty-state {
  padding: 56px 20px; text-align: center;
  color: var(--muted2); font-size: 11px; letter-spacing: 1.5px; text-transform: uppercase;
}
.empty-state code {
  display: block; margin-top: 12px; font-family: monospace;
  color: var(--muted); font-size: 11px; text-transform: none; letter-spacing: 0;
}
/* ── Recruiting ─────────────────────────────────────────────── */
.stage-filters { display: flex; gap: 3px; flex-wrap: wrap; margin-bottom: 20px; }
.stage-btn {
  background: var(--surface); border: 1px solid var(--border);
  color: var(--muted2); font-size: 10px; font-weight: 600;
  letter-spacing: 1.5px; text-transform: uppercase;
  padding: 6px 14px; cursor: pointer; transition: all 0.1s;
}
.stage-btn:hover { color: var(--muted); border-color: var(--border2); }
.stage-btn.active { background: var(--text); color: #000; border-color: var(--text); }
/* ── School ──────────────────────────────────────────────────── */
.urgent td { color: var(--text); }
.urgent td:nth-child(3) { color: var(--muted) !important; }
/* ── Health ──────────────────────────────────────────────────── */
.health-grid {
  display: grid; grid-template-columns: repeat(7, 1fr);
  gap: 4px; margin-bottom: 20px;
}
.health-day {
  background: var(--surface); border: 1px solid var(--border);
  padding: 12px 8px; text-align: center;
}
.health-day .day-label {
  font-size: 9px; color: var(--muted2); margin-bottom: 6px;
  text-transform: uppercase; letter-spacing: 1.5px;
}
.health-day .day-date { font-size: 18px; font-weight: 700; margin-bottom: 8px; color: var(--text); }
.health-day .day-icons { display: flex; gap: 4px; justify-content: center; font-size: 13px; }
.health-day.today { border-color: var(--border2); background: var(--surface2); }
.health-day.today .day-date { color: var(--accent); }
/* ── Responsive ────────────────────────────────────────────── */
@media (max-width: 900px) {
  .grid-4 { grid-template-columns: repeat(2, 1fr); }
  .grid-3 { grid-template-columns: repeat(2, 1fr); }
  .charts-row { grid-template-columns: 1fr; }
  .hero-value { font-size: 42px; letter-spacing: -2px; }
  .health-grid { grid-template-columns: repeat(4, 1fr); }
  .section { padding: 28px 20px 60px; }
}
</style>
</head>
<body>

<nav class="topnav">
  <div class="logo"><span>Life</span> OS</div>
  <button class="nav-tab active" onclick="showTab('finance')">Finance</button>
  <button class="nav-tab" onclick="showTab('recruiting')">Recruiting</button>
  <button class="nav-tab" onclick="showTab('school')">School</button>
  <button class="nav-tab" onclick="showTab('health')">Health</button>
  <div class="nav-right">SNAPSHOT // __UPDATED__</div>
</nav>

<!-- ── Finance ──────────────────────────────────────────────── -->
<div id="finance" class="section active">
  <div class="hero">
    <div class="hero-eyebrow">Total Net Worth</div>
    <div class="nw-row">
      <div class="hero-value" id="f-nw">$*****</div>
      <button class="nw-toggle" id="nw-toggle" onclick="toggleNW()"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg></button>
    </div>
    <div class="hero-sub" id="f-nw-sub"></div>
  </div>
  <div class="grid-4" id="f-stats"></div>
  <div class="charts-row">
    <div class="chart-card">
      <div class="section-eyebrow" id="f-pie-label">Spending by Category</div>
      <canvas id="pieChart"></canvas>
    </div>
    <div class="chart-card">
      <div class="section-eyebrow">Monthly Spend Trend</div>
      <canvas id="barChart"></canvas>
    </div>
  </div>
  <div class="panel">
    <div class="panel-header">Investment Portfolio</div>
    <table id="f-portfolio"></table>
  </div>
</div>

<!-- ── Recruiting ───────────────────────────────────────────── -->
<div id="recruiting" class="section">
  <div class="hero">
    <div class="hero-eyebrow">Recruiting Pipeline</div>
    <div class="hero-value" id="r-active"></div>
    <div class="hero-sub" id="r-sub"></div>
  </div>
  <div class="grid-4" id="r-stage-cards"></div>
  <div class="stage-filters" id="r-filters"></div>
  <div class="panel">
    <div class="panel-header">
      All Applications
      <span class="count" id="r-count"></span>
    </div>
    <table id="r-table"></table>
  </div>
</div>

<!-- ── School ───────────────────────────────────────────────── -->
<div id="school" class="section">
  <div class="hero">
    <div class="hero-eyebrow">School Deadlines</div>
    <div class="hero-value" id="s-upcoming"></div>
    <div class="hero-sub" id="s-sub"></div>
  </div>
  <div class="panel">
    <div class="panel-header">
      Deadlines
      <span class="count" id="s-count"></span>
    </div>
    <table id="s-table"></table>
  </div>
</div>

<!-- ── Health ───────────────────────────────────────────────── -->
<div id="health" class="section">
  <div class="hero">
    <div class="hero-eyebrow">Health Log</div>
    <div class="hero-value" id="h-streak"></div>
    <div class="hero-sub" id="h-sub"></div>
  </div>
  <div class="health-grid" id="h-grid"></div>
  <div class="panel">
    <div class="panel-header">Recent Log</div>
    <table id="h-table"></table>
  </div>
</div>

<script>
const D = __DATA_JSON__;

// ── Tab navigation ────────────────────────────────────────────
function showTab(name) {
  document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
  document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
  document.getElementById(name).classList.add('active');
  event.currentTarget.classList.add('active');
}

// ── Helpers ───────────────────────────────────────────────────
function fmt(n) {
  return "$" + (+n).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}
function fmtShort(n) {
  if (n >= 1000) return "$" + (n / 1000).toFixed(1) + "k";
  return "$" + Math.round(n);
}
function relDate(iso) {
  if (!iso) return "—";
  const diff = Math.round((new Date(iso) - new Date()) / 86400000);
  if (diff < -1)  return `${Math.abs(diff)}d overdue`;
  if (diff === -1) return "Yesterday";
  if (diff === 0)  return "Today";
  if (diff === 1)  return "Tomorrow";
  if (diff <= 7)   return `${diff}d`;
  return iso;
}
function badge(text, color) {
  return `<span class="badge" style="background:${color}22;color:${color};border:1px solid ${color}44">${text}</span>`;
}

// ── Finance ───────────────────────────────────────────────────
(function renderFinance() {
  const F = D.finance;
  if (!F || !F.net_worth) {
    document.getElementById('finance').innerHTML +=
      '<div class="empty-state">No financial snapshot found.<code>Add financial_snapshot_YYYY-MM-DD.json to the repo.</code></div>';
    return;
  }
  const nw = F.net_worth;
  const nwEl = document.getElementById('f-nw');
  const _nwFmt = fmt(nw.total);
  let _nwVisible = false;
  document.getElementById('f-nw-sub').innerHTML =
    `<div>Liquid Cash <span id="f-nw-cash">*****</span></div>` +
    `<div>Taxable Investments <span id="f-nw-taxable">*****</span></div>` +
    `<div>Roth IRA <span id="f-nw-ira">*****</span></div>`;

  window.toggleNW = function() {
    _nwVisible = !_nwVisible;
    const btn = document.getElementById('nw-toggle');
    if (_nwVisible) {
      nwEl.textContent = _nwFmt;
      document.getElementById('f-nw-cash').textContent = fmt(nw.cash);
      document.getElementById('f-nw-taxable').textContent = fmt(nw.taxable);
      document.getElementById('f-nw-ira').textContent = fmt(nw.ira);
      btn.innerHTML = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>';
    } else {
      nwEl.textContent = "$*****";
      document.getElementById("f-nw-cash").textContent = "*****";
      document.getElementById("f-nw-taxable").textContent = "*****";
      document.getElementById("f-nw-ira").textContent = "*****";
      btn.innerHTML = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>';
    }
  };

  const avgMo    = F.income.avg_monthly_net;
  const spend    = F.total_spend_latest;
  const savePct  = avgMo > 0 ? Math.round((1 - spend / avgMo) * 100) : 0;
  const saveAmt  = avgMo - spend;

  const stats = [
    { label: "Avg Monthly Income", value: fmt(avgMo),  sub: `YTD net ${fmt(F.income.ytd_net)}` },
    { label: "Monthly Spend",      value: fmt(spend),  sub: F.latest_month || "Latest" },
    { label: "Est. Savings Rate",  value: savePct + "%", sub: `~${fmt(saveAmt)} / mo kept`, cls: savePct > 40 ? "pos" : "" },
    { label: "Portfolio Gain",     value: fmt(F.portfolio.total_gain), sub: "unrealized total", cls: "pos" },
  ];
  const sg = document.getElementById('f-stats');
  stats.forEach(s => {
    sg.innerHTML += `<div class="stat-card"><div class="stat-label">${s.label}</div><div class="stat-value ${s.cls||''}">${s.value}</div><div class="stat-sub">${s.sub}</div></div>`;
  });

  if (F.latest_month) {
    const [y, m] = F.latest_month.split("-");
    const lbl = new Date(+y, +m-1).toLocaleString("en-US", { month: "long", year: "numeric" });
    document.getElementById('f-pie-label').textContent = lbl + " — Spending by Category";
  }

  const latestSpend = F.monthly_spending[F.latest_month] || {};
  const pieLabels   = Object.keys(latestSpend);
  const pieData     = Object.values(latestSpend);
  const pieColors   = pieLabels.map(l => F.category_colors[l] || "#666666");

  new Chart(document.getElementById("pieChart"), {
    type: "doughnut",
    data: { labels: pieLabels, datasets: [{ data: pieData, backgroundColor: pieColors, borderWidth: 1, borderColor: "#141414", hoverOffset: 6 }] },
    options: {
      plugins: {
        legend: { position: "right", labels: { color: "#555555", font: { size: 11, family: "Inter, -apple-system, sans-serif" }, padding: 12, boxWidth: 10 } },
        tooltip: { callbacks: { label: ctx => ` ${ctx.label}: ${fmt(ctx.raw)}` }, backgroundColor: "#1a1a1a", borderColor: "#2e2e2e", borderWidth: 1, titleColor: "#f5f5f5", bodyColor: "#888888" },
      },
      cutout: "66%",
    },
  });

  const barMonths = Object.keys(F.monthly_totals);
  const barVals   = Object.values(F.monthly_totals);
  const barLabels = barMonths.map(m => {
    const [y, mo] = m.split("-");
    return new Date(+y, +mo-1).toLocaleString("en-US", { month: "short" });
  });

  new Chart(document.getElementById("barChart"), {
    type: "bar",
    data: { labels: barLabels, datasets: [{ data: barVals, backgroundColor: "rgba(255,255,255,0.12)", borderColor: "rgba(255,255,255,0.25)", borderWidth: 1, borderRadius: 1, borderSkipped: false, hoverBackgroundColor: "rgba(255,255,255,0.22)" }] },
    options: {
      plugins: { legend: { display: false }, tooltip: { callbacks: { label: ctx => ` ${fmt(ctx.raw)}` }, backgroundColor: "#1a1a1a", borderColor: "#2e2e2e", borderWidth: 1, titleColor: "#f5f5f5", bodyColor: "#888888" } },
      scales: {
        x: { grid: { display: false }, ticks: { color: "#444444", font: { size: 11 } }, border: { color: "#242424" } },
        y: { grid: { color: "#1a1a1a" }, ticks: { color: "#444444", font: { size: 11 }, callback: v => "$" + v.toLocaleString() }, border: { color: "#242424" } },
      },
    },
  });

  const tbl = document.getElementById('f-portfolio');
  tbl.innerHTML = `<tr><th>Symbol</th><th>Account</th><th style="text-align:right">Value</th><th style="text-align:right">Gain/Loss</th><th style="text-align:right">Return</th></tr>`;
  F.portfolio.positions.forEach(p => {
    const cls = p.gain >= 0 ? "pos" : "neg";
    const sgn = p.gain >= 0 ? "+" : "";
    tbl.innerHTML += `<tr>
      <td><span class="mono">${p.symbol}</span></td>
      <td><span class="tag">${p.account}</span></td>
      <td style="text-align:right">${fmt(p.value)}</td>
      <td style="text-align:right" class="${cls}">${sgn}${fmt(Math.abs(p.gain))}</td>
      <td style="text-align:right" class="${cls}">${sgn}${p.gain_pct.toFixed(2)}%</td>
    </tr>`;
  });
  tbl.innerHTML += `<tr style="font-weight:700">
    <td class="mono">TOTAL</td><td></td>
    <td style="text-align:right">${fmt(F.portfolio.total)}</td>
    <td style="text-align:right" class="pos">+${fmt(F.portfolio.total_gain)}</td>
    <td></td>
  </tr>`;
})();

// ── Recruiting ────────────────────────────────────────────────
(function renderRecruiting() {
  const R        = D.recruiting;
  const entries  = R.entries;
  const stats    = R.stats;
  const colors   = R.stage_colors;
  let   current  = "All";

  document.getElementById('r-active').textContent = stats.active + " active";
  const subParts = Object.entries(stats.by_stage)
    .filter(([,v]) => v > 0)
    .map(([s, v]) => `<span style="color:${colors[s]||'#666666'}">${v} ${s}</span>`);
  document.getElementById('r-sub').innerHTML = subParts.join('<span style="color:#3d444d;margin:0 4px">·</span>');

  // Stage summary cards
  const stagesToShow = ["Applied", "Phone Screen", "OA", "Interview"];
  const sg = document.getElementById('r-stage-cards');
  stagesToShow.forEach(s => {
    const c = colors[s] || "#666666";
    sg.innerHTML += `<div class="stat-card" style="border-top:2px solid ${c}22">
      <div class="stat-label" style="color:${c}">${s}</div>
      <div class="stat-value">${stats.by_stage[s] || 0}</div>
      <div class="stat-sub">${s === 'Applied' ? 'awaiting response' : s === 'Phone Screen' ? 'in progress' : s === 'OA' ? 'pending' : 'scheduled'}</div>
    </div>`;
  });

  // Filter buttons
  const filters = document.getElementById('r-filters');
  const allStages = ["All", ...Object.keys(stats.by_stage).filter(s => stats.by_stage[s] > 0)];
  allStages.forEach(s => {
    const c = s === "All" ? "#ffffff" : (colors[s] || "#666666");
    const btn = document.createElement('button');
    btn.className = "stage-btn" + (s === "All" ? " active" : "");
    btn.style.cssText = s === "All" ? `background:${c};color:#000;border-color:${c}` : "";
    btn.textContent = s === "All" ? `All (${entries.length})` : `${s} (${stats.by_stage[s]})`;
    btn.onclick = () => filterRecruiting(s);
    filters.appendChild(btn);
  });

  function filterRecruiting(stage) {
    current = stage;
    document.querySelectorAll('.stage-btn').forEach(b => {
      b.classList.remove('active');
      b.style.cssText = "";
    });
    event.currentTarget.classList.add('active');
    const c = stage === "All" ? "#ffffff" : (colors[stage] || "#ffffff");
    event.currentTarget.style.cssText = `background:${c};color:#000;border-color:${c}`;
    renderTable();
  }

  function renderTable() {
    const filtered = current === "All" ? entries : entries.filter(e => e.stage === current);
    document.getElementById('r-count').textContent = filtered.length;
    const tbl = document.getElementById('r-table');

    if (!filtered.length) {
      tbl.innerHTML = `<tr><td colspan="5" style="padding:40px;text-align:center;color:var(--muted)">
        ${entries.length === 0 ? 'No entries — run <code style="color:var(--muted)">python main.py</code> to sync from Gmail' : 'No entries for this stage'}
      </td></tr>`;
      return;
    }

    tbl.innerHTML = `<tr><th>Company</th><th>Role</th><th>Stage</th><th>Last Contact</th><th>Next Action</th></tr>`;
    filtered.forEach(e => {
      const c = colors[e.stage] || "#666666";
      tbl.innerHTML += `<tr>
        <td style="font-weight:700">${e.company}</td>
        <td style="color:var(--muted)">${e.role || "—"}</td>
        <td>${badge(e.stage, c)}</td>
        <td class="mono" style="color:var(--muted)">${e.last_contact || "—"}</td>
        <td style="color:var(--muted);font-size:12px">${e.next_action || "—"}</td>
      </tr>`;
    });
  }

  document.getElementById('r-count').textContent = entries.length;
  renderTable();
})();

// ── School ────────────────────────────────────────────────────
(function renderSchool() {
  const S      = D.school;
  const entries = S.entries;
  const today  = S.today;

  const upcoming = entries.filter(e => {
    if (!e.due_date || e.status === "Complete") return false;
    const diff = (new Date(e.due_date) - new Date(today)) / 86400000;
    return diff <= 7;
  }).length;

  const active = entries.filter(e => e.status !== "Complete").length;

  document.getElementById('s-upcoming').textContent = upcoming + " due soon";
  document.getElementById('s-sub').innerHTML =
    `<div><span>${active}</span> active assignments</div>` +
    `<div><span>${entries.filter(e => e.status === "Complete").length}</span> completed</div>`;

  document.getElementById('s-count').textContent = entries.length;

  const tbl = document.getElementById('s-table');
  if (!entries.length) {
    tbl.innerHTML = `<tr><td colspan="5" class="empty-state">No school entries — run <code>python main.py</code> to sync from Gmail</td></tr>`;
    return;
  }

  const statusColor = { "Not Started": "#f85149", "In Progress": "#f59e0b", "Complete": "#39d353" };
  tbl.innerHTML = `<tr><th>Assignment</th><th>Course</th><th>Due Date</th><th>Status</th><th>Notes</th></tr>`;
  entries.forEach(e => {
    const diff = e.due_date ? Math.round((new Date(e.due_date) - new Date(today)) / 86400000) : null;
    const overdue = diff !== null && diff < 0 && e.status !== "Complete";
    const c = statusColor[e.status] || "#666666";
    tbl.innerHTML += `<tr class="${overdue ? 'urgent' : ''}">
      <td style="font-weight:600">${e.assignment}</td>
      <td><span class="tag">${e.course || "—"}</span></td>
      <td class="mono" style="color:${overdue ? '#f85149' : 'var(--muted)'}">${relDate(e.due_date)}</td>
      <td>${badge(e.status, c)}</td>
      <td style="color:var(--muted);font-size:12px">${e.notes ? e.notes.substring(0, 60) + (e.notes.length > 60 ? '…' : '') : '—'}</td>
    </tr>`;
  });
})();

// ── Health ────────────────────────────────────────────────────
(function renderHealth() {
  const H       = D.health;
  const entries = H.entries;
  const stats   = H.stats;
  const today   = H.today;

  document.getElementById('h-streak').textContent =
    stats.streak_workout + "-day streak";
  document.getElementById('h-sub').innerHTML =
    `<div>Workout streak <span>${stats.streak_workout} days</span></div>` +
    `<div>Ate well streak <span>${stats.streak_ate_well} days</span></div>` +
    `<div>Worked out <span>${stats.pct_workout_30}%</span> of last 30 days</div>` +
    `<div>Ate well <span>${stats.pct_ate_well_30}%</span> of last 30 days</div>`;

  // 14-day grid (2 rows of 7)
  const grid    = document.getElementById('h-grid');
  const byDate  = Object.fromEntries(entries.map(e => [e.date, e]));
  const days    = Array.from({ length: 14 }, (_, i) => {
    const d = new Date(today);
    d.setDate(d.getDate() - (13 - i));
    return d.toISOString().split("T")[0];
  });

  days.forEach(iso => {
    const e   = byDate[iso];
    const d   = new Date(iso + "T12:00:00");
    const lbl = d.toLocaleString("en-US", { weekday: "short" }).toUpperCase();
    const num = d.getDate();
    const isToday = iso === today;
    const w   = e?.worked_out ? "💪" : "·";
    const a   = e?.ate_well   ? "🥗" : "·";
    grid.innerHTML += `<div class="health-day${isToday ? ' today' : ''}">
      <div class="day-label">${lbl}</div>
      <div class="day-date">${num}</div>
      <div class="day-icons"><span title="Workout">${w}</span><span title="Ate well">${a}</span></div>
    </div>`;
  });

  const tbl = document.getElementById('h-table');
  if (!entries.length) {
    tbl.innerHTML = `<tr><td colspan="4" class="empty-state">No health entries — run <code>python main.py</code> to seed the last 14 days</td></tr>`;
    return;
  }
  tbl.innerHTML = `<tr><th>Date</th><th>Worked Out</th><th>Workout Type</th><th>Ate Well</th></tr>`;
  entries.slice(0, 30).forEach(e => {
    const w = e.worked_out ? `<span class="pos">✓</span>` : `<span style="color:#3d444d">—</span>`;
    const a = e.ate_well   ? `<span class="pos">✓</span>` : `<span style="color:#3d444d">—</span>`;
    tbl.innerHTML += `<tr>
      <td class="mono">${e.date}</td>
      <td>${w}</td>
      <td style="color:var(--muted)">${e.workout_type || "—"}</td>
      <td>${a}</td>
    </tr>`;
  });
})();
</script>
</body>
</html>
"""


def generate_site(out_path: str = "index.html") -> None:
    data = build_site_data()
    html = (
        _TEMPLATE
        .replace("__DATA_JSON__", json.dumps(data, indent=2))
        .replace("__UPDATED__",   data["updated"])
    )
    with open(out_path, "w") as f:
        f.write(html)
    print(f"Generated {out_path}")


def show_terminal_finance() -> None:
    from finance_generator import _load_snapshot, show_terminal
    snap = _load_snapshot()
    show_terminal(snap)


if __name__ == "__main__":
    if "--finance" in sys.argv:
        show_terminal_finance()
    else:
        generate_site()
        print("Open index.html or push to Cloudflare Pages.")
