from boss_tool.analysis import build_local_analysis
from boss_tool.models import ChatMessage, ConversationSummary, ScanSnapshot


def test_build_local_analysis_summarizes_unread_and_priorities() -> None:
    snapshot = ScanSnapshot.empty()
    snapshot.conversation_list = [
        ConversationSummary(
            name="灵灵",
            job_title="自拍馆前台",
            last_message="明天可以面试吗",
            time_label="14:40",
            unread_count=2,
            selected=True,
        ),
        ConversationSummary(
            name="李耀先",
            job_title="人事主管",
            last_message="还在招聘吗",
            time_label="昨天",
            unread_count=0,
        ),
    ]
    snapshot.current_messages = [
        ChatMessage(speaker="候选人", text="明天可以面试吗", time_label="14:40")
    ]

    analysis = build_local_analysis(snapshot)

    assert analysis["unread_summary"] == "识别到 2 个候选人会话，合计 2 条未读。"
    assert "灵灵" in analysis["current_chat_summary"]
    assert analysis["priorities"][0] == "高优先级：灵灵 有 2 条未读，最近消息：明天可以面试吗"
    assert "面试" in analysis["reply_suggestions"][0]


def test_build_local_analysis_handles_empty_snapshot() -> None:
    analysis = build_local_analysis(ScanSnapshot.empty())

    assert analysis["unread_summary"] == "暂未识别到候选人会话。"
    assert analysis["priorities"] == ["暂无可排序的候选人会话。"]
