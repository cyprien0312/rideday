# rideday-radar 🏁

一个本地看板,把澳洲各家摩托车赛道日 (ride day) 提供商的活动聚合到**一个页面**,免去逐个网站翻看。

每条活动显示:**日期 · 赛道 · 州 · 价格 · 卖票情况 · 订票链接**。页面可按列排序、按赛道/州/状态过滤,后台每 3 小时自动抓一次,也可手动「立即刷新」。

## 覆盖的站点

| provider | 名称 | 站点 |
|---|---|---|
| `champions` | Champions Ride Days | https://championsridedays.com.au/events/ |
| `phillip_island` | Phillip Island Ride Days (PIRD) | https://www.phillipislandridedays.com.au/pird-ride-days |
| `smsp` | Sydney Motorsport Park Ride Days | https://www.smsprd.com/smsprd-ride-days |

## 在线版 (GitHub Pages)

**https://cyprien0312.github.io/rideday/**

这是一个静态快照:GitHub Actions 每 6 小时(以及每次 push、手动触发)在云端跑一遍抓取,
生成把数据烤进去的静态页并发布到 Pages。静态版没有实时「立即刷新」按钮(纯静态无后端),
页面显示"更新于 …";想立刻刷新可在 repo 的 **Actions → Build & deploy → Run workflow** 手动触发。

本地实时版(带刷新按钮、可选任意刷新间隔)见下方「快速开始」——两种模式共用同一套 adapter。

## 订阅到日历 (Apple Calendar / Google Calendar)

每次发布同时生成一组 `.ics` 订阅源:**全量一个,每个州各一个**。在页面上点「订阅到日历」那排按钮即可,
或直接用下面的 webcal 链接:

| feed | 链接 |
|---|---|
| VIC | `webcal://cyprien0312.github.io/rideday/vic.ics` |
| NSW | `webcal://cyprien0312.github.io/rideday/nsw.ics` |
| QLD | `webcal://cyprien0312.github.io/rideday/qld.ics` |
| SA | `webcal://cyprien0312.github.io/rideday/sa.ics` |
| WA | `webcal://cyprien0312.github.io/rideday/wa.ics` |
| 全部 | `webcal://cyprien0312.github.io/rideday/all.ics` |

州的 feed 按当次抓到的数据动态生成——某个州这轮没有活动,就不会有那个文件。

**Apple Calendar**:点 webcal 链接会直接弹出「订阅日历」;或「文件 → 新建日历订阅」粘贴上面的 https 版链接。
建议把自动刷新设成「每天」。

口径:

- 每场是**全天事件**,不占用忙碌时间 (`TRANSP:TRANSPARENT`)。列表页的开始时间(如 PIRD 的 7:00am)
  写在备注里——各站列表层给的时间不统一,不适合当精确的 DTSTART。
- 已售罄的场次**保留**在日历里,标题标 `[售罄]`、快满标 `[快满]`,免得某天凭空消失。
  不用 `STATUS:CANCELLED`,因为不少客户端会直接把它藏掉。
- 事件 UID 用 `event_uid`,与页面去重键同源:重复刷新不会产生重复日历项。

本地实时版同样提供 `GET /calendar/<州>.ics`(例:http://127.0.0.1:8765/calendar/vic.ics),
主要用于测试和一次性导入——长期订阅还是用线上那份。

## 快速开始(本地实时版)

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
./scripts/run.sh            # 或: .venv/bin/python app.py
# 打开 http://127.0.0.1:8765
```

## 构建静态版(与 Pages 同款)

```bash
.venv/bin/python scripts/build_static.py   # 输出 dist/index.html + dist/*.ics + dist/static/
```

订阅链接里的域名来自 `RIDEDAY_BASE_URL`(默认 `https://cyprien0312.github.io/rideday`)。

首次启动会在后台抓一次(几秒),抓完刷新页面即可看到数据。之后后台每 3 小时自动刷新。

## 环境变量

| 变量 | 默认 | 说明 |
|---|---|---|
| `RIDEDAY_DB` | `data/events.db` | SQLite 缓存文件路径 |
| `RIDEDAY_INTERVAL_HOURS` | `3` | 后台自动抓取间隔(小时) |
| `RIDEDAY_PORT` | `8765` | Web 服务端口 |

## 卖票状态 (status)

列表层尽力而为:

- Champions 列表页有明确文字 → `open` (Available) / `filling_fast` (Filling Fast) / `sold_out` (Sold Out)
- PIRD / SMSP 列表页只有 "Book Now" → `open`;拿不到确切售罄信号时为 `unknown`

以各官网为准。

## 加一个新的赛道日站点

1. 在 `lib/providers/` 新建 `<name>.py`,继承 `Provider`,实现 `parse(html) -> list[Event]`
   (设 `key` / `name` / `base_url`;若与 PIRD/SMSP 同款订票模板,直接复用
   `lib/providers/_ridedays_template.py` 的 `parse_ridedays`)
2. 抓一份列表页 HTML 存到 `tests/fixtures/<name>.html`
3. 写 `tests/test_<name>.py`,用 fixture 断言解析结果
4. 在 `lib/registry.py` 的 `PROVIDERS` 里加一行

## 测试

```bash
.venv/bin/pytest              # 单测(离线,用 fixture)
.venv/bin/pytest -m live -v   # 联网 smoke:确认真站仍可抓
```

站点改版导致解析失败时,`scrape_runs` 会把该站标为失败、页面顶部标警告,其它站不受影响。
更新 fixture:`.venv/bin/python scripts/capture_fixtures.py`,再据实调整对应 adapter 与测试。

## 结构

```
app.py                  FastAPI: GET / (看板), GET /api/events, GET /calendar/<州>.ics,
                        POST /api/refresh, 后台调度
lib/models.py           Event dataclass + Status 枚举 + event_uid
lib/ics.py              纯函数:events -> .ics 文本 + 按州分 feed(离线可测)
lib/store.py            SQLite: upsert / upcoming 查询 / scrape_runs
lib/providers/          base.py(ABC + 共享解析) + 每站一个 adapter
lib/registry.py         已注册 provider 列表
lib/scrape.py           run_all():轮询所有 adapter,每站独立容错
templates/ static/      看板页面 + 前端排序/过滤 JS
tests/                  fixture + 单测 + 联网 smoke
```

数据只留本地,不外发。
