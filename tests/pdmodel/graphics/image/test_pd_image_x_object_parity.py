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
    assert image.is_empty() is True
    assert image.get_suffix() == "png"


# ---------- stream helpers ----------


def test_is_empty_reflects_raw_stream_length() -> None:
    image = _make_image()
    assert image.is_empty() is True

    image.get_cos_object().set_raw_data(b"\x00\x01")
    assert image.is_empty() is False


def test_get_suffix_maps_native_image_filters() -> None:
    image = _make_image()
    cos = image.get_cos_object()

    cos.set_item(COSName.FILTER, COSName.get_pdf_name("DCTDecode"))  # type: ignore[attr-defined]
    assert image.get_suffix() == "jpg"

    cos.set_item(COSName.FILTER, COSName.get_pdf_name("JPXDecode"))  # type: ignore[attr-defined]
    assert image.get_suffix() == "jpx"

    cos.set_item(COSName.FILTER, COSName.get_pdf_name("CCITTFaxDecode"))  # type: ignore[attr-defined]
    assert image.get_suffix() == "tiff"

    cos.set_item(COSName.FILTER, COSName.get_pdf_name("JBIG2Decode"))  # type: ignore[attr-defined]
    assert image.get_suffix() == "jb2"


def test_get_suffix_maps_lossless_pdf_filters_to_png() -> None:
    image = _make_image()
    cos = image.get_cos_object()

    cos.set_item(COSName.FILTER, COSName.get_pdf_name("FlateDecode"))  # type: ignore[attr-defined]
    assert image.get_suffix() == "png"

    cos.set_item(COSName.FILTER, COSName.get_pdf_name("LZWDecode"))  # type: ignore[attr-defined]
    assert image.get_suffix() == "png"

    cos.set_item(COSName.FILTER, COSName.get_pdf_name("RunLengthDecode"))  # type: ignore[attr-defined]
    assert image.get_suffix() == "png"


def test_get_suffix_checks_entire_filter_chain() -> None:
    image = _make_image()
    filters = COSArray()
    filters.add(COSName.get_pdf_name("ASCII85Decode"))
    filters.add(COSName.get_pdf_name("DCTDecode"))
    image.get_cos_object().set_item(COSName.FILTER, filters)  # type: ignore[attr-defined]

    assert image.get_suffix() == "jpg"


def test_get_suffix_unknown_filter_returns_none() -> None:
    image = _make_image()
    image.get_cos_object().set_item(
        COSName.FILTER,  # type: ignore[attr-defined]
        COSName.get_pdf_name("Crypt"),
    )

    assert image.get_suffix() is None


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


def test_get_decode_array_returns_underlying_cos_array() -> None:
    """Mirrors upstream ``getDecode()`` which returns the underlying
    ``COSArray`` directly rather than a decoded ``list[float]``."""
    image = _make_image()
    image.set_decode([0.0, 1.0, 1.0, 0.0])

    array = image.get_decode_array()
    assert isinstance(array, COSArray)
    assert array is image.get_cos_object().get_dictionary_object(
        COSName.get_pdf_name("Decode")
    )
    assert array.to_float_array() == [0.0, 1.0, 1.0, 0.0]


def test_get_decode_array_is_none_when_absent() -> None:
    image = _make_image()
    assert image.get_decode_array() is None


# ---------- create_thumbnail factory ----------


def test_create_thumbnail_wraps_existing_stream() -> None:
    """Mirrors upstream ``PDImageXObject.createThumbnail(COSStream)``:
    constructs an Image XObject around any existing stream — the factory
    must stamp ``/Type /XObject`` and ``/Subtype /Image`` on the dict."""
    cos_stream = COSStream()
    cos_stream.set_int(COSName.get_pdf_name("Width"), 64)
    cos_stream.set_int(COSName.get_pdf_name("Height"), 48)
    cos_stream.set_int(COSName.get_pdf_name("BitsPerComponent"), 8)

    thumb = PDImageXObject.create_thumbnail(cos_stream)
    assert isinstance(thumb, PDImageXObject)
    assert thumb.get_cos_object() is cos_stream
    assert thumb.get_width() == 64
    assert thumb.get_height() == 48
    assert thumb.get_bits_per_component() == 8
    # Thumbnail factory still goes through the XObject ctor, so the
    # /Type and /Subtype keys are stamped.
    assert cos_stream.get_name(COSName.TYPE) == "XObject"  # type: ignore[attr-defined]
    assert cos_stream.get_name(COSName.get_pdf_name("Subtype")) == "Image"


def test_create_thumbnail_overrides_non_image_subtype() -> None:
    """Upstream notes that thumbnails are special: any non-null subtype
    is treated as ``/Image``. The factory ctor stamps ``/Subtype /Image``
    so an existing odd subtype is overwritten."""
    cos_stream = COSStream()
    cos_stream.set_name(COSName.get_pdf_name("Subtype"), "Form")

    thumb = PDImageXObject.create_thumbnail(cos_stream)
    assert thumb.get_cos_object().get_name(
        COSName.get_pdf_name("Subtype")
    ) == "Image"


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


def test_oc_returns_bare_property_list_for_unknown_type() -> None:
    image = _make_image()
    other = COSDictionary()
    other.set_name(COSName.TYPE, "Other")  # type: ignore[attr-defined]
    image.get_cos_object().set_item(COSName.get_pdf_name("OC"), other)
    # Upstream PDPropertyList.create wraps an unknown /Type in a bare
    # PDPropertyList (the "todo: more types" fallback). It is *not* None.
    result = image.get_oc()
    assert result is not None
    assert type(result) is PDPropertyList
    assert result.get_cos_object() is other
    # Sanity: PDPropertyList.create directly agrees.
    direct = PDPropertyList.create(other)
    assert direct is not None
    assert type(direct) is PDPropertyList


# ---------- mechanical aliases mirroring upstream camelCase ----------


def test_get_interpolate_alias_matches_is_interpolate() -> None:
    """``getInterpolate`` is the upstream interface name; ``isInterpolate``
    follows the Python-side ``isXxx`` pattern. Both should agree."""
    image = _make_image()
    assert image.get_interpolate() is False
    assert image.is_interpolate() is False

    image.set_interpolate(True)
    assert image.get_interpolate() is True
    assert image.is_interpolate() is True
    # Both accessors read the same /Interpolate entry.
    assert image.get_interpolate() == image.is_interpolate()


def test_get_optional_content_alias_round_trip() -> None:
    """``get_optional_content`` / ``set_optional_content`` mirror upstream
    ``getOptionalContent`` / ``setOptionalContent`` and share state with
    the short-form ``get_oc`` / ``set_oc`` accessors."""
    image = _make_image()
    assert image.get_optional_content() is None
    assert image.get_oc() is None

    ocg_dict = COSDictionary()
    ocg_dict.set_name(COSName.TYPE, "OCG")  # type: ignore[attr-defined]
    ocg_dict.set_string(COSName.get_pdf_name("Name"), "layer-1")
    ocg = PDOptionalContentGroup(ocg_dict)

    image.set_optional_content(ocg)
    fetched_long = image.get_optional_content()
    fetched_short = image.get_oc()
    assert fetched_long is not None
    assert fetched_short is not None
    # Both accessors return wrappers around the same COS dict.
    assert fetched_long.get_cos_object() is ocg_dict
    assert fetched_short.get_cos_object() is ocg_dict


def test_set_optional_content_none_clears_entry() -> None:
    image = _make_image()
    ocmd_dict = COSDictionary()
    ocmd_dict.set_name(COSName.TYPE, "OCMD")  # type: ignore[attr-defined]
    image.set_optional_content(PDOptionalContentMembershipDictionary(ocmd_dict))
    assert image.get_optional_content() is not None

    image.set_optional_content(None)
    assert image.get_optional_content() is None
    # Underlying COS dictionary no longer carries the /OC entry either.
    assert image.get_cos_object().get_dictionary_object(COSName.get_pdf_name("OC")) is None
