"""Build a static snapshot of the dashboard for GitHub Pages.

Scrapes all providers live, renders templates/index.html in static mode (no
backend, no refresh button, data baked in), writes one subscribable .ics per
state (plus all.ics), and puts the self-contained site in dist/. Used by
.github/workflows/deploy.yml on a schedule.

Run locally:  .venv/bin/python scripts/build_static.py
Output:       dist/index.html  +  dist/*.ics  +  dist/static/*
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

from lib.ics import build_feeds, render_feed  # noqa: E402
from lib.registry import PROVIDERS  # noqa: E402
from lib.scrape import run_all  # noqa: E402
from lib.store import Store  # noqa: E402
from lib.weather.attach import weather_map  # noqa: E402
from lib.weather.normals import load_normals  # noqa: E402
from lib.weather.refresh import refresh_weather  # noqa: E402

# Where the built site lives — calendar subscriptions need absolute URLs.
SITE_URL = os.environ.get("RIDEDAY_BASE_URL", "https://cyprien0312.github.io/rideday").rstrip("/")


def _now_sydney() -> str:
    try:
        from zoneinfo import ZoneInfo
        now = datetime.now(ZoneInfo("Australia/Sydney"))
        return now.strftime("%Y-%m-%d %H:%M AEST/AEDT")
    except Exception:  # tzdata missing (rare) -> fall back to UTC
        return datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")


def main() -> int:
    dist = BASE / "dist"
    if dist.exists():
        shutil.rmtree(dist)
    dist.mkdir(parents=True)

    # Scrape into a throwaway DB (run_all isolates per-provider failures).
    with tempfile.TemporaryDirectory() as tmp:
        store = Store(Path(tmp) / "build.db")
        run_all(store, providers=PROVIDERS)
        refresh_weather(store)
        events = store.upcoming_events()
        runs = store.latest_runs()
        weather = weather_map(events, store.forecasts(), load_normals())

    provider_runs = {p.key: runs.get(p.key) for p in PROVIDERS}
    ok = sum(1 for r in provider_runs.values() if r and r.ok)
    print(f"scraped: {ok}/{len(PROVIDERS)} providers ok, {len(events)} upcoming events")
    for key, r in provider_runs.items():
        if r:
            print(f"  {key:16} ok={r.ok} count={r.event_count} err={r.error}")
    wr = runs.get("weather")
    print(f"weather: ok={wr.ok if wr else None} locations={wr.event_count if wr else 0} "
          f"err={wr.error if wr else None}; {len(weather)} events have weather")

    if not events:  # nothing to publish -> fail the build, keep the old Pages copy
        print("ERROR: 0 events across all providers — refusing to publish an empty page")
        return 1

    # Calendar feeds: webcal:// so a click subscribes instead of downloading a copy.
    feeds = build_feeds(events)
    now = datetime.now(timezone.utc)
    webcal_base = SITE_URL.split("://", 1)[-1]
    for feed in feeds:
        (dist / feed.filename).write_text(render_feed(feed, now=now), encoding="utf-8")
    print(f"wrote {len(feeds)} calendar feeds: "
          + ", ".join(f"{f.filename}({len(f.events)})" for f in feeds))

    env = Environment(
        loader=FileSystemLoader(str(BASE / "templates")),
        autoescape=select_autoescape(["html"]),
    )
    html = env.get_template("index.html").render(
        events=events,
        runs=runs,
        provider_names={**{p.key: p.name for p in PROVIDERS}, "weather": "Open-Meteo"},
        weather=weather,
        asset_base="static",       # relative -> works under the /rideday/ Pages subpath
        static_mode=True,
        generated_at=_now_sydney(),
        feeds=[{"slug": f.slug, "label": f.label, "count": len(f.events),
                "href": f"webcal://{webcal_base}/{f.filename}"} for f in feeds],
    )
    (dist / "index.html").write_text(html, encoding="utf-8")
    shutil.copytree(BASE / "static", dist / "static")
    (dist / ".nojekyll").write_text("", encoding="utf-8")
    print(f"wrote {dist/'index.html'} ({len(html)} bytes) + static assets")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
