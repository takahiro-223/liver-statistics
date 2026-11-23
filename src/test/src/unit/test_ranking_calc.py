from datetime import date

from liver_statistics.db.repository import MemberSnapshot
from liver_statistics.normalize import normalize_name
from liver_statistics.ranking.calc import build_ranking

CUR, PREV = date(2026, 11, 23), date(2026, 11, 16)


def snap(mid, name, level, honor, review=False):
    return MemberSnapshot(mid, name, normalize_name(name), level, honor, review)


def names(entries):
    return [(e.rank, e.name, e.value) for e in entries]


def test_levels_and_honors_sorted_desc_with_competition_ranks():
    cur = [snap(1, "alice", 100, 500), snap(2, "henry", 100, 700), snap(3, "momoka", 90, 700), snap(4, "zed", 80, 100)]
    t = build_ranking(cur, [], CUR, None)
    assert names(t.level) == [(1, "alice", 100), (1, "henry", 100), (3, "momoka", 90), (4, "zed", 80)]
    assert names(t.honor) == [(1, "henry", 700), (1, "momoka", 700), (3, "alice", 500), (4, "zed", 100)]


def test_ties_are_ordered_by_name_key():
    cur = [snap(1, "Zed", 10, 1), snap(2, "alice", 10, 1), snap(3, "Bob", 10, 1)]
    t = build_ranking(cur, [], CUR, None)
    assert [e.name for e in t.level] == ["alice", "Bob", "Zed"]  # 正規化後（小文字）の昇順
    assert [e.rank for e in t.level] == [1, 1, 1]


def test_gains_zero_and_negative_ordering():
    cur = [snap(1, "alice", 120, 1000), snap(2, "henry", 100, 900), snap(3, "momoka", 95, 800), snap(4, "zed", 80, 700)]
    prev = [snap(1, "alice", 100, 900), snap(2, "henry", 100, 900), snap(3, "momoka", 100, 900), snap(4, "zed", 70, 600)]
    t = build_ranking(cur, prev, CUR, PREV)
    assert names(t.level_gain) == [(1, "alice", 20), (2, "zed", 10), (3, "henry", 0), (4, "momoka", -5)]
    assert names(t.honor_gain) == [(1, "alice", 100), (1, "zed", 100), (3, "henry", 0), (4, "momoka", -100)]


def test_member_without_previous_is_last_with_no_rank():
    cur = [snap(1, "alice", 120, 1000), snap(2, "newbie", 10, 50)]
    prev = [snap(1, "alice", 100, 900)]
    t = build_ranking(cur, prev, CUR, PREV)
    assert names(t.level_gain) == [(1, "alice", 20), (None, "newbie", None)]
    assert names(t.honor_gain) == [(1, "alice", 100), (None, "newbie", None)]
    assert t.no_previous == ["newbie"]
    # 最高レベル・名誉は前回なしでも順位が付く
    assert names(t.level) == [(1, "alice", 120), (2, "newbie", 10)]


def test_none_values_go_last_without_rank():
    cur = [snap(1, "alice", None, 1000), snap(2, "henry", 50, None), snap(3, "momoka", 60, 900)]
    prev = [snap(1, "alice", 10, 900), snap(2, "henry", 40, 800), snap(3, "momoka", 50, 800)]
    t = build_ranking(cur, prev, CUR, PREV)
    assert names(t.level) == [(1, "momoka", 60), (2, "henry", 50), (None, "alice", None)]
    assert names(t.honor) == [(1, "alice", 1000), (2, "momoka", 900), (None, "henry", None)]
    assert names(t.level_gain) == [(1, "henry", 10), (1, "momoka", 10), (None, "alice", None)]
    assert names(t.honor_gain) == [(1, "alice", 100), (1, "momoka", 100), (None, "henry", None)]


def test_members_only_in_previous_are_not_listed():
    cur = [snap(1, "alice", 120, 1000)]
    prev = [snap(1, "alice", 100, 900), snap(2, "left", 50, 50)]
    t = build_ranking(cur, prev, CUR, PREV)
    assert [e.name for e in t.level] == ["alice"]
    assert t.no_previous == []


def test_first_week_has_no_previous_date():
    cur = [snap(1, "alice", 120, 1000), snap(2, "henry", 100, 900)]
    t = build_ranking(cur, [], CUR, None)
    assert t.previous_date is None
    assert all(e.value is None and e.rank is None for e in t.level_gain + t.honor_gain)
    assert t.no_previous == []  # 初回は「前回なし」の列挙はしない（previous_date is None で分かる）


def test_needs_review_from_current_or_previous():
    cur = [snap(1, "alice", 120, 1000, review=True), snap(2, "henry", 100, 900), snap(3, "momoka", 90, 800)]
    prev = [snap(1, "alice", 100, 900), snap(2, "henry", 90, 800, review=True), snap(3, "momoka", 80, 700)]
    t = build_ranking(cur, prev, CUR, PREV)
    assert sorted(t.needs_review) == ["alice", "henry"]


def test_previous_matched_by_member_id_not_by_name():
    cur = [snap(10, "alice", 120, 1000)]
    prev = [snap(99, "alice", 100, 900)]  # 同じ名前でも別の member_id は別人
    t = build_ranking(cur, prev, CUR, PREV)
    assert names(t.level_gain) == [(None, "alice", None)]
    assert t.no_previous == ["alice"]
