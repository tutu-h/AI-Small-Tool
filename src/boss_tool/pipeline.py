from __future__ import annotations

from typing import Any

from boss_tool.analysis import build_local_analysis
from boss_tool.fallback import (
    should_use_vision_fallback,
    should_use_vision_for_candidate,
    should_use_vision_for_chat,
    should_use_vision_for_conversations,
)
from boss_tool.models import ScanSnapshot
from boss_tool.parsers import (
    parse_candidate_lines,
    parse_chat_lines,
    parse_conversation_lines,
)


class BossInsightPipeline:
    def __init__(self, capture_service, ocr_service, vision_service, analyzer) -> None:
        self.capture_service = capture_service
        self.ocr_service = ocr_service
        self.vision_service = vision_service
        self.analyzer = analyzer
        self._current_snapshot: ScanSnapshot | None = None

    def run_scan(self) -> ScanSnapshot:
        snapshot = self.capture_service.scan()
        self._current_snapshot = snapshot
        if not snapshot.window.found:
            return snapshot

        regions = snapshot.diagnostics.get("regions", {})
        ui_texts = snapshot.diagnostics.get("ui_texts", [])
        conversation_lines = self._ocr_region_lines(regions, "conversation_list")
        candidate_lines = self._ocr_region_lines(regions, "candidate_header")
        chat_lines = self._ocr_region_lines(regions, "chat_body")

        if not conversation_lines:
            conversation_lines = self._conversation_lines_from_ui_texts(ui_texts)
        if not candidate_lines:
            candidate_lines = self._candidate_lines_from_ui_texts(ui_texts)
        if not chat_lines:
            chat_lines = self._chat_lines_from_ui_texts(ui_texts)

        snapshot.raw_conversation_lines = conversation_lines
        snapshot.raw_candidate_lines = candidate_lines
        snapshot.raw_chat_lines = chat_lines
        snapshot.conversation_list = parse_conversation_lines(conversation_lines)
        snapshot.current_candidate = parse_candidate_lines(candidate_lines)
        snapshot.current_messages = parse_chat_lines(chat_lines)
        self._mark_default_selected_conversation(snapshot)
        vision_recommended = self._should_trigger_vision(snapshot)

        fallback_used = False
        if vision_recommended and self.vision_service is not None:
            fallback_used = self._apply_vision_fallback(snapshot, regions)
            self._mark_default_selected_conversation(snapshot)

        snapshot.analysis = build_local_analysis(snapshot)
        if self.analyzer is not None:
            try:
                snapshot.analysis = self.analyzer.analyze_snapshot(snapshot)
            except Exception as exc:
                snapshot.diagnostics.setdefault("warnings", []).append(str(exc))

        snapshot.diagnostics["vision_recommended"] = vision_recommended
        snapshot.diagnostics["fallback_used"] = fallback_used
        return snapshot

    def _ocr_region_lines(self, regions: dict[str, Any], name: str) -> list[str]:
        region = regions.get(name)
        if region is None or self.ocr_service is None:
            return []
        try:
            lines = self.ocr_service.extract_lines(region.image_bytes)
            return self.ocr_service.texts(lines)
        except Exception as exc:
            region_label = {
                "conversation_list": "左侧会话列表",
                "candidate_header": "候选人资料区",
                "chat_body": "当前聊天区",
            }.get(name, name)
            self._current_snapshot.diagnostics.setdefault("warnings", []).append(
                f"{region_label}OCR失败: {exc}"
            )
            return []

    def _should_trigger_vision(self, snapshot: ScanSnapshot) -> bool:
        if should_use_vision_fallback(snapshot):
            return True
        capture_mode = snapshot.diagnostics.get("capture_mode")
        is_web_boss = snapshot.diagnostics.get("is_web_boss", False)
        prefer_web_vision = getattr(
            getattr(self.capture_service, "config", None),
            "prefer_vision_for_web",
            True,
        )
        return capture_mode == "live_window" and is_web_boss and prefer_web_vision

    def _apply_vision_fallback(
        self, snapshot: ScanSnapshot, regions: dict[str, Any]
    ) -> bool:
        used = False
        attempted_regions: list[str] = []
        used_regions: list[str] = []
        if should_use_vision_for_conversations(snapshot) and "conversation_list" in regions:
            attempted_regions.append("conversation_list")
            data = self._analyze_region_safely(
                snapshot,
                "左侧会话列表",
                regions["conversation_list"].image_bytes,
                (
                    "请识别 Boss 直聘左侧会话列表，返回 JSON 对象，"
                    "包含 conversations 数组。每项包含 name、job_title、"
                    "last_message、time_label、unread_count。"
                ),
            )
            conversations = data.get("conversations", [])
            if conversations:
                vision_conversations = [
                    self._conversation_from_dict(item, source="vision")
                    for item in conversations
                    if item.get("name")
                ]
                snapshot.conversation_list = self._merge_conversations(
                    snapshot.conversation_list,
                    vision_conversations,
                )
            if conversations:
                used = True
                used_regions.append("conversation_list")

        if should_use_vision_for_candidate(snapshot) and "candidate_header" in regions:
            attempted_regions.append("candidate_header")
            data = self._analyze_region_safely(
                snapshot,
                "候选人资料区",
                regions["candidate_header"].image_bytes,
                (
                    "请识别候选人顶部信息，返回 JSON 对象 candidate，"
                    "至少包含 name 和 summary_lines。"
                ),
            )
            candidate = data.get("candidate", {})
            candidate_name = str(candidate.get("name", "") or "").strip()
            summary_lines = candidate.get("summary_lines", [])
            if candidate_name or summary_lines:
                snapshot.current_candidate.name = candidate_name or snapshot.current_candidate.name
                snapshot.current_candidate.summary_lines = summary_lines or snapshot.current_candidate.summary_lines
                snapshot.current_candidate.source = "vision"
                snapshot.current_candidate.confidence = (
                    0.78 if snapshot.current_candidate.name else 0.0
                )
                used = True
                used_regions.append("candidate_header")

        if should_use_vision_for_chat(snapshot) and "chat_body" in regions:
            attempted_regions.append("chat_body")
            data = self._analyze_region_safely(
                snapshot,
                "当前聊天区",
                regions["chat_body"].image_bytes,
                (
                    "请识别聊天消息，返回 JSON 对象，包含 messages 数组。"
                    "每项包含 speaker、text、time_label。"
                ),
            )
            messages = [
                self._message_from_dict(item, source="vision")
                for item in data.get("messages", [])
                if item.get("text")
            ]
            if messages:
                snapshot.current_messages = messages
                used = True
                used_regions.append("chat_body")
            else:
                snapshot.current_messages = self._without_profile_noise_messages(
                    snapshot.current_messages
                )

        if attempted_regions:
            snapshot.diagnostics["vision_regions_attempted"] = attempted_regions
        if used_regions:
            snapshot.diagnostics["vision_regions_used"] = used_regions

        return used

    @staticmethod
    def _mark_default_selected_conversation(snapshot: ScanSnapshot) -> None:
        has_selected = False
        for index, item in enumerate(snapshot.conversation_list):
            item.selected = index == 0
            has_selected = has_selected or item.selected
        if not has_selected and snapshot.conversation_list:
            snapshot.conversation_list[0].selected = True

    @staticmethod
    def _conversation_lines_from_ui_texts(ui_texts: list[str]) -> list[str]:
        lines: list[str] = []
        for text in ui_texts:
            value = text.strip()
            if not value:
                continue
            if len(value) <= 50:
                lines.append(value)
            if len(lines) >= 30:
                break
        return lines

    @staticmethod
    def _candidate_lines_from_ui_texts(ui_texts: list[str]) -> list[str]:
        lines: list[str] = []
        for text in ui_texts:
            value = text.strip()
            if value and len(value) <= 40:
                lines.append(value)
            if len(lines) >= 8:
                break
        return lines

    @staticmethod
    def _chat_lines_from_ui_texts(ui_texts: list[str]) -> list[str]:
        lines: list[str] = []
        for text in ui_texts:
            value = text.strip()
            if value and len(value) <= 120:
                lines.append(value)
            if len(lines) >= 40:
                break
        return lines

    @staticmethod
    def _conversation_from_dict(item: dict[str, Any], source: str):
        from boss_tool.models import ConversationSummary

        return ConversationSummary(
            name=item.get("name", ""),
            job_title=item.get("job_title", ""),
            last_message=item.get("last_message", ""),
            time_label=item.get("time_label", ""),
            unread_count=int(item.get("unread_count", 0) or 0),
            source=source,
            confidence=0.78,
        )

    def _analyze_region_safely(
        self,
        snapshot: ScanSnapshot,
        region_label: str,
        image_bytes: bytes,
        instruction: str,
    ) -> dict[str, Any]:
        try:
            return self.vision_service.analyze_region_image(image_bytes, instruction)
        except Exception as exc:
            snapshot.diagnostics.setdefault("warnings", []).append(
                f"{region_label}视觉识别失败: {exc}"
            )
            return {}

    @staticmethod
    def _message_from_dict(item: dict[str, Any], source: str):
        from boss_tool.models import ChatMessage

        return ChatMessage(
            speaker=item.get("speaker", "候选人"),
            text=item.get("text", ""),
            time_label=item.get("time_label", ""),
            source=source,
            confidence=0.78,
        )

    @staticmethod
    def _without_profile_noise_messages(messages):
        noisy_markers = ("工作经历", "在线简历", "期望：", "附件简历")
        return [
            message
            for message in messages
            if not any(marker in message.text for marker in noisy_markers)
        ]

    @staticmethod
    def _merge_conversations(existing, incoming):
        merged = list(existing)
        index_by_key = {
            BossInsightPipeline._conversation_key(item): position
            for position, item in enumerate(merged)
        }
        for item in incoming:
            key = BossInsightPipeline._conversation_key(item)
            if key not in index_by_key:
                merged.append(item)
                index_by_key[key] = len(merged) - 1
                continue
            current = merged[index_by_key[key]]
            current.job_title = current.job_title or item.job_title
            current.last_message = current.last_message or item.last_message
            current.time_label = current.time_label or item.time_label
            if item.unread_count > current.unread_count:
                current.unread_count = item.unread_count
            current.confidence = max(current.confidence, item.confidence)
            if item.source == "vision":
                current.source = "ocr+vision"
        return merged

    @staticmethod
    def _conversation_key(item) -> tuple[str, str]:
        return (item.name.strip(), item.time_label.strip())
