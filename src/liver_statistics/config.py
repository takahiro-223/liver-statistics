"""設定管理。`.env` と `config/ocr_layout.toml` を読み込む。"""
from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from .errors import InputError

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class LayoutConfig:
    """アイコン高さ h を単位とした領域の相対比率（config/ocr_layout.toml）。"""

    star_dy: float          # 剣アイコン上端から星アイコン上端までの距離
    star_match_tolerance: float  # 星アイコン検出の許容ずれ（h 単位）
    name_x0: float
    name_x1: float
    name_y0: float
    name_y1: float
    num_x0: float
    num_x1: float
    num_row_height: float
    level_y0: float
    honor_y0: float
    scales: tuple[float, ...]    # アイコンテンプレートの拡縮率


@dataclass(frozen=True)
class Config:
    db_path: Path
    log_level: str
    ocr_lang: str
    tesseract_cmd: str | None
    confidence_threshold: float
    icon_match_threshold: float
    name_similarity_threshold: float
    name_edit_min_length: int   # 編集距離 1 以内を類似名とみなす最小の名前の長さ
    tesseract_timeout_sec: float
    number_ocr_lang: str        # Tesseract にフォールバックして数値を読む際の言語
    digit_max_distance: float   # 桁テンプレートとの距離がこの値のとき信頼度 0
    icons_dir: Path
    digits_dir: Path
    layout: LayoutConfig


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name, "")
    if raw == "":
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise InputError(f"環境変数 {name} が数値ではありません: {raw!r}") from exc


def _env_float_in(name: str, default: float, low: float, high: float | None = None) -> float:
    """low を超え（high があれば high 以下の）数値。範囲外は InputError。"""
    value = _env_float(name, default)
    if not value > low or (high is not None and value > high):
        bound = f"{low} より大きく {high} 以下" if high is not None else f"{low} より大きい値"
        raise InputError(f"環境変数 {name} は {bound}を指定してください: {value}")
    return value


def _env_min_length(name: str, default: int) -> int:
    value = _env_float(name, default)
    if value < 1 or value != int(value):
        raise InputError(f"環境変数 {name} は 1 以上の整数を指定してください: {value}")
    return int(value)


_LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")


def _env_log_level() -> str:
    level = (os.environ.get("LOG_LEVEL") or "INFO").upper()
    if level not in _LOG_LEVELS:
        raise InputError(f"環境変数 LOG_LEVEL が不正です: {level!r}（{', '.join(_LOG_LEVELS)} のいずれか）")
    return level


def _resolve(path: str) -> Path:
    p = Path(path)
    return p if p.is_absolute() else PROJECT_ROOT / p


def load_layout(path: Path) -> LayoutConfig:
    try:
        with path.open("rb") as f:
            data = tomllib.load(f)
    except FileNotFoundError as exc:
        raise InputError(f"レイアウト設定ファイルが見つかりません: {path}") from exc
    try:
        return LayoutConfig(
            star_dy=data["icon"]["star_dy"],
            star_match_tolerance=data["icon"]["star_match_tolerance"],
            name_x0=data["name"]["x0"],
            name_x1=data["name"]["x1"],
            name_y0=data["name"]["y0"],
            name_y1=data["name"]["y1"],
            num_x0=data["number"]["x0"],
            num_x1=data["number"]["x1"],
            num_row_height=data["number"]["row_height"],
            level_y0=data["number"]["level_y0"],
            honor_y0=data["number"]["honor_y0"],
            scales=tuple(data["icon"]["scales"]),
        )
    except KeyError as exc:
        raise InputError(f"レイアウト設定に項目がありません: {exc} ({path})") from exc


def load_config() -> Config:
    load_dotenv(PROJECT_ROOT / ".env")
    return Config(
        db_path=_resolve(os.environ.get("DB_PATH") or "data/liver_statistics.db"),
        log_level=_env_log_level(),
        ocr_lang=os.environ.get("OCR_LANG") or "jpn+eng",
        tesseract_cmd=os.environ.get("TESSERACT_CMD") or None,
        confidence_threshold=_env_float_in("CONFIDENCE_THRESHOLD", 60.0, -1, 100),
        icon_match_threshold=_env_float_in("ICON_MATCH_THRESHOLD", 0.7, 0, 1),
        name_similarity_threshold=_env_float_in("NAME_SIMILARITY_THRESHOLD", 0.8, 0, 1),
        name_edit_min_length=_env_min_length("NAME_EDIT_MIN_LENGTH", 3),
        tesseract_timeout_sec=_env_float_in("TESSERACT_TIMEOUT_SEC", 30.0, 0),
        number_ocr_lang=os.environ.get("NUMBER_OCR_LANG") or "eng",
        digit_max_distance=_env_float_in("DIGIT_MAX_DISTANCE", 0.30, 0),
        icons_dir=_resolve(os.environ.get("ICONS_DIR") or "assets/icons"),
        digits_dir=_resolve(os.environ.get("DIGITS_DIR") or "assets/digits"),
        layout=load_layout(
            _resolve(os.environ.get("OCR_LAYOUT_PATH") or "config/ocr_layout.toml")
        ),
    )
