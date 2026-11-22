from liver_statistics.ocr.engine import OcrResult
from liver_statistics.ocr.parser import parse_card, parse_number


def r(text, conf=90.0):
    return OcrResult(text=text, confidence=conf)


def test_parse_number():
    assert parse_number("1,408,565") == 1408565
    assert parse_number("633") == 633
    assert parse_number("") is None
    assert parse_number("1,40") is None
    assert parse_number("12a") is None


def test_ok_card(cfg):
    c = parse_card(r("alice"), r("2,813"), r("1,408,565"), cfg)
    assert (c.name, c.level, c.honor, c.needs_review) == ("alice", 2813, 1408565, False)


def test_parse_error_and_low_confidence(cfg):
    c = parse_card(r("x", 10), r("??"), r("5", 10), cfg)
    assert c.needs_review
    assert set(c.review_reasons) == {"parse_error_level", "low_confidence_honor", "low_confidence_name"}
    assert c.level is None and c.honor == 5


def test_empty_name_discarded(cfg):
    assert parse_card(r(""), r("1"), r("1"), cfg) is None


def test_japanese_spaces_removed(cfg):
    c = parse_card(r("Henry へ ん り ー"), r("1"), r("1"), cfg)
    assert c.name == "Henryへんりー"
    c2 = parse_card(r("Mr Smith"), r("1"), r("1"), cfg)
    assert c2.name == "Mr Smith"
