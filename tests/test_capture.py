from pathlib import Path

from PIL import Image

from boss_tool.capture import BossWindowCapture, ImageFileCapture, segment_image
from boss_tool.config import AppConfig


def test_segment_image_creates_expected_regions() -> None:
    image = Image.new("RGB", (1000, 800), color="white")

    regions = segment_image(image)

    assert set(regions) == {"conversation_list", "candidate_header", "chat_body"}
    assert regions["conversation_list"].box == (0, 0, 390, 800)


def test_image_file_capture_marks_snapshot_found(tmp_path: Path) -> None:
    image_path = tmp_path / "boss-sample.png"
    Image.new("RGB", (640, 480), color="white").save(image_path)

    snapshot = ImageFileCapture(image_path).scan()

    assert snapshot.window.found is True
    assert snapshot.window.title == "boss-sample.png"
    assert snapshot.diagnostics["capture_mode"] == "imported_image"


def test_segment_image_supports_web_layout() -> None:
    image = Image.new("RGB", (1200, 900), color="white")

    regions = segment_image(image, layout_mode="web")

    assert set(regions) == {"conversation_list", "candidate_header", "chat_body"}
    assert regions["conversation_list"].box == (0, 0, 360, 900)


def test_image_file_capture_uses_web_layout_for_zhipin_named_screenshot(tmp_path: Path) -> None:
    image_path = tmp_path / "zhipin.com-chat.png"
    Image.new("RGB", (1200, 900), color="white").save(image_path)

    snapshot = ImageFileCapture(image_path).scan()

    assert snapshot.diagnostics["is_web_boss"] is True
    assert snapshot.diagnostics["layout_mode"] == "web"
    assert snapshot.diagnostics["regions"]["conversation_list"].box == (0, 0, 360, 900)


class FakeRectangle:
    left = 0
    top = 0
    right = 100
    bottom = 100


class FakeWindow:
    def __init__(self) -> None:
        self.set_focus_called = False

    def rectangle(self):
        return FakeRectangle()

    def window_text(self):
        return "Boss直聘客户端"

    def descendants(self):
        return []

    def set_focus(self):
        self.set_focus_called = True


def test_window_capture_returns_warning_when_screenshot_fails() -> None:
    capture = BossWindowCapture(AppConfig())
    window = FakeWindow()
    capture._find_window = lambda: window
    capture.grab_image = lambda _bounds: (_ for _ in ()).throw(RuntimeError("screen denied"))

    snapshot = capture.scan()

    assert window.set_focus_called is True
    assert snapshot.window.found is True
    assert snapshot.diagnostics["regions"] == {}
    assert "窗口截图失败: screen denied" in snapshot.diagnostics["warnings"]


def test_window_capture_keeps_scanning_when_focus_fails() -> None:
    class FocusFailingWindow(FakeWindow):
        def set_focus(self):
            raise RuntimeError("focus denied")

    capture = BossWindowCapture(AppConfig())
    window = FocusFailingWindow()
    capture._find_window = lambda: window
    capture.grab_image = lambda _bounds: Image.new("RGB", (100, 100), color="white")

    snapshot = capture.scan()

    assert snapshot.window.found is True
    assert "激活 Boss 窗口失败: focus denied" in snapshot.diagnostics["warnings"]
    assert set(snapshot.diagnostics["regions"]) == {
        "conversation_list",
        "candidate_header",
        "chat_body",
    }
