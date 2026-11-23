from liver_statistics.members.matcher import normalize_name, resolve_member


class FakeRepo:
    def __init__(self, members):
        self.members = members  # {key: (id, name)}

    def find_member(self, tribe_id, key):
        return self.members[key][0] if key in self.members else None

    def list_member_keys(self, tribe_id):
        return [(n, k) for k, (_, n) in self.members.items()]


def test_normalize():
    assert normalize_name(" Ａｌｉｃｅ ") == "alice"
    assert normalize_name("Henry へんりー") == "henryへんりー"


def test_existing():
    repo = FakeRepo({"alice": (1, "alice")})
    assert resolve_member(repo, 1, "ALICE", 0.8, 3).member_id == 1


def test_similar_new():
    repo = FakeRepo({"zedknight": (1, "ZedKnight")})
    m = resolve_member(repo, 1, "ZedKnightZ", 0.8, 3)
    assert m.member_id is None and m.similar_to == "ZedKnight"


def test_dissimilar_new():
    repo = FakeRepo({"alice": (1, "alice")})
    m = resolve_member(repo, 1, "りの", 0.8, 3)
    assert m.member_id is None and m.similar_to is None


def test_short_name_one_char_diff_is_similar():
    repo = FakeRepo({"ぽこた": (1, "ぽこた")})
    m = resolve_member(repo, 1, "ぼこた", 0.8, 3)
    assert m.member_id is None and m.similar_to == "ぽこた"


def test_short_name_below_min_length_not_similar():
    repo = FakeRepo({"ab": (1, "ab")})
    assert resolve_member(repo, 1, "ac", 0.8, 3).similar_to is None


def test_within_one_edit():
    from liver_statistics.members.matcher import _within_one_edit
    assert _within_one_edit("abc", "abd") and _within_one_edit("abc", "ab") and _within_one_edit("abc", "xabc")
    assert not _within_one_edit("abc", "axd") and not _within_one_edit("abc", "a")


def test_similar_name_shown_is_highest_ratio():
    repo = FakeRepo({"ぽこた": (1, "ぽこた"), "ぼこたろう": (2, "ぼこたろう")})
    # 「ぼこた」は ぽこた（編集距離1）にも ぼこたろう（ratio 約0.75）にも近い
    m = resolve_member(repo, 1, "ぼこた", 0.7, 3)
    assert m.similar_to == "ぼこたろう"
