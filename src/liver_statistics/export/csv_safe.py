"""CSV を表計算ソフトで開いたときの安全対策（数式の誤実行の防止）と、書き込みの安全化。"""
from __future__ import annotations

import os
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import TextIO

# 先頭にあると、表計算ソフトが数式として解釈する文字（OWASP の CSV インジェクション対策）
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def csv_safe(text: str) -> str:
    """ユーザ名・部族名など、他者が決める文字列用。数式と解釈されうる先頭の文字がある場合、先頭に `'` を付ける。

    数値や、値なしを示す「-」には使わない。
    """
    return "'" + text if text.startswith(_FORMULA_PREFIXES) else text


@contextmanager
def atomic_csv(out_path: Path) -> Iterator[TextIO]:
    """UTF-8 BOM 付きで書き込むためのファイルを開く。

    同じフォルダの一時ファイルに書き、成功したときだけ out_path と置き換える。
    書き込みの途中で失敗しても、既存のファイルは壊れず、一時ファイルも残らない。
    """
    fd, tmp = tempfile.mkstemp(dir=out_path.parent, prefix=f".{out_path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8-sig", newline="") as f:
            yield f
        os.replace(tmp, out_path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
