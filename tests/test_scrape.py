from datetime import date, timedelta

from lib.models import Event, Status
from lib.scrape import run_all
from lib.store import Store


class Good:
    key, name = "good", "Good"

    def fetch(self):
        return [Event(provider="good", provider_name="Good", title="RD", track="T",
                      date_start=date.today() + timedelta(days=1), price_display="$1",
                      url="https://x/good", status=Status.OPEN)]


class Bad:
    key, name = "bad", "Bad"

    def fetch(self):
        raise RuntimeError("boom")


class Empty:
    key, name = "empty", "Empty"

    def fetch(self):
        return []


def test_run_all_isolates_failures(tmp_path):
    s = Store(tmp_path / "t.db")
    run_all(s, providers=[Good(), Bad()])
    assert len(s.upcoming_events()) == 1
    runs = s.latest_runs()
    assert runs["good"].ok is True and runs["good"].event_count == 1
    assert runs["bad"].ok is False and "boom" in runs["bad"].error


def test_empty_result_is_recorded_as_failure(tmp_path):
    s = Store(tmp_path / "t.db")
    run_all(s, providers=[Empty()])
    assert s.latest_runs()["empty"].ok is False  # 0 parsed => suspect site change
