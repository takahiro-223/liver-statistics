# テスト観点

## ユニットテスト（`src/test/src/unit/`）

| 対象 | 観点 |
|---|---|
| `ingest/scanner.py` | PNG/JPG（大文字拡張子含む）のみ列挙・ファイル名順 / 画像以外と隠しファイルは無視 / フォルダ無し・画像0枚で例外 |
| `ingest/captured_at.py` | 指定値 > EXIF > フォルダ名の日付 > 更新日時の優先順位 / `YYYY-MM-DD`・`YYYYMMDD` の解釈 / 不正な日付のフォルダ名は無視 |
| `ocr/parser.py` | カンマ付き数値の変換 / 解釈不能は None + `parse_error_*` / 信頼度閾値未満は `low_confidence_*` / 名前が空ならカード破棄 / 日本語文字間の空白除去 |
| `ocr/digit_reader.py` | 桁とカンマを正しく切り出す / 同じ桁の連続（44）を 1 桁に潰さない / 文字なし・テンプレート無し・0-9 不足は None（Tesseract にフォールバック） |
| `members/matcher.py` | 正規化（全角半角・大文字小文字・空白）/ 既存メンバーと一致 / 類似名で `similar_to` / 類似しない名前は新規 |
| `pipeline.merge_duplicates` | 同一（記録日,名前）を1件に統合 / 信頼度が高い方を採用 / 画像間で値が違えば `conflict_between_images` |
| `export/csv_exporter.py` | BOM 付き UTF-8 / ヘッダー / None は空欄 / 件数を返す |
| `cli.py` | 日付形式の検証 / `--date` と `--from/--to` の同時指定でエラー |

## インテグレーションテスト（`src/test/src/integration/`）

実際の SQLite（一時ファイル）と、実際の Tesseract・サンプル画像（`docs/sample/BASE_INF.PNG`）を使う。

| 観点 |
|---|
| サンプル画像から、見切れたカードを除く4人のユーザ名・レベル・名誉が正しく登録される |
| 同じ画像を再取り込みしても件数が増えない（skip）/ overwrite では上書きされ件数は増えない |
| 画像1枚の読み取り失敗（壊れた画像）があっても他の画像は登録され、失敗画像が報告される |
| 登録中に例外が起きた場合はロールバックされ、部分的なデータが残らない |
| 類似名の新規メンバーは登録され、`needs_review` と `similar_to:` が付く |
| export（日付指定・期間・メンバー指定）が条件どおりの行を出力する |
| 別部族は別メンバーとして分離される |
