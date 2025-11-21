# MA Policy Feed — Daily Press Releases & Hearings Digest

This repo fetches **RSS/Atom press releases** and **ICS hearing calendars** (where permitted), normalizes the last 24 hours of items, and writes a dated Markdown report in `reports/`.
It runs automatically every morning via **GitHub Actions**.

> ⚠️ Respect each site’s Terms and robots.txt. Only add feeds/ICS that explicitly allow automated access. No HTML scraping—RSS/ICS only.

## Quick start

1. **Create a new public GitHub repo** and copy this project into it.
2. Edit `src/feeds.yaml` and paste the RSS/Atom and ICS URLs you want to monitor (examples included as placeholders).
3. Commit and push.
4. The workflow in `.github/workflows/daily.yml` runs daily and commits `reports/YYYY-MM-DD.md`.

### Local test
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python src/main.py --since "24h"
```

### Add/adjust feeds
Edit `src/feeds.yaml`:

```yaml
rss:
  - "https://example.com/press.rss"     # Replace with real RSS/Atom feeds
ics:
  - "https://example.com/hearings.ics"  # Replace with real ICS calendars
```

### Output
- One Markdown file per day in `reports/`
- Sections: **Press Releases** (RSS/Atom) and **Hearings** (ICS)
- Each entry: time (America/New_York), title, source, and link

## Notes
- Timezone: America/New_York
- Window: last 24 hours by default (configurable via `--since`).
- No scraping of HTML pages. If a site lacks RSS/ICS, don’t add it.
