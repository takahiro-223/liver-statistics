import pytest

from liver_statistics.cli import build_parser, main


def test_invalid_date_rejected():
    with pytest.raises(SystemExit):
        build_parser().parse_args(["import", "--dir", ".", "--tribe", "T", "--date", "2026/11/22"])


def test_date_and_range_conflict(capsys, tmp_path):
    code = main(["export", "--tribe", "T", "--date", "2026-11-22", "--from", "2026-11-01",
                 "--out", str(tmp_path / "o.csv")])
    assert code == 1
    assert "同時に指定できません" in capsys.readouterr().err
