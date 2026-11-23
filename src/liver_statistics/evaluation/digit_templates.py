"""数値読み取り用の桁テンプレート（assets/digits/）を、サンプル画像と正解 CSV から作成する。

Tesseract で読んだ結果が正解 CSV の値（レベル・名誉）と一致し、桁数と切り出した桁の数が
合うカードだけから桁画像を集める。
"""
from __future__ import annotations

import csv
from pathlib import Path

import cv2
import numpy as np

from ..config import Config
from ..errors import InputError
from ..ingest.scanner import list_images
from ..ocr.card_detector import check_assets, detect_cards, load_image
from ..ocr.digit_reader import segment
from ..ocr.tesseract_engine import TesseractEngine


def collect_glyphs(directory: Path, truth_csv: Path, engine: TesseractEngine, cfg: Config,
                   per_digit: int) -> dict[str, list[np.ndarray]]:
    """桁ごとの正規化済み桁画像（float32, 0-1）を最大 per_digit 枚集める。"""
    check_assets(cfg)
    with truth_csv.open(encoding="utf-8-sig", newline="") as f:
        values = {v.replace(",", "").strip() for r in csv.DictReader(f) for v in (r["レベル"], r["名誉"])}

    collected: dict[str, list[np.ndarray]] = {str(d): [] for d in range(10)}
    for path in list_images(directory):
        image = load_image(path)
        for regions in detect_cards(image, cfg):
            for box in (regions.level, regions.honor):
                crop = box.crop(image)
                text = engine.read_number_tesseract(crop).text
                glyphs = segment(crop)
                if text.replace(",", "") not in values or glyphs is None:
                    continue
                if [g is None for g in glyphs] != [c == "," for c in text]:
                    continue
                for ch, g in zip(text, glyphs):
                    if g is not None and len(collected[ch]) < per_digit:
                        collected[ch].append(g)
    return collected


def write_templates(collected: dict[str, list[np.ndarray]], out_dir: Path) -> dict[str, int]:
    """0-9 すべてが揃っていれば既存テンプレートを置き換えて保存する。足りなければ InputError。"""
    missing = [d for d, v in collected.items() if not v]
    if missing:
        raise InputError(f"桁 {','.join(missing)} のサンプルが集まりませんでした。サンプルを増やしてください。")
    # 先に全件を PNG に変換し、失敗しても既存テンプレートを壊さないようにする
    encoded: dict[str, bytes] = {}
    for digit, glyphs in collected.items():
        for i, g in enumerate(glyphs):
            ok, buf = cv2.imencode(".png", (g * 255).astype(np.uint8))
            if not ok:
                raise InputError(f"桁画像を PNG に変換できません: {digit}_{i:02d}")
            encoded[f"{digit}_{i:02d}.png"] = buf.tobytes()
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("[0-9]_*.png"):
        old.unlink()
    for name, data in encoded.items():
        (out_dir / name).write_bytes(data)
    return {d: len(v) for d, v in collected.items()}
