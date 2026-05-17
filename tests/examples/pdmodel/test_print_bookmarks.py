"""Coverage tests for :class:`PrintBookmarks` example."""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSString
from pypdfbox.examples.pdmodel.print_bookmarks import PrintBookmarks
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.interactive.action.pd_action_go_to import PDActionGoTo
from pypdfbox.pdmodel.interactive.action.pd_action_launch import PDActionLaunch
from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_named_destination import (
    PDNamedDestination,
)
from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_page_fit_destination import (
    PDPageFitDestination,
)
from pypdfbox.pdmodel.interactive.documentnavigation.outline.pd_document_outline import (
    PDDocumentOutline,
)
from pypdfbox.pdmodel.interactive.documentnavigation.outline.pd_outline_item import (
    PDOutlineItem,
)

# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------


def _make_item(title: str, page_index: int) -> PDOutlineItem:
    item = PDOutlineItem()
    item.set_title(title)
    dest = PDPageFitDestination()
    dest.set_page_number(page_index)
    item.set_destination(dest)
    return item


def _build_outline_pdf(path: Path) -> Path:
    """Three-page PDF with a two-level outline tree."""
    doc = PDDocument()
    try:
        for _ in range(3):
            doc.add_page(PDPage(PDRectangle(0.0, 0.0, 612.0, 792.0)))

        outline = PDDocumentOutline()
        doc.get_document_catalog().set_document_outline(outline)

        chapter1 = _make_item("Chapter 1", 0)
        outline.add_last(chapter1)

        section_11 = _make_item("Section 1.1", 1)
        chapter1.add_last(section_11)

        chapter2 = _make_item("Chapter 2", 2)
        outline.add_last(chapter2)

        doc.save(path)
    finally:
        doc.close()
    return path


def _build_named_destination_pdf(path: Path) -> Path:
    """Outline whose single item targets a named destination."""
    doc = PDDocument()
    try:
        for _ in range(3):
            doc.add_page(PDPage(PDRectangle(0.0, 0.0, 612.0, 792.0)))

        named_page = PDPageFitDestination()
        named_page.set_page_number(2)
        names_array = COSArray()
        names_array.add(COSString("named-chapter"))
        names_array.add(named_page.get_cos_object())
        dests = COSDictionary()
        dests.set_item(COSName.get_pdf_name("Names"), names_array)
        names = COSDictionary()
        names.set_item(COSName.get_pdf_name("Dests"), dests)
        doc.get_document_catalog().get_cos_object().set_item(
            COSName.get_pdf_name("Names"), names
        )

        outline = PDDocumentOutline()
        doc.get_document_catalog().set_document_outline(outline)
        item = PDOutlineItem()
        item.set_title("Named Chapter")
        item.set_destination(PDNamedDestination("named-chapter"))
        outline.add_last(item)

        doc.save(path)
    finally:
        doc.close()
    return path


def _build_empty_pdf(path: Path) -> Path:
    doc = PDDocument()
    try:
        doc.add_page(PDPage(PDRectangle(0.0, 0.0, 612.0, 792.0)))
        doc.save(path)
    finally:
        doc.close()
    return path


# ---------------------------------------------------------------------------
# main() — usage + driver paths
# ---------------------------------------------------------------------------


def test_main_with_no_args_prints_usage(
    capsys: pytest.CaptureFixture[str],
) -> None:
    PrintBookmarks.main(None)
    err = capsys.readouterr().err
    assert "Usage: PrintBookmarks" in err


def test_main_with_too_many_args_prints_usage(
    capsys: pytest.CaptureFixture[str],
) -> None:
    PrintBookmarks.main(["a", "b"])
    err = capsys.readouterr().err
    assert "Usage: PrintBookmarks" in err


def test_main_emits_no_bookmarks_message_when_outline_absent(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    pdf = _build_empty_pdf(tmp_path / "plain.pdf")
    PrintBookmarks.main([str(pdf)])
    out = capsys.readouterr().out
    assert out == "This document does not contain any bookmarks\n"


def test_main_walks_outline_tree(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    pdf = _build_outline_pdf(tmp_path / "outline.pdf")
    PrintBookmarks.main([str(pdf)])
    out = capsys.readouterr().out
    # Top-level items at indent 0; child indented 4 spaces.
    assert "Chapter 1\n" in out
    assert "    Section 1.1\n" in out
    assert "Chapter 2\n" in out
    # Destination pages are 1-based.
    assert "Destination page: 1" in out
    assert "Destination page: 2" in out
    assert "Destination page: 3" in out


def test_main_resolves_named_destination(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    pdf = _build_named_destination_pdf(tmp_path / "named.pdf")
    PrintBookmarks.main([str(pdf)])
    out = capsys.readouterr().out
    # Named destination resolves to page 3 (1-based).
    assert "Destination page: 3" in out
    assert "Named Chapter\n" in out


# ---------------------------------------------------------------------------
# print_bookmark() — action handling branches
# ---------------------------------------------------------------------------


def test_print_bookmark_handles_gotoaction_with_page_destination(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A GoTo action carrying an explicit PDPageDestination should print
    the resolved 1-based page number."""
    doc = PDDocument()
    try:
        page0 = PDPage(PDRectangle(0.0, 0.0, 612.0, 792.0))
        page1 = PDPage(PDRectangle(0.0, 0.0, 612.0, 792.0))
        doc.add_page(page0)
        doc.add_page(page1)

        outline = PDDocumentOutline()
        doc.get_document_catalog().set_document_outline(outline)

        item = PDOutlineItem()
        item.set_title("Goto Action Item")
        # NB: only ``set_action`` (no ``set_destination``) so the
        # action-handling branches fire.
        action = PDActionGoTo()
        dest = PDPageFitDestination()
        dest.set_page(page1)  # bind to a real page dictionary
        action.set_destination(dest)
        item.set_action(action)
        outline.add_last(item)

        PrintBookmarks().print_bookmark(doc, outline, "")
    finally:
        doc.close()
    out = capsys.readouterr().out
    assert "Destination page: 2\n" in out
    assert "Goto Action Item\n" in out


def test_print_bookmark_handles_gotoaction_with_named_destination(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A GoTo action whose ``/D`` entry is a name string surfaces as a
    plain ``str`` from ``get_destination`` — neither PDPageDestination
    nor PDNamedDestination — landing in the action-class fallback."""
    doc = PDDocument()
    try:
        doc.add_page(PDPage(PDRectangle(0.0, 0.0, 612.0, 792.0)))

        outline = PDDocumentOutline()
        doc.get_document_catalog().set_document_outline(outline)

        item = PDOutlineItem()
        item.set_title("Goto Named")
        action = PDActionGoTo()
        action.set_named_destination("hello")  # /D becomes a COSString
        item.set_action(action)
        outline.add_last(item)

        PrintBookmarks().print_bookmark(doc, outline, "")
    finally:
        doc.close()
    out = capsys.readouterr().out
    # The str branch is neither PDPageDestination nor PDNamedDestination, so
    # the helper logs the action-dest's class (which is ``str``).
    assert "Destination class: str\n" in out
    assert "Goto Named\n" in out


def test_print_bookmark_handles_non_goto_action(
    capsys: pytest.CaptureFixture[str],
) -> None:
    doc = PDDocument()
    try:
        doc.add_page(PDPage(PDRectangle(0.0, 0.0, 612.0, 792.0)))

        outline = PDDocumentOutline()
        doc.get_document_catalog().set_document_outline(outline)

        item = PDOutlineItem()
        item.set_title("Launcher")
        item.set_action(PDActionLaunch())
        outline.add_last(item)

        PrintBookmarks().print_bookmark(doc, outline, "")
    finally:
        doc.close()
    out = capsys.readouterr().out
    assert "Action class: PDActionLaunch\n" in out
    assert "Launcher\n" in out


def test_print_bookmark_handles_goto_action_with_absent_destination(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A GoTo action whose ``/D`` is absent returns ``None`` from
    ``get_destination`` — falls into the ``Destination class`` branch
    with ``NoneType`` as the recorded class name."""
    doc = PDDocument()
    try:
        doc.add_page(PDPage(PDRectangle(0.0, 0.0, 612.0, 792.0)))

        outline = PDDocumentOutline()
        doc.get_document_catalog().set_document_outline(outline)

        item = PDOutlineItem()
        item.set_title("Empty GoTo")
        item.set_action(PDActionGoTo())  # no /D
        outline.add_last(item)

        PrintBookmarks().print_bookmark(doc, outline, "")
    finally:
        doc.close()
    out = capsys.readouterr().out
    assert "Destination class: NoneType\n" in out
    assert "Empty GoTo\n" in out


def test_print_bookmark_handles_named_destination_at_item_level(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """An outline item whose ``/Dest`` is itself a named destination
    (no action) reaches the ``find_named_destination_page`` branch
    in ``print_bookmark``."""
    doc = PDDocument()
    try:
        for _ in range(3):
            doc.add_page(PDPage(PDRectangle(0.0, 0.0, 612.0, 792.0)))

        # /Names /Dests for the lookup.
        named_page = PDPageFitDestination()
        named_page.set_page_number(1)
        names_array = COSArray()
        names_array.add(COSString("named-x"))
        names_array.add(named_page.get_cos_object())
        dests = COSDictionary()
        dests.set_item(COSName.get_pdf_name("Names"), names_array)
        names = COSDictionary()
        names.set_item(COSName.get_pdf_name("Dests"), dests)
        doc.get_document_catalog().get_cos_object().set_item(
            COSName.get_pdf_name("Names"), names
        )

        outline = PDDocumentOutline()
        doc.get_document_catalog().set_document_outline(outline)

        item = PDOutlineItem()
        item.set_title("Named Item")
        item.set_destination(PDNamedDestination("named-x"))
        outline.add_last(item)

        PrintBookmarks().print_bookmark(doc, outline, "")
    finally:
        doc.close()
    out = capsys.readouterr().out
    assert "Destination page: 2\n" in out
    assert "Named Item\n" in out


def test_usage_writes_to_stderr(
    capsys: pytest.CaptureFixture[str],
) -> None:
    PrintBookmarks.usage()
    err = capsys.readouterr().err
    assert err == "Usage: PrintBookmarks <input-pdf>\n"
