from __future__ import annotations

import pytest

from pypdfbox.pdmodel.fdf import FDFAnnotationInk


def test_default_constructor_sets_subtype() -> None:
    ink = FDFAnnotationInk()
    assert ink.get_cos_object().get_name_as_string("Subtype") == "Ink"


def test_set_get_ink_list_roundtrip() -> None:
    ink = FDFAnnotationInk()
    paths = [[1.0, 2.0, 3.0, 4.0], [5.0, 6.0]]
    ink.set_ink_list(paths)
    out = ink.get_ink_list()
    assert out is not None
    assert len(out) == 2
    assert out[0] == pytest.approx([1.0, 2.0, 3.0, 4.0])
    assert out[1] == pytest.approx([5.0, 6.0])


def test_set_ink_list_none_clears() -> None:
    ink = FDFAnnotationInk()
    ink.set_ink_list([[1.0, 2.0]])
    ink.set_ink_list(None)
    assert ink.get_ink_list() is None


def test_get_ink_list_when_absent() -> None:
    ink = FDFAnnotationInk()
    assert ink.get_ink_list() is None


def test_empty_paths() -> None:
    ink = FDFAnnotationInk()
    ink.set_ink_list([])
    out = ink.get_ink_list()
    assert out == []
