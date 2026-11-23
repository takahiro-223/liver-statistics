import numpy as np
import pytest

from liver_statistics.errors import InputError
from liver_statistics.evaluation import accuracy
from liver_statistics.evaluation.accuracy import AccuracyReport, evaluate
from liver_statistics.evaluation.digit_templates import write_templates
from liver_statistics.ocr.parser import ParsedCard


def card(name, level, honor):
    return ParsedCard(name, level, honor, False, [], 90.0)


def test_report_rate():
    assert AccuracyReport(correct=7, total=10).achieved
    assert not AccuracyReport(correct=6, total=10).achieved
    assert AccuracyReport().rate == 0.0


def test_evaluate_counts_items(cfg, tmp_path, monkeypatch):
    (tmp_path / "a.png").write_bytes(b"x")
    monkeypatch.setattr(accuracy, "read_cards", lambda *a: [card("alice", 10, 200), card("りの", 5, 999)])
    truth = {
        "alice": {"ユーザ名": "alice", "レベル": "10", "名誉": "200"},
        "りの": {"ユーザ名": "りの", "レベル": "5", "名誉": "1,000"},
        "ぽこた": {"ユーザ名": "ぽこた", "レベル": "1", "名誉": "1"},
    }
    report = evaluate(tmp_path, truth, engine=None, cfg=cfg)
    assert (report.correct, report.total) == (5, 9)
    assert len(report.errors) == 2


def test_write_templates_requires_all_digits(tmp_path):
    g = np.zeros((36, 24), np.float32)
    with pytest.raises(InputError):
        write_templates({str(d): ([g] if d < 9 else []) for d in range(10)}, tmp_path)
    counts = write_templates({str(d): [g, g] for d in range(10)}, tmp_path)
    assert counts["3"] == 2 and (tmp_path / "3_01.png").exists()


def test_load_truth_errors(tmp_path):
    from liver_statistics.evaluation.accuracy import load_truth
    with pytest.raises(InputError, match="読めません"):
        load_truth(tmp_path / "none.csv")
    bad = tmp_path / "bad.csv"
    bad.write_text("名前,値\nA,1\n", encoding="utf-8")
    with pytest.raises(InputError, match="列"):
        load_truth(bad)
    dup = tmp_path / "dup.csv"
    dup.write_text("ユーザ名,レベル,名誉\nA,1,1\nａ,2,2\n", encoding="utf-8")
    with pytest.raises(InputError, match="重複"):
        load_truth(dup)


def test_write_templates_keeps_existing_on_encode_failure(tmp_path, monkeypatch):
    import cv2
    g = np.zeros((36, 24), np.float32)
    write_templates({str(d): [g] for d in range(10)}, tmp_path)
    monkeypatch.setattr(cv2, "imencode", lambda *a, **k: (False, None))
    with pytest.raises(InputError):
        write_templates({str(d): [g, g] for d in range(10)}, tmp_path)
    assert len(list(tmp_path.glob("[0-9]_*.png"))) == 10
