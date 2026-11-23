"""ランキングの算出（DB・ファイルに触れない純粋な関数）。

規則は EDD 5.9（PRD 4.6）に従う。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from ..db.repository import MemberSnapshot


@dataclass(frozen=True)
class RankEntry:
    rank: int | None     # 順位。None は順位なし（CSV では空欄）
    name: str            # 表示名
    value: int | None    # None は値なし（CSV では「-」）


@dataclass(frozen=True)
class RankingTable:
    current_date: date
    previous_date: date | None      # 前回の記録日。無ければ None（初回）
    level: list[RankEntry]          # 最高レベル
    honor: list[RankEntry]          # 名誉
    level_gain: list[RankEntry]     # レベル上昇値
    honor_gain: list[RankEntry]     # 名誉上昇値
    no_previous: list[str]          # 前回の記録が無いメンバー（前回の記録日が無い場合は空）
    needs_review: list[str]         # 今回または前回の記録が要確認のメンバー


def _gain(current: int | None, previous: int | None) -> int | None:
    return None if current is None or previous is None else current - previous


def _rank(items: list[tuple[str, str, int | None]]) -> list[RankEntry]:
    """(name_key, 表示名, 値) を、値の降順・同値は name_key の昇順に並べ、競技順位を付ける。

    値が None のものは末尾に並べ、順位は付けない。順位は 1 + 「自分より値が大きい人数」（1, 2, 2, 4 …）。
    """
    values = [v for _, _, v in items if v is not None]
    ordered = sorted(items, key=lambda t: (t[2] is None, -(t[2] or 0), t[0]))
    return [
        RankEntry(None if v is None else 1 + sum(1 for x in values if x > v), name, v)
        for _, name, v in ordered
    ]


def build_ranking(
    current: list[MemberSnapshot], previous: list[MemberSnapshot],
    current_date: date, previous_date: date | None,
) -> RankingTable:
    """今回の記録日にデータがあるメンバーを、前回の記録（member_id が同じもの）と比べてランキングにする。"""
    prev_by_id = {s.member_id: s for s in previous} if previous_date is not None else {}
    levels, honors, level_gains, honor_gains = [], [], [], []
    no_previous: list[str] = []
    needs_review: list[str] = []
    for cur in sorted(current, key=lambda s: s.name_key):
        prev = prev_by_id.get(cur.member_id)
        levels.append((cur.name_key, cur.name, cur.level))
        honors.append((cur.name_key, cur.name, cur.honor))
        level_gains.append((cur.name_key, cur.name, _gain(cur.level, prev.level) if prev else None))
        honor_gains.append((cur.name_key, cur.name, _gain(cur.honor, prev.honor) if prev else None))
        if previous_date is not None and prev is None:
            no_previous.append(cur.name)
        if cur.needs_review or (prev is not None and prev.needs_review):
            needs_review.append(cur.name)
    return RankingTable(
        current_date=current_date, previous_date=previous_date,
        level=_rank(levels), honor=_rank(honors),
        level_gain=_rank(level_gains), honor_gain=_rank(honor_gains),
        no_previous=no_previous, needs_review=needs_review,
    )
