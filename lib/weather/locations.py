"""Track -> weather location table.

Each ride-day track maps to one Open-Meteo grid point (lat/lon) and one BOM
place page (link only — we never parse BOM). `locate()` matches the messy
track strings providers emit ("The Bend Brekky and Bikes – Sat 29 August!!")
by lowercase substring, so a new marketing suffix doesn't break the match.
Coordinates from OpenStreetMap (Nominatim), 2026-09-15.
"""
from __future__ import annotations

from dataclasses import dataclass

BOM_BASE = "https://www.bom.gov.au/places"


@dataclass(frozen=True)
class TrackLocation:
    key: str
    name: str
    lat: float
    lon: float
    tz: str
    bom_path: str
    match: tuple[str, ...]

    @property
    def bom_url(self) -> str:
        return f"{BOM_BASE}/{self.bom_path}/forecast/"


LOCATIONS: list[TrackLocation] = [
    TrackLocation("broadford", "Broadford", -37.2147, 145.0835,
                  "Australia/Melbourne", "vic/broadford", ("broadford",)),
    TrackLocation("phillip_island", "Phillip Island", -38.5041, 145.2346,
                  "Australia/Melbourne", "vic/cowes", ("phillip island",)),
    TrackLocation("smsp", "Sydney Motorsport Park", -33.8064, 150.8710,
                  "Australia/Sydney", "nsw/eastern-creek", ("sydney motorsport",)),
    TrackLocation("the_bend", "The Bend", -35.3019, 139.5148,
                  "Australia/Adelaide", "sa/tailem-bend", ("the bend",)),
    TrackLocation("mallala", "Mallala", -34.4139, 138.5053,
                  "Australia/Adelaide", "sa/mallala", ("mallala",)),
    # Morgan Park is ~5 km south of Warwick; Open-Meteo's grid is ~11 km anyway.
    TrackLocation("morgan_park", "Morgan Park", -28.2500, 152.0400,
                  "Australia/Brisbane", "qld/warwick", ("morgan park",)),
    TrackLocation("collie", "Collie", -33.4291, 116.2446,
                  "Australia/Perth", "wa/collie", ("collie",)),
    TrackLocation("wanneroo", "Wanneroo", -31.6643, 115.7907,
                  "Australia/Perth", "wa/wanneroo", ("wanneroo",)),
]

BY_KEY: dict[str, TrackLocation] = {l.key: l for l in LOCATIONS}


def locate(track: str) -> TrackLocation | None:
    t = (track or "").lower()
    if not t:
        return None
    for loc in LOCATIONS:
        if any(m in t for m in loc.match):
            return loc
    return None
