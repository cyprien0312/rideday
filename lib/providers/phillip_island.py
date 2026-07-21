"""Phillip Island Ride Days (PIRD) adapter.

Fixture: tests/fixtures/pird_ride_days.html
Structure (per event): `.event`
  .date h4           -> "Mon 07 Sep"        (start date, no year)
  .detail h3         -> "From $315"         (price, lower bound)
  .detail p          -> "7:00am"            (start time)
  .status button.book-> "Book Now", data-id (booking is a JS popup, no href)

Track is always the Phillip Island GP Circuit (VIC). The listing has no
per-event URL, so we build a unique anchor from the button's data-id.
"""
from __future__ import annotations

from bs4 import BeautifulSoup

from lib.models import Event
from lib.providers.base import Provider, parse_date, parse_price, parse_status

TRACK = "Phillip Island Grand Prix Circuit"


class PhillipIsland(Provider):
    key = "phillip_island"
    name = "Phillip Island Ride Days"
    base_url = "https://www.phillipislandridedays.com.au/pird-ride-days"

    def parse(self, html: str) -> list[Event]:
        soup = BeautifulSoup(html, "lxml")
        events: list[Event] = []
        for row in soup.select(".event"):
            date_el = row.select_one(".date h4") or row.select_one(".date")
            if not date_el:
                continue
            d_start, d_end = parse_date(date_el.get_text(" ", strip=True), want_range=True)
            if d_start is None:
                continue
            price_el = row.select_one(".detail h3")
            time_el = row.select_one(".detail p")
            btn = row.select_one(".status button") or row.select_one("button")

            price_disp = price_el.get_text(" ", strip=True) if price_el else ""
            status, status_raw = parse_status(btn.get_text(" ", strip=True) if btn else "")

            anchor = (btn.get("data-id") if btn else None) or d_start.isoformat()
            url = f"{self.base_url}#{anchor}"

            events.append(Event(
                provider=self.key, provider_name=self.name,
                title=f"{TRACK} ride day", track=TRACK, state="VIC",
                date_start=d_start, date_end=d_end,
                start_time=time_el.get_text(" ", strip=True) if time_el else None,
                price_display=price_disp, price_aud=parse_price(price_disp),
                url=url, status=status, status_raw=status_raw))
        return events
