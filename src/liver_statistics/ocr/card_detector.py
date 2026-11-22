"""メンバーカードの検出（アイコンのテンプレートマッチング）。"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np

from ..config import Config
from ..errors import ImageReadError


@dataclass(frozen=True)
class Box:
    x0: int
    y0: int
    x1: int
    y1: int

    def crop(self, image: np.ndarray) -> np.ndarray:
        return image[self.y0:self.y1, self.x0:self.x1]


@dataclass(frozen=True)
class CardRegions:
    name: Box
    level: Box
    honor: Box


def load_image(path: Path) -> np.ndarray:
    """画像を BGR で読み込む。日本語パスでも読めるよう imdecode を使う。"""
    try:
        data = np.fromfile(str(path), dtype=np.uint8)
    except OSError as exc:
        raise ImageReadError(f"画像を開けません: {path} ({exc})") from exc
    image = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if image is None:
        raise ImageReadError(f"画像として読み込めません（壊れている可能性）: {path}")
    return image


@lru_cache(maxsize=4)
def _load_template(path: str) -> np.ndarray:
    template = cv2.imread(path, cv2.IMREAD_COLOR)
    if template is None:
        raise ImageReadError(f"アイコン画像を読み込めません: {path}")
    return template


def _scaled(template: np.ndarray, scale: float) -> np.ndarray:
    if scale == 1.0:
        return template
    h, w = template.shape[:2]
    return cv2.resize(template, (max(1, round(w * scale)), max(1, round(h * scale))),
                      interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC)


def _find_anchors(image: np.ndarray, template: np.ndarray, cfg: Config) -> list[tuple[int, int, float, int]]:
    """剣アイコンの (x, y, score, icon_height) を上から順に返す。"""
    found: list[tuple[int, int, float, int]] = []
    for scale in cfg.layout.scales:
        t = _scaled(template, scale)
        if t.shape[0] > image.shape[0] or t.shape[1] > image.shape[1]:
            continue
        result = cv2.matchTemplate(image, t, cv2.TM_CCOEFF_NORMED)
        ys, xs = np.where(result >= cfg.icon_match_threshold)
        for y, x in zip(ys.tolist(), xs.tolist()):
            found.append((x, y, float(result[y, x]), t.shape[0]))
    # 近接する候補をまとめ、スコアが最大のものを残す（NMS）
    found.sort(key=lambda r: -r[2])
    kept: list[tuple[int, int, float, int]] = []
    for x, y, score, h in found:
        if all(abs(y - ky) > h or abs(x - kx) > h for kx, ky, _, _ in kept):
            kept.append((x, y, score, h))
    kept.sort(key=lambda r: r[1])
    return kept


def detect_cards(image: np.ndarray, cfg: Config) -> list[CardRegions]:
    """メンバーカード（族長を含む）の領域を上から順に返す。

    星アイコンが期待位置に無いカード、領域が画像外にはみ出すカードは、
    見切れているとみなして除外する（PRD 4.2）。
    """
    sword = _load_template(str(cfg.icons_dir / "sword.png"))
    star = _load_template(str(cfg.icons_dir / "star.png"))
    lay = cfg.layout
    height, width = image.shape[:2]
    cards: list[CardRegions] = []
    for x, y, _score, h in _find_anchors(image, sword, cfg):
        # 星アイコンの確認
        sy = round(y + lay.star_dy * h)
        tol = max(2, round(lay.star_match_tolerance * h))
        star_t = _scaled(star, h / sword.shape[0])
        y0, y1 = sy - tol, sy + tol + star_t.shape[0]
        x0, x1 = x - tol, x + tol + star_t.shape[1]
        if y0 < 0 or x0 < 0 or y1 > height or x1 > width:
            continue
        match = cv2.matchTemplate(image[y0:y1, x0:x1], star_t, cv2.TM_CCOEFF_NORMED)
        if float(match.max()) < cfg.icon_match_threshold:
            continue

        def box(bx0: float, bx1: float, by0: float, by1: float) -> Box:
            return Box(round(x + bx0 * h), round(y + by0 * h), round(x + bx1 * h), round(y + by1 * h))

        name = box(lay.name_x0, lay.name_x1, lay.name_y0, lay.name_y1)
        level = box(lay.num_x0, lay.num_x1, lay.level_y0, lay.level_y0 + lay.num_row_height)
        honor = box(lay.num_x0, lay.num_x1, lay.honor_y0, lay.honor_y0 + lay.num_row_height)
        if any(b.x0 < 0 or b.y0 < 0 or b.x1 > width or b.y1 > height for b in (name, level, honor)):
            continue
        cards.append(CardRegions(name=name, level=level, honor=honor))
    return cards
