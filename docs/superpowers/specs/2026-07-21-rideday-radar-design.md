# rideday-radar — 设计文档 (Design Spec)

**日期**: 2026-07-21
**状态**: Approved (brainstorming) → 待写实现计划
**作者**: cyprien0312

---

## 1. 目的 (Purpose)

把澳洲各家摩托车赛道日 (ride day) 提供商的活动信息聚合到**一个本地看板**,免去逐个网站翻看的麻烦。个人自用工具。

每条活动要能看到:**时间、赛道、价格、卖票情况、URL**。

初期覆盖三家,架构要能低成本扩展到"澳洲所有赛道日站点":

| provider key | 名称 | 起始 URL |
|---|---|---|
| `champions` | Champions Ride Days | https://championsridedays.com.au/events/ |
| `phillip_island` | Phillip Island Ride Days (PIRD) | https://www.phillipislandridedays.com.au/pird-ride-days |
| `smsp` | Sydney Motorsport Park Ride Days | https://www.smsprd.com/smsprd-ride-days |

## 2. 已确认的关键决策 (Decisions)

1. **查看方式**:本地 Web 服务(浏览器访问 localhost 看实时页面)。
2. **抓取时机**:后台定时(默认每 3 小时)抓一次写本地缓存;页面秒开读缓存;页面上有「立即刷新」按钮手动触发重抓。
3. **卖票状态精度**:列表层**尽力而为**。列表页能拿到的就拿(Champions 有 `Available` / `Filling Fast` 等文字);PIRD / SMSP 列表页只有 `Book Now`,拿不到确切售罄信号时状态标 `unknown`。**不**逐个活动点进详情页(暂不做,留作后续可选增强)。
4. **现成工具调研结论**:没有覆盖这些澳洲小众自建站的现成开源项目;通用抓取框架(如 Scrapy)对 3 个站属过度工程。采用**轻量自定义抓取器 + 每站一个 adapter**,复用成熟库,不引重框架。

## 3. 站点侦察结论 (Recon)

三个站的活动数据都在**静态 HTML** 里,无需 headless 浏览器(初期):

- **Champions**:WooCommerce 风格商品卡,含 日期 / 赛道+州 / 价格 / 状态文字(`Available`、`Filling Fast`…),每卡链到 `/product/...` 详情页。
- **PIRD**:自建订票系统,列表含 日期 / 开始时间 / 价格;赛道固定 = Phillip Island GP Circuit (VIC);状态列表层只有 `Book Now`。
- **SMSP**:自建模板,列表含 日期 / 时间 / 价格(常见 `From $X`);赛道固定 = Sydney Motorsport Park (NSW);状态列表层只有 `Book Now`。

> ⚠️ 站点结构随时可能改版。解析要写得防御性强,并用 fixture 测试兜底(见 §8)。若将来某站改成 JS 动态渲染,再单独给该 adapter 加 `requests-html` / Playwright fallback,不影响其它站。

## 4. 架构 (Architecture)

```
rideday-radar/
├── app.py                     # FastAPI 应用: 路由 + 启动时挂 APScheduler
├── lib/
│   ├── __init__.py
│   ├── models.py              # Event dataclass, Status 枚举
│   ├── store.py               # SQLite: upsert / 查询 / scrape_runs 记录
│   ├── registry.py            # 已注册 provider 列表
│   ├── scrape.py              # run_all(): 轮询 adapter → 写 store → 记录每站结果
│   └── providers/
│       ├── __init__.py
│       ├── base.py            # Provider ABC/Protocol: key, name, fetch() -> list[Event]
│       ├── champions.py
│       ├── phillip_island.py
│       └── smsp.py
├── templates/
│   └── index.html             # Jinja2 看板页
├── static/
│   ├── app.js                 # 原生 JS: 表头排序 / 州·赛道·价格过滤 / 刷新按钮
│   └── style.css
├── tests/
│   ├── fixtures/              # 各站列表页 HTML 快照
│   │   ├── champions_events.html
│   │   ├── pird_ride_days.html
│   │   └── smsp_ride_days.html
│   ├── test_champions.py
│   ├── test_phillip_island.py
│   ├── test_smsp.py
│   └── test_store.py
├── data/
│   └── events.db              # SQLite (gitignored)
├── requirements.txt
├── pyproject.toml
├── .gitignore
├── README.md
└── CLAUDE.md
```

**技术栈**:Python 3.12 · `requests` + `BeautifulSoup4` + `lxml`(解析)· `tenacity`(重试)· `FastAPI` + `uvicorn`(web)· `APScheduler`(定时)· `Jinja2`(模板)· stdlib `sqlite3`(存储)· 前端原生 JS(不引框架)。全部对齐 `catalyst-checker` 现有习惯。

## 5. 数据模型 (Data Model)

`Event` (dataclass):

| 字段 | 类型 | 说明 |
|---|---|---|
| `provider` | str | provider key,如 `champions` |
| `provider_name` | str | 展示名,如 `Champions Ride Days` |
| `event_uid` | str | 稳定去重键;默认 = `sha1(provider + '|' + url)`,url 缺失时退化为 `provider+date+track` |
| `title` | str | 活动标题原文 |
| `track` | str | 赛道/场地名 |
| `state` | str \| None | 澳洲州缩写 (VIC/WA/SA/NSW/…),尽力解析 |
| `date_start` | date (ISO) | 活动日期(多日活动的开始) |
| `date_end` | date \| None | 多日活动的结束(单日为 None) |
| `start_time` | str \| None | 开始时间原文(如 `7:00am`),仅展示 |
| `price_aud` | float \| None | 数值价格;`From $X` 取下限;用于排序 |
| `price_display` | str | 价格原文(如 `From $365`、`$220.00`) |
| `status` | enum | `open` / `filling_fast` / `sold_out` / `unknown` |
| `status_raw` | str \| None | 站点原始状态文字 |
| `url` | str | 订票/详情链接(绝对 URL) |
| `first_seen` | datetime | 首次抓到的时间 |
| `last_seen` | datetime | 最近一次抓到的时间 |

**存储**:SQLite,表 `events`(主键 `event_uid`,upsert:存在则更新 `last_seen`/价格/状态,不存在则插入并置 `first_seen`)。表 `scrape_runs`(每次每 provider 一行:`provider`、`started_at`、`finished_at`、`ok`(bool)、`event_count`、`error`)——页面据此显示每站"上次更新 / 失败"。

**看板显示口径**:只显示 `date_start >= 今天` **且** 属于该 provider **最近一次成功抓取**(`ok=true`)所见集合的活动。某 provider 抓取失败时,继续显示它上一次成功抓取的数据,并在页面顶部标 stale。

## 6. 数据流 (Data Flow)

1. **启动**:`app.py` 起 FastAPI,`APScheduler` 注册周期任务(默认每 3h)调用 `scrape.run_all()`;并在启动时先跑一次(若缓存为空)。
2. **抓取**:`run_all()` 遍历 `registry` 里每个 provider,各自 `fetch()` → 返回 `list[Event]` → `store.upsert_events()`,同时写 `scrape_runs`。**每个 provider 独立 try/except**,一个失败不影响其它。
3. **展示**:`GET /` 从 `store` 读"今天及以后"的活动 + 每站抓取状态 → Jinja2 渲染 `index.html`。前端 JS 负责排序/过滤(纯客户端,无需再请求)。
4. **手动刷新**:`POST /api/refresh` 触发一次 `run_all()`(带去抖/加锁,避免并发重复抓);完成后前端刷新页面或重取数据。

## 7. 容错 & 礼貌抓取 (Resilience & Politeness)

- **隔离**:adapter 之间互不影响;解析异常/网络异常都被捕获并记入 `scrape_runs.error`。
- **重试**:`tenacity` 对网络请求做少量指数退避重试;整体超时保护。
- **礼貌**:低频抓取(默认 3h)、正常 `User-Agent`、请求超时、手动刷新加去抖;上线前查各站 `robots.txt` 并遵守。
- **隐私**:所有数据只留本地 SQLite,不外发任何第三方。
- **降级**:某站解析结果为 0 条时视为疑似改版,记为失败(不覆盖上次好数据),页面标警告。

## 8. 测试策略 (Testing) — TDD

- **Fixture 驱动的 adapter 单测**:把每站列表页 HTML 存成 `tests/fixtures/*.html`;`test_<provider>.py` 用 fixture 喂给 adapter 的解析函数,断言产出的 `Event` 列表(条数、日期解析、价格解析、状态映射、URL 绝对化)。离线可跑,站点改版时能立刻发现。
- **`test_store.py`**:upsert 幂等性、`first_seen` 不被覆盖、`last_seen` 更新、"今天及以后"查询过滤正确。
- **可选联网 smoke 测试**(`@pytest.mark.live`,默认跳过):真实抓取每站,断言 `> 0` 条且关键字段非空——用于人工确认真站仍可抓、结构未大改。
- 遵循 TDD:先写 fixture + 期望断言,再写解析实现。

## 9. 非目标 / YAGNI (Out of Scope)

- 不做逐活动详情页抓取(卖票状态只到列表层)。
- 不做用户账号、通知/邮件推送、日历导出(可作为后续增强)。
- 不做 headless 浏览器渲染(除非某站改版成必须)。
- 不做公网部署;仅本地 localhost。
- 不引入前端框架、ORM、重型抓取框架。

## 10. 后续可扩展点 (Future, 非本次)

- 加更多澳洲赛道日 provider(每个 = 一个 adapter 文件 + registry 一行)。
- 卖票状态深挖:对 PIRD/SMSP 逐活动抓详情页拿 sold out / spots left。
- "新活动 / 快售罄"通知(邮件或本地)。
- 导出 iCal / 加入日历。

## 11. Git / 交付约定

- 本地 git,私有,**不推远程**(除非另行要求)。
- commit 作者:`cyprien0312 <fwuak15@outlook.com>`。
- 单人项目,直接提交到 `main`,不走 PR。
- 布局 / 风格对齐 `catalyst-checker`(`lib/`、`tests/`、`requirements.txt`、`CLAUDE.md`)。
