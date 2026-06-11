from __future__ import annotations

import re

from boss_tool.models import CandidateProfile, ChatMessage, ConversationSummary


TIME_PATTERN = re.compile(r"^\d{1,2}[:：]\d{2}$")
RELATIVE_TIME_PATTERN = re.compile(r"^(刚刚|昨天|今天|周[一二三四五六日天])$")
PURE_NUMBER_PATTERN = re.compile(r"^\d+$")
CHINESE_NAME_PATTERN = re.compile(r"^[\u4e00-\u9fff]{2,6}(女士|先生)?$")

JOB_HINTS = [
    "自拍馆",
    "自怕馆",
    "前台",
    "日结",
    "白结",
    "包吃住",
    "武汉",
    "零售",
    "求职",
]
CONVERSATION_NOISE = {
    "全部",
    "未读",
    "批量",
    "账号权益",
    "消息",
    "意向沟通",
    "推荐",
    "搜索",
    "职位",
    "道具",
    "数据",
    "面试",
    "更多",
}
CHAT_NOISE = {
    "求简历",
    "换电话",
    "换微信",
    "约面试",
    "不合适",
    "发送",
    "常用语",
    "表情",
    "图片",
}
CANDIDATE_NOISE_PARTS = {
    "在线简历",
    "附件简历",
    "刚刚活跃",
    "工作经历",
    "期望",
    "高中",
    "初中",
    "应届生",
}


def parse_conversation_lines(lines: list[str]) -> list[ConversationSummary]:
    cleaned = [normalize_text(line) for line in lines if normalize_text(line)]
    conversations: list[ConversationSummary] = []

    for index, line in enumerate(cleaned):
        if not _is_time(line):
            continue

        split_card = _find_previous_split_card_header(cleaned, index - 1)
        if split_card is not None:
            name, job_title = split_card
        else:
            header = _find_previous_header(cleaned, index - 1)
            if not header:
                continue
            name, job_title = _split_name_and_job(header)
        if not name:
            continue

        summary = _find_next_summary(cleaned, index + 1)
        unread_count = _find_nearby_unread(cleaned, index)

        conversations.append(
            ConversationSummary(
                name=name,
                job_title=job_title,
                last_message=summary,
                time_label=_normalize_time(line),
                unread_count=unread_count,
                confidence=0.76,
            )
        )

    return _dedupe_conversations(conversations)


def parse_candidate_lines(lines: list[str]) -> CandidateProfile:
    cleaned = [normalize_text(line) for line in lines if normalize_text(line)]
    if not cleaned:
        return CandidateProfile()

    name = ""
    summary_lines: list[str] = []
    for line in cleaned:
        if _looks_like_candidate_name(line):
            name = line
            continue
        if _is_candidate_summary(line):
            summary_lines.append(line)

    if not name:
        for line in cleaned:
            if len(line) > 1 and not PURE_NUMBER_PATTERN.match(line):
                name = line
                break

    return CandidateProfile(
        name=name,
        summary_lines=summary_lines[:8],
        confidence=0.75 if name else 0.0,
    )


def parse_chat_lines(lines: list[str]) -> list[ChatMessage]:
    cleaned = [normalize_text(line) for line in lines if normalize_text(line)]
    messages: list[ChatMessage] = []
    pending_time = ""
    pending_speaker = "候选人"
    for line in cleaned:
        if _is_time(line):
            pending_time = line.replace("：", ":")
            continue
        if line in {"已读", "未读"} or line in CHAT_NOISE:
            continue
        if _is_chat_summary_noise(line):
            continue
        if line.endswith(("吗", "呢", "呀", "嘛")):
            pending_speaker = "候选人"
        messages.append(
            ChatMessage(
                speaker=pending_speaker,
                text=line,
                time_label=pending_time,
                confidence=0.7,
            )
        )
        pending_time = ""
        pending_speaker = "我"
    return messages


def normalize_text(text: str) -> str:
    return (
        text.strip()
        .replace(" ", "")
        .replace("：", ":")
        .replace("附件简所", "附件简历")
    )


def _is_time(text: str) -> bool:
    return bool(TIME_PATTERN.match(text) or RELATIVE_TIME_PATTERN.match(text))


def _normalize_time(text: str) -> str:
    return text.replace("：", ":")


def _find_previous_split_card_header(
    lines: list[str], start_index: int
) -> tuple[str, str] | None:
    if start_index - 1 < 0:
        return None
    name_line = lines[start_index - 1]
    job_line = lines[start_index]
    if _looks_like_candidate_name(name_line) and _looks_like_job_line(job_line):
        return name_line, job_line
    return None


def _find_previous_header(lines: list[str], start_index: int) -> str:
    for index in range(start_index, max(-1, start_index - 3), -1):
        if index < 0:
            break
        line = lines[index]
        if _is_conversation_header(line):
            return line
    return ""


def _find_next_summary(lines: list[str], start_index: int) -> str:
    for index in range(start_index, min(len(lines), start_index + 4)):
        line = lines[index]
        if line in CONVERSATION_NOISE:
            continue
        if PURE_NUMBER_PATTERN.match(line):
            continue
        if _is_time(line):
            continue
        if _is_conversation_header(line):
            continue
        return line
    return ""


def _find_nearby_unread(lines: list[str], time_index: int) -> int:
    candidate_numbers: list[int] = []
    for index in range(max(0, time_index - 2), min(len(lines), time_index + 3)):
        line = lines[index]
        if PURE_NUMBER_PATTERN.match(line):
            value = int(line)
            if 1 <= value <= 99:
                candidate_numbers.append(value)
    return candidate_numbers[0] if candidate_numbers else 0


def _split_name_and_job(header: str) -> tuple[str, str]:
    for hint in JOB_HINTS:
        position = header.find(hint)
        if position > 0:
            return header[:position], header[position:]
    if len(header) >= 2:
        return header[:2], header[2:]
    return "", header


def _looks_like_job_line(text: str) -> bool:
    if len(text) < 2:
        return False
    if _is_time(text) or PURE_NUMBER_PATTERN.match(text):
        return False
    if _looks_like_candidate_name(text):
        return False
    return _has_job_marker(text)


def _has_job_marker(text: str) -> bool:
    return any(hint in text for hint in JOB_HINTS) or any(
        marker in text for marker in ("主管", "专员", "助理", "经理", "销售", "客服")
    )


def _is_conversation_header(text: str) -> bool:
    if len(text) < 4:
        return False
    if text in CONVERSATION_NOISE:
        return False
    if _is_time(text):
        return False
    if PURE_NUMBER_PATTERN.match(text):
        return False
    return any(hint in text for hint in JOB_HINTS)


def _dedupe_conversations(
    conversations: list[ConversationSummary],
) -> list[ConversationSummary]:
    seen: set[tuple[str, str]] = set()
    result: list[ConversationSummary] = []
    for item in conversations:
        key = (item.name, item.time_label)
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _looks_like_candidate_name(text: str) -> bool:
    if len(text) <= 1:
        return False
    if any(part in text for part in CANDIDATE_NOISE_PARTS):
        return False
    if any(char.isdigit() for char in text):
        return False
    if text in {"高中", "初中", "本科", "大专"}:
        return False
    return bool(CHINESE_NAME_PATTERN.match(text)) and not _has_job_marker(text)


def _is_candidate_summary(text: str) -> bool:
    if not text or len(text) <= 1:
        return False
    if _looks_like_candidate_name(text):
        return False
    if text in {"在线简历", "附件简历", "刚刚活跃"}:
        return False
    return any(
        marker in text
        for marker in ["岁", "届", "高中", "初中", "工作经历", "期望", "经验", "本科", "大专"]
    )


def _is_chat_summary_noise(text: str) -> bool:
    return any(
        marker in text
        for marker in [
            "工作经历",
            "期望：",
            "在线简历",
            "附件简历",
            "系统提示",
            "请勿线下交易",
        ]
    )
