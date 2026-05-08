"""Hand-written tests for Wave 231 PDImageXObject surface:

- ``get_bits_per_component`` short-circuits to ``1`` for stencil masks
- ``/Matte`` accessor (``get_matte`` / ``set_matte`` / ``get_matte_array``)
- presence predicates (``has_mask`` / ``has_soft_mask`` / ``has_metadata``
  / ``has_optional_content`` / ``has_color_space`` / ``has_decode`` /
  ``has_matte`` and the explicit/color-key splits)
- filter-type predicates (``is_jpeg`` / ``is_jpx`` / ``is_jbig2`` /
  ``is_ccittfax``)
- ``set_decode_array`` taking a pre-built ``COSArray``
- ``SUBTYPE_IMAGE`` module-level constant
"""

from __future__ import annotations

from pypdfbox.cos import (
    COSArray,
    COSFloat,
    COSInteger,
    COSName,
    COSStream,
)
from pypdfbox.pdmodel.common.pd_metadata import PDMetadata
from pypdfbox.pdmodel.graphics.color import PDDeviceGray
from pypdfbox.pdmodel.graphics.image import PDImageXObject
from pypdfbox.pdmodel.graphics.image.pd_image_x_object import SUBTYPE_IMAGE
from pypdfbox.pdmodel.graphics.optionalcontent import PDOptionalContentGroup


def _make_image() -> PDImageXObject:
    return PDImageXObject(COSStream())


# ---------- SUBTYPE_IMAGE constant ----------


def test_subtype_image_is_pdf_name_image() -> None:
    assert isinstance(SUBTYPE_IMAGE, COSName)
    assert SUBTYPE_IMAGE.name == "Image"


def test_subtype_image_matches_constructor_subtype() -> None:
    image = _make_image()
    assert image.get_subtype() == SUBTYPE_IMAGE.name


# ---------- bits-per-component stencil short-circuit ----------


def test_get_bits_per_component_returns_minus_one_when_absent() -> None:
    image = _make_image()
    assert image.get_bits_per_component() == -1


def test_get_bits_per_component_reads_dictionary_entry() -> None:
    image = _make_image()
    image.set_bits_per_component(8)
    assert image.get_bits_per_component() == 8


def test_get_bits_per_component_falls_back_to_short_bpc_alias() -> None:
    image = _make_image()
    image.get_cos_object().set_int(COSName.get_pdf_name("BPC"), 4)
    assert image.get_bits_per_component() == 4


def test_get_bits_per_component_returns_one_for_stencil() -> None:
    """Stencil masks always report 1 even if /BitsPerComponent is missing
    or carries a different value — mirrors upstream short-circuit."""
    image = _make_image()
    image.set_stencil(True)
    assert image.get_bits_per_component() == 1


def test_get_bits_per_component_stencil_overrides_existing_dict_value() -> None:
    image = _make_image()
    image.set_bits_per_component(8)
    image.set_stencil(True)
    # Even though /BitsPerComponent is 8 in the dict, stencil short-circuits.
    assert image.get_bits_per_component() == 1


def test_get_bits_per_component_non_stencil_after_reset() -> None:
    image = _make_image()
    image.set_bits_per_component(8)
    image.set_stencil(True)
    assert image.get_bits_per_component() == 1
    image.set_stencil(False)
    assert image.get_bits_per_component() == 8


def test_get_color_space_stencil_without_entry_yields_devicegray() -> None:
    """Stencil masks have an implicit gray color space when /ColorSpace is absent."""
    image = _make_image()
    image.set_stencil(True)

    assert image.get_color_space() is PDDeviceGray.INSTANCE


# ---------- /Matte accessor ----------


def test_get_matte_returns_none_when_absent() -> None:
    image = _make_image()
    assert image.get_matte() is None
    assert image.get_matte_array() is None


def test_set_matte_round_trip_to_floats() -> None:
    image = _make_image()
    image.set_matte([0.0, 0.5, 1.0])
    matte = image.get_matte()
    assert matte is not None
    # COSFloat round-trip uses 32-bit storage on the way through; 0.0,
    # 0.5, and 1.0 are exactly representable so equality is safe.
    assert matte == [0.0, 0.5, 1.0]


def test_set_matte_none_removes_entry() -> None:
    image = _make_image()
    image.set_matte([0.5, 0.5, 0.5])
    image.set_matte(None)
    assert image.get_matte() is None
    assert image.has_matte() is False
    # The dictionary must not contain the /Matte entry after removal.
    assert (
        image.get_cos_object().get_dictionary_object(COSName.get_pdf_name("Matte"))
        is None
    )


def test_get_matte_returns_none_when_not_array() -> None:
    image = _make_image()
    image.get_cos_object().set_int(COSName.get_pdf_name("Matte"), 1)
    assert image.get_matte() is None
    assert image.get_matte_array() is None


def test_get_matte_array_returns_underlying_cos_array() -> None:
    image = _make_image()
    array = COSArray()
    array.add(COSFloat(0.0))
    array.add(COSFloat(1.0))
    image.get_cos_object().set_item(COSName.get_pdf_name("Matte"), array)
    assert image.get_matte_array() is array
    assert image.get_matte() == [0.0, 1.0]


# ---------- presence predicates ----------


def test_has_mask_false_by_default() -> None:
    image = _make_image()
    assert image.has_mask() is False
    assert image.has_explicit_mask() is False
    assert image.has_color_key_mask() is False


def test_has_explicit_mask_when_stream() -> None:
    image = _make_image()
    mask = PDImageXObject(COSStream())
    image.set_mask(mask)
    assert image.has_mask() is True
    assert image.has_explicit_mask() is True
    assert image.has_color_key_mask() is False


def test_has_color_key_mask_when_array() -> None:
    image = _make_image()
    image.set_color_key_mask([10, 20])
    assert image.has_mask() is True
    assert image.has_explicit_mask() is False
    assert image.has_color_key_mask() is True


def test_has_soft_mask_round_trip() -> None:
    image = _make_image()
    assert image.has_soft_mask() is False
    image.set_soft_mask(PDImageXObject(COSStream()))
    assert image.has_soft_mask() is True
    image.set_soft_mask(None)
    assert image.has_soft_mask() is False


def test_has_color_space_round_trip() -> None:
    image = _make_image()
    assert image.has_color_space() is False
    image.set_color_space("DeviceRGB")
    assert image.has_color_space() is True


def test_has_color_space_uses_short_alias() -> None:
    image = _make_image()
    image.get_cos_object().set_item(
        COSName.get_pdf_name("CS"), COSName.get_pdf_name("DeviceGray")
    )
    assert image.has_color_space() is True


def test_has_metadata_round_trip() -> None:
    image = _make_image()
    assert image.has_metadata() is False
    image.set_metadata(PDMetadata(COSStream()))
    assert image.has_metadata() is True
    image.set_metadata(None)
    assert image.has_metadata() is False


def test_has_optional_content_round_trip() -> None:
    image = _make_image()
    assert image.has_optional_content() is False
    image.set_optional_content(PDOptionalContentGroup("X"))
    assert image.has_optional_content() is True


def test_has_decode_round_trip() -> None:
    image = _make_image()
    assert image.has_decode() is False
    image.set_decode([0.0, 1.0, 0.0, 1.0])
    assert image.has_decode() is True
    image.set_decode(None)
    assert image.has_decode() is False


def test_has_matte_round_trip() -> None:
    image = _make_image()
    assert image.has_matte() is False
    image.set_matte([0.0, 0.0, 0.0])
    assert image.has_matte() is True
    image.set_matte(None)
    assert image.has_matte() is False


# ---------- filter-type predicates ----------


def test_filter_predicates_false_by_default() -> None:
    image = _make_image()
    assert image.is_jpeg() is False
    assert image.is_jpx() is False
    assert image.is_jbig2() is False
    assert image.is_ccittfax() is False


def test_is_jpeg_when_dct_decode() -> None:
    image = _make_image()
    image.get_cos_object().set_item(
        COSName.FILTER, COSName.get_pdf_name("DCTDecode")  # type: ignore[attr-defined]
    )
    assert image.is_jpeg() is True
    assert image.is_jpx() is False


def test_is_jpx_when_jpx_decode() -> None:
    image = _make_image()
    image.get_cos_object().set_item(
        COSName.FILTER, COSName.get_pdf_name("JPXDecode")  # type: ignore[attr-defined]
    )
    assert image.is_jpx() is True
    assert image.is_jpeg() is False


def test_is_jpx_when_short_jpx_filter_alias() -> None:
    image = _make_image()
    image.get_cos_object().set_item(
        COSName.FILTER, COSName.get_pdf_name("JPX")  # type: ignore[attr-defined]
    )
    assert image.is_jpx() is True


def test_is_jbig2_when_jbig2_decode() -> None:
    image = _make_image()
    image.get_cos_object().set_item(
        COSName.FILTER, COSName.get_pdf_name("JBIG2Decode")  # type: ignore[attr-defined]
    )
    assert image.is_jbig2() is True


def test_is_ccittfax_when_ccittfax_decode() -> None:
    image = _make_image()
    image.get_cos_object().set_item(
        COSName.FILTER, COSName.get_pdf_name("CCITTFaxDecode")  # type: ignore[attr-defined]
    )
    assert image.is_ccittfax() is True


def test_is_ccittfax_when_short_ccf_filter_alias() -> None:
    image = _make_image()
    image.get_cos_object().set_item(
        COSName.FILTER, COSName.get_pdf_name("CCF")  # type: ignore[attr-defined]
    )
    assert image.is_ccittfax() is True


def test_filter_predicate_handles_filter_chain() -> None:
    """A filter chain like [/FlateDecode, /DCTDecode] should still match
    is_jpeg() — the predicate scans the entire chain, mirroring how
    ``get_suffix`` reads the chain."""
    image = _make_image()
    chain = COSArray()
    chain.add(COSName.get_pdf_name("FlateDecode"))
    chain.add(COSName.get_pdf_name("DCTDecode"))
    image.get_cos_object().set_item(COSName.FILTER, chain)  # type: ignore[attr-defined]
    assert image.is_jpeg() is True


# ---------- set_decode_array ----------


def test_set_decode_array_round_trip() -> None:
    image = _make_image()
    array = COSArray()
    array.add(COSFloat(0.0))
    array.add(COSFloat(1.0))
    image.set_decode_array(array)
    assert image.get_decode_array() is array
    assert image.get_decode() == [0.0, 1.0]


def test_set_decode_array_none_removes_entry() -> None:
    image = _make_image()
    image.set_decode([0.0, 1.0])
    image.set_decode_array(None)
    assert image.get_decode() is None
    assert image.get_decode_array() is None


def test_set_decode_array_accepts_int_entries() -> None:
    """COSArray for /Decode may carry COSInteger entries — the typed
    setter does not transform contents, mirroring the raw Java setter."""
    image = _make_image()
    array = COSArray()
    array.add(COSInteger.get(0))
    array.add(COSInteger.get(1))
    image.set_decode_array(array)
    assert image.get_decode_array() is array
    # to_float_array coerces integer entries to floats.
    assert image.get_decode() == [0.0, 1.0]
