"""CSV 出力。"""
from __future__ import annotations

import csv
from pathlib import Path

from ..db.repository import RecordRow

HEADER = ["部族名", "記録日", "ユーザ名", "レベル", "名誉", "要確認"]


def export_csv(rows: list[RecordRow], out_path: Path) -> int:
    """UTF-8 BOM 付きで書き出し、出力件数を返す。既存ファイルは上書きする。"""
    with out_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(HEADER)
        for r in rows:
            writer.writerow([
                r.tribe, r.record_date, r.member,
                "" if r.level is None else r.level,
                "" if r.honor is None else r.honor,
                1 if r.needs_review else 0,
            ])
    return len(rows)
