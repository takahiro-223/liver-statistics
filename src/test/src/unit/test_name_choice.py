from liver_statistics.ocr.engine import OcrResult
from liver_statistics.ocr.name_choice import choose_name


def r(text, conf):
    return OcrResult(text=text, confidence=conf)


def test_agree_keeps_higher_confidence():
    out = choose_name(r("Alice", 70), r("ALICE", 90), 55)
    assert (out.text, out.confidence) == ("ALICE", 90)


def test_agree_ignores_japanese_spaces_and_width():
    out = choose_name(r("へ ん り ー", 80), r("へんりー", 70), 55)
    assert out.confidence == 80


def test_disagree_picks_higher_and_caps_confidence():
    out = choose_name(r("PA", 90), r("やん", 75), 55)
    assert (out.text, out.confidence) == ("PA", 55)


def test_disagree_low_confidence_stays_low():
    out = choose_name(r("ぼんた", 40), r("ぽんた", 30), 55)
    assert (out.text, out.confidence) == ("ぼんた", 40)


def test_tie_prefers_primary():
    assert choose_name(r("a", 60), r("b", 60), 55).text == "a"
