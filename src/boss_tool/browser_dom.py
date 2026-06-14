from __future__ import annotations

from pathlib import Path
import re
import subprocess
from typing import Callable
from urllib.request import urlopen

from boss_tool.models import CandidateProfile, ChatMessage, ConversationSummary, ScanSnapshot


DEFAULT_DEBUG_PORT = 9222
BOSS_URL = "https://www.zhipin.com/web/geek/chat"
TIME_OR_DATE_PATTERN = re.compile(r"^(\d{1,2}:\d{2}|\d{2}月\d{2}日|昨天|今天|刚刚|周[一二三四五六日天])$")
NAME_PATTERN = re.compile(r"^[\u4e00-\u9fff]{1,5}(女士|先生)$")
CONTROL_TEXTS = {
    "搜索30天内的联系人",
    "全部",
    "未读",
    "新招呼",
    "更多",
    "AI筛选",
    "查看更多职位",
    "复制微信号",
    "发简历",
    "换电话",
    "换微信",
    "发送",
    "已读",
}


class BrowserDomSnapshotReader:
    def __init__(
        self,
        endpoint: str = f"http://127.0.0.1:{DEFAULT_DEBUG_PORT}",
        page_provider: Callable[[], list[object]] | None = None,
    ) -> None:
        self.endpoint = endpoint
        self.page_provider = page_provider

    def scan(self) -> ScanSnapshot:
        try:
            pages = self.page_provider() if self.page_provider else self._load_pages_from_cdp()
        except Exception as exc:
            snapshot = ScanSnapshot.empty()
            snapshot.diagnostics["warnings"] = [f"未连接到 Boss 网页 DOM: {exc}"]
            snapshot.diagnostics["capture_mode"] = "browser_dom"
            return snapshot

        page = self._pick_boss_page(pages)
        if page is None:
            snapshot = ScanSnapshot.empty()
            snapshot.diagnostics["warnings"] = ["未连接到 Boss 网页 DOM，请先启动专用浏览器并打开 Boss 消息页"]
            snapshot.diagnostics["capture_mode"] = "browser_dom"
            return snapshot

        title = _safe_page_title(page)
        try:
            text = extract_visible_text_from_page(page)
        except Exception as exc:
            snapshot = ScanSnapshot.empty()
            snapshot.window.title = title
            snapshot.diagnostics["warnings"] = [f"读取 Boss 网页 DOM 失败: {exc}"]
            snapshot.diagnostics["capture_mode"] = "browser_dom"
            return snapshot
        return build_snapshot_from_dom_text(text, title)

    def _load_pages_from_cdp(self) -> list[object]:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            browser = playwright.chromium.connect_over_cdp(self.endpoint)
            pages = [page for context in browser.contexts for page in context.pages]
            snapshots = []
            for page in pages:
                snapshots.append(_PageTextSnapshot.from_page(page))
            return snapshots

    @staticmethod
    def _pick_boss_page(pages: list[object]):
        for page in pages:
            title = _safe_page_title(page).lower()
            url = str(getattr(page, "url", "") or "").lower()
            if any(marker in title or marker in url for marker in ("zhipin", "boss直聘", "kanzhun")):
                return page
        return None


class _PageTextSnapshot:
    def __init__(self, title: str, url: str, text: str) -> None:
        self._title = title
        self.url = url
        self._text = text

    @classmethod
    def from_page(cls, page):
        return cls(_safe_page_title(page), str(getattr(page, "url", "") or ""), extract_visible_text_from_page(page))

    def title(self) -> str:
        return self._title

    def locator(self, _selector: str):
        return _TextLocator(self._text)


class _TextLocator:
    def __init__(self, text: str) -> None:
        self.text = text

    def inner_text(self, timeout: int = 0) -> str:
        return self.text


def start_dedicated_browser(
    port: int = DEFAULT_DEBUG_PORT,
    browser_finder: Callable[[], str] | None = None,
    process_launcher: Callable[[list[str]], object] | None = None,
    endpoint_checker: Callable[[str], bool] | None = None,
) -> str:
    endpoint = f"http://127.0.0.1:{port}"
    checker = endpoint_checker or is_debug_endpoint_available
    if checker(endpoint):
        return endpoint
    browser_path = (browser_finder or find_browser_executable)()
    user_data_dir = Path.home() / ".boss-insight-assistant" / "browser-profile"
    user_data_dir.mkdir(parents=True, exist_ok=True)
    args = [
        browser_path,
        f"--remote-debugging-port={port}",
        f"--user-data-dir={user_data_dir}",
        "--new-window",
        BOSS_URL,
    ]
    if process_launcher is None:
        subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        process_launcher(args)
    return endpoint


def is_debug_endpoint_available(endpoint: str) -> bool:
    try:
        with urlopen(f"{endpoint}/json/version", timeout=0.5) as response:
            return response.status == 200
    except Exception:
        return False


def find_browser_executable() -> str:
    candidates = [
        Path("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"),
        Path("C:/Program Files/Microsoft/Edge/Application/msedge.exe"),
        Path("C:/Program Files/Google/Chrome/Application/chrome.exe"),
        Path("C:/Program Files (x86)/Google/Chrome/Application/chrome.exe"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    raise FileNotFoundError("未找到 Edge 或 Chrome 浏览器")


def extract_visible_text_from_page(page) -> str:
    return page.locator("body").inner_text(timeout=1500).strip()


def build_snapshot_from_dom_text(text: str, title: str) -> ScanSnapshot:
    lines = _clean_lines(text)
    snapshot = ScanSnapshot.empty()
    snapshot.window.found = bool(lines)
    snapshot.window.title = title
    snapshot.diagnostics["capture_mode"] = "browser_dom"
    snapshot.diagnostics["is_web_boss"] = True
    snapshot.diagnostics["layout_mode"] = "browser_dom"
    snapshot.diagnostics["dom_line_count"] = len(lines)
    snapshot.raw_conversation_lines = lines
    snapshot.raw_chat_lines = lines
    snapshot.conversation_list = _parse_dom_conversations(lines)
    snapshot.current_candidate = _parse_dom_candidate(lines, snapshot.conversation_list)
    snapshot.current_messages = _parse_dom_messages(lines, snapshot.current_candidate.name)
    if snapshot.conversation_list:
        snapshot.conversation_list[0].selected = True
    if not (
        snapshot.conversation_list
        or snapshot.current_candidate.name
        or snapshot.current_messages
    ):
        snapshot.diagnostics.setdefault("warnings", []).append(
            "DOM已连接，但没有识别到候选人或聊天内容，请确认专用浏览器停留在Boss消息页"
        )
    return snapshot


def _parse_dom_conversations(lines: list[str]) -> list[ConversationSummary]:
    conversations: list[ConversationSummary] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if not NAME_PATTERN.match(line):
            index += 1
            continue
        if _is_current_header(lines, index):
            index += 1
            continue
        company_job = _join_until_time(lines, index + 1)
        time_index = index + 1 + len(company_job)
        if time_index >= len(lines) or not TIME_OR_DATE_PATTERN.match(lines[time_index]):
            index += 1
            continue
        last_message = _next_message_after_time(lines, time_index + 1)
        conversations.append(
            ConversationSummary(
                name=line,
                job_title=" ".join(company_job),
                last_message=last_message,
                time_label=lines[time_index],
                unread_count=0,
                source="browser_dom",
                confidence=0.88,
            )
        )
        index = time_index + 1
    return _dedupe_conversations(conversations)


def _parse_dom_candidate(lines: list[str], conversations: list[ConversationSummary]) -> CandidateProfile:
    for index, line in enumerate(lines):
        if NAME_PATTERN.match(line) and _is_current_header(lines, index):
            summary = []
            for item in lines[index + 1:index + 8]:
                if item in CONTROL_TEXTS or NAME_PATTERN.match(item):
                    continue
                summary.append(item)
            return CandidateProfile(
                name=line,
                summary_lines=summary[:6],
                source="browser_dom",
                confidence=0.88,
            )
    if conversations:
        return CandidateProfile(name=conversations[0].name, source="browser_dom", confidence=0.72)
    return CandidateProfile()


def _parse_dom_messages(lines: list[str], candidate_name: str) -> list[ChatMessage]:
    if not candidate_name:
        return []
    start = _message_start_index(lines, candidate_name)
    messages: list[ChatMessage] = []
    for line in lines[start:]:
        if line in CONTROL_TEXTS:
            continue
        if NAME_PATTERN.match(line):
            continue
        if TIME_OR_DATE_PATTERN.match(line):
            continue
        if _looks_like_job_or_company(line):
            continue
        if len(line) > 80 and " " not in line:
            continue
        messages.append(ChatMessage(speaker="候选人", text=line, source="browser_dom", confidence=0.82))
    return messages[-30:]


def _message_start_index(lines: list[str], candidate_name: str) -> int:
    if candidate_name:
        for index, line in enumerate(lines):
            if line == candidate_name and _is_current_header(lines, index):
                return min(len(lines), index + 4)
    markers = ("复制微信号", "换电话", "换微信")
    for index, line in enumerate(lines):
        if line in markers:
            return index + 1
    return 0


def _join_until_time(lines: list[str], start: int) -> list[str]:
    items: list[str] = []
    for line in lines[start:start + 5]:
        if TIME_OR_DATE_PATTERN.match(line):
            break
        if line in CONTROL_TEXTS or NAME_PATTERN.match(line):
            break
        items.append(line)
    return items


def _next_message_after_time(lines: list[str], start: int) -> str:
    for line in lines[start:start + 4]:
        if line in CONTROL_TEXTS:
            continue
        if TIME_OR_DATE_PATTERN.match(line) or NAME_PATTERN.match(line):
            continue
        return line.removeprefix("[已读]").strip()
    return ""


def _is_current_header(lines: list[str], index: int) -> bool:
    nearby = lines[index + 1:index + 6]
    return any(_looks_like_salary_or_city(item) for item in nearby)


def _looks_like_salary_or_city(text: str) -> bool:
    return bool(re.search(r"\d+\s*-\s*\d+\s*K", text, re.IGNORECASE)) or text in {"北京", "上海", "广州", "深圳", "西安", "武汉", "成都", "杭州"}


def _looks_like_job_or_company(text: str) -> bool:
    return any(marker in text for marker in ("人事", "HR", "招聘", "科技", "传媒", "信息", "公司", "主管", "专员"))


def _dedupe_conversations(items: list[ConversationSummary]) -> list[ConversationSummary]:
    seen: set[tuple[str, str, str]] = set()
    result: list[ConversationSummary] = []
    for item in items:
        key = (item.name, item.job_title, item.time_label)
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _clean_lines(text: str) -> list[str]:
    lines = []
    for raw in text.splitlines():
        line = re.sub(r"\s+", " ", raw).strip()
        if not line:
            continue
        compact_items = _split_compact_conversation_row(line)
        if compact_items:
            lines.extend(compact_items)
            continue
        if line in CONTROL_TEXTS:
            lines.append(line)
            continue
        lines.append(line.replace("｜", " ").strip())
    return lines


def _split_compact_conversation_row(line: str) -> list[str]:
    match = re.match(
        r"^(?P<name>[\u4e00-\u9fff]{1,5}(?:女士|先生))\s+"
        r"(?P<middle>.+?)\s+"
        r"(?P<time>\d{2}月\d{2}日|昨天|今天|刚刚|周[一二三四五六日天]|\d{1,2}:\d{2})"
        r"(?:\s+(?P<message>.+))?$",
        line,
    )
    if not match:
        return []
    items = [match.group("name")]
    middle = match.group("middle").strip()
    if middle:
        items.extend(_split_company_job(middle))
    items.append(match.group("time"))
    message = (match.group("message") or "").strip()
    if message:
        items.append(message.removeprefix("[已读]").strip())
    return [item for item in items if item]


def _split_company_job(text: str) -> list[str]:
    for marker in ("人事主管", "招聘专员", "人事", "HR", "行政人事", "人力资源主管"):
        if text.endswith(marker) and len(text) > len(marker):
            return [text[: -len(marker)].strip(), marker]
    return [text]


def _safe_page_title(page) -> str:
    try:
        return page.title()
    except Exception:
        return ""
