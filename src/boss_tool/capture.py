from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image, ImageGrab

from boss_tool.config import AppConfig
from boss_tool.models import ScanSnapshot

try:
    from pywinauto import Desktop
except ImportError:  # pragma: no cover
    Desktop = None


@dataclass(slots=True)
class CapturedRegion:
    name: str
    box: tuple[int, int, int, int]
    image_bytes: bytes
    ui_texts: list[str]


class BossWindowCapture:
    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def scan(self) -> ScanSnapshot:
        snapshot = ScanSnapshot.empty()
        window = self._find_window()
        if window is None:
            snapshot.diagnostics["warnings"] = build_window_not_found_warnings(
                self.config.boss_window_keyword
            )
            return snapshot

        rectangle = window.rectangle()
        bounds = (rectangle.left, rectangle.top, rectangle.right, rectangle.bottom)
        snapshot.window.title = window.window_text()
        snapshot.window.found = True
        snapshot.window.bounds = bounds
        is_web_boss = is_probably_web_boss_window(snapshot.window.title)
        self.focus_window(window, snapshot)
        try:
            image = self.grab_image(bounds)
        except Exception as exc:
            snapshot.diagnostics["regions"] = {}
            snapshot.diagnostics.setdefault("warnings", []).append(
                f"窗口截图失败: {exc}"
            )
        else:
            snapshot.diagnostics["regions"] = segment_image(
                image,
                layout_mode="web" if is_web_boss else "desktop",
            )
        snapshot.diagnostics["ui_texts"] = self.collect_ui_texts(window)
        snapshot.diagnostics["capture_mode"] = "live_window"
        snapshot.diagnostics["is_web_boss"] = is_web_boss
        snapshot.diagnostics["layout_mode"] = "web" if is_web_boss else "desktop"
        return snapshot

    def grab_image(self, bounds: tuple[int, int, int, int]) -> Image.Image:
        return ImageGrab.grab(bbox=bounds, all_screens=True)

    def focus_window(self, window: Any, snapshot: ScanSnapshot) -> None:
        try:
            window.set_focus()
        except Exception as exc:
            snapshot.diagnostics.setdefault("warnings", []).append(
                f"激活 Boss 窗口失败: {exc}"
            )

    def collect_ui_texts(self, window: Any) -> list[str]:
        try:
            descendants = window.descendants()
        except Exception:
            return []
        texts: list[str] = []
        for item in descendants:
            try:
                text = item.window_text().strip()
            except Exception:
                continue
            if text:
                texts.append(text)
        return texts

    def _find_window(self) -> Any | None:
        if Desktop is None:
            return None
        try:
            desktop = Desktop(backend="uia")
            windows = desktop.windows()
        except Exception:
            return None
        keyword = self.config.boss_window_keyword.lower()
        for window in windows:
            try:
                title = window.window_text()
            except Exception:
                continue
            if title_matches_boss_window(title, keyword):
                return window
        return None


class ImageFileCapture:
    def __init__(self, image_path: str | Path) -> None:
        self.image_path = Path(image_path)

    def scan(self) -> ScanSnapshot:
        snapshot = ScanSnapshot.empty()
        if not self.image_path.exists():
            snapshot.diagnostics["warnings"] = [f"图片不存在: {self.image_path}"]
            return snapshot

        image = Image.open(self.image_path)
        is_web_boss = is_probably_web_boss_window(self.image_path.name)
        layout_mode = "web" if is_web_boss else "desktop"
        snapshot.window.title = self.image_path.name
        snapshot.window.found = True
        snapshot.window.bounds = (0, 0, image.size[0], image.size[1])
        snapshot.diagnostics["regions"] = segment_image(image, layout_mode=layout_mode)
        snapshot.diagnostics["ui_texts"] = []
        snapshot.diagnostics["capture_mode"] = "imported_image"
        snapshot.diagnostics["image_path"] = str(self.image_path)
        snapshot.diagnostics["is_web_boss"] = is_web_boss
        snapshot.diagnostics["layout_mode"] = layout_mode
        return snapshot


class FallbackCapture:
    def __init__(self, primary, fallback) -> None:
        self.primary = primary
        self.fallback = fallback
        self.config = getattr(fallback, "config", None)

    def scan(self) -> ScanSnapshot:
        primary_snapshot = self.primary.scan()
        if _has_useful_dom_snapshot(primary_snapshot):
            return primary_snapshot
        fallback_snapshot = self.fallback.scan()
        warnings = primary_snapshot.diagnostics.get("warnings", [])
        if warnings:
            fallback_snapshot.diagnostics.setdefault("warnings", []).extend(warnings)
        fallback_snapshot.diagnostics["dom_fallback_used"] = True
        return fallback_snapshot


def segment_image(
    image: Image.Image, layout_mode: str = "desktop"
) -> dict[str, CapturedRegion]:
    width, height = image.size
    if layout_mode == "web":
        region_boxes = {
            "conversation_list": (0, 0, int(width * 0.30), height),
            "candidate_header": (int(width * 0.30), 0, width, int(height * 0.20)),
            "chat_body": (int(width * 0.30), int(height * 0.17), width, height),
        }
    else:
        region_boxes = {
            "conversation_list": (0, 0, int(width * 0.39), height),
            "candidate_header": (int(width * 0.39), 0, width, int(height * 0.25)),
            "chat_body": (int(width * 0.39), int(height * 0.20), width, height),
        }
    captured: dict[str, CapturedRegion] = {}
    for name, region_box in region_boxes.items():
        region_image = image.crop(region_box)
        buffer = BytesIO()
        region_image.save(buffer, format="PNG")
        captured[name] = CapturedRegion(
            name=name,
            box=region_box,
            image_bytes=buffer.getvalue(),
            ui_texts=[],
        )
    return captured


def _has_useful_dom_snapshot(snapshot: ScanSnapshot) -> bool:
    return (
        snapshot.window.found
        and snapshot.diagnostics.get("capture_mode") == "browser_dom"
        and (
            bool(snapshot.conversation_list)
            or bool(snapshot.current_messages)
            or bool(snapshot.current_candidate.name)
        )
    )


def title_matches_boss_window(title: str, keyword: str) -> bool:
    lowered = title.lower()
    if "boss insight assistant" in lowered:
        return False
    keyword_lower = keyword.lower().strip()
    explicit_markers = ("boss直聘", "zhipin", "zhipin.com", "kanzhun", "看准")
    if any(marker in lowered for marker in explicit_markers):
        return True
    return bool(keyword_lower and keyword_lower in lowered and "直聘" in lowered)


def is_probably_web_boss_window(title: str) -> bool:
    lowered = title.lower()
    return any(marker in lowered for marker in ("chrome", "edge", "firefox", "zhipin.com"))


def build_window_not_found_warnings(keyword: str) -> list[str]:
    return [
        "未找到 Boss 直聘窗口",
        "请先打开 Boss 直聘客户端或网页版消息页，并保持窗口不要最小化",
        f"当前窗口关键词：{keyword or 'BOSS'}，如窗口标题不含该词可在左侧配置修改",
    ]
