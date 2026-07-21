from datetime import date, timedelta

from lib.models import Event, Status
from lib.store import Store


def _ev(uid_url, d, price=200.0, provider="champions"):
    return Event(provider=provider, provider_name="C", title="RD", track="Broadford",
                 date_start=d, price_display=f"${price}", url=uid_url, price_aud=price,
                 status=Status.OPEN)


def test_upsert_then_upcoming(tmp_path):
    s = Store(tmp_path / "t.db")
    today = date.today()
    s.upsert_events([_ev("u1", today + timedelta(days=2)),
                     _ev("u2", today - timedelta(days=2))])  # past
    up = s.upcoming_events()
    assert [e.url for e in up] == ["u1"]  # past filtered out


def test_upsert_is_idempotent_and_keeps_first_seen(tmp_path):
    s = Store(tmp_path / "t.db")
    d = date.today() + timedelta(days=3)
    s.upsert_events([_ev("u1", d, price=200)])
    first = s.upcoming_events()[0].first_seen
    s.upsert_events([_ev("u1", d, price=250)])  # price changed
    row = s.upcoming_events()[0]
    assert row.first_seen == first          # preserved
    assert row.price_aud == 250             # updated
    assert row.last_seen >= first           # advanced


def test_record_and_latest_runs(tmp_path):
    s = Store(tmp_path / "t.db")
    s.record_run("champions", ok=True, event_count=8, error=None)
    s.record_run("smsp", ok=False, event_count=0, error="timeout")
    runs = s.latest_runs()
    assert runs["champions"].ok is True and runs["champions"].event_count == 8
    assert runs["smsp"].ok is False and runs["smsp"].error == "timeout"
