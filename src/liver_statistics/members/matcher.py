"""メンバー名の正規化と、既存メンバーとの照合。"""
from __future__ import annotations

import difflib
from dataclasses import dataclass

from ..normalize import normalize_name  # noqa: F401 - 既存の import 先（matcher）との互換のため再公開


@dataclass(frozen=True)
class MatchResult:
    member_id: int | None          # 既存メンバーなら ID、新規なら None
    name_key: str
    similar_to: str | None = None  # 新規だが類似する既存メンバーがある場合、その表示名


def _within_one_edit(a: str, b: str) -> bool:
    """a と b の編集距離（挿入・削除・置換）が 1 以内か。"""
    if abs(len(a) - len(b)) > 1:
        return False
    if len(a) > len(b):
        a, b = b, a
    i = 0
    while i < len(a) and a[i] == b[i]:
        i += 1
    if len(a) == len(b):
        return a[i + 1:] == b[i + 1:]
    return a[i:] == b[i + 1:]


def resolve_member(repo, tribe_id: int, name: str, threshold: float, edit_min_length: int) -> MatchResult:
    """name_key / 別名が一致すれば既存メンバー。一致しなければ新規。

    新規で、同部族の既存メンバーに類似名があれば similar_to を返す。類似とは、
    ratio >= threshold、または両者とも edit_min_length 文字以上で編集距離 1 以内（短い名前の
    1 文字違いは ratio が閾値に届かないため）。
    """
    key = normalize_name(name)
    existing = repo.find_member(tribe_id, key)
    if existing is not None:
        return MatchResult(member_id=existing, name_key=key)
    best: tuple[float, str] | None = None
    for member_name, member_key in repo.list_member_keys(tribe_id):
        ratio = difflib.SequenceMatcher(None, key, member_key).ratio()
        similar = ratio >= threshold or (
            min(len(key), len(member_key)) >= edit_min_length and _within_one_edit(key, member_key)
        )
        if similar and (best is None or ratio > best[0]):
            best = (ratio, member_name)  # 表示する類似名は ratio が最大のもの
    return MatchResult(member_id=None, name_key=key, similar_to=best[1] if best else None)
