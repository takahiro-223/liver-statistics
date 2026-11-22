"""OCR エンジンのインターフェース。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import numpy as np


@dataclass(frozen=True)
class OcrResult:
    text: str
    confidence: float  # 0-100。文字が検出できなければ 0


class OcrEngine(Protocol):
    def read_name(self, image: np.ndarray) -> OcrResult: ...

    def read_number(self, image: np.ndarray) -> OcrResult: ...
