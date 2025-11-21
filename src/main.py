#!/usr/bin/env python3
# RSS-only version for LegiScan feeds; last 24h window; MA-friendly title
import os, sys, feedparser
from datetime import datetime, timedelta, timezone
from dateutil import tz
import yaml

WINDOW_HOURS = int(os.environ.get("WINDOW_HOURS", "24"))

def iso_boston(dt_utc):
    return dt_utc.astimezone(tz.gettz("America/New_York")).strftime("%Y-%m-%d %H:%M")

def parse_dt(entry):
    # Prefer published/updated; fall back to structured parsed values
    for k in ("published", "updated", "created"):
        if k in entry:
            try:
                return datetime.fromisoformat(str(entry[k]))
            except Exception:
                pass
    if getattr(entry, "published_parsed", None):
        return datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
    if getattr(entry, "updated_parsed", None):
        return datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)
    return None

def load_feeds(path="src/feeds.yaml"):
    with open(path, "r") as f:
        data = yaml.safe_load(f) or {}
    return data.get("rss", [])

def main():
    now = datetime.now(timezone.utc)
    since = now - timedelta(hours=WINDOW_HOURS)

    urls = load_feeds()
    if not urls:
        print("[WARN] No RSS URLs configured in src/feeds.yaml")
        sys.exit(0)

    items = []
    for url in urls:
        fp = feedparser.parse(url)
        source = (fp.feed.get("title") or url).strip() if getattr(fp, "feed", None) else url
        for e in fp.entries:
            dt = parse_dt(e)
            if not dt:
                continue
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            dt_utc = dt.astimezone(timezone.utc)
            if dt_utc < since:
                continue

            title = (e.get("title") or "").strip() or "(no title)"
            link = (e.get("link") or "").strip()

            # Optional: only keep things that look like bill introductions.
            # If your LegiScan feed already scopes to "introduced", you can remove this filter.
            text_for_filter = f"{title} {(e.get('summary') or '')}".lower()
            keep = ("introduc" in text_for_filter) or True  # keep all by default
            if not keep:
                continue

            items.append({
                "when": dt_utc,
                "title": title,
                "link": link,
                "source": source
            })

    items.sort(key=lambda x: x["when"], reverse=True)

    date_title = datetime.now(tz=tz.gettz("America/New_York")).strftime("%Y-%m-%d")
    lines = [f"# Massachusetts Bills Introduced — {date_title}", ""]
    if not items:
        lines.append("> No new items found in the last 24 hours.")
    else:
        for it in items:
            lines.append(f"- **{iso_boston(it['when'])}** — [{it['title']}]({it['link']})  _{it['source']}_")
    lines.append("")

    os.makedirs("reports", exist_ok=True)
    out_path = f"reports/{date_title}.md"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Wrote {out_path} with {len(items)} items.")

if __name__ == "__main__":
    main()
