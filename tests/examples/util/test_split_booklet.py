"""Smoke + branch tests for :class:`SplitBooklet`."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from pypdfbox.examples.util.split_booklet import SplitBooklet
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage


def test_split_doubles_pages(make_pdf: Callable[..., Path], tmp_path: Path) -> None:
    src = make_pdf("booklet.pdf", page_count=2)
    dst = tmp_path / "split.pdf"
    SplitBooklet.split(str(src), str(dst))
    with PDDocument.load(str(dst)) as doc:
        # Each booklet page expands to two output pages.
        assert doc.get_number_of_pages() == 4


def test_constructor_is_callable() -> None:
    """Exercise the no-op ``__init__`` body (covers line 25)."""
    instance = SplitBooklet()
    assert isinstance(instance, SplitBooklet)


def test_main_too_few_args_exits_with_minus_one(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``main([])`` writes usage to stderr then ``raise SystemExit(-1)``
    (covers lines 30-34 + 97)."""
    with pytest.raises(SystemExit) as exc_info:
        SplitBooklet.main([])
    # SystemExit(-1) -> code == -1.
    assert exc_info.value.code == -1
    err = capsys.readouterr().err
    assert "Usage" in err


def test_main_one_arg_exits_with_minus_one(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        SplitBooklet.main(["only-one.pdf"])
    assert exc_info.value.code == -1
    assert "Usage" in capsys.readouterr().err


def test_main_with_none_argv_exits(capsys: pytest.CaptureFixture[str]) -> None:
    """``argv=None`` is normalised to an empty list (line 30)."""
    with pytest.raises(SystemExit):
        SplitBooklet.main(None)
    assert "Usage" in capsys.readouterr().err


def test_main_dispatches_to_split(monkeypatch, tmp_path: Path) -> None:
    seen: list[tuple[str, str]] = []

    def _stub(src: str, dst: str) -> None:
        seen.append((src, dst))

    monkeypatch.setattr(SplitBooklet, "split", staticmethod(_stub))
    SplitBooklet.main(["in.pdf", "out.pdf"])
    assert seen == [("in.pdf", "out.pdf")]


def test_usage_writes_to_stderr(capsys: pytest.CaptureFixture[str]) -> None:
    """Direct call to the helper covers line 97 without going through main."""
    SplitBooklet.usage()
    err = capsys.readouterr().err
    assert "Usage: SplitBooklet" in err
    assert "input-pdf" in err


def _build_rotated_pdf(path: Path, *, rotation: int, page_count: int = 1) -> None:
    """Helper: build a PDF where every page has the given /Rotate."""
    with PDDocument() as doc:
        for _ in range(page_count):
            page = PDPage()
            page.set_rotation(rotation)
            doc.add_page(page)
        doc.save(str(path))


def test_split_handles_rotation_90(tmp_path: Path) -> None:
    """Rotation 90 → the horizontal-split branch (lines 60-64) fires."""
    src = tmp_path / "rot90.pdf"
    dst = tmp_path / "rot90-split.pdf"
    _build_rotated_pdf(src, rotation=90, page_count=1)
    SplitBooklet.split(str(src), str(dst))
    with PDDocument.load(str(dst)) as doc:
        assert doc.get_number_of_pages() == 2


def test_split_handles_rotation_180(tmp_path: Path) -> None:
    """Rotation 180 → right-then-left ordering branch (lines 79-82)."""
    src = tmp_path / "rot180.pdf"
    dst = tmp_path / "rot180-split.pdf"
    _build_rotated_pdf(src, rotation=180, page_count=1)
    SplitBooklet.split(str(src), str(dst))
    with PDDocument.load(str(dst)) as doc:
        assert doc.get_number_of_pages() == 2


def test_split_handles_rotation_270(tmp_path: Path) -> None:
    """Rotation 270 → both branches (60-64 + 79-82) fire on the same page."""
    src = tmp_path / "rot270.pdf"
    dst = tmp_path / "rot270-split.pdf"
    _build_rotated_pdf(src, rotation=270, page_count=1)
    SplitBooklet.split(str(src), str(dst))
    with PDDocument.load(str(dst)) as doc:
        assert doc.get_number_of_pages() == 2
