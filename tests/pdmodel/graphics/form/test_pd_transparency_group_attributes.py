from __future__ import annotations

import pytest

from pypdfbox.cos import COSBoolean, COSDictionary, COSName
from pypdfbox.pdmodel.graphics.color.pd_device_gray import PDDeviceGray
from pypdfbox.pdmodel.graphics.color.pd_device_rgb import PDDeviceRGB
from pypdfbox.pdmodel.graphics.form import PDTransparencyGroupAttributes
from pypdfbox.pdmodel.pd_resources import PDResources

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


# ---------- Wave 274: mutators, presence predicates, subtype helpers ----------


def test_set_color_space_accepts_typed_color_space_and_marks_present() -> None:
    attrs = PDTransparencyGroupAttributes()
    attrs.set_color_space(PDDeviceRGB.INSTANCE)

    assert attrs.has_color_space() is True
    assert attrs.get_cos_object().get_dictionary_object(_CS) is (
        PDDeviceRGB.INSTANCE.get_cos_object()
    )
    assert attrs.get_color_space() is PDDeviceRGB.INSTANCE


def test_set_color_space_accepts_raw_cos_value_and_marks_present() -> None:
    attrs = PDTransparencyGroupAttributes()
    name = COSName.get_pdf_name("DeviceGray")
    attrs.set_color_space(name)

    assert attrs.has_color_space() is True
    assert attrs.get_cos_object().get_dictionary_object(_CS) is name
    assert attrs.get_color_space() is PDDeviceGray.INSTANCE


def test_set_color_space_none_clears_entry_and_cached_typed_value() -> None:
    attrs = PDTransparencyGroupAttributes()
    attrs.set_color_space(COSName.get_pdf_name("DeviceGray"))
    assert attrs.get_color_space() is PDDeviceGray.INSTANCE

    attrs.set_color_space(None)

    assert attrs.has_color_space() is False
    assert attrs.get_cos_object().get_dictionary_object(_CS) is None
    assert attrs.get_color_space() is None


def test_set_color_space_resets_cached_typed_value() -> None:
    attrs = PDTransparencyGroupAttributes()
    attrs.set_color_space(COSName.get_pdf_name("DeviceGray"))
    assert attrs.get_color_space() is PDDeviceGray.INSTANCE

    attrs.set_color_space(COSName.get_pdf_name("DeviceRGB"))

    assert attrs.get_color_space() is PDDeviceRGB.INSTANCE


def test_set_color_space_rejects_unsupported_type() -> None:
    attrs = PDTransparencyGroupAttributes()

    with pytest.raises(TypeError):
        attrs.set_color_space("DeviceRGB")  # type: ignore[arg-type]


def test_set_isolated_writes_false_and_true_and_marks_present() -> None:
    attrs = PDTransparencyGroupAttributes()
    assert attrs.has_isolated() is False

    attrs.set_isolated(False)
    assert attrs.has_isolated() is True
    assert attrs.is_isolated() is False

    attrs.set_isolated(True)
    assert attrs.has_isolated() is True
    assert attrs.is_isolated() is True


def test_set_knockout_writes_false_and_true_and_marks_present() -> None:
    attrs = PDTransparencyGroupAttributes()
    assert attrs.has_knockout() is False

    attrs.set_knockout(False)
    assert attrs.has_knockout() is True
    assert attrs.is_knockout() is False

    attrs.set_knockout(True)
    assert attrs.has_knockout() is True
    assert attrs.is_knockout() is True


def test_subtype_default_presence_and_transparency_predicate() -> None:
    attrs = PDTransparencyGroupAttributes()

    assert attrs.has_subtype() is True
    assert attrs.get_subtype() == "Transparency"
    assert attrs.is_transparency_group() is True


def test_set_subtype_accepts_string_and_cos_name() -> None:
    attrs = PDTransparencyGroupAttributes()

    attrs.set_subtype("OtherGroup")
    assert attrs.has_subtype() is True
    assert attrs.get_subtype() == "OtherGroup"
    assert attrs.is_transparency_group() is False

    attrs.set_subtype(COSName.get_pdf_name("Transparency"))
    assert attrs.has_subtype() is True
    assert attrs.get_subtype() == "Transparency"
    assert attrs.is_transparency_group() is True


def test_set_subtype_none_clears_entry() -> None:
    attrs = PDTransparencyGroupAttributes()

    attrs.set_subtype(None)

    assert attrs.has_subtype() is False
    assert attrs.get_subtype() is None
    assert attrs.is_transparency_group() is False


def test_presence_predicates_report_explicit_dictionary_entries() -> None:
    attrs = PDTransparencyGroupAttributes(COSDictionary())
    assert attrs.has_color_space() is False
    assert attrs.has_isolated() is False
    assert attrs.has_knockout() is False
    assert attrs.has_subtype() is False

    attrs.get_cos_object().set_item(_CS, COSName.get_pdf_name("DeviceRGB"))
    attrs.get_cos_object().set_item(_I, COSBoolean.FALSE)
    attrs.get_cos_object().set_item(_K, COSBoolean.FALSE)
    attrs.get_cos_object().set_name(_S, "Transparency")

    assert attrs.has_color_space() is True
    assert attrs.has_isolated() is True
    assert attrs.has_knockout() is True
    assert attrs.has_subtype() is True


def test_wave330_get_color_space_re_resolves_named_entry_per_resources() -> None:
    alias = COSName.get_pdf_name("GroupCS")
    raw = COSDictionary()
    raw.set_item(_CS, alias)
    attrs = PDTransparencyGroupAttributes(raw)

    gray_resources = PDResources()
    gray_resources.put(
        PDResources.COLOR_SPACE,
        alias,
        COSName.get_pdf_name("DeviceGray"),
    )
    rgb_resources = PDResources()
    rgb_resources.put(
        PDResources.COLOR_SPACE,
        alias,
        COSName.get_pdf_name("DeviceRGB"),
    )

    assert attrs.get_color_space(gray_resources) is PDDeviceGray.INSTANCE
    assert attrs.get_color_space(rgb_resources) is PDDeviceRGB.INSTANCE
