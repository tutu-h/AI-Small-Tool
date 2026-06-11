from __future__ import annotations

from boss_tool.models import ScanSnapshot


GENERIC_CANDIDATE_NAMES = {
    "",
    "会话",
    "消息",
    "全部",
    "在线简历",
    "附件简历",
    "工作经历",
}


def should_use_vision_fallback(snapshot: ScanSnapshot) -> bool:
    return any(
        (
            should_use_vision_for_conversations(snapshot),
            should_use_vision_for_candidate(snapshot),
            should_use_vision_for_chat(snapshot),
        )
    )


def should_use_vision_for_conversations(snapshot: ScanSnapshot) -> bool:
    if not snapshot.conversation_list:
        return True
    if snapshot.raw_conversation_lines and all(
        item.unread_count == 0 for item in snapshot.conversation_list
    ):
        if any(line.isdigit() and int(line) > 1 for line in snapshot.raw_conversation_lines):
            return True
    if len(snapshot.conversation_list) == 1 and len(snapshot.raw_conversation_lines) > 8:
        return True
    return False


def should_use_vision_for_candidate(snapshot: ScanSnapshot) -> bool:
    if snapshot.current_candidate.name in GENERIC_CANDIDATE_NAMES:
        return True
    if snapshot.current_candidate.name and len(snapshot.current_candidate.name) == 1:
        return True
    return False


def should_use_vision_for_chat(snapshot: ScanSnapshot) -> bool:
    noisy_markers = ("工作经历", "在线简历", "期望：", "附件简历")
    if snapshot.current_messages and any(
        any(marker in message.text for marker in noisy_markers)
        for message in snapshot.current_messages
    ):
        return True
    if snapshot.raw_chat_lines and not snapshot.current_messages:
        return True
    if snapshot.current_messages:
        return False
    return any(any(marker in line for marker in noisy_markers) for line in snapshot.raw_chat_lines)
