"""Climate normals: per-location, per-month averages used when no forecast
exists (events more than 16 days out).

`normals.json` next to this file is generated once by
scripts/build_climate_normals.py from Open-Meteo's ERA5 archive and committed.
`compute_normals` / `parse_archive` are pure so the script stays thin.
"""
from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from statistics import mean

from lib.weather._openmeteo import daily_arrays

NORMALS_PATH = Path(__file__).with_name("normals.json")
RAIN_DAY_MM = 1.0          # a day with >= 1 mm counts as a rain day
ARCHIVE_FIELDS = ("temperature_2m_max", "temperature_2m_min", "precipitation_sum")

DailyRow = tuple[date, float | None, float | None, float | None]   # (day, tmax, tmin, precip_mm)


@dataclass(frozen=True)
class Normal:
    tmax: float | None
    tmin: float | None
    rain_days_pct: int | None


def parse_archive(json_text: str) -> list[DailyRow]:
    """Pure: Open-Meteo /v1/archive JSON -> (day, tmax, tmin, precip) rows."""
    daily = daily_arrays(json_text, ARCHIVE_FIELDS, "archive")
    rows = []
    for i, day_text in enumerate(daily["time"]):
        try:
            rows.append((date.fromisoformat(day_text),
                         daily["temperature_2m_max"][i],
                         daily["temperature_2m_min"][i],
                         daily["precipitation_sum"][i]))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"archive day {i} ({day_text!r}) malformed: {exc}") from exc
    return rows


def compute_normals(rows: list[DailyRow]) -> dict[int, Normal]:
    """Pure: daily rows -> {month: Normal}. None values are skipped per field."""
    tmax: dict[int, list[float]] = defaultdict(list)
    tmin: dict[int, list[float]] = defaultdict(list)
    rain: dict[int, list[bool]] = defaultdict(list)
    for day, hi, lo, mm in rows:
        m = day.month
        if hi is not None:
            tmax[m].append(hi)
        if lo is not None:
            tmin[m].append(lo)
        if mm is not None:
            rain[m].append(mm >= RAIN_DAY_MM)
    out = {}
    for m in sorted(set(tmax) | set(tmin) | set(rain)):
        out[m] = Normal(
            tmax=round(mean(tmax[m]), 1) if tmax[m] else None,
            tmin=round(mean(tmin[m]), 1) if tmin[m] else None,
            rain_days_pct=round(100 * sum(rain[m]) / len(rain[m])) if rain[m] else None,
        )
    return out


def load_normals(path: Path = NORMALS_PATH) -> dict[str, dict[int, Normal]]:
    """{location_key: {month: Normal}}. Missing file -> {} (weather is optional).
    A malformed file raises on purpose: the shipped file is committed and
    guarded by test_shipped_normals_cover_all_locations_and_months, so a bad
    file here is a bug to fix, not something to swallow silently."""
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    out: dict[str, dict[int, Normal]] = {}
    for key, months in data.items():
        if key.startswith("_"):
            continue
        out[key] = {int(m): Normal(v.get("tmax"), v.get("tmin"), v.get("rain_days_pct"))
                    for m, v in months.items()}
    return out
