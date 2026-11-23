"""2 つの OCR モデルの名前の読み取り結果から、採用する結果を決める（純粋なロジック）。"""
from __future__ import annotations

from ..normalize import normalize_name
from .engine import OcrResult
from .parser import clean_name


def choose_name(primary: OcrResult, secondary: OcrResult, disagree_cap: float) -> OcrResult:
    """信頼度が高い方を採用する（同じなら primary）。

    2 つの結果が（正規化後に）食い違う場合は、どちらが正しいか分からないため、
    採用した結果の信頼度を disagree_cap 以下にして「要確認」になりやすくする。
    """
    chosen = secondary if secondary.confidence > primary.confidence else primary
    if normalize_name(clean_name(primary.text)) == normalize_name(clean_name(secondary.text)):
        return chosen
    return OcrResult(text=chosen.text, confidence=min(chosen.confidence, disagree_cap))
