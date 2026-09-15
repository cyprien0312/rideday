import json
from datetime import date
from pathlib import Path

import pytest

from lib.weather.forecast import DailyForecast, describe, parse_forecast

FIXTURE = Path("tests/fixtures/openmeteo_broadford.json").read_text(encoding="utf-8")


def test_parse_fixture_gives_16_consecutive_days():
    rows = parse_forecast("broadford", FIXTURE)
    assert len(rows) == 16
    assert all(isinstance(r, DailyForecast) for r in rows)
    assert rows[0].day == date(2026, 9, 15) and rows[-1].day == date(2026, 9, 30)
    assert all((rows[i + 1].day - rows[i].day).days == 1 for i in range(15))
    assert all(r.location_key == "broadford" for r in rows)


def test_parse_fixture_field_values():
    r = parse_forecast("broadford", FIXTURE)[1]   # 2026-09-16
    assert r.code == 51
    assert r.tmax == 10.0 and r.tmin == 5.5
    assert r.rain_mm == 0.3 and r.rain_prob == 2
    assert r.wind_kmh == 27.0


def test_parse_tolerates_nulls():
    d = json.loads(FIXTURE)
    d["daily"]["temperature_2m_max"][0] = None
    d["daily"]["precipitation_probability_max"][0] = None
    r = parse_forecast("broadford", json.dumps(d))[0]
    assert r.tmax is None and r.rain_prob is None
    assert r.tmin == 5.7   # other fields untouched


def test_parse_rejects_missing_field():
    d = json.loads(FIXTURE)
    del d["daily"]["weather_code"]
    with pytest.raises(ValueError):
        parse_forecast("broadford", json.dumps(d))


def test_parse_rejects_ragged_arrays():
    d = json.loads(FIXTURE)
    d["daily"]["wind_speed_10m_max"].pop()
    with pytest.raises(ValueError):
        parse_forecast("broadford", json.dumps(d))


def test_parse_rejects_non_json():
    with pytest.raises(ValueError):
        parse_forecast("broadford", "<html>nope</html>")


@pytest.mark.parametrize("code,emoji,desc", [
    (0, "☀️", "晴"), (1, "🌤", "少云"), (2, "🌤", "少云"), (3, "☁️", "阴"),
    (45, "🌫", "雾"), (48, "🌫", "雾"),
    (51, "🌦", "毛毛雨"), (57, "🌦", "毛毛雨"),
    (61, "🌧", "雨"), (67, "🌧", "雨"),
    (71, "🌨", "雪"), (77, "🌨", "雪"),
    (80, "🌦", "阵雨"), (82, "🌦", "阵雨"),
    (85, "🌨", "阵雪"), (86, "🌨", "阵雪"),
    (95, "⛈", "雷暴"), (99, "⛈", "雷暴"),
    (4, "", ""), (100, "", ""), (None, "", ""),
])
def test_describe(code, emoji, desc):
    assert describe(code) == (emoji, desc)
