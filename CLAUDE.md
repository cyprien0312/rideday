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
- **日历订阅 `lib/ics.py`**:`render_ics` 跟 `parse` 一样是纯函数(同样 events + 同样 `now` → 字节一致),
  所以能离线测。`build_feeds` 按数据里出现的州动态分 feed + 一个 `all`,不硬编码州列表。
  全天事件 (`VALUE=DATE`,`DTEND` 排他要 +1 天),不碰时区。售罄的**保留**并在 SUMMARY 标 `[售罄]`,
  **不要**用 `STATUS:CANCELLED`——客户端会把事件藏掉。UID 复用 `event_uid`,订阅刷新才不会重复。
  写 .ics 属性一律走 `_escape` + `_fold`(75 octet 折行,别切断 UTF-8 字符)。

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

- **有 remote,要推**(`origin` = github.com/cyprien0312/rideday)。push 到 `main` 会触发 Actions 重建并发布 Pages。
  (原来这里写的是「本地 git,不推远程」—— 2026-07-21 加了 Pages 部署后就不成立了,2026-08-03 更正。)
- commit 作者 `cyprien0312 <fwuak15@outlook.com>`;单人项目直接进 `main`,不走 PR。
- `data/`、`.venv/`、`__pycache__/` 已 gitignore。fixture HTML 入库(测试要用)。

## 坑 / 故意没做的

**本质局限**(条件变了才值得重估):

- **列表页给不出精确时段**,所以日历事件一律全天。Champions 列表层完全没有时间,PIRD/SMSP 只有
  「7:00am」这种开始时间、没有结束时间。→ 重估条件:某站在列表页开始给出结束时间或明确时段。
- **订阅是全量替换**:某场从官网下架后,下次抓取它就不在 feed 里,已订阅日历里那条会消失。
  ics 里没有历史,也没法发 `METHOD:CANCEL`(那是邀请流,不是订阅流)。
- **PIRD/SMSP 没有 per-event URL**,订票是 JS 弹窗。日历项的 URL 只能指到列表页的 `#data-id` 锚点。

**只是没做**(don't assume it exists):

- 日历项**没有 VALARM 提醒**。
- **没有 VTIMEZONE 块** —— 全天事件不需要;哪天改成定时事件必须补上。
- **没有 per-provider 的 feed**(只按州分)。
- 站点改版只有「抓 0 条 = 失败」这一层,**数量骤降不报警**。
- 订阅链接的域名走 `RIDEDAY_BASE_URL`,默认硬编码 `https://cyprien0312.github.io/rideday`。
  换 repo 名 / 换域名要改这个环境变量,`scripts/build_static.py` 顶部。

## 短期记忆 / 规格 / 计划

**开工先读 `docs/STATE.md`**(此刻状态 + 待办)。
规格 `docs/superpowers/specs/2026-07-21-rideday-radar-design.md` · 计划 `docs/superpowers/plans/2026-07-21-rideday-radar.md`
