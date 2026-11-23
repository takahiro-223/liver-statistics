from datetime import date

from liver_statistics.db.connection import connect
from liver_statistics.db.repository import Repository

D1, D2, D3 = date(2026, 11, 9), date(2026, 11, 16), date(2026, 11, 23)


def repo_for(cfg):
    conn = connect(cfg.db_path)
    return conn, Repository(conn)


def test_dates(cfg, seed):
    seed("T", [("alice", D1, 1, 1), ("alice", D3, 2, 2)])  # D2 は抜けている
    conn, repo = repo_for(cfg)
    try:
        tid = repo.find_tribe("T")
        assert repo.latest_record_date(tid) == D3
        assert repo.previous_record_date(tid, D3) == D1  # 間が空いても直前の記録日
        assert repo.previous_record_date(tid, D1) is None
        assert repo.has_records_on(tid, D3) and not repo.has_records_on(tid, D2)
    finally:
        conn.close()


def test_latest_none_when_no_records(cfg):
    conn, repo = repo_for(cfg)
    try:
        tid, _ = repo.get_or_create_tribe("T")
        assert repo.latest_record_date(tid) is None
    finally:
        conn.close()


def test_snapshots_are_scoped_to_tribe_and_date(cfg, seed):
    seed("T", [("alice", D1, 1, 10), ("alice", D3, 2, 20, True), ("henry", D3, 3, 30)])
    seed("OTHER", [("zed", D3, 9, 90)])
    conn, repo = repo_for(cfg)
    try:
        snaps = repo.list_snapshots(repo.find_tribe("T"), D3)
        assert [(s.name, s.level, s.honor, s.needs_review) for s in snaps] == [
            ("alice", 2, 20, True), ("henry", 3, 30, False)]
        assert repo.latest_record_date(repo.find_tribe("OTHER")) == D3
    finally:
        conn.close()
