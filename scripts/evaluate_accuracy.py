"""正答率の測定スクリプト（DB には登録しない）。ロジックは liver_statistics.evaluation にある。

使い方:
    python scripts/evaluate_accuracy.py --dir <画像フォルダ> --truth <正解CSV>

正解CSV: ヘッダー `ユーザ名,レベル,名誉`（UTF-8）。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from liver_statistics.config import load_config
from liver_statistics.errors import LiverStatisticsError
from liver_statistics.evaluation.accuracy import TARGET_RATE, evaluate, load_truth
from liver_statistics.ocr.tesseract_engine import TesseractEngine


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", required=True, type=Path)
    parser.add_argument("--truth", required=True, type=Path)
    args = parser.parse_args()
    try:
        cfg = load_config()
        report = evaluate(args.dir, load_truth(args.truth), TesseractEngine(cfg), cfg)
    except LiverStatisticsError as exc:
        print(f"エラー: {exc}", file=sys.stderr)
        return 1
    print(f"正答率: {report.rate:.1f}% ({report.correct}/{report.total} 項目)  "
          f"目標: {TARGET_RATE:.0f}% 以上 → {'達成' if report.achieved else '未達'}")
    for e in report.errors:
        print("  誤り:", e)
    return 0


if __name__ == "__main__":
    sys.exit(main())
