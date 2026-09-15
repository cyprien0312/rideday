from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from lib.models import Event, Status
from lib.weather.forecast import DailyForecast


@dataclass
class RunInfo:
    provider: str
    ok: bool
    event_count: int
    error: str | None
    finished_at: datetime


SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
  event_uid TEXT PRIMARY KEY, provider TEXT, provider_name TEXT, title TEXT,
  track TEXT, state TEXT, date_start TEXT, date_end TEXT, start_time TEXT,
  price_aud REAL, price_display TEXT, status TEXT, status_raw TEXT, url TEXT,
  first_seen TEXT, last_seen TEXT
);
CREATE TABLE IF NOT EXISTS scrape_runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT, provider TEXT, started_at TEXT,
  finished_at TEXT, ok INTEGER, event_count INTEGER, error TEXT
);
CREATE TABLE IF NOT EXISTS forecasts (
  location_key TEXT, day TEXT, code INTEGER, tmin REAL, tmax REAL,
  rain_mm REAL, rain_prob INTEGER, wind_kmh REAL, fetched_at TEXT,
  PRIMARY KEY (location_key, day)
);
"""


class Store:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as c:
            c.executescript(SCHEMA)

    def _conn(self):
        c = sqlite3.connect(self.path)
        c.row_factory = sqlite3.Row
        return c

    def upsert_events(self, events: list[Event]) -> None:
        now = datetime.now().isoformat(timespec="seconds")
        with self._conn() as c:
            for e in events:
                existing = c.execute("SELECT first_seen FROM events WHERE event_uid=?",
                                     (e.event_uid,)).fetchone()
                first_seen = existing["first_seen"] if existing else now
                c.execute("""
                  INSERT INTO events (event_uid, provider, provider_name, title, track,
                    state, date_start, date_end, start_time, price_aud, price_display,
                    status, status_raw, url, first_seen, last_seen)
                  VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                  ON CONFLICT(event_uid) DO UPDATE SET
                    provider_name=excluded.provider_name, title=excluded.title,
                    track=excluded.track, state=excluded.state,
                    date_start=excluded.date_start, date_end=excluded.date_end,
                    start_time=excluded.start_time, price_aud=excluded.price_aud,
                    price_display=excluded.price_display, status=excluded.status,
                    status_raw=excluded.status_raw, url=excluded.url,
                    last_seen=excluded.last_seen
                """, (e.event_uid, e.provider, e.provider_name, e.title, e.track,
                      e.state, e.date_start.isoformat(),
                      e.date_end.isoformat() if e.date_end else None, e.start_time,
                      e.price_aud, e.price_display, e.status.value, e.status_raw,
                      e.url, first_seen, now))

    def upcoming_events(self) -> list[Event]:
        today = date.today().isoformat()
        with self._conn() as c:
            rows = c.execute(
                "SELECT * FROM events WHERE date_start>=? ORDER BY date_start",
                (today,)).fetchall()
        return [self._row_to_event(r) for r in rows]

    def record_run(self, provider, *, ok, event_count, error, started_at=None) -> None:
        now = datetime.now().isoformat(timespec="seconds")
        with self._conn() as c:
            c.execute("""INSERT INTO scrape_runs
              (provider, started_at, finished_at, ok, event_count, error)
              VALUES (?,?,?,?,?,?)""",
              (provider, started_at or now, now, 1 if ok else 0, event_count, error))

    def latest_runs(self) -> dict[str, RunInfo]:
        with self._conn() as c:
            rows = c.execute("""SELECT r.* FROM scrape_runs r JOIN
              (SELECT provider, MAX(id) mid FROM scrape_runs GROUP BY provider) x
              ON r.id=x.mid""").fetchall()
        return {r["provider"]: RunInfo(r["provider"], bool(r["ok"]), r["event_count"],
                r["error"], datetime.fromisoformat(r["finished_at"])) for r in rows}

    def upsert_forecasts(self, rows: list[DailyForecast]) -> None:
        """Upsert forecast rows (other locations untouched); purge days before today."""
        now = datetime.now().isoformat(timespec="seconds")
        today = date.today()
        with self._conn() as c:
            c.execute("DELETE FROM forecasts WHERE day < ?", (today.isoformat(),))
            for r in rows:
                if r.day < today:
                    continue
                c.execute("""
                  INSERT INTO forecasts (location_key, day, code, tmin, tmax, rain_mm,
                    rain_prob, wind_kmh, fetched_at)
                  VALUES (?,?,?,?,?,?,?,?,?)
                  ON CONFLICT(location_key, day) DO UPDATE SET
                    code=excluded.code, tmin=excluded.tmin, tmax=excluded.tmax,
                    rain_mm=excluded.rain_mm, rain_prob=excluded.rain_prob,
                    wind_kmh=excluded.wind_kmh, fetched_at=excluded.fetched_at
                """, (r.location_key, r.day.isoformat(), r.code, r.tmin, r.tmax,
                      r.rain_mm, r.rain_prob, r.wind_kmh, now))

    def forecasts(self) -> dict[tuple[str, date], DailyForecast]:
        with self._conn() as c:
            rows = c.execute("SELECT * FROM forecasts").fetchall()
        out = {}
        for r in rows:
            d = date.fromisoformat(r["day"])
            out[(r["location_key"], d)] = DailyForecast(
                location_key=r["location_key"], day=d, code=r["code"],
                tmin=r["tmin"], tmax=r["tmax"], rain_mm=r["rain_mm"],
                rain_prob=r["rain_prob"], wind_kmh=r["wind_kmh"])
        return out

    @staticmethod
    def _row_to_event(r) -> Event:
        e = Event(provider=r["provider"], provider_name=r["provider_name"], title=r["title"],
                  track=r["track"], date_start=date.fromisoformat(r["date_start"]),
                  price_display=r["price_display"], url=r["url"], state=r["state"],
                  date_end=date.fromisoformat(r["date_end"]) if r["date_end"] else None,
                  start_time=r["start_time"], price_aud=r["price_aud"],
                  status=Status(r["status"]), status_raw=r["status_raw"])
        e.first_seen = datetime.fromisoformat(r["first_seen"])
        e.last_seen = datetime.fromisoformat(r["last_seen"])
        return e
