"""Tesseract による OCR 実装（ローカル完結）。"""
from __future__ import annotations

import cv2
import numpy as np
import pytesseract
from pytesseract import Output, TesseractNotFoundError

from ..config import Config
from ..errors import OcrEngineUnavailableError
from .digit_reader import load_templates, read_digits
from .engine import OcrResult

_TESSERACT_TIMEOUT_SEC = 30


class TesseractEngine:
    def __init__(self, cfg: Config) -> None:
        self._lang = cfg.ocr_lang
        self._digits_dir = str(cfg.digits_dir)
        if cfg.tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = cfg.tesseract_cmd
        try:
            pytesseract.get_tesseract_version()
        except TesseractNotFoundError as exc:
            raise OcrEngineUnavailableError(
                "Tesseract が見つかりません。`brew install tesseract tesseract-lang` で導入するか、"
                "環境変数 TESSERACT_CMD を設定してください。"
            ) from exc

    @staticmethod
    def _preprocess(image: np.ndarray) -> np.ndarray:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        gray = cv2.resize(gray, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
        # 文字が黒・背景が白になるよう、背景（縁の多数派）が黒なら反転する
        if binary.mean() < 127:
            binary = cv2.bitwise_not(binary)
        return cv2.copyMakeBorder(binary, 10, 10, 10, 10, cv2.BORDER_CONSTANT, value=255)

    @staticmethod
    def _preprocess_name(image: np.ndarray) -> np.ndarray:
        """名前用の前処理。二値化・拡大はかえって文字を崩すため、グレースケールのまま渡す。"""
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        return cv2.copyMakeBorder(gray, 20, 20, 20, 20, cv2.BORDER_CONSTANT, value=255)

    def _run(self, prepared: np.ndarray, lang: str, extra: str) -> OcrResult:
        data = pytesseract.image_to_data(
            prepared, lang=lang, config=f"--psm 7 {extra}",
            output_type=Output.DICT, timeout=_TESSERACT_TIMEOUT_SEC,
        )
        words = [(t, float(c)) for t, c in zip(data["text"], data["conf"]) if t.strip() and float(c) >= 0]
        if not words:
            return OcrResult(text="", confidence=0.0)
        text = " ".join(t for t, _ in words) if len(words) > 1 else words[0][0]
        return OcrResult(text=text.strip(), confidence=min(c for _, c in words))

    def read_name(self, image: np.ndarray) -> OcrResult:
        return self._run(self._preprocess_name(image), self._lang, "")

    def read_number(self, image: np.ndarray) -> OcrResult:
        """数値は桁テンプレート照合を優先し、使えない場合のみ Tesseract で読む。"""
        result = read_digits(image, load_templates(self._digits_dir))
        return result if result is not None else self.read_number_tesseract(image)

    def read_number_tesseract(self, image: np.ndarray) -> OcrResult:
        return self._run(self._preprocess(image), "eng", "-c tessedit_char_whitelist=0123456789,")
