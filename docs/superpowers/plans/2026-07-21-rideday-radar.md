# rideday-radar Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A local FastAPI web dashboard that aggregates Australian motorcycle ride-day events (date, track, state, price, ticket status, URL) from Champions Ride Days, Phillip Island (PIRD) and Sydney Motorsport Park (SMSP) into one sortable/filterable page, refreshed on a background schedule with a manual "refresh now" button.

**Architecture:** Per-site adapter (`fetch() -> list[Event]`) parses static HTML with requests + BeautifulSoup; results upserted into SQLite; APScheduler runs `scrape.run_all()` every 3h; FastAPI serves a Jinja2 page reading the cache plus a `POST /api/refresh` endpoint. Each adapter is isolated so one failing site never breaks the others. TDD against saved HTML fixtures.

**Tech Stack:** Python 3.12 · requests · beautifulsoup4 · lxml · tenacity · FastAPI · uvicorn · APScheduler · Jinja2 · stdlib sqlite3 · pytest · vanilla JS frontend.

---

## File Structure

- `requirements.txt`, `pyproject.toml`, `.gitignore` (done), `README.md`, `CLAUDE.md` — project meta
- `lib/models.py` — `Status` enum, `Event` dataclass, `event_uid()` helper
- `lib/store.py` — SQLite schema, `upsert_events()`, `upcoming_events()`, `record_run()`, `latest_runs()`
- `lib/providers/base.py` — `Provider` ABC (`key`, `name`, `fetch()`), shared HTTP `get_html()` helper
- `lib/providers/champions.py` / `phillip_island.py` / `smsp.py` — one adapter each
- `lib/registry.py` — `PROVIDERS` list
- `lib/scrape.py` — `run_all(store)` orchestration, per-provider isolation
- `app.py` — FastAPI app, routes, APScheduler startup
- `templates/index.html` — dashboard
- `static/app.js`, `static/style.css` — client-side sort/filter + refresh
- `tests/fixtures/*.html` — captured real listing pages
- `tests/test_models.py`, `test_store.py`, `test_champions.py`, `test_phillip_island.py`, `test_smsp.py`, `test_scrape.py`

---

### Task 0: Scaffold + dependencies

**Files:**
- Create: `requirements.txt`, `pyproject.toml`, `lib/__init__.py`, `lib/providers/__init__.py`, `tests/__init__.py`, `tests/fixtures/.gitkeep`

- [ ] **Step 1: Write `requirements.txt`**

```
requests>=2.32
beautifulsoup4>=4.12
lxml>=5.2
tenacity>=8.4
python-dateutil>=2.9
fastapi>=0.111
uvicorn>=0.30
apscheduler>=3.10
jinja2>=3.1
```

`requirements-dev.txt`:
```
pytest>=8.2
```

- [ ] **Step 2: Write `pyproject.toml`** (minimal, pytest config)

```toml
[project]
name = "rideday-radar"
version = "0.1.0"
requires-python = ">=3.12"

[tool.pytest.ini_options]
testpaths = ["tests"]
markers = ["live: hits real websites (deselect with -m 'not live')"]
addopts = "-m 'not live'"
```

- [ ] **Step 3: Create venv + install**

Run: `cd /Users/test/claudecode/rideday-radar && python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt -r requirements-dev.txt`
Expected: installs cleanly.

- [ ] **Step 4: Create empty package files** (`lib/__init__.py`, `lib/providers/__init__.py`, `tests/__init__.py`, `tests/fixtures/.gitkeep`).

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "chore: scaffold rideday-radar (deps, venv, package layout)"
```

---

### Task 1: Data model (`lib/models.py`)

**Files:**
- Create: `lib/models.py`
- Test: `tests/test_models.py`

- [ ] **Step 1: Write failing test**

```python
from datetime import date, datetime
from lib.models import Event, Status, event_uid

def test_event_uid_stable_from_provider_and_url():
    a = event_uid("champions", "https://x/product/1/")
    b = event_uid("champions", "https://x/product/1/")
    assert a == b and len(a) == 40  # sha1 hex

def test_event_uid_falls_back_to_date_track_when_no_url():
    uid = event_uid("smsp", "", date_start=date(2026, 7, 26), track="Sydney Motorsport Park")
    assert uid == event_uid("smsp", "", date_start=date(2026, 7, 26), track="Sydney Motorsport Park")

def test_event_defaults():
    e = Event(provider="smsp", provider_name="SMSP", title="Ride Day",
              track="Sydney Motorsport Park", date_start=date(2026, 7, 26),
              price_display="From $365", url="https://x/1")
    assert e.status is Status.UNKNOWN
    assert e.state is None and e.price_aud is None and e.date_end is None
    assert e.event_uid == event_uid("smsp", "https://x/1")
```

- [ ] **Step 2: Run test — expect FAIL** (`ImportError`).

Run: `.venv/bin/pytest tests/test_models.py -v`

- [ ] **Step 3: Implement `lib/models.py`**

```python
from __future__ import annotations
import hashlib
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum

class Status(str, Enum):
    OPEN = "open"
    FILLING_FAST = "filling_fast"
    SOLD_OUT = "sold_out"
    UNKNOWN = "unknown"

def event_uid(provider: str, url: str, *, date_start: date | None = None, track: str = "") -> str:
    basis = f"{provider}|{url}" if url else f"{provider}|{date_start}|{track}"
    return hashlib.sha1(basis.encode("utf-8")).hexdigest()

@dataclass
class Event:
    provider: str
    provider_name: str
    title: str
    track: str
    date_start: date
    price_display: str
    url: str
    state: str | None = None
    date_end: date | None = None
    start_time: str | None = None
    price_aud: float | None = None
    status: Status = Status.UNKNOWN
    status_raw: str | None = None
    first_seen: datetime | None = None
    last_seen: datetime | None = None
    event_uid: str = field(default="", init=False)

    def __post_init__(self):
        self.event_uid = event_uid(self.provider, self.url,
                                   date_start=self.date_start, track=self.track)
```

- [ ] **Step 4: Run test — expect PASS.**

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: Event model + Status enum + stable event_uid"`

---

### Task 2: Store (`lib/store.py`)

**Files:**
- Create: `lib/store.py`
- Test: `tests/test_store.py`

- [ ] **Step 1: Write failing test** (use in-memory-ish temp db via `tmp_path`)

```python
from datetime import date, timedelta
from lib.models import Event, Status
from lib.store import Store

def _ev(uid_url, d, price=200.0, provider="champions"):
    return Event(provider=provider, provider_name="C", title="RD", track="Broadford",
                 date_start=d, price_display=f"${price}", url=uid_url, price_aud=price,
                 status=Status.OPEN)

def test_upsert_then_upcoming(tmp_path):
    s = Store(tmp_path / "t.db")
    today = date.today()
    s.upsert_events([_ev("u1", today + timedelta(days=2)),
                     _ev("u2", today - timedelta(days=2))])  # past
    up = s.upcoming_events()
    assert [e.url for e in up] == ["u1"]  # past filtered out

def test_upsert_is_idempotent_and_keeps_first_seen(tmp_path):
    s = Store(tmp_path / "t.db")
    d = date.today() + timedelta(days=3)
    s.upsert_events([_ev("u1", d, price=200)])
    first = s.upcoming_events()[0].first_seen
    s.upsert_events([_ev("u1", d, price=250)])  # price changed
    row = s.upcoming_events()[0]
    assert row.first_seen == first          # preserved
    assert row.price_aud == 250             # updated
    assert row.last_seen >= first           # advanced

def test_record_and_latest_runs(tmp_path):
    s = Store(tmp_path / "t.db")
    s.record_run("champions", ok=True, event_count=8, error=None)
    s.record_run("smsp", ok=False, event_count=0, error="timeout")
    runs = s.latest_runs()
    assert runs["champions"].ok is True and runs["champions"].event_count == 8
    assert runs["smsp"].ok is False and runs["smsp"].error == "timeout"
```

- [ ] **Step 2: Run — expect FAIL.**

- [ ] **Step 3: Implement `lib/store.py`**

```python
from __future__ import annotations
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from lib.models import Event, Status

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
            rows = c.execute("SELECT * FROM events WHERE date_start>=? ORDER BY date_start",
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
```

- [ ] **Step 4: Run — expect PASS.**
- [ ] **Step 5: Commit** — `git commit -am "feat: SQLite store with upsert, upcoming query, run tracking"`

---

### Task 3: Provider base + registry

**Files:**
- Create: `lib/providers/base.py`, `lib/registry.py`

- [ ] **Step 1: Implement `lib/providers/base.py`** (ABC + shared polite HTTP getter)

```python
from __future__ import annotations
from abc import ABC, abstractmethod
import requests
from tenacity import retry, stop_after_attempt, wait_exponential
from lib.models import Event

UA = "rideday-radar/0.1 (personal ride-day aggregator; contact: local)"

class Provider(ABC):
    key: str
    name: str
    base_url: str

    @abstractmethod
    def fetch(self) -> list[Event]:
        ...

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8), reraise=True)
    def get_html(self, url: str) -> str:
        resp = requests.get(url, headers={"User-Agent": UA}, timeout=20)
        resp.raise_for_status()
        return resp.text

    @abstractmethod
    def parse(self, html: str) -> list[Event]:
        """Pure function html -> events. Tested against fixtures."""
        ...

    def fetch(self) -> list[Event]:  # noqa: F811  default impl
        return self.parse(self.get_html(self.base_url))
```

> Note: `fetch` default calls `get_html(base_url)` then `parse`. Adapters override `base_url` + `parse`. Keep `parse` pure so tests feed fixture HTML without network.

- [ ] **Step 2: Implement `lib/registry.py`** (import each adapter; filled in as adapters land)

```python
from lib.providers.champions import Champions
from lib.providers.phillip_island import PhillipIsland
from lib.providers.smsp import SMSP

PROVIDERS = [Champions(), PhillipIsland(), SMSP()]
```

> During execution, add imports to `registry.py` only after each adapter task completes so the module always imports. (Start `registry.py` with an empty `PROVIDERS = []` in this task, append per adapter.)

- [ ] **Step 3: Commit** — `git commit -am "feat: Provider ABC (pure parse + polite get_html) + empty registry"`

---

### Task 4: Capture real HTML fixtures

**Files:**
- Create: `tests/fixtures/champions_events.html`, `pird_ride_days.html`, `smsp_ride_days.html`
- Create: `scripts/capture_fixtures.py`

- [ ] **Step 1: Write `scripts/capture_fixtures.py`** — downloads each listing page to `tests/fixtures/` using the same UA/headers as `Provider.get_html`.

```python
import requests
from pathlib import Path
UA = "rideday-radar/0.1 (personal ride-day aggregator; contact: local)"
PAGES = {
    "champions_events.html": "https://championsridedays.com.au/events/",
    "pird_ride_days.html": "https://www.phillipislandridedays.com.au/pird-ride-days",
    "smsp_ride_days.html": "https://www.smsprd.com/smsprd-ride-days",
}
out = Path("tests/fixtures")
out.mkdir(parents=True, exist_ok=True)
for name, url in PAGES.items():
    html = requests.get(url, headers={"User-Agent": UA}, timeout=30).text
    (out / name).write_text(html, encoding="utf-8")
    print(name, len(html), "bytes")
```

- [ ] **Step 2: Run it** — `.venv/bin/python scripts/capture_fixtures.py`. Expected: three files written, each > 10 KB.

- [ ] **Step 3: Inspect structure** — for each fixture, identify the repeating event container and the child elements holding date / track / price / status / link. Record the CSS selectors in a comment block at the top of the matching adapter (Tasks 5-7). This is the step where the exact selectors get pinned; the parser code in Tasks 5-7 is written against what is actually in the fixture.

- [ ] **Step 4: Commit** — `git add -A && git commit -m "test: capture real HTML fixtures for the three ride-day sites"`

---

### Task 5: Champions adapter (`lib/providers/champions.py`)

**Files:**
- Create: `lib/providers/champions.py`
- Test: `tests/test_champions.py`
- Modify: `lib/registry.py` (append `Champions()`)

Champions is the richest source: WooCommerce product cards with an explicit status word (`Available` / `Filling Fast` / possibly `Sold Out`) and `date + track (STATE)` text.

- [ ] **Step 1: Write failing test against the fixture** — assert on a handful of known rows captured in Task 4 (fill exact expected values from the fixture during execution).

```python
from pathlib import Path
from lib.providers.champions import Champions
from lib.models import Status

HTML = Path("tests/fixtures/champions_events.html").read_text(encoding="utf-8")

def test_parses_events():
    events = Champions().parse(HTML)
    assert len(events) >= 5
    e = events[0]
    assert e.provider == "champions"
    assert e.track and e.date_start is not None
    assert e.url.startswith("https://championsridedays.com.au/")
    assert e.price_aud is not None

def test_status_mapping_and_state():
    events = Champions().parse(HTML)
    # at least one event carries a non-UNKNOWN status word from the listing
    assert any(e.status in (Status.OPEN, Status.FILLING_FAST, Status.SOLD_OUT) for e in events)
    # state parsed out of "Track (VIC)" style labels for at least some rows
    assert any(e.state for e in events)
```

- [ ] **Step 2: Run — expect FAIL** (ImportError).

- [ ] **Step 3: Implement adapter.** Skeleton below; the selectors marked `SELECTOR` are confirmed against the Task-4 fixture. Date parsing uses `dateutil` with a forward-looking year (ride-day listings show `26 Jul` without a year → assume the next occurrence ≥ today).

```python
from __future__ import annotations
import re
from datetime import date
from bs4 import BeautifulSoup
from dateutil import parser as dparser
from lib.models import Event, Status
from lib.providers.base import Provider

STATUS_MAP = {
    "sold out": Status.SOLD_OUT, "soldout": Status.SOLD_OUT,
    "filling fast": Status.FILLING_FAST, "selling fast": Status.FILLING_FAST,
    "available": Status.OPEN, "in stock": Status.OPEN, "book now": Status.OPEN,
}
STATE_RE = re.compile(r"\(([A-Z]{2,3})\)")

def _resolve_date(text: str) -> date | None:
    try:
        dt = dparser.parse(text, dayfirst=True, fuzzy=True, default=None)
    except (ValueError, OverflowError):
        return None
    d = dt.date()
    if d < date.today():
        try:
            d = d.replace(year=d.year + 1)
        except ValueError:
            pass
    return d

def _price(text: str) -> float | None:
    m = re.search(r"\$?\s*([\d,]+(?:\.\d{2})?)", text or "")
    return float(m.group(1).replace(",", "")) if m else None

def _status(text: str) -> tuple[Status, str | None]:
    t = (text or "").strip().lower()
    for key, val in STATUS_MAP.items():
        if key in t:
            return val, text.strip()
    return Status.UNKNOWN, (text.strip() or None)

class Champions(Provider):
    key = "champions"
    name = "Champions Ride Days"
    base_url = "https://championsridedays.com.au/events/"

    def parse(self, html: str) -> list[Event]:
        soup = BeautifulSoup(html, "lxml")
        events: list[Event] = []
        for card in soup.select("SELECTOR_CARD"):     # e.g. "li.product"
            link = card.select_one("SELECTOR_LINK")   # e.g. "a.woocommerce-LoopProduct-link"
            title_el = card.select_one("SELECTOR_TITLE")
            price_el = card.select_one("SELECTOR_PRICE")  # e.g. ".price"
            status_el = card.select_one("SELECTOR_STATUS")  # stock/badge; may be None
            if not (link and title_el):
                continue
            title = title_el.get_text(" ", strip=True)
            url = link.get("href", "")
            if url and not url.startswith("http"):
                url = "https://championsridedays.com.au" + url
            d = _resolve_date(title)  # date often in title text; refine per fixture
            if d is None:
                continue
            state_m = STATE_RE.search(title)
            status, status_raw = _status(status_el.get_text(" ", strip=True) if status_el else "")
            price_disp = price_el.get_text(" ", strip=True) if price_el else ""
            events.append(Event(
                provider=self.key, provider_name=self.name, title=title,
                track=re.sub(r"\d{1,2}\s+\w+", "", title).strip(" -") or title,
                date_start=d, price_display=price_disp, price_aud=_price(price_disp),
                url=url, state=state_m.group(1) if state_m else None,
                status=status, status_raw=status_raw))
        return events
```

> During execution, replace every `SELECTOR_*` with the real selector from the fixture, and adjust `track`/`date` extraction to where the fixture actually puts them (title vs a separate `.date` element). Tighten the test's expected values to concrete known rows once selectors are locked.

- [ ] **Step 4: Run — expect PASS.**
- [ ] **Step 5: Append `Champions()` to `lib/registry.py`.**
- [ ] **Step 6: Commit** — `git commit -am "feat: Champions Ride Days adapter (fixture-tested)"`

---

### Task 6: PIRD adapter (`lib/providers/phillip_island.py`)

**Files:**
- Create: `lib/providers/phillip_island.py`
- Test: `tests/test_phillip_island.py`
- Modify: `lib/registry.py`

Track is constant = `Phillip Island Grand Prix Circuit`, state = `VIC`. Listing has date + start_time + price; status best-effort → `UNKNOWN` unless a `sold out` word is present.

- [ ] **Step 1: Failing test**

```python
from pathlib import Path
from lib.providers.phillip_island import PhillipIsland
HTML = Path("tests/fixtures/pird_ride_days.html").read_text(encoding="utf-8")

def test_parses_pird():
    events = PhillipIsland().parse(HTML)
    assert len(events) >= 5
    e = events[0]
    assert e.provider == "phillip_island"
    assert e.track == "Phillip Island Grand Prix Circuit"
    assert e.state == "VIC"
    assert e.price_aud is not None
    assert e.url.startswith("https://www.phillipislandridedays.com.au")
```

- [ ] **Step 2: Run — FAIL.**
- [ ] **Step 3: Implement** (reuse `_price`, `_resolve_date`, `_status` — move these shared helpers into `lib/providers/base.py` as module functions and import them, to stay DRY across adapters). Constant track/state; `date_end` set when the row is a date range (e.g. `07 Dec - 23 Dec`).

```python
from __future__ import annotations
from bs4 import BeautifulSoup
from lib.models import Event, Status
from lib.providers.base import Provider, parse_date, parse_price, parse_status

TRACK = "Phillip Island Grand Prix Circuit"

class PhillipIsland(Provider):
    key = "phillip_island"
    name = "Phillip Island Ride Days"
    base_url = "https://www.phillipislandridedays.com.au/pird-ride-days"

    def parse(self, html: str) -> list[Event]:
        soup = BeautifulSoup(html, "lxml")
        events: list[Event] = []
        for row in soup.select("SELECTOR_ROW"):
            date_txt = row.select_one("SELECTOR_DATE")
            price_el = row.select_one("SELECTOR_PRICE")
            time_el = row.select_one("SELECTOR_TIME")
            link = row.select_one("a")
            if not date_txt:
                continue
            d_start, d_end = parse_date(date_txt.get_text(" ", strip=True), want_range=True)
            if d_start is None:
                continue
            price_disp = price_el.get_text(" ", strip=True) if price_el else ""
            status, status_raw = parse_status(row.get_text(" ", strip=True))
            url = (link.get("href") if link else "") or self.base_url
            if url and not url.startswith("http"):
                url = "https://www.phillipislandridedays.com.au" + url
            events.append(Event(
                provider=self.key, provider_name=self.name,
                title=f"{TRACK} ride day", track=TRACK, state="VIC",
                date_start=d_start, date_end=d_end,
                start_time=time_el.get_text(strip=True) if time_el else None,
                price_display=price_disp, price_aud=parse_price(price_disp),
                url=url, status=status, status_raw=status_raw))
        return events
```

> `parse_date(text, want_range=True)` returns `(start, end)`; the single-date version returns `(d, None)`. Add this signature to `base.py` when extracting the helper in this task.

- [ ] **Step 4: Run — PASS.**
- [ ] **Step 5: Append `PhillipIsland()` to registry. Commit** — `git commit -am "feat: Phillip Island (PIRD) adapter (fixture-tested)"`

---

### Task 7: SMSP adapter (`lib/providers/smsp.py`)

**Files:**
- Create: `lib/providers/smsp.py`
- Test: `tests/test_smsp.py`
- Modify: `lib/registry.py`

Track constant = `Sydney Motorsport Park`, state = `NSW`. Price often `From $X` → `price_aud` = lower bound. Status best-effort.

- [ ] **Step 1: Failing test**

```python
from pathlib import Path
from lib.providers.smsp import SMSP
HTML = Path("tests/fixtures/smsp_ride_days.html").read_text(encoding="utf-8")

def test_parses_smsp():
    events = SMSP().parse(HTML)
    assert len(events) >= 5
    e = events[0]
    assert e.provider == "smsp"
    assert e.track == "Sydney Motorsport Park"
    assert e.state == "NSW"
    assert e.price_aud is not None       # "From $365" -> 365.0
    assert e.url.startswith("https://www.smsprd.com")
```

- [ ] **Step 2: Run — FAIL.**
- [ ] **Step 3: Implement** — same shape as PIRD, constant track/state = Sydney Motorsport Park / NSW, selectors from the SMSP fixture, `parse_price("From $365") == 365.0`.

```python
from __future__ import annotations
from bs4 import BeautifulSoup
from lib.models import Event
from lib.providers.base import Provider, parse_date, parse_price, parse_status

TRACK = "Sydney Motorsport Park"

class SMSP(Provider):
    key = "smsp"
    name = "Sydney Motorsport Park Ride Days"
    base_url = "https://www.smsprd.com/smsprd-ride-days"

    def parse(self, html: str) -> list[Event]:
        soup = BeautifulSoup(html, "lxml")
        events: list[Event] = []
        for row in soup.select("SELECTOR_ROW"):
            date_el = row.select_one("SELECTOR_DATE")
            price_el = row.select_one("SELECTOR_PRICE")
            time_el = row.select_one("SELECTOR_TIME")
            link = row.select_one("a")
            if not date_el:
                continue
            d_start, _ = parse_date(date_el.get_text(" ", strip=True))
            if d_start is None:
                continue
            price_disp = price_el.get_text(" ", strip=True) if price_el else ""
            status, status_raw = parse_status(row.get_text(" ", strip=True))
            url = (link.get("href") if link else "") or self.base_url
            if url and not url.startswith("http"):
                url = "https://www.smsprd.com" + url
            events.append(Event(
                provider=self.key, provider_name=self.name,
                title=f"{TRACK} ride day", track=TRACK, state="NSW",
                date_start=d_start,
                start_time=time_el.get_text(strip=True) if time_el else None,
                price_display=price_disp, price_aud=parse_price(price_disp),
                url=url, status=status, status_raw=status_raw))
        return events
```

- [ ] **Step 4: Run — PASS.**
- [ ] **Step 5: Append `SMSP()` to registry. Commit** — `git commit -am "feat: SMSP adapter (fixture-tested)"`

---

### Task 8: Scrape orchestration (`lib/scrape.py`)

**Files:**
- Create: `lib/scrape.py`
- Test: `tests/test_scrape.py`

- [ ] **Step 1: Failing test** — a fake provider that raises must not break a good provider; both runs recorded.

```python
from datetime import date, timedelta
from lib.scrape import run_all
from lib.store import Store
from lib.models import Event, Status

class Good:
    key, name = "good", "Good"
    def fetch(self):
        return [Event(provider="good", provider_name="Good", title="RD", track="T",
                      date_start=date.today()+timedelta(days=1), price_display="$1",
                      url="https://x/good", status=Status.OPEN)]
class Bad:
    key, name = "bad", "Bad"
    def fetch(self):
        raise RuntimeError("boom")

def test_run_all_isolates_failures(tmp_path):
    s = Store(tmp_path / "t.db")
    run_all(s, providers=[Good(), Bad()])
    assert len(s.upcoming_events()) == 1
    runs = s.latest_runs()
    assert runs["good"].ok is True and runs["good"].event_count == 1
    assert runs["bad"].ok is False and "boom" in runs["bad"].error
```

- [ ] **Step 2: Run — FAIL.**
- [ ] **Step 3: Implement**

```python
from __future__ import annotations
import logging
from datetime import datetime
from lib.registry import PROVIDERS
from lib.store import Store

log = logging.getLogger("rideday.scrape")

def run_all(store: Store, providers=None) -> None:
    providers = providers if providers is not None else PROVIDERS
    for p in providers:
        started = datetime.now().isoformat(timespec="seconds")
        try:
            events = p.fetch()
            if not events:
                raise ValueError("0 events parsed (possible site change)")
            store.upsert_events(events)
            store.record_run(p.key, ok=True, event_count=len(events), error=None,
                             started_at=started)
            log.info("scraped %s: %d events", p.key, len(events))
        except Exception as exc:  # isolate: one site failing never breaks others
            store.record_run(p.key, ok=False, event_count=0, error=str(exc),
                             started_at=started)
            log.warning("scrape failed %s: %s", p.key, exc)
```

- [ ] **Step 4: Run — PASS.**
- [ ] **Step 5: Commit** — `git commit -am "feat: run_all orchestration with per-provider isolation"`

---

### Task 9: FastAPI app + scheduler (`app.py`)

**Files:**
- Create: `app.py`
- Test: `tests/test_app.py`

- [ ] **Step 1: Failing test** (FastAPI `TestClient`; seed the store, assert page + refresh endpoint)

```python
from datetime import date, timedelta
from fastapi.testclient import TestClient
from lib.models import Event, Status
import app as appmod

def test_index_and_refresh(tmp_path, monkeypatch):
    monkeypatch.setenv("RIDEDAY_DB", str(tmp_path / "t.db"))
    application = appmod.create_app()
    application.state.store.upsert_events([Event(provider="champions",
        provider_name="Champions Ride Days", title="Broadford", track="Broadford",
        date_start=date.today()+timedelta(days=2), price_display="$220",
        url="https://championsridedays.com.au/x", status=Status.OPEN)])
    client = TestClient(application)
    r = client.get("/")
    assert r.status_code == 200 and "Broadford" in r.text
    j = client.get("/api/events").json()
    assert j[0]["track"] == "Broadford"
    assert client.post("/api/refresh").status_code in (200, 202)
```

- [ ] **Step 2: Run — FAIL.**
- [ ] **Step 3: Implement `app.py`** (factory `create_app()`; APScheduler started only when run as server, not under tests; `POST /api/refresh` runs `run_all` synchronously with a lock)

```python
from __future__ import annotations
import os, threading
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request
from apscheduler.schedulers.background import BackgroundScheduler
from lib.store import Store
from lib.scrape import run_all
from lib.registry import PROVIDERS

BASE = Path(__file__).parent
templates = Jinja2Templates(directory=str(BASE / "templates"))
_refresh_lock = threading.Lock()

def create_app() -> FastAPI:
    app = FastAPI(title="rideday-radar")
    app.mount("/static", StaticFiles(directory=str(BASE / "static")), name="static")
    store = Store(os.environ.get("RIDEDAY_DB", str(BASE / "data" / "events.db")))
    app.state.store = store

    def do_refresh():
        if _refresh_lock.acquire(blocking=False):
            try:
                run_all(store, providers=PROVIDERS)
            finally:
                _refresh_lock.release()

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request):
        events = store.upcoming_events()
        runs = store.latest_runs()
        return templates.TemplateResponse("index.html", {
            "request": request, "events": events, "runs": runs,
            "provider_names": {p.key: p.name for p in PROVIDERS}})

    @app.get("/api/events")
    def api_events():
        return JSONResponse([_ev_json(e) for e in store.upcoming_events()])

    @app.post("/api/refresh")
    def api_refresh():
        do_refresh()
        return JSONResponse({"ok": True}, status_code=200)

    app.state.do_refresh = do_refresh
    return app

def _ev_json(e):
    return {"provider": e.provider, "provider_name": e.provider_name, "title": e.title,
            "track": e.track, "state": e.state, "date_start": e.date_start.isoformat(),
            "date_end": e.date_end.isoformat() if e.date_end else None,
            "start_time": e.start_time, "price_aud": e.price_aud,
            "price_display": e.price_display, "status": e.status.value,
            "status_raw": e.status_raw, "url": e.url}

app = create_app()

def _start_scheduler():
    interval = int(os.environ.get("RIDEDAY_INTERVAL_HOURS", "3"))
    sched = BackgroundScheduler()
    sched.add_job(app.state.do_refresh, "interval", hours=interval, id="scrape")
    sched.start()
    if not app.state.store.latest_runs():   # cold start: scrape once now
        threading.Thread(target=app.state.do_refresh, daemon=True).start()

if __name__ == "__main__":
    import uvicorn
    _start_scheduler()
    uvicorn.run(app, host="127.0.0.1", port=8765)
```

- [ ] **Step 4: Run — PASS.**
- [ ] **Step 5: Commit** — `git commit -am "feat: FastAPI app (index, /api/events, /api/refresh) + scheduler"`

---

### Task 10: Frontend (`templates/index.html`, `static/app.js`, `static/style.css`)

**Files:**
- Create: `templates/index.html`, `static/app.js`, `static/style.css`

- [ ] **Step 1: Write `templates/index.html`** — server-renders the table from `events`; a status bar from `runs`; a "刷新" button. Table rows carry `data-*` attributes for client-side sort/filter.

```html
<!doctype html>
<html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>rideday-radar · 澳洲赛道日看板</title>
<link rel="stylesheet" href="/static/style.css"></head>
<body>
<header>
  <h1>澳洲摩托赛道日看板</h1>
  <div class="runs">
    {% for key, name in provider_names.items() %}
      {% set r = runs.get(key) %}
      <span class="run {{ 'ok' if r and r.ok else 'bad' }}">
        {{ name }}: {% if r and r.ok %}✓ {{ r.finished_at.strftime('%m-%d %H:%M') }}
        {% elif r %}⚠ 失败{% else %}—{% endif %}</span>
    {% endfor %}
    <button id="refresh">立即刷新</button>
  </div>
  <div class="filters">
    <input id="q" placeholder="搜索赛道…">
    <select id="state"><option value="">全部州</option></select>
  </div>
</header>
<table id="events"><thead><tr>
  <th data-sort="date">日期</th><th data-sort="track">赛道</th><th data-sort="state">州</th>
  <th data-sort="price">价格</th><th>卖票情况</th><th>链接</th>
</tr></thead><tbody>
  {% for e in events %}
  <tr data-date="{{ e.date_start.isoformat() }}" data-track="{{ e.track|lower }}"
      data-state="{{ e.state or '' }}" data-price="{{ e.price_aud or 0 }}">
    <td>{{ e.date_start.strftime('%a %d %b') }}{% if e.date_end %} – {{ e.date_end.strftime('%d %b') }}{% endif %}
        {% if e.start_time %}<small>{{ e.start_time }}</small>{% endif %}</td>
    <td>{{ e.track }}<br><small>{{ e.provider_name }}</small></td>
    <td>{{ e.state or '' }}</td>
    <td>{{ e.price_display }}</td>
    <td class="st st-{{ e.status.value }}">{{ e.status_raw or e.status.value }}</td>
    <td><a href="{{ e.url }}" target="_blank" rel="noopener">订票 ↗</a></td>
  </tr>
  {% endfor %}
</tbody></table>
{% if not events %}<p class="empty">还没有数据,点「立即刷新」抓取。</p>{% endif %}
<script src="/static/app.js"></script>
</body></html>
```

- [ ] **Step 2: Write `static/app.js`** — populate state filter options, text+state filtering, header-click sorting (date/track/state/price), refresh button POSTs then reloads.

```javascript
const tbody = document.querySelector("#events tbody");
const rows = () => [...tbody.querySelectorAll("tr")];
const stateSel = document.querySelector("#state");
[...new Set(rows().map(r => r.dataset.state).filter(Boolean))].sort()
  .forEach(s => stateSel.add(new Option(s, s)));

function applyFilter() {
  const q = document.querySelector("#q").value.toLowerCase();
  const st = stateSel.value;
  rows().forEach(r => {
    const ok = r.dataset.track.includes(q) && (!st || r.dataset.state === st);
    r.style.display = ok ? "" : "none";
  });
}
document.querySelector("#q").addEventListener("input", applyFilter);
stateSel.addEventListener("change", applyFilter);

let asc = {};
document.querySelectorAll("th[data-sort]").forEach(th => th.addEventListener("click", () => {
  const key = th.dataset.sort; asc[key] = !asc[key];
  const val = r => key === "price" ? parseFloat(r.dataset.price)
    : key === "date" ? r.dataset.date : r.dataset[key];
  rows().sort((a, b) => (val(a) > val(b) ? 1 : -1) * (asc[key] ? 1 : -1))
        .forEach(r => tbody.appendChild(r));
}));

document.querySelector("#refresh").addEventListener("click", async (e) => {
  e.target.disabled = true; e.target.textContent = "抓取中…";
  await fetch("/api/refresh", { method: "POST" });
  location.reload();
});
```

- [ ] **Step 3: Write `static/style.css`** — a clean readable table; status color classes `.st-open`(green) `.st-filling_fast`(amber) `.st-sold_out`(red/strikethrough) `.st-unknown`(grey); `.run.bad` red, `.run.ok` green. (Concrete CSS written during execution — keep it minimal and legible, dark-friendly.)

- [ ] **Step 4: Manual verify** — `RIDEDAY_DB=data/events.db .venv/bin/python app.py`, open `http://127.0.0.1:8765/`, click 立即刷新, confirm rows appear, sorting + filter + status colors work.

- [ ] **Step 5: Commit** — `git commit -am "feat: dashboard UI (sortable/filterable table, status bar, refresh)"`

---

### Task 11: Docs, live smoke test, wrap-up

**Files:**
- Create: `README.md`, `CLAUDE.md`, `tests/test_live.py`, `scripts/run.sh`

- [ ] **Step 1: `tests/test_live.py`** (marked `live`, skipped by default) — real fetch each provider asserts ≥1 event; run manually with `-m live` to confirm real sites still parse.

```python
import pytest
from lib.registry import PROVIDERS

@pytest.mark.live
@pytest.mark.parametrize("provider", PROVIDERS, ids=[p.key for p in PROVIDERS])
def test_live_provider_returns_events(provider):
    events = provider.fetch()
    assert len(events) >= 1
    assert all(e.date_start and e.url for e in events)
```

- [ ] **Step 2: `README.md`** — what it is, install (`python -m venv .venv && pip install -r requirements.txt`), run (`python app.py` → http://127.0.0.1:8765), how to add a new provider (add adapter + fixture + test + registry line), env vars (`RIDEDAY_DB`, `RIDEDAY_INTERVAL_HOURS`), how to refresh fixtures (`scripts/capture_fixtures.py`).

- [ ] **Step 3: `CLAUDE.md`** — repo conventions (aligns with catalyst-checker), adapter pattern, TDD-against-fixtures rule, "sites may change → keep parse() pure + fixtures", git rules (local only, author cyprien0312, straight to main).

- [ ] **Step 4: `scripts/run.sh`** — one-liner launcher: `#!/usr/bin/env bash` + `exec .venv/bin/python app.py`.

- [ ] **Step 5: Full test run** — `.venv/bin/pytest` (all non-live green), then optionally `.venv/bin/pytest -m live` to confirm real sites.

- [ ] **Step 6: Commit** — `git commit -am "docs: README + CLAUDE.md + live smoke test + run script"`

---

## Self-Review Notes

- **Spec coverage:** view=local web service (Task 9-10 ✓); background 3h + manual refresh (Task 9 scheduler + `/api/refresh`, Task 10 button ✓); fields date/track/state/price/status/url (Task 1 model, Tasks 5-7 adapters ✓); status best-effort + unknown (Task 5-7 `parse_status`/UNKNOWN default ✓); no per-event detail fetch (adapters parse listing only ✓); SQLite cache + upcoming-only + per-run status (Task 2 ✓); resilience/isolation (Task 8 ✓); politeness UA/retry/timeout (Task 3 `get_html` ✓); fixture TDD + optional live smoke (Task 4-7, 11 ✓); extensibility = adapter+registry (Task 3, 5-7 ✓); git local/author/main (Task 0 + throughout ✓).
- **Placeholder scan:** `SELECTOR_*` tokens in Tasks 5-7 are intentional and explicitly resolved in Task 4 Step 3 against the captured fixture — not silent placeholders. All other code is concrete.
- **Type consistency:** `Store`, `Event`, `Status`, `event_uid`, `run_all(store, providers=...)`, `parse_date/parse_price/parse_status` (helpers live in `base.py`, used by Tasks 6-7 — note Task 5 defines them inline then Task 6 extracts to `base.py`; during execution, extract the shared helpers to `base.py` in Task 5 so Tasks 6-7 import them). `create_app()` + `app.state.store` consistent across Task 9 and its test.
