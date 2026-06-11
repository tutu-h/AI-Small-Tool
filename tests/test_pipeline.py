from boss_tool.models import CandidateProfile, ChatMessage, ConversationSummary, ScanSnapshot
from boss_tool.pipeline import BossInsightPipeline


class FakeCapture:
    def scan(self) -> ScanSnapshot:
        snapshot = ScanSnapshot.empty()
        snapshot.window.found = True
        snapshot.window.title = "Boss Mock"
        snapshot.diagnostics["regions"] = {}
        return snapshot


class FakeAnalyzer:
    def analyze_snapshot(self, snapshot: ScanSnapshot):
        return {"current_chat_summary": "summary"}


class FailingAnalyzer:
    def analyze_snapshot(self, snapshot: ScanSnapshot):
        raise RuntimeError("text model timeout")


def test_pipeline_returns_analysis_dict() -> None:
    pipeline = BossInsightPipeline(
        capture_service=FakeCapture(),
        ocr_service=None,
        vision_service=None,
        analyzer=FakeAnalyzer(),
    )

    result = pipeline.run_scan()

    assert result.analysis["current_chat_summary"] == "summary"


def test_pipeline_uses_local_analysis_when_no_analyzer() -> None:
    snapshot = ScanSnapshot.empty()
    snapshot.window.found = True
    snapshot.diagnostics["ui_texts"] = [
        "灵灵",
        "自拍馆前台",
        "14:40",
        "1",
        "明天可以面试吗",
    ]

    class LocalCapture:
        def scan(self) -> ScanSnapshot:
            return snapshot

    pipeline = BossInsightPipeline(
        capture_service=LocalCapture(),
        ocr_service=None,
        vision_service=None,
        analyzer=None,
    )

    result = pipeline.run_scan()

    assert result.analysis["unread_summary"] == "识别到 1 个候选人会话，合计 1 条未读。"
    assert "面试" in result.analysis["reply_suggestions"][0]


def test_pipeline_falls_back_to_local_analysis_when_text_model_fails() -> None:
    snapshot = ScanSnapshot.empty()
    snapshot.window.found = True
    snapshot.diagnostics["ui_texts"] = [
        "李耀先",
        "人事主管",
        "昨天",
        "1",
        "还在招聘吗",
    ]

    class LocalCapture:
        def scan(self) -> ScanSnapshot:
            return snapshot

    pipeline = BossInsightPipeline(
        capture_service=LocalCapture(),
        ocr_service=None,
        vision_service=None,
        analyzer=FailingAnalyzer(),
    )

    result = pipeline.run_scan()

    assert "text model timeout" in result.diagnostics["warnings"]
    assert result.analysis["unread_summary"] == "识别到 1 个候选人会话，合计 1 条未读。"


class FakeImageCapture:
    def scan(self) -> ScanSnapshot:
        snapshot = ScanSnapshot.empty()
        snapshot.window.found = True
        snapshot.window.title = "sample.jpg"
        snapshot.diagnostics["capture_mode"] = "imported_image"
        snapshot.diagnostics["regions"] = {}
        return snapshot


def test_pipeline_supports_imported_image_capture() -> None:
    pipeline = BossInsightPipeline(
        capture_service=FakeImageCapture(),
        ocr_service=None,
        vision_service=None,
        analyzer=FakeAnalyzer(),
    )

    result = pipeline.run_scan()

    assert result.window.title == "sample.jpg"
    assert result.analysis["current_chat_summary"] == "summary"


def test_pipeline_marks_first_conversation_selected() -> None:
    snapshot = ScanSnapshot.empty()
    snapshot.window.found = True
    snapshot.window.title = "Boss"
    snapshot.conversation_list = []

    pipeline = BossInsightPipeline(
        capture_service=FakeCapture(),
        ocr_service=None,
        vision_service=None,
        analyzer=None,
    )

    pipeline._mark_default_selected_conversation(snapshot)

    assert snapshot.conversation_list == []


def test_pipeline_preserves_capture_layout_metadata() -> None:
    snapshot = ScanSnapshot.empty()
    snapshot.window.found = True
    snapshot.window.title = "BOSS直聘 - Chrome"
    snapshot.diagnostics["capture_mode"] = "live_window"
    snapshot.diagnostics["is_web_boss"] = True
    snapshot.diagnostics["layout_mode"] = "web"
    snapshot.diagnostics["regions"] = {}

    class FakeWebCapture:
        def scan(self) -> ScanSnapshot:
            return snapshot

    pipeline = BossInsightPipeline(
        capture_service=FakeWebCapture(),
        ocr_service=None,
        vision_service=None,
        analyzer=None,
    )

    result = pipeline.run_scan()

    assert result.diagnostics["is_web_boss"] is True
    assert result.diagnostics["layout_mode"] == "web"


def test_pipeline_records_warning_and_uses_ui_texts_when_ocr_region_fails() -> None:
    snapshot = ScanSnapshot.empty()
    snapshot.window.found = True
    snapshot.diagnostics["regions"] = {"conversation_list": FakeRegion()}
    snapshot.diagnostics["ui_texts"] = [
        "灵灵",
        "自拍馆前台",
        "14:40",
        "1",
        "明天可以面试吗",
    ]

    class LocalCapture:
        def scan(self) -> ScanSnapshot:
            return snapshot

    pipeline = BossInsightPipeline(
        capture_service=LocalCapture(),
        ocr_service=FailingOcrService(),
        vision_service=None,
        analyzer=None,
    )

    result = pipeline.run_scan()

    assert "左侧会话列表OCR失败: ocr engine crashed" in result.diagnostics["warnings"]
    assert result.conversation_list[0].name == "灵灵"
    assert result.conversation_list[0].last_message == "明天可以面试吗"


class FakeRegion:
    image_bytes = b"fake-image"


class FailingOcrService:
    def extract_lines(self, _image_bytes: bytes):
        raise RuntimeError("ocr engine crashed")

    def texts(self, _lines):
        return []


class EmptyVisionService:
    def analyze_region_image(self, _image_bytes: bytes, _prompt: str) -> dict:
        return {}


class FailingVisionService:
    def analyze_region_image(self, _image_bytes: bytes, _prompt: str) -> dict:
        raise RuntimeError("vision api timeout")


def test_vision_fallback_does_not_replace_good_ocr_with_empty_result() -> None:
    snapshot = ScanSnapshot.empty()
    snapshot.current_candidate = CandidateProfile(name="灵灵", summary_lines=["18岁"])
    snapshot.conversation_list = [
        ConversationSummary(
            name="灵灵",
            job_title="自拍馆前台",
            last_message="我想了解一下",
            time_label="14:38",
            unread_count=0,
        )
    ]
    snapshot.current_messages = [
        ChatMessage(speaker="候选人", text="在线简历", time_label=""),
        ChatMessage(speaker="候选人", text="明天可以面试吗", time_label="14:40")
    ]
    snapshot.raw_conversation_lines = ["204", "灵灵自拍馆前台", "14:38"]
    snapshot.raw_chat_lines = ["在线简历", "明天可以面试吗"]

    pipeline = BossInsightPipeline(
        capture_service=FakeCapture(),
        ocr_service=None,
        vision_service=EmptyVisionService(),
        analyzer=None,
    )

    used = pipeline._apply_vision_fallback(
        snapshot,
        {
            "conversation_list": FakeRegion(),
            "candidate_header": FakeRegion(),
            "chat_body": FakeRegion(),
        },
    )

    assert used is False
    assert snapshot.current_candidate.name == "灵灵"
    assert snapshot.current_messages[0].text == "明天可以面试吗"
    assert snapshot.diagnostics["vision_regions_attempted"] == [
        "conversation_list",
        "chat_body",
    ]


def test_vision_fallback_records_warning_when_region_call_fails() -> None:
    snapshot = ScanSnapshot.empty()
    snapshot.current_candidate = CandidateProfile(name="灵灵")
    snapshot.conversation_list = []

    pipeline = BossInsightPipeline(
        capture_service=FakeCapture(),
        ocr_service=None,
        vision_service=FailingVisionService(),
        analyzer=None,
    )

    used = pipeline._apply_vision_fallback(
        snapshot,
        {"conversation_list": FakeRegion()},
    )

    assert used is False
    assert snapshot.conversation_list == []
    assert snapshot.diagnostics["vision_regions_attempted"] == ["conversation_list"]
    assert "左侧会话列表视觉识别失败: vision api timeout" in snapshot.diagnostics["warnings"]


class ConversationVisionService:
    def analyze_region_image(self, _image_bytes: bytes, _prompt: str) -> dict:
        return {
            "conversations": [
                {
                    "name": "灵灵",
                    "job_title": "",
                    "last_message": "",
                    "time_label": "14:38",
                    "unread_count": 2,
                },
                {
                    "name": "李耀先",
                    "job_title": "人事主管",
                    "last_message": "还在招聘吗",
                    "time_label": "昨天",
                    "unread_count": 1,
                },
            ]
        }


def test_vision_fallback_merges_conversation_duplicates_without_losing_ocr_fields() -> None:
    snapshot = ScanSnapshot.empty()
    snapshot.current_candidate = CandidateProfile(name="灵灵")
    snapshot.conversation_list = [
        ConversationSummary(
            name="灵灵",
            job_title="自拍馆前台",
            last_message="明天可以面试吗",
            time_label="14:38",
            unread_count=0,
            selected=True,
        )
    ]
    snapshot.raw_conversation_lines = ["灵灵", "14:38", "2"]

    pipeline = BossInsightPipeline(
        capture_service=FakeCapture(),
        ocr_service=None,
        vision_service=ConversationVisionService(),
        analyzer=None,
    )

    used = pipeline._apply_vision_fallback(
        snapshot,
        {"conversation_list": FakeRegion()},
    )

    assert used is True
    assert len(snapshot.conversation_list) == 2
    assert snapshot.conversation_list[0].name == "灵灵"
    assert snapshot.conversation_list[0].job_title == "自拍馆前台"
    assert snapshot.conversation_list[0].last_message == "明天可以面试吗"
    assert snapshot.conversation_list[0].unread_count == 2
    assert snapshot.conversation_list[0].selected is True
