# テスト観点

## ユニットテスト（`src/test/src/unit/`）

| 対象 | 観点 |
|---|---|
| `ingest/scanner.py` | PNG/JPG（大文字拡張子含む）のみ列挙・ファイル名順 / 画像以外と隠しファイルは無視 / フォルダ無し・画像0枚で例外 |
| `ingest/captured_at.py` | 指定値 > EXIF > フォルダ名の日付 > 更新日時の優先順位 / `YYYY-MM-DD`・`YYYYMMDD` の解釈 / 不正な日付のフォルダ名は無視 |
| `ocr/parser.py` | カンマ付き数値の変換 / 解釈不能は None + `parse_error_*` / 信頼度閾値未満は `low_confidence_*` / 名前が空ならカード破棄 / 日本語文字間の空白除去 |
| `ocr/digit_reader.py` | 桁とカンマを正しく切り出す / 同じ桁の連続（44）を 1 桁に潰さない / 文字なし・テンプレート無し・0-9 不足は None（Tesseract にフォールバック） / 信頼度の換算が `max_distance` 引数に従う |
| `ocr/tesseract_engine.py`（名前） | 高精度モデルが無ければ 1 回、あれば 2 回（`--tessdata-dir` 付き）呼ぶ / 食い違いは信頼度が上限以下 / 初期化時に試し読みし、壊れた学習データは `OcrEngineUnavailableError` / 1 モデル・2 モデルのどちらかを INFO ログに出す |
| `normalize.py` | 全角半角・空白・大文字小文字の正規化 / `members.matcher` からも同じ関数を参照できる |
| `ocr/name_choice.py` | 一致なら信頼度が高い方 / 空白・全角半角・大文字小文字を無視して一致判定 / 食い違いは信頼度を上限以下にして採用 / 低い信頼度はそのまま / 同点は primary |
| `config.py`（高精度モデル） | 学習データが揃えば有効 / `TESSDATA_BEST_DIR` 明示で不足ならエラー / 既定の場所に無ければ無効 / 食い違い時の上限が閾値以上なら、高精度モデルの有無にかかわらずエラー / `for_ocr=False`（export）では学習データを検証しない |
| `ocr/card_detector.check_assets` | アイコン画像が読めれば通る / 無ければ `InputError`（画像単位の失敗に埋もれない） |
| `config.py` | 追加設定（`TESSERACT_TIMEOUT_SEC` 等）の既定値と環境変数による上書き / `LOG_LEVEL` が不正なら `InputError` / 数値でない値・範囲外の値（0 以下の距離・タイムアウト、範囲外の閾値、整数でない最小長）は `InputError` / テストは `.env` に左右されない |
| `evaluation/accuracy.py` | 項目単位の正答数・総数 / ユーザ名を読めない場合は3項目とも不正解 / 目標値 70% での達成判定 / 正解 CSV の欠落・列不足・名前の重複は `InputError` |
| `evaluation/digit_templates.py` | 0-9 が揃わなければ `InputError` / 揃えば既存テンプレートを置き換えて保存 / PNG 変換に失敗しても既存テンプレートを消さない |
| `members/matcher.py` | 正規化（全角半角・大文字小文字・空白）/ 既存メンバーと一致 / 類似名で `similar_to`（複数候補なら ratio 最大のものを表示）/ 類似しない名前は新規 / 短い名前（3文字以上）の1文字違いも類似扱い（「ぽこた」「ぼこた」）/ 最小長未満は対象外 / 編集距離1の判定（置換・挿入・削除） |
| `pipeline.merge_duplicates` | 同一（記録日,名前）を1件に統合 / 信頼度が高い方を採用 / 画像間で値が違えば `conflict_between_images` |
| `export/csv_exporter.py` | BOM 付き UTF-8 / ヘッダー / None は空欄 / 件数を返す |
| `pipeline.run_import`（カード未検出） | カードが無い画像は `images_no_cards` に入り、失敗には数えない / 登録は 0 件で DB に触れない（空の部族も作らない） / CLI が「カード未検出」の行・確認を促す注意書きを出し、全画像が該当する場合は警告を出す（終了コードは 0） |
| `cli.py` | 日付形式の検証 / `--date` と `--from/--to` の同時指定でエラー / `LOG_LEVEL` が不正なら終了コード1 |

## インテグレーションテスト（`src/test/src/integration/`）

実際の SQLite（一時ファイル）と、実際の Tesseract・サンプル画像（`docs/sample/BASE_INF.PNG`、git 管理外。無い場合はスキップ）を使う。

| 観点 |
|---|
| サンプル画像から、見切れたカードを除く4人のユーザ名・レベル・名誉が正しく登録される |
| 同じ画像を再取り込みしても件数が増えない（skip）/ overwrite では上書きされ件数は増えない |
| 画像1枚の読み取り失敗（壊れた画像）があっても他の画像は登録され、失敗画像が報告される |
| 登録中に例外が起きた場合はロールバックされ、部分的なデータが残らない |
| 類似名の新規メンバーは登録され、`needs_review` と `similar_to:` が付く |
| export（日付指定・期間・メンバー指定）が条件どおりの行を出力する |
| 別部族は別メンバーとして分離される |
| アイコン画像が無い設定で取り込むと、全画像失敗ではなく `InputError` で終了し DB に何も書かない |
