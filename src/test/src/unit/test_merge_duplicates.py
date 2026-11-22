from datetime import date
from pathlib import Path

from liver_statistics.ocr.parser import ParsedCard
from liver_statistics.pipeline import _Extracted, merge_duplicates


def item(name, level, honor, conf, d=date(2026, 11, 22), img="a.png"):
    return _Extracted(d, Path(img), None, ParsedCard(name, level, honor, False, [], conf))


def test_merge_same_values_keeps_best():
    out = merge_duplicates([item("alice", 1, 2, 70, img="a.png"), item("Alice", 1, 2, 90, img="b.png")])
    assert len(out) == 1 and out[0].image_path.name == "b.png" and not out[0].card.needs_review


def test_conflict_flags_review():
    out = merge_duplicates([item("alice", 1, 2, 70), item("alice", 1, 3, 90)])
    assert out[0].card.needs_review and "conflict_between_images" in out[0].card.review_reasons
    assert out[0].card.honor == 3


def test_different_dates_not_merged():
    out = merge_duplicates([item("alice", 1, 2, 90), item("alice", 1, 2, 90, d=date(2026, 11, 29))])
    assert len(out) == 2
