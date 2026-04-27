from __future__ import annotations

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSStream,
    COSString,
)
from pypdfbox.pdmodel.common.pd_metadata import PDMetadata
from pypdfbox.pdmodel.graphics.image import PDImageXObject
from pypdfbox.pdmodel.graphics.optionalcontent import (
    PDOptionalContentGroup,
    PDOptionalContentMembershipDictionary,
)
from pypdfbox.pdmodel.graphics.pd_property_list import PDPropertyList


def _make_image() -> PDImageXObject:
    return PDImageXObject(COSStream())


# ---------- defaults ----------


def test_defaults() -> None:
    image = _make_image()
    assert image.get_mask() is None
    assert image.get_color_key_mask() is None
    assert image.get_soft_mask() is None
    assert image.get_decode() is None
    assert image.is_interpolate() is False
    assert image.is_image_mask() is False
    assert image.get_struct_parent() == -1
    assert image.get_metadata() is None
    assert image.get_oc() is None


# ---------- /Mask explicit-mask Image XObject ----------


def test_mask_round_trip_explicit_image_mask() -> None:
    image = _make_image()
    mask = _make_image()
    mask.set_width(8)
    mask.set_height(8)
    mask.set_image_mask(True)
    image.set_mask(mask)

    fetched = image.get_mask()
    assert fetched is not None
    assert fetched.get_cos_object() is mask.get_cos_object()
    # When /Mask is a stream, the color-key accessor must report None.
    assert image.get_color_key_mask() is None


def test_set_mask_none_removes_entry() -> None:
    image = _make_image()
    image.set_mask(_make_image())
    assert image.get_cos_object().get_dictionary_object(COSName.get_pdf_name("Mask")) is not None
    image.set_mask(None)
    assert image.get_cos_object().get_dictionary_object(COSName.get_pdf_name("Mask")) is None
    assert image.get_mask() is None


# ---------- /Mask color-key array ----------


def test_color_key_mask_round_trip_int_array() -> None:
    image = _make_image()
    image.set_color_key_mask([0, 10, 200, 255])

    assert image.get_color_key_mask() == [0, 10, 200, 255]
    # When /Mask is an array of ints, the explicit-mask accessor returns None.
    assert image.get_mask() is None
    raw = image.get_cos_object().get_dictionary_object(COSName.get_pdf_name("Mask"))
    assert isinstance(raw, COSArray)
    assert all(isinstance(item, COSInteger) for item in raw)


def test_color_key_mask_reads_existing_array() -> None:
    image = _make_image()
    array = COSArray()
    array.add(COSInteger.get(5))
    array.add(COSInteger.get(15))
    image.get_cos_object().set_item(COSName.get_pdf_name("Mask"), array)

    assert image.get_color_key_mask() == [5, 15]
    assert image.get_mask() is None


def test_color_key_mask_returns_none_for_non_int_entries() -> None:
    image = _make_image()
    array = COSArray()
    array.add(COSString(b"oops"))
    image.get_cos_object().set_item(COSName.get_pdf_name("Mask"), array)
    assert image.get_color_key_mask() is None


def test_set_color_key_mask_none_removes_entry() -> None:
    image = _make_image()
    image.set_color_key_mask([0, 10])
    image.set_color_key_mask(None)
    assert image.get_cos_object().get_dictionary_object(COSName.get_pdf_name("Mask")) is None
    assert image.get_color_key_mask() is None


# ---------- /SMask ----------


def test_soft_mask_round_trip() -> None:
    image = _make_image()
    smask = _make_image()
    smask.set_width(4)
    smask.set_height(4)
    image.set_soft_mask(smask)

    fetched = image.get_soft_mask()
    assert fetched is not None
    assert fetched.get_cos_object() is smask.get_cos_object()


def test_set_soft_mask_none_removes_entry() -> None:
    image = _make_image()
    image.set_soft_mask(_make_image())
    image.set_soft_mask(None)
    assert image.get_soft_mask() is None
    assert image.get_cos_object().get_dictionary_object(COSName.get_pdf_name("SMask")) is None


# ---------- /Decode ----------


def test_decode_round_trip() -> None:
    image = _make_image()
    image.set_decode([0.0, 1.0, 1.0, 0.0])

    assert image.get_decode() == [0.0, 1.0, 1.0, 0.0]
    raw = image.get_cos_object().get_dictionary_object(COSName.get_pdf_name("Decode"))
    assert isinstance(raw, COSArray)
    assert all(isinstance(item, COSFloat) for item in raw)


def test_set_decode_none_removes_entry() -> None:
    image = _make_image()
    image.set_decode([0.0, 1.0])
    image.set_decode(None)
    assert image.get_decode() is None
    assert image.get_cos_object().get_dictionary_object(COSName.get_pdf_name("Decode")) is None


# ---------- /Interpolate ----------


def test_interpolate_round_trip() -> None:
    image = _make_image()
    image.set_interpolate(True)
    assert image.is_interpolate() is True
    image.set_interpolate(False)
    assert image.is_interpolate() is False


# ---------- /ImageMask ----------


def test_image_mask_round_trip() -> None:
    image = _make_image()
    image.set_image_mask(True)
    assert image.is_image_mask() is True
    image.set_image_mask(False)
    assert image.is_image_mask() is False


# ---------- /StructParent ----------


def test_struct_parent_round_trip() -> None:
    image = _make_image()
    image.set_struct_parent(7)
    assert image.get_struct_parent() == 7
    image.set_struct_parent(0)
    assert image.get_struct_parent() == 0


# ---------- /Metadata ----------


def test_metadata_round_trip() -> None:
    image = _make_image()
    metadata_stream = COSStream()
    metadata_stream.set_name(COSName.TYPE, "Metadata")  # type: ignore[attr-defined]
    metadata_stream.set_name(COSName.SUBTYPE, "XML")  # type: ignore[attr-defined]
    metadata = PDMetadata(metadata_stream)
    image.set_metadata(metadata)

    fetched = image.get_metadata()
    assert isinstance(fetched, PDMetadata)
    assert fetched.get_cos_object() is metadata_stream


def test_set_metadata_none_removes_entry() -> None:
    image = _make_image()
    image.set_metadata(PDMetadata(COSStream()))
    image.set_metadata(None)
    assert image.get_metadata() is None
    assert image.get_cos_object().get_dictionary_object(COSName.METADATA) is None  # type: ignore[attr-defined]


# ---------- /OC ----------


def test_oc_round_trip_optional_content_group() -> None:
    image = _make_image()
    ocg_dict = COSDictionary()
    ocg_dict.set_name(COSName.TYPE, "OCG")  # type: ignore[attr-defined]
    ocg_dict.set_string("Name", "Layer 1")
    ocg = PDOptionalContentGroup(ocg_dict)
    image.set_oc(ocg)

    fetched = image.get_oc()
    assert isinstance(fetched, PDOptionalContentGroup)
    assert fetched.get_cos_object() is ocg_dict


def test_oc_round_trip_membership_dictionary() -> None:
    image = _make_image()
    ocmd_dict = COSDictionary()
    ocmd_dict.set_name(COSName.TYPE, "OCMD")  # type: ignore[attr-defined]
    ocmd = PDOptionalContentMembershipDictionary(ocmd_dict)
    image.set_oc(ocmd)

    fetched = image.get_oc()
    assert isinstance(fetched, PDOptionalContentMembershipDictionary)
    assert fetched.get_cos_object() is ocmd_dict


def test_set_oc_none_removes_entry() -> None:
    image = _make_image()
    ocg_dict = COSDictionary()
    ocg_dict.set_name(COSName.TYPE, "OCG")  # type: ignore[attr-defined]
    image.set_oc(PDOptionalContentGroup(ocg_dict))
    image.set_oc(None)
    assert image.get_oc() is None
    assert image.get_cos_object().get_dictionary_object(COSName.get_pdf_name("OC")) is None


def test_oc_returns_none_for_unknown_type() -> None:
    image = _make_image()
    other = COSDictionary()
    other.set_name(COSName.TYPE, "Other")  # type: ignore[attr-defined]
    image.get_cos_object().set_item(COSName.get_pdf_name("OC"), other)
    # PDPropertyList.create returns None for unrecognised /Type entries.
    assert image.get_oc() is None
    # Sanity: PDPropertyList.create directly agrees.
    assert PDPropertyList.create(other) is None
