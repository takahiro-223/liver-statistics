"""取り込み対象フォルダの画像列挙。"""
from __future__ import annotations

from pathlib import Path

from ..errors import ImportDirectoryNotFoundError, NoImagesFoundError

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg"}


def list_images(directory: Path) -> list[Path]:
    """直下の .png/.jpg/.jpeg（大文字小文字を区別しない）をファイル名順に返す。"""
    if not directory.is_dir():
        raise ImportDirectoryNotFoundError(f"フォルダが存在しません: {directory}")
    images = sorted(
        p for p in directory.iterdir()
        if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES and not p.name.startswith(".")
    )
    if not images:
        raise NoImagesFoundError(f"画像（PNG/JPG）が見つかりません: {directory}")
    return images
