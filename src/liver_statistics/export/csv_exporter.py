"""CSV 出力。"""
from __future__ import annotations

import csv
from pathlib import Path

from ..db.repository import RecordRow
from .csv_safe import atomic_csv, csv_safe

HEADER = ["部族名", "記録日", "ユーザ名", "レベル", "名誉", "要確認"]


def export_csv(rows: list[RecordRow], out_path: Path) -> int:
    """UTF-8 BOM 付きで書き出し、出力件数を返す。既存ファイルは上書きする（書き込みに成功したときだけ置き換える）。

    部族名・ユーザ名は、数式として解釈されないよう csv_safe を通す。
    """
    with atomic_csv(out_path) as f:
        writer = csv.writer(f)
        writer.writerow(HEADER)
        for r in rows:
            writer.writerow([
                csv_safe(r.tribe), r.record_date, csv_safe(r.member),
                "" if r.level is None else r.level,
                "" if r.honor is None else r.honor,
                1 if r.needs_review else 0,
            ])
    return len(rows)
