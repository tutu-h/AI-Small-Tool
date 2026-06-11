from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(slots=True)
class WindowInfo:
    title: str = ""
    found: bool = False
    bounds: tuple[int, int, int, int] | None = None
    captured_at: str = ""


@dataclass(slots=True)
class ConversationSummary:
    name: str
    job_title: str
    last_message: str
    time_label: str
    unread_count: int = 0
    selected: bool = False
    source: str = "ocr"
    confidence: float = 0.0


@dataclass(slots=True)
class CandidateProfile:
    name: str = ""
    summary_lines: list[str] = field(default_factory=list)
    source: str = "ocr"
    confidence: float = 0.0


@dataclass(slots=True)
class ChatMessage:
    speaker: str
    text: str
    time_label: str = ""
    source: str = "ocr"
    confidence: float = 0.0


@dataclass(slots=True)
class ScanSnapshot:
    window: WindowInfo = field(default_factory=WindowInfo)
    conversation_list: list[ConversationSummary] = field(default_factory=list)
    current_candidate: CandidateProfile = field(default_factory=CandidateProfile)
    current_messages: list[ChatMessage] = field(default_factory=list)
    analysis: dict[str, object] = field(default_factory=dict)
    diagnostics: dict[str, object] = field(default_factory=dict)
    raw_conversation_lines: list[str] = field(default_factory=list)
    raw_chat_lines: list[str] = field(default_factory=list)
    raw_candidate_lines: list[str] = field(default_factory=list)

    @classmethod
    def empty(cls) -> "ScanSnapshot":
        snapshot = cls()
        snapshot.window.captured_at = datetime.now().isoformat(timespec="seconds")
        return snapshot
