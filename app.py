from __future__ import annotations

import os
import threading
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

from lib.ics import build_feeds, render_feed
from lib.registry import PROVIDERS
from lib.scrape import run_all
from lib.store import Store
from lib.weather.attach import weather_map
from lib.weather.normals import load_normals
from lib.weather.refresh import RUN_KEY, refresh_weather

BASE = Path(__file__).parent
templates = Jinja2Templates(directory=str(BASE / "templates"))
_refresh_lock = threading.Lock()


def _event_json(e) -> dict:
    return {
        "provider": e.provider, "provider_name": e.provider_name, "title": e.title,
        "track": e.track, "state": e.state, "date_start": e.date_start.isoformat(),
        "date_end": e.date_end.isoformat() if e.date_end else None,
        "start_time": e.start_time, "price_aud": e.price_aud,
        "price_display": e.price_display, "status": e.status.value,
        "status_raw": e.status_raw, "url": e.url,
    }


def _weather_json(w) -> dict | None:
    return None if w is None else asdict(w)  # raw fields only; display strings are properties


def create_app() -> FastAPI:
    app = FastAPI(title="rideday-radar")
    app.mount("/static", StaticFiles(directory=str(BASE / "static")), name="static")
    store = Store(os.environ.get("RIDEDAY_DB", str(BASE / "data" / "events.db")))
    app.state.store = store

    def do_refresh() -> bool:
        """Scrape all providers, then refresh weather. Skips if a refresh is already running."""
        if not _refresh_lock.acquire(blocking=False):
            return False
        try:
            run_all(store, providers=PROVIDERS)
            refresh_weather(store)
            return True
        finally:
            _refresh_lock.release()

    app.state.do_refresh = do_refresh

    def _weather(events):
        return weather_map(events, store.forecasts(), load_normals())

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request):
        events = store.upcoming_events()
        return templates.TemplateResponse(request, "index.html", {
            "events": events,
            "runs": store.latest_runs(),
            "provider_names": {**{p.key: p.name for p in PROVIDERS}, RUN_KEY: "Open-Meteo"},
            "weather": _weather(events),
            "asset_base": "/static",
            "static_mode": False,
            "feeds": [{"slug": f.slug, "label": f.label, "count": len(f.events),
                       "href": f"/calendar/{f.filename}"} for f in build_feeds(events)],
        })

    @app.get("/api/events")
    def api_events():
        events = store.upcoming_events()
        weather = _weather(events)
        return JSONResponse([{**_event_json(e), "weather": _weather_json(weather.get(e.event_uid))}
                             for e in events])

    @app.api_route("/calendar/{slug}.ics", methods=["GET", "HEAD"])
    def calendar(slug: str):
        """Subscribable .ics per state (plus `all`) — same feeds the Pages build publishes."""
        feeds = {f.slug: f for f in build_feeds(store.upcoming_events())}
        feed = feeds.get(slug.lower())
        if feed is None:
            raise HTTPException(status_code=404, detail=f"no feed for {slug!r}")
        body = render_feed(feed, now=datetime.now(timezone.utc))
        return Response(body, media_type="text/calendar; charset=utf-8", headers={
            "Content-Disposition": f'inline; filename="rideday-{feed.filename}"'})

    @app.post("/api/refresh")
    def api_refresh():
        ran = do_refresh()
        return JSONResponse({"ok": True, "ran": ran})

    return app


app = create_app()


def _start_scheduler() -> None:
    interval = int(os.environ.get("RIDEDAY_INTERVAL_HOURS", "3"))
    sched = BackgroundScheduler()
    sched.add_job(app.state.do_refresh, "interval", hours=interval, id="scrape")
    sched.start()
    if not app.state.store.latest_runs():  # cold start: scrape once in the background
        threading.Thread(target=app.state.do_refresh, daemon=True).start()


if __name__ == "__main__":
    import uvicorn

    _start_scheduler()
    port = int(os.environ.get("RIDEDAY_PORT", "8765"))
    print(f"rideday-radar -> http://127.0.0.1:{port}")
    uvicorn.run(app, host="127.0.0.1", port=port)
