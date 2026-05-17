"""Branch tests for :class:`GoToSecondBookmarkOnOpen`.

The base smoke tests live in ``test_loader_examples.py``; this module
covers the remaining branches (encryption guard, page-count guard,
happy path with a real two-bookmark outline).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.examples.pdmodel.go_to_second_bookmark_on_open import (
    GoToSecondBookmarkOnOpen,
)
from pypdfbox.pdmodel.interactive.documentnavigation.destination import (
    pd_page_fit_width_destination as _fitwidth,
)
from pypdfbox.pdmodel.interactive.documentnavigation.outline import (
    pd_document_outline as _outline,
)
from pypdfbox.pdmodel.interactive.documentnavigation.outline import (
    pd_outline_item as _outline_item,
)
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage

PDPageFitWidthDestination = _fitwidth.PDPageFitWidthDestination
PDDocumentOutline = _outline.PDDocumentOutline
PDOutlineItem = _outline_item.PDOutlineItem


def test_constructor_is_callable() -> None:
    """Exercise the no-op ``__init__`` (line 19)."""
    instance = GoToSecondBookmarkOnOpen()
    assert isinstance(instance, GoToSecondBookmarkOnOpen)


def test_main_one_arg_prints_usage(capsys: pytest.CaptureFixture[str]) -> None:
    """Single positional arg -> usage helper; no further work."""
    # `usage` is called for argv != 2 elements (returns quietly).
    GoToSecondBookmarkOnOpen.main(["only-one"])
    err = capsys.readouterr().err
    assert "Usage" in err


def test_main_three_args_prints_usage(capsys: pytest.CaptureFixture[str]) -> None:
    GoToSecondBookmarkOnOpen.main(["a", "b", "c"])
    assert "Usage" in capsys.readouterr().err


def _make_two_page_pdf_with_outline(path: Path) -> None:
    """Build a PDF with two pages and a two-item top-level outline."""
    with PDDocument() as doc:
        page_a = PDPage()
        page_b = PDPage()
        doc.add_page(page_a)
        doc.add_page(page_b)
        outline = PDDocumentOutline()
        doc.get_document_catalog().set_document_outline(outline)
        # First bookmark targets page A.
        first = PDOutlineItem()
        first.set_title("First")
        first_dest = PDPageFitWidthDestination()
        first_dest.set_page(page_a)
        first.set_destination(first_dest)
        outline.add_last(first)
        # Second bookmark targets page B — this is the one main() picks.
        second = PDOutlineItem()
        second.set_title("Second")
        second_dest = PDPageFitWidthDestination()
        second_dest.set_page(page_b)
        second.set_destination(second_dest)
        outline.add_last(second)
        doc.save(str(path))


def test_main_sets_open_action_to_second_bookmark(tmp_path: Path) -> None:
    """Happy path: pages>=2 + 2-bookmark outline -> open action is set."""
    src = tmp_path / "in.pdf"
    dst = tmp_path / "out.pdf"
    _make_two_page_pdf_with_outline(src)
    GoToSecondBookmarkOnOpen.main([str(src), str(dst)])
    assert dst.exists()
    assert dst.read_bytes()[:4] == b"%PDF"
    # The output PDF should now carry an /OpenAction in the catalog.
    with PDDocument.load(str(dst)) as out_doc:
        catalog = out_doc.get_document_catalog()
        assert catalog.get_open_action() is not None


def test_main_raises_when_under_two_pages(tmp_path: Path) -> None:
    """Single-page document trips the page-count guard (line 36)."""
    src = tmp_path / "single.pdf"
    dst = tmp_path / "out.pdf"
    with PDDocument() as doc:
        doc.add_page(PDPage())
        doc.save(str(src))
    with pytest.raises(OSError, match="at least 2 pages"):
        GoToSecondBookmarkOnOpen.main([str(src), str(dst)])


def test_main_encrypted_document_exits(tmp_path: Path, monkeypatch) -> None:
    """``document.is_encrypted()`` -> stderr write + ``SystemExit(1)``."""
    src = tmp_path / "enc.pdf"
    dst = tmp_path / "out.pdf"
    _make_two_page_pdf_with_outline(src)
    # Patch ``is_encrypted`` at the class level — a real encrypted PDF
    # would require running the full encryption pipeline which is out of
    # scope for this branch test.
    monkeypatch.setattr(PDDocument, "is_encrypted", lambda self: True)
    with pytest.raises(SystemExit) as exc_info:
        GoToSecondBookmarkOnOpen.main([str(src), str(dst)])
    assert exc_info.value.code == 1
