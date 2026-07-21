from pathlib import Path

from lib.models import Status
from lib.providers.phillip_island import PhillipIsland

HTML = Path("tests/fixtures/pird_ride_days.html").read_text(encoding="utf-8")
EVENTS = PhillipIsland().parse(HTML)


def test_parses_pird():
    assert len(EVENTS) >= 10
    e = EVENTS[0]
    assert e.provider == "phillip_island"
    assert e.track == "Phillip Island Grand Prix Circuit"
    assert e.state == "VIC"
    assert e.price_aud == 315.0            # "From $315"
    assert e.start_time == "7:00am"
    assert e.status is Status.OPEN         # "Book Now"
    assert e.url.startswith("https://www.phillipislandridedays.com.au/pird-ride-days#")


def test_events_have_unique_uids():
    # no per-event URL on the site -> uids must still be distinct (built from data-id)
    assert len({e.event_uid for e in EVENTS}) == len(EVENTS)
