"""Fetch every track location's forecast into the store.

Mirrors scrape.run_all: one location failing never blocks the others, and a
failed location keeps whatever rows it already had. Recorded as a single
scrape_runs entry under provider="weather" so the dashboard LED strip shows it.
"""
from __future__ import annotations

import logging
from datetime import datetime

from lib.store import Store
from lib.weather.forecast import fetch_forecast
from lib.weather.locations import LOCATIONS

log = logging.getLogger("rideday.weather")
RUN_KEY = "weather"


def refresh_weather(store: Store, locations=None, fetch=fetch_forecast) -> None:
    locations = locations if locations is not None else LOCATIONS
    started = datetime.now().isoformat(timespec="seconds")
    rows, errors = [], []
    for loc in locations:
        try:
            got = fetch(loc)
            if not got:
                raise ValueError("0 days parsed (possible API change)")
            rows.extend(got)
            log.info("weather %s: %d days", loc.key, len(got))
        except Exception as exc:  # isolate per location
            errors.append(f"{loc.key}: {exc}")
            log.warning("weather failed %s: %s", loc.key, exc)
    if rows:
        store.upsert_forecasts(rows)
    ok_count = len(locations) - len(errors)
    store.record_run(RUN_KEY, ok=not errors, event_count=ok_count,
                     error="; ".join(errors) or None, started_at=started)
