from boss_tool.browser_dom import (
    BrowserDomSnapshotReader,
    build_snapshot_from_dom_text,
    extract_visible_text_from_page,
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


def test_extract_visible_text_from_page_uses_body_text() -> None:
    assert extract_visible_text_from_page(FakePage("赵女士\n好的")) == "赵女士\n好的"


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
