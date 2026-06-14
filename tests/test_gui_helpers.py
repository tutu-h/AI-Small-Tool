from boss_tool.gui import (
    build_config_from_values,
    build_chat_panel_content,
    build_history_entries,
    history_index_to_snapshot_index,
    build_scan_diagnostics_content,
    build_scan_mode_label,
)
from boss_tool.models import ChatMessage, ConversationSummary, ScanSnapshot


def test_build_scan_mode_label_marks_web_window() -> None:
    diagnostics = {"capture_mode": "live_window", "is_web_boss": True}
    assert build_scan_mode_label(diagnostics, "BOSS直聘 - Chrome") == "网页端窗口"


def test_build_scan_mode_label_marks_imported_image() -> None:
    diagnostics = {"capture_mode": "imported_image", "is_web_boss": False}
    assert build_scan_mode_label(diagnostics, "sample.png") == "导入截图"


def test_build_scan_mode_label_marks_browser_dom() -> None:
    diagnostics = {"capture_mode": "browser_dom", "is_web_boss": True}
    assert build_scan_mode_label(diagnostics, "BOSS直聘 - 招聘沟通") == "浏览器DOM"


def test_chat_panel_labels_exact_messages_as_current_open_conversation() -> None:
    snapshot = ScanSnapshot.empty()
    snapshot.conversation_list = [
        ConversationSummary(
            name="灵灵",
            job_title="自拍馆前台",
            last_message="我想了解一下",
            time_label="14:38",
            unread_count=1,
            selected=True,
        )
    ]
    snapshot.current_messages = [
        ChatMessage(speaker="候选人", text="明天可以面试吗", time_label="14:40")
    ]

    content = build_chat_panel_content(snapshot)

    assert "精确聊天内容来自 Boss 当前打开的会话" in content
    assert "候选人: 明天可以面试吗" in content


def test_chat_panel_uses_selected_left_list_summary_when_chat_not_exact() -> None:
    snapshot = ScanSnapshot.empty()
    snapshot.conversation_list = [
        ConversationSummary(
            name="杨莹",
            job_title="自拍馆前台",
            last_message="女生比较喜欢的那种",
            time_label="14:38",
            unread_count=3,
            selected=True,
        )
    ]

    content = build_chat_panel_content(snapshot)

    assert "未打开的左侧会话只能显示最近消息摘要" in content
    assert "杨莹" in content
    assert "女生比较喜欢的那种" in content


def test_scan_diagnostics_content_shows_vision_attempts_and_used_regions() -> None:
    diagnostics = {
        "layout_mode": "web",
        "vision_recommended": True,
        "fallback_used": True,
        "vision_regions_attempted": ["conversation_list", "chat_body"],
        "vision_regions_used": ["chat_body"],
    }

    content = build_scan_diagnostics_content(diagnostics)

    assert "布局：web" in content
    assert "建议视觉兜底：是" in content
    assert "已尝试区域：左侧会话列表、当前聊天区" in content
    assert "生效区域：当前聊天区" in content


def test_scan_diagnostics_content_includes_warnings() -> None:
    diagnostics = {
        "warnings": [
            "未找到 Boss 直聘窗口",
            "请先打开 Boss 直聘客户端或网页版消息页",
        ]
    }

    content = build_scan_diagnostics_content(diagnostics)

    assert "提示：未找到 Boss 直聘窗口；请先打开 Boss 直聘客户端或网页版消息页" in content


def test_scan_diagnostics_content_shows_dom_status() -> None:
    content = build_scan_diagnostics_content(
        {
            "capture_mode": "browser_dom",
            "layout_mode": "browser_dom",
            "dom_line_count": 45,
            "dom_fallback_used": False,
        }
    )

    assert "DOM读取：成功，45行文本" in content


def test_scan_diagnostics_content_shows_dom_fallback() -> None:
    content = build_scan_diagnostics_content(
        {
            "capture_mode": "live_window",
            "layout_mode": "web",
            "dom_fallback_used": True,
            "warnings": ["未连接到 Boss 网页 DOM"],
        }
    )

    assert "DOM读取：失败，已回退OCR" in content


def test_build_history_entries_keeps_recent_scan_summary_first() -> None:
    older = ScanSnapshot.empty()
    older.window.title = "Boss"
    older.conversation_list = [
        ConversationSummary(
            name="李耀先",
            job_title="人事主管",
            last_message="还在招聘吗",
            time_label="11:05",
            unread_count=1,
        )
    ]

    newer = ScanSnapshot.empty()
    newer.window.title = "BOSS直聘 - Chrome"
    newer.conversation_list = [
        ConversationSummary(
            name="灵灵",
            job_title="自拍馆前台",
            last_message="明天可以面试吗",
            time_label="14:40",
            unread_count=2,
        )
    ]

    entries = build_history_entries([older, newer])

    assert entries[0] == "14:40 | 2未读 | 1会话 | 灵灵：明天可以面试吗"
    assert entries[1] == "11:05 | 1未读 | 1会话 | 李耀先：还在招聘吗"


def test_history_index_to_snapshot_index_maps_display_order_back_to_storage_order() -> None:
    assert history_index_to_snapshot_index(display_index=0, history_length=3) == 2
    assert history_index_to_snapshot_index(display_index=2, history_length=3) == 0
    assert history_index_to_snapshot_index(display_index=3, history_length=3) is None


def test_build_config_from_values_sanitizes_invalid_interval() -> None:
    config = build_config_from_values(
        base_url="",
        api_key=" secret ",
        text_model="",
        vision_model="",
        interval_value="abc",
        boss_window_keyword="",
        prefer_vision_for_web=True,
    )

    assert config.api_key == "secret"
    assert config.monitor_interval_seconds == 5
    assert config.boss_window_keyword == "BOSS"
