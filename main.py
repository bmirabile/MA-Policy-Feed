#!/usr/bin/env python3
import argparse, os, sys, json, hashlib, requests, feedparser, yaml
from datetime import datetime, timedelta, timezone
from dateutil import parser as dtparse
from icalendar import Calendar
from io import BytesIO

NY_TZ = "America/New_York"

def now_utc():
    return datetime.now(timezone.utc)

def to_dt(obj):
    if isinstance(obj, datetime):
        return obj
    return dtparse.parse(str(obj))

def iso_ny(dt):
    # Render in America/New_York without external tz packages (use offset conversion from UTC)
    # Assumes dt is timezone-aware
    try:
        # Fallback: convert via fixed offsets using localize from zoneinfo (Python 3.9+)
        from zoneinfo import ZoneInfo
        return dt.astimezone(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %H:%M")
    except Exception:
        # If zoneinfo not available, display in UTC as fallback
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

def within_window(dt_obj, since_dt):
    return dt_obj >= since_dt

def fetch_rss(url):
    fp = feedparser.parse(url)
    items = []
    for e in fp.entries:
        # Pick the best available timestamp
        dt_candidate = None
        for key in ("published", "updated", "created"):
            if key in e:
                try:
                    dt_candidate = to_dt(e[key])
                    break
                except Exception:
                    pass
        if not dt_candidate and "published_parsed" in e and e.published_parsed:
            dt_candidate = datetime(*e.published_parsed[:6], tzinfo=timezone.utc)
        if not dt_candidate:
            # Skip undated
            continue
        title = e.get("title", "").strip() or "(untitled)"
        link = e.get("link", "").strip() or ""
        source = (fp.feed.get("title") or url).strip()
        items.append({
            "type": "rss",
            "source": source,
            "title": title,
            "link": link,
            "dt": to_dt(dt_candidate).astimezone(timezone.utc).isoformat(),
        })
    return items

def fetch_ics(url):
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    cal = Calendar.from_ical(resp.content)
    items = []
    for comp in cal.walk():
        if comp.name != "VEVENT":
            continue
        summary = str(comp.get("summary", "(no title)"))
        # Prefer DTSTART; some events have DTEND only
        dtstart = comp.get("dtstart")
        if not dtstart:
            continue
        dt = dtstart.dt
        # Normalize to aware datetime in UTC
        if isinstance(dt, datetime):
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            dt_utc = dt.astimezone(timezone.utc)
        else:
            # date-only, set noon to avoid timezone ambiguity
            dt_utc = datetime(dt.year, dt.month, dt.day, 12, 0, tzinfo=timezone.utc)
        url_field = comp.get("url")
        link = str(url_field) if url_field else ""
        organizer = str(comp.get("organizer", ""))
        items.append({
            "type": "ics",
            "source": url,
            "title": summary,
            "link": link,
            "dt": dt_utc.isoformat(),
        })
    return items

def load_feeds(path):
    with open(path, "r") as f:
        data = yaml.safe_load(f) or {}
    return data.get("rss", []), data.get("ics", [])

def render_markdown(items, report_date_str):
    rss_items = [i for i in items if i["type"]=="rss"]
    ics_items = [i for i in items if i["type"]=="ics"]
    lines = []
    lines.append(f"# Massachusetts Policy Feed — {report_date_str}")
    lines.append("")
    if rss_items:
        lines.append("## Press Releases (last 24h)")
        lines.append("")
        for it in sorted(rss_items, key=lambda x: x["dt"], reverse=True):
            dt_local = iso_ny(datetime.fromisoformat(it["dt"]))
            title = it["title"].replace("\n", " ").strip()
            src = it["source"]
            link = it["link"]
            bullet = f"- **{dt_local}** — [{title}]({link})  _{src}_"
            lines.append(bullet)
        lines.append("")
    else:
        lines.append("## Press Releases")
        lines.append("> No new items in the last 24 hours.")
        lines.append("")
    if ics_items:
        lines.append("## Hearings & Meetings (last 24h window start times)")
        lines.append("")
        for it in sorted(ics_items, key=lambda x: x["dt"], reverse=True):
            dt_local = iso_ny(datetime.fromisoformat(it["dt"]))
            title = it["title"].replace("\n", " ").strip()
            src = it["source"]
            link = it["link"]
            if link:
                bullet = f"- **{dt_local}** — [{title}]({link})  _{src}_"
            else:
                bullet = f"- **{dt_local}** — {title}  _{src}_"
            lines.append(bullet)
        lines.append("")
    else:
        lines.append("## Hearings & Meetings")
        lines.append("> No events starting in the last 24 hours.")
        lines.append("")
    return "\n".join(lines)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--feeds", default="src/feeds.yaml")
    ap.add_argument("--since", default="24h", help='Time window, e.g. "24h", "7d"')
    ap.add_argument("--reports-dir", default="reports")
    args = ap.parse_args()

    # Parse the since window
    now = now_utc()
    since = now - timedelta(hours=int(args.since[:-1])) if args.since.endswith("h") else now - timedelta(days=int(args.since[:-1]))
    rss_urls, ics_urls = load_feeds(args.feeds)

    all_items = []
    for url in rss_urls:
        try:
            for it in fetch_rss(url):
                dt = datetime.fromisoformat(it["dt"])
                if within_window(dt, since):
                    all_items.append(it)
        except Exception as e:
            print(f"[WARN] RSS fetch failed: {url}: {e}", file=sys.stderr)

    for url in ics_urls:
        try:
            for it in fetch_ics(url):
                dt = datetime.fromisoformat(it["dt"])
                if within_window(dt, since):
                    all_items.append(it)
        except Exception as e:
            print(f"[WARN] ICS fetch failed: {url}: {e}", file=sys.stderr)

    report_date_str = datetime.now().strftime("%Y-%m-%d")
    md = render_markdown(all_items, report_date_str)

    os.makedirs(args.reports_dir, exist_ok=True)
    out_path = os.path.join(args.reports_dir, f"{report_date_str}.md")
    with open(out_path, "w") as f:
        f.write(md)
    print(f"Wrote {out_path} with {len(all_items)} items.")

if __name__ == "__main__":
    main()
