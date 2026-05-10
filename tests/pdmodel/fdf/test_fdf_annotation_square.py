from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.fdf import FDFAnnotation, FDFAnnotationSquare


def test_default_constructor_stamps_subtype_square() -> None:
    a = FDFAnnotationSquare()
    assert a.get_subtype() == "Square"


def test_interior_color_round_trip() -> None:
    a = FDFAnnotationSquare()
    assert a.get_interior_color() is None
    a.set_interior_color((0.1, 0.2, 0.3))
    got = a.get_interior_color()
    assert got is not None
    assert got == pytest.approx((0.1, 0.2, 0.3), abs=1e-6)
    a.set_interior_color(None)
    assert a.get_interior_color() is None


def test_inherits_base_color_setter() -> None:
    a = FDFAnnotationSquare()
    a.set_color((1.0, 0.0, 0.0))
    assert a.get_color() == (1.0, 0.0, 0.0)


def test_factory_dispatch_square() -> None:
    d = COSDictionary()
    d.set_item(COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Square"))
    obj = FDFAnnotation.create(d)
    assert isinstance(obj, FDFAnnotationSquare)


def test_init_fringe_sets_rd_rectangle() -> None:
    a = FDFAnnotationSquare()
    assert a.get_fringe() is None
    a.init_fringe("1.0,2.0,3.0,4.0")
    rect = a.get_fringe()
    assert rect is not None
    assert rect.get_lower_left_x() == pytest.approx(1.0)
    assert rect.get_lower_left_y() == pytest.approx(2.0)
    assert rect.get_upper_right_x() == pytest.approx(3.0)
    assert rect.get_upper_right_y() == pytest.approx(4.0)


def test_init_fringe_noop_on_empty_or_none() -> None:
    a = FDFAnnotationSquare()
    a.init_fringe(None)
    assert a.get_fringe() is None
    a.init_fringe("")
    assert a.get_fringe() is None


def test_init_fringe_rejects_wrong_arity() -> None:
    a = FDFAnnotationSquare()
    with pytest.raises(OSError):
        a.init_fringe("1.0,2.0,3.0")
