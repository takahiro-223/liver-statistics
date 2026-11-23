# 環境構築手順

## 前提

- macOS、Python 3.14（依存ライブラリが未対応の場合は 3.13 / 3.12。ADR-002 参照）
- [uv](https://docs.astral.sh/uv/)
- Tesseract 本体と日本語学習データ

```bash
brew install tesseract tesseract-lang
tesseract --list-langs | grep -E "^(jpn|eng)$"   # jpn と eng が表示されること
```

## セットアップ

```bash
uv venv --python 3.14 .venv
uv pip install -e ".[dev]"
cp .env.example .env     # 必要に応じて編集
```

## 使い方

```bash
# 日付フォルダ配下のスクリーンショットを読み取り、登録する
.venv/bin/liver-stats import --dir ./shots/2026-11-22 --tribe ABC

# CSV 出力
.venv/bin/liver-stats export --tribe ABC --date 2026-11-22 --out members.csv
.venv/bin/liver-stats export --tribe ABC --member alice --from 2026-10-01 --to 2026-11-30 --out history.csv
```

- 記録日は `--date` > 画像の撮影日時(EXIF) > フォルダ名の日付 > ファイル更新日時の順に決まる。
- 「要確認」の行は SQLite で抽出し、必要なら直接書き換えて訂正する。
  `sqlite3 data/liver_statistics.db "SELECT * FROM member_records WHERE needs_review = 1"`

## テスト

```bash
.venv/bin/pytest                      # ユニット + インテグレーション
.venv/bin/python scripts/evaluate_accuracy.py --dir <画像フォルダ> --truth <正解CSV>   # 正答率の測定
.venv/bin/python scripts/build_digit_templates.py --dir <画像フォルダ> --truth <正解CSV>   # 数値の桁テンプレート（assets/digits）を作り直す（通常は不要）
```
