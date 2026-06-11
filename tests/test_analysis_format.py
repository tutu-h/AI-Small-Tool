from boss_tool.gui import (
    build_candidate_card_content,
    build_chat_panel_content,
    format_analysis_sections,
)
from boss_tool.models import CandidateProfile, ConversationSummary, ScanSnapshot


def test_format_analysis_sections_handles_string_priority_without_character_split() -> None:
    analysis = {
        "unread_summary": "有 2 条未读消息",
        "current_chat_summary": "候选人询问工作时间",
        "priorities": ["高优先级：候选人主动追问", "中优先级：等待补充信息"],
        "reply_suggestions": [
            "你好，我们这边工作时间是...",
            "如果方便的话我也可以发你岗位详情。",
        ],
    }

    sections = format_analysis_sections(analysis)

    assert "高优先级：候选人主动追问" in sections["priorities"]
    assert "高" != sections["priorities"][0]


def test_format_analysis_sections_wraps_plain_text_into_lists() -> None:
    analysis = {
        "unread_summary": "暂无未读消息",
        "current_chat_summary": "沟通刚开始",
        "priorities": "低优先级：继续观察",
        "reply_suggestions": "您好，我看到了您的消息。",
    }

    sections = format_analysis_sections(analysis)

    assert sections["priorities"] == ["低优先级：继续观察"]
    assert sections["reply_suggestions"] == ["您好，我看到了您的消息。"]


def test_build_candidate_card_prefers_selected_conversation_when_profile_is_empty() -> None:
    snapshot = ScanSnapshot.empty()
    snapshot.current_candidate = CandidateProfile(name="", summary_lines=[])
    snapshot.conversation_list = [
        ConversationSummary(
            name="李耀先",
            job_title="人事主管",
            last_message="心怀期待，静待相逢",
            time_label="11:05",
            unread_count=1,
            selected=True,
        )
    ]

    title, details = build_candidate_card_content(snapshot)

    assert title == "李耀先"
    assert "当前会话岗位：人事主管" in details


def test_build_chat_panel_content_falls_back_to_selected_conversation_summary() -> None:
    snapshot = ScanSnapshot.empty()
    snapshot.conversation_list = [
        ConversationSummary(
            name="李耀先",
            job_title="人事主管",
            last_message="您好，还在招聘吗",
            time_label="11:05",
            unread_count=2,
            selected=True,
        )
    ]
    snapshot.current_messages = []
    snapshot.diagnostics["warnings"] = []

    content = build_chat_panel_content(snapshot)

    assert "未打开的左侧会话只能显示最近消息摘要" in content
    assert "候选人：李耀先" in content
    assert "最近消息：您好，还在招聘吗" in content
