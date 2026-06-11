from boss_tool.history import HistoryStore
from boss_tool.models import CandidateProfile, ConversationSummary, ScanSnapshot


def make_snapshot(index: int) -> ScanSnapshot:
    snapshot = ScanSnapshot.empty()
    snapshot.window.title = f"scan-{index}"
    snapshot.current_candidate = CandidateProfile(name=f"候选人{index}")
    snapshot.conversation_list = [
        ConversationSummary(
            name=f"候选人{index}",
            job_title="自拍馆前台",
            last_message=f"消息{index}",
            time_label="14:40",
            unread_count=index,
        )
    ]
    return snapshot


def test_history_store_round_trips_recent_snapshots(tmp_path) -> None:
    store = HistoryStore(tmp_path / "history.json", limit=20)

    store.save([make_snapshot(index) for index in range(25)])
    loaded = store.load()

    assert len(loaded) == 20
    assert loaded[0].window.title == "scan-5"
    assert loaded[-1].current_candidate.name == "候选人24"
    assert loaded[-1].conversation_list[0].last_message == "消息24"


def test_history_store_returns_empty_list_for_missing_file(tmp_path) -> None:
    store = HistoryStore(tmp_path / "missing.json")

    assert store.load() == []


def test_history_store_skips_invalid_snapshot_items(tmp_path) -> None:
    path = tmp_path / "history.json"
    path.write_text(
        '{"snapshots": ["bad-item", {"window": {"title": "good-scan"}}]}',
        encoding="utf-8",
    )

    loaded = HistoryStore(path).load()

    assert len(loaded) == 1
    assert loaded[0].window.title == "good-scan"
