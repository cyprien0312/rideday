"""Shared parser for the ride-days booking template used by both Phillip Island
(PIRD) and Sydney Motorsport Park (SMSP) — same platform, same markup:

    .event
      .date h4            -> "Mon 07 Sep"   (start date, no year)
      .detail h3          -> "From $315"     (price, lower bound)
      .detail p           -> "7:00am"        (start time)
      .status button[data-id] -> "Book Now"  (booking is a JS popup, no href)

Track/state are constant per site; the listing has no per-event URL, so a unique
anchor is built from the button's data-id.
"""
from __future__ import annotations

from bs4 import BeautifulSoup

from lib.models import Event
from lib.providers.base import parse_date, parse_price, parse_status


def parse_ridedays(html: str, *, provider_key: str, provider_name: str,
                   base_url: str, track: str, state: str) -> list[Event]:
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

        events.append(Event(
            provider=provider_key, provider_name=provider_name,
            title=f"{track} ride day", track=track, state=state,
            date_start=d_start, date_end=d_end,
            start_time=time_el.get_text(" ", strip=True) if time_el else None,
            price_display=price_disp, price_aud=parse_price(price_disp),
            url=f"{base_url}#{anchor}", status=status, status_raw=status_raw))
    return events
