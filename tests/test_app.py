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


def test_refresh_endpoint_runs_providers_and_weather(tmp_path, monkeypatch):
    monkeypatch.setenv("RIDEDAY_DB", str(tmp_path / "t.db"))
    application = appmod.create_app()

    calls = {"providers": 0, "weather": 0}

    def fake_run_all(store, providers=None):
        calls["providers"] += 1

    def fake_refresh_weather(store):
        calls["weather"] += 1

    monkeypatch.setattr(appmod, "run_all", fake_run_all)
    monkeypatch.setattr(appmod, "refresh_weather", fake_refresh_weather)
    client = TestClient(application)
    resp = client.post("/api/refresh")
    assert resp.status_code == 200
    assert calls == {"providers": 1, "weather": 1}


def test_index_and_api_show_normal_tier_without_forecast(tmp_path, monkeypatch):
    monkeypatch.setenv("RIDEDAY_DB", str(tmp_path / "t.db"))
    application = appmod.create_app()
    _seed(application)
    client = TestClient(application)

    html = client.get("/").text
    assert "https://www.bom.gov.au/places/vic/broadford/forecast/" in html
    assert "月平均" in html
    assert "Open-Meteo" in html            # footer attribution
    assert html.count("Open-Meteo") == 2   # LED strip + footer
    assert "尚未抓取" in html               # no weather run recorded yet -> LED says so

    w = client.get("/api/events").json()[0]["weather"]
    assert w["tier"] == "normal" and w["bom_url"].endswith("/vic/broadford/forecast/")
    assert w["tmax"] is not None


def test_api_weather_is_null_for_unknown_track(tmp_path, monkeypatch):
    monkeypatch.setenv("RIDEDAY_DB", str(tmp_path / "t.db"))
    application = appmod.create_app()
    _seed(application)
    application.state.store.upsert_events([Event(
        provider="champions", provider_name="Champions Ride Days", title="Nowhere Circuit",
        track="Nowhere Circuit", date_start=date.today() + timedelta(days=3),
        price_display="$220", price_aud=220.0,
        url="https://x/none", status=Status.OPEN)])
    client = TestClient(application)

    js = client.get("/api/events").json()
    item = next(i for i in js if i["track"] == "Nowhere Circuit")
    assert item["weather"] is None

    assert 'class="wx-none"' in client.get("/").text


def test_index_and_api_show_forecast_tier_when_row_exists(tmp_path, monkeypatch):
    from lib.weather.forecast import DailyForecast
    monkeypatch.setenv("RIDEDAY_DB", str(tmp_path / "t.db"))
    application = appmod.create_app()
    _seed(application)
    d = date.today() + timedelta(days=2)
    application.state.store.upsert_forecasts([DailyForecast("broadford", d, 61, 8.0, 14.0, 6.5, 70, 30.0)])
    client = TestClient(application)

    html = client.get("/").text
    assert "🌧 8–14° · 雨 70%" in html
    assert 'data-rain="70"' in html
    assert 'class="wx-forecast"' in html

    w = client.get("/api/events").json()[0]["weather"]
    assert w["tier"] == "forecast" and w["rain_prob"] == 70 and w["desc"] == "雨"
