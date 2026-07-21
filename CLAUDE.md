# CLAUDE.md — rideday-radar

本地聚合澳洲摩托赛道日 (ride day) 的看板。个人自用。栈:Python + requests/BeautifulSoup + FastAPI + SQLite,风格对齐 `../catalyst-checker`。

## 核心约定

- **每站一个 adapter**:`lib/providers/<name>.py` 继承 `Provider`,只实现纯函数 `parse(html) -> list[Event]`;
  网络交给基类 `get_html`(带 tenacity 重试 + 礼貌 UA + 超时)。`fetch()` = `parse(get_html(base_url))`。
- **`parse` 必须是纯函数**:输入 HTML 字符串,输出 `list[Event]`。这样能用 `tests/fixtures/*.html` 离线测试,
  站点改版时立刻发现。**不要**在 adapter 里直接发网络请求。
- **共享解析器**:PIRD 与 SMSP 是同款订票平台,共用 `lib/providers/_ridedays_template.py`。
  通用小工具(`parse_date` / `parse_price` / `parse_status` / `STATE_RE`)在 `lib/providers/base.py`。
- **去重键 `event_uid`**:优先用订票 URL;URL 缺失/相同的站(PIRD/SMSP 无 per-event URL)用 `data-id`
  拼成唯一 anchor URL,避免 uid 碰撞。
- **容错隔离**:`scrape.run_all()` 对每个 provider 独立 try/except;抓 0 条视为疑似改版记为失败,
  不覆盖上次好数据。失败在页面顶部标警告。
- **展示口径**:只显示 `date_start >= 今天` 的活动;列表页无年份 → 解析时滚动到下一次出现。

## TDD

先写 fixture + 期望断言,再写解析实现。改 adapter → 跑 `.venv/bin/pytest`。
真站核对 → `.venv/bin/pytest -m live -v`(默认跳过)。

## 已知站点结构(便于改版时定位)

- **Champions**:`.bookride .bookinnerhead` 卡片;`.ride-date` 日期、`.ride-title a` 赛道+URL、
  `.ride-nsw` 州(括号内)、`.ride-filling` 状态、`.book-price` 价格(**促销取 `<ins>` 现价,非 `<del>` 原价**;
  标题含字面 `**markdown**` 需清洗)。
- **PIRD / SMSP**:`.event` 行;`.date h4` 日期、`.detail h3` 价格(`From $X` 取下限)、`.detail p` 时间、
  `.status button[data-id]` 状态+id。赛道/州为常量。

## Git

- 本地 git,**不推远程**;commit 作者 `cyprien0312 <fwuak15@outlook.com>`;单人项目直接进 `main`,不走 PR。
- `data/`、`.venv/`、`__pycache__/` 已 gitignore。fixture HTML 入库(测试要用)。

## 规格 / 计划

`docs/superpowers/specs/2026-07-21-rideday-radar-design.md` · `docs/superpowers/plans/2026-07-21-rideday-radar.md`
