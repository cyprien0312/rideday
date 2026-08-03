# STATE — rideday-radar

> 真相源。开工先读这里:此刻是什么状态 + 还剩什么。
> 长期结论进 `docs/notes/`,决策进 `docs/decisions.md`,过程进 `sessions/`。

**最后更新:2026-08-03**

## 此刻状态

三个 provider 全绿,离线单测 43 条 + 联网 smoke 3 条全过。

| provider | 状态 | 本轮抓到 |
|---|---|---|
| `champions` | ok | 91 |
| `phillip_island` (PIRD) | ok | 16 |
| `smsp` | ok | 18 |

- 线上:https://cyprien0312.github.io/rideday/ ,GitHub Actions 每 6 小时 + 每次 push 重建并发布。
- 本地实时版:`./scripts/run.sh` → http://127.0.0.1:8765
- **日历订阅(2026-08-03 新增)**:每次发布同时生成 `all.ics` + 每个州一个 `.ics`。
  本轮:all(125) / nsw(18) / qld(24) / sa(42) / vic(33) / wa(8)。
  实现在 `lib/ics.py`(纯函数,离线可测),口径见 README「订阅到日历」一节。

## 待办

| # | 待办 | 备注 |
|---|---|---|
| 1 | 用 Apple Calendar 实际订阅一次 | 线上文件本身已验过(见下),**只剩在「日历」App 里真点一次 `webcal://cyprien0312.github.io/rideday/vic.ics`**,确认能加进去、事件显示正常。这步只能在你自己机器上做。 |
| 2 | 决定要不要加 VALARM 提醒 | 现在订阅项没有任何提醒。加的话得决定提前多久,以及要不要只给「有票」的场次加 |
| 3 | 站点改版监控 | 现在只有「抓 0 条 = 失败」这一层。某站从 20 条掉到 3 条不会报警 |

### 已关闭

- ~~把 VIC 的活动变成 Apple Calendar 订阅~~ —— 2026-08-03 关闭。
  凭据:`.venv/bin/pytest -q` → `43 passed, 3 deselected`;
  `.venv/bin/python scripts/build_static.py` → `wrote 6 calendar feeds: all.ics(125), nsw.ics(18), qld.ics(24), sa.ics(42), vic.ics(33), wa.ics(8)`;
  6 份 .ics 全部通过 `icalendar` 库的严格 RFC 5545 解析,UID 无重复、DTEND > DTSTART、无超 75 octet 行。
  最终做的是**每州一个 + 全量**(用户选),不止 VIC。
- ~~线上验证发布出来的 feed~~ —— 2026-08-03 关闭。凭据:Actions run 30788182849 success;
  `curl -so /dev/null -w '%{http_code} %{content_type}' https://cyprien0312.github.io/rideday/vic.ics`
  → `200 text/calendar`(**content-type 对是 webcal 能订阅的关键**);vic 33 / all 125 / nsw 18 个 VEVENT。

## 相关文件

- 规格:`docs/superpowers/specs/2026-07-21-rideday-radar-design.md`
- 计划:`docs/superpowers/plans/2026-07-21-rideday-radar.md`
- 约定与坑:`CLAUDE.md`
