from __future__ import annotations

from boss_tool.models import ScanSnapshot


def build_local_analysis(snapshot: ScanSnapshot) -> dict[str, object]:
    conversations = snapshot.conversation_list
    if not conversations:
        return {
            "unread_summary": "暂未识别到候选人会话。",
            "current_chat_summary": "暂无当前聊天内容。",
            "priorities": ["暂无可排序的候选人会话。"],
            "reply_suggestions": ["请先扫描 Boss 消息页或导入截图。"],
        }

    total_unread = sum(item.unread_count for item in conversations)
    current = _current_conversation(snapshot)
    current_name = current.name if current is not None else "当前候选人"
    latest_message = _latest_message(snapshot, current)

    return {
        "unread_summary": (
            f"识别到 {len(conversations)} 个候选人会话，合计 {total_unread} 条未读。"
        ),
        "current_chat_summary": _build_current_summary(current_name, latest_message),
        "priorities": _build_priorities(conversations),
        "reply_suggestions": _build_reply_suggestions(latest_message),
    }


def _current_conversation(snapshot: ScanSnapshot):
    for item in snapshot.conversation_list:
        if item.selected:
            return item
    return snapshot.conversation_list[0] if snapshot.conversation_list else None


def _latest_message(snapshot: ScanSnapshot, current) -> str:
    if snapshot.current_messages:
        return snapshot.current_messages[-1].text
    if current is not None:
        return current.last_message
    return ""


def _build_current_summary(candidate_name: str, latest_message: str) -> str:
    if latest_message:
        return f"{candidate_name} 最近关注：{latest_message}"
    return f"{candidate_name} 暂无可用聊天内容。"


def _build_priorities(conversations) -> list[str]:
    sorted_items = sorted(
        conversations,
        key=lambda item: (item.unread_count, bool(item.last_message)),
        reverse=True,
    )
    priorities: list[str] = []
    for item in sorted_items[:8]:
        level = "高优先级" if item.unread_count > 0 else "普通优先级"
        message = item.last_message or "暂无最近消息"
        priorities.append(
            f"{level}：{item.name or '未识别候选人'} 有 {item.unread_count} 条未读，最近消息：{message}"
        )
    return priorities or ["暂无可排序的候选人会话。"]


def _build_reply_suggestions(latest_message: str) -> list[str]:
    if not latest_message:
        return ["您好，我看到了您的消息，可以再发一下您想了解的问题。"]
    if "面试" in latest_message:
        return ["可以的，您明天哪个时间段方便？我这边帮您确认面试安排。"]
    if "地址" in latest_message or "在哪" in latest_message:
        return ["您好，我们的位置在这里，我也可以发您详细路线和到店方式。"]
    if "招聘" in latest_message:
        return ["您好，还在招聘的。您方便说一下目前的求职时间和期望岗位吗？"]
    return ["您好，我看到了您的消息，我先帮您确认一下岗位信息后回复您。"]
