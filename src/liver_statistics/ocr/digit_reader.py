"""数値（レベル・名誉）のテンプレート照合による読み取り。

ゲーム独自フォントの「4」などを Tesseract が誤読する（特に「44」の並びで桁が落ちる）ため、
数値は 1 桁ずつ切り出し、`assets/digits/` のテンプレート画像との最近傍照合で読む（ADR-004 追記）。
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np

from .engine import OcrResult

GLYPH_SIZE = (24, 36)  # (幅, 高さ)。切り出した 1 桁をこの大きさに正規化して比較する
# 以下は切り出しアルゴリズムの内部定数（テンプレートの正規化と一体のため設定化しない）
_SCALE = 3
_MIN_AREA = 20  # 拡大後の画素数。これ未満の連結成分はノイズとして無視する
_COMMA_MAX_HEIGHT_RATIO = 0.5   # 最大の文字の高さに対し、これ未満ならカンマ
_MAX_ASPECT = 0.95              # 幅/高さ がこれを超える成分は桁がくっついている疑い


def _ink_mask(image: np.ndarray) -> np.ndarray | None:
    """文字部分を 255 とした二値画像（文字範囲に切り詰め済み）。文字が無ければ None。"""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    _, dark = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
    if dark.mean() > 127:  # 背景が暗い（文字が明るい）場合は反転する
        dark = cv2.bitwise_not(dark)
    ys, xs = np.where(dark > 0)
    if len(ys) == 0:
        return None
    gray = gray[max(ys.min() - 2, 0):ys.max() + 3, max(xs.min() - 2, 0):xs.max() + 3]
    gray = cv2.resize(gray, None, fx=_SCALE, fy=_SCALE, interpolation=cv2.INTER_CUBIC)
    _, ink = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
    if ink.mean() > 127:
        ink = cv2.bitwise_not(ink)
    return ink


def segment(image: np.ndarray) -> list[np.ndarray | None] | None:
    """左から順に、桁は正規化済みの float32 配列（0-1）、カンマは None として返す。

    桁がくっついている等で信頼できない場合、または文字が無い場合は None。
    """
    ink = _ink_mask(image)
    if ink is None:
        return None
    n, _, stats, _ = cv2.connectedComponentsWithStats(ink)
    comps = sorted((stats[i] for i in range(1, n) if stats[i][4] > _MIN_AREA), key=lambda s: s[0])
    if not comps:
        return None
    max_h = max(c[3] for c in comps)
    glyphs: list[np.ndarray | None] = []
    for x, y, w, h, _ in comps:
        if h < _COMMA_MAX_HEIGHT_RATIO * max_h:
            glyphs.append(None)
            continue
        if w / h > _MAX_ASPECT:
            return None
        crop = cv2.resize(ink[y:y + h, x:x + w], GLYPH_SIZE, interpolation=cv2.INTER_AREA)
        glyphs.append(crop.astype(np.float32) / 255.0)
    return glyphs


@lru_cache(maxsize=2)
def load_templates(directory: str) -> dict[str, np.ndarray]:
    """`<桁>_<連番>.png` を読み込み、桁ごとの配列 (N, 高さ, 幅) にして返す。無ければ空。"""
    by_digit: dict[str, list[np.ndarray]] = {}
    for path in sorted(Path(directory).glob("[0-9]_*.png")):
        data = cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
        if data is None or data.shape[::-1] != GLYPH_SIZE:
            continue
        by_digit.setdefault(path.name[0], []).append(data.astype(np.float32) / 255.0)
    return {d: np.stack(v) for d, v in by_digit.items()}


def read_digits(image: np.ndarray, templates: dict[str, np.ndarray], max_distance: float) -> OcrResult | None:
    """テンプレート照合で数値を読む。読めない（照合不能）場合は None。

    信頼度は、各桁の最近傍距離（画素の平均絶対差）の最大値から 0-100 に換算する
    （max_distance のとき 0。設定 DIGIT_MAX_DISTANCE）。
    """
    if len(templates) < 10:  # 0-9 が揃っていなければ使えない
        return None
    glyphs = segment(image)
    if not glyphs:
        return None
    text = ""
    worst = 0.0
    for glyph in glyphs:
        if glyph is None:
            text += ","
            continue
        best_digit, best = "", float("inf")
        for digit, stack in templates.items():
            d = float(np.abs(stack - glyph).mean(axis=(1, 2)).min())
            if d < best:
                best_digit, best = digit, d
        text += best_digit
        worst = max(worst, best)
    return OcrResult(text=text, confidence=round(max(0.0, 100.0 * (1.0 - worst / max_distance)), 1))
