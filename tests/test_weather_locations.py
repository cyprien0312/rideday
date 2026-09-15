from pathlib import Path

import pytest

from lib.registry import PROVIDERS
from lib.weather.locations import LOCATIONS, locate

FIXTURES = {"champions": "champions_events.html",
            "phillip_island": "pird_ride_days.html",
            "smsp": "smsp_ride_days.html"}


def _all_fixture_tracks():
    tracks = set()
    for p in PROVIDERS:
        html = Path("tests/fixtures", FIXTURES[p.key]).read_text(encoding="utf-8")
        tracks.update(e.track for e in p.parse(html))
    return sorted(tracks)


def test_table_has_eight_unique_keys():
    keys = [l.key for l in LOCATIONS]
    assert len(keys) == 8 and len(set(keys)) == 8


@pytest.mark.parametrize("track,key", [
    ("Broadford Raceway", "broadford"),
    ("Broadford Raceway DOUBLE DAY SPECIAL 12-13 December 2026", "broadford"),
    ("Phillip Island Grand Prix Circuit", "phillip_island"),
    ("Sydney Motorsport Park", "smsp"),
    ("The Bend Brekky and Bikes – Sat 29 August!!", "the_bend"),
    ("The Bend Motorsport Park (EAST CIRCUIT – 3.93km)", "the_bend"),
    ("Brekky Laps at Mallala Motorsport Park Special Price", "mallala"),
    ("Morgan Park Raceway 16-17 Sept 2026 DOUBLE!!", "morgan_park"),
    ("Collie Motorplex", "collie"),
    ("Wanneroo Raceway (Public Holiday!)", "wanneroo"),
])
def test_locate_known_tracks(track, key):
    loc = locate(track)
    assert loc is not None and loc.key == key


def test_locate_unknown_returns_none():
    assert locate("Unknown Raceway") is None
    assert locate("") is None


def test_every_fixture_track_locates():
    missing = [t for t in _all_fixture_tracks() if locate(t) is None]
    assert missing == []


def test_bom_url_shape():
    loc = locate("Broadford Raceway")
    assert loc.bom_url == "https://www.bom.gov.au/places/vic/broadford/forecast/"
