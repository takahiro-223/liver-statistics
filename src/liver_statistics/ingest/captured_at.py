"""記録日の決定。"""
from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path

from PIL import Image, UnidentifiedImageError

_EXIF_DATETIME_ORIGINAL = 36867  # Exif IFD: DateTimeOriginal
_EXIF_IFD_POINTER = 34665
_EXIF_DATETIME = 306  # IFD0: DateTime（DateTimeOriginal が無い場合の代替）
_FOLDER_DATE_RE = re.compile(r"^(\d{4})[-_]?(\d{2})[-_]?(\d{2})$")


def _exif_datetime(image_path: Path) -> datetime | None:
    try:
        with Image.open(image_path) as img:
            exif = img.getexif()
            raw = exif.get_ifd(_EXIF_IFD_POINTER).get(_EXIF_DATETIME_ORIGINAL) or exif.get(_EXIF_DATETIME)
    except (OSError, UnidentifiedImageError):
        return None
    if not raw:
        return None
    try:
        return datetime.strptime(str(raw).strip(), "%Y:%m:%d %H:%M:%S")
    except ValueError:
        return None


def parse_folder_date(folder_name: str) -> date | None:
    """フォルダ名が YYYY-MM-DD / YYYYMMDD（区切りは - _ 可）なら日付を返す。"""
    m = _FOLDER_DATE_RE.match(folder_name.strip())
    if not m:
        return None
    try:
        return date(int(m[1]), int(m[2]), int(m[3]))
    except ValueError:
        return None


def resolve_record_date(image_path: Path, override: date | None) -> tuple[date, datetime]:
    """記録日を決める。優先順: 指定値 > EXIF 撮影日時 > 親フォルダ名の日付 > ファイル更新日時。

    戻り値は (記録日, 決定に使った日時)。
    """
    if override is not None:
        return override, datetime.combine(override, datetime.min.time())
    taken = _exif_datetime(image_path)
    if taken is not None:
        return taken.date(), taken
    folder_date = parse_folder_date(image_path.parent.name)
    if folder_date is not None:
        return folder_date, datetime.combine(folder_date, datetime.min.time())
    mtime = datetime.fromtimestamp(image_path.stat().st_mtime)
    return mtime.date(), mtime
