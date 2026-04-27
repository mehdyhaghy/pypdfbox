"""Tests for ``pypdfbox listbookmarks`` and the ``list_bookmarks`` helper."""
from __future__ import annotations

import io
from pathlib import Path

import pytest

from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_page_fit_destination import (
    PDPageFitDestination,
)
from pypdfbox.pdmodel.interactive.documentnavigation.outline.pd_document_outline import (
    PDDocumentOutline,
)
from pypdfbox.pdmodel.interactive.documentnavigation.outline.pd_outline_item import (
    PDOutlineItem,
)
from pypdfbox.tools import cli
from pypdfbox.tools.listbookmarks import list_bookmarks


# ----------------------------------------------------------------- helpers


def _build_outline_pdf(path: Path) -> Path:
    """Build a small PDF with a 3-level outline tree:

        Chapter 1
            Section 1.1
                Subsection 1.1.1
            Section 1.2
        Chapter 2

    Each item targets a different page so we can verify page-number
    resolution as well as titles + indentation.
    """
    doc = PDDocument()
    try:
        for _ in range(4):
            doc.add_page(PDPage(PDRectangle(0.0, 0.0, 612.0, 792.0)))

        outline = PDDocumentOutline()
        doc.get_document_catalog().set_document_outline(outline)

        def _make_item(title: str, page_index: int) -> PDOutlineItem:
            item = PDOutlineItem()
            item.set_title(title)
            dest = PDPageFitDestination()
            dest.set_page_number(page_index)
            item.set_destination(dest)
            return item

        chapter1 = _make_item("Chapter 1", 0)
        outline.add_last(chapter1)

        section_11 = _make_item("Section 1.1", 1)
        chapter1.add_last(section_11)

        subsection_111 = _make_item("Subsection 1.1.1", 1)
        section_11.add_last(subsection_111)

        section_12 = _make_item("Section 1.2", 2)
        chapter1.add_last(section_12)

        chapter2 = _make_item("Chapter 2", 3)
        outline.add_last(chapter2)

        doc.save(path)
    finally:
        doc.close()
    return path


def _build_empty_outline_pdf(path: Path) -> Path:
    """One-page PDF with no outline at all."""
    doc = PDDocument()
    try:
        doc.add_page(PDPage(PDRectangle(0.0, 0.0, 612.0, 792.0)))
        doc.save(path)
    finally:
        doc.close()
    return path


# --------------------------------------------------------------- list_bookmarks helper


def test_list_bookmarks_helper_writes_tree(tmp_path: Path) -> None:
    pdf = _build_outline_pdf(tmp_path / "outline.pdf")
    buf = io.StringIO()
    with PDDocument.load(pdf) as doc:
        list_bookmarks(doc, buf, format="tree")
    text = buf.getvalue()
    # All five titles appear.
    for title in (
        "Chapter 1", "Section 1.1", "Subsection 1.1.1", "Section 1.2",
        "Chapter 2",
    ):
        assert title in text, f"missing title: {title}"
    # Indentation: top-level titles start at column 0, sections at 4
    # spaces, subsection at 8 spaces. Match against fully composed lines
    # so a stray leading-space change here would catch it.
    assert "Chapter 1\n" in text
    assert "    Section 1.1\n" in text
    assert "        Subsection 1.1.1\n" in text
    assert "    Section 1.2\n" in text
    assert "Chapter 2\n" in text


def test_list_bookmarks_helper_emits_destination_pages(tmp_path: Path) -> None:
    pdf = _build_outline_pdf(tmp_path / "outline.pdf")
    buf = io.StringIO()
    with PDDocument.load(pdf) as doc:
        list_bookmarks(doc, buf, format="tree")
    text = buf.getvalue()
    # Page numbers are 1-based per upstream PrintBookmarks
    # (``retrievePageNumber() + 1``). Chapter 1 → page 1; Chapter 2 → 4.
    assert "Destination page: 1" in text
    assert "Destination page: 2" in text
    assert "Destination page: 3" in text
    assert "Destination page: 4" in text


def test_list_bookmarks_helper_flat_format(tmp_path: Path) -> None:
    pdf = _build_outline_pdf(tmp_path / "outline.pdf")
    buf = io.StringIO()
    with PDDocument.load(pdf) as doc:
        list_bookmarks(doc, buf, format="flat")
    text = buf.getvalue()
    # No indentation in flat mode.
    assert "Chapter 1 -> page 1\n" in text
    assert "Section 1.1 -> page 2\n" in text
    assert "Subsection 1.1.1 -> page 2\n" in text
    assert "Section 1.2 -> page 3\n" in text
    assert "Chapter 2 -> page 4\n" in text
    # Each non-blank line should have no leading whitespace.
    for line in text.splitlines():
        if line:
            assert not line.startswith(" "), f"flat line has indent: {line!r}"


def test_list_bookmarks_helper_no_outline(tmp_path: Path) -> None:
    pdf = _build_empty_outline_pdf(tmp_path / "plain.pdf")
    buf = io.StringIO()
    with PDDocument.load(pdf) as doc:
        list_bookmarks(doc, buf, format="tree")
    assert buf.getvalue() == "This document does not contain any bookmarks\n"


# --------------------------------------------------------------- CLI


def test_listbookmarks_cli_tree_default(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    pdf = _build_outline_pdf(tmp_path / "outline.pdf")
    rc = cli.run_cli(["listbookmarks", str(pdf)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Chapter 1\n" in out
    assert "    Section 1.1\n" in out
    assert "        Subsection 1.1.1\n" in out
    assert "Chapter 2\n" in out


def test_listbookmarks_cli_flat_format(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    pdf = _build_outline_pdf(tmp_path / "outline.pdf")
    rc = cli.run_cli(["listbookmarks", str(pdf), "-format", "flat"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Chapter 1 -> page 1" in out
    assert "Section 1.1 -> page 2" in out
    assert "    " not in out  # no indentation anywhere in flat mode


def test_listbookmarks_cli_no_outline_message(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    pdf = _build_empty_outline_pdf(tmp_path / "plain.pdf")
    rc = cli.run_cli(["listbookmarks", str(pdf)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "This document does not contain any bookmarks" in out


def test_listbookmarks_cli_missing_file_returns_4(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    missing = tmp_path / "nope.pdf"
    rc = cli.run_cli(["listbookmarks", str(missing)])
    assert rc == 4
    assert "not a file" in capsys.readouterr().out
