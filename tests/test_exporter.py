import json

from boss_tool.exporter import (
    export_snapshot,
    snapshot_from_dict,
    snapshot_to_dict,
    snapshot_to_markdown,
)
from boss_tool.models import (
    CandidateProfile,
    ChatMessage,
    ConversationSummary,
    ScanSnapshot,
)


def test_snapshot_to_dict_contains_recruiter_workbench_fields() -> None:
    snapshot = ScanSnapshot.empty()
    snapshot.window.title = "BOSS直聘 - Chrome"
    snapshot.current_candidate = CandidateProfile(name="灵灵", summary_lines=["18岁"])
    snapshot.conversation_list = [
        ConversationSummary(
            name="灵灵",
            job_title="自拍馆前台",
            last_message="明天可以面试吗",
            time_label="14:40",
            unread_count=2,
            selected=True,
        )
    ]
    snapshot.current_messages = [
        ChatMessage(speaker="候选人", text="明天可以面试吗", time_label="14:40")
    ]
    snapshot.analysis = {
        "current_chat_summary": "候选人询问面试时间",
        "reply_suggestions": ["可以，明天上午方便吗？"],
    }
    snapshot.diagnostics = {
        "layout_mode": "web",
        "vision_regions_used": ["chat_body"],
    }

    data = snapshot_to_dict(snapshot)

    assert data["window"]["title"] == "BOSS直聘 - Chrome"
    assert data["candidate"]["name"] == "灵灵"
    assert data["conversations"][0]["unread_count"] == 2
    assert data["current_messages"][0]["text"] == "明天可以面试吗"
    assert data["analysis"]["current_chat_summary"] == "候选人询问面试时间"
    json.dumps(data, ensure_ascii=False)


def test_snapshot_to_markdown_is_readable_for_recruiter_review() -> None:
    snapshot = ScanSnapshot.empty()
    snapshot.window.title = "Boss"
    snapshot.current_candidate = CandidateProfile(name="李耀先")
    snapshot.conversation_list = [
        ConversationSummary(
            name="李耀先",
            job_title="人事主管",
            last_message="您好，还在招聘吗",
            time_label="11:05",
            unread_count=1,
        )
    ]

    content = snapshot_to_markdown(snapshot)

    assert "# Boss 识别结果" in content
    assert "## 候选人列表" in content
    assert "| 李耀先 | 人事主管 | 11:05 | 1 | 您好，还在招聘吗 |" in content


def test_snapshot_from_dict_restores_scan_snapshot() -> None:
    snapshot = ScanSnapshot.empty()
    snapshot.window.title = "Boss"
    snapshot.current_candidate = CandidateProfile(name="灵灵")
    snapshot.conversation_list = [
        ConversationSummary(
            name="灵灵",
            job_title="自拍馆前台",
            last_message="明天可以面试吗",
            time_label="14:40",
            unread_count=2,
            selected=True,
        )
    ]
    snapshot.current_messages = [
        ChatMessage(speaker="候选人", text="明天可以面试吗", time_label="14:40")
    ]

    restored = snapshot_from_dict(snapshot_to_dict(snapshot))

    assert restored.window.title == "Boss"
    assert restored.current_candidate.name == "灵灵"
    assert restored.conversation_list[0].selected is True
    assert restored.current_messages[0].text == "明天可以面试吗"


def test_export_snapshot_uses_clean_final_file_without_temp_leftovers(tmp_path) -> None:
    snapshot = ScanSnapshot.empty()
    snapshot.window.title = "Boss"
    export_path = tmp_path / "boss-result.json"

    export_snapshot(snapshot, export_path)

    assert export_path.exists()
    assert list(tmp_path.glob("*.tmp")) == []
