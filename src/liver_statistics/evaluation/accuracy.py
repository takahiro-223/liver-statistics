"""正答率の測定（DB には登録しない）。項目単位: ユーザ名・レベル・名誉 × 正解データの人数。"""
from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path

from ..config import Config
from ..errors import InputError
from ..ingest.scanner import list_images
from ..members.matcher import normalize_name
from ..ocr.card_detector import check_assets
from ..ocr.engine import OcrEngine
from ..pipeline import read_cards

_TRUTH_COLUMNS = ("ユーザ名", "レベル", "名誉")
TARGET_RATE = 70.0  # BRD の成功基準（%）


@dataclass
class AccuracyReport:
    correct: int = 0
    total: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def rate(self) -> float:
        return self.correct / self.total * 100 if self.total else 0.0

    @property
    def achieved(self) -> bool:
        return self.rate >= TARGET_RATE


def load_truth(path: Path) -> dict[str, dict[str, str]]:
    """正解 CSV（ヘッダー `ユーザ名,レベル,名誉`、UTF-8）を正規化名で引ける辞書にする。"""
    try:
        with path.open(encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f))
    except OSError as exc:
        raise InputError(f"正解データを読めません: {path} ({exc})") from exc
    truth: dict[str, dict[str, str]] = {}
    for line, row in enumerate(rows, start=2):
        if any(row.get(c) is None for c in _TRUTH_COLUMNS):
            raise InputError(f"正解データに列 {'/'.join(_TRUTH_COLUMNS)} が必要です: {path}（{line}行目）")
        key = normalize_name(row["ユーザ名"])
        if key in truth:
            raise InputError(f"正解データのユーザ名が重複しています: {row['ユーザ名']}（{line}行目）")
        truth[key] = row
    return truth


def evaluate(directory: Path, truth: dict[str, dict[str, str]], engine: OcrEngine, cfg: Config) -> AccuracyReport:
    check_assets(cfg)
    read = {}
    for path in list_images(directory):
        for card in read_cards(path, engine, cfg):
            read.setdefault(normalize_name(card.name), card)

    report = AccuracyReport(total=len(truth) * 3)
    for key, row in truth.items():
        card = read.get(key)
        if card is None:
            report.errors.append(f"{row['ユーザ名']}: ユーザ名を読み取れず（レベル・名誉も不正解）")
            continue
        report.correct += 1  # ユーザ名
        for label, got, want in (("レベル", card.level, row["レベル"]), ("名誉", card.honor, row["名誉"])):
            if got is not None and str(got) == want.replace(",", "").strip():
                report.correct += 1
            else:
                report.errors.append(f"{row['ユーザ名']}: {label} 正解={want} 読取={got}")
    return report
