# STATE — rideday-radar

> 短期记忆。开工先读这里:此刻是什么状态 + 还剩什么。
> 长期结论进 `docs/notes/`,决策进 `docs/decisions.md`,过程进 `sessions/`。

**最后更新:2026-11-24**

## 此刻状态

三个 provider + 天气全绿,离线单测 122 条 + 联网 smoke 4 条全过。
定时发布有 keepalive 兜底(2026-11-24 加,见下)。

| provider | 状态 | 本轮抓到 |
|---|---|---|
| `champions` | ok | 23 |
| `phillip_island` (PIRD) | ok | 23 |
| `smsp` | ok | 31 |
| `weather` (Open-Meteo) | ok | 8 地点 |

> **2026-11-24 事故:线上停更 10 天,已修。** 2026-09-15 之后没再 commit,整 60 天后
> (2026-11-14)GitHub 按「repo 不活动」把 workflow 自动停用(`state=disabled_inactivity`),
> cron 和 push 都不再触发,看板冻在 11-14 的快照、首页挂着已经跑完的场次。
> **代码没坏**:离线 114 条、联网 smoke 4 条、三站真实抓取全过,解析器行为与 11-14 一致
> (旧页 89 格 − 已过期 12 场 = 77,和本轮新抓的 77 吻合)。
> 修法:`gh workflow enable` + 推一次 commit(清零 60 天计时)。详见 CLAUDE.md「运维坑」。
> champions 67 → 23 是官网自己的挂牌量变化,不是掉量(站点真实 23 张卡,无分页)。

- 线上:https://cyprien0312.github.io/rideday/ ,GitHub Actions 每 6 小时 + 每次 push 重建并发布。
- 本地实时版:`./scripts/run.sh` → http://127.0.0.1:8765
- **日历订阅(2026-08-03 新增)**:每次发布同时生成 `all.ics` + 每个州一个 `.ics`。
  本轮:all(77) / nsw(31) / sa(15) / vic(27) / wa(4)。**这轮没有 `qld.ics`**(QLD 暂时没有未来场次,
  feed 按数据里出现的州动态生成)—— 之前订过 qld 的客户端会拿到 404,见待办 8。
  实现在 `lib/ics.py`(纯函数,离线可测),口径见 README「订阅到日历」一节。
- **天气(2026-09-15 新增)**:每行一个天气格,三档 预报(≤7 天)/ 远期预报(8–15 天)/ N 月平均,
  点开是该赛道的 BOM 预报页。本轮 77 场全部有天气:forecast 8 / outlook 10 / normal 59。
  实现在 `lib/weather/`,口径见 README「天气」一节;**BOM 只做链接不解析**(见 CLAUDE.md)。
  线上已发布(Actions run 34938788380 success)。

## 待办

| # | 待办 | 备注 |
|---|---|---|
| 1 | 用 Apple Calendar 实际订阅一次 | 线上文件本身已验过(见下),**只剩在「日历」App 里真点一次 `webcal://cyprien0312.github.io/rideday/vic.ics`**,确认能加进去、事件显示正常。这步只能在你自己机器上做。 |
| 2 | 决定要不要加 VALARM 提醒 | 现在订阅项没有任何提醒。加的话得决定提前多久,以及要不要只给「有票」的场次加 |
| 3 | 站点改版监控 | 现在只有「抓 0 条 = 失败」这一层。某站从 20 条掉到 3 条不会报警 |
| 5 | 天气要不要写进 .ics DESCRIPTION | 改动小(`lib/ics.py` 加一行描述)。看板用一阵子再决定 |
| 6 | 天气 review 遗留小项(都不阻塞) | ① 本地版旧预报行没有「年龄」提示:Open-Meteo 连挂几天,几天前的行仍显示「预报」,`fetched_at` 存了但没读回;② 7/8 地点成功时 LED 只写「抓取失败」,不显示计数;③ `DailyForecast` 定义在 `forecast.py`,让 `lib.store` 传递依赖 requests,挪到 `lib/models.py` 可切断 |
| 8 | 州 feed 会整个消失 | 某州暂时没有未来场次时(这轮的 QLD),那个 `.ics` 根本不生成,已订阅的客户端拿 404 而不是空日历。要么对已知州一律出空 feed,要么接受。设计上是「不硬编码州列表」的代价 |

### 已关闭

- ~~四个 action 还在 Node 20 上(原待办 9)~~ —— 2026-11-24 关闭,顺带多升了一个。
  `checkout` v4→v7、`setup-python` v5→v7、`configure-pages` v5→v6、
  `upload-pages-artifact` v3→v5、`deploy-pages` v4→v5(这个本来没报警告,但也落后一个大版本)。
  原先报的 `upload-artifact@v4` 不是工作流里直接写的,是 `upload-pages-artifact@v3` 的**传递依赖**,
  v5 内部已把它钉到 v7.0.0,所以一并消失。
  **跨大版本读 release notes 查到两条,都处理了**:
  ① `upload-pages-artifact` v4 起 dotfile 默认不进 artifact,而 `build_static.py:101` 会写
  `dist/.nojekyll` → 显式加 `include-hidden-files: true`,升级前后线上那个文件都是 `200 / 0 bytes`;
  ② `checkout` v6 改成「凭据存到单独文件」,而 keepalive 的 `git push` 正依赖它 →
  强制 dispatch 实测仍能推(run 45296885104,`0617bb3..b425254  HEAD -> main`)。
  **凭据**:push run 45296696364 `build/deploy success`、`keepalive skipped`、**Node 20 警告消失**;
  站点 11:23 新鲜、77 场、0 警告,5 个 feed 与 `static/*` 全 200。

- ~~防 `schedule` 再被 GitHub 停用(原待办 7)~~ —— 2026-11-24 关闭,做的是 keepalive(方案 ①)。
  `deploy.yml` 加 `keepalive` job,快到 45 天时自己推一个空 commit 清零 60 天计时;
  判断逻辑 `lib/keepalive.py` 是纯函数,`tests/test_keepalive.py` 8 条钉住临界值
  (44 天 23 小时不推、45 天整推、未来时间戳不推、默认阈值对 60 天留 15 天余量)。
  **凭据(强制 dispatch 实测,不是推理)**:`gh workflow run deploy.yml -f keepalive_threshold_days=0`
  → run 45294254680 三个 job 全 success,日志里 `要不要推:true` → `5e8f07e..7891e7d  HEAD -> main`
  **push 成功**,证明 job 级 `contents: write` 压得过 repo 级 `default_workflow_permissions: read`;
  skip-ci 标记也确认有效,但凭据不是 `7891e7d`(bot 那次 `GITHUB_TOKEN` 推的 push 本身就不触发
  workflow,两条规则分不开),而是 `e512891` —— 那次我**本人**推,只因为 message 正文里
  引用了这个标记来解释代码,整个构建就没出现过 run。坑已记进 CLAUDE.md。
  **仍未验证**:bot commit 是否真的重置 GitHub 的 60 天计时 —— 只能等 ~2026-01-23 那个窗口。

- ~~线上验证天气列~~ —— 2026-09-15 关闭。凭据:push `9cf437a` 触发 Actions run 34938788380 → `success`;
  `curl -s https://cyprien0312.github.io/rideday/ | tr -s '\n ' ' ' | grep -o 'Open-Meteo · [0-9]* 地点'` → `Open-Meteo · 8 地点`;
  `grep -c 'class="wx-forecast\|class="wx-outlook\|class="wx-normal'` → `101`(= 事件数)。
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
- 天气规格:`docs/superpowers/specs/2026-09-15-weather-design.md`
- 天气计划:`docs/superpowers/plans/2026-09-15-weather.md`
- 天气过程:`sessions/2026-09-15-weather/notes.md`
- 约定与坑:`CLAUDE.md`
