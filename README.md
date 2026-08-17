# Life OS

A personal dashboard that scrapes your Gmail for signals about your own life — recruiting pipeline, school deadlines, health tracking, finances — and presents them in a clean React UI deployed on Vercel.

Built as a personal tool, open-sourced as a template. The panels shown here reflect one person's interests (recruiting, school, health). Fork it and swap in whatever matters to you.

![Dashboard preview](public/data/dashboard.json)

---

## How it works

```
Gmail (OAuth2)
  └─ gmail_scraper.py     fetch emails matching your queries
  └─ classifier.py        extract structured fields (company, stage, date, etc.)
  └─ json_writer.py       deduplicate and write to data/*.json
  └─ main.py              orchestrate all of the above

data/*.json
  └─ main.py (_merge_dashboard)   merge into public/data/dashboard.json

public/data/dashboard.json
  └─ vite build           inline as window.__DASHBOARD_DATA__ at build time
  └─ Vercel               serve as a fully static site
```

No database, no server, no runtime API calls. Everything is baked into the build.

---

## Setup

### 1. Clone and install

```bash
git clone https://github.com/your-username/life-os
cd life-os
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
npm install
```

### 2. Google OAuth credentials

You need a Google Cloud project with the Gmail API enabled.

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Create a project → Enable the Gmail API
3. Create an OAuth 2.0 Desktop client → download the JSON
4. Save it as `credentials.json` in the project root
5. (Optional) Repeat for a second Gmail account → save as `credentials_school.json`

On first run, a browser window will open for you to authorize. The token is cached as `token_personal.json` so subsequent runs are silent.

### 3. Configure your queries and keywords

Edit `config.py` to match what you want to track:

```python
# Gmail search queries — controls what emails get fetched
QUERIES = {
    'recruiting': 'subject:(interview OR offer OR application) newer_than:90d',
    'school':     'subject:(due OR deadline OR assignment) newer_than:30d',
}

# Keywords that signal a recruiting stage
STAGE_KEYWORDS = {
    'Offer':        ['offer', 'pleased to offer'],
    'Interview':    ['interview', 'meet with the team'],
    'Phone Screen': ['phone screen', 'introductory call'],
    ...
}

# Companies you're targeting — emails from these get boosted signal
TARGET_COMPANIES = ['stripe', 'figma', 'notion', ...]
```

### 4. Run

```bash
# Preview without writing anything
python main.py --dry-run

# Full scrape + rebuild dashboard
python main.py

# Only look at recent emails
python main.py --since 30

# One account only
python main.py --accounts personal
```

### 5. Local dev

```bash
npm run dev
```

Vite reads `public/data/dashboard.json` and serves the React app at `localhost:5173`.

---

## Deployment

Push to GitHub and connect to [Vercel](https://vercel.com). The build command is `vite build` — no environment variables needed for a basic deployment.

For a **auth-gated production deployment** (so your real data stays private):
1. Create a [Supabase](https://supabase.com) project
2. Add `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY` to Vercel environment variables
3. Create your user under Supabase → Authentication → Users

---

## Customizing panels

Each panel is a standalone React component in `src/panels/`. The dashboard JSON shape drives what's displayed.

**To add a new panel (e.g. "Fitness"):**

1. Add a section to `public/data/dashboard.json`:
```json
{
  "fitness": {
    "entries": [],
    "stats": {}
  }
}
```

2. Create `src/panels/Fitness.jsx` to render it

3. Add it to the tab list in `src/App.jsx`:
```jsx
const TABS = ['Finance', 'Recruiting', 'School', 'Health', 'Fitness']
```

4. Add a classifier in `classifier.py` that extracts fitness signals from your Gmail and writes to `data/fitness.json`

5. Add a merge step in `main.py`'s `_merge_dashboard()` to fold it into `public/data/dashboard.json`

**To remove a panel you don't need:** delete the tab from `TABS`, remove the component import in `App.jsx`, and skip the classifier entirely.

---

## Finance tracking

The finance panel is populated separately from a CSV export workflow rather than Gmail:

```bash
# Open all bank sites at once
python main.py --csv-open

# After downloading CSVs to ~/Downloads:
python main.py --csv
```

Supported out of the box: Capital One, Discover, Chase, Schwab, Fidelity. Add your own bank by editing `csv_scraper.py`.

---

## Data files

| File | Purpose |
|---|---|
| `data/recruiting.json` | Recruiting pipeline entries |
| `data/school.json` | School deadlines |
| `public/data/dashboard.json` | Generated — rebuilt on every run, do not edit directly |
| `credentials.json` | Google OAuth client *(gitignored)* |
| `token_personal.json` | Cached OAuth token *(gitignored)* |
| `financial_snapshot_*.json` | Finance snapshots *(gitignored)* |

---

## License

MIT
