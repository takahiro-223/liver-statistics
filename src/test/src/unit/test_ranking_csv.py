import csv
from datetime import date

from liver_statistics.ranking.calc import RankEntry, RankingTable
from liver_statistics.ranking.csv_writer import HEADER, write_ranking_csv


def entries(*items):
    return [RankEntry(*i) for i in items]


def table(previous=date(2026, 11, 16)):
    return RankingTable(
        current_date=date(2026, 11, 23), previous_date=previous,
        level=entries((1, "henry", 2905), (2, "alice", 2832), (3, "newbie", 120)),
        honor=entries((1, "alice", 1446442), (2, "henry", 983362), (3, "newbie", 5000)),
        level_gain=entries((1, "henry", 30), (2, "alice", 20), (None, "newbie", None)),
        honor_gain=entries((1, "alice", 38000), (2, "henry", 25000), (None, "newbie", None)),
        no_previous=["newbie"], needs_review=[],
    )


def read(path):
    raw = path.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")  # UTF-8 BOM
    return list(csv.reader(raw.decode("utf-8-sig").splitlines()))


def test_layout(tmp_path):
    out = tmp_path / "r.csv"
    assert write_ranking_csv(table(), out) == 3
    rows = read(out)
    assert rows[0] == ["2026/11/16〜2026/11/23 各種ランキング"]
    assert rows[1] == HEADER and len(HEADER) == 12
    assert rows[2] == ["1", "henry", "2905", "1", "alice", "1446442", "1", "henry", "30", "1", "alice", "38000"]
    assert rows[3][6:9] == ["2", "alice", "20"]


def test_none_rank_blank_and_none_value_dash(tmp_path):
    out = tmp_path / "r.csv"
    write_ranking_csv(table(), out)
    last = read(out)[4]
    assert last == ["3", "newbie", "120", "3", "newbie", "5000", "", "newbie", "-", "", "newbie", "-"]


def test_first_week_title(tmp_path):
    out = tmp_path / "r.csv"
    write_ranking_csv(table(previous=None), out)
    assert read(out)[0] == ["（前回なし）〜2026/11/23 各種ランキング"]


def test_shorter_columns_are_padded(tmp_path):
    t = table()
    t = RankingTable(**{**t.__dict__, "honor": t.honor[:2]})
    out = tmp_path / "r.csv"
    write_ranking_csv(t, out)
    assert read(out)[4][3:6] == ["", "", ""]


def test_overwrites_existing_file(tmp_path):
    out = tmp_path / "r.csv"
    out.write_text("old", encoding="utf-8")
    write_ranking_csv(table(), out)
    assert "old" not in out.read_text(encoding="utf-8-sig")
