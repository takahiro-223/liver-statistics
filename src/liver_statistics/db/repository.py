"""DB アクセス。SQL はすべてプレースホルダを使用する。"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal

OnConflict = Literal["skip", "overwrite"]
UpsertResult = Literal["inserted", "overwritten", "skipped"]


@dataclass(frozen=True)
class RecordInput:
    member_id: int
    record_date: date
    level: int | None
    honor: int | None
    needs_review: bool
    review_reason: str | None
    source_image_id: int


@dataclass(frozen=True)
class RecordRow:
    tribe: str
    record_date: str
    member: str
    level: int | None
    honor: int | None
    needs_review: bool


class Repository:
    """コミット・ロールバックは呼び出し側（pipeline）が管理する。"""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    # --- 部族 ---
    def get_or_create_tribe(self, name: str) -> tuple[int, bool]:
        row = self._conn.execute("SELECT id FROM tribes WHERE name = ?", (name,)).fetchone()
        if row:
            return row["id"], False
        cur = self._conn.execute("INSERT INTO tribes (name) VALUES (?)", (name,))
        return int(cur.lastrowid), True

    def find_tribe(self, name: str) -> int | None:
        row = self._conn.execute("SELECT id FROM tribes WHERE name = ?", (name,)).fetchone()
        return row["id"] if row else None

    # --- メンバー ---
    def find_member(self, tribe_id: int, name_key: str) -> int | None:
        row = self._conn.execute(
            "SELECT id FROM members WHERE tribe_id = ? AND name_key = ?", (tribe_id, name_key)
        ).fetchone()
        if row:
            return row["id"]
        row = self._conn.execute(
            "SELECT m.id FROM member_aliases a JOIN members m ON m.id = a.member_id "
            "WHERE m.tribe_id = ? AND a.alias_key = ?",
            (tribe_id, name_key),
        ).fetchone()
        return row["id"] if row else None

    def list_member_keys(self, tribe_id: int) -> list[tuple[str, str]]:
        rows = self._conn.execute(
            "SELECT name, name_key FROM members WHERE tribe_id = ?", (tribe_id,)
        ).fetchall()
        return [(r["name"], r["name_key"]) for r in rows]

    def create_member(self, tribe_id: int, name: str, name_key: str) -> int:
        cur = self._conn.execute(
            "INSERT INTO members (tribe_id, name, name_key) VALUES (?, ?, ?)",
            (tribe_id, name, name_key),
        )
        return int(cur.lastrowid)

    # --- 画像 ---
    def get_or_create_source_image(
        self, tribe_id: int, file_name: str, file_path: str, sha256: str, captured_at: datetime
    ) -> int:
        row = self._conn.execute(
            "SELECT id FROM source_images WHERE tribe_id = ? AND sha256 = ?", (tribe_id, sha256)
        ).fetchone()
        if row:
            return row["id"]
        cur = self._conn.execute(
            "INSERT INTO source_images (tribe_id, file_name, file_path, sha256, captured_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (tribe_id, file_name, file_path, sha256, captured_at.isoformat(timespec="seconds")),
        )
        return int(cur.lastrowid)

    # --- 記録 ---
    def upsert_record(self, rec: RecordInput, on_conflict: OnConflict) -> UpsertResult:
        params = (
            rec.member_id, rec.record_date.isoformat(), rec.level, rec.honor,
            int(rec.needs_review), rec.review_reason, rec.source_image_id,
        )
        exists = self._conn.execute(
            "SELECT 1 FROM member_records WHERE member_id = ? AND record_date = ?",
            (rec.member_id, rec.record_date.isoformat()),
        ).fetchone()
        if exists is None:
            self._conn.execute(
                "INSERT INTO member_records (member_id, record_date, level, honor, needs_review, "
                "review_reason, source_image_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
                params,
            )
            return "inserted"
        if on_conflict == "skip":
            return "skipped"
        self._conn.execute(
            "UPDATE member_records SET level = ?, honor = ?, needs_review = ?, review_reason = ?, "
            "source_image_id = ?, updated_at = datetime('now', 'localtime') "
            "WHERE member_id = ? AND record_date = ?",
            (rec.level, rec.honor, int(rec.needs_review), rec.review_reason, rec.source_image_id,
             rec.member_id, rec.record_date.isoformat()),
        )
        return "overwritten"

    def query_records(
        self, tribe: str, on_date: date | None = None, date_from: date | None = None,
        date_to: date | None = None, member: str | None = None,
        member_key: str | None = None,
    ) -> list[RecordRow]:
        sql = (
            "SELECT t.name AS tribe, r.record_date, m.name AS member, r.level, r.honor, r.needs_review "
            "FROM member_records r JOIN members m ON m.id = r.member_id "
            "JOIN tribes t ON t.id = m.tribe_id WHERE t.name = ?"
        )
        params: list = [tribe]
        if on_date:
            sql += " AND r.record_date = ?"
            params.append(on_date.isoformat())
        if date_from:
            sql += " AND r.record_date >= ?"
            params.append(date_from.isoformat())
        if date_to:
            sql += " AND r.record_date <= ?"
            params.append(date_to.isoformat())
        if member_key:
            sql += " AND (m.name_key = ? OR m.id IN (SELECT member_id FROM member_aliases WHERE alias_key = ?))"
            params.extend([member_key, member_key])
        sql += " ORDER BY r.record_date, m.name"
        return [
            RecordRow(r["tribe"], r["record_date"], r["member"], r["level"], r["honor"], bool(r["needs_review"]))
            for r in self._conn.execute(sql, params).fetchall()
        ]
