"""SQLite 接続とスキーマ初期化。"""
from __future__ import annotations

import sqlite3
from importlib import resources
from pathlib import Path


def connect(db_path: Path) -> sqlite3.Connection:
    """外部キーを有効化して接続し、スキーマが無ければ作成する。"""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    schema = resources.files("liver_statistics.db").joinpath("schema.sql").read_text(encoding="utf-8")
    conn.executescript(schema)
    return conn
