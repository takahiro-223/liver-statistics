"""CLI: liver-stats import / export。"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import date
from pathlib import Path

from .config import Config, load_config
from .db.connection import connect
from .db.repository import Repository
from .errors import InputError, LiverStatisticsError
from .export.csv_exporter import export_csv
from .members.matcher import normalize_name
from .pipeline import run_import


def _date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"日付は YYYY-MM-DD 形式で指定してください: {value}") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="liver-stats", description="スクリーンショットから部族メンバーの活動を記録する")
    sub = parser.add_subparsers(dest="command", required=True)

    imp = sub.add_parser("import", help="フォルダ内の画像を読み取りDBに登録する")
    imp.add_argument("--dir", required=True, type=Path, help="スクリーンショットのフォルダ")
    imp.add_argument("--tribe", required=True, help="部族名")
    imp.add_argument("--date", type=_date, help="記録日 (YYYY-MM-DD)。未指定なら撮影日時/フォルダ名/更新日時")
    imp.add_argument("--on-conflict", choices=["skip", "overwrite"], default="skip",
                     help="同一部族・記録日・メンバーが既にある場合の動作（既定 skip）")

    exp = sub.add_parser("export", help="蓄積データをCSVに出力する")
    exp.add_argument("--tribe", required=True, help="部族名")
    exp.add_argument("--date", type=_date, help="記録日（この日の全メンバー）")
    exp.add_argument("--from", dest="date_from", type=_date, help="期間の開始日")
    exp.add_argument("--to", dest="date_to", type=_date, help="期間の終了日")
    exp.add_argument("--member", help="メンバー名（任意）")
    exp.add_argument("--out", required=True, type=Path, help="出力先CSVパス")
    return parser


def _cmd_import(args: argparse.Namespace, cfg: Config) -> int:
    s = run_import(args.dir, args.tribe, args.date, args.on_conflict, cfg)
    ok = s.images_total - len(s.images_failed) - len(s.images_no_cards)
    print(f"部族: {args.tribe}" + (f" / 記録日: {args.date}" if args.date else ""))
    print(f"画像: {s.images_total}枚（成功 {ok} / 失敗 {len(s.images_failed)} / カード未検出 {len(s.images_no_cards)}）")
    if s.images_failed:
        print("  失敗: " + ", ".join(s.images_failed))
    if s.images_no_cards:
        print("  カード未検出: " + ", ".join(s.images_no_cards))
        print("  ※ メンバー画面のスクリーンショットを、縮小されていない元の解像度で指定しているか確認してください")
    if s.images_no_cards and len(s.images_no_cards) + len(s.images_failed) == s.images_total:
        print("警告: どの画像からもメンバーを読み取れませんでした（登録は行われていません）")
    print(f"登録: {s.inserted + s.overwritten + s.skipped}件"
          f"（新規 {s.inserted} / 上書き {s.overwritten} / スキップ {s.skipped}）")
    print(f"要確認: {len(s.needs_review)}件" + (f"（{', '.join(s.needs_review)}）" if s.needs_review else ""))
    return 0


def _cmd_export(args: argparse.Namespace, cfg: Config) -> int:
    if args.date and (args.date_from or args.date_to):
        raise InputError("--date と --from/--to は同時に指定できません")
    if args.date_from and args.date_to and args.date_from > args.date_to:
        raise InputError("--from は --to 以前の日付を指定してください")
    if not args.out.parent.is_dir():
        raise InputError(f"出力先フォルダが存在しません: {args.out.parent}")
    conn = connect(cfg.db_path)
    try:
        repo = Repository(conn)
        if repo.find_tribe(args.tribe) is None:
            raise InputError(f"部族が登録されていません: {args.tribe}")
        rows = repo.query_records(
            args.tribe, args.date, args.date_from, args.date_to,
            member_key=normalize_name(args.member) if args.member else None,
        )
    finally:
        conn.close()
    count = export_csv(rows, args.out)
    print(f"{count}件を出力しました: {args.out}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        cfg = load_config()  # 設定エラーは引数の検証より先に報告する
        logging.basicConfig(level=cfg.log_level, format="%(levelname)s %(message)s")
        return _cmd_import(args, cfg) if args.command == "import" else _cmd_export(args, cfg)
    except LiverStatisticsError as exc:
        print(f"エラー: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001 - CLI 最上位。想定外エラーを終了コード2で通知する
        print(f"想定外のエラー: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
