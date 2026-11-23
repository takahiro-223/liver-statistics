# 開発環境ルール

このファイルは **liver-statistics プロジェクトで原則として使用する開発環境・技術スタックのルール**を定めたファイルです。
新しい技術の選定や実装方針を決める際は、必ずこのファイルを参照し、ルールに従って作業を行ってください。

---

## 技術スタック

### 言語

- **Python 3.14** を使用する（依存ライブラリが未対応の場合は 3.13 → 3.12。ADR-002）
- 依存関係の管理には `pyproject.toml` を使用する

### データストア（該当する場合）

- **SQLite**（標準ライブラリ `sqlite3`）を使用する
  - ローカル単一ユーザー向けでサーバー不要。DB ファイルは `data/` 配下（git 管理外）。ADR-003

### その他の主要ライブラリ・フレームワーク

- **OpenCV / Pillow / NumPy**: 画像処理（カード検出・前処理・EXIF）
- **Tesseract + pytesseract**: ローカル OCR（ADR-004）。本体は `brew install tesseract tesseract-lang`
- **python-dotenv**: `.env` の読み込み
- **pytest**: テスト（`dev` セクション）

## ルール

- 上記以外の言語・データストアへの変更は、`docs/decisions/` にADR形式で理由を記録した上で検討する
- 依存ライブラリはバージョン管理ファイル（`pyproject.toml` / `package.json` 等）で一元管理し、直接インストールのみで済ませない
