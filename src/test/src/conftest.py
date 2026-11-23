from pathlib import Path

import pytest

from liver_statistics.config import load_config

SAMPLE = Path(__file__).resolve().parents[3] / "docs" / "sample" / "BASE_INF.PNG"


@pytest.fixture
def cfg(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    return load_config()


@pytest.fixture(autouse=True)
def _ignore_dotenv(monkeypatch):
    """開発者の .env にテスト結果が左右されないようにする。"""
    monkeypatch.setattr("liver_statistics.config.load_dotenv", lambda *a, **k: False)
