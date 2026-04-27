"""Ported from upstream PDFBox 3.0:
``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/PageLayoutTest.java``."""

from __future__ import annotations

import pytest

from pypdfbox.pdmodel.page_layout import PageLayout


def test_values() -> None:
    # PDFBOX-3362: every member round-trips through ``from_string`` and the
    # set of string values has the same cardinality as the enum.
    page_layout_set: set[PageLayout] = set()
    string_set: set[str] = set()
    for pl in PageLayout:
        s = pl.string_value()
        string_set.add(s)
        page_layout_set.add(PageLayout.from_string(s))
    assert len(page_layout_set) == len(list(PageLayout))
    assert len(string_set) == len(list(PageLayout))


def test_from_string_input_not_null_output_illegal_argument_exception() -> None:
    # Upstream raises ``IllegalArgumentException``; the Python analogue is
    # ``ValueError`` (also what ``Enum`` itself raises for unknown values).
    with pytest.raises(ValueError):
        PageLayout.from_string("SinglePag")
