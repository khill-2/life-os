import { useState, useEffect, useRef, useLayoutEffect } from 'react'
import Chart from 'chart.js/auto'
import { fmt } from '../lib/fmt'
import { flipReveal } from '../lib/flip'

const EYE_OPEN = (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
    <circle cx="12" cy="12" r="3"/>
  </svg>
)
const EYE_CLOSED = (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/>
    <line x1="1" y1="1" x2="23" y2="23"/>
  </svg>
)


export default function Finance({ data }) {
  const [visible, setVisible] = useState(false)
  const nwRef      = useRef(null)
  const cashRef    = useRef(null)
  const taxableRef = useRef(null)
  const iraRef     = useRef(null)
  const liabRef    = useRef(null)
  const pieRef     = useRef(null)
  const barRef     = useRef(null)
  const mounted    = useRef(false)

  if (!data || !data.net_worth) {
    return (
      <div className="section">
        <div className="empty-state">
          No financial snapshot found.
          <code>Add financial_snapshot_YYYY-MM-DD.json to the repo.</code>
        </div>
      </div>
    )
  }

  const nw         = data.net_worth
  const nwFmt      = fmt(nw.total)
  const cashFmt    = fmt(nw.cash)
  const taxableFmt = fmt(nw.taxable)
  const iraFmt     = fmt(nw.ira)
  const liabFmt    = fmt(nw.liabilities || 0)

  // Flip animation on toggle
  useLayoutEffect(() => {
    if (!mounted.current) { mounted.current = true; return }
    if (visible) {
      flipReveal(nwRef.current,      nwFmt,           1400)
      flipReveal(cashRef.current,    cashFmt,         1100)
      flipReveal(taxableRef.current, taxableFmt,      1100)
      flipReveal(iraRef.current,     iraFmt,          1100)
      flipReveal(liabRef.current,    '−' + liabFmt,  1100)
    }
  }, [visible])

  // Charts
  useEffect(() => {
    if (!pieRef.current || !barRef.current) return
    const latestSpend = data.monthly_spending?.[data.latest_month] ?? {}
    const pieLabels   = Object.keys(latestSpend)
    const pieData     = Object.values(latestSpend)
    const pieColors   = pieLabels.map(l => data.category_colors?.[l] ?? '#666666')

    const pie = new Chart(pieRef.current, {
      type: 'doughnut',
      data: { labels: pieLabels, datasets: [{ data: pieData, backgroundColor: pieColors, borderWidth: 1, borderColor: '#141414', hoverOffset: 6 }] },
      options: {
        plugins: {
          legend: { position: 'right', labels: { color: '#555555', font: { size: 11, family: 'Inter, -apple-system, sans-serif' }, padding: 12, boxWidth: 10 } },
          tooltip: { callbacks: { label: ctx => ` ${ctx.label}: ${fmt(ctx.raw)}` }, backgroundColor: '#1a1a1a', borderColor: '#2e2e2e', borderWidth: 1, titleColor: '#f5f5f5', bodyColor: '#888888' },
        },
        cutout: '66%',
      },
    })

    const barMonths = Object.keys(data.monthly_totals ?? {})
    const barVals   = Object.values(data.monthly_totals ?? {})
    const barLabels = barMonths.map(m => {
      const [y, mo] = m.split('-')
      return new Date(+y, +mo - 1).toLocaleString('en-US', { month: 'short' })
    })

    const bar = new Chart(barRef.current, {
      type: 'bar',
      data: { labels: barLabels, datasets: [{ data: barVals, backgroundColor: 'rgba(255,255,255,0.12)', borderColor: 'rgba(255,255,255,0.25)', borderWidth: 1, borderRadius: 1, borderSkipped: false, hoverBackgroundColor: 'rgba(255,255,255,0.22)' }] },
      options: {
        plugins: { legend: { display: false }, tooltip: { callbacks: { label: ctx => ` ${fmt(ctx.raw)}` }, backgroundColor: '#1a1a1a', borderColor: '#2e2e2e', borderWidth: 1, titleColor: '#f5f5f5', bodyColor: '#888888' } },
        scales: {
          x: { grid: { display: false }, ticks: { color: '#444444', font: { size: 11 } }, border: { color: '#242424' } },
          y: { grid: { color: '#1a1a1a' }, ticks: { color: '#444444', font: { size: 11 }, callback: v => '$' + v.toLocaleString() }, border: { color: '#242424' } },
        },
      },
    })

    return () => { pie.destroy(); bar.destroy() }
  }, [data])

  const avgMo   = data.income?.avg_monthly_net ?? 0
  const spend   = data.total_spend_latest ?? 0
  const savePct = avgMo > 0 ? Math.round((1 - spend / avgMo) * 100) : 0
  const saveAmt = avgMo - spend

  const pieLabel = data.latest_month
    ? (() => { const [y, m] = data.latest_month.split('-'); return new Date(+y, +m - 1).toLocaleString('en-US', { month: 'long', year: 'numeric' }) + ' — Spending by Category' })()
    : 'Spending by Category'

  const stats = [
    { label: 'Avg Monthly Income', value: fmt(avgMo),    sub: `YTD net ${fmt(data.income?.ytd_net ?? 0)}` },
    { label: 'Monthly Spend',      value: fmt(spend),    sub: data.latest_month ?? 'Latest' },
    { label: 'Est. Savings Rate',  value: savePct + '%', sub: `~${fmt(saveAmt)} / mo kept`, cls: savePct > 40 ? 'pos' : '' },
    { label: 'Portfolio Gain',     value: fmt(data.portfolio?.total_gain ?? 0), sub: 'unrealized total', cls: 'pos' },
  ]

  const IG      = data.investment_goals
  const today   = new Date()
  const fullMos = 12 - (today.getMonth() + 1)

  return (
    <div className="section">
      {/* Hero */}
      <div className="hero">
        <div className="hero-eyebrow">Total Net Worth</div>
        <div className="nw-row">
          <div className="hero-value" ref={nwRef} style={{ opacity: visible ? 1 : 0, transition: 'opacity 0.4s ease' }}>{nwFmt}</div>
          <button className="nw-toggle" onClick={() => setVisible(v => !v)}>
            {visible ? EYE_OPEN : EYE_CLOSED}
          </button>
        </div>
        <div className="hero-sub" style={{ opacity: visible ? 1 : 0, transition: 'opacity 0.35s ease' }}>
          <div>Liquid Cash <span ref={cashRef}>{cashFmt}</span></div>
          <div>Taxable Investments <span ref={taxableRef}>{taxableFmt}</span></div>
          <div>Roth IRA <span ref={iraRef}>{iraFmt}</span></div>
          {nw.liabilities > 0 && (
            <div style={{ color: 'var(--red)' }}>Liabilities <span ref={liabRef}>{'−' + liabFmt}</span></div>
          )}
        </div>
      </div>

      {/* Stats */}
      <div className="grid-4">
        {stats.map(s => (
          <div className="stat-card" key={s.label}>
            <div className="stat-label">{s.label}</div>
            <div className={`stat-value ${s.cls ?? ''}`}>{s.value}</div>
            <div className="stat-sub">{s.sub}</div>
          </div>
        ))}
      </div>

      {/* Charts */}
      <div className="charts-row">
        <div className="chart-card">
          <div className="section-eyebrow">{pieLabel}</div>
          <canvas ref={pieRef} />
        </div>
        <div className="chart-card">
          <div className="section-eyebrow">Monthly Spend Trend</div>
          <canvas ref={barRef} />
        </div>
      </div>

      {/* Portfolio */}
      <div className="panel">
        <div className="panel-header">Investment Portfolio</div>
        <table>
          <thead>
            <tr>
              <th>Symbol</th><th>Account</th>
              <th style={{ textAlign: 'right' }}>Value</th>
              <th style={{ textAlign: 'right' }}>Gain/Loss</th>
              <th style={{ textAlign: 'right' }}>Return</th>
            </tr>
          </thead>
          <tbody>
            {(data.portfolio?.positions ?? []).map((p, i) => {
              const cls = p.gain >= 0 ? 'pos' : 'neg'
              const sgn = p.gain >= 0 ? '+' : ''
              return (
                <tr key={i}>
                  <td><span className="mono">{p.symbol}</span></td>
                  <td><span className="tag">{p.account}</span></td>
                  <td style={{ textAlign: 'right' }}>{fmt(p.value)}</td>
                  <td style={{ textAlign: 'right' }} className={cls}>{sgn}{fmt(Math.abs(p.gain))}</td>
                  <td style={{ textAlign: 'right' }} className={cls}>{sgn}{p.gain_pct.toFixed(2)}%</td>
                </tr>
              )
            })}
            <tr style={{ fontWeight: 700 }}>
              <td className="mono">TOTAL</td><td></td>
              <td style={{ textAlign: 'right' }}>{fmt(data.portfolio?.total ?? 0)}</td>
              <td style={{ textAlign: 'right' }} className="pos">+{fmt(data.portfolio?.total_gain ?? 0)}</td>
              <td></td>
            </tr>
          </tbody>
        </table>
      </div>

      {/* Investment Goals */}
      {IG && <InvestmentGoals ig={IG} fullMos={fullMos} today={today} />}
    </div>
  )
}

function InvestmentGoals({ ig, fullMos, today }) {
  const rothLimit   = ig.roth_ira?.limit ?? 7000
  const rothDone    = ig.roth_ira?.contributed ?? 0
  const rothLeft    = rothLimit - rothDone
  const rothMonthly = fullMos > 0 ? rothLeft / fullMos : rothLeft
  const rothPct     = Math.min(100, Math.round(rothDone / rothLimit * 100))

  const broYTD    = ig.brokerage?.invested_ytd ?? 0
  const broTarget = ig.brokerage?.monthly_target ?? 3000
  const monthsIn  = today.getMonth() + today.getDate() / 31
  const broPace   = monthsIn > 0 ? Math.round(broYTD / monthsIn) : 0

  const CB = ig.chase_bonus
  let chaseRow = null
  if (CB?.spend_goal) {
    const deadline    = new Date(CB.spend_by + 'T00:00:00')
    const daysLeft    = Math.max(0, Math.round((deadline - today) / 86400000))
    const chaseLeft   = CB.spend_goal - CB.current_spend
    const dailyNeeded = daysLeft > 0 ? chaseLeft / daysLeft : chaseLeft
    const chasePct    = Math.min(100, Math.round(CB.current_spend / CB.spend_goal * 100))
    chaseRow = (
      <div className="invest-row">
        <div className="invest-top">
          <div className="invest-name">Chase Sapphire — Signup Bonus</div>
          <div className="invest-amt">{fmt(CB.current_spend)}<span className="of">of {fmt(CB.spend_goal)}</span></div>
        </div>
        <div className="invest-track"><div className="invest-fill" style={{ width: chasePct + '%' }} /></div>
        <div className="invest-meta">
          <div>Deadline <span>{CB.spend_by}</span></div>
          <div><span>{daysLeft}d</span> remaining</div>
          <div>Need <span>{fmt(chaseLeft)}</span> more · <span>{fmt(dailyNeeded)}/day</span></div>
          <div><span>{(CB.points ?? 0).toLocaleString()} UR pts</span> on completion</div>
        </div>
      </div>
    )
  }

  return (
    <div className="panel">
      <div className="panel-header">2026 Investment Goals</div>
      <div className="invest-row">
        <div className="invest-top">
          <div className="invest-name">Roth IRA — 2026</div>
          <div className="invest-amt">{fmt(rothDone)}<span className="of">of {fmt(rothLimit)}</span></div>
        </div>
        <div className="invest-track"><div className="invest-fill" style={{ width: rothPct + '%' }} /></div>
        <div className="invest-meta">
          <div><span>{fmt(rothLeft)}</span> remaining</div>
          <div><span>{fmt(Math.round(rothMonthly))}/mo</span> to max by Dec</div>
          <div><span>{fullMos}</span> full months left</div>
        </div>
      </div>
      <div className="invest-row">
        <div className="invest-top">
          <div className="invest-name">Taxable Brokerage — YTD</div>
          <div className="invest-amt">{fmt(broYTD)}</div>
        </div>
        <div className="invest-meta">
          <div>Target <span>{fmt(broTarget)}/mo</span></div>
          <div>Pace <span>{fmt(broPace)}/mo</span> YTD avg</div>
        </div>
      </div>
      {chaseRow}
    </div>
  )
}
