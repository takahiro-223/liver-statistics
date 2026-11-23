"""ランキング表の CSV 書き出し（PRD 6 章のレイアウト）。"""
from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

from .calc import RankEntry, RankingTable

HEADER = [
    "順位", "ユーザー名", "最高レベル",
    "順位", "ユーザー名", "名誉",
    "順位", "ユーザー名", "レベル上昇値",
    "順位", "ユーザー名", "名誉上昇値",
]


def _fmt_date(d: date) -> str:
    return f"{d:%Y/%m/%d}"


def _cells(entry: RankEntry | None) -> list[str]:
    if entry is None:
        return ["", "", ""]
    return [
        "" if entry.rank is None else str(entry.rank),
        entry.name,
        "-" if entry.value is None else str(entry.value),
    ]


def write_ranking_csv(table: RankingTable, out_path: Path) -> int:
    """メンバー数（データ行数）を返す。UTF-8 BOM 付き。出力先が既存の場合は上書きする。

    1 行目は期間と「各種ランキング」を入れた 1 セル（CSV には結合セルが無いため）。
    """
    previous = "（前回なし）" if table.previous_date is None else _fmt_date(table.previous_date)
    columns = [table.level, table.honor, table.level_gain, table.honor_gain]
    rows = max(len(c) for c in columns)
    with out_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([f"{previous}〜{_fmt_date(table.current_date)} 各種ランキング"])
        writer.writerow(HEADER)
        for i in range(rows):
            line: list[str] = []
            for column in columns:
                line += _cells(column[i] if i < len(column) else None)
            writer.writerow(line)
    return rows
