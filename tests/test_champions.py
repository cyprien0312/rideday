from pathlib import Path

from lib.models import Status
from lib.providers.champions import Champions

HTML = Path("tests/fixtures/champions_events.html").read_text(encoding="utf-8")
EVENTS = Champions().parse(HTML)


def test_parses_many_events():
    assert len(EVENTS) >= 20
    e = EVENTS[0]
    assert e.provider == "champions"
    assert e.track and e.date_start is not None
    assert e.url.startswith("https://championsridedays.com.au/")
    assert e.price_aud is not None


def test_broadford_row_details():
    broadford = next(e for e in EVENTS if "Broadford Raceway" == e.track)
    assert broadford.state == "VIC"
    assert broadford.price_aud == 220.0
    assert broadford.date_start.month == 7 and broadford.date_start.day == 26
    assert broadford.status is Status.OPEN


def test_status_and_state_present():
    assert any(e.status is Status.FILLING_FAST for e in EVENTS)
    assert any(e.status is Status.OPEN for e in EVENTS)
    assert all(e.state for e in EVENTS)  # every Champions card has a (STATE) label
