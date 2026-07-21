from datetime import date

from lib.models import Event, Status, event_uid


def test_event_uid_stable_from_provider_and_url():
    a = event_uid("champions", "https://x/product/1/")
    b = event_uid("champions", "https://x/product/1/")
    assert a == b and len(a) == 40  # sha1 hex


def test_event_uid_falls_back_to_date_track_when_no_url():
    uid = event_uid("smsp", "", date_start=date(2026, 7, 26), track="Sydney Motorsport Park")
    assert uid == event_uid("smsp", "", date_start=date(2026, 7, 26), track="Sydney Motorsport Park")


def test_event_defaults():
    e = Event(provider="smsp", provider_name="SMSP", title="Ride Day",
              track="Sydney Motorsport Park", date_start=date(2026, 7, 26),
              price_display="From $365", url="https://x/1")
    assert e.status is Status.UNKNOWN
    assert e.state is None and e.price_aud is None and e.date_end is None
    assert e.event_uid == event_uid("smsp", "https://x/1")
