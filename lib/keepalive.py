"""保活:让 GitHub 不要因为「repo 不活动」把定时 workflow 停用。

GitHub 在 repo 连续 60 天没有新 commit 后会停用整个 workflow
(`state` = `disabled_inactivity`),cron 和 push 都不再触发,而且历史 run 全是
success、不发任何告警。2026-11-24 这个 repo 就这么停更了 10 天,详见 CLAUDE.md
「运维坑」。

所以快到期时由 CI 自己推一个空 commit 把计时清零。要不要推是个纯函数,
只看「最后一次 commit 距今多少天」,所以能离线测;读 git、推 commit 那层留在
workflow 的 shell 里(跟 provider 的 `parse` / `get_html` 分工一致)。
"""

#: GitHub 的硬性上限:连续这么多天没有 commit 就停用 workflow。
GITHUB_INACTIVITY_LIMIT_DAYS = 60

#: 默认阈值。留 15 天余量,够几十班 6 小时 schedule 连续失败。
DEFAULT_THRESHOLD_DAYS = 45

_SECONDS_PER_DAY = 86_400


def should_keepalive(last_commit_ts: int, now_ts: int, threshold_days: int) -> bool:
    """最后一次 commit 已经过了 `threshold_days` 天就该推一个空 commit。

    两个时间戳都是 Unix 秒(`git log -1 --format=%ct` 给的就是这个)。
    不足一天向下取整 —— 否则临界那天每 6 小时会多推一堆空 commit。
    commit 时间在未来(时钟偏移、改过的 committer date)一律不推。
    """
    age_days = (now_ts - last_commit_ts) // _SECONDS_PER_DAY
    return age_days >= threshold_days


if __name__ == "__main__":  # pragma: no cover - workflow 用的薄壳
    import argparse
    import time

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--last-commit-ts", type=int, required=True)
    ap.add_argument("--threshold-days", type=int, default=DEFAULT_THRESHOLD_DAYS)
    args = ap.parse_args()
    verdict = should_keepalive(
        args.last_commit_ts, int(time.time()), args.threshold_days
    )
    print("true" if verdict else "false")
