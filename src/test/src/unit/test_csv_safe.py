import pytest

from liver_statistics.export.csv_safe import atomic_csv, csv_safe


@pytest.mark.parametrize("text", ["=1+1", "+81", "-abc", "@sum", "\tx", "\rx", "=HYPERLINK(\"http://x\")"])
def test_formula_like_text_is_prefixed(text):
    assert csv_safe(text) == "'" + text


@pytest.mark.parametrize("text", ["alice", "Henryへんりー", "3か7", "0123", "3-7", "a=b", "ももか", "", " alice", "'="])
def test_normal_text_is_unchanged(text):
    assert csv_safe(text) == text


def test_atomic_csv_writes_bom_and_replaces(tmp_path):
    out = tmp_path / "o.csv"
    out.write_text("old", encoding="utf-8")
    with atomic_csv(out) as f:
        f.write("新しい\n")
    assert out.read_bytes() == b"\xef\xbb\xbf" + "新しい\n".encode()
    assert [p.name for p in tmp_path.iterdir()] == ["o.csv"]  # 一時ファイルが残らない


def test_atomic_csv_failure_keeps_existing_file(tmp_path):
    out = tmp_path / "o.csv"
    out.write_text("old", encoding="utf-8")
    with pytest.raises(RuntimeError):
        with atomic_csv(out) as f:
            f.write("partial")
            raise RuntimeError("boom")
    assert out.read_text(encoding="utf-8") == "old"
    assert [p.name for p in tmp_path.iterdir()] == ["o.csv"]


def test_atomic_csv_failure_without_existing_file(tmp_path):
    out = tmp_path / "o.csv"
    with pytest.raises(RuntimeError):
        with atomic_csv(out):
            raise RuntimeError("boom")
    assert list(tmp_path.iterdir()) == []
