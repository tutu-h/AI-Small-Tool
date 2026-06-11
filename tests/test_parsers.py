from boss_tool.parsers import (
    parse_candidate_lines,
    parse_chat_lines,
    parse_conversation_lines,
)


def test_parse_conversation_lines_extracts_unread_count_and_summary() -> None:
    lines = [
        "杨莹自拍馆前台日结300-500+包吃住",
        "14:38",
        "3",
        "女生比较喜欢的那种",
        "吴女士自拍馆前台日结300-500+包吃住",
        "14:11",
        "1",
        "地址在哪",
    ]

    conversations = parse_conversation_lines(lines)

    assert len(conversations) == 2
    assert conversations[0].name == "杨莹"
    assert conversations[0].unread_count == 3
    assert conversations[0].last_message == "女生比较喜欢的那种"


def test_parse_conversation_lines_handles_web_split_card_lines() -> None:
    lines = [
        "灵灵",
        "自拍馆前台日结300-500",
        "14:40",
        "2",
        "明天可以面试吗",
        "李耀先",
        "人事主管",
        "昨天",
        "还在招聘吗",
    ]

    conversations = parse_conversation_lines(lines)

    assert len(conversations) == 2
    assert conversations[0].name == "灵灵"
    assert conversations[0].job_title == "自拍馆前台日结300-500"
    assert conversations[0].unread_count == 2
    assert conversations[0].last_message == "明天可以面试吗"
    assert conversations[1].name == "李耀先"
    assert conversations[1].time_label == "昨天"


def test_parse_candidate_lines_skips_bad_single_character_name() -> None:
    profile = parse_candidate_lines(["X", "灵灵", "刚刚活跃", "18岁", "25年应届生", "高中"])

    assert profile.name == "灵灵"
    assert "18岁" in profile.summary_lines


def test_parse_candidate_lines_keeps_recruiter_profile_facts() -> None:
    profile = parse_candidate_lines(
        [
            "灵灵",
            "刚刚活跃",
            "18岁",
            "25年应届生",
            "高中",
            "期望：武汉零售",
            "工作经历：自拍馆前台",
            "在线简历",
            "附件简历",
        ]
    )

    assert profile.name == "灵灵"
    assert profile.summary_lines == [
        "18岁",
        "25年应届生",
        "高中",
        "期望:武汉零售",
        "工作经历:自拍馆前台",
    ]


def test_parse_chat_lines_keeps_time_labels() -> None:
    lines = [
        "06:47",
        "喜欢的",
        "平时喜欢自拍吗",
        "已读",
        "换微信",
    ]

    messages = parse_chat_lines(lines)

    assert len(messages) == 2
    assert messages[0].time_label == "06:47"
    assert messages[0].text == "喜欢的"


def test_parse_chat_lines_filters_boss_buttons_and_profile_noise() -> None:
    lines = [
        "求简历",
        "换电话",
        "在线简历",
        "附件简历",
        "工作经历",
        "系统提示：请勿线下交易",
        "14:40",
        "明天可以面试吗",
        "发送",
    ]

    messages = parse_chat_lines(lines)

    assert [message.text for message in messages] == ["明天可以面试吗"]
    assert messages[0].time_label == "14:40"
