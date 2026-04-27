from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.fdf import FDFAnnotation, FDFAnnotationCircle


def test_default_constructor_stamps_subtype_circle() -> None:
    a = FDFAnnotationCircle()
    assert a.get_subtype() == "Circle"


def test_interior_color_round_trip() -> None:
    a = FDFAnnotationCircle()
    assert a.get_interior_color() is None
    a.set_interior_color((0.4, 0.5, 0.6))
    got = a.get_interior_color()
    assert got is not None
    assert got == pytest.approx((0.4, 0.5, 0.6), abs=1e-6)
    a.set_interior_color(None)
    assert a.get_interior_color() is None


def test_rect_inherited() -> None:
    a = FDFAnnotationCircle()
    a.set_rectangle((0.0, 0.0, 100.0, 50.0))
    assert a.get_rectangle() == (0.0, 0.0, 100.0, 50.0)


def test_factory_dispatch_circle() -> None:
    d = COSDictionary()
    d.set_item(COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Circle"))
    obj = FDFAnnotation.create(d)
    assert isinstance(obj, FDFAnnotationCircle)
