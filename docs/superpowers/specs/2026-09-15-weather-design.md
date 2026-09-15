# rideday-radar — 天气接入设计 (Weather Design Spec)

**日期**: 2026-09-15
**状态**: Approved (brainstorming) → 待写实现计划
**作者**: cyprien0312

---

## 1. 目的

看板每一场活动都要有个天气参考,帮着决定去不去。用户给的起点是 BOM 的 Broadford 预报页
(`https://www.bom.gov.au/places/vic/broadford/forecast/`)。

## 2. 已确认的关键决策

1. **数据源:Open-Meteo,不解析 BOM。** BOM 页面能抓(curl + 浏览器 UA 得 200,`/places/` 不在
   robots.txt 禁区),结构也干净,但只给 7 天;用户要的是**所有场次**都有参考。Open-Meteo 免费、
   无 key、16 天预报、JSON,一个解析器管到底。BOM 的 JSON API 明写 "You must not use, copy or share it",不碰。
2. **BOM 只当链接**:每行天气格点开直达该赛道的 BOM 预报页。BOM 改版不会挂看板。
3. **16 天外用历史同期兜底**:任何源都没有 16 天外的预报。用 Open-Meteo 历史 API(ERA5)算每个赛道
   每个月的十年平均,存 JSON 进 repo。这样 125 场全部有数字。
4. **三档必须标清楚**:`预报`(≤ 7 天)/ `远期预报`(8–15 天,准确度低)/ `历史同期`(月平均)。
   不能让人把气候均值当预报看。
5. **`.ics` 不动**。用途是看板;要写进 DESCRIPTION 以后加,改动小。
6. **不做小时级,多日活动只看首日。**

## 3. 侦察结论

- BOM 地点页:看板里 8 个赛道全有,逐个 curl 过 200:
  `vic/broadford` `vic/cowes`(Phillip Island)`nsw/eastern-creek`(SMSP)`sa/tailem-bend`(The Bend)
  `sa/mallala` `qld/warwick`(Morgan Park)`wa/collie` `wa/wanneroo`。
- Open-Meteo forecast:`forecast_days=16`,`daily=weather_code,temperature_2m_max,temperature_2m_min,
  precipitation_sum,precipitation_probability_max,wind_speed_10m_max`,`timezone=<当地>` 让日期按当地划。
  实测 Broadford 返回 16 天(含今天)。许可 CC BY 4.0,页脚要署名。免费额度 10k 请求/天,
  我们 8 个/次、每 6 小时一次。
- Open-Meteo archive:`archive-api.open-meteo.com/v1/archive`,同样的 daily 字段,按日期区间拉。

## 4. 架构

```
lib/weather/
  locations.py   TrackLocation 表 + locate(track)
  forecast.py    DailyForecast, parse_forecast(纯), fetch_forecast(网络), WMO 码映射
  normals.py     Normal, compute_normals(纯), load_normals()
  normals.json   生成物,进 repo(8 地点 × 12 月)
  attach.py      WeatherView, weather_for(event, forecasts, normals, today)
  refresh.py     refresh_weather(store) —— 8 地点逐个抓,失败隔离,记 scrape_runs("weather")
scripts/build_climate_normals.py   手动跑,产出 normals.json
lib/store.py     加 forecasts 表 + upsert_forecasts / forecasts
app.py / scripts/build_static.py   run_all 之后调 refresh_weather;渲染时 attach
templates/index.html / static/*    「天气」列、Open-Meteo LED、页脚署名
```

`run_all` 不改,现有 `test_scrape` 不会碰网络。

### 4.1 地点表

```python
@dataclass(frozen=True)
class TrackLocation:
    key: str            # "broadford"
    name: str           # "Broadford"
    lat: float
    lon: float
    tz: str             # "Australia/Melbourne"
    bom_path: str       # "vic/broadford"
    match: tuple[str, ...]   # 小写子串,命中任一即匹配
```

| key | match | tz | bom_path |
|---|---|---|---|
| `broadford` | `broadford` | Australia/Melbourne | vic/broadford |
| `phillip_island` | `phillip island` | Australia/Melbourne | vic/cowes |
| `smsp` | `sydney motorsport` | Australia/Sydney | nsw/eastern-creek |
| `the_bend` | `the bend` | Australia/Adelaide | sa/tailem-bend |
| `mallala` | `mallala` | Australia/Adelaide | sa/mallala |
| `morgan_park` | `morgan park` | Australia/Brisbane | qld/warwick |
| `collie` | `collie` | Australia/Perth | wa/collie |
| `wanneroo` | `wanneroo` | Australia/Perth | wa/wanneroo |

坐标从 OSM 取,写死在表里。`locate(track)` 对 `track.lower()` 做子串匹配,没命中返回 `None`。

### 4.2 预报

- `DailyForecast(location_key, day: date, code: int, tmin, tmax, rain_mm, rain_prob: int, wind_kmh)`。
- `parse_forecast(location_key, json_text) -> list[DailyForecast]`:纯函数。`daily` 数组任一字段缺失或
  长度不齐 → 抛 `ValueError`(视为改版)。`null` 值容忍:该天字段为 `None`。
- `fetch_forecast(loc) -> list[DailyForecast]`:requests + tenacity(沿用 `providers/base.py` 的重试参数
  和 UA),超时 20s。
- WMO 码映射 `describe(code) -> (emoji, 中文)`:0 ☀️ 晴;1–2 🌤 少云;3 ☁️ 阴;45/48 🌫 雾;51–57 🌦 毛毛雨;
  61–67 🌧 雨;71–77 🌨 雪;80–82 🌦 阵雨;85–86 🌨 阵雪;95–99 ⛈ 雷暴;其它 `("", "")`。

### 4.3 历史同期

- `compute_normals(rows) -> dict[int, Normal]`:输入 `(day, tmax, tmin, precip_mm)` 序列,按月聚合:
  `tmax` 均值、`tmin` 均值、`rain_days_pct` = 日雨量 ≥ 1 mm 的天数比例,取整。`None` 跳过。
- `normals.json` 结构:`{"broadford": {"1": {"tmax": 27.3, "tmin": 12.1, "rain_days_pct": 18}, ...}, ...}`。
  顶层另有 `_meta: {source, period: "2016-01-01/2025-12-31", generated_at}`。
- `load_normals() -> dict[str, dict[int, Normal]]`:读同目录 JSON,文件缺失返回空 dict(不抛)。
- 脚本 `scripts/build_climate_normals.py`:逐地点拉 archive,调 `compute_normals`,写 JSON。手动跑。

### 4.4 存储

```sql
CREATE TABLE IF NOT EXISTS forecasts (
  location_key TEXT, day TEXT, code INTEGER, tmin REAL, tmax REAL,
  rain_mm REAL, rain_prob INTEGER, wind_kmh REAL, fetched_at TEXT,
  PRIMARY KEY (location_key, day)
);
```

- `upsert_forecasts(rows)`:同一事务里先 `DELETE WHERE day < today`,再逐行 upsert。
- `forecasts() -> dict[tuple[str, date], DailyForecast]`。

### 4.5 抓取流程

`refresh_weather(store, locations=LOCATIONS)`:逐地点 `fetch_forecast`,单个失败 catch 住继续;
成功的合并一次 `upsert_forecasts`;最后 `record_run("weather", ok=失败数==0, event_count=成功地点数,
error="; ".join(f"{key}: {exc}"))`。`app.do_refresh` 与 `build_static.main` 在 `run_all(...)` 之后调它。

### 4.6 三档匹配

```python
@dataclass
class WeatherView:
    tier: Literal["forecast", "outlook", "normal"]
    tier_label: str        # 预报 / 远期预报 / 9 月平均
    emoji: str; desc: str  # 历史同期档为空
    tmin: float | None; tmax: float | None
    rain_prob: int | None  # forecast/outlook: 降雨概率;normal: 雨天比例
    rain_mm: float | None; wind_kmh: float | None
    bom_url: str
```

`weather_for(event, forecasts, normals, today)`:
1. `loc = locate(event.track)`;`None` → 返回 `None`。
2. `delta = (event.date_start - today).days`;`row = forecasts.get((loc.key, event.date_start))`。
3. `row` 存在且 `delta <= 7` → `forecast`;`row` 存在且 `delta > 7` → `outlook`。
4. 否则 `normals[loc.key][event.date_start.month]` 存在 → `normal`,`tier_label = f"{month} 月平均"`。
5. 否则 `None`。

`today` 沿用 `date.today()`(和 `upcoming_events` 同口径)。

### 4.7 展示

表格列序:日期 / 赛道 / 州 / **天气** / 价格 / 卖票情况 / 链接。格子整体是 `<a href=bom_url target=_blank>`:

| tier | 主行 | 小字 | title(hover) |
|---|---|---|---|
| forecast | `⛅ 4–11° · 雨 30%` | 预报 | `多云 · 风 27 km/h · 雨量 0.4 mm · 点开看 BOM` |
| outlook | 同上 | 远期预报 | 同上 |
| normal | `15°/4° · 雨天 42%` | 9 月平均 | `2016–2025 同期平均 · 点开看 BOM` |
| 无 | `—` | | |

- `tr` 加 `data-rain`(rain_prob,无则 `-1`),表头 `th[data-sort=rain]` 复用现有排序。
- `outlook` 与 `normal` 用弱一档的颜色,forecast 正常。
- 顶部 runs 那排多一个 LED:`Open-Meteo · N 地点 · 时间`,失败标红。
- 页脚:`天气数据 Open-Meteo (CC BY 4.0) · 预报页 BOM`。
- `/api/events` 每条多 `weather: {tier, tmin, tmax, rain_prob, rain_mm, wind_kmh, desc, bom_url} | null`。

## 5. 容错

- 某地点 Open-Meteo 失败:该赛道退到历史同期(本地版若库里还有上次预报行则继续用),LED 标警告,
  活动数据不受影响。
- 8 个地点全失败:同上,只是全部退到历史同期。**不**因此让 build 失败。
- `normals.json` 缺地点 / 缺月:该行「—」。
- 赛道没匹配到地点:「—」。

## 6. 测试

| 文件 | 覆盖 |
|---|---|
| `tests/test_weather_locations.py` | fixture 里全部赛道字符串 `locate()` 都命中预期 key;`"Unknown Raceway"` → None |
| `tests/test_weather_forecast.py` | `openmeteo_broadford.json` fixture → 16 行、字段值;缺字段 → ValueError;`null` 容忍;`describe()` 边界码 |
| `tests/test_weather_normals.py` | `compute_normals` 合成 3 个月数据;`load_normals()` 读到 8 地点 × 12 月 |
| `tests/test_weather_attach.py` | 四档分支 + 没地点 + 缺 normals |
| `tests/test_store.py` | forecasts upsert / 读 / 过期清理 |
| `tests/test_app.py` | 页面出现「天气」列和 BOM 链接;api 带 `weather` |
| `tests/test_live.py` | Open-Meteo 真调一次(`-m live`) |

新依赖:无(requests / tenacity 已有)。
