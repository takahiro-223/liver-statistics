"""Tesseract による OCR 実装（ローカル完結）。"""
from __future__ import annotations

import logging
import shlex
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import cv2
import numpy as np
import pytesseract
from pytesseract import Output, TesseractNotFoundError

from ..config import Config
from ..errors import OcrEngineUnavailableError
from .digit_reader import load_templates, read_digits
from .engine import OcrResult
from .name_choice import choose_name

logger = logging.getLogger(__name__)


class TesseractEngine:
    def __init__(self, cfg: Config) -> None:
        self._lang = cfg.ocr_lang
        self._number_lang = cfg.number_ocr_lang
        self._timeout = cfg.tesseract_timeout_sec
        self._max_distance = cfg.digit_max_distance
        self._digits_dir = str(cfg.digits_dir)
        self._best_dir = cfg.tessdata_best_dir
        self._disagree_cap = cfg.name_disagree_confidence_cap
        if cfg.tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = cfg.tesseract_cmd
        try:
            pytesseract.get_tesseract_version()
        except TesseractNotFoundError as exc:
            raise OcrEngineUnavailableError(
                "Tesseract が見つかりません。`brew install tesseract tesseract-lang` で導入するか、"
                "環境変数 TESSERACT_CMD を設定してください。"
            ) from exc
        if self._best_dir is not None:
            self._check_best_model()
            logger.info("名前の読み取り: 2 モデル（高精度モデル: %s）", self._best_dir)
        else:
            logger.info("名前の読み取り: 1 モデル（高精度モデルなし。取得手順は docs/setup.md）")

    def _check_best_model(self) -> None:
        """高精度モデルが実際に読めることを、白い画像での試し読みで確認する。

        壊れた・空の学習データが「全画像の失敗」として埋もれないよう、画像処理の前に止める。
        """
        try:
            self._run(np.full((40, 120), 255, np.uint8), self._lang, "", self._best_dir)
        except (RuntimeError, OSError) as exc:  # pytesseract.TesseractError は RuntimeError の派生
            raise OcrEngineUnavailableError(
                f"高精度モデルの学習データを読み込めません（壊れている可能性）: {self._best_dir} ({exc})"
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

    @staticmethod
    def _preprocess_name_stretched(image: np.ndarray) -> np.ndarray:
        """高精度モデル用。文字が黒・背景が白に近づくよう、濃淡を引き伸ばす（拡大・二値化はしない）。"""
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY).astype(np.float32)
        low, high = np.percentile(gray, 2), np.percentile(gray, 90)
        stretched = np.clip((gray - low) / max(high - low, 1.0) * 255, 0, 255).astype(np.uint8)
        return cv2.copyMakeBorder(stretched, 20, 20, 20, 20, cv2.BORDER_CONSTANT, value=255)

    def _run(self, prepared: np.ndarray, lang: str, extra: str, tessdata_dir: Path | None = None) -> OcrResult:
        if tessdata_dir is not None:
            extra = f"{extra} --tessdata-dir {shlex.quote(str(tessdata_dir))}"
        data = pytesseract.image_to_data(
            prepared, lang=lang, config=f"--psm 7 {extra}",
            output_type=Output.DICT, timeout=self._timeout,
        )
        words = [(t, float(c)) for t, c in zip(data["text"], data["conf"]) if t.strip() and float(c) >= 0]
        if not words:
            return OcrResult(text="", confidence=0.0)
        text = " ".join(t for t, _ in words) if len(words) > 1 else words[0][0]
        return OcrResult(text=text.strip(), confidence=min(c for _, c in words))

    def read_name(self, image: np.ndarray) -> OcrResult:
        """名前を読む。高精度モデルがあれば 2 モデルで読み、結果を突き合わせる（ADR-004 追記）。"""
        if self._best_dir is None:
            return self._run(self._preprocess_name(image), self._lang, "")
        # 2 つの Tesseract は別プロセスで動くので、並列に呼ぶ
        with ThreadPoolExecutor(max_workers=1) as pool:
            second = pool.submit(
                self._run, self._preprocess_name_stretched(image), self._lang, "", self._best_dir
            )
            primary = self._run(self._preprocess_name(image), self._lang, "")
            return choose_name(primary, second.result(), self._disagree_cap)

    def read_number(self, image: np.ndarray) -> OcrResult:
        """数値は桁テンプレート照合を優先し、使えない場合のみ Tesseract で読む。"""
        result = read_digits(image, load_templates(self._digits_dir), self._max_distance)
        return result if result is not None else self.read_number_tesseract(image)

    def read_number_tesseract(self, image: np.ndarray) -> OcrResult:
        return self._run(self._preprocess(image), self._number_lang, "-c tessedit_char_whitelist=0123456789,")
