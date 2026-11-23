"""ランキング作成の統合: DB の読み取り → 算出 → CSV の書き出し。DB は書き換えない。"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from ..config import Config
from ..db.connection import connect
from ..db.repository import Repository
from ..errors import InputError
from .calc import build_ranking
from .csv_writer import write_ranking_csv


@dataclass(frozen=True)
class RankingSummary:
    current_date: date
    previous_date: date | None
    members: int
    no_previous: list[str]
    needs_review: list[str]


def run_ranking(tribe: str, on_date: date | None, out_path: Path, cfg: Config) -> RankingSummary:
    """今回の記録日（既定は部族の最新）と、その前回の記録日を比べたランキング表を out_path に出力する。

    未登録の部族・記録が無い部族・指定した記録日にデータが無い場合は InputError。
    """
    conn = connect(cfg.db_path)
    try:
        repo = Repository(conn)
        tribe_id = repo.find_tribe(tribe)
        if tribe_id is None:
            raise InputError(f"部族が登録されていません: {tribe}")
        if on_date is None:
            current_date = repo.latest_record_date(tribe_id)
            if current_date is None:
                raise InputError(f"部族に記録がありません: {tribe}")
        elif repo.has_records_on(tribe_id, on_date):
            current_date = on_date
        else:
            raise InputError(f"指定した記録日のデータがありません: {tribe} / {on_date}")
        previous_date = repo.previous_record_date(tribe_id, current_date)
        current = repo.list_snapshots(tribe_id, current_date)
        previous = repo.list_snapshots(tribe_id, previous_date) if previous_date else []
    finally:
        conn.close()
    table = build_ranking(current, previous, current_date, previous_date)
    members = write_ranking_csv(table, out_path)
    return RankingSummary(current_date, previous_date, members, table.no_previous, table.needs_review)
