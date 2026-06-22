import { useState, useEffect } from 'react'
import Finance from './panels/Finance'
import Recruiting from './panels/Recruiting'
import School from './panels/School'
import Health from './panels/Health'

const TABS = ['Finance', 'Recruiting', 'School', 'Health']

export default function App() {
  const [tab, setTab] = useState('Finance')
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    fetch('/data/dashboard.json')
      .then(r => { if (!r.ok) throw new Error(r.status); return r.json() })
      .then(setData)
      .catch(e => setError(e.message))
  }, [])

  return (
    <>
      <nav className="topnav">
        <div className="logo"><span>K.</span> Hill</div>
        {TABS.map(t => (
          <button
            key={t}
            className={`nav-tab${tab === t ? ' active' : ''}`}
            onClick={() => setTab(t)}
          >{t}</button>
        ))}
        <div className="nav-right">SNAPSHOT // {data?.updated ?? '—'}</div>
      </nav>

      {!data && !error && (
        <div style={{ padding: '80px 32px', textAlign: 'center', color: 'var(--muted)' }}>
          Loading...
        </div>
      )}
      {error && (
        <div style={{ padding: '80px 32px', textAlign: 'center', color: 'var(--muted)' }}>
          <div>Could not load dashboard data.</div>
          <code style={{ display: 'block', marginTop: 12, color: 'var(--muted)', fontSize: 11 }}>
            Run: python site_generator.py
          </code>
        </div>
      )}
      {data && tab === 'Finance'    && <Finance    data={data.finance} />}
      {data && tab === 'Recruiting' && <Recruiting data={data.recruiting} />}
      {data && tab === 'School'     && <School     data={data.school} />}
      {data && tab === 'Health'     && <Health     data={data.health} />}
    </>
  )
}
