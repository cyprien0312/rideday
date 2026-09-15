"""Pick the weather tier for an event and pre-render the strings the
template shows. Pure: same inputs -> same WeatherView.

Tiers (by days from `today` to date_start):
  forecast  <= 7 and a forecast row exists
  outlook   > 7 and a forecast row exists (Open-Meteo gives 16 days; skill is low)
  normal    no forecast row -> 10-year monthly average from normals.json
Multi-day events use date_start only.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal

from lib.models import Event
from lib.weather.forecast import DailyForecast, describe
from lib.weather.locations import locate
from lib.weather.normals import Normal

FORECAST_MAX_DAYS = 7
Tier = Literal["forecast", "outlook", "normal"]
TIER_LABEL = {"forecast": "预报", "outlook": "远期预报"}


@dataclass(frozen=True)
class WeatherView:
    tier: Tier
    tier_label: str
    emoji: str
    desc: str
    tmin: float | None
    tmax: float | None
    rain_prob: int | None     # forecast/outlook: chance of rain; normal: % of rain days
    rain_mm: float | None
    wind_kmh: float | None
    bom_url: str

    @property
    def temp_text(self) -> str:
        if self.tmin is None or self.tmax is None:
            return "—"
        if self.tier == "normal":
            return f"{round(self.tmax)}°/{round(self.tmin)}°"
        return f"{round(self.tmin)}–{round(self.tmax)}°"

    @property
    def rain_text(self) -> str:
        pct = "—" if self.rain_prob is None else f"{self.rain_prob}%"
        return f"雨天 {pct}" if self.tier == "normal" else f"雨 {pct}"

    @property
    def hover(self) -> str:
        if self.tier == "normal":
            return "2016–2025 同期平均 · 点开看 BOM"  # keep in sync with scripts/build_climate_normals.START/END
        wind = "—" if self.wind_kmh is None else f"{round(self.wind_kmh)}"
        mm = "—" if self.rain_mm is None else f"{self.rain_mm:g}"
        head = f"{self.desc} · " if self.desc else ""
        return f"{head}风 {wind} km/h · 雨量 {mm} mm · 点开看 BOM"


def weather_for(event: Event, forecasts: dict[tuple[str, date], DailyForecast],
                normals: dict[str, dict[int, Normal]], today: date) -> WeatherView | None:
    loc = locate(event.track)
    if loc is None:
        return None
    day = event.date_start
    row = forecasts.get((loc.key, day))
    if row is not None:
        tier: Tier = "forecast" if (day - today).days <= FORECAST_MAX_DAYS else "outlook"
        emoji, desc = describe(row.code)
        return WeatherView(tier, TIER_LABEL[tier], emoji, desc, row.tmin, row.tmax,
                           row.rain_prob, row.rain_mm, row.wind_kmh, loc.bom_url)
    normal = normals.get(loc.key, {}).get(day.month)
    if normal is None:
        return None
    return WeatherView("normal", f"{day.month} 月平均", "", "", normal.tmin, normal.tmax,
                       normal.rain_days_pct, None, None, loc.bom_url)


def weather_map(events: list[Event], forecasts, normals, today: date | None = None
                ) -> dict[str, WeatherView]:
    """{event_uid: WeatherView} for every event that resolves to a tier."""
    today = today if today is not None else date.today()
    out = {}
    for e in events:
        w = weather_for(e, forecasts, normals, today)
        if w is not None:
            out[e.event_uid] = w
    return out
