from __future__ import annotations

import re
from abc import ABC, abstractmethod
from datetime import date

import requests
from dateutil import parser as dparser
from tenacity import retry, stop_after_attempt, wait_exponential

from lib.models import Event, Status

UA = "rideday-radar/0.1 (personal ride-day aggregator; contact: local)"

# --- shared parsing helpers (used by every adapter) ---------------------------

STATUS_MAP = {
    "sold out": Status.SOLD_OUT,
    "soldout": Status.SOLD_OUT,
    "fully booked": Status.SOLD_OUT,
    "filling fast": Status.FILLING_FAST,
    "selling fast": Status.FILLING_FAST,
    "almost full": Status.FILLING_FAST,
    "few left": Status.FILLING_FAST,
    "available": Status.OPEN,
    "in stock": Status.OPEN,
    "book now": Status.OPEN,
    "add to cart": Status.OPEN,
}
STATE_RE = re.compile(r"\(([A-Za-z]{2,3})\)")
_WEEKDAY_RE = re.compile(r"\b(mon|tue|tues|wed|thu|thur|thurs|fri|sat|sun)[a-z]*\b", re.I)
_DASH_RE = re.compile(r"\s*[‐-―−]\s*|\s+-\s+|\s+to\s+", re.I)
_PRICE_RE = re.compile(r"\$?\s*([\d,]+(?:\.\d{1,2})?)")


def _clean_date_text(text: str) -> str:
    return _WEEKDAY_RE.sub(" ", text or "").strip()


def _one_date(text: str) -> date | None:
    cleaned = _clean_date_text(text)
    if not cleaned:
        return None
    try:
        dt = dparser.parse(cleaned, dayfirst=True, fuzzy=True)
    except (ValueError, OverflowError):
        return None
    d = dt.date()
    if d < date.today():          # listings omit the year; roll to next occurrence
        try:
            d = d.replace(year=d.year + 1)
        except ValueError:
            pass
    return d


def parse_date(text: str, want_range: bool = False) -> tuple[date | None, date | None]:
    """Return (start, end). end is None unless want_range and the text is a range."""
    text = (text or "").strip()
    if want_range:
        parts = _DASH_RE.split(text, maxsplit=1)
        if len(parts) == 2:
            start = _one_date(parts[0])
            end = _one_date(parts[1])
            # end like "23 Dec" may lack a month; if it parsed but is before start, drop it
            if start and end and end < start:
                end = None
            return start, end
    return _one_date(text), None


def parse_price(text: str) -> float | None:
    m = _PRICE_RE.search(text or "")
    return float(m.group(1).replace(",", "")) if m else None


def parse_status(text: str) -> tuple[Status, str | None]:
    t = (text or "").strip().lower()
    for key, val in STATUS_MAP.items():
        if key in t:
            return val, text.strip() or None
    return Status.UNKNOWN, (text.strip() or None)


# --- provider base ------------------------------------------------------------

class Provider(ABC):
    key: str
    name: str
    base_url: str

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8), reraise=True)
    def get_html(self, url: str) -> str:
        resp = requests.get(url, headers={"User-Agent": UA}, timeout=20)
        resp.raise_for_status()
        return resp.text

    @abstractmethod
    def parse(self, html: str) -> list[Event]:
        """Pure function html -> events. Tested against saved fixtures."""

    def fetch(self) -> list[Event]:
        return self.parse(self.get_html(self.base_url))
