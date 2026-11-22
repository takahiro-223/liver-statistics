import cv2
import numpy as np

from liver_statistics.ocr.digit_reader import read_digits, segment


def render(text: str) -> np.ndarray:
    """灰色の背景に黒い文字を描いた画像（実画像のカード領域を模す）。"""
    img = np.full((60, 40 * len(text) + 20, 3), 225, np.uint8)
    cv2.putText(img, text, (10, 45), cv2.FONT_HERSHEY_SIMPLEX, 1.6, (20, 20, 20), 3, cv2.LINE_AA)
    return img


def make_templates() -> dict[str, np.ndarray]:
    glyphs = [g for g in segment(render("0123456789")) if g is not None]
    return {str(i): np.stack([g]) for i, g in enumerate(glyphs)}


def test_reads_digits_and_commas():
    result = read_digits(render("9,081,726"), make_templates())
    assert result is not None
    assert result.text == "9,081,726"
    assert result.confidence > 60


def test_repeated_digits_are_not_merged():
    # Tesseract が「44」を 1 桁に潰す問題の再発防止
    result = read_digits(render("449,448"), make_templates())
    assert result is not None and result.text == "449,448"


def test_segment_marks_comma_as_none():
    glyphs = segment(render("1,2"))
    assert [g is None for g in glyphs] == [False, True, False]


def test_returns_none_when_unreadable():
    templates = make_templates()
    assert read_digits(np.full((40, 200, 3), 225, np.uint8), templates) is None  # 文字なし
    assert read_digits(render("123"), {}) is None                                # テンプレートなし
    assert read_digits(render("123"), {"1": templates["1"]}) is None             # 0-9 が揃っていない
