"""Champions Ride Days adapter.

Fixture: tests/fixtures/champions_events.html
Structure (per event): `.bookride .bookinnerhead`
  .ride-date   -> "26" + <span>Jul</span>      (start date, no year)
  .ride-title a-> track name + href (product page, absolute)
  .ride-nsw    -> "Broadford (VIC)"            (state in parens)
  .ride-filling-> "Available!" / "Filling Fast!" / "Sold Out"
  .book-price  -> "$ 220.00"
"""
from __future__ import annotations

from bs4 import BeautifulSoup

from lib.models import Event
from lib.providers.base import (
    STATE_RE,
    Provider,
    parse_date,
    parse_price,
    parse_status,
)


class Champions(Provider):
    key = "champions"
    name = "Champions Ride Days"
    base_url = "https://championsridedays.com.au/events/"

    def parse(self, html: str) -> list[Event]:
        soup = BeautifulSoup(html, "lxml")
        events: list[Event] = []
        for head in soup.select(".bookride .bookinnerhead"):
            title_a = head.select_one(".ride-title a")
            date_el = head.select_one(".ride-date")
            if not (title_a and date_el):
                continue
            d_start, _ = parse_date(date_el.get_text(" ", strip=True))
            if d_start is None:
                continue
            track = title_a.get_text(" ", strip=True)
            url = title_a.get("href", "").strip()

            state = None
            loc_el = head.select_one(".ride-nsw")
            if loc_el:
                m = STATE_RE.search(loc_el.get_text(" ", strip=True))
                if m:
                    state = m.group(1).upper()

            fill_el = head.select_one(".ride-filling")
            status, status_raw = parse_status(
                fill_el.get_text(" ", strip=True) if fill_el else "")

            price_el = head.select_one(".book-price")
            price_disp = price_el.get_text(" ", strip=True) if price_el else ""

            events.append(Event(
                provider=self.key, provider_name=self.name, title=track, track=track,
                date_start=d_start, state=state,
                price_display=price_disp, price_aud=parse_price(price_disp),
                url=url, status=status, status_raw=status_raw))
        return events
