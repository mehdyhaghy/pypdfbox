"""Sanity tests for examples whose main reads an input PDF.

Each builds a small input PDF on the fly, then exercises ``main()`` and
asserts the output PDF is produced or the expected output is emitted.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.examples.pdmodel.add_message_to_each_page import AddMessageToEachPage
from pypdfbox.examples.pdmodel.create_blank_pdf import CreateBlankPDF
from pypdfbox.examples.pdmodel.create_bookmarks import CreateBookmarks
from pypdfbox.examples.pdmodel.go_to_second_bookmark_on_open import (
    GoToSecondBookmarkOnOpen,
)
from pypdfbox.examples.pdmodel.hello_world import HelloWorld
from pypdfbox.examples.pdmodel.print_bookmarks import PrintBookmarks
from pypdfbox.examples.pdmodel.print_document_meta_data import PrintDocumentMetaData
from pypdfbox.examples.pdmodel.remove_first_page import RemoveFirstPage
from pypdfbox.examples.pdmodel.replace_urls import ReplaceURLs
from pypdfbox.examples.pdmodel.rubber_stamp import RubberStamp


def _make_two_page_pdf(path: Path) -> None:
    from pypdfbox.pdmodel.pd_document import PDDocument
    from pypdfbox.pdmodel.pd_page import PDPage

    with PDDocument() as doc:
        doc.add_page(PDPage())
        doc.add_page(PDPage())
        doc.save(str(path))


def _make_one_page_pdf(path: Path) -> None:
    CreateBlankPDF.main([str(path)])


def _make_hello_pdf(path: Path) -> None:
    HelloWorld.main([str(path), "Hello!"])


def _assert_is_pdf(path: Path) -> None:
    assert path.exists()
    assert path.read_bytes()[:4] == b"%PDF"


def test_remove_first_page_main(tmp_path: Path) -> None:
    src = tmp_path / "in.pdf"
    dst = tmp_path / "out.pdf"
    _make_two_page_pdf(src)
    RemoveFirstPage.main([str(src), str(dst)])
    _assert_is_pdf(dst)


def test_remove_first_page_single_page_raises(tmp_path: Path) -> None:
    src = tmp_path / "in.pdf"
    dst = tmp_path / "out.pdf"
    _make_one_page_pdf(src)
    with pytest.raises(OSError):
        RemoveFirstPage.main([str(src), str(dst)])


def test_remove_first_page_usage(tmp_path: Path) -> None:
    del tmp_path
    # Upstream returns quietly after printing usage.
    RemoveFirstPage.main([])


def test_add_message_to_each_page_main(tmp_path: Path) -> None:
    src = tmp_path / "in.pdf"
    dst = tmp_path / "out.pdf"
    _make_hello_pdf(src)
    AddMessageToEachPage.main([str(src), "DRAFT", str(dst)])
    _assert_is_pdf(dst)


def test_add_message_to_each_page_usage(tmp_path: Path) -> None:
    del tmp_path
    AddMessageToEachPage.main([])


def test_create_bookmarks_main(tmp_path: Path) -> None:
    src = tmp_path / "in.pdf"
    dst = tmp_path / "out.pdf"
    _make_two_page_pdf(src)
    CreateBookmarks.main([str(src), str(dst)])
    _assert_is_pdf(dst)


def test_create_bookmarks_usage() -> None:
    CreateBookmarks.main([])


def test_go_to_second_bookmark_requires_outline(tmp_path: Path) -> None:
    """Upstream raises ``IOException`` when the document has no outline."""
    src = tmp_path / "in.pdf"
    dst = tmp_path / "out.pdf"
    _make_two_page_pdf(src)
    with pytest.raises(OSError):
        GoToSecondBookmarkOnOpen.main([str(src), str(dst)])


def test_go_to_second_bookmark_usage() -> None:
    GoToSecondBookmarkOnOpen.main([])


def test_print_document_meta_data_main(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    src = tmp_path / "in.pdf"
    _make_one_page_pdf(src)
    PrintDocumentMetaData.main([str(src)])
    out = capsys.readouterr().out
    assert "Page Count=" in out


def test_print_document_meta_data_usage() -> None:
    PrintDocumentMetaData.main([])


def test_print_bookmarks_no_outline(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    src = tmp_path / "in.pdf"
    _make_one_page_pdf(src)
    PrintBookmarks.main([str(src)])
    out = capsys.readouterr().out
    assert "does not contain any bookmarks" in out


def test_print_bookmarks_usage() -> None:
    PrintBookmarks.main([])


def test_replace_urls_no_links_is_noop(tmp_path: Path) -> None:
    """ReplaceURLs is a no-op on a PDF with no link annotations."""
    src = tmp_path / "in.pdf"
    dst = tmp_path / "out.pdf"
    _make_one_page_pdf(src)
    ReplaceURLs.main([str(src), str(dst)])
    _assert_is_pdf(dst)


def test_replace_urls_usage() -> None:
    ReplaceURLs.main([])


def test_rubber_stamp_main(tmp_path: Path) -> None:
    src = tmp_path / "in.pdf"
    dst = tmp_path / "out.pdf"
    _make_one_page_pdf(src)
    RubberStamp.main([str(src), str(dst)])
    _assert_is_pdf(dst)


def test_rubber_stamp_usage() -> None:
    RubberStamp.main([])
