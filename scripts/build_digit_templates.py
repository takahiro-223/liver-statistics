"""桁テンプレート（assets/digits/）の作成スクリプト。ロジックは liver_statistics.evaluation にある。

使い方:
    python scripts/build_digit_templates.py --dir <画像フォルダ> --truth <正解CSV> [--per-digit 30]

既存の `assets/digits/*.png` は置き換える。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from liver_statistics.config import load_config
from liver_statistics.errors import LiverStatisticsError
from liver_statistics.evaluation.digit_templates import collect_glyphs, write_templates
from liver_statistics.ocr.tesseract_engine import TesseractEngine


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", required=True, type=Path)
    parser.add_argument("--truth", required=True, type=Path)
    parser.add_argument("--per-digit", type=int, default=30, help="桁ごとに保存する最大枚数")
    args = parser.parse_args()
    try:
        cfg = load_config()
        collected = collect_glyphs(args.dir, args.truth, TesseractEngine(cfg), cfg, args.per_digit)
        counts = write_templates(collected, cfg.digits_dir)
    except LiverStatisticsError as exc:
        print(f"エラー: {exc}", file=sys.stderr)
        return 1
    print("作成:", counts, "→", cfg.digits_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
