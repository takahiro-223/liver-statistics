# 環境構築手順

## 前提

- macOS、Python 3.14（依存ライブラリが未対応の場合は 3.13 / 3.12。ADR-002 参照）
- [uv](https://docs.astral.sh/uv/)
- Tesseract 本体と日本語学習データ

```bash
brew install tesseract tesseract-lang
tesseract --list-langs | grep -E "^(jpn|eng)$"   # jpn と eng が表示されること
```

名前の読み取り精度を上げるため、高精度モデル（`tessdata_best`、約 30MB）を `assets/tessdata_best/` に置くことを推奨します（git 管理外。無くても動作しますが、名前は 1 モデルで読みます）。

```bash
# コミットを固定して取得し、SHA-256 を検証する（ブランチ最新を取得しない）
REV=e12c65a915945e4c28e237a9b52bc4a8f39a0cec
mkdir -p assets/tessdata_best
for l in jpn eng; do curl -fL -o assets/tessdata_best/$l.traineddata https://github.com/tesseract-ocr/tessdata_best/raw/$REV/$l.traineddata; done
cat > /tmp/tessdata_best.sha256 <<EOF2
8280aed0782fe27257a68ea10fe7ef324ca0f8d85bd2fd145d1c2b560bcb66ba  assets/tessdata_best/eng.traineddata
36bdf9ac823f5911e624c30d0553e890b8abc7c31a65b3ef14da943658c40b79  assets/tessdata_best/jpn.traineddata
EOF2
shasum -a 256 -c /tmp/tessdata_best.sha256   # 両方 OK と表示されること
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

# ランキング表（最新の記録日と、その前回の記録日の比較）。確認・訂正の後に実行する
.venv/bin/liver-stats ranking --tribe ABC --out ranking.csv

# CSV 出力
.venv/bin/liver-stats export --tribe ABC --date 2026-11-22 --out members.csv
.venv/bin/liver-stats export --tribe ABC --member alice --from 2026-10-01 --to 2026-11-30 --out history.csv
```

- 記録日は `--date` > 画像の撮影日時(EXIF) > フォルダ名の日付 > ファイル更新日時の順に決まる。
- 「要確認」の行は SQLite で抽出し、必要なら直接書き換えて訂正する（手順は「データの確認・訂正」）。

## データの確認・訂正

登録後の誤り（主に誤読したユーザ名）は、SQLite で直接確認・訂正します（訂正機能は提供していません）。**訂正の前にバックアップを取ってください**（次節）。

`member_records` にはユーザ名の列が無く、名前は `members` テーブルにあります（`tribes` は部族名）。

### 1. 要確認の行を、ユーザ名つきで一覧する

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

`record_id` は記録の ID、`member_id` はメンバーの ID です（以降の訂正で使います）。`review_reason` の見方: `low_confidence_*` は信頼度が低い、`parse_error_*` は数値として読めない、`conflict_between_images` は画像間で値が食い違う、`similar_to:<名前>` は既存メンバーに名前が似ている。名前を 2 つのモデルで読んで食い違った場合は `low_confidence_name` になります（読み取りが正しくても付くことがあります）。

### 2. ユーザ名を訂正する

メンバーの表示名（`members.name`）と照合用キー（`members.name_key`）を直します。`name_key` は、全角半角を揃え（NFKC）、空白を除き、小文字にした値です。次のコマンドで求められます。

```bash
.venv/bin/python -c "from liver_statistics.normalize import normalize_name; print(normalize_name('正しい名前'))"
```

誤読名を**別名（`member_aliases`）に登録**しておくと、次回以降に同じ誤読が起きても同じメンバーに紐付きます（新しいメンバーが増えません）。

```sql
BEGIN;
-- 誤読名のキーを別名にする
INSERT INTO member_aliases (member_id, alias_key) SELECT id, name_key FROM members WHERE id = <member_id>;
-- 表示名と照合キーを、正しい名前に直す
UPDATE members SET name = '正しい名前', name_key = '<正しい名前の正規化キー>' WHERE id = <member_id>;
COMMIT;
```

**書き換えてよいのは `<…>` の部分と `'正しい名前'` だけです。** `INSERT INTO member_aliases (member_id, alias_key)` の `(member_id, alias_key)` は**列名**なので、値（`8` など）に書き換えないでください（書き換えると `near "8": syntax error` になります。誤読名のキーは `SELECT id, name_key FROM members` が自動で入れます）。

例: 一覧で `member_id = 8` の `おはる._oharu` を `おはる_oharu` に直す（キーは上のコマンドで求めた値。ここでは同じ文字列）:

```bash
sqlite3 data/liver_statistics.db "
BEGIN;
INSERT INTO member_aliases (member_id, alias_key) SELECT id, name_key FROM members WHERE id = 8;
UPDATE members SET name = 'おはる_oharu', name_key = 'おはる_oharu' WHERE id = 8;
COMMIT;"
```

エラーが出た場合は、`BEGIN` 以降が取り消されるので DB は変わりません（`SELECT id, name, name_key FROM members WHERE id = 8;` で確認できます）。名前に `'` が含まれる場合は `''` と 2 つ重ねます。`$` や `` ` `` を含む名前は、シェルが解釈してしまうので、`sqlite3 data/liver_statistics.db` を対話的に起動して SQL を貼り付けてください。

同じ部族に、正しい名前のメンバーが**既にいる**場合（誤読名が別メンバーとして増えた場合）は、上の UPDATE ではなく、記録を正しいメンバーへ付け替えて、誤ったメンバーを削除します（`PRAGMA foreign_keys = ON;` を先に実行）。

```sql
BEGIN;
UPDATE member_records SET member_id = <正しい member_id> WHERE member_id = <誤った member_id>;
INSERT INTO member_aliases (member_id, alias_key) SELECT <正しい member_id>, name_key FROM members WHERE id = <誤った member_id>;
DELETE FROM member_aliases WHERE member_id = <誤った member_id>;
DELETE FROM members WHERE id = <誤った member_id>;
COMMIT;
```

### 3. レベル・名誉を訂正する

```sql
UPDATE member_records SET level = <レベル>, honor = <名誉> WHERE id = <record_id>;
```

### 4. 確認済みにする

訂正した行、または読み取りが正しかった行は、要確認を外します（外すと次回の一覧に出ません）。

```sql
UPDATE member_records SET needs_review = 0, review_reason = NULL WHERE id = <record_id>;
-- 同じメンバーの要確認をまとめて外す場合
UPDATE member_records SET needs_review = 0, review_reason = NULL WHERE member_id = <member_id>;
```

SQL は `sqlite3 data/liver_statistics.db` で対話的に実行するか、`sqlite3 data/liver_statistics.db "<SQL>"` で 1 文ずつ実行します。

## バックアップ

DB は SQLite の単一ファイル（`data/liver_statistics.db`、git 管理外）です。取り込みの前と、DB を直接書き換える（要確認の行や誤読した名前を訂正する）前後に、SQLite 標準の `.backup` でバックアップを取ってください（書き込み中でも一貫したコピーが作られます）。バックアップはメンバー情報を含むため、`data/` 配下（git 管理外）に置きます。

```bash
mkdir -p data/backup
sqlite3 data/liver_statistics.db ".backup data/backup/liver_statistics_$(date +%Y%m%d).db"
```

復元するときは、バックアップのファイルを `DB_PATH`（既定 `data/liver_statistics.db`）の場所へコピーして戻します。

## テスト

```bash
.venv/bin/pytest                      # ユニット + インテグレーション
.venv/bin/python scripts/evaluate_accuracy.py --dir <画像フォルダ> --truth <正解CSV>   # 正答率の測定
.venv/bin/python scripts/build_digit_templates.py --dir <画像フォルダ> --truth <正解CSV>   # 数値の桁テンプレート（assets/digits）を作り直す（通常は不要）
```
