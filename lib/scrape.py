from __future__ import annotations

import logging
from datetime import datetime

from lib.registry import PROVIDERS
from lib.store import Store

log = logging.getLogger("rideday.scrape")


def run_all(store: Store, providers=None) -> None:
    """Scrape every provider into the store. Each provider is isolated: one
    failing site never breaks the others, and its previous good data is kept."""
    providers = providers if providers is not None else PROVIDERS
    for p in providers:
        started = datetime.now().isoformat(timespec="seconds")
        try:
            events = p.fetch()
            if not events:
                raise ValueError("0 events parsed (possible site change)")
            store.upsert_events(events)
            store.record_run(p.key, ok=True, event_count=len(events), error=None,
                             started_at=started)
            log.info("scraped %s: %d events", p.key, len(events))
        except Exception as exc:  # isolate failures per provider
            store.record_run(p.key, ok=False, event_count=0, error=str(exc),
                             started_at=started)
            log.warning("scrape failed %s: %s", p.key, exc)
