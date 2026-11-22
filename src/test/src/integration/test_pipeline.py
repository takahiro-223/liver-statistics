import shutil
import sqlite3
from datetime import date

import pytest

from conftest import SAMPLE
from liver_statistics.cli import main
from liver_statistics.db.connection import connect
from liver_statistics.pipeline import run_import

pytestmark = pytest.mark.skipif(not SAMPLE.exists(), reason="サンプル画像が無い")

EXPECTED = {
    "ミケル": (1633, 398125),
    "Henryへんりー": (2881, 962013),
    "alice": (2813, 1408565),
    "りの": (2643, 1065504),
}


@pytest.fixture
def shots(tmp_path):
    d = tmp_path / "2026-11-22"
    d.mkdir()
    shutil.copy(SAMPLE, d / "BASE_INF.PNG")
    return d


def rows(cfg, sql="SELECT m.name, r.level, r.honor, r.needs_review, r.review_reason, r.record_date "
                  "FROM member_records r JOIN members m ON m.id = r.member_id"):
    conn = sqlite3.connect(cfg.db_path)
    try:
        return conn.execute(sql).fetchall()
    finally:
        conn.close()


def test_import_sample(cfg, shots):
    s = run_import(shots, "TEST", date(2026, 11, 22), "skip", cfg)
    assert (s.images_total, s.inserted, s.skipped, s.images_failed) == (1, 4, 0, [])
    got = {r[0]: (r[1], r[2]) for r in rows(cfg)}
    assert got == EXPECTED
    assert all(r[5] == "2026-11-22" for r in rows(cfg))


def test_reimport_skip_and_overwrite(cfg, shots):
    run_import(shots, "TEST", date(2026, 11, 22), "skip", cfg)
    s = run_import(shots, "TEST", date(2026, 11, 22), "skip", cfg)
    assert (s.inserted, s.skipped) == (0, 4)
    s = run_import(shots, "TEST", date(2026, 11, 22), "overwrite", cfg)
    assert (s.inserted, s.overwritten) == (0, 4)
    assert len(rows(cfg)) == 4
    assert rows(cfg, "SELECT count(*) FROM source_images")[0][0] == 1


def test_broken_image_reported_others_imported(cfg, shots):
    (shots / "broken.png").write_bytes(b"not an image")
    s = run_import(shots, "TEST", date(2026, 11, 22), "skip", cfg)
    assert s.images_failed == ["broken.png"] and s.inserted == 4


def test_tribes_are_separate(cfg, shots):
    run_import(shots, "A", date(2026, 11, 22), "skip", cfg)
    s = run_import(shots, "B", date(2026, 11, 22), "skip", cfg)
    assert s.inserted == 4
    assert rows(cfg, "SELECT count(*) FROM members")[0][0] == 8


def test_similar_name_flagged(cfg, shots):
    conn = connect(cfg.db_path)
    with conn:
        conn.execute("INSERT INTO tribes (name) VALUES ('TEST')")
        conn.execute("INSERT INTO members (tribe_id, name, name_key) VALUES (1, 'alicen', 'alicen')")
    conn.close()
    s = run_import(shots, "TEST", date(2026, 11, 22), "skip", cfg)
    assert s.inserted == 4 and "alice" in s.needs_review
    reason = [r for r in rows(cfg) if r[0] == "alice"][0][4]
    assert "similar_to:alicen" in reason


def test_rollback_on_failure(cfg, shots, monkeypatch):
    from liver_statistics.db import repository

    calls = {"n": 0}
    orig = repository.Repository.upsert_record

    def boom(self, rec, on_conflict):
        calls["n"] += 1
        if calls["n"] == 3:
            raise RuntimeError("boom")
        return orig(self, rec, on_conflict)

    monkeypatch.setattr(repository.Repository, "upsert_record", boom)
    with pytest.raises(RuntimeError):
        run_import(shots, "TEST", date(2026, 11, 22), "skip", cfg)
    assert rows(cfg) == []
    assert rows(cfg, "SELECT count(*) FROM members")[0][0] == 0


def test_export_cli(cfg, shots, tmp_path, monkeypatch):
    run_import(shots, "TEST", date(2026, 11, 22), "skip", cfg)
    run_import(shots, "TEST", date(2026, 11, 29), "skip", cfg)
    monkeypatch.setenv("DB_PATH", str(cfg.db_path))
    out = tmp_path / "o.csv"

    assert main(["export", "--tribe", "TEST", "--date", "2026-11-22", "--out", str(out)]) == 0
    assert len(out.read_text(encoding="utf-8-sig").splitlines()) == 1 + 4

    assert main(["export", "--tribe", "TEST", "--member", "ALICE", "--from", "2026-11-01",
                 "--to", "2026-11-30", "--out", str(out)]) == 0
    lines = out.read_text(encoding="utf-8-sig").splitlines()
    assert len(lines) == 1 + 2 and all("alice" in l for l in lines[1:])

    assert main(["export", "--tribe", "NONE", "--out", str(out)]) == 1
