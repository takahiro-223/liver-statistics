import pytest

from liver_statistics.cli import main
from liver_statistics.db.connection import connect
from liver_statistics.errors import InputError


def test_must_exist_raises_without_creating(tmp_path):
    db = tmp_path / "deep" / "x.db"
    with pytest.raises(InputError, match="DB ファイルがありません"):
        connect(db, must_exist=True)
    assert not (tmp_path / "deep").exists()


def test_default_creates_db_and_folders(tmp_path):
    db = tmp_path / "deep" / "x.db"
    connect(db).close()
    assert db.is_file()


def test_must_exist_opens_existing_db(tmp_path):
    db = tmp_path / "x.db"
    connect(db).close()
    connect(db, must_exist=True).close()


@pytest.mark.parametrize("command", [["ranking", "--tribe", "T"], ["export", "--tribe", "T"]])
def test_read_commands_do_not_create_db(tmp_path, monkeypatch, capsys, command):
    db = tmp_path / "typo" / "x.db"
    monkeypatch.setenv("DB_PATH", str(db))
    assert main([*command, "--out", str(tmp_path / "o.csv")]) == 1
    assert "DB ファイルがありません" in capsys.readouterr().err
    assert not (tmp_path / "typo").exists() and not (tmp_path / "o.csv").exists()
