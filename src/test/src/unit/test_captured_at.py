import os
from datetime import date, datetime

from PIL import Image

from liver_statistics.ingest.captured_at import parse_folder_date, resolve_record_date


def _png(path, exif_dt=None):
    img = Image.new("RGB", (4, 4))
    if exif_dt:
        exif = Image.Exif()
        exif[306] = exif_dt
        img.save(path, exif=exif)
    else:
        img.save(path)


def test_override_wins(tmp_path):
    p = tmp_path / "a.png"
    _png(p, "2026:01:02 03:04:05")
    assert resolve_record_date(p, date(2026, 5, 6))[0] == date(2026, 5, 6)


def test_exif_before_folder(tmp_path):
    d = tmp_path / "2026-11-22"
    d.mkdir()
    p = d / "a.png"
    _png(p, "2026:11:19 22:53:27")
    assert resolve_record_date(p, None) == (date(2026, 11, 19), datetime(2026, 11, 19, 22, 53, 27))


def test_folder_name_before_mtime(tmp_path):
    d = tmp_path / "20261122"
    d.mkdir()
    p = d / "a.png"
    _png(p)
    os.utime(p, (0, 0))
    assert resolve_record_date(p, None)[0] == date(2026, 11, 22)


def test_mtime_fallback(tmp_path):
    p = tmp_path / "shots" / "a.png"
    p.parent.mkdir()
    _png(p)
    ts = datetime(2026, 3, 4, 12, 0).timestamp()
    os.utime(p, (ts, ts))
    assert resolve_record_date(p, None)[0] == date(2026, 3, 4)


def test_parse_folder_date():
    assert parse_folder_date("2026-11-22") == date(2026, 11, 22)
    assert parse_folder_date("2026_11_22") == date(2026, 11, 22)
    assert parse_folder_date("2026-13-40") is None
    assert parse_folder_date("shots") is None
