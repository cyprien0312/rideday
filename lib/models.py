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
    """Stable dedup key. Prefer the booking URL; fall back to provider+date+track."""
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
