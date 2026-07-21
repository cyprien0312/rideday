"""Phillip Island Ride Days (PIRD) adapter.

Same booking template as SMSP — see _ridedays_template.parse_ridedays.
Fixture: tests/fixtures/pird_ride_days.html
"""
from __future__ import annotations

from lib.models import Event
from lib.providers._ridedays_template import parse_ridedays
from lib.providers.base import Provider

TRACK = "Phillip Island Grand Prix Circuit"


class PhillipIsland(Provider):
    key = "phillip_island"
    name = "Phillip Island Ride Days"
    base_url = "https://www.phillipislandridedays.com.au/pird-ride-days"

    def parse(self, html: str) -> list[Event]:
        return parse_ridedays(
            html, provider_key=self.key, provider_name=self.name,
            base_url=self.base_url, track=TRACK, state="VIC")
