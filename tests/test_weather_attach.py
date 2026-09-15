from datetime import date, timedelta

from lib.models import Event, Status
from lib.weather.attach import WeatherView, weather_for, weather_map
from lib.weather.forecast import DailyForecast
from lib.weather.normals import Normal

TODAY = date(2026, 9, 15)


def _ev(track, d, url="https://x/1"):
    return Event(provider="champions", provider_name="C", title="RD", track=track,
                 date_start=d, price_display="$1", url=url, status=Status.OPEN)


def _fc(key, d, code=3, tmin=4.2, tmax=11.4, mm=0.3, prob=30, wind=27.7):
    return DailyForecast(key, d, code, tmin, tmax, mm, prob, wind)


NORMALS = {"broadford": {9: Normal(15.2, 4.1, 42)}}


def test_forecast_tier_within_7_days():
    d = TODAY + timedelta(days=3)
    w = weather_for(_ev("Broadford Raceway", d), {("broadford", d): _fc("broadford", d)},
                    NORMALS, TODAY)
    assert w.tier == "forecast" and w.tier_label == "预报"
    assert w.emoji == "☁️" and w.desc == "阴"
    assert w.temp_text == "4–11°" and w.rain_text == "雨 30%"
    assert w.hover == "阴 · 风 28 km/h · 雨量 0.3 mm · 点开看 BOM"
    assert w.bom_url == "https://www.bom.gov.au/places/vic/broadford/forecast/"
    assert w.rain_prob == 30


def test_outlook_tier_8_to_15_days():
    d = TODAY + timedelta(days=8)
    w = weather_for(_ev("Broadford Raceway", d), {("broadford", d): _fc("broadford", d)},
                    NORMALS, TODAY)
    assert w.tier == "outlook" and w.tier_label == "远期预报"
    assert w.temp_text == "4–11°"


def test_boundary_day_7_is_forecast():
    d = TODAY + timedelta(days=7)
    w = weather_for(_ev("Broadford Raceway", d), {("broadford", d): _fc("broadford", d)},
                    NORMALS, TODAY)
    assert w.tier == "forecast"


def test_normal_tier_when_no_forecast_row():
    d = TODAY + timedelta(days=40)   # October -> no normals for month 10 in fixture
    w = weather_for(_ev("Broadford Raceway", d), {}, NORMALS, TODAY)
    assert w is None
    d = TODAY + timedelta(days=10)   # still September, no forecast row -> normal
    w = weather_for(_ev("Broadford Raceway", d), {}, NORMALS, TODAY)
    assert w.tier == "normal" and w.tier_label == "9 月平均"
    assert w.emoji == "" and w.desc == ""
    assert w.temp_text == "15°/4°" and w.rain_text == "雨天 42%"
    assert w.hover == "2016–2025 同期平均 · 点开看 BOM"
    assert w.rain_prob == 42


def test_unknown_track_is_none():
    d = TODAY + timedelta(days=1)
    assert weather_for(_ev("Unknown Raceway", d), {("broadford", d): _fc("broadford", d)},
                       NORMALS, TODAY) is None


def test_forecast_with_null_fields_renders_dashes():
    d = TODAY + timedelta(days=1)
    row = DailyForecast("broadford", d, None, None, None, None, None, None)
    w = weather_for(_ev("Broadford Raceway", d), {("broadford", d): row}, NORMALS, TODAY)
    assert w.tier == "forecast"
    assert w.temp_text == "—" and w.rain_text == "雨 —"
    assert w.hover == "风 — km/h · 雨量 — mm · 点开看 BOM"


def test_weather_map_keys_by_event_uid():
    d1, d2 = TODAY + timedelta(days=2), TODAY + timedelta(days=2)
    evs = [_ev("Broadford Raceway", d1, "https://x/a"), _ev("Unknown", d2, "https://x/b")]
    m = weather_map(evs, {("broadford", d1): _fc("broadford", d1)}, NORMALS, TODAY)
    assert set(m) == {evs[0].event_uid}
    assert isinstance(m[evs[0].event_uid], WeatherView)


def test_weather_map_defaults_today():
    evs = [_ev("Broadford Raceway", date.today() + timedelta(days=1))]
    m = weather_map(evs, {}, {"broadford": {date.today().month: Normal(1.0, 0.0, 5)}})
    # tomorrow may roll into next month at month end; either way it resolves without error
    assert isinstance(m, dict)
