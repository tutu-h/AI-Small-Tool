from boss_tool.fallback import (
    should_use_vision_fallback,
    should_use_vision_for_candidate,
    should_use_vision_for_chat,
    should_use_vision_for_conversations,
)
from boss_tool.models import CandidateProfile, ConversationSummary, ScanSnapshot


def test_should_use_vision_fallback_when_messages_missing() -> None:
    snapshot = ScanSnapshot.empty()
    snapshot.raw_chat_lines = ["您好", "在吗"]

    assert should_use_vision_fallback(snapshot) is True


def test_should_not_use_vision_fallback_when_core_fields_exist() -> None:
    snapshot = ScanSnapshot.empty()
    snapshot.current_candidate = CandidateProfile(name="灵灵", confidence=0.8)
    snapshot.conversation_list = [
        ConversationSummary(
            name="灵灵",
            job_title="自拍馆前台",
            last_message="喜欢的",
            time_label="06:47",
            unread_count=1,
            confidence=0.8,
        )
    ]

    assert should_use_vision_fallback(snapshot) is False


def test_should_use_vision_for_conversations_when_unread_counts_all_zero() -> None:
    snapshot = ScanSnapshot.empty()
    snapshot.current_candidate = CandidateProfile(name="灵灵", confidence=0.8)
    snapshot.conversation_list = [
        ConversationSummary(
            name="杨莹",
            job_title="自拍馆前台",
            last_message="女生比较喜欢的那种",
            time_label="14:38",
            unread_count=0,
            confidence=0.6,
        ),
        ConversationSummary(
            name="吴女士",
            job_title="自拍馆前台",
            last_message="地址在哪",
            time_label="14:11",
            unread_count=0,
            confidence=0.6,
        ),
    ]
    snapshot.raw_conversation_lines = ["杨莹自拍馆前台", "14:38", "204", "女生比较喜欢的那种"]

    assert should_use_vision_for_conversations(snapshot) is True
    assert should_use_vision_fallback(snapshot) is True


def test_should_use_vision_for_candidate_when_name_is_generic() -> None:
    snapshot = ScanSnapshot.empty()
    snapshot.current_candidate = CandidateProfile(name="会话", summary_lines=["18岁"])

    assert should_use_vision_for_candidate(snapshot) is True


def test_should_use_vision_for_chat_when_messages_contain_profile_noise() -> None:
    snapshot = ScanSnapshot.empty()
    snapshot.current_messages = []
    snapshot.raw_chat_lines = ["工作经历", "在线简历", "期望：武汉零售"]

    assert should_use_vision_for_chat(snapshot) is True
