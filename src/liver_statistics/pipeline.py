"""統合レイヤー: 取り込み全工程とトランザクション境界を担う。"""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field, replace
from datetime import date, datetime
from pathlib import Path

from .config import Config
from .db.connection import connect
from .db.repository import OnConflict, RecordInput, Repository
from .errors import ImageReadError
from .ingest.captured_at import resolve_record_date
from .ingest.scanner import list_images
from .members.matcher import resolve_member
from .normalize import normalize_name
from .ocr.card_detector import check_assets, detect_cards, load_image
from .ocr.engine import OcrEngine
from .ocr.parser import ParsedCard, parse_card

logger = logging.getLogger(__name__)


@dataclass
class ImportSummary:
    images_total: int = 0
    images_failed: list[str] = field(default_factory=list)
    images_no_cards: list[str] = field(default_factory=list)  # 読み取れたカードが1枚も無かった画像
    inserted: int = 0
    overwritten: int = 0
    skipped: int = 0
    needs_review: list[str] = field(default_factory=list)  # 対象ユーザ名


@dataclass(frozen=True)
class _Extracted:
    record_date: date
    image_path: Path
    captured_at: datetime
    card: ParsedCard


def read_cards(image_path: Path, engine: OcrEngine, cfg: Config) -> list[ParsedCard]:
    """1枚の画像からメンバーカードを読み取る（DB には触れない）。"""
    image = load_image(image_path)
    cards: list[ParsedCard] = []
    for regions in detect_cards(image, cfg):
        parsed = parse_card(
            engine.read_name(regions.name.crop(image)),
            engine.read_number(regions.level.crop(image)),
            engine.read_number(regions.honor.crop(image)),
            cfg,
        )
        if parsed is not None:
            cards.append(parsed)
    return cards


def merge_duplicates(items: list[_Extracted]) -> list[_Extracted]:
    """同一（記録日, 正規化名）を1件にまとめる。

    信頼度が最も高いものを採用し、値が画像間で異なる場合は要確認にする（EDD 3.2）。
    """
    groups: dict[tuple[date, str], list[_Extracted]] = {}
    for item in items:
        groups.setdefault((item.record_date, normalize_name(item.card.name)), []).append(item)
    merged: list[_Extracted] = []
    for group in groups.values():
        best = max(group, key=lambda e: e.card.min_confidence)
        conflict = any((e.card.level, e.card.honor) != (best.card.level, best.card.honor) for e in group)
        if conflict:
            reasons = best.card.review_reasons + ["conflict_between_images"]
            best = replace(best, card=replace(best.card, needs_review=True, review_reasons=reasons))
        merged.append(best)
    return merged


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_import(
    directory: Path, tribe: str, record_date: date | None, on_conflict: OnConflict,
    cfg: Config, engine: OcrEngine | None = None,
) -> ImportSummary:
    """フォルダ内の画像を読み取り、1トランザクションで登録する。"""
    images = list_images(directory)
    check_assets(cfg)  # アイコン不備は画像単位の失敗にせず、ここで入力エラーとして止める
    if engine is None:
        from .ocr.tesseract_engine import TesseractEngine  # 重い初期化は必要時のみ
        engine = TesseractEngine(cfg)

    summary = ImportSummary(images_total=len(images))
    extracted: list[_Extracted] = []
    for path in images:
        try:
            rec_date, captured = resolve_record_date(path, record_date)
            cards = read_cards(path, engine, cfg)
            if not cards:
                logger.debug("メンバーのカードを検出できませんでした: %s", path.name)  # 実行結果に表示するのでログは DEBUG
                summary.images_no_cards.append(path.name)
            for card in cards:
                extracted.append(_Extracted(rec_date, path, captured, card))
        except ImageReadError as exc:
            logger.warning("画像の処理に失敗しました: %s", exc)
            summary.images_failed.append(path.name)
        except Exception as exc:  # noqa: BLE001 - 1枚の失敗で全体を止めず、失敗画像として報告する
            logger.warning("画像の処理中に想定外のエラー: %s: %s", path.name, exc)
            summary.images_failed.append(path.name)

    if not extracted:
        return summary  # 登録するカードが無ければ DB に触れない（空の部族も作らない）

    conn = connect(cfg.db_path)
    try:
        with conn:  # 例外時はロールバック
            repo = Repository(conn)
            tribe_id, _created = repo.get_or_create_tribe(tribe)
            image_ids: dict[Path, int] = {}
            for item in merge_duplicates(extracted):
                if item.image_path not in image_ids:
                    image_ids[item.image_path] = repo.get_or_create_source_image(
                        tribe_id, item.image_path.name, str(item.image_path.resolve()),
                        _sha256(item.image_path), item.captured_at,
                    )
                card = item.card
                reasons = list(card.review_reasons)
                match = resolve_member(
                    repo, tribe_id, card.name, cfg.name_similarity_threshold, cfg.name_edit_min_length
                )
                if match.member_id is None:
                    member_id = repo.create_member(tribe_id, card.name, match.name_key)
                    if match.similar_to:
                        reasons.append(f"similar_to:{match.similar_to}")
                else:
                    member_id = match.member_id
                needs_review = bool(reasons)
                result = repo.upsert_record(
                    RecordInput(
                        member_id=member_id, record_date=item.record_date,
                        level=card.level, honor=card.honor, needs_review=needs_review,
                        review_reason=",".join(reasons) or None,
                        source_image_id=image_ids[item.image_path],
                    ),
                    on_conflict,
                )
                if result == "inserted":
                    summary.inserted += 1
                elif result == "overwritten":
                    summary.overwritten += 1
                else:
                    summary.skipped += 1
                if needs_review and result != "skipped":
                    summary.needs_review.append(card.name)
    finally:
        conn.close()
    return summary
