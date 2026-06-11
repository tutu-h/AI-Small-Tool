# Boss Insight Assistant Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Windows desktop utility that scans the Boss Zhipin desktop client, extracts unread conversations and current chat content, falls back to a Bailian vision model for low-confidence regions, and lets the user configure model names and API keys in the GUI.

**Architecture:** Use a Python Tkinter desktop shell over service modules for settings, capture, OCR parsing, vision fallback, analysis, and monitoring. Keep the live desktop integration behind interfaces so deterministic tests can cover parsers and orchestration without a running Boss client.

**Tech Stack:** Python 3.12, Tkinter, Pillow, pywinauto, rapidocr-onnxruntime, requests, pytest

---

### Task 1: Project Skeleton And Settings

**Files:**
- Create: `D:\Project\AI Small Tool\pyproject.toml`
- Create: `D:\Project\AI Small Tool\src\boss_tool\__init__.py`
- Create: `D:\Project\AI Small Tool\src\boss_tool\config.py`
- Create: `D:\Project\AI Small Tool\tests\test_config.py`

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path

from boss_tool.config import AppConfig, ConfigStore


def test_config_store_round_trips_models_and_api_key(tmp_path: Path) -> None:
    store = ConfigStore(tmp_path / "settings.json")
    original = AppConfig(
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        api_key="secret",
        text_model="qwen-plus",
        vision_model="qwen-vl-ocr",
        monitor_interval_seconds=5,
    )

    store.save(original)
    loaded = store.load()

    assert loaded == original
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError` for `boss_tool.config`

- [ ] **Step 3: Write minimal implementation**

```python
from dataclasses import asdict, dataclass
import json
from pathlib import Path


@dataclass(slots=True)
class AppConfig:
    base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    api_key: str = ""
    text_model: str = "qwen-plus"
    vision_model: str = "qwen-vl-ocr"
    monitor_interval_seconds: int = 5


class ConfigStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> AppConfig:
        if not self.path.exists():
            return AppConfig()
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        return AppConfig(**payload)

    def save(self, config: AppConfig) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(asdict(config), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_config.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml src/boss_tool/__init__.py src/boss_tool/config.py tests/test_config.py
git commit -m "feat: add config persistence"
```

### Task 2: OCR Parsers

**Files:**
- Create: `D:\Project\AI Small Tool\src\boss_tool\models.py`
- Create: `D:\Project\AI Small Tool\src\boss_tool\parsers.py`
- Create: `D:\Project\AI Small Tool\tests\test_parsers.py`

- [ ] **Step 1: Write the failing test**

```python
from boss_tool.parsers import parse_conversation_lines


def test_parse_conversation_lines_extracts_unread_count_and_summary() -> None:
    lines = [
        "杨莹 自拍馆前台白结300-500+包吃住 14:38",
        "3",
        "女生比较喜欢的那种",
        "吴女士 自拍馆前台白结300-500+包吃住 14:11",
        "1",
        "地址在哪",
    ]

    conversations = parse_conversation_lines(lines)

    assert len(conversations) == 2
    assert conversations[0].name == "杨莹"
    assert conversations[0].unread_count == 3
    assert conversations[0].last_message == "女生比较喜欢的那种"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_parsers.py -v`
Expected: FAIL with `ImportError` or missing parser function

- [ ] **Step 3: Write minimal implementation**

```python
from dataclasses import dataclass


@dataclass(slots=True)
class ConversationSummary:
    name: str
    job_title: str
    last_message: str
    time_label: str
    unread_count: int


def parse_conversation_lines(lines: list[str]) -> list[ConversationSummary]:
    conversations: list[ConversationSummary] = []
    index = 0
    while index + 2 < len(lines):
        header = lines[index].strip()
        unread_line = lines[index + 1].strip()
        summary_line = lines[index + 2].strip()
        header_parts = header.split()
        if len(header_parts) >= 3 and unread_line.isdigit():
            conversations.append(
                ConversationSummary(
                    name=header_parts[0],
                    job_title=" ".join(header_parts[1:-1]),
                    time_label=header_parts[-1],
                    unread_count=int(unread_line),
                    last_message=summary_line,
                )
            )
            index += 3
            continue
        index += 1
    return conversations
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_parsers.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/boss_tool/models.py src/boss_tool/parsers.py tests/test_parsers.py
git commit -m "feat: add OCR text parsers"
```

### Task 3: Fallback Decision Logic

**Files:**
- Create: `D:\Project\AI Small Tool\src\boss_tool\fallback.py`
- Create: `D:\Project\AI Small Tool\tests\test_fallback.py`

- [ ] **Step 1: Write the failing test**

```python
from boss_tool.fallback import should_use_vision_fallback
from boss_tool.models import ScanSnapshot


def test_should_use_vision_fallback_when_messages_missing() -> None:
    snapshot = ScanSnapshot.empty()
    snapshot.raw_chat_lines = ["您好", "在吗"]

    assert should_use_vision_fallback(snapshot) is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_fallback.py -v`
Expected: FAIL with missing `ScanSnapshot` or `should_use_vision_fallback`

- [ ] **Step 3: Write minimal implementation**

```python
def should_use_vision_fallback(snapshot: ScanSnapshot) -> bool:
    if not snapshot.conversation_list:
        return True
    if snapshot.raw_chat_lines and not snapshot.current_messages:
        return True
    if not snapshot.current_candidate.name:
        return True
    return False
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_fallback.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/boss_tool/fallback.py tests/test_fallback.py
git commit -m "feat: add fallback decision rules"
```

### Task 4: Service Layer And GUI

**Files:**
- Create: `D:\Project\AI Small Tool\src\boss_tool\bailian.py`
- Create: `D:\Project\AI Small Tool\src\boss_tool\ocr.py`
- Create: `D:\Project\AI Small Tool\src\boss_tool\capture.py`
- Create: `D:\Project\AI Small Tool\src\boss_tool\pipeline.py`
- Create: `D:\Project\AI Small Tool\src\boss_tool\monitor.py`
- Create: `D:\Project\AI Small Tool\src\boss_tool\gui.py`
- Create: `D:\Project\AI Small Tool\src\boss_tool\app.py`

- [ ] **Step 1: Write the failing integration-style tests**

```python
from boss_tool.pipeline import BossInsightPipeline
from boss_tool.models import ScanSnapshot


class FakeCapture:
    def scan(self) -> ScanSnapshot:
        return ScanSnapshot.empty()


class FakeAnalyzer:
    def analyze(self, snapshot: ScanSnapshot):
        return {"current_chat_summary": "summary"}


def test_pipeline_returns_analysis_dict() -> None:
    pipeline = BossInsightPipeline(
        capture_service=FakeCapture(),
        ocr_service=None,
        vision_service=None,
        analyzer=FakeAnalyzer(),
    )

    result = pipeline.run_scan()

    assert result.analysis["current_chat_summary"] == "summary"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests -v`
Expected: FAIL with missing pipeline or snapshot definitions

- [ ] **Step 3: Write minimal implementation**

```python
class BossInsightPipeline:
    def __init__(self, capture_service, ocr_service, vision_service, analyzer) -> None:
        self.capture_service = capture_service
        self.ocr_service = ocr_service
        self.vision_service = vision_service
        self.analyzer = analyzer

    def run_scan(self):
        snapshot = self.capture_service.scan()
        snapshot.analysis = self.analyzer.analyze(snapshot)
        return snapshot
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/boss_tool/bailian.py src/boss_tool/ocr.py src/boss_tool/capture.py src/boss_tool/pipeline.py src/boss_tool/monitor.py src/boss_tool/gui.py src/boss_tool/app.py
git commit -m "feat: add desktop workflow"
```

### Task 5: Documentation And Verification

**Files:**
- Modify: `D:\Project\AI Small Tool\README.md`

- [ ] **Step 1: Write the failing verification expectation**

```text
The README must explain setup, dependencies, configuration, and how to run the desktop tool.
```

- [ ] **Step 2: Run verification to confirm the gap**

Run: `Get-Content README.md`
Expected: Existing README is too small and does not explain usage

- [ ] **Step 3: Write minimal implementation**

```markdown
# AI Small Tool

Boss直聘桌面识别与AI建议工具。

## 功能

- 自动连接 Boss 直聘桌面客户端
- 本地 OCR 提取会话列表和聊天内容
- 低置信度区域调用百炼视觉模型兜底
- 使用百炼文本模型生成摘要、优先级和回复建议
- GUI 内填写模型名和 API Key

## 运行

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e .[dev]
python -m boss_tool.app
```
```

- [ ] **Step 4: Run verification to confirm it passes**

Run: `Get-Content README.md`
Expected: README contains setup and run instructions

- [ ] **Step 5: Commit**

```bash
git add README.md
git commit -m "docs: add setup and usage guide"
```
