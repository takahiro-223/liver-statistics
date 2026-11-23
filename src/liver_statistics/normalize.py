"""名前の正規化（members / ocr など複数のモジュールから使う共通処理）。"""
from __future__ import annotations

import unicodedata


def normalize_name(name: str) -> str:
    """NFKC 正規化 → 空白除去 → casefold。"""
    return "".join(unicodedata.normalize("NFKC", name).split()).casefold()
