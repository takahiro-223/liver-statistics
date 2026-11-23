import csv
import shutil
import sqlite3
from datetime import date

import pytest

from conftest import SAMPLE
from liver_statistics.cli import main
from liver_statistics.db.connection import connect
from liver_statistics.pipeline import run_import

# サンプル画像と期待値（メンバー名を含むため git 管理外。docs/sample/ に手元で置く）が無ければスキップする
EXPECTED_CSV = SAMPLE.with_name("BASE_INF.expected.csv")  # ヘッダー: ユーザ名,レベル,名誉
pytestmark = pytest.mark.skipif(
    not (SAMPLE.exists() and EXPECTED_CSV.exists()), reason="サンプル画像または期待値 CSV が無い（git 管理外）"
)


def _load_expected() -> dict[str, tuple[int, int]]:
    if not EXPECTED_CSV.exists():
        return {}
    with EXPECTED_CSV.open(encoding="utf-8-sig", newline="") as f:
        return {r["ユーザ名"]: (int(r["レベル"]), int(r["名誉"])) for r in csv.DictReader(f)}


EXPECTED = _load_expected()
# 大文字小文字を区別しない検索・類似名のテストに使う、ASCII の名前
NAME = next((n for n in EXPECTED if n.isascii()), "")


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
        similar = f"{NAME}n"
        conn.execute("INSERT INTO members (tribe_id, name, name_key) VALUES (1, ?, ?)", (similar, similar.casefold()))
    conn.close()
    s = run_import(shots, "TEST", date(2026, 11, 22), "skip", cfg)
    assert s.inserted == 4 and NAME in s.needs_review
    reason = [r for r in rows(cfg) if r[0] == NAME][0][4]
    assert f"similar_to:{NAME}n" in reason


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

    assert main(["export", "--tribe", "TEST", "--member", NAME.upper(), "--from", "2026-11-01",
                 "--to", "2026-11-30", "--out", str(out)]) == 0
    lines = out.read_text(encoding="utf-8-sig").splitlines()
    assert len(lines) == 1 + 2 and all(NAME in l for l in lines[1:])

    assert main(["export", "--tribe", "NONE", "--out", str(out)]) == 1


def test_missing_icons_is_input_error_not_image_failure(cfg, shots, tmp_path):
    import dataclasses

    from liver_statistics.errors import InputError

    bad = dataclasses.replace(cfg, icons_dir=tmp_path / "none")
    with pytest.raises(InputError):
        run_import(shots, "TEST", date(2026, 11, 22), "skip", bad)
    assert not bad.db_path.exists()  # DB にも触れずに終了する
