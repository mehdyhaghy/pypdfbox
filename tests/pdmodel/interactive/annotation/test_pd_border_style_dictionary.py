from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName
from pypdfbox.pdmodel.interactive.annotation.pd_border_style_dictionary import (
    PDBorderStyleDictionary,
)


def test_default_constructor_sets_type_border() -> None:
    bs = PDBorderStyleDictionary()
    cos = bs.get_cos_object()
    assert isinstance(cos, COSDictionary)
    assert cos.get_name(COSName.TYPE) == "Border"  # type: ignore[attr-defined]


def test_default_width_is_one() -> None:
    bs = PDBorderStyleDictionary()
    assert bs.get_width() == 1.0


def test_default_style_is_solid() -> None:
    bs = PDBorderStyleDictionary()
    assert bs.get_style() == PDBorderStyleDictionary.STYLE_SOLID
    assert bs.get_style() == "S"


def test_default_dash_style_is_none() -> None:
    bs = PDBorderStyleDictionary()
    assert bs.get_dash_style() is None


def test_width_round_trip_float() -> None:
    bs = PDBorderStyleDictionary()
    bs.set_width(2.5)
    assert bs.get_width() == 2.5


def test_width_round_trip_integer_valued_float_is_stored_as_int() -> None:
    # PDFBOX-3929: integer-valued floats are stored as int.
    bs = PDBorderStyleDictionary()
    bs.set_width(2.0)
    cos = bs.get_cos_object()
    raw = cos.get_dictionary_object(COSName.get_pdf_name("W"))
    # Should be a COSInteger, not a COSFloat
    from pypdfbox.cos import COSFloat
    assert not isinstance(raw, COSFloat)
    assert bs.get_width() == 2.0


def test_style_round_trip_dashed() -> None:
    bs = PDBorderStyleDictionary()
    bs.set_style(PDBorderStyleDictionary.STYLE_DASHED)
    assert bs.get_style() == "D"


def test_dash_style_round_trip() -> None:
    bs = PDBorderStyleDictionary()
    arr = COSArray()
    arr.add(COSInteger.get(3))
    arr.add(COSInteger.get(2))
    bs.set_dash_style(arr)
    rt = bs.get_dash_style()
    assert isinstance(rt, COSArray)
    assert len(rt) == 2


def test_construct_from_existing_dict_preserves_contents() -> None:
    d = COSDictionary()
    d.set_name(COSName.get_pdf_name("S"), "D")
    d.set_float(COSName.get_pdf_name("W"), 3.5)
    bs = PDBorderStyleDictionary(d)
    assert bs.get_style() == "D"
    assert bs.get_width() == 3.5
    # Constructor with existing dict should NOT clobber /Type if present,
    # nor inject one if absent.
    assert bs.get_cos_object().get_name(COSName.TYPE) is None  # type: ignore[attr-defined]


def test_width_with_cosname_value_returns_zero() -> None:
    """Adobe quirk: name value for /W returns 0."""
    d = COSDictionary()
    d.set_name(COSName.get_pdf_name("W"), "Foo")
    bs = PDBorderStyleDictionary(d)
    assert bs.get_width() == 0.0


def test_dash_style_clear() -> None:
    bs = PDBorderStyleDictionary()
    arr = COSArray()
    arr.add(COSInteger.get(3))
    bs.set_dash_style(arr)
    bs.set_dash_style(None)
    assert bs.get_dash_style() is None
