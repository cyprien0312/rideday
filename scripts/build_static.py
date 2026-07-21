"""Build a static snapshot of the dashboard for GitHub Pages.

Scrapes all providers live, renders templates/index.html in static mode (no
backend, no refresh button, data baked in), and writes a self-contained site to
dist/. Used by .github/workflows/deploy.yml on a schedule.

Run locally:  .venv/bin/python scripts/build_static.py
Output:       dist/index.html  +  dist/static/*
"""
from __future__ import annotations

import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

from lib.registry import PROVIDERS  # noqa: E402
from lib.scrape import run_all  # noqa: E402
from lib.store import Store  # noqa: E402


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
        events = store.upcoming_events()
        runs = store.latest_runs()

    ok = sum(1 for r in runs.values() if r.ok)
    print(f"scraped: {ok}/{len(PROVIDERS)} providers ok, {len(events)} upcoming events")
    for key, r in runs.items():
        print(f"  {key:16} ok={r.ok} count={r.event_count} err={r.error}")

    if not events:  # nothing to publish -> fail the build, keep the old Pages copy
        print("ERROR: 0 events across all providers — refusing to publish an empty page")
        return 1

    env = Environment(
        loader=FileSystemLoader(str(BASE / "templates")),
        autoescape=select_autoescape(["html"]),
    )
    html = env.get_template("index.html").render(
        events=events,
        runs=runs,
        provider_names={p.key: p.name for p in PROVIDERS},
        asset_base="static",       # relative -> works under the /rideday/ Pages subpath
        static_mode=True,
        generated_at=_now_sydney(),
    )
    (dist / "index.html").write_text(html, encoding="utf-8")
    shutil.copytree(BASE / "static", dist / "static")
    (dist / ".nojekyll").write_text("", encoding="utf-8")
    print(f"wrote {dist/'index.html'} ({len(html)} bytes) + static assets")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
