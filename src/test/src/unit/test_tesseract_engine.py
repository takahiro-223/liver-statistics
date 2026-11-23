import dataclasses
import logging

import numpy as np
import pytest

from liver_statistics.errors import OcrEngineUnavailableError
from liver_statistics.ocr import tesseract_engine
from liver_statistics.ocr.tesseract_engine import TesseractEngine

IMG = np.full((40, 200, 3), 200, np.uint8)


def fake_data(text, conf):
    return {"text": [text], "conf": [conf]}


@pytest.fixture
def calls(monkeypatch):
    """pytesseract.image_to_data をモックし、呼び出しの設定を記録する。"""
    recorded = []

    def fake(prepared, lang, config, output_type, timeout):
        recorded.append(config)
        return fake_data("--tessdata-dir" in config and "BEST" or "FAST", 80.0)

    monkeypatch.setattr(tesseract_engine.pytesseract, "image_to_data", fake)
    monkeypatch.setattr(tesseract_engine.pytesseract, "get_tesseract_version", lambda: "5")
    return recorded


def make_cfg(cfg, best_dir):
    return dataclasses.replace(cfg, tessdata_best_dir=best_dir)


def test_single_model_when_no_best_dir(cfg, calls):
    engine = TesseractEngine(make_cfg(cfg, None))
    assert engine.read_name(IMG).text == "FAST"
    assert len(calls) == 1 and "--tessdata-dir" not in calls[0]


def test_two_models_when_best_dir(cfg, calls, tmp_path):
    engine = TesseractEngine(make_cfg(cfg, tmp_path))
    calls.clear()  # 初期化時の試し読みは除く
    result = engine.read_name(IMG)
    assert len(calls) == 2
    assert sum("--tessdata-dir" in c for c in calls) == 1
    assert str(tmp_path) in next(c for c in calls if "--tessdata-dir" in c)
    # FAST と BEST で食い違う → 信頼度は上限以下
    assert result.confidence <= cfg.name_disagree_confidence_cap


def test_startup_check_runs_with_best_dir(cfg, calls, tmp_path):
    TesseractEngine(make_cfg(cfg, tmp_path))
    assert len(calls) == 1 and "--tessdata-dir" in calls[0]


def test_corrupt_best_model_is_engine_error(cfg, tmp_path):
    for lang in ("jpn", "eng"):
        (tmp_path / f"{lang}.traineddata").write_bytes(b"")
    with pytest.raises(OcrEngineUnavailableError, match="高精度モデル"):
        TesseractEngine(make_cfg(cfg, tmp_path))


def test_logs_model_mode(cfg, calls, tmp_path, caplog):
    with caplog.at_level(logging.INFO):
        TesseractEngine(make_cfg(cfg, None))
        TesseractEngine(make_cfg(cfg, tmp_path))
    text = caplog.text
    assert "1 モデル" in text and "2 モデル" in text
