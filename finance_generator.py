#!/usr/bin/env python3
"""
Reads financial_snapshot_*.json → generates index.html (Cloudflare Pages dashboard).
Run directly to regenerate the dashboard or print a terminal view.

Usage:
    python finance_generator.py              # generate index.html
    python finance_generator.py --terminal   # rich terminal dashboard
"""

import json
import glob
import sys
from datetime import datetime
from collections import defaultdict

# ── Category mappings ────────────────────────────────────────────────────────

CATEGORY_MAP = {
    "Restaurants":        "Food & Dining",
    "Supermarkets":       "Food & Dining",
    "Food & Drink":       "Food & Dining",
    "Gasoline":           "Transportation",
    "Travel/Entertainment": "Entertainment",
    "Education":          "Entertainment",
    "Automotive":         "Auto",
    "Medical Services":   "Health",
    "Merchandise":        "Shopping",
    "Home Improvement":   "Shopping",
    "Services":           "Other",
}

CATEGORY_COLORS = {
    "Food & Dining":  "#f59e0b",
    "Housing":        "#3b82f6",
    "Transportation": "#8b5cf6",
    "Entertainment":  "#10b981",
    "Auto":           "#f43f5e",
    "Health":         "#06b6d4",
    "Shopping":       "#f97316",
    "Workspace":      "#a78bfa",
    "Insurance":      "#64748b",
    "Investments":    "#22c55e",
    "Fees":           "#ef4444",
    "Trading":        "#fbbf24",
    "Other":          "#94a3b8",
}

# ── Data loading ─────────────────────────────────────────────────────────────

def _load_snapshot() -> dict:
    files = sorted(glob.glob("financial_snapshot_*.json"))
    if not files:
        raise FileNotFoundError("No financial_snapshot_*.json found in current directory.")
    with open(files[-1]) as f:
        return json.load(f)


# ── Computation ──────────────────────────────────────────────────────────────

def _compute_monthly_spending(snap: dict) -> dict:
    monthly: dict = defaultdict(lambda: defaultdict(float))

    # Discover card: positive = charge; skip payments/credits/fees
    for tx in snap["accounts"]["discover_it"]["transactions"]:
        if tx["category"] in ("Payments and Credits", "Fees"):
            continue
        if tx["amount"] <= 0:
            continue
        cat = CATEGORY_MAP.get(tx["category"], tx["category"])
        monthly[tx["date"][:7]][cat] += tx["amount"]

    # Chase Sapphire: negative = charge
    for tx in snap["accounts"]["chase_sapphire_preferred"]["transactions"]:
        if tx["amount"] >= 0:
            continue
        cat = CATEGORY_MAP.get(tx["category"], tx["category"])
        monthly[tx["date"][:7]][cat] += abs(tx["amount"])

    # Housing from savings (OHANA)
    for tx in snap["accounts"]["capital_one_savings"]["transactions"]:
        if "OHANA" in tx["description"]:
            monthly[tx["date"][:7]]["Housing"] += abs(tx["amount"])

    # Workspace + Insurance + Trading from checking
    for tx in snap["accounts"]["capital_one_checking"]["transactions"]:
        desc = tx["description"].upper()
        amt = tx["amount"]
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
            "symbol": p["symbol"],
            "value": p["market_value"],
            "gain": p["gain_loss"],
            "gain_pct": p["gain_loss_pct"],
            "account": "Schwab",
        })
    for p in snap["accounts"]["fidelity_roth_ira"]["positions"]:
        if p.get("symbol") == "SPAXX":
            continue
        positions.append({
            "symbol": p["symbol"],
            "value": p["market_value"],
            "gain": p.get("gain_loss", 0),
            "gain_pct": p.get("gain_loss_pct", 0),
            "account": "Fidelity Roth",
        })
    schwab = snap["accounts"]["schwab_brokerage"]
    fidelity = snap["accounts"]["fidelity_roth_ira"]
    return {
        "total": schwab["total_value"] + fidelity["total_value"],
        "total_gain": schwab["total_gain_loss"] + fidelity["total_gain_loss"],
        "positions": sorted(positions, key=lambda x: -x["value"]),
    }


# ── HTML generation ──────────────────────────────────────────────────────────

_HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>OS / Finance</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
  :root {
    --bg:      #060a0f;
    --surface: #0d1117;
    --border:  #1c2333;
    --text:    #f0f6fc;
    --muted:   #8b949e;
    --accent:  #4a9eff;
    --green:   #39d353;
    --red:     #f85149;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    background: var(--bg);
    color: var(--text);
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Inter', sans-serif;
    font-size: 13px;
    line-height: 1.5;
    min-height: 100vh;
    background-image: radial-gradient(circle at 1px 1px, #1c2333 1px, transparent 0);
    background-size: 28px 28px;
  }
  #dashboard { max-width: 1280px; margin: 0 auto; padding: 32px 24px; }
  .site-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 48px;
    padding-bottom: 20px;
    border-bottom: 1px solid var(--border);
  }
  .logo {
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 4px;
    text-transform: uppercase;
    color: var(--muted);
  }
  .logo span { color: var(--accent); }
  .updated { font-size: 11px; color: var(--muted); font-family: monospace; }
  .hero {
    margin-bottom: 48px;
  }
  .hero-label {
    font-size: 11px;
    letter-spacing: 3px;
    text-transform: uppercase;
    color: var(--muted);
    margin-bottom: 8px;
  }
  .hero-value {
    font-size: 64px;
    font-weight: 800;
    letter-spacing: -3px;
    color: var(--text);
    line-height: 1;
  }
  .hero-sub {
    margin-top: 12px;
    font-size: 13px;
    color: var(--muted);
    display: flex;
    gap: 24px;
  }
  .hero-sub span { color: var(--text); }
  .stat-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 1px;
    background: var(--border);
    border: 1px solid var(--border);
    margin-bottom: 24px;
  }
  .stat {
    background: var(--surface);
    padding: 20px;
  }
  .stat-label {
    font-size: 10px;
    letter-spacing: 2px;
    text-transform: uppercase;
    color: var(--muted);
    margin-bottom: 8px;
  }
  .stat-value {
    font-size: 28px;
    font-weight: 700;
    letter-spacing: -1px;
    font-variant-numeric: tabular-nums;
  }
  .stat-sub { font-size: 11px; color: var(--muted); margin-top: 4px; }
  .pos { color: var(--green); }
  .neg { color: var(--red); }
  .charts-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1px;
    background: var(--border);
    border: 1px solid var(--border);
    margin-bottom: 24px;
  }
  .chart-card {
    background: var(--surface);
    padding: 24px;
  }
  .section-label {
    font-size: 10px;
    letter-spacing: 2px;
    text-transform: uppercase;
    color: var(--muted);
    margin-bottom: 20px;
  }
  canvas { max-height: 240px; }
  .table-card {
    border: 1px solid var(--border);
    background: var(--surface);
    margin-bottom: 24px;
  }
  .table-header {
    padding: 16px 20px;
    border-bottom: 1px solid var(--border);
    font-size: 10px;
    letter-spacing: 2px;
    text-transform: uppercase;
    color: var(--muted);
  }
  table { width: 100%; border-collapse: collapse; }
  th {
    text-align: left;
    padding: 10px 20px;
    font-size: 10px;
    letter-spacing: 1.5px;
    text-transform: uppercase;
    color: var(--muted);
    border-bottom: 1px solid var(--border);
    font-weight: 500;
  }
  td { padding: 12px 20px; border-bottom: 1px solid var(--border); font-variant-numeric: tabular-nums; }
  tr:last-child td { border-bottom: none; }
  tr:hover td { background: rgba(74, 158, 255, 0.03); }
  .mono { font-family: 'SF Mono', 'Fira Code', monospace; font-size: 13px; }
  .tag {
    display: inline-block;
    font-size: 10px;
    letter-spacing: 1px;
    padding: 2px 7px;
    border: 1px solid var(--border);
    color: var(--muted);
    text-transform: uppercase;
  }
  @media (max-width: 768px) {
    .stat-grid { grid-template-columns: repeat(2, 1fr); }
    .charts-row { grid-template-columns: 1fr; }
    .hero-value { font-size: 40px; }
  }
</style>
</head>
<body>

<div id="dashboard">
  <header class="site-header">
    <div class="logo"><span>KCH</span> / OS — FINANCE</div>
    <div class="updated">SNAPSHOT // __UPDATED__</div>
  </header>

  <div class="hero">
    <div class="hero-label">Total Net Worth</div>
    <div class="hero-value" id="nw-value"></div>
    <div class="hero-sub" id="nw-sub"></div>
  </div>

  <div class="stat-grid" id="stats"></div>

  <div class="charts-row">
    <div class="chart-card">
      <div class="section-label">__MONTH_LABEL__ — Spending by Category</div>
      <canvas id="pieChart"></canvas>
    </div>
    <div class="chart-card">
      <div class="section-label">Monthly Spend Trend</div>
      <canvas id="barChart"></canvas>
    </div>
  </div>

  <div class="table-card">
    <div class="table-header">Investment Portfolio</div>
    <table id="portfolio-table"></table>
  </div>
</div>

<script>
const D = __DATA_JSON__;

renderDashboard();
function renderDashboard() {
  const nw = D.net_worth;
  document.getElementById("nw-value").textContent = fmt(nw.total);
  document.getElementById("nw-sub").innerHTML =
    `<div>Liquid Cash <span>${fmt(nw.cash)}</span></div>` +
    `<div>Taxable Investments <span>${fmt(nw.taxable)}</span></div>` +
    `<div>Roth IRA <span>${fmt(nw.ira)}</span></div>`;

  // Stat cards
  const avgMonthly = D.income.avg_monthly_net;
  const totalSpend = D.total_spend_latest;
  const savingsRate = avgMonthly > 0 ? Math.round((1 - totalSpend / avgMonthly) * 100) : 0;

  const stats = [
    { label: "Avg Monthly Income", value: fmt(avgMonthly), sub: `YTD net ${fmt(D.income.ytd_net)}` },
    { label: "Monthly Spend", value: fmt(totalSpend), sub: `${D.latest_month || "Latest"}` },
    { label: "Est. Savings Rate", value: savingsRate + "%", sub: `~${fmt(avgMonthly - totalSpend)} / mo kept`, cls: savingsRate > 40 ? "pos" : "" },
    { label: "Portfolio Gain", value: fmt(D.portfolio.total_gain), sub: "unrealized", cls: "pos" },
  ];

  const statsEl = document.getElementById("stats");
  stats.forEach(s => {
    statsEl.innerHTML += `<div class="stat">
      <div class="stat-label">${s.label}</div>
      <div class="stat-value ${s.cls || ''}">${s.value}</div>
      <div class="stat-sub">${s.sub}</div>
    </div>`;
  });

  // Pie chart
  const latestSpend = D.monthly_spending[D.latest_month] || {};
  const pieLabels = Object.keys(latestSpend);
  const pieData   = Object.values(latestSpend);
  const pieColors = pieLabels.map(l => D.category_colors[l] || "#94a3b8");

  new Chart(document.getElementById("pieChart"), {
    type: "doughnut",
    data: {
      labels: pieLabels,
      datasets: [{ data: pieData, backgroundColor: pieColors, borderWidth: 0, hoverOffset: 8 }],
    },
    options: {
      plugins: {
        legend: {
          position: "right",
          labels: { color: "#8b949e", font: { size: 11 }, padding: 10, boxWidth: 10 },
        },
        tooltip: { callbacks: { label: ctx => ` ${ctx.label}: ${fmt(ctx.raw)}` } },
      },
      cutout: "64%",
    },
  });

  // Bar chart
  const barMonths = Object.keys(D.monthly_totals);
  const barVals   = Object.values(D.monthly_totals);
  const barLabels = barMonths.map(m => {
    const [y, mo] = m.split("-");
    return new Date(+y, +mo - 1).toLocaleString("en-US", { month: "short" });
  });

  new Chart(document.getElementById("barChart"), {
    type: "bar",
    data: {
      labels: barLabels,
      datasets: [{
        label: "Total Spend",
        data: barVals,
        backgroundColor: "rgba(74, 158, 255, 0.7)",
        borderRadius: 2,
        borderSkipped: false,
      }],
    },
    options: {
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: { label: ctx => ` ${fmt(ctx.raw)}` } },
      },
      scales: {
        x: { grid: { display: false }, ticks: { color: "#8b949e", font: { size: 11 } } },
        y: {
          grid: { color: "#1c2333" },
          ticks: { color: "#8b949e", font: { size: 11 }, callback: v => "$" + v.toLocaleString() },
        },
      },
    },
  });

  // Portfolio table
  const tbl = document.getElementById("portfolio-table");
  tbl.innerHTML = `<tr>
    <th>Symbol</th><th>Account</th>
    <th style="text-align:right">Value</th>
    <th style="text-align:right">Gain / Loss</th>
    <th style="text-align:right">Return</th>
  </tr>`;

  D.portfolio.positions.forEach(p => {
    const cls = p.gain >= 0 ? "pos" : "neg";
    const sign = p.gain >= 0 ? "+" : "";
    tbl.innerHTML += `<tr>
      <td><span class="mono">${p.symbol}</span></td>
      <td><span class="tag">${p.account}</span></td>
      <td style="text-align:right">${fmt(p.value)}</td>
      <td style="text-align:right" class="${cls}">${sign}${fmt(Math.abs(p.gain))}</td>
      <td style="text-align:right" class="${cls}">${sign}${p.gain_pct.toFixed(2)}%</td>
    </tr>`;
  });

  const totalGain = D.portfolio.total_gain;
  tbl.innerHTML += `<tr style="font-weight:700">
    <td class="mono">TOTAL</td><td></td>
    <td style="text-align:right">${fmt(D.portfolio.total)}</td>
    <td style="text-align:right" class="pos">+${fmt(totalGain)}</td>
    <td></td>
  </tr>`;
}

function fmt(n) {
  return "$" + (+n).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}
</script>
</body>
</html>
"""


def generate_dashboard(snap: dict, out_path: str = "index.html") -> None:
    monthly_spending = _compute_monthly_spending(snap)
    portfolio        = _compute_portfolio(snap)
    nw               = snap["net_worth_summary"]
    income           = snap["income_summary"]

    months       = list(monthly_spending.keys())
    latest_month = months[-1] if months else None
    latest_spend = monthly_spending.get(latest_month, {})
    total_spend  = round(sum(latest_spend.values()), 2)

    monthly_totals = {
        m: round(sum(cats.values()), 2)
        for m, cats in monthly_spending.items()
    }

    avg_monthly_income = round(income["avg_biweekly_net"] * 26 / 12, 2)

    month_label = ""
    if latest_month:
        dt = datetime.strptime(latest_month, "%Y-%m")
        month_label = dt.strftime("%B %Y")

    dashboard_data = {
        "updated":            snap["snapshot_date"],
        "net_worth":          {
            "total":   nw["total_assets"],
            "cash":    nw["liquid_cash"],
            "taxable": nw["taxable_investments"],
            "ira":     nw["tax_advantaged_investments"],
        },
        "income":             {
            "avg_monthly_net": avg_monthly_income,
            "ytd_net":         income["ytd_net_income"],
        },
        "monthly_spending":   monthly_spending,
        "monthly_totals":     monthly_totals,
        "latest_month":       latest_month,
        "total_spend_latest": total_spend,
        "portfolio":          portfolio,
        "category_colors":    CATEGORY_COLORS,
    }

    html = (
        _HTML_TEMPLATE
        .replace("__DATA_JSON__",   json.dumps(dashboard_data, indent=2))
        .replace("__UPDATED__",     snap["snapshot_date"])
        .replace("__MONTH_LABEL__", month_label)
    )

    with open(out_path, "w") as f:
        f.write(html)
    print(f"Generated {out_path}")


# ── Terminal dashboard ────────────────────────────────────────────────────────

def show_terminal(snap: dict) -> None:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel

    console = Console()
    monthly  = _compute_monthly_spending(snap)
    port     = _compute_portfolio(snap)
    nw       = snap["net_worth_summary"]
    income   = snap["income_summary"]

    latest      = list(monthly.keys())[-1] if monthly else None
    latest_spend = monthly.get(latest, {})
    total_spend  = sum(latest_spend.values())

    console.print(Panel(
        f"[bold white]Net Worth:[/bold white] [green]${nw['total_assets']:,.2f}[/green]   "
        f"[dim]Cash:[/dim] [white]${nw['liquid_cash']:,.2f}[/white]   "
        f"[dim]Invested:[/dim] [white]${nw['taxable_investments'] + nw['tax_advantaged_investments']:,.2f}[/white]   "
        f"[dim]Avg Mo. Income:[/dim] [white]${income['avg_biweekly_net'] * 26 / 12:,.0f}[/white]",
        title="[bold cyan]KCH / OS — FINANCE[/bold cyan]",
        border_style="cyan",
    ))

    if latest:
        dt = datetime.strptime(latest, "%Y-%m")
        console.print(f"\n  [bold]{dt.strftime('%B %Y')} Spending[/bold]  [dim]${total_spend:,.2f} total[/dim]\n")
        for cat, amt in latest_spend.items():
            pct = amt / total_spend if total_spend else 0
            filled = int(pct * 28)
            bar = "█" * filled + "░" * (28 - filled)
            console.print(f"  [dim]{cat:<16}[/dim]  [cyan]{bar}[/cyan]  [white bold]${amt:>9,.2f}[/white bold]  [dim]{pct:>4.0%}[/dim]")

    tbl = Table(border_style="dim", show_header=True, header_style="dim", padding=(0, 1))
    tbl.add_column("SYMBOL", style="bold cyan", width=8)
    tbl.add_column("ACCOUNT", style="dim", width=14)
    tbl.add_column("VALUE", justify="right", width=12)
    tbl.add_column("GAIN/LOSS", justify="right", width=12)
    tbl.add_column("RETURN", justify="right", width=8)

    for p in port["positions"]:
        g, gp = p["gain"], p["gain_pct"]
        g_str  = f"[green]+${g:,.2f}[/green]"  if g >= 0 else f"[red]-${abs(g):,.2f}[/red]"
        gp_str = f"[green]+{gp:.2f}%[/green]"  if gp >= 0 else f"[red]{gp:.2f}%[/red]"
        tbl.add_row(p["symbol"], p["account"], f"${p['value']:,.2f}", g_str, gp_str)

    tbl.add_section()
    total_g = port["total_gain"]
    tbl.add_row(
        "[bold]TOTAL[/bold]", "",
        f"[bold]${port['total']:,.2f}[/bold]",
        f"[bold green]+${total_g:,.2f}[/bold green]", "",
    )
    console.print(f"\n  [bold]Portfolio[/bold]\n")
    console.print(tbl)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import os
    snap = _load_snapshot()

    if "--terminal" in sys.argv:
        show_terminal(snap)
    else:
        generate_dashboard(snap)
        print("Open index.html in a browser or deploy to Cloudflare Pages.")
