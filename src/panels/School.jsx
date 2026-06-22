import { relDate } from '../lib/fmt'

function Badge({ text, color }) {
  return (
    <span
      className="badge"
      style={{ background: color + '22', color, border: `1px solid ${color}44` }}
    >{text}</span>
  )
}

const STATUS_COLOR = {
  'Not Started': '#f85149',
  'In Progress': '#f59e0b',
  'Complete':    '#39d353',
}

export default function School({ data }) {
  const { entries = [], today = new Date().toISOString().split('T')[0] } = data ?? {}

  const upcoming = entries.filter(e => {
    if (!e.due_date || e.status === 'Complete') return false
    const diff = (new Date(e.due_date) - new Date(today)) / 86400000
    return diff <= 7
  }).length

  const active    = entries.filter(e => e.status !== 'Complete').length
  const completed = entries.filter(e => e.status === 'Complete').length

  return (
    <div className="section">
      <div className="hero">
        <div className="hero-eyebrow">School Deadlines</div>
        <div className="hero-value">{upcoming} due soon</div>
        <div className="hero-sub">
          <div><span>{active}</span> active assignments</div>
          <div><span>{completed}</span> completed</div>
        </div>
      </div>

      <div className="panel">
        <div className="panel-header">
          Deadlines
          <span className="count">{entries.length}</span>
        </div>
        <table>
          {entries.length > 0 && (
            <thead>
              <tr>
                <th>Assignment</th><th>Course</th><th>Due Date</th><th>Status</th><th>Notes</th>
              </tr>
            </thead>
          )}
          <tbody>
            {entries.length === 0 ? (
              <tr>
                <td colSpan={5} className="empty-state">
                  No school entries — run <code>python main.py</code> to sync from Gmail
                </td>
              </tr>
            ) : entries.map((e, i) => {
              const diff    = e.due_date ? Math.round((new Date(e.due_date) - new Date(today)) / 86400000) : null
              const overdue = diff !== null && diff < 0 && e.status !== 'Complete'
              const c       = STATUS_COLOR[e.status] ?? '#666666'
              return (
                <tr key={i} className={overdue ? 'urgent' : ''}>
                  <td style={{ fontWeight: 600 }}>{e.assignment}</td>
                  <td><span className="tag">{e.course ?? '—'}</span></td>
                  <td className="mono" style={{ color: overdue ? '#f85149' : 'var(--muted)' }}>{relDate(e.due_date)}</td>
                  <td><Badge text={e.status} color={c} /></td>
                  <td style={{ color: 'var(--muted)', fontSize: 12 }}>
                    {e.notes ? e.notes.substring(0, 60) + (e.notes.length > 60 ? '…' : '') : '—'}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
