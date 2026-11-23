# ディレクトリ構成ルール

このファイルは **{{PROJECT_NAME}} プロジェクトのディレクトリ構造に関するルール**を定めたファイルです。
新しいファイルやディレクトリを追加・変更する際は、必ずこのファイルを参照し、ルールに従って作業を行ってください。

---

このプロジェクトは以下のフォルダ構成に従ってください。

```
{{PROJECT_NAME}}/
├── README.md                    # プロジェクト概要・クイックスタート
├── CLAUDE.md                    # Claude Code 向け作業ガイド
├── .env.example                 # 環境変数テンプレート
├── {{VERSION_FILE}}             # 依存関係・ビルド設定（pyproject.toml / package.json 等）
│
├── docs/                        # ドキュメント
│   ├── BRD.md                   # ビジネス要件定義書 (Business Requirements Document)
│   ├── EDD.md                   # エンジニアリング設計書 (Engineering Design Document)
│   ├── PRD.md                   # プロダクト要件定義書 (Product Requirements Document)
│   ├── architecture.md          # システム全体設計
│   ├── data_flow.md             # データフロー図・説明
│   ├── setup.md                 # 環境構築手順
│   ├── api.md                   # API仕様（API を持つ場合）
│   └── decisions/               # 技術選定の意思決定記録 (ADR)
│       └── 001_example.md
│
├── src/
│   └── {{package_name}}/        # メインのソースコード
│       ├── __init__.py
│       ├── {{module_a}}/        # 役割に応じてモジュールを分割する
│       ├── {{module_b}}/
│       └── config.py            # 設定管理
│   └── test/                    # テスト（詳細は src/.claude/rules/TEST_REGULATION.md）
│       ├── TEST_POINT.md        # テスト観点
│       └── src/
│           ├── unit/            # ユニットテスト
│           └── integration/     # インテグレーションテスト
│
└── scripts/                     # 実行スクリプト（必要な場合）
    └── {{script}}.py
```

## ルール

- 新しいファイルは必ず上記の対応するディレクトリに配置する
- `src/{{package_name}}/` 配下のモジュールは役割ごとに分離し、統合レイヤー（`pipeline.py` 等）でまとめる
- 機密データ・生成物（`data/`・`.env` 等）はgit管理外 (`.gitignore` に追記) とする
- **画像データ（スクリーンショット）と、メンバー情報を含む資料（正解データ CSV、DB、出力 CSV）は GitHub で管理しない。** `src/resources/`・`src/test/resources/`・`docs/sample/`・`data/`、および `*.csv` / `*.db` / 画像の一括パターンを `.gitignore` で除外している。新しい置き場所を作る場合も `.gitignore` に追記すること（`assets/` のアイコン・桁テンプレートは動作に必要なため管理対象）
- 設定値はすべて `config.py` および `.env` で一元管理し、ハードコードしない
- ドキュメントは `docs/` に集約し、技術選定の理由は `docs/decisions/` にADR形式で記録する
- `docs/BRD.md`、`docs/EDD.md`、`docs/PRD.md` は必ず作成する必須ドキュメントとする
- **機能追加・既存機能の変更を行う場合は、実装作業の前に必ず `docs/BRD.md` を修正すること**
