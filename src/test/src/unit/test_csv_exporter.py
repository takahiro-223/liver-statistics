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
