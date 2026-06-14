from boss_tool.browser_dom import (
    BrowserDomSnapshotReader,
    _join_visible_text_rows,
    build_snapshot_from_dom_text,
    extract_visible_text_from_page,
    start_dedicated_browser,
)


class FakeLocator:
    def __init__(self, text: str) -> None:
        self.text = text

    def inner_text(self, timeout: int = 0) -> str:
        return self.text


class FakePage:
    url = "https://www.zhipin.com/web/geek/chat"

    def __init__(self, text: str) -> None:
        self.text = text

    def locator(self, _selector: str) -> FakeLocator:
        return FakeLocator(self.text)

    def title(self) -> str:
        return "BOSS直聘 - 招聘沟通"


class FakeStructuredPage(FakePage):
    def __init__(self, text: str, structured_text: str) -> None:
        super().__init__(text)
        self.structured_text = structured_text

    def evaluate(self, _script: str) -> str:
        return self.structured_text


def test_extract_visible_text_from_page_uses_body_text() -> None:
    assert extract_visible_text_from_page(FakePage("赵女士\n好的")) == "赵女士\n好的"


def test_extract_visible_text_from_page_prefers_structured_visible_nodes() -> None:
    page = FakeStructuredPage(
        text="整页文本兜底",
        structured_text="赵女士\n鼎昌电子信息技术\n06月09日\n好的",
    )

    assert extract_visible_text_from_page(page) == "赵女士\n鼎昌电子信息技术\n06月09日\n好的"


def test_join_visible_text_rows_keeps_repeated_list_text() -> None:
    rows = [
        {"text": "赵女士", "top": 10, "left": 20},
        {"text": "人事", "top": 20, "left": 20},
        {"text": "好的", "top": 30, "left": 20},
        {"text": "郭先生", "top": 40, "left": 20},
        {"text": "人事", "top": 50, "left": 20},
        {"text": "好的", "top": 60, "left": 20},
    ]

    assert _join_visible_text_rows(rows) == "赵女士\n人事\n好的\n郭先生\n人事\n好的"


def test_build_snapshot_from_dom_text_extracts_conversations_and_chat() -> None:
    text = """
搜索30天内的联系人
全部
未读
赵女士
鼎昌电子信息技术
人事
06月09日
[已读]好的
郭先生
武汉利正源科技
人事主管
06月09日
[已读]好的
文女士
优联传媒
HR
昨天
帅哥，问你个问题呗
赵女士
Java中级开发工程师
8-10K
西安
赵女士的微信号
linfei928907
好的
我加啦
你稍等
"""

    snapshot = build_snapshot_from_dom_text(text, "BOSS直聘 - 招聘沟通")

    assert snapshot.window.found is True
    assert snapshot.diagnostics["capture_mode"] == "browser_dom"
    assert snapshot.conversation_list[0].name == "赵女士"
    assert snapshot.conversation_list[0].job_title == "鼎昌电子信息技术 人事"
    assert snapshot.conversation_list[2].name == "文女士"
    assert snapshot.conversation_list[2].last_message == "帅哥，问你个问题呗"
    assert snapshot.current_candidate.name == "赵女士"
    assert [message.text for message in snapshot.current_messages[-3:]] == [
        "好的",
        "我加啦",
        "你稍等",
    ]


def test_build_snapshot_from_dom_text_splits_compact_conversation_rows() -> None:
    text = """
赵女士 鼎昌电子信息技术 人事 06月09日 [已读]好的
郭先生 武汉利正源科技 人事主管 06月09日 [已读]好的
文女士 优联传媒 HR 昨天 帅哥，问你个问题呗
赵女士
Java中级开发工程师
8-10K
西安
好的
"""

    snapshot = build_snapshot_from_dom_text(text, "BOSS直聘 - 招聘沟通")

    assert [item.name for item in snapshot.conversation_list] == [
        "赵女士",
        "郭先生",
        "文女士",
    ]
    assert snapshot.conversation_list[0].job_title == "鼎昌电子信息技术 人事"
    assert snapshot.conversation_list[2].last_message == "帅哥，问你个问题呗"


def test_build_snapshot_from_dom_text_extracts_unread_count_from_separate_badge_line() -> None:
    text = """
赵女士
鼎昌电子信息技术
人事
2
06月09日
[未读]好的
郭先生
武汉利正源科技
人事主管
未读
昨天
好的
赵女士
Java中级开发工程师
8-10K
西安
好的
"""

    snapshot = build_snapshot_from_dom_text(text, "BOSS直聘 - 招聘沟通")

    assert snapshot.conversation_list[0].unread_count == 2
    assert snapshot.conversation_list[0].job_title == "鼎昌电子信息技术 人事"
    assert snapshot.conversation_list[0].last_message == "好的"
    assert snapshot.conversation_list[1].unread_count == 1


def test_build_snapshot_from_dom_text_extracts_unread_count_from_compact_badge() -> None:
    text = """
赵女士 鼎昌电子信息技术 人事 3 06月09日 [未读]好的
郭先生 武汉利正源科技 人事主管 未读 昨天 好的
赵女士 Java中级开发工程师
8-10K
西安
好的
"""

    snapshot = build_snapshot_from_dom_text(text, "BOSS直聘 - 招聘沟通")

    assert [item.name for item in snapshot.conversation_list[:2]] == ["赵女士", "郭先生"]
    assert snapshot.conversation_list[0].unread_count == 3
    assert snapshot.conversation_list[0].last_message == "好的"
    assert snapshot.conversation_list[1].unread_count == 1
    assert snapshot.conversation_list[1].job_title == "武汉利正源科技 人事主管"


def test_build_snapshot_from_dom_text_warns_when_no_message_content() -> None:
    snapshot = build_snapshot_from_dom_text("首页\n职位\n公司\n登录", "BOSS直聘")

    assert snapshot.window.found is True
    assert snapshot.conversation_list == []
    assert "DOM已连接，但没有识别到候选人或聊天内容，请确认专用浏览器停留在Boss消息页" in snapshot.diagnostics["warnings"]


def test_dom_reader_returns_snapshot_from_active_boss_page() -> None:
    reader = BrowserDomSnapshotReader(page_provider=lambda: [FakePage("赵女士\n人事\n06月09日\n好的")])

    snapshot = reader.scan()

    assert snapshot.window.title == "BOSS直聘 - 招聘沟通"
    assert snapshot.diagnostics["capture_mode"] == "browser_dom"


def test_dom_reader_returns_not_found_when_no_boss_page() -> None:
    class NonBossPage(FakePage):
        url = "https://example.com"

        def title(self) -> str:
            return "Example"

    reader = BrowserDomSnapshotReader(page_provider=lambda: [NonBossPage("hello")])

    snapshot = reader.scan()

    assert snapshot.window.found is False
    assert "未连接到 Boss 网页 DOM" in snapshot.diagnostics["warnings"][0]


def test_start_dedicated_browser_reuses_running_debug_browser() -> None:
    calls = []

    endpoint = start_dedicated_browser(
        port=9223,
        browser_finder=lambda: "msedge.exe",
        process_launcher=lambda _args: calls.append(_args),
        endpoint_checker=lambda _endpoint: True,
    )

    assert endpoint == "http://127.0.0.1:9223"
    assert calls == []


def test_start_dedicated_browser_launches_detached_browser_profile() -> None:
    calls = []

    endpoint = start_dedicated_browser(
        port=9224,
        browser_finder=lambda: "msedge.exe",
        process_launcher=lambda args: calls.append(args),
        endpoint_checker=lambda _endpoint: False,
    )

    assert endpoint == "http://127.0.0.1:9224"
    args = calls[0]
    assert "--no-first-run" in args
    assert "--no-default-browser-check" in args
    assert any(arg.startswith("--remote-debugging-port=9224") for arg in args)
    assert any(arg.startswith("--user-data-dir=") for arg in args)
