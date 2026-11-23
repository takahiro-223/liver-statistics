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


@pytest.fixture
def seed(cfg):
    """DB にメンバーの記録を直接登録するヘルパー（ランキングのテスト用）。

    seed("部族名", [(名前, 記録日, レベル, 名誉, 要確認=False), ...])
    """
    from datetime import datetime

    from liver_statistics.db.connection import connect
    from liver_statistics.db.repository import RecordInput, Repository
    from liver_statistics.normalize import normalize_name

    def _seed(tribe, rows):
        conn = connect(cfg.db_path)
        try:
            with conn:
                repo = Repository(conn)
                tribe_id, _ = repo.get_or_create_tribe(tribe)
                members, images = {}, {}
                for row in rows:
                    name, on, level, honor = row[:4]
                    needs_review = row[4] if len(row) > 4 else False
                    key = normalize_name(name)
                    if key not in members:
                        members[key] = repo.find_member(tribe_id, key) or repo.create_member(tribe_id, name, key)
                    if on not in images:
                        images[on] = repo.get_or_create_source_image(
                            tribe_id, f"{on}.png", f"/dummy/{on}.png", f"sha-{tribe}-{on}",
                            datetime.combine(on, datetime.min.time()),
                        )
                    repo.upsert_record(
                        RecordInput(members[key], on, level, honor, needs_review,
                                    "low_confidence_name" if needs_review else None, images[on]),
                        "overwrite",
                    )
        finally:
            conn.close()

    return _seed
