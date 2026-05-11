from __future__ import annotations

import pytest

from pypdfbox.pdmodel.fdf import FDFAnnotationTextMarkup


def test_coords_roundtrip() -> None:
    markup = FDFAnnotationTextMarkup()
    markup.set_coords([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0])
    assert markup.get_coords() == pytest.approx([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0])


def test_coords_none_clears() -> None:
    markup = FDFAnnotationTextMarkup()
    markup.set_coords([1.0, 2.0])
    markup.set_coords(None)
    assert markup.get_coords() is None


def test_coords_get_when_absent() -> None:
    markup = FDFAnnotationTextMarkup()
    assert markup.get_coords() is None
