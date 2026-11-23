# liver-statistics

ゲームのメンバー一覧のスクリーンショットから、部族メンバーのユーザ名・レベル・名誉を読み取って SQLite に蓄積し、CSV で出力するバッチ（CLI）です。画像の読み取りはすべてローカルで行い、外部へは送信しません。

## セットアップ

前提: macOS、Python 3.14、[uv](https://docs.astral.sh/uv/)、Tesseract（日本語学習データ付き）

```bash
brew install tesseract tesseract-lang
uv venv --python 3.14 .venv
uv pip install -e ".[dev]"
cp .env.example .env        # 必要に応じて編集
```

詳細は [docs/setup.md](docs/setup.md) を参照してください。

## 使い方

コマンドは `.venv/bin/liver-stats`（`source .venv/bin/activate` 済みなら `liver-stats`）です。

### 1. スクリーンショットを取り込む（import）

メンバー画面のスクリーンショットを 1 つのフォルダにまとめ、取り込みます。

```bash
.venv/bin/liver-stats import --dir ./shots/2026-11-22 --tribe ABC
```

| オプション | 必須 | 説明 |
|---|---|---|
| `--dir` | ○ | スクリーンショット（PNG / JPG）のフォルダ |
| `--tribe` | ○ | 部族名 |
| `--date` | | 記録日 `YYYY-MM-DD`。未指定なら下記の優先順位で決まる |
| `--on-conflict` | | 同じ部族・記録日・メンバーが既にある場合の動作。`skip`（既定、何もしない）/ `overwrite`（上書き） |

- 記録日は `--date` > 画像の撮影日時（EXIF）> フォルダ名の日付（`2026-11-22` / `20261122`）> ファイル更新日時 の順に決まります。
- 画像は連続して重なるようにスクロールしながら撮影してください。重なったメンバーは 1 件に統合されます。画面端で見切れたカードは読み取り対象外です。
- 実行後に、画像数・登録件数（新規 / 上書き / スキップ）・要確認の件数が表示されます。壊れた画像があっても他の画像は登録されます。
- 同じフォルダを再度取り込んでも、既定（`skip`）では件数は増えません。

### 2. CSV に出力する（export）

```bash
# 特定の日の全メンバー
.venv/bin/liver-stats export --tribe ABC --date 2026-11-22 --out members.csv

# 期間・メンバーを指定した履歴
.venv/bin/liver-stats export --tribe ABC --member alice --from 2026-10-01 --to 2026-11-30 --out history.csv
```

| オプション | 必須 | 説明 |
|---|---|---|
| `--tribe` | ○ | 部族名 |
| `--out` | ○ | 出力先 CSV（出力先フォルダは存在すること） |
| `--date` | | 記録日（この日の全メンバー）。`--from` / `--to` とは同時に指定できない |
| `--from` / `--to` | | 期間の開始日 / 終了日 |
| `--member` | | メンバー名で絞り込む |

出力は BOM 付き UTF-8（Excel でそのまま開けます）。列は `部族名, 記録日, ユーザ名, レベル, 名誉, 要確認` です。

### 3. 「要確認」の訂正

信頼度が低い・数値を解釈できない・画像間で値が食い違う、といった行には「要確認」が付きます。`member_records` にはユーザ名の列が無い（名前は `members` テーブル）ので、`members` と `tribes` を結合して抽出し、必要なら直接書き換えて訂正してください。

```bash
sqlite3 -header -column data/liver_statistics.db "
SELECT r.id AS record_id, t.name AS tribe, r.record_date, m.id AS member_id, m.name,
       r.level, r.honor, r.review_reason
FROM member_records r
JOIN members m ON m.id = r.member_id
JOIN tribes t  ON t.id = m.tribe_id
WHERE r.needs_review = 1
ORDER BY r.record_date, m.name;"
```

名前・数値の訂正や、「確認済み」にする手順（SQL の例）は [docs/setup.md](docs/setup.md#データの確認訂正) にあります。訂正の前後にはバックアップを取ってください。

名前が既存メンバーに似ている場合（類似度が閾値以上、または3文字以上で1文字違い）は新規メンバーとして登録されたうえで、要確認（`similar_to:<既存名>`）になります。

### 終了コード

| コード | 意味 |
|---|---|
| 0 | 正常終了 |
| 1 | 入力エラー等（フォルダ・部族・日付の指定ミスなど。メッセージを確認） |
| 2 | 想定外のエラー |

## バックアップ

取り込みの前と、DB を直接書き換える前後に、`sqlite3 data/liver_statistics.db ".backup data/backup/liver_statistics_$(date +%Y%m%d).db"` でバックアップを取ります（詳細は [docs/setup.md](docs/setup.md)）。

## 設定

`.env`（`.env.example` をコピーして作成）で変更できます。主なもの:

| 変数 | 既定 | 説明 |
|---|---|---|
| `DB_PATH` | `data/liver_statistics.db` | SQLite のファイル（`data/` は git 管理外） |
| `CONFIDENCE_THRESHOLD` | `60` | この値未満の信頼度を「要確認」にする（0-100） |
| `NAME_SIMILARITY_THRESHOLD` | `0.8` | 類似名と判定する類似度（0-1） |
| `NAME_EDIT_MIN_LENGTH` | `3` | この文字数以上の名前は1文字違いでも類似名とみなす |
| `TESSERACT_TIMEOUT_SEC` | `30` | Tesseract 1回の呼び出しのタイムアウト（秒） |
| `DIGIT_MAX_DISTANCE` | `0.30` | 桁テンプレートとの距離がこの値のとき信頼度0 |
| `NUMBER_OCR_LANG` | `eng` | 数値を Tesseract で読む際の言語（フォールバック時） |
| `LOG_LEVEL` | `INFO` | ログレベル（DEBUG/INFO/WARNING/ERROR/CRITICAL） |
| `TESSDATA_BEST_DIR` | `assets/tessdata_best` | 高精度モデルの置き場所。jpn/eng があれば名前を2モデルで読み、食い違いを要確認にする（取得手順は `docs/setup.md`） |
| `NAME_DISAGREE_CONFIDENCE_CAP` | `55` | 2モデルの名前が食い違ったときの信頼度の上限（`CONFIDENCE_THRESHOLD` より小さく） |
| `TESSERACT_CMD` | （空） | Tesseract の場所。空なら PATH から探す |

画面レイアウトに依存する値は `config/ocr_layout.toml` にあります。

## 精度の測定・調整

```bash
# 正答率の測定（DB には登録しない）。正解 CSV の列は ユーザ名,レベル,名誉
.venv/bin/python scripts/evaluate_accuracy.py --dir src/test/resources/20261122 --truth src/test/resources/truth_20261122.csv

# 数値の桁テンプレート（assets/digits）を作り直す。フォントや画面が変わった場合のみ
.venv/bin/python scripts/build_digit_templates.py --dir <画像フォルダ> --truth <正解CSV>
```

目標の正答率は 70% 以上です（サンプル 10 枚・31 人分で 91.4%）。

## テスト

スクリーンショット・正解データ（`src/resources/`、`src/test/resources/`、`docs/sample/`）はメンバー情報を含むため **GitHub では管理していません**（`.gitignore` で除外）。手元に配置してください。サンプル画像（`docs/sample/BASE_INF.PNG`）が無い場合、インテグレーションテストはスキップされます。

```bash
.venv/bin/pytest
```

## ドキュメント

| ドキュメント | 説明 |
|---|---|
| [docs/BRD.md](docs/BRD.md) | ビジネス要件定義書 |
| [docs/PRD.md](docs/PRD.md) | プロダクト要件定義書 |
| [docs/EDD.md](docs/EDD.md) | エンジニアリング設計書 |
| [docs/setup.md](docs/setup.md) | 環境構築手順 |
| [docs/decisions/](docs/decisions/) | 技術選定の記録（ADR） |
