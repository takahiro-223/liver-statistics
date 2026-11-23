"""SQLite 接続とスキーマ初期化。"""
from __future__ import annotations

import sqlite3
from importlib import resources
from pathlib import Path

from ..errors import InputError


def connect(db_path: Path, must_exist: bool = False) -> sqlite3.Connection:
    """外部キーを有効化して接続し、スキーマが無ければ作成する。

    must_exist=True（export・ranking など読み取りのコマンド）では、DB ファイルが無ければ InputError にし、
    フォルダも空の DB も作らない（DB_PATH の指定ミスに気付けるようにするため）。
    """
    if must_exist:
        if not db_path.is_file():
            raise InputError(f"DB ファイルがありません: {db_path}（DB_PATH を確認してください。import で作成されます）")
    else:
        db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    schema = resources.files("liver_statistics.db").joinpath("schema.sql").read_text(encoding="utf-8")
    conn.executescript(schema)
    return conn
