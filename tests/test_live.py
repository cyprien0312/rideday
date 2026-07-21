"""Live smoke tests — hit the real websites. Skipped by default.

Run manually to confirm the real sites still parse:
    .venv/bin/pytest -m live -v
"""
import pytest

from lib.registry import PROVIDERS


@pytest.mark.live
@pytest.mark.parametrize("provider", PROVIDERS, ids=[p.key for p in PROVIDERS])
def test_live_provider_returns_events(provider):
    events = provider.fetch()
    assert len(events) >= 1, f"{provider.key} parsed 0 events — site may have changed"
    assert all(e.date_start and e.url for e in events)
    assert all(e.track for e in events)
