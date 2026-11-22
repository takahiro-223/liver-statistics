import pytest

from liver_statistics.errors import ImportDirectoryNotFoundError, NoImagesFoundError
from liver_statistics.ingest.scanner import list_images


def test_lists_only_images_sorted(tmp_path):
    for name in ["b.PNG", "a.jpg", "c.jpeg", "note.txt", ".hidden.png"]:
        (tmp_path / name).write_bytes(b"x")
    (tmp_path / "sub").mkdir()
    assert [p.name for p in list_images(tmp_path)] == ["a.jpg", "b.PNG", "c.jpeg"]


def test_missing_directory(tmp_path):
    with pytest.raises(ImportDirectoryNotFoundError):
        list_images(tmp_path / "none")


def test_no_images(tmp_path):
    (tmp_path / "note.txt").write_text("x")
    with pytest.raises(NoImagesFoundError):
        list_images(tmp_path)
