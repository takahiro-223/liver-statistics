import dataclasses

import pytest

from liver_statistics.errors import InputError
from liver_statistics.ocr.card_detector import check_assets


def test_check_assets_ok(cfg):
    check_assets(cfg)


def test_check_assets_missing(cfg, tmp_path):
    bad = dataclasses.replace(cfg, icons_dir=tmp_path / "none")
    with pytest.raises(InputError, match="ICONS_DIR"):
        check_assets(bad)
