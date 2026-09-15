from datetime import date

from lib.store import Store
from lib.weather.forecast import DailyForecast
from lib.weather.locations import BY_KEY
from lib.weather.refresh import refresh_weather


def test_refresh_isolates_failures_and_records_run(tmp_path):
    s = Store(tmp_path / "t.db")
    locs = [BY_KEY["broadford"], BY_KEY["smsp"], BY_KEY["collie"]]

    def fake_fetch(loc):
        if loc.key == "smsp":
            raise RuntimeError("boom")
        return [DailyForecast(loc.key, date.today(), 3, 5.0, 20.0, 0.0, 10, 15.0)]

    refresh_weather(s, locations=locs, fetch=fake_fetch)
    fc = s.forecasts()
    assert set(k for k, _ in fc) == {"broadford", "collie"}
    run = s.latest_runs()["weather"]
    assert run.ok is False and run.event_count == 2
    assert "smsp: boom" in run.error


def test_refresh_all_ok(tmp_path):
    s = Store(tmp_path / "t.db")
    locs = [BY_KEY["broadford"], BY_KEY["smsp"]]
    refresh_weather(s, locations=locs,
                    fetch=lambda loc: [DailyForecast(loc.key, date.today(), 0, 1.0, 2.0, 0.0, 0, 1.0)])
    run = s.latest_runs()["weather"]
    assert run.ok is True and run.event_count == 2 and run.error is None


def test_refresh_empty_result_counts_as_failure(tmp_path):
    s = Store(tmp_path / "t.db")
    refresh_weather(s, locations=[BY_KEY["broadford"]], fetch=lambda loc: [])
    run = s.latest_runs()["weather"]
    assert run.ok is False and "0 days" in run.error
