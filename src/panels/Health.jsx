export default function Health({ data }) {
  const { entries = [], stats = {}, today = new Date().toISOString().split('T')[0] } = data ?? {}

  const byDate = Object.fromEntries(entries.map(e => [e.date, e]))
  const days   = Array.from({ length: 14 }, (_, i) => {
    const d = new Date(today + 'T12:00:00')
    d.setDate(d.getDate() - (13 - i))
    return d.toISOString().split('T')[0]
  })

  return (
    <div className="section">
      <div className="hero">
        <div className="hero-eyebrow">Health Log</div>
        <div className="hero-value">{stats.streak_workout ?? 0}-day streak</div>
        <div className="hero-sub">
          <div>Workout streak <span>{stats.streak_workout ?? 0} days</span></div>
          <div>Ate well streak <span>{stats.streak_ate_well ?? 0} days</span></div>
          <div>Worked out <span>{stats.pct_workout_30 ?? 0}%</span> of last 30 days</div>
          <div>Ate well <span>{stats.pct_ate_well_30 ?? 0}%</span> of last 30 days</div>
        </div>
      </div>

      <div className="health-grid">
        {days.map(iso => {
          const e       = byDate[iso]
          const d       = new Date(iso + 'T12:00:00')
          const lbl     = d.toLocaleString('en-US', { weekday: 'short' }).toUpperCase()
          const num     = d.getDate()
          const isToday = iso === today
          return (
            <div key={iso} className={`health-day${isToday ? ' today' : ''}`}>
              <div className="day-label">{lbl}</div>
              <div className="day-date">{num}</div>
              <div className="day-icons">
                {e?.worked_out
                  ? <span className="h-on" title="Worked out">W</span>
                  : <span className="h-off" title="No workout">·</span>}
                {e?.ate_well
                  ? <span className="h-on" title="Ate well">A</span>
                  : <span className="h-off" title="Didn't eat well">·</span>}
              </div>
            </div>
          )
        })}
      </div>

      <div className="panel">
        <div className="panel-header">Recent Log</div>
        <table>
          {entries.length > 0 && (
            <thead>
              <tr>
                <th>Date</th><th>Worked Out</th><th>Workout Type</th><th>Ate Well</th>
              </tr>
            </thead>
          )}
          <tbody>
            {entries.length === 0 ? (
              <tr>
                <td colSpan={4} className="empty-state">
                  No health entries — run <code>python main.py</code> to seed the last 14 days
                </td>
              </tr>
            ) : entries.slice(0, 30).map((e, i) => (
              <tr key={i}>
                <td className="mono">{e.date}</td>
                <td>{e.worked_out ? <span className="pos">✓</span> : <span style={{ color: '#3d444d' }}>—</span>}</td>
                <td style={{ color: 'var(--muted)' }}>{e.workout_type ?? '—'}</td>
                <td>{e.ate_well ? <span className="pos">✓</span> : <span style={{ color: '#3d444d' }}>—</span>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
