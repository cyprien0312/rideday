from lib.keepalive import (
    DEFAULT_THRESHOLD_DAYS,
    GITHUB_INACTIVITY_LIMIT_DAYS,
    should_keepalive,
)

DAY = 86_400
NOW = 1_800_000_000  # 任意固定时刻:纯函数不该关心具体是哪天


def _aged(days: float) -> dict:
    return {"last_commit_ts": int(NOW - days * DAY), "now_ts": NOW}


def test_silent_repo_at_threshold_gets_a_keepalive():
    assert should_keepalive(**_aged(45), threshold_days=45) is True


def test_silent_repo_past_threshold_still_gets_one():
    # 错过一两班 schedule 之后补上,而不是「错过就算了」
    assert should_keepalive(**_aged(59), threshold_days=45) is True


def test_active_repo_is_left_alone():
    assert should_keepalive(**_aged(0), threshold_days=45) is False
    assert should_keepalive(**_aged(44), threshold_days=45) is False


def test_just_under_threshold_does_not_commit():
    # 44 天 23 小时:钉住「不足一天不向上取整」,否则每 6 小时会多推一堆空 commit
    assert should_keepalive(
        last_commit_ts=NOW - 44 * DAY - 23 * 3600, now_ts=NOW, threshold_days=45
    ) is False


def test_just_over_threshold_commits():
    assert should_keepalive(
        last_commit_ts=NOW - 45 * DAY - 1, now_ts=NOW, threshold_days=45
    ) is True


def test_commit_in_the_future_does_not_commit():
    # 时钟偏移或被改过的 committer date 不该触发 push
    assert should_keepalive(**_aged(-10), threshold_days=45) is False


def test_threshold_is_configurable():
    # workflow_dispatch 传 0 用来做一次强制的真实验证
    assert should_keepalive(**_aged(0), threshold_days=0) is True


def test_default_threshold_leaves_slack_before_github_disables():
    assert DEFAULT_THRESHOLD_DAYS < GITHUB_INACTIVITY_LIMIT_DAYS
    # 余量要够几班 schedule 连续失败
    assert GITHUB_INACTIVITY_LIMIT_DAYS - DEFAULT_THRESHOLD_DAYS >= 7
