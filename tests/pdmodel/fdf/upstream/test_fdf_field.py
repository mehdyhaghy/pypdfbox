"""Ported from upstream PDFBox FDFFieldTest-shape coverage.

See note in ``test_fdf_document.py`` re: provenance.
"""

from __future__ import annotations

from pypdfbox.cos import COSName
from pypdfbox.pdmodel.fdf import FDFField


def test_set_value_string_round_trip() -> None:
    f = FDFField()
    f.set_value("hello")
    assert f.get_value() == "hello"


def test_set_value_name_round_trip() -> None:
    """Buttons store the on-state as /Yes (a name)."""
    f = FDFField()
    f.set_value(COSName.get_pdf_name("Yes"))
    assert f.get_value() == "Yes"


def test_set_value_list_round_trip() -> None:
    """Multi-select choice fields store an array of strings."""
    f = FDFField()
    f.set_value(["one", "two"])
    assert f.get_value() == ["one", "two"]


def test_kids_round_trip() -> None:
    parent = FDFField()
    parent.set_partial_field_name("group")
    child = FDFField()
    child.set_partial_field_name("inner")
    parent.set_kids([child])
    kids = parent.get_kids()
    assert kids is not None and len(kids) == 1
    assert kids[0].get_partial_field_name() == "inner"
