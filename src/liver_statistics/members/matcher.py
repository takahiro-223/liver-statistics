"""メンバー名の正規化と、既存メンバーとの照合。"""
from __future__ import annotations

import difflib
import unicodedata
from dataclasses import dataclass


def normalize_name(name: str) -> str:
    """NFKC 正規化 → 空白除去 → casefold。"""
    return "".join(unicodedata.normalize("NFKC", name).split()).casefold()


@dataclass(frozen=True)
class MatchResult:
    member_id: int | None          # 既存メンバーなら ID、新規なら None
    name_key: str
    similar_to: str | None = None  # 新規だが類似する既存メンバーがある場合、その表示名


def resolve_member(repo, tribe_id: int, name: str, threshold: float) -> MatchResult:
    """name_key / 別名が一致すれば既存メンバー。一致しなければ新規。

    新規で、同部族の既存メンバーに類似名（ratio >= threshold）があれば similar_to を返す。
    """
    key = normalize_name(name)
    existing = repo.find_member(tribe_id, key)
    if existing is not None:
        return MatchResult(member_id=existing, name_key=key)
    best: tuple[float, str] | None = None
    for member_name, member_key in repo.list_member_keys(tribe_id):
        ratio = difflib.SequenceMatcher(None, key, member_key).ratio()
        if ratio >= threshold and (best is None or ratio > best[0]):
            best = (ratio, member_name)
    return MatchResult(member_id=None, name_key=key, similar_to=best[1] if best else None)
