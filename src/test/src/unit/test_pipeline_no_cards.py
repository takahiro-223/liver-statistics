import cv2
import numpy as np
import pytest

from liver_statistics.cli import main
from liver_statistics.pipeline import run_import


class NeverCalledEngine:
    def read_name(self, image):
        raise AssertionError("カードが無いので呼ばれない")

    read_number = read_name


@pytest.fixture
def blank_dir(tmp_path):
    d = tmp_path / "2026-11-23"
    d.mkdir()
    cv2.imwrite(str(d / "blank.png"), np.full((600, 300, 3), 200, np.uint8))
    return d


def test_image_without_cards_is_reported(cfg, blank_dir):
    s = run_import(blank_dir, "T", None, "skip", cfg, engine=NeverCalledEngine())
    assert s.images_no_cards == ["blank.png"] and s.images_failed == []
    assert s.inserted == 0
    assert not cfg.db_path.exists()  # 登録するカードが無ければ DB に触れない（空の部族も作らない）


def test_cli_warns_when_no_cards(cfg, blank_dir, monkeypatch, capsys):
    class Dummy(NeverCalledEngine):
        def __init__(self, cfg):
            pass

    monkeypatch.setattr("liver_statistics.ocr.tesseract_engine.TesseractEngine", Dummy)
    monkeypatch.setenv("DB_PATH", str(cfg.db_path))
    assert main(["import", "--dir", str(blank_dir), "--tribe", "T"]) == 0
    out = capsys.readouterr().out
    assert "成功 0 / 失敗 0 / カード未検出 1" in out
    assert "カード未検出: blank.png" in out
    assert "どの画像からもメンバーを読み取れませんでした" in out
