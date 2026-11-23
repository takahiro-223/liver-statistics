from liver_statistics.members.matcher import normalize_name as via_matcher
from liver_statistics.normalize import normalize_name


def test_normalize_name():
    assert normalize_name(" Ａｌｉｃｅ ") == "alice"
    assert normalize_name("Henry へんりー") == "henryへんりー"


def test_matcher_still_exposes_normalize_name():
    assert via_matcher is normalize_name
