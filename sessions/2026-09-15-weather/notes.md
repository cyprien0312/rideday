# 2026-09-15 · 天气接入

## 做了什么

用户给了 BOM 的 Broadford 预报页,问能不能接天气。侦察后改成 **Open-Meteo 管 0–16 天 + ERA5 十年同期兜底,
BOM 只做链接**(用户选的方案 2,理由见 spec §2)。

流程:brainstorming → spec → plan(10 task)→ subagent-driven 实现,每组 task 过 spec review + quality review。
16 个 commit,`00e26c4..HEAD`。

## review 里改掉的东西(plan 原文没有)

- `parse_forecast` 两种畸形 shape 会漏 `TypeError`,改成一律 `ValueError` 并带字段/天序号。
- forecast 与 archive 两份信封校验重复且已漂移一次 → 抽 `lib/weather/_openmeteo.daily_arrays`,stdlib-only。
- `refresh_weather` 用减法算成功数,传 generator 会在写库后炸 → 改成直接计数。
- 补了「失败地点保留旧行」「LED 出现 Open-Meteo」「API 对未知赛道给 null」三条 pinning 测试。
- `build_static.py` 的 `N/3 providers ok` 摘要会被 weather run 污染成 `4/3` → 限定到 provider key。
- 页脚不写死「2016–2025」,只写「十年同期平均」;hover 里保留年份并注释「与脚本 START/END 同步」。

## 验证

- `.venv/bin/pytest -q` → `114 passed, 4 deselected`
- `.venv/bin/pytest -m live -q` → `4 passed`(3 站 + Open-Meteo)
- `.venv/bin/python scripts/build_static.py` → `weather: ok=True locations=8 err=None; 101 events have weather`
- 浏览器看过 dist:三档颜色对、按雨排序对、hover/BOM 链接对、375px 宽不横滚。

## 没做 / 留着

天气不进 .ics;没有小时级;多日活动只看首日。见 CLAUDE.md「坑」和 STATE 待办 4、5。
