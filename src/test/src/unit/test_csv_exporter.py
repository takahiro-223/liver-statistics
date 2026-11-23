import pytest

from liver_statistics.db.repository import RecordRow
from liver_statistics.export.csv_exporter import export_csv


def test_export(tmp_path):
    out = tmp_path / "o.csv"
    n = export_csv([RecordRow("T", "2026-11-22", "alice", 1, None, True)], out)
    assert n == 1
    raw = out.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")
    lines = raw.decode("utf-8-sig").splitlines()
    assert lines[0] == "部族名,記録日,ユーザ名,レベル,名誉,要確認"
    assert lines[1] == "T,2026-11-22,alice,1,,1"


def test_export_neutralizes_formula_like_names(tmp_path):
    out = tmp_path / "o.csv"
    export_csv([
        RecordRow("=T", "2026-11-22", "=1+1", -5, 0, False),
        RecordRow("T", "2026-11-22", "@sum", 1, 2, False),
        RecordRow("T", "2026-11-22", "0123", 1, 2, False),
    ], out)
    lines = out.read_bytes().decode("utf-8-sig").splitlines()
    assert lines[1] == "'=T,2026-11-22,'=1+1,-5,0,0"  # 数値（負の数を含む）は変えない
    assert lines[2].split(",")[2] == "'@sum"
    assert lines[3].split(",")[2] == "0123"


def test_export_failure_keeps_existing_file(tmp_path, monkeypatch):
    from liver_statistics.export import csv_exporter

    out = tmp_path / "o.csv"
    out.write_text("old", encoding="utf-8")

    def boom(text):
        raise RuntimeError("boom")

    monkeypatch.setattr(csv_exporter, "csv_safe", boom)
    with pytest.raises(RuntimeError):
        export_csv([RecordRow("T", "2026-11-22", "alice", 1, 1, False)], out)
    assert out.read_text(encoding="utf-8") == "old"
    assert [p.name for p in tmp_path.iterdir()] == ["o.csv"]
