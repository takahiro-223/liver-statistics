"""数値読み取り用の桁テンプレート（assets/digits/）を、サンプル画像と正解 CSV から作成する。

使い方:
    python scripts/build_digit_templates.py --dir <画像フォルダ> --truth <正解CSV> [--per-digit 30]

Tesseract で読んだ結果が正解 CSV の値（レベル・名誉）と一致し、桁数と切り出した桁の数が
合うカードだけから、桁画像を集める。既存の `assets/digits/*.png` は置き換える。
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import cv2
import numpy as np

from liver_statistics.config import load_config
from liver_statistics.ingest.scanner import list_images
from liver_statistics.ocr.card_detector import detect_cards, load_image
from liver_statistics.ocr.digit_reader import segment
from liver_statistics.ocr.tesseract_engine import TesseractEngine


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", required=True, type=Path)
    parser.add_argument("--truth", required=True, type=Path)
    parser.add_argument("--per-digit", type=int, default=30, help="桁ごとに保存する最大枚数")
    args = parser.parse_args()

    cfg = load_config()
    engine = TesseractEngine(cfg)
    with args.truth.open(encoding="utf-8-sig", newline="") as f:
        values = {v.replace(",", "").strip() for r in csv.DictReader(f) for v in (r["レベル"], r["名誉"])}

    collected: dict[str, list[np.ndarray]] = {str(d): [] for d in range(10)}
    for path in list_images(args.dir):
        image = load_image(path)
        for regions in detect_cards(image, cfg):
            for box in (regions.level, regions.honor):
                crop = box.crop(image)
                text = engine.read_number_tesseract(crop).text
                digits = text.replace(",", "")
                glyphs = segment(crop)
                if digits not in values or glyphs is None:
                    continue
                if [g is None for g in glyphs] != [c == "," for c in text]:
                    continue
                for ch, g in zip(text, glyphs):
                    if g is not None and len(collected[ch]) < args.per_digit:
                        collected[ch].append(g)

    missing = [d for d, v in collected.items() if not v]
    if missing:
        print(f"桁 {','.join(missing)} のサンプルが集まりませんでした。サンプルを増やしてください。", file=sys.stderr)
        return 1
    out = cfg.digits_dir
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("[0-9]_*.png"):
        old.unlink()
    for digit, glyphs in collected.items():
        for i, g in enumerate(glyphs):
            ok, buf = cv2.imencode(".png", (g * 255).astype(np.uint8))
            (out / f"{digit}_{i:02d}.png").write_bytes(buf.tobytes())
    print("作成:", {d: len(v) for d, v in collected.items()}, "→", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
