from pathlib import Path

from lib.models import Status
from lib.providers.smsp import SMSP

HTML = Path("tests/fixtures/smsp_ride_days.html").read_text(encoding="utf-8")
EVENTS = SMSP().parse(HTML)


def test_parses_smsp():
    assert len(EVENTS) >= 15
    e = EVENTS[0]
    assert e.provider == "smsp"
    assert e.track == "Sydney Motorsport Park"
    assert e.state == "NSW"
    assert e.price_aud == 365.0            # "From $365" -> lower bound
    assert e.start_time == "6:30am"
    assert e.status is Status.OPEN
    assert e.url.startswith("https://www.smsprd.com/smsprd-ride-days#")


def test_from_price_lower_bound_and_unique_uids():
    cheap = next(e for e in EVENTS if e.price_aud == 255.0)  # the twilight sessions
    assert "255" in cheap.price_display
    assert len({e.event_uid for e in EVENTS}) == len(EVENTS)
