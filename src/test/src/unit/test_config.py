import pytest

from liver_statistics.config import load_config
from liver_statistics.errors import InputError


def test_new_settings_defaults(monkeypatch):
    for name in ("TESSERACT_TIMEOUT_SEC", "NUMBER_OCR_LANG", "DIGIT_MAX_DISTANCE", "NAME_EDIT_MIN_LENGTH", "LOG_LEVEL"):
        monkeypatch.delenv(name, raising=False)
    cfg = load_config()
    assert (cfg.tesseract_timeout_sec, cfg.number_ocr_lang, cfg.digit_max_distance, cfg.name_edit_min_length) == (
        30.0, "eng", 0.30, 3)
    assert cfg.log_level == "INFO"


def test_new_settings_override(monkeypatch):
    monkeypatch.setenv("TESSERACT_TIMEOUT_SEC", "5")
    monkeypatch.setenv("LOG_LEVEL", "debug")
    cfg = load_config()
    assert cfg.tesseract_timeout_sec == 5.0 and cfg.log_level == "DEBUG"


def test_invalid_log_level(monkeypatch):
    monkeypatch.setenv("LOG_LEVEL", "LOUD")
    with pytest.raises(InputError, match="LOG_LEVEL"):
        load_config()


def test_non_numeric_value(monkeypatch):
    monkeypatch.setenv("DIGIT_MAX_DISTANCE", "abc")
    with pytest.raises(InputError, match="DIGIT_MAX_DISTANCE"):
        load_config()


@pytest.mark.parametrize("name,value", [
    ("DIGIT_MAX_DISTANCE", "0"),
    ("TESSERACT_TIMEOUT_SEC", "-1"),
    ("NAME_EDIT_MIN_LENGTH", "0"),
    ("NAME_EDIT_MIN_LENGTH", "3.7"),
    ("ICON_MATCH_THRESHOLD", "1.5"),
    ("NAME_SIMILARITY_THRESHOLD", "0"),
    ("CONFIDENCE_THRESHOLD", "101"),
])
def test_out_of_range_rejected(monkeypatch, name, value):
    monkeypatch.setenv(name, value)
    with pytest.raises(InputError, match=name):
        load_config()


def test_dotenv_is_ignored_in_tests():
    # conftest の autouse フィクスチャが .env の読み込みを無効にしている
    from liver_statistics import config
    assert config.load_dotenv("x") is False


def _make_best(tmp_path, langs=("jpn", "eng")):
    for lang in langs:
        (tmp_path / f"{lang}.traineddata").write_bytes(b"x")
    return tmp_path


def test_tessdata_best_enabled_when_files_exist(monkeypatch, tmp_path):
    monkeypatch.setenv("TESSDATA_BEST_DIR", str(_make_best(tmp_path)))
    assert load_config().tessdata_best_dir == tmp_path


def test_tessdata_best_explicit_but_missing_is_error(monkeypatch, tmp_path):
    monkeypatch.setenv("TESSDATA_BEST_DIR", str(_make_best(tmp_path, ("jpn",))))
    with pytest.raises(InputError, match="eng.traineddata"):
        load_config()


def test_tessdata_best_default_location_missing_is_disabled(monkeypatch, tmp_path):
    from liver_statistics import config
    monkeypatch.delenv("TESSDATA_BEST_DIR", raising=False)
    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(config, "load_layout", lambda p: None)
    assert config.load_config().tessdata_best_dir is None


def test_disagree_cap_must_be_below_threshold(monkeypatch, tmp_path):
    monkeypatch.setenv("TESSDATA_BEST_DIR", str(_make_best(tmp_path)))
    monkeypatch.setenv("NAME_DISAGREE_CONFIDENCE_CAP", "60")
    with pytest.raises(InputError, match="NAME_DISAGREE_CONFIDENCE_CAP"):
        load_config()


def test_for_ocr_false_skips_tessdata_check(monkeypatch, tmp_path):
    monkeypatch.setenv("TESSDATA_BEST_DIR", str(_make_best(tmp_path, ("jpn",))))  # 不足していても
    assert load_config(for_ocr=False).tessdata_best_dir is None


def test_disagree_cap_validated_even_without_best_model(monkeypatch, tmp_path):
    from liver_statistics import config
    monkeypatch.delenv("TESSDATA_BEST_DIR", raising=False)
    monkeypatch.setenv("NAME_DISAGREE_CONFIDENCE_CAP", "60")
    monkeypatch.setattr(config, "_resolve_tessdata_best", lambda lang: None)
    with pytest.raises(InputError, match="NAME_DISAGREE_CONFIDENCE_CAP"):
        load_config()
