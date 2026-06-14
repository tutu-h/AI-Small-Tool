from boss_tool.capture import (
    build_window_not_found_warnings,
    is_probably_web_boss_window,
    title_matches_boss_window,
)


def test_title_matches_boss_window_for_browser_page() -> None:
    assert title_matches_boss_window("BOSS直聘 - Google Chrome", "BOSS") is True
    assert title_matches_boss_window("zhipin.com 沟通中 - Microsoft Edge", "BOSS") is True
    assert title_matches_boss_window("招聘沟通 - BOSS直聘网页版", "BOSS") is True
    assert title_matches_boss_window("BOSS直聘 - 招聘沟通 - Google Chrome", "BOSS直聘") is True


def test_title_does_not_match_irrelevant_window() -> None:
    assert title_matches_boss_window("微信", "BOSS") is False
    assert title_matches_boss_window("Boss Insight Assistant", "BOSS直聘") is False


def test_detects_probably_web_boss_window() -> None:
    assert is_probably_web_boss_window("BOSS直聘 - Google Chrome") is True
    assert is_probably_web_boss_window("zhipin.com - Microsoft Edge") is True
    assert is_probably_web_boss_window("Boss直聘客户端") is False


def test_build_window_not_found_warnings_are_actionable() -> None:
    warnings = build_window_not_found_warnings("BOSS")

    assert warnings[0] == "未找到 Boss 直聘窗口"
    assert "请先打开 Boss 直聘客户端或网页版消息页" in warnings[1]
    assert "当前窗口关键词：BOSS" in warnings[2]
