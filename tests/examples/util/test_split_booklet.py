"""Smoke test for :class:`SplitBooklet`."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from pypdfbox.examples.util.split_booklet import SplitBooklet
from pypdfbox.pdmodel.pd_document import PDDocument


def test_split_doubles_pages(make_pdf: Callable[..., Path], tmp_path: Path) -> None:
    src = make_pdf("booklet.pdf", page_count=2)
    dst = tmp_path / "split.pdf"
    SplitBooklet.split(str(src), str(dst))
    with PDDocument.load(str(dst)) as doc:
        # Each booklet page expands to two output pages.
        assert doc.get_number_of_pages() == 4
