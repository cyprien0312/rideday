"""Regenerate lib/weather/normals.json from Open-Meteo's ERA5 archive.

One request per track location (10 years of daily rows each), then the pure
`compute_normals`. Run rarely — the output is committed:

    .venv/bin/python scripts/build_climate_normals.py
"""
from __future__ import annotations

import json
import sys
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import requests

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

from lib.providers.base import UA  # noqa: E402
from lib.weather.locations import LOCATIONS  # noqa: E402
from lib.weather.normals import (ARCHIVE_FIELDS, NORMALS_PATH, RAIN_DAY_MM,  # noqa: E402
                                 compute_normals, parse_archive)

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
START, END = "2016-01-01", "2025-12-31"


def main() -> int:
    out: dict = {"_meta": {
        "source": "Open-Meteo ERA5 archive (CC BY 4.0)",
        "period": f"{START}/{END}",
        "rain_day_threshold_mm": RAIN_DAY_MM,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
    }}
    for loc in LOCATIONS:
        resp = requests.get(ARCHIVE_URL, params={
            "latitude": loc.lat, "longitude": loc.lon,
            "start_date": START, "end_date": END,
            "daily": ",".join(ARCHIVE_FIELDS), "timezone": loc.tz,
        }, headers={"User-Agent": UA}, timeout=60)
        resp.raise_for_status()
        rows = parse_archive(resp.text)
        normals = compute_normals(rows)
        out[loc.key] = {str(m): asdict(v) for m, v in normals.items()}
        print(f"{loc.key:16} {len(rows)} days -> {len(normals)} months")
        time.sleep(1)   # be polite; the archive endpoint is slower than forecast
    NORMALS_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n",
                            encoding="utf-8")
    print(f"wrote {NORMALS_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
