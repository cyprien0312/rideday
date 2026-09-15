import json
from datetime import date, timedelta

import pytest

from lib.weather.normals import Normal, compute_normals, load_normals, parse_archive


def _days(start, n, tmax, tmin, precip):
    return [(start + timedelta(days=i), tmax, tmin, precip) for i in range(n)]


def test_compute_normals_groups_by_month():
    rows = (_days(date(2024, 1, 1), 10, 30.0, 15.0, 0.0)      # Jan, dry
            + _days(date(2024, 1, 11), 10, 20.0, 10.0, 5.0)   # Jan, wet
            + _days(date(2024, 7, 1), 4, 12.0, 4.0, 0.5))     # Jul, drizzle < 1 mm
    n = compute_normals(rows)
    assert set(n) == {1, 7}
    assert n[1] == Normal(tmax=25.0, tmin=12.5, rain_days_pct=50)
    assert n[7] == Normal(tmax=12.0, tmin=4.0, rain_days_pct=0)


def test_compute_normals_skips_none_values():
    rows = [(date(2024, 3, 1), None, 5.0, None), (date(2024, 3, 2), 20.0, None, 2.0)]
    n = compute_normals(rows)
    assert n[3] == Normal(tmax=20.0, tmin=5.0, rain_days_pct=100)


def test_compute_normals_empty():
    assert compute_normals([]) == {}


def test_parse_archive_rows():
    js = json.dumps({"daily": {"time": ["2025-09-01", "2025-09-02"],
                               "temperature_2m_max": [12.3, None],
                               "temperature_2m_min": [3.0, 3.7],
                               "precipitation_sum": [0.4, 4.2]}})
    assert parse_archive(js) == [(date(2025, 9, 1), 12.3, 3.0, 0.4),
                                 (date(2025, 9, 2), None, 3.7, 4.2)]


def test_parse_archive_rejects_missing_field():
    with pytest.raises(ValueError):
        parse_archive(json.dumps({"daily": {"time": ["2025-09-01"]}}))


def test_load_normals_missing_file_is_empty(tmp_path):
    assert load_normals(tmp_path / "nope.json") == {}


def test_load_normals_roundtrip(tmp_path):
    p = tmp_path / "n.json"
    p.write_text(json.dumps({
        "_meta": {"source": "test"},
        "broadford": {"9": {"tmax": 15.2, "tmin": 4.1, "rain_days_pct": 42}},
    }), encoding="utf-8")
    n = load_normals(p)
    assert "_meta" not in n
    assert n["broadford"][9] == Normal(tmax=15.2, tmin=4.1, rain_days_pct=42)


def test_shipped_normals_cover_all_locations_and_months():
    from lib.weather.locations import LOCATIONS
    n = load_normals()
    assert set(n) == {l.key for l in LOCATIONS}
    for key, months in n.items():
        assert set(months) == set(range(1, 13)), key
        for m, v in months.items():
            assert v.tmax is not None and v.tmin is not None and v.rain_days_pct is not None, (key, m)
            assert -10 < v.tmin < v.tmax < 50, (key, m)
            assert 0 <= v.rain_days_pct <= 100, (key, m)
