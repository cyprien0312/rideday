from datetime import date, timedelta

from fastapi.testclient import TestClient

import app as appmod
from lib.models import Event, Status


def _seed(application):
    application.state.store.upsert_events([Event(
        provider="champions", provider_name="Champions Ride Days", title="Broadford",
        track="Broadford", date_start=date.today() + timedelta(days=2),
        price_display="$220", price_aud=220.0,
        url="https://championsridedays.com.au/x", status=Status.OPEN)])


def test_index_and_events_api(tmp_path, monkeypatch):
    monkeypatch.setenv("RIDEDAY_DB", str(tmp_path / "t.db"))
    application = appmod.create_app()
    _seed(application)
    client = TestClient(application)

    r = client.get("/")
    assert r.status_code == 200 and "Broadford" in r.text

    j = client.get("/api/events").json()
    assert j and j[0]["track"] == "Broadford" and j[0]["status"] == "open"


def test_calendar_feed_is_served_per_state_and_all(tmp_path, monkeypatch):
    monkeypatch.setenv("RIDEDAY_DB", str(tmp_path / "t.db"))
    application = appmod.create_app()
    _seed(application)
    client = TestClient(application)

    r = client.get("/calendar/all.ics")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/calendar")
    assert "BEGIN:VEVENT" in r.text and "Broadford" in r.text

    assert client.get("/calendar/vic.ics").status_code == 404  # seeded event has no state
    assert client.get("/calendar/nope.ics").status_code == 404


def test_index_links_the_calendar_feeds(tmp_path, monkeypatch):
    monkeypatch.setenv("RIDEDAY_DB", str(tmp_path / "t.db"))
    application = appmod.create_app()
    _seed(application)
    assert "/calendar/all.ics" in TestClient(application).get("/").text


def test_refresh_endpoint_runs_providers(tmp_path, monkeypatch):
    monkeypatch.setenv("RIDEDAY_DB", str(tmp_path / "t.db"))
    application = appmod.create_app()

    calls = {"n": 0}

    def fake_run_all(store, providers=None):
        calls["n"] += 1

    monkeypatch.setattr(appmod, "run_all", fake_run_all)
    client = TestClient(application)
    resp = client.post("/api/refresh")
    assert resp.status_code == 200
    assert calls["n"] == 1
