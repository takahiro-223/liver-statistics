import csv
import sqlite3
from datetime import date

import pytest

from liver_statistics.cli import main
from liver_statistics.errors import InputError
from liver_statistics.ranking.service import run_ranking

D1, D2, D3 = date(2026, 11, 16), date(2026, 11, 23), date(2026, 11, 30)


def read(path):
    return list(csv.reader(path.read_text(encoding="utf-8-sig").splitlines()))


@pytest.fixture
def two_weeks(seed):
    seed("T", [
        ("alice", D1, 100, 1000), ("henry", D1, 90, 900), ("left", D1, 50, 500),
        ("alice", D2, 120, 1500), ("henry", D2, 95, 1000), ("newbie", D2, 10, 50),
    ])


def test_default_is_latest_date_with_previous(cfg, two_weeks, tmp_path):
    out = tmp_path / "r.csv"
    s = run_ranking("T", None, out, cfg)
    assert (s.current_date, s.previous_date, s.members) == (D2, D1, 3)
    assert s.no_previous == ["newbie"] and s.needs_review == []
    rows = read(out)
    assert rows[0] == ["2026/11/16〜2026/11/23 各種ランキング"]
    # レベル上昇値: alice +20, henry +5, newbie は前回なし
    assert [r[6:9] for r in rows[2:]] == [["1", "alice", "20"], ["2", "henry", "5"], ["", "newbie", "-"]]
    assert "left" not in out.read_text(encoding="utf-8-sig")  # 今回にいないメンバーは載せない


def test_specified_past_date(cfg, two_weeks, tmp_path):
    out = tmp_path / "r.csv"
    s = run_ranking("T", D1, out, cfg)
    assert (s.current_date, s.previous_date) == (D1, None)  # 初回: 前回なし
    assert read(out)[0] == ["（前回なし）〜2026/11/16 各種ランキング"]


@pytest.mark.parametrize("tribe,on,message", [
    ("NONE", None, "部族が登録されていません"),
    ("T", date(2026, 12, 1), "指定した記録日のデータがありません"),
])
def test_input_errors(cfg, two_weeks, tmp_path, tribe, on, message):
    with pytest.raises(InputError, match=message):
        run_ranking(tribe, on, tmp_path / "r.csv", cfg)
    assert not (tmp_path / "r.csv").exists()


def test_tribe_without_records(cfg, tmp_path):
    from liver_statistics.db.connection import connect
    from liver_statistics.db.repository import Repository
    conn = connect(cfg.db_path)
    with conn:
        Repository(conn).get_or_create_tribe("EMPTY")
    conn.close()
    with pytest.raises(InputError, match="部族に記録がありません"):
        run_ranking("EMPTY", None, tmp_path / "r.csv", cfg)


def test_db_is_not_modified(cfg, two_weeks, tmp_path):
    def snapshot():
        conn = sqlite3.connect(cfg.db_path)
        try:
            return [conn.execute(f"SELECT * FROM {t} ORDER BY 1").fetchall()
                    for t in ("tribes", "members", "member_records", "source_images", "member_aliases")]
        finally:
            conn.close()
    before = snapshot()
    run_ranking("T", None, tmp_path / "r.csv", cfg)
    assert snapshot() == before


def test_needs_review_in_summary(cfg, seed, tmp_path):
    seed("T", [("alice", D1, 100, 1000), ("alice", D2, 120, 1500, True), ("henry", D2, 1, 1)])
    s = run_ranking("T", None, tmp_path / "r.csv", cfg)
    assert s.needs_review == ["alice"] and s.no_previous == ["henry"]


# --- CLI ---
def cli(cfg, monkeypatch, *args):
    monkeypatch.setenv("DB_PATH", str(cfg.db_path))
    return main(["ranking", *args])


def test_cli_outputs_summary(cfg, two_weeks, tmp_path, monkeypatch, capsys):
    out = tmp_path / "r.csv"
    assert cli(cfg, monkeypatch, "--tribe", "T", "--out", str(out)) == 0
    text = capsys.readouterr().out
    assert "今回: 2026-11-23 / 前回: 2026-11-16" in text
    assert "ランキング: 3人" in text and "前回なし: 1人（newbie）" in text
    assert "警告" not in text and out.exists()


def test_cli_warns_but_exits_zero(cfg, seed, tmp_path, monkeypatch, capsys):
    seed("T", [("alice", D1, 100, 1000), ("alice", D2, 120, 1500, True)])
    assert cli(cfg, monkeypatch, "--tribe", "T", "--out", str(tmp_path / "r.csv")) == 0
    assert "警告: 要確認の記録が残っています: 1件（alice）" in capsys.readouterr().out


def test_cli_first_week(cfg, seed, tmp_path, monkeypatch, capsys):
    seed("T", [("alice", D1, 100, 1000)])
    assert cli(cfg, monkeypatch, "--tribe", "T", "--out", str(tmp_path / "r.csv")) == 0
    assert "前回: なし（上昇値は全員「-」）" in capsys.readouterr().out


@pytest.mark.parametrize("args,message", [
    (["--tribe", "NONE"], "部族が登録されていません"),
    (["--tribe", "T", "--date", "2030-01-01"], "指定した記録日のデータがありません"),
])
def test_cli_input_errors_exit_1(cfg, two_weeks, tmp_path, monkeypatch, capsys, args, message):
    assert cli(cfg, monkeypatch, *args, "--out", str(tmp_path / "r.csv")) == 1
    assert message in capsys.readouterr().err


def test_cli_missing_output_folder(cfg, two_weeks, tmp_path, monkeypatch, capsys):
    assert cli(cfg, monkeypatch, "--tribe", "T", "--out", str(tmp_path / "no" / "r.csv")) == 1
    assert "出力先フォルダが存在しません" in capsys.readouterr().err


def test_cli_rejects_bad_date_format(tmp_path):
    from liver_statistics.cli import build_parser
    with pytest.raises(SystemExit):
        build_parser().parse_args(["ranking", "--tribe", "T", "--date", "2026/11/23", "--out", str(tmp_path / "r.csv")])
