"""Tests for ``pypdfbox.examples.printing.printing``."""
from __future__ import annotations

import pytest

from pypdfbox.examples.printing.printing import Printing
from pypdfbox.printing.pdf_pageable import PDFPageable
from pypdfbox.printing.pdf_printable import PDFPrintable


class _FakeDocument:
    """Stand-in for :class:`PDDocument` for the static helper tests."""

    def get_number_of_pages(self) -> int:
        return 0

    def get_document_catalog(self) -> object:
        return self

    def get_viewer_preferences(self) -> None:
        return None


def test_constructor_is_private_like() -> None:
    with pytest.raises(RuntimeError):
        Printing()


def test_main_requires_one_arg() -> None:
    with pytest.raises(SystemExit):
        Printing.main([])


def test_print_helper_returns_pageable() -> None:
    pageable = Printing.print(_FakeDocument())
    assert isinstance(pageable, PDFPageable)


def test_print_with_attributes_returns_pageable() -> None:
    pageable = Printing.print_with_attributes(_FakeDocument())
    assert isinstance(pageable, PDFPageable)


def test_print_with_dialog_returns_pageable() -> None:
    pageable = Printing.print_with_dialog(_FakeDocument())
    assert isinstance(pageable, PDFPageable)


def test_print_with_dialog_and_attributes_returns_pageable() -> None:
    pageable = Printing.print_with_dialog_and_attributes(_FakeDocument())
    assert isinstance(pageable, PDFPageable)


def test_print_with_paper_returns_printable() -> None:
    printable = Printing.print_with_paper(_FakeDocument())
    assert isinstance(printable, PDFPrintable)
