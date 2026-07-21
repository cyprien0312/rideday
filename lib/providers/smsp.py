"""Sydney Motorsport Park Ride Days (SMSP) adapter.

Same booking template as Phillip Island — see _ridedays_template.parse_ridedays.
Fixture: tests/fixtures/smsp_ride_days.html
"""
from __future__ import annotations

from lib.models import Event
from lib.providers._ridedays_template import parse_ridedays
from lib.providers.base import Provider

TRACK = "Sydney Motorsport Park"


class SMSP(Provider):
    key = "smsp"
    name = "Sydney Motorsport Park Ride Days"
    base_url = "https://www.smsprd.com/smsprd-ride-days"

    def parse(self, html: str) -> list[Event]:
        return parse_ridedays(
            html, provider_key=self.key, provider_name=self.name,
            base_url=self.base_url, track=TRACK, state="NSW")
