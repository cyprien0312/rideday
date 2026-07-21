"""Download the three ride-day listing pages into tests/fixtures/ for offline TDD.

Re-run this when a site changes structure and the adapter tests start failing,
then update the affected adapter + its expected test values.

Captured pages may embed third-party secrets (e.g. Google Maps API keys in map
iframes). We scrub those before saving so they never land in the repo — the
parsers don't use them anyway. See _sanitize().
"""
import re
from pathlib import Path

import requests

UA = "rideday-radar/0.1 (personal ride-day aggregator; contact: local)"
PAGES = {
    "champions_events.html": "https://championsridedays.com.au/events/",
    "pird_ride_days.html": "https://www.phillipislandridedays.com.au/pird-ride-days",
    "smsp_ride_days.html": "https://www.smsprd.com/smsprd-ride-days",
}

# Redact obvious third-party secrets from captured HTML before it hits disk.
_SECRET_PATTERNS = [
    (re.compile(r"AIza[0-9A-Za-z_-]{35}"), "REDACTED-GOOGLE-MAPS-KEY"),  # Google API keys
]


def _sanitize(html: str) -> str:
    for pattern, replacement in _SECRET_PATTERNS:
        html = pattern.sub(replacement, html)
    return html


def main() -> None:
    out = Path(__file__).resolve().parent.parent / "tests" / "fixtures"
    out.mkdir(parents=True, exist_ok=True)
    for name, url in PAGES.items():
        html = _sanitize(requests.get(url, headers={"User-Agent": UA}, timeout=30).text)
        (out / name).write_text(html, encoding="utf-8")
        print(f"{name}: {len(html)} bytes  <- {url}")


if __name__ == "__main__":
    main()
