"""Open-Meteo daily forecast: pure JSON -> DailyForecast rows.

Same contract as the ride-day providers: `parse_forecast` is a pure function
tested against `tests/fixtures/openmeteo_*.json`; the network lives only in
`fetch_forecast`. Open-Meteo returns up to 16 days (today included), local
dates because we pass `timezone=<location tz>`.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from lib.providers.base import UA
from lib.weather.locations import TrackLocation

DAILY_FIELDS = ("weather_code", "temperature_2m_max", "temperature_2m_min",
                "precipitation_sum", "precipitation_probability_max",
                "wind_speed_10m_max")


@dataclass(frozen=True)
class DailyForecast:
    location_key: str
    day: date
    code: int | None
    tmin: float | None
    tmax: float | None
    rain_mm: float | None
    rain_prob: int | None
    wind_kmh: float | None


def parse_forecast(location_key: str, json_text: str) -> list[DailyForecast]:
    """Pure: Open-Meteo /v1/forecast JSON -> one row per day. Raises ValueError
    if the shape is off (treated as an API change by the caller)."""
    try:
        data = json.loads(json_text)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"forecast is not JSON: {exc}") from exc
    daily = data.get("daily") if isinstance(data, dict) else None
    if not isinstance(daily, dict) or "time" not in daily:
        raise ValueError("forecast JSON has no daily.time")
    missing = [f for f in DAILY_FIELDS if f not in daily]
    if missing:
        raise ValueError(f"forecast JSON missing daily fields: {missing}")
    for name in ("time", *DAILY_FIELDS):
        if not isinstance(daily[name], list):
            raise ValueError(f"forecast JSON field is not a list: {name}")
    n = len(daily["time"])
    ragged = [f"{name}={len(daily[name])} != time={n}" for name in DAILY_FIELDS
              if len(daily[name]) != n]
    if ragged:
        raise ValueError(f"forecast JSON arrays ragged: {', '.join(ragged)}")

    rows = []
    for i, day_text in enumerate(daily["time"]):
        try:
            code = daily["weather_code"][i]
            prob = daily["precipitation_probability_max"][i]
            rows.append(DailyForecast(
                location_key=location_key,
                day=date.fromisoformat(day_text),
                code=int(code) if code is not None else None,
                tmin=daily["temperature_2m_min"][i],
                tmax=daily["temperature_2m_max"][i],
                rain_mm=daily["precipitation_sum"][i],
                rain_prob=int(prob) if prob is not None else None,
                wind_kmh=daily["wind_speed_10m_max"][i],
            ))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"forecast day {i} ({day_text!r}) malformed: {exc}") from exc
    return rows


# WMO 4677 weather codes as Open-Meteo emits them, collapsed to what a rider cares about.
_WMO: list[tuple[int, int, str, str]] = [
    (0, 0, "☀️", "晴"),
    (1, 2, "🌤", "少云"),
    (3, 3, "☁️", "阴"),
    (45, 48, "🌫", "雾"),
    (51, 57, "🌦", "毛毛雨"),
    (61, 67, "🌧", "雨"),
    (71, 77, "🌨", "雪"),
    (80, 82, "🌦", "阵雨"),
    (85, 86, "🌨", "阵雪"),
    (95, 99, "⛈", "雷暴"),
]


def describe(code: int | None) -> tuple[str, str]:
    """WMO code -> (emoji, 中文). Unknown/None -> ("", "")."""
    if code is None:
        return "", ""
    for lo, hi, emoji, desc in _WMO:
        if lo <= code <= hi:
            return emoji, desc
    return "", ""


FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
FORECAST_DAYS = 16


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8), reraise=True)
def get_forecast_json(loc: TrackLocation) -> str:
    resp = requests.get(FORECAST_URL, params={
        "latitude": loc.lat, "longitude": loc.lon,
        "daily": ",".join(DAILY_FIELDS),
        "timezone": loc.tz, "forecast_days": FORECAST_DAYS,
    }, headers={"User-Agent": UA}, timeout=20)
    resp.raise_for_status()
    return resp.text


def fetch_forecast(loc: TrackLocation) -> list[DailyForecast]:
    return parse_forecast(loc.key, get_forecast_json(loc))
