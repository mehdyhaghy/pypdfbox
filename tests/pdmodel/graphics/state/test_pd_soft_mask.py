"""Hand-written tests for :class:`PDSoftMask`.

PDF 32000-1 §11.6.5.3 (Soft-Mask Dictionaries) — Table 144 keys ``S`` /
``G`` / ``BC`` / ``TR`` round-trip through the lite typed wrapper.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSFloat,
    COSName,
    COSStream,
)
from pypdfbox.pdmodel.graphics.form.pd_form_x_object import PDFormXObject
from pypdfbox.pdmodel.graphics.state.pd_soft_mask import PDSoftMask


def test_default_constructor_marks_type_mask() -> None:
    sm = PDSoftMask()
    cos = sm.get_cos_object()
    type_entry = cos.get_dictionary_object(COSName.get_pdf_name("Type"))
    assert isinstance(type_entry, COSName)
    assert type_entry.name == "Mask"


def test_subtype_round_trip_alpha_and_luminosity() -> None:
    sm = PDSoftMask()
    sm.set_subtype(COSName.get_pdf_name("Alpha"))
    assert sm.is_alpha()
    assert not sm.is_luminosity()
    sm.set_subtype(COSName.get_pdf_name("Luminosity"))
    assert sm.is_luminosity()
    assert not sm.is_alpha()


def test_create_returns_none_for_none_name() -> None:
    assert PDSoftMask.create(COSName.get_pdf_name("None")) is None


def test_create_returns_none_for_unknown_input() -> None:
    assert PDSoftMask.create(None) is None
    # Non-dictionary, non-name bases are not soft masks.
    assert PDSoftMask.create(COSName.get_pdf_name("Foo")) is None


def test_create_wraps_dictionary() -> None:
    base = COSDictionary()
    base.set_item(COSName.get_pdf_name("S"), COSName.get_pdf_name("Alpha"))
    sm = PDSoftMask.create(base)
    assert isinstance(sm, PDSoftMask)
    assert sm.is_alpha()


def test_set_group_accepts_typed_form_x_object() -> None:
    sm = PDSoftMask()
    form_stream = COSStream()
    form_stream.set_item(
        COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Form")
    )
    form = PDFormXObject(form_stream)
    sm.set_group(form)
    g = sm.get_group()
    assert isinstance(g, PDFormXObject)
    assert g.get_cos_object() is form_stream


def test_set_group_accepts_raw_cos_stream() -> None:
    sm = PDSoftMask()
    s = COSStream()
    sm.set_group(s)
    g = sm.get_group()
    assert isinstance(g, PDFormXObject)
    assert g.get_cos_object() is s


def test_set_group_rejects_other_types() -> None:
    sm = PDSoftMask()
    with pytest.raises(TypeError):
        sm.set_group(COSDictionary())  # not a stream


def test_set_group_none_removes_entry() -> None:
    sm = PDSoftMask()
    sm.set_group(COSStream())
    assert sm.get_group() is not None
    sm.set_group(None)
    assert sm.get_group() is None


def test_backdrop_color_round_trip() -> None:
    sm = PDSoftMask()
    bc = COSArray()
    for v in (0.25, 0.5, 0.75):
        bc.add(COSFloat(v))
    sm.set_backdrop_color(bc)
    out = sm.get_backdrop_color()
    assert out is bc
    sm.set_backdrop_color(None)
    assert sm.get_backdrop_color() is None


def test_transfer_function_round_trip() -> None:
    sm = PDSoftMask()
    sm.set_transfer_function(COSName.get_pdf_name("Identity"))
    tr = sm.get_transfer_function()
    assert isinstance(tr, COSName)
    assert tr.name == "Identity"
    sm.set_transfer_function(None)
    assert sm.get_transfer_function() is None


def test_constructor_rejects_non_dictionary() -> None:
    with pytest.raises(TypeError):
        PDSoftMask(42)  # type: ignore[arg-type]
