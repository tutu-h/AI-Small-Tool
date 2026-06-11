from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from typing import Iterable

from PIL import Image
from rapidocr_onnxruntime import RapidOCR


@dataclass(slots=True)
class OcrLine:
    text: str
    score: float


class OcrService:
    def __init__(self) -> None:
        self.engine = RapidOCR()
        self._warmed_up = False

    def extract_lines(self, image_bytes: bytes) -> list[OcrLine]:
        image = Image.open(BytesIO(image_bytes))
        result, _ = self.engine(image)
        lines: list[OcrLine] = []
        if not result:
            return lines
        for item in result:
            _, text, score = item
            lines.append(OcrLine(text=text.strip(), score=float(score)))
        return lines

    @staticmethod
    def texts(lines: Iterable[OcrLine]) -> list[str]:
        return [line.text for line in lines if line.text]

    def warm_up(self) -> None:
        if self._warmed_up:
            return
        sample = Image.new("RGB", (64, 64), color="white")
        self.engine(sample)
        self._warmed_up = True
