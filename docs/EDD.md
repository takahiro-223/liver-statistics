# EDD - エンジニアリング設計書 (Engineering Design Document)

## 1. プロジェクト概要

| 項目 | 内容 |
|---|---|
| プロジェクト名 | liver-statistics |
| 作成日 | 2026-11-22 |
| 関連ドキュメント | [BRD](./BRD.md) / [PRD](./PRD.md) |
| 技術選定の記録 | [ADR-002 言語](./decisions/002_language_python.md) / [ADR-003 データストア](./decisions/003_datastore_sqlite.md) / [ADR-004 画像読み取り方式](./decisions/004_ocr_approach.md) |

---

## 2. システム構成

### 2.1 技術スタック

| 役割 | 技術 | 備考 |
|---|---|---|
| 言語 | Python 3.14 | ADR-002。依存ライブラリが未対応の場合は 3.13 → 3.12 の順に変更を検討。依存関係は `pyproject.toml` で管理 |
| データストア | SQLite（標準ライブラリ `sqlite3`） | ADR-003。ローカル単一ファイル。ORM は使わない |
| 画像処理 | OpenCV (`opencv-python-headless`)、Pillow、NumPy | カード位置の検出、前処理、EXIF 取得 |
| 文字認識（OCR） | Tesseract 5（`jpn` / `eng` 学習データ）+ `pytesseract` | ADR-004。ローカル完結。`OcrEngine` インターフェース越しに差し替え可能 |
| CLI | `argparse`（標準ライブラリ） | コマンド名: `liver-stats` |
| 設定 | `python-dotenv`、`config.py` | 設定値は `.env` と設定ファイル（TOML）で管理 |
| テスト | `pytest` | `pyproject.toml` の `dev` セクションで管理 |
| システム依存 | Tesseract 本体（macOS: `brew install tesseract tesseract-lang`） | pip では導入できないため `docs/setup.md` に手順を記載。開発環境には導入済み |

### 2.2 コンポーネント構成

```
┌──────────────────────────────────────────┐
│ cli.py   (liver-stats import / export)   │
└───────┬───────────────────────┬──────────┘
        │ import                │ export
┌───────▼──────────┐     ┌──────▼───────────┐
│ pipeline.py      │     │ export/          │
│ (統合レイヤー)    │     │  csv_exporter.py │
└─┬────┬─────┬────┬┘     └──────┬───────────┘
  │    │     │    │             │
┌─▼──┐ ┌▼───┐ ┌▼──────┐ ┌▼──────▼────────┐
│ingest│ │ocr/ │ │members/│ │ db/            │
│      │ │     │ │matcher │ │ repository.py  │
└──────┘ └─────┘ └────────┘ └───────┬────────┘
                                    │
                           ┌────────▼────────┐
                           │ SQLite (data/*.db)│
                           └─────────────────┘
```

- `scripts/` の `evaluate_accuracy.py` / `build_digit_templates.py` は、`evaluation/`（正答率の測定・桁テンプレート作成）を呼ぶ補助ツールで、図の `pipeline.py` / `ocr/` を再利用する（取り込みの本線には含まれない）。
- 外部ネットワークへの通信は行わない（PRD セキュリティ要件）。OCR は Tesseract をローカルのサブプロセスとして呼び出す。
- `pipeline.py` が取り込みの全工程を統合し、トランザクション境界を持つ。

---

## 3. データフロー

### 3.1 取り込み（`liver-stats import`）

```
フォルダパス + 部族名 [+ 記録日] [+ 競合時の動作]
  → ingest.scanner      : 直下の PNG/JPG を列挙（ファイル名順）。0枚ならエラー終了
  → ingest.captured_at  : 画像ごとに記録日を決定
                          （--date 指定 > EXIF 撮影日時 > フォルダ名の日付 > ファイル更新日時）
  → ocr.card_detector   : （処理前に check_assets でアイコン画像を確認。無ければ InputError で終了）
                          アイコンのテンプレートマッチングでメンバーカードを検出
  → ocr.engine          : カードごとにユーザ名・レベル・名誉の領域を OCR（文字列 + 信頼度）
  → ocr.parser          : 数値のカンマ除去・変換、「要確認」判定
  → pipeline            : 同一実行内の重複メンバーを統合（3.2 参照）
  → members.matcher     : ユーザ名を既存メンバー・別名と照合（4章・5.4 参照）
  → db.repository       : 1トランザクションで登録（重複は上書き／スキップ）
  → 実行結果の表示（画像数・登録件数・要確認件数と対象ユーザ名・失敗画像・カード未検出の画像）
```

- 1枚の画像で例外が発生した場合は、その画像を失敗として記録して次の画像へ進む。
- 登録するカードが全画像で1枚も無い場合は、DB に触れない（空の部族も作らない）。
- 例外は出なかったが、読み取れたカードが1枚も無い画像（アイコンを検出できない低解像度の画像、メンバー画面以外、名前がすべて空など）は、失敗とは別に「カード未検出」として記録し、実行結果で報告する（ログは DEBUG）。登録は妨げない。
- DB への書き込みは、全画像の解析が終わった後に1トランザクションで行う。登録中に失敗した場合はロールバックし、部分的なデータを残さない。ただし画像単位の解析失敗は登録を妨げない（失敗画像として報告する）。

### 3.2 同一実行内の重複統合

同じ（記録日、正規化済みユーザ名）が複数画像から得られた場合、1件にまとめる。

1. 全項目（名前・レベル・名誉）の信頼度の最小値が高い方を採用する
2. 値（レベル・名誉）が画像間で異なる場合は、採用した方に「要確認」を付け、理由に `conflict_between_images` を記録する

### 3.3 CSV 出力（`liver-stats export`）

```
部族名 + (記録日 | 期間 [+ メンバー名]) + 出力先パス
  → db.repository : 条件に合致する記録を取得
  → export.csv_exporter : CSV（UTF-8 BOM 付き）としてファイルに書き出す
```

---

## 4. データベース設計

テーブルは5つ（`tribes` / `members` / `member_aliases` / `source_images` / `member_records`）。5つを超えないため、個別設計書には分割せず本書で記載する。

### 4.1 E-R 図

```
tribes 1 ──< members 1 ──< member_aliases
  │             │
  │             └──< member_records >── 1 source_images
  └──────────────────< source_images
```

| 関係 | 説明 |
|---|---|
| tribes 1 : N members | 部族は複数のメンバーを持つ。メンバーは1つの部族に属する |
| members 1 : N member_aliases | メンバーは複数の別名（誤読名など）を持てる |
| members 1 : N member_records | メンバーは記録日ごとに1件の記録を持つ |
| source_images 1 : N member_records | 1枚の画像から複数メンバーの記録が作られる |
| tribes 1 : N source_images | 画像は取り込み時に指定した部族に紐付く |

### 4.2 テーブル定義

```sql
PRAGMA foreign_keys = ON;

CREATE TABLE tribes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL UNIQUE,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE members (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    tribe_id    INTEGER NOT NULL REFERENCES tribes(id),
    name        TEXT    NOT NULL,              -- 表示用ユーザ名（初回登録時の読み取り値）
    name_key    TEXT    NOT NULL,              -- 正規化キー（5.4）
    created_at  TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    UNIQUE (tribe_id, name_key)
);

CREATE TABLE member_aliases (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id   INTEGER NOT NULL REFERENCES members(id),
    alias_key   TEXT    NOT NULL,              -- 別名の正規化キー
    created_at  TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    UNIQUE (member_id, alias_key)
);

CREATE TABLE source_images (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    tribe_id     INTEGER NOT NULL REFERENCES tribes(id),
    file_name    TEXT    NOT NULL,
    file_path    TEXT    NOT NULL,
    sha256       TEXT    NOT NULL,
    captured_at  TEXT    NOT NULL,             -- 記録日の決定に使った日時（ISO 8601）
    imported_at  TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    UNIQUE (tribe_id, sha256)                  -- 同じ画像の二重登録を防ぐ
);

CREATE TABLE member_records (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id        INTEGER NOT NULL REFERENCES members(id),
    record_date      TEXT    NOT NULL,         -- YYYY-MM-DD
    level            INTEGER,                  -- 解釈できない場合は NULL（要確認）
    honor            INTEGER,                  -- 同上
    needs_review     INTEGER NOT NULL DEFAULT 0 CHECK (needs_review IN (0, 1)),
    review_reason    TEXT,                     -- 例: low_confidence_name,parse_error_level
    source_image_id  INTEGER NOT NULL REFERENCES source_images(id),
    created_at       TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at       TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    UNIQUE (member_id, record_date)            -- 同一メンバー・同一記録日の重複防止
);

CREATE INDEX idx_member_records_date ON member_records(record_date);
```

- 重複防止（US-04）は `UNIQUE (member_id, record_date)` と `source_images.sha256` で担保する。
- 登録後の訂正・別名登録は運営者が DB を直接書き換える（PRD 4.3 / 4.4）。`needs_review = 1` の行を SQL で抽出できる。
- `review_reason` は複数ある場合カンマ区切りとする。

---

## 5. モジュール設計

### 5.1 `config.py`

設定を一元管理する。`.env` と設定ファイル `config/ocr_layout.toml` を読み込み、型付きオブジェクトとして提供する。

```python
@dataclass(frozen=True)
class Config:
    db_path: Path
    log_level: str
    ocr_lang: str                # 既定 "jpn+eng"
    tesseract_cmd: str | None
    confidence_threshold: float  # 要確認とする信頼度の閾値（0-100）
    icon_match_threshold: float  # アイコン検出のマッチ率の閾値（0-1）
    name_similarity_threshold: float  # 類似名の閾値（既定 0.8）
    name_edit_min_length: int    # 編集距離1以内を類似名とみなす最小の名前の長さ（既定 3）
    tesseract_timeout_sec: float # Tesseract 1回の呼び出しのタイムアウト（既定 30 秒）
    number_ocr_lang: str         # 数値を Tesseract で読む際の言語（既定 "eng"）
    digit_max_distance: float    # 桁テンプレートとの距離がこの値のとき信頼度 0（既定 0.30）
    tessdata_best_dir: Path | None  # 高精度モデルの置き場所（既定 assets/tessdata_best。無ければ None で1モデル）
    name_disagree_confidence_cap: float  # 2モデルの名前が食い違ったときの信頼度の上限（既定 55）
    icons_dir: Path              # アイコン画像の置き場所（既定 assets/icons）
    digits_dir: Path             # 数値の桁テンプレートの置き場所（既定 assets/digits）
    layout: LayoutConfig         # 5.3 参照（アイコン高さ h を単位とする相対比率）

def load_config(for_ocr: bool = True) -> Config: ...
# for_ocr=False（export など OCR を使わないコマンド）では高精度モデルの学習データを検証せず None とする
# LOG_LEVEL が DEBUG/INFO/WARNING/ERROR/CRITICAL 以外、数値設定が数値でない場合は InputError

```

### 5.2 `ingest/`

```python
# scanner.py
def list_images(directory: Path) -> list[Path]:
    """直下の .png/.jpg/.jpeg（大文字小文字を区別しない）をファイル名順に返す。
    ディレクトリが存在しない場合は ImportDirectoryNotFoundError、
    画像が0枚の場合は NoImagesFoundError を送出する。"""

# captured_at.py（EXIF は DateTimeOriginal を優先し、無ければ DateTime を使う。
#   サンプル画像には DateTime のみが含まれていた）
def resolve_record_date(image_path: Path, override: date | None) -> tuple[date, datetime]:
    """override があればそれを優先。なければ EXIF DateTimeOriginal、
    それも無ければ画像の親フォルダ名が日付（YYYY-MM-DD / YYYYMMDD）ならその日付、
    それも無ければファイル更新日時（ローカル時刻）を使う。
    スマホから手動コピーすると更新日時が変わるため、日付フォルダの運用を前提とする。
    戻り値は (記録日, 決定に使った日時)。"""
```

### 5.3 `ocr/`

**`card_detector.py`** — メンバーカードの検出

「剣アイコン」のテンプレート（`assets/icons/sword.png`、サンプル画像から切り出し）を複数スケールでテンプレートマッチングし、見つかった位置を1カード分のアンカーとする。続いて星アイコン（`star.png`）が期待位置にあることを確認し、無ければ見切れたカードとして除外する。星アイコン・宝石アイコンは剣アイコンから下方向に等間隔で並ぶため、剣アイコンの位置とサイズを基準に、相対比率でユーザ名・レベル・名誉の領域を算出する。族長カードも同じ配置のため同一処理で検出する。

```python
@dataclass(frozen=True)
class CardRegions:
    name: Box      # ユーザ名の領域
    level: Box     # レベル（剣）の数値領域
    honor: Box     # 名誉（星）の数値領域

def check_assets(cfg: Config) -> None:
    """sword.png / star.png が読めなければ InputError（ICONS_DIR の確認を促す）。"""

def detect_cards(image: np.ndarray, cfg: Config) -> list[CardRegions]:
    """マッチ率が閾値未満のアンカーは除外する。
    画像の下端・上端で見切れて領域が画像外にはみ出すカードは除外する（PRD 4.2）。
    上から下の順に返す。"""
```

- 領域の相対比率（アイコン高さ `h` を単位とする）は `config/ocr_layout.toml` に置く。初期値は `docs/sample/BASE_INF.PNG` を基準に実装時に調整する。
  - 名前: 剣アイコンの上端から約 `1.2h` 上を下端とする1行分、左端はアイコン左端、右端はカード右端
  - 数値: 各アイコンと同じ高さの帯、左端はアイコン右端から約 `2h`、右端はカード右端

**`engine.py`** — OCR エンジンのインターフェース

```python
@dataclass(frozen=True)
class OcrResult:
    text: str
    confidence: float   # 0-100。文字が検出できなければ 0

class OcrEngine(Protocol):
    def read_name(self, image: np.ndarray) -> OcrResult: ...
    def read_number(self, image: np.ndarray) -> OcrResult: ...
```

**`tesseract_engine.py`** — Tesseract 実装

- 名前: グレースケールのまま（拡大・二値化はしない）周囲に白い余白を付け、`--psm 7`（1行）、言語 `jpn+eng`。二値化と拡大は細い字や濁点・半濁点を崩すため行わない（ADR-004 追記）
- 名前の 2 モデル読み取り（ADR-004 追記）: `assets/tessdata_best/`（高精度モデル）に `OCR_LANG` の全言語の学習データがあれば、同じ領域を高精度モデルでも読む（前処理は濃淡の引き伸ばし。`--tessdata-dir` で学習データを指定）。`ocr/name_choice.choose_name(primary, secondary, disagree_cap)` が、信頼度が高い方を採用し、正規化後の名前が食い違うときは信頼度を `NAME_DISAGREE_CONFIDENCE_CAP` 以下にして「要確認」にする。学習データが無ければ従来の 1 モデルで読む。`TESSDATA_BEST_DIR` を明示して学習データが無い場合は `InputError`。2 つの Tesseract は別プロセスなので並列に呼ぶ。エンジン初期化時に、高精度モデルを使う場合は白い画像の試し読みで学習データが読めることを確認し、読めなければ `OcrEngineUnavailableError`（壊れた学習データが「全画像の失敗」に埋もれないようにする）。どちらのモードで読むかは初期化時に INFO ログで出す
- 数値: `digit_reader`（桁テンプレート照合）で読む。テンプレートが無い・切り出せない場合のみ、前処理の後 `--psm 7`、`tessedit_char_whitelist=0123456789,` の Tesseract にフォールバックする（`read_number_tesseract`）
- 信頼度は Tesseract が返す単語ごとの信頼度の最小値とする
- Tesseract が見つからない場合は `OcrEngineUnavailableError`

**`digit_reader.py`** — 数値の桁テンプレート照合（ADR-004 追記）

ゲーム独自フォントの「4」を Tesseract が誤読し、「449,368」→「49368」のように「44」の並びで桁が落ちるため、数値は Tesseract を使わずに読む。

- 数値領域を二値化し、文字範囲に切り詰めて 3 倍に拡大する
- 連結成分で 1 桁ずつ切り出す（最大の文字の高さの半分未満の成分はカンマ）。幅/高さが 0.95 を超える成分（桁のくっつき）がある場合は読み取り不能として `None`
- 各桁を 24×36 に正規化し、`assets/digits/<桁>_<連番>.png`（桁ごとに最大 30 枚）との最近傍照合（画素の平均絶対差）で 0-9 を決める
- 信頼度 = `100 × (1 − 各桁の最近傍距離の最大値 / DIGIT_MAX_DISTANCE)`（下限 0。`read_digits(image, templates, max_distance)`）。`CONFIDENCE_THRESHOLD` 未満は従来どおり「要確認」
- 0-9 のテンプレートが揃っていなければ `None`（Tesseract にフォールバック）
- テンプレートは `scripts/build_digit_templates.py`（ロジックは `evaluation/digit_templates.py`）が、サンプル画像と正解 CSV から作成する（Tesseract の読み取りが正解と一致したカードの桁だけを採用）。フォントや画面が変わった場合は作り直す

**`parser.py`** — 解釈と要確認判定

```python
@dataclass(frozen=True)
class ParsedCard:
    name: str
    level: int | None
    honor: int | None
    needs_review: bool
    review_reasons: list[str]
    min_confidence: float

def parse_card(name: OcrResult, level: OcrResult, honor: OcrResult, cfg: Config) -> ParsedCard:
    """カンマを除去して整数に変換する。変換できない場合は None とし
    parse_error_level / parse_error_honor を理由に付ける。
    信頼度が閾値未満なら low_confidence_name / _level / _honor を付ける。
    名前が空の場合は None を返しカードを破棄する。
    名前は、Tesseract(jpn) が文字間に入れる空白のうち、非 ASCII 文字に隣接するものを除去する
    （例: 「Henry へ ん り ー」→「Henryへんりー」）。"""
```

**エラー定義**（`errors.py` に集約。基底は `LiverStatisticsError`）

| 例外クラス | 発生条件 |
|---|---|
| `ImportDirectoryNotFoundError` | 取り込みフォルダが存在しない |
| `NoImagesFoundError` | 取り込みフォルダに画像が0枚 |
| `OcrEngineUnavailableError` | Tesseract 本体が見つからない |
| `ImageReadError` | 画像ファイルを開けない、または壊れている |
| `InputError` | CLI 引数・設定値が不正（日付の同時指定、出力先なし、未登録部族の出力など） |

### 5.4 `members/matcher.py`

```python
# normalize_name は normalize.py に置く（members/matcher.py からも参照できる）
def normalize_name(name: str) -> str:
    """NFKC 正規化 → 前後・内部の空白除去 → 大文字小文字を区別しない形（casefold）に変換。"""

def resolve_member(repo, tribe_id: int, name: str, threshold: float, edit_min_length: int) -> MatchResult:
    """name_key が members.name_key または member_aliases.alias_key と一致すれば既存メンバー。
    一致しなければ新規メンバーとする。新規の場合、同部族の既存メンバーと
    類似度（difflib の ratio）が閾値（既定 0.8）以上、または両者とも edit_min_length（既定 3）
    文字以上で編集距離 1 以内のものがあれば、similar_to:<既存名> を review_reason に付けて
    「要確認」とする（登録自体は行う）。短い名前（例: ぽこた/ぼこた）は 1 文字違いでも ratio が
    約 0.67 にしかならず閾値に届かないため、編集距離の条件を併用する。
    similar_to の review_reason への付与は pipeline.py が行う。"""
```

### 5.5 `db/`

```python
# connection.py
def connect(db_path: Path) -> sqlite3.Connection:
    """外部キー有効化、row_factory 設定。スキーマ（schema.sql）が無ければ作成する。"""

# repository.py
class Repository:
    def get_or_create_tribe(self, name: str) -> tuple[int, bool]: ...
    def find_tribe(self, name: str) -> int | None: ...
    def find_member(self, tribe_id: int, name_key: str) -> int | None:
        """name_key または別名（alias_key）が一致するメンバー ID。"""
    def list_member_keys(self, tribe_id: int) -> list[tuple[str, str]]: ...  # 類似名の判定用
    def create_member(self, tribe_id: int, name: str, name_key: str) -> int: ...
    def get_or_create_source_image(self, ...) -> int: ...
    def upsert_record(self, rec: RecordInput, on_conflict: Literal["skip", "overwrite"]) -> UpsertResult:
        """UpsertResult は inserted / overwritten / skipped のいずれか。"""
    def query_records(self, tribe: str, on_date: date | None = None, date_from: date | None = None,
                      date_to: date | None = None, member_key: str | None = None) -> list[RecordRow]: ...
```

- 競合時の動作は、`(member_id, record_date)` の既存行を `SELECT` で確認し、無ければ `INSERT`、あれば `skip` は何もせず、`overwrite` は `UPDATE` する。単一プロセス・単一トランザクションで動くため競合しない。最終的な重複防止は `UNIQUE (member_id, record_date)` 制約が担保する。
- トランザクションは `pipeline.py` で `with conn:` により管理する。

### 5.6 `pipeline.py`（統合レイヤー）

```python
@dataclass
class ImportSummary:
    images_total: int
    images_failed: list[str]
    images_no_cards: list[str]  # 例外は無いが、読み取れたカードが1枚も無かった画像
    inserted: int
    overwritten: int
    skipped: int
    needs_review: list[str]     # 対象ユーザ名

def run_import(directory: Path, tribe: str, record_date: date | None,
               on_conflict: Literal["skip", "overwrite"], cfg: Config,
               engine: OcrEngine | None = None) -> ImportSummary:
    """engine を省略すると TesseractEngine を生成する（テストでは差し替える）。
    画像ごとの処理に入る前に check_assets(cfg) でアイコン画像を確認し、
    設定・アセットの不備は画像単位の失敗にせず InputError で終了する。"""
```

### 5.7 `export/csv_exporter.py`

```python
def export_csv(rows: list[RecordRow], out_path: Path) -> int:
    """出力件数を返す。列: 部族名, 記録日, ユーザ名, レベル, 名誉, 要確認
    UTF-8 BOM 付き（表計算ソフトで文字化けしないため）。出力先が既存の場合は上書きする。"""
```

### 5.8 `cli.py`

| コマンド | 主なオプション | 終了コード |
|---|---|---|
| `liver-stats import` | `--dir`（必須）`--tribe`（必須）`--date`（任意、YYYY-MM-DD）`--on-conflict {skip,overwrite}`（既定 skip） | 0: 成功（失敗画像・カード未検出の画像があっても0。結果に表示。すべての画像で読み取れなかった場合は警告を表示）/ 1: 入力エラー / 2: 想定外エラー |
| `liver-stats export` | `--tribe`（必須）`--date` または `--from`/`--to`、`--member`（任意）、`--out`（必須） | 同上 |

- `--date` と `--from`/`--to` の同時指定、`--out` の親ディレクトリが存在しない場合は入力エラーとする。
- 出力結果の形式は PRD 6章の例に従う。

---

## 6. 設定管理

`config.py` および `.env` で以下を管理する。

```
# .env
DB_PATH=data/liver_statistics.db
LOG_LEVEL=INFO
OCR_LANG=jpn+eng
OCR_LAYOUT_PATH=config/ocr_layout.toml   # 任意
ICONS_DIR=assets/icons                  # 任意
DIGITS_DIR=assets/digits                # 任意
TESSERACT_CMD=              # 空の場合は PATH から探す
CONFIDENCE_THRESHOLD=60     # この値未満を要確認とする（0-100）
ICON_MATCH_THRESHOLD=0.7    # アイコン検出のマッチ率の閾値（0-1）
NAME_SIMILARITY_THRESHOLD=0.8
NAME_EDIT_MIN_LENGTH=3      # この文字数以上の名前は編集距離1でも類似名とみなす
TESSERACT_TIMEOUT_SEC=30    # Tesseract 1回の呼び出しのタイムアウト（秒）
NUMBER_OCR_LANG=eng         # 数値を Tesseract で読む際の言語（フォールバック時）
DIGIT_MAX_DISTANCE=0.30     # 桁テンプレートとの距離がこの値のとき信頼度0
TESSDATA_BEST_DIR=assets/tessdata_best  # 任意。jpn/eng の高精度モデルがあれば名前を2モデルで読む
NAME_DISAGREE_CONFIDENCE_CAP=55         # 2モデルが食い違ったときの信頼度の上限（CONFIDENCE_THRESHOLD より小さく。高精度モデルの有無にかかわらず検証する）
```

`LOG_LEVEL` は CLI 起動時に `logging` へ反映する。設定値は型に加えて範囲も検証し（例: `DIGIT_MAX_DISTANCE` / `TESSERACT_TIMEOUT_SEC` は 0 より大きい、`*_THRESHOLD` は範囲内、`NAME_EDIT_MIN_LENGTH` は 1 以上の整数）、不正なら `InputError` とする。CLI は `load_config()` を 1 回だけ呼び、結果を各コマンドに渡す。`digit_reader.py` の `_SCALE` などの切り出し定数は、テンプレートの正規化（`GLYPH_SIZE`）と一体のアルゴリズム内部値のため設定化しない。

画面レイアウトに依存する値（アイコン基準の領域比率）は `config/ocr_layout.toml` に置き、コードに直接記載しない。

---

## 7. ディレクトリ構成（実装対象）

```
liver-statistics/
├── pyproject.toml
├── .env.example
├── config/
│   └── ocr_layout.toml
├── assets/
│   ├── icons/                 # sword.png, star.png（サンプル画像から切り出し）
│   └── digits/                # 数値の桁テンプレート（0_00.png 等。build_digit_templates.py で作成）
├── data/                      # DB・生成物（git 管理外）
├── src/
│   ├── liver_statistics/
│   │   ├── __init__.py
│   │   ├── cli.py
│   │   ├── config.py
│   │   ├── errors.py          # 例外クラス
│   │   ├── normalize.py       # 名前の正規化（members / ocr から共通利用）
│   │   ├── pipeline.py
│   │   ├── ingest/
│   │   │   ├── scanner.py
│   │   │   └── captured_at.py
│   │   ├── evaluation/        # 正答率の測定・桁テンプレート作成のロジック（scripts から呼ぶ）
│   │   │   ├── accuracy.py
│   │   │   └── digit_templates.py
│   │   ├── ocr/
│   │   │   ├── card_detector.py   # 剣・星アイコンでカードを検出
│   │   │   ├── engine.py
│   │   │   ├── tesseract_engine.py
│   │   │   ├── name_choice.py     # 2モデルの名前の結果から採用するものを決める
│   │   │   ├── digit_reader.py    # 数値の桁テンプレート照合
│   │   │   └── parser.py
│   │   ├── members/
│   │   │   └── matcher.py
│   │   ├── db/
│   │   │   ├── connection.py
│   │   │   ├── schema.sql
│   │   │   └── repository.py
│   │   └── export/
│   │       └── csv_exporter.py
│   └── test/                  # TEST_REGULATION.md に従う
│       ├── TEST_POINT.md
│       └── src/{unit,integration}/
└── scripts/
    ├── evaluate_accuracy.py   # 正答率の測定（evaluation/accuracy.py を呼ぶ薄いスクリプト）
    └── build_digit_templates.py  # 桁テンプレートの作成（evaluation/digit_templates.py を呼ぶ）
```

### 正答率の測定（`scripts/evaluate_accuracy.py` → `evaluation/accuracy.py`）

- 入力: サンプル画像のフォルダと、運営者が作成した正解データ CSV（`ユーザ名, レベル, 名誉`）
- 処理: 画像を読み取り（DB には登録しない）、正解データとユーザ名で突き合わせる
- 出力: 項目単位（ユーザ名・レベル・名誉）の正解数／全項目数（PRD 5章の定義）、項目別の正答率、誤読の一覧
- 判定: 全体の正答率 70% 以上。測定対象はサンプル画像10枚程度・30人分（PRD 5章）
- ユーザ名の正解判定は、`normalize_name` 後の完全一致とする

---

## 8. 今後の拡張ポイント

| 拡張内容 | 対応モジュール |
|---|---|
| OCR エンジンの差し替え（精度が目標に届かない場合） | `ocr/engine.py` の別実装を追加。`config` でエンジンを選択 |
| 確認・修正画面、登録後データの訂正機能 | `pipeline.py` の登録前に確認ステップを挿入、`db/repository.py` に更新系を追加 |
| Web 画面からの画像アップロード | `ingest/` に入力経路を追加、`pipeline.py` を再利用 |
| 累計寄付値などの記録項目の追加 | `ocr/card_detector.py` に領域追加、`member_records` に列追加 |
| 別名の登録コマンド | `members/` と `cli.py` に追加（現状は DB 直接操作） |
| 複数管理者・外部公開 | 認証、DB を SQLite から RDBMS へ移行（ADR-003 を更新） |
