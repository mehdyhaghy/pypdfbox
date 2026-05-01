from __future__ import annotations

from pypdfbox.cos import COSBoolean, COSDictionary, COSName
from pypdfbox.pdmodel.graphics.form import PDTransparencyGroupAttributes


_S = COSName.get_pdf_name("S")
_I = COSName.get_pdf_name("I")
_K = COSName.get_pdf_name("K")
_CS = COSName.get_pdf_name("CS")
_TRANSPARENCY = COSName.get_pdf_name("Transparency")


def test_default_constructor_stamps_subtype_transparency() -> None:
    attrs = PDTransparencyGroupAttributes()
    cos = attrs.get_cos_object()
    # /S /Transparency is the only soft-group subtype currently defined
    # in PDF 32000 §11.6 — it must be stamped on construction.
    assert cos.get_name(_S) == "Transparency"


def test_dictionary_constructor_does_not_overwrite_existing() -> None:
    raw = COSDictionary()
    raw.set_name(_S, "Transparency")
    raw.set_item(_I, COSBoolean.TRUE)
    attrs = PDTransparencyGroupAttributes(raw)
    assert attrs.get_cos_object() is raw
    # Existing /I flag is preserved (constructor must not reset entries).
    assert attrs.is_isolated() is True


def test_is_isolated_default_false() -> None:
    attrs = PDTransparencyGroupAttributes()
    # /I defaults to false per PDF 32000 §11.6.6.
    assert attrs.is_isolated() is False


def test_is_isolated_round_trip_via_dict() -> None:
    raw = COSDictionary()
    raw.set_item(_I, COSBoolean.TRUE)
    attrs = PDTransparencyGroupAttributes(raw)
    assert attrs.is_isolated() is True


def test_is_knockout_default_false() -> None:
    attrs = PDTransparencyGroupAttributes()
    # /K defaults to false per PDF 32000 §11.6.6.
    assert attrs.is_knockout() is False


def test_is_knockout_round_trip_via_dict() -> None:
    raw = COSDictionary()
    raw.set_item(_K, COSBoolean.TRUE)
    attrs = PDTransparencyGroupAttributes(raw)
    assert attrs.is_knockout() is True


def test_get_color_space_none_when_cs_absent() -> None:
    attrs = PDTransparencyGroupAttributes()
    # No /CS entry → no color space (and no exception).
    assert attrs.get_color_space() is None


def test_get_color_space_resolves_device_gray() -> None:
    raw = COSDictionary()
    raw.set_item(_CS, COSName.get_pdf_name("DeviceGray"))
    attrs = PDTransparencyGroupAttributes(raw)

    cs = attrs.get_color_space()
    assert cs is not None
    # Device color spaces resolve to the singleton; calling twice returns
    # the cached typed instance.
    assert attrs.get_color_space() is cs
