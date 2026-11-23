# CLAUDE.md - Claude Code 向け作業ガイド

このファイルは **{{PROJECT_NAME}} プロジェクトにおける Claude Code の作業ガイド**です。
作業を開始する前に必ずこのファイルを読んでください。

---

## プロジェクト概要

{{プロジェクトの目的・概要を1〜2文で記載する}}

---

## 必読ルール

作業前に以下のルールファイルを必ず参照してください。

| ルール | ファイル |
|---|---|
| 開発環境・技術スタック | `.claude/rules/development.md` |
| ディレクトリ構成 | `.claude/rules/directory_structure.md` |
| ドキュメント管理 | `docs/.claude/rules/DOCUMENT_MAINTENANCE.md` |

---

## ドキュメント

| ドキュメント | 説明 |
|---|---|
| [docs/BRD.md](docs/BRD.md) | ビジネス要件定義書 |
| [docs/PRD.md](docs/PRD.md) | プロダクト要件定義書 |
| [docs/EDD.md](docs/EDD.md) | エンジニアリング設計書 |
| [docs/setup.md](docs/setup.md) | 環境構築手順 |

---

## 作業フロー

1. **機能追加・変更の前に**: `docs/BRD.md` を修正する（`docs/.claude/rules/DOCUMENT_MAINTENANCE.md` 参照）
2. **BRD 修正後**: `docs/PRD.md` → `docs/EDD.md` の順に作成・更新する
3. **実装後**: 実装レビュー観点 (`docs/.claude/skills/implementation_review/skill.md`) に沿ってレビューする

---

## 環境構築

```bash
# 依存パッケージのインストール
{{インストールコマンド}}

# 環境変数ファイルの作成
cp .env.example .env
# .env を編集して必要な値を設定する
```

詳細は [docs/setup.md](docs/setup.md) を参照してください。
