from __future__ import annotations

import tkinter as tk

from boss_tool.config import AppConfig, ConfigStore
from boss_tool.gui import BossToolApp
from boss_tool.history import HistoryStore
from boss_tool.models import CandidateProfile, ConversationSummary, ScanSnapshot


class DummyPipeline:
    def __init__(self) -> None:
        self.run_count = 0

    def run_scan(self):
        self.run_count += 1
        return None


class DummyVar:
    def __init__(self, value="") -> None:
        self.value = value

    def set(self, value: str) -> None:
        self.value = value

    def get(self) -> str:
        return self.value


class RaisingVar:
    def get(self):
        raise ValueError("bad tk variable")


class FakeConfigStore:
    def __init__(self) -> None:
        self.saved_config = None

    def save(self, config: AppConfig) -> None:
        self.saved_config = config


class DummyRoot:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def withdraw(self) -> None:
        self.calls.append("withdraw")

    def deiconify(self) -> None:
        self.calls.append("deiconify")

    def update_idletasks(self) -> None:
        self.calls.append("update_idletasks")


def test_build_pipeline_reuses_service_instances(tmp_path) -> None:
    root = tk.Tk()
    root.withdraw()
    app = BossToolApp(root, ConfigStore(tmp_path / "settings.json"))

    first_pipeline = app._build_pipeline()
    second_pipeline = app._build_pipeline()

    assert first_pipeline.ocr_service is second_pipeline.ocr_service
    assert first_pipeline.analyzer is second_pipeline.analyzer
    root.destroy()


def test_scan_history_keeps_latest_twenty_items(tmp_path) -> None:
    app = BossToolApp.__new__(BossToolApp)
    app.scan_history = []
    app.history_store = HistoryStore(tmp_path / "history.json")
    app.status_var = DummyVar()

    for index in range(25):
        snapshot = ScanSnapshot.empty()
        snapshot.window.title = f"scan-{index}"
        snapshot.window.found = True
        snapshot.conversation_list = [
            ConversationSummary(
                name=f"候选人{index}",
                job_title="自拍馆前台",
                last_message="消息",
                time_label="14:40",
            )
        ]
        app._record_scan_history(snapshot)

    assert len(app.scan_history) == 20
    assert app.scan_history[0].window.title == "scan-5"


def test_app_loads_and_persists_scan_history(tmp_path) -> None:
    history_path = tmp_path / "history.json"
    existing = ScanSnapshot.empty()
    existing.window.title = "old-scan"
    existing.current_candidate = CandidateProfile(name="灵灵")
    HistoryStore(history_path).save([existing])

    app = BossToolApp.__new__(BossToolApp)
    app.history_store = HistoryStore(history_path)
    app.scan_history = app.history_store.load()
    app.status_var = DummyVar()

    new_snapshot = ScanSnapshot.empty()
    new_snapshot.window.title = "new-scan"
    new_snapshot.window.found = True
    new_snapshot.conversation_list = [
        ConversationSummary(
            name="灵灵",
            job_title="自拍馆前台",
            last_message="消息",
            time_label="14:40",
        )
    ]
    app._record_scan_history(new_snapshot)

    reloaded = HistoryStore(history_path).load()

    assert app.scan_history[0].window.title == "old-scan"
    assert reloaded[-1].window.title == "new-scan"


def test_scan_history_skips_invalid_empty_scan(tmp_path) -> None:
    app = BossToolApp.__new__(BossToolApp)
    app.scan_history = []
    app.history_store = HistoryStore(tmp_path / "history.json")
    app.status_var = DummyVar()

    snapshot = ScanSnapshot.empty()
    snapshot.window.found = False
    app._record_scan_history(snapshot)

    assert app.scan_history == []
    assert app.status_var.get() == "本次扫描无有效识别内容，未写入历史"


def test_replay_history_snapshot_renders_without_recording_again(tmp_path) -> None:
    app = BossToolApp.__new__(BossToolApp)
    app.scan_history = [ScanSnapshot.empty(), ScanSnapshot.empty()]
    app.scan_history[0].window.title = "old"
    app.scan_history[1].window.title = "new"
    app.snapshot = None
    app.status_var = DummyVar()
    rendered = []
    app._render_snapshot = rendered.append

    app._replay_history_snapshot(display_index=0)

    assert app.snapshot.window.title == "new"
    assert rendered[0].window.title == "new"
    assert len(app.scan_history) == 2
    assert app.status_var.get() == "已回放历史扫描"


def test_refresh_services_rebuilds_client_when_vision_model_changes() -> None:
    app = BossToolApp.__new__(BossToolApp)
    app.config = AppConfig(
        api_key="secret",
        text_model="qwen-plus",
        vision_model="vision-a",
    )
    app.analyzer = None
    app._service_signature = None

    app._refresh_services()
    first_analyzer = app.analyzer

    app.config = AppConfig(
        api_key="secret",
        text_model="qwen-plus",
        vision_model="vision-b",
    )
    app._refresh_services()

    assert first_analyzer is not app.analyzer
    assert app.analyzer.config.vision_model == "vision-b"


def test_save_config_falls_back_when_interval_var_cannot_be_read() -> None:
    app = BossToolApp.__new__(BossToolApp)
    app.base_url_var = DummyVar("")
    app.api_key_var = DummyVar(" secret ")
    app.text_model_var = DummyVar("")
    app.vision_model_var = DummyVar("")
    app.interval_var = RaisingVar()
    app.keyword_var = DummyVar("")
    app.prefer_vision_for_web_var = DummyVar(True)
    app.config_store = FakeConfigStore()
    app.status_var = DummyVar()
    app._refresh_services = lambda: None

    app.save_config()

    assert app.config.monitor_interval_seconds == 5
    assert app.config.api_key == "secret"
    assert app.config_store.saved_config is app.config


def test_window_scan_temporarily_hides_assistant_window() -> None:
    app = BossToolApp.__new__(BossToolApp)
    app.root = DummyRoot()
    app.imported_image_path = None

    app._prepare_window_for_scan()

    assert app.root.calls == ["withdraw", "update_idletasks"]
    assert app._root_hidden_for_scan is True


def test_scan_result_restores_assistant_window() -> None:
    app = BossToolApp.__new__(BossToolApp)
    app.root = DummyRoot()
    app._root_hidden_for_scan = True
    snapshot = ScanSnapshot.empty()
    rendered = []
    app._record_scan_history = lambda item: None
    app._render_snapshot = rendered.append
    app.status_var = DummyVar()

    class FinishedFuture:
        def result(self):
            return snapshot

    app._handle_scan_result(FinishedFuture())

    assert app.root.calls == ["deiconify"]
    assert app._root_hidden_for_scan is False
    assert rendered == [snapshot]
