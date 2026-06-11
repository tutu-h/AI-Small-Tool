from __future__ import annotations

from boss_tool.ocr import OcrService


def test_ocr_service_can_be_warmed_up() -> None:
    service = OcrService()

    service.warm_up()

    assert service._warmed_up is True
