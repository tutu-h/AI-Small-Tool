from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from boss_tool.storage import atomic_write_text
from boss_tool.models import (
    CandidateProfile,
    ChatMessage,
    ConversationSummary,
    ScanSnapshot,
    WindowInfo,
)


def snapshot_to_dict(snapshot: ScanSnapshot) -> dict[str, Any]:
    return {
        "window": asdict(snapshot.window),
        "candidate": asdict(snapshot.current_candidate),
        "conversations": [asdict(item) for item in snapshot.conversation_list],
        "current_messages": [asdict(item) for item in snapshot.current_messages],
        "analysis": snapshot.analysis,
        "diagnostics": _serializable_diagnostics(snapshot.diagnostics),
        "raw": {
            "conversation_lines": snapshot.raw_conversation_lines,
            "candidate_lines": snapshot.raw_candidate_lines,
            "chat_lines": snapshot.raw_chat_lines,
        },
    }


def snapshot_from_dict(data: dict[str, Any]) -> ScanSnapshot:
    snapshot = ScanSnapshot.empty()
    window = data.get("window", {})
    snapshot.window = WindowInfo(
        title=window.get("title", ""),
        found=bool(window.get("found", False)),
        bounds=_tuple_or_none(window.get("bounds")),
        captured_at=window.get("captured_at", ""),
    )
    candidate = data.get("candidate", {})
    snapshot.current_candidate = CandidateProfile(
        name=candidate.get("name", ""),
        summary_lines=list(candidate.get("summary_lines", [])),
        source=candidate.get("source", "ocr"),
        confidence=float(candidate.get("confidence", 0.0) or 0.0),
    )
    snapshot.conversation_list = [
        ConversationSummary(
            name=item.get("name", ""),
            job_title=item.get("job_title", ""),
            last_message=item.get("last_message", ""),
            time_label=item.get("time_label", ""),
            unread_count=int(item.get("unread_count", 0) or 0),
            selected=bool(item.get("selected", False)),
            source=item.get("source", "ocr"),
            confidence=float(item.get("confidence", 0.0) or 0.0),
        )
        for item in data.get("conversations", [])
    ]
    snapshot.current_messages = [
        ChatMessage(
            speaker=item.get("speaker", ""),
            text=item.get("text", ""),
            time_label=item.get("time_label", ""),
            source=item.get("source", "ocr"),
            confidence=float(item.get("confidence", 0.0) or 0.0),
        )
        for item in data.get("current_messages", [])
    ]
    snapshot.analysis = dict(data.get("analysis", {}))
    snapshot.diagnostics = dict(data.get("diagnostics", {}))
    raw = data.get("raw", {})
    snapshot.raw_conversation_lines = list(raw.get("conversation_lines", []))
    snapshot.raw_candidate_lines = list(raw.get("candidate_lines", []))
    snapshot.raw_chat_lines = list(raw.get("chat_lines", []))
    return snapshot


def snapshot_to_markdown(snapshot: ScanSnapshot) -> str:
    lines = [
        "# Boss 识别结果",
        "",
        f"- 来源：{snapshot.window.title or '未知'}",
        f"- 时间：{snapshot.window.captured_at or '未知'}",
        f"- 当前候选人：{snapshot.current_candidate.name or '未识别'}",
        "",
        "## 候选人列表",
        "",
        "| 候选人 | 岗位/标签 | 时间 | 未读 | 最近消息 |",
        "| --- | --- | --- | ---: | --- |",
    ]
    for item in snapshot.conversation_list:
        lines.append(
            "| "
            + " | ".join(
                [
                    _escape_markdown_cell(item.name),
                    _escape_markdown_cell(item.job_title),
                    _escape_markdown_cell(item.time_label),
                    str(item.unread_count),
                    _escape_markdown_cell(item.last_message),
                ]
            )
            + " |"
        )

    lines.extend(["", "## 当前聊天", ""])
    if snapshot.current_messages:
        for message in snapshot.current_messages:
            time_label = f"[{message.time_label}] " if message.time_label else ""
            lines.append(
                f"- {time_label}{message.speaker or '未知'}：{message.text}"
            )
    else:
        lines.append("暂无精确聊天内容。")

    lines.extend(["", "## AI 建议", ""])
    if snapshot.analysis:
        lines.append("```json")
        lines.append(json.dumps(snapshot.analysis, ensure_ascii=False, indent=2))
        lines.append("```")
    else:
        lines.append("暂无 AI 建议。")

    lines.extend(["", "## 识别诊断", ""])
    lines.append("```json")
    lines.append(
        json.dumps(_serializable_diagnostics(snapshot.diagnostics), ensure_ascii=False, indent=2)
    )
    lines.append("```")
    return "\n".join(lines)


def export_snapshot(snapshot: ScanSnapshot, path: str | Path) -> Path:
    export_path = Path(path)
    export_path.parent.mkdir(parents=True, exist_ok=True)
    suffix = export_path.suffix.lower()
    if suffix == ".json":
        atomic_write_text(
            export_path,
            json.dumps(snapshot_to_dict(snapshot), ensure_ascii=False, indent=2),
        )
        return export_path
    if suffix in {".md", ".markdown"}:
        atomic_write_text(export_path, snapshot_to_markdown(snapshot))
        return export_path
    raise ValueError("仅支持导出 .json 或 .md 文件")


def _serializable_diagnostics(diagnostics: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in diagnostics.items():
        if key == "regions":
            result[key] = {
                name: {"name": region.name, "box": region.box}
                for name, region in value.items()
            }
            continue
        try:
            json.dumps(value, ensure_ascii=False)
        except TypeError:
            result[key] = str(value)
        else:
            result[key] = value
    return result


def _escape_markdown_cell(value: str) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ")


def _tuple_or_none(value) -> tuple[int, int, int, int] | None:
    if value is None:
        return None
    if isinstance(value, (list, tuple)) and len(value) == 4:
        return tuple(int(item) for item in value)
    return None
