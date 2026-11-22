"""正答率の測定スクリプト（DB には登録しない）。

使い方:
    python scripts/evaluate_accuracy.py --dir <画像フォルダ> --truth <正解CSV>

正解CSV: ヘッダー `ユーザ名,レベル,名誉`（UTF-8）。
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from liver_statistics.config import load_config
from liver_statistics.ingest.scanner import list_images
from liver_statistics.members.matcher import normalize_name
from liver_statistics.ocr.tesseract_engine import TesseractEngine
from liver_statistics.pipeline import read_cards


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", required=True, type=Path)
    parser.add_argument("--truth", required=True, type=Path)
    args = parser.parse_args()

    cfg = load_config()
    engine = TesseractEngine(cfg)
    with args.truth.open(encoding="utf-8-sig", newline="") as f:
        truth = {normalize_name(r["ユーザ名"]): r for r in csv.DictReader(f)}

    read = {}
    for path in list_images(args.dir):
        for card in read_cards(path, engine, cfg):
            read.setdefault(normalize_name(card.name), card)

    # 項目単位: ユーザ名・レベル・名誉 × 正解データの人数
    total = len(truth) * 3
    correct = 0
    errors: list[str] = []
    for key, row in truth.items():
        card = read.get(key)
        if card is None:
            errors.append(f"{row['ユーザ名']}: ユーザ名を読み取れず（レベル・名誉も不正解）")
            continue
        correct += 1  # ユーザ名
        for label, got, want in (("レベル", card.level, row["レベル"]), ("名誉", card.honor, row["名誉"])):
            if got is not None and str(got) == want.replace(",", "").strip():
                correct += 1
            else:
                errors.append(f"{row['ユーザ名']}: {label} 正解={want} 読取={got}")
    rate = correct / total * 100 if total else 0.0
    print(f"正答率: {rate:.1f}% ({correct}/{total} 項目)  目標: 70% 以上 → {'達成' if rate >= 70 else '未達'}")
    for e in errors:
        print("  誤り:", e)
    return 0


if __name__ == "__main__":
    sys.exit(main())
