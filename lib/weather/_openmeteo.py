"""Shared envelope validation for Open-Meteo JSON responses.

Stdlib only — no `requests`/`tenacity` — so importing `lib.weather.normals`
(which has no network of its own) doesn't transitively pull in the network
stack that `lib.weather.forecast` needs for `fetch_forecast`.
"""
from __future__ import annotations

import json


def daily_arrays(json_text: str, fields: tuple[str, ...], what: str) -> dict[str, list]:
    """Pure: validate an Open-Meteo response envelope and return its `daily`
    arrays (`time` + `fields`), all lists of equal length. Raises ValueError with
    `what` ("forecast"/"archive") and the offending field/length in the message."""
    try:
        data = json.loads(json_text)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{what} is not JSON: {exc}") from exc
    daily = data.get("daily") if isinstance(data, dict) else None
    if not isinstance(daily, dict) or "time" not in daily:
        raise ValueError(f"{what} JSON has no daily.time")
    missing = [f for f in fields if f not in daily]
    if missing:
        raise ValueError(f"{what} JSON missing daily fields: {missing}")
    for name in ("time", *fields):
        if not isinstance(daily[name], list):
            raise ValueError(f"{what} JSON field is not a list: {name}")
    n = len(daily["time"])
    ragged = [f"{name}={len(daily[name])} != time={n}" for name in fields
              if len(daily[name]) != n]
    if ragged:
        raise ValueError(f"{what} JSON arrays ragged: {', '.join(ragged)}")
    return {name: daily[name] for name in ("time", *fields)}
