"""OCR 結果の解釈と「要確認」判定。"""
from __future__ import annotations

import re
from dataclasses import dataclass

from ..config import Config
from .engine import OcrResult

_NUMBER_RE = re.compile(r"^\d{1,3}(,\d{3})*$|^\d+$")
# Tesseract の jpn は文字間に空白を入れるため、非 ASCII 文字に隣接する空白を除去する
_CJK_SPACE_RE = re.compile(r"(?<=[^\x00-\x7f])\s+|\s+(?=[^\x00-\x7f])")


def clean_name(text: str) -> str:
    return _CJK_SPACE_RE.sub("", text.strip())


@dataclass(frozen=True)
class ParsedCard:
    name: str
    level: int | None
    honor: int | None
    needs_review: bool
    review_reasons: list[str]
    min_confidence: float


def parse_number(text: str) -> int | None:
    """カンマ区切りの数値を整数に変換する。解釈できなければ None。"""
    cleaned = text.strip().replace(" ", "")
    if not cleaned or not _NUMBER_RE.match(cleaned):
        return None
    return int(cleaned.replace(",", ""))


def parse_card(name: OcrResult, level: OcrResult, honor: OcrResult, cfg: Config) -> ParsedCard | None:
    """名前が空の場合は None（カードを破棄する）。"""
    cleaned = clean_name(name.text)
    if not cleaned:
        return None
    reasons: list[str] = []
    level_value = parse_number(level.text)
    honor_value = parse_number(honor.text)
    if level_value is None:
        reasons.append("parse_error_level")
    elif level.confidence < cfg.confidence_threshold:
        reasons.append("low_confidence_level")
    if honor_value is None:
        reasons.append("parse_error_honor")
    elif honor.confidence < cfg.confidence_threshold:
        reasons.append("low_confidence_honor")
    if name.confidence < cfg.confidence_threshold:
        reasons.append("low_confidence_name")
    return ParsedCard(
        name=cleaned,
        level=level_value,
        honor=honor_value,
        needs_review=bool(reasons),
        review_reasons=reasons,
        min_confidence=min(name.confidence, level.confidence, honor.confidence),
    )
