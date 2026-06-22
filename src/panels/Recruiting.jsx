import { useState } from 'react'
import { fmt } from '../lib/fmt'

function Badge({ text, color }) {
  return (
    <span
      className="badge"
      style={{ background: color + '22', color, border: `1px solid ${color}44` }}
    >{text}</span>
  )
}

export default function Recruiting({ data }) {
  const { entries = [], stats = {}, stage_colors: colors = {} } = data ?? {}
  const [activeStage, setActiveStage] = useState('All')
  const [editingKey, setEditingKey] = useState(null)
  const [editingValue, setEditingValue] = useState('')
  const [notes, setNotes] = useState(() => {
    const stored = {}
    entries.forEach(e => {
      const k = `note:${e.company}:${e.role}`
      const v = localStorage.getItem(k)
      if (v) stored[k] = v
    })
    return stored
  })

  const byStage = stats.by_stage ?? {}
  const active  = stats.active ?? entries.length

  const subParts = Object.entries(byStage)
    .filter(([, v]) => v > 0)
    .map(([s, v]) => (
      <span key={s} style={{ color: colors[s] ?? '#666666' }}>{v} {s}</span>
    ))

  const stagesToShow = ['Applied', 'Phone Screen', 'OA', 'Interview']
  const allStages    = ['All', ...Object.keys(byStage).filter(s => byStage[s] > 0)]

  const filtered = activeStage === 'All' ? entries : entries.filter(e => e.stage === activeStage)

  function getNote(e) {
    return notes[`note:${e.company}:${e.role}`] ?? e.notes ?? ''
  }

  function saveNote(e, value) {
    const k = `note:${e.company}:${e.role}`
    if (value.trim()) {
      localStorage.setItem(k, value.trim())
      setNotes(prev => ({ ...prev, [k]: value.trim() }))
    } else {
      localStorage.removeItem(k)
      setNotes(prev => { const n = { ...prev }; delete n[k]; return n })
    }
  }

  return (
    <div className="section">
      <div className="hero">
        <div className="hero-eyebrow">Recruiting Pipeline</div>
        <div className="hero-value">{active} active</div>
        <div className="hero-sub">
          {subParts.map((el, i) => (
            <span key={i}>
              {el}
              {i < subParts.length - 1 && <span style={{ color: '#3d444d', margin: '0 4px' }}>·</span>}
            </span>
          ))}
        </div>
      </div>

      <div className="grid-4">
        {stagesToShow.map(s => {
          const c = colors[s] ?? '#666666'
          const subs = { Applied: 'awaiting response', 'Phone Screen': 'in progress', OA: 'pending', Interview: 'scheduled' }
          return (
            <div className="stat-card" key={s} style={{ borderTop: `2px solid ${c}22` }}>
              <div className="stat-label" style={{ color: c }}>{s}</div>
              <div className="stat-value">{byStage[s] ?? 0}</div>
              <div className="stat-sub">{subs[s]}</div>
            </div>
          )
        })}
      </div>

      <div className="stage-filters">
        {allStages.map(s => {
          const isActive = s === activeStage
          const c = s === 'All' ? '#ffffff' : (colors[s] ?? '#666666')
          return (
            <button
              key={s}
              className={`stage-btn${isActive ? ' active' : ''}`}
              style={isActive ? { background: c, color: '#000', borderColor: c } : {}}
              onClick={() => setActiveStage(s)}
            >
              {s === 'All' ? `All (${entries.length})` : `${s} (${byStage[s]})`}
            </button>
          )
        })}
      </div>

      <div className="panel">
        <div className="panel-header">
          All Applications
          <span className="count">{filtered.length}</span>
        </div>
        <table>
          {filtered.length > 0 && (
            <thead>
              <tr>
                <th>Company</th><th>Role</th><th>Stage</th><th>Last Contact</th><th>Notes</th>
              </tr>
            </thead>
          )}
          <tbody>
            {filtered.length === 0 ? (
              <tr>
                <td colSpan={5} style={{ padding: '40px', textAlign: 'center', color: 'var(--muted)' }}>
                  {entries.length === 0
                    ? <>No entries — run <code style={{ color: 'var(--muted)' }}>python main.py</code> to sync from Gmail</>
                    : 'No entries for this stage'}
                </td>
              </tr>
            ) : filtered.map(e => {
              const c      = colors[e.stage] ?? '#666666'
              const noteKey = `note:${e.company}:${e.role}`
              const note    = getNote(e)
              return (
                <tr key={e.id ?? noteKey}>
                  <td style={{ fontWeight: 700 }}>{e.company}</td>
                  <td style={{ color: 'var(--muted)' }}>{e.role ?? '—'}</td>
                  <td><Badge text={e.stage} color={c} /></td>
                  <td className="mono" style={{ color: 'var(--muted)' }}>{e.last_contact ?? '—'}</td>
                  <td>
                    {editingKey === noteKey ? (
                      <input
                        autoFocus
                        value={editingValue}
                        onChange={ev => setEditingValue(ev.target.value)}
                        onBlur={() => { saveNote(e, editingValue); setEditingKey(null) }}
                        onKeyDown={ev => { if (ev.key === 'Enter') ev.target.blur() }}
                        style={{ background: 'transparent', border: 'none', borderBottom: '1px solid var(--border2)', color: 'var(--text)', fontSize: 12, width: '100%', outline: 'none' }}
                      />
                    ) : (
                      <span
                        style={{ color: 'var(--muted)', fontSize: 12, cursor: 'pointer' }}
                        title="Click to edit"
                        onClick={() => { setEditingKey(noteKey); setEditingValue(note) }}
                      >{note || '—'}</span>
                    )}
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
