from __future__ import annotations

import io
import zlib

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSInteger,
    COSName,
)
from pypdfbox.pdmodel.graphics.color import (
    PDDeviceGray,
    PDDeviceRGB,
)
from pypdfbox.pdmodel.graphics.image import PDInlineImage


def _basic_dict(width: int = 4, height: int = 4, bpc: int = 8) -> COSDictionary:
    d = COSDictionary()
    d.set_int(COSName.get_pdf_name("W"), width)
    d.set_int(COSName.get_pdf_name("H"), height)
    d.set_int(COSName.get_pdf_name("BPC"), bpc)
    return d


# ---------- basic geometry ----------


def test_width_height_bpc_basic() -> None:
    d = _basic_dict(width=12, height=7, bpc=8)
    img = PDInlineImage(d, b"\x00" * (12 * 7), None)
    assert img.get_width() == 12
    assert img.get_height() == 7
    assert img.get_bits_per_component() == 8


def test_long_name_keys_fall_back() -> None:
    """``/Width`` / ``/Height`` / ``/BitsPerComponent`` long form is
    accepted when the abbreviation isn't present (mirrors upstream
    two-key lookup)."""
    d = COSDictionary()
    d.set_int(COSName.get_pdf_name("Width"), 9)
    d.set_int(COSName.get_pdf_name("Height"), 11)
    d.set_int(COSName.get_pdf_name("BitsPerComponent"), 4)
    img = PDInlineImage(d, b"\x00", None)
    assert img.get_width() == 9
    assert img.get_height() == 11
    assert img.get_bits_per_component() == 4


def test_setters_use_short_form() -> None:
    img = PDInlineImage(_basic_dict(), b"\x00", None)
    img.set_width(101)
    img.set_height(202)
    img.set_bits_per_component(2)
    cos = img.get_cos_object()
    assert cos.get_int(COSName.get_pdf_name("W")) == 101
    assert cos.get_int(COSName.get_pdf_name("H")) == 202
    assert cos.get_int(COSName.get_pdf_name("BPC")) == 2


# ---------- two-key precedence + COSNull fallback ----------
# Oracle-pinned against Apache PDFBox 3.0.7 (InlineImageKeyResolveProbe):
# PDInlineImage scalar getters resolve via COSDictionary#getInt/getBoolean
# (firstKey, secondKey, default), which delegate to
# getDictionaryObject(firstKey, secondKey). That overload (a) resolves a
# COSNull first-key value to None and falls back to the second key, and
# (b) returns the default — without re-consulting the long key — when the
# first key resolves to a non-null value of the wrong type.


def test_two_key_short_form_wins_when_both_present() -> None:
    """Both ``/W`` and ``/Width`` present → short abbreviation wins.
    Oracle: ``both_W_Width=7``."""
    d = COSDictionary()
    d.set_item(COSName.get_pdf_name("W"), COSInteger.get(7))
    d.set_item(COSName.get_pdf_name("Width"), COSInteger.get(99))
    img = PDInlineImage(d, b"", None)
    assert img.get_width() == 7


def test_two_key_int_cosnull_short_falls_back_to_long() -> None:
    """``/W`` = COSNull resolves to None, so the long ``/Width`` is used.
    Oracle: ``Wnull_Width13=13``."""
    from pypdfbox.cos.cos_null import COSNull

    d = COSDictionary()
    d.set_item(COSName.get_pdf_name("W"), COSNull.NULL)
    d.set_item(COSName.get_pdf_name("Width"), COSInteger.get(13))
    img = PDInlineImage(d, b"", None)
    assert img.get_width() == 13


def test_two_key_int_cosnull_short_only_yields_default() -> None:
    """``/W`` = COSNull with no long form → default ``-1``.
    Oracle: ``Wnull_only=-1``."""
    from pypdfbox.cos.cos_null import COSNull

    d = COSDictionary()
    d.set_item(COSName.get_pdf_name("W"), COSNull.NULL)
    img = PDInlineImage(d, b"", None)
    assert img.get_width() == -1


def test_two_key_int_wrong_type_short_does_not_fall_back() -> None:
    """``/H`` = a COSName (non-number) resolves non-null but is not a
    number → default ``-1``; the long ``/Height`` is NOT consulted.
    Oracle: ``Hname_Height21=-1``."""
    d = COSDictionary()
    d.set_item(COSName.get_pdf_name("H"), COSName.get_pdf_name("Foo"))
    d.set_item(COSName.get_pdf_name("Height"), COSInteger.get(21))
    img = PDInlineImage(d, b"", None)
    assert img.get_height() == -1


def test_two_key_bpc_cosnull_short_falls_back_to_long() -> None:
    """``/BPC`` = COSNull → long ``/BitsPerComponent`` used (non-stencil).
    Oracle: ``BPCnull_BPCfull4=4``."""
    from pypdfbox.cos.cos_null import COSNull

    d = COSDictionary()
    d.set_item(COSName.get_pdf_name("BPC"), COSNull.NULL)
    d.set_item(COSName.get_pdf_name("BitsPerComponent"), COSInteger.get(4))
    img = PDInlineImage(d, b"", None)
    assert img.get_bits_per_component() == 4


def test_two_key_boolean_cosnull_short_falls_back_to_long() -> None:
    """``/IM`` = COSNull → long ``/ImageMask`` used.
    Oracle: ``IMnull_ImageMaskTrue=true``."""
    from pypdfbox.cos import COSBoolean
    from pypdfbox.cos.cos_null import COSNull

    d = COSDictionary()
    d.set_item(COSName.get_pdf_name("IM"), COSNull.NULL)
    d.set_item(COSName.get_pdf_name("ImageMask"), COSBoolean.TRUE)
    img = PDInlineImage(d, b"", None)
    assert img.is_stencil() is True


def test_two_key_boolean_short_false_wins_over_long_true() -> None:
    """``/IM`` explicitly false beats long ``/ImageMask`` true.
    Oracle: ``IMfalse_ImageMaskTrue=false``."""
    from pypdfbox.cos import COSBoolean

    d = COSDictionary()
    d.set_item(COSName.get_pdf_name("IM"), COSBoolean.FALSE)
    d.set_item(COSName.get_pdf_name("ImageMask"), COSBoolean.TRUE)
    img = PDInlineImage(d, b"", None)
    assert img.is_stencil() is False


def test_two_key_interpolate_cosnull_short_falls_back_to_long() -> None:
    """``/I`` = COSNull → long ``/Interpolate`` used.
    Oracle: ``Inull_InterpolateTrue=true``."""
    from pypdfbox.cos import COSBoolean
    from pypdfbox.cos.cos_null import COSNull

    d = COSDictionary()
    d.set_item(COSName.get_pdf_name("I"), COSNull.NULL)
    d.set_item(COSName.get_pdf_name("Interpolate"), COSBoolean.TRUE)
    img = PDInlineImage(d, b"", None)
    assert img.get_interpolate() is True


# ---------- /CS color space ----------


def test_color_space_short_name_g_expands_to_devicegray() -> None:
    d = _basic_dict()
    d.set_item(COSName.get_pdf_name("CS"), COSName.get_pdf_name("G"))
    img = PDInlineImage(d, b"\x00", None)
    assert img.get_color_space() is PDDeviceGray.INSTANCE


def test_color_space_short_name_rgb_expands_to_devicergb() -> None:
    d = _basic_dict()
    d.set_item(COSName.get_pdf_name("CS"), COSName.get_pdf_name("RGB"))
    img = PDInlineImage(d, b"\x00", None)
    assert img.get_color_space() is PDDeviceRGB.INSTANCE


def test_stencil_without_colorspace_yields_devicegray() -> None:
    d = _basic_dict(bpc=1)
    d.set_boolean(COSName.get_pdf_name("IM"), True)
    img = PDInlineImage(d, b"\x00", None)
    # stencil overrides BPC to 1
    assert img.get_bits_per_component() == 1
    assert img.get_color_space() is PDDeviceGray.INSTANCE


def test_missing_colorspace_non_stencil_raises() -> None:
    img = PDInlineImage(_basic_dict(), b"\x00", None)
    with pytest.raises(OSError):
        img.get_color_space()


# ---------- decoded data ----------


def test_get_data_returns_raw_when_no_filters() -> None:
    payload = bytes(range(16))
    img = PDInlineImage(_basic_dict(width=4, height=4, bpc=8), payload, None)
    assert img.get_data() == payload
    # raw stream surface
    assert img.get_stream() == payload
    # default create_input_stream() returns decoded bytes
    with img.create_input_stream() as stream:
        assert stream.read() == payload
    assert not img.is_empty()


def test_flate_decode_round_trip() -> None:
    raw_payload = b"hello inline image"
    encoded = zlib.compress(raw_payload)
    d = _basic_dict(width=len(raw_payload), height=1, bpc=8)
    d.set_item(COSName.get_pdf_name("F"), COSName.get_pdf_name("FlateDecode"))
    img = PDInlineImage(d, encoded, None)
    assert img.get_data() == raw_payload
    # raw stream is the still-encoded form
    assert img.get_stream() == encoded


def test_short_filter_name_fl_is_accepted() -> None:
    raw_payload = b"abcXYZ"
    encoded = zlib.compress(raw_payload)
    d = _basic_dict(width=len(raw_payload), height=1, bpc=8)
    d.set_item(COSName.get_pdf_name("F"), COSName.get_pdf_name("Fl"))
    img = PDInlineImage(d, encoded, None)
    assert img.get_data() == raw_payload


# ---------- /Filter accessor ----------


def test_get_filters_single_name() -> None:
    d = _basic_dict()
    d.set_item(COSName.get_pdf_name("F"), COSName.get_pdf_name("FlateDecode"))
    # Force-encode an empty payload so the constructor's filter loop
    # has valid zlib input — the test only inspects the metadata.
    img = PDInlineImage(d, zlib.compress(b""), None)
    assert img.get_filters() == ["FlateDecode"]


def test_get_filters_array_form() -> None:
    d = _basic_dict()
    arr = COSArray()
    arr.add(COSName.get_pdf_name("ASCIIHexDecode"))
    arr.add(COSName.get_pdf_name("FlateDecode"))
    d.set_item(COSName.get_pdf_name("F"), arr)
    raw = b"foo"
    payload = zlib.compress(raw).hex().encode("ascii") + b">"
    img = PDInlineImage(d, payload, None)
    assert img.get_filters() == ["ASCIIHexDecode", "FlateDecode"]
    assert img.get_data() == raw


def test_get_filters_empty_when_absent() -> None:
    img = PDInlineImage(_basic_dict(), b"", None)
    assert img.get_filters() == []


# ---------- /D /Decode ----------


def test_get_decode_with_array() -> None:
    d = _basic_dict(width=1, height=1, bpc=1)
    d.set_boolean(COSName.get_pdf_name("IM"), True)
    arr = COSArray()
    arr.add(COSInteger.ONE)
    arr.add(COSInteger.ZERO)
    d.set_item(COSName.get_pdf_name("D"), arr)
    img = PDInlineImage(d, b"\x00", None)
    decode = img.get_decode()
    assert decode is not None
    assert decode.size() == 2


def test_get_decode_returns_none_for_invalid_type() -> None:
    """Mirrors upstream's PDFBOX-fix: malformed PDFs may set /D to a
    non-array (e.g. integer); ``get_decode`` must return ``None`` rather
    than raise."""
    d = _basic_dict(width=1, height=1, bpc=1)
    d.set_boolean(COSName.get_pdf_name("IM"), True)
    d.set_int(COSName.get_pdf_name("D"), 123)
    img = PDInlineImage(d, b"\x00", None)
    assert img.get_decode() is None


def test_get_decode_returns_none_when_absent() -> None:
    d = _basic_dict(width=1, height=1, bpc=1)
    d.set_boolean(COSName.get_pdf_name("IM"), True)
    img = PDInlineImage(d, b"\x00", None)
    assert img.get_decode() is None


# ---------- stencil ----------


def test_is_stencil_round_trip() -> None:
    img = PDInlineImage(_basic_dict(), b"\x00", None)
    assert img.is_stencil() is False
    img.set_stencil(True)
    assert img.is_stencil() is True
    # ``is_image_mask`` mirrors ``is_stencil``
    assert img.is_image_mask() is True


def test_is_stencil_long_form_image_mask() -> None:
    d = _basic_dict()
    d.set_boolean(COSName.get_pdf_name("ImageMask"), True)
    img = PDInlineImage(d, b"\x00", None)
    assert img.is_stencil() is True


# ---------- /I /Interpolate ----------


def test_interpolate_default_false() -> None:
    img = PDInlineImage(_basic_dict(), b"\x00", None)
    assert img.get_interpolate() is False


def test_interpolate_round_trip() -> None:
    img = PDInlineImage(_basic_dict(), b"\x00", None)
    img.set_interpolate(True)
    assert img.get_interpolate() is True


# ---------- create_input_stream stop_filters ----------


def test_create_input_stream_stop_filters_short_circuits() -> None:
    raw = b"unencoded"
    encoded = zlib.compress(raw)
    d = _basic_dict(width=len(raw), height=1, bpc=8)
    d.set_item(COSName.get_pdf_name("F"), COSName.get_pdf_name("FlateDecode"))
    img = PDInlineImage(d, encoded, None)
    with img.create_input_stream(stop_filters=["FlateDecode"]) as stream:
        # Stop before decoding so the still-encoded raw bytes come back.
        assert stream.read() == encoded


# ---------- get_suffix ----------


def test_get_suffix_default_png() -> None:
    img = PDInlineImage(_basic_dict(), b"\x00", None)
    assert img.get_suffix() == "png"


def test_get_suffix_dct_long_name() -> None:
    d = _basic_dict()
    d.set_item(COSName.get_pdf_name("F"), COSName.get_pdf_name("DCTDecode"))
    # Avoid running the filter pipeline by bypassing actual JPEG decoding —
    # the constructor calls FilterFactory which does have DCTDecode wiring;
    # this test only inspects the suffix metadata path. Use empty data so
    # the suffix accessor short-circuits independently of decoder output.
    img = PDInlineImage.__new__(PDInlineImage)
    img._parameters = d
    img._resources = None
    img._raw_data = b""
    img._decoded_data = b""
    assert img.get_suffix() == "jpg"


def test_get_suffix_dct_short_name() -> None:
    d = _basic_dict()
    d.set_item(COSName.get_pdf_name("F"), COSName.get_pdf_name("DCT"))
    img = PDInlineImage.__new__(PDInlineImage)
    img._parameters = d
    img._resources = None
    img._raw_data = b""
    img._decoded_data = b""
    assert img.get_suffix() == "jpg"


def test_get_suffix_ccitt() -> None:
    d = _basic_dict()
    d.set_item(COSName.get_pdf_name("F"), COSName.get_pdf_name("CCF"))
    img = PDInlineImage.__new__(PDInlineImage)
    img._parameters = d
    img._resources = None
    img._raw_data = b""
    img._decoded_data = b""
    assert img.get_suffix() == "tiff"


# ---------- to_pil_image ----------


def test_to_pil_image_devicergb_8bit() -> None:
    width = 2
    height = 2
    # Three bytes per pixel — solid colours so we don't need a real codec.
    pixels = bytes([255, 0, 0,  0, 255, 0,  0, 0, 255,  255, 255, 255])
    d = _basic_dict(width=width, height=height, bpc=8)
    d.set_item(COSName.get_pdf_name("CS"), COSName.get_pdf_name("RGB"))
    img = PDInlineImage(d, pixels, None)
    out = img.to_pil_image()
    assert out is not None
    assert out.size == (2, 2)
    assert out.mode == "RGB"
    assert out.getpixel((0, 0)) == (255, 0, 0)
    assert out.getpixel((1, 1)) == (255, 255, 255)


def test_to_pil_image_devicegray_8bit() -> None:
    width = 4
    height = 1
    pixels = bytes([0, 64, 128, 255])
    d = _basic_dict(width=width, height=height, bpc=8)
    d.set_item(COSName.get_pdf_name("CS"), COSName.get_pdf_name("G"))
    img = PDInlineImage(d, pixels, None)
    out = img.to_pil_image()
    assert out is not None
    assert out.size == (4, 1)


# ---------- COS surface ----------


def test_get_cos_object_returns_parameters() -> None:
    d = _basic_dict()
    img = PDInlineImage(d, b"\x00", None)
    assert img.get_cos_object() is d


# ---------- create_input_stream returns BinaryIO ----------


def test_create_input_stream_is_binary_io() -> None:
    img = PDInlineImage(_basic_dict(), b"abc", None)
    stream = img.create_input_stream()
    assert isinstance(stream, io.BytesIO)
    stream.close()


# ---------- get_resources / is_interpolate mirror methods ----------


def test_get_resources_returns_constructor_argument() -> None:
    """``get_resources`` exposes the page-level ``PDResources`` passed at
    construction time — the same instance used internally for resolving
    named color spaces in inline /CS arrays."""
    from pypdfbox.pdmodel.pd_resources import PDResources

    resources = PDResources()
    img = PDInlineImage(_basic_dict(), b"\x00", resources)
    assert img.get_resources() is resources


def test_get_resources_returns_none_when_not_provided() -> None:
    img = PDInlineImage(_basic_dict(), b"\x00", None)
    assert img.get_resources() is None


def test_is_interpolate_alias_matches_get_interpolate() -> None:
    """``is_interpolate`` mirrors :meth:`PDImageXObject.is_interpolate`
    naming; both readers must agree on the underlying /I (or /Interpolate)
    entry value."""
    img = PDInlineImage(_basic_dict(), b"\x00", None)
    assert img.get_interpolate() is False
    assert img.is_interpolate() is False

    img.set_interpolate(True)
    assert img.get_interpolate() is True
    assert img.is_interpolate() is True


# ---------- /Mask color-key array (raw COSArray accessor) ----------


def test_get_color_key_mask_array_returns_underlying_array() -> None:
    """Mirrors the upstream ``getColorKeyMask()`` shape: returns the raw
    ``COSArray`` rather than a decoded list."""
    d = _basic_dict(width=1, height=1, bpc=1)
    d.set_boolean(COSName.get_pdf_name("IM"), True)
    array = COSArray()
    for value in (4, 17, 200, 255):
        array.add(COSInteger.get(value))
    d.set_item(COSName.get_pdf_name("Mask"), array)
    img = PDInlineImage(d, b"\x00", None)

    fetched = img.get_color_key_mask_array()
    assert isinstance(fetched, COSArray)
    assert fetched is array
    # The decoded list helper continues to work in parallel.
    assert img.get_color_key_mask() == [4, 17, 200, 255]


def test_get_color_key_mask_array_is_none_when_absent() -> None:
    img = PDInlineImage(_basic_dict(), b"\x00", None)
    assert img.get_color_key_mask_array() is None


# ---------- /D /Decode (decoded float helper) ----------


def test_get_decode_as_floats_returns_list_of_floats() -> None:
    """Mirrors :meth:`PDImageXObject.get_decode` shape — convenience
    parallel that returns a ``list[float]`` rather than the raw
    ``COSArray`` exposed by ``get_decode``."""
    d = _basic_dict(width=1, height=1, bpc=1)
    d.set_boolean(COSName.get_pdf_name("IM"), True)
    arr = COSArray()
    arr.add(COSInteger.ONE)
    arr.add(COSInteger.ZERO)
    d.set_item(COSName.get_pdf_name("D"), arr)
    img = PDInlineImage(d, b"\x00", None)

    decoded = img.get_decode_as_floats()
    assert decoded == [1.0, 0.0]
    assert all(isinstance(v, float) for v in decoded)


def test_get_decode_as_floats_returns_none_when_absent() -> None:
    img = PDInlineImage(_basic_dict(), b"\x00", None)
    assert img.get_decode_as_floats() is None


# ---------- /CS raw COS accessor ----------


def test_get_color_space_cos_object_returns_short_name() -> None:
    """Raw ``/CS`` access returns the COSName verbatim (no short→long
    expansion). Mirrors :meth:`PDImageXObject.get_color_space_cos_object`."""
    d = _basic_dict()
    cs_name = COSName.get_pdf_name("RGB")
    d.set_item(COSName.get_pdf_name("CS"), cs_name)
    img = PDInlineImage(d, b"\x00", None)

    raw = img.get_color_space_cos_object()
    # Identity preserved — the short ``/RGB`` form is returned as-is so
    # callers can distinguish abbreviated inline color spaces from the
    # long form.
    assert raw is cs_name
    assert isinstance(raw, COSName)
    assert raw.get_name() == "RGB"


def test_get_color_space_cos_object_returns_long_name_when_only_long_set() -> None:
    """Long-form ``/ColorSpace`` is the fallback when ``/CS`` is absent."""
    d = _basic_dict()
    long_name = COSName.get_pdf_name("DeviceRGB")
    d.set_item(COSName.get_pdf_name("ColorSpace"), long_name)
    img = PDInlineImage(d, b"\x00", None)

    assert img.get_color_space_cos_object() is long_name


def test_get_color_space_cos_object_returns_array_form() -> None:
    """Array color spaces (e.g. ``[/I /DeviceRGB N <hex>]``) come back
    intact — no copy and no short-form expansion."""
    d = _basic_dict()
    array = COSArray()
    array.add(COSName.get_pdf_name("I"))
    array.add(COSName.get_pdf_name("RGB"))
    array.add(COSInteger.get(1))
    d.set_item(COSName.get_pdf_name("CS"), array)
    img = PDInlineImage(d, b"\x00", None)

    raw = img.get_color_space_cos_object()
    assert raw is array


def test_get_color_space_cos_object_returns_none_when_absent() -> None:
    img = PDInlineImage(_basic_dict(), b"\x00", None)
    assert img.get_color_space_cos_object() is None


# ---------- /F raw COS accessor + has_filters() ----------


def test_get_filter_cos_object_returns_single_name() -> None:
    d = _basic_dict()
    name = COSName.get_pdf_name("FlateDecode")
    d.set_item(COSName.get_pdf_name("F"), name)
    img = PDInlineImage(d, zlib.compress(b""), None)

    raw = img.get_filter_cos_object()
    assert raw is name
    assert isinstance(raw, COSName)


def test_get_filter_cos_object_returns_array_form() -> None:
    d = _basic_dict()
    arr = COSArray()
    arr.add(COSName.get_pdf_name("ASCIIHexDecode"))
    arr.add(COSName.get_pdf_name("FlateDecode"))
    d.set_item(COSName.get_pdf_name("F"), arr)
    payload = zlib.compress(b"foo").hex().encode("ascii") + b">"
    img = PDInlineImage(d, payload, None)

    assert img.get_filter_cos_object() is arr


def test_get_filter_cos_object_long_form_fallback() -> None:
    """``/Filter`` (long form) is the fallback when ``/F`` is absent."""
    d = _basic_dict()
    name = COSName.get_pdf_name("FlateDecode")
    d.set_item(COSName.get_pdf_name("Filter"), name)
    img = PDInlineImage(d, zlib.compress(b""), None)

    assert img.get_filter_cos_object() is name


def test_get_filter_cos_object_returns_none_when_absent() -> None:
    img = PDInlineImage(_basic_dict(), b"", None)
    assert img.get_filter_cos_object() is None


def test_has_filters_false_when_no_filter_entry() -> None:
    img = PDInlineImage(_basic_dict(), b"", None)
    assert img.has_filters() is False


def test_has_filters_true_for_single_name() -> None:
    d = _basic_dict()
    d.set_item(COSName.get_pdf_name("F"), COSName.get_pdf_name("FlateDecode"))
    img = PDInlineImage(d, zlib.compress(b""), None)
    assert img.has_filters() is True


def test_has_filters_true_for_non_empty_array() -> None:
    d = _basic_dict()
    arr = COSArray()
    arr.add(COSName.get_pdf_name("FlateDecode"))
    d.set_item(COSName.get_pdf_name("F"), arr)
    img = PDInlineImage(d, zlib.compress(b""), None)
    assert img.has_filters() is True


def test_has_filters_false_for_empty_array() -> None:
    """An empty ``/F`` array — pathological but seen in malformed PDFs —
    must report no filters rather than raising."""
    d = _basic_dict()
    d.set_item(COSName.get_pdf_name("F"), COSArray())
    img = PDInlineImage(d, b"", None)
    assert img.has_filters() is False
    # Mirror cross-check: get_filters() also reports an empty list.
    assert img.get_filters() == []


# ---------- is_jpeg / is_ccitt predicates ----------


def test_is_jpeg_true_for_long_dct_decode() -> None:
    d = _basic_dict()
    d.set_item(COSName.get_pdf_name("F"), COSName.get_pdf_name("DCTDecode"))
    # Bypass the actual filter pipeline — predicate lookup is metadata-only.
    img = PDInlineImage.__new__(PDInlineImage)
    img._parameters = d
    img._resources = None
    img._raw_data = b""
    img._decoded_data = b""
    assert img.is_jpeg() is True
    assert img.is_ccitt() is False


def test_is_jpeg_true_for_short_dct_abbreviation() -> None:
    d = _basic_dict()
    d.set_item(COSName.get_pdf_name("F"), COSName.get_pdf_name("DCT"))
    img = PDInlineImage.__new__(PDInlineImage)
    img._parameters = d
    img._resources = None
    img._raw_data = b""
    img._decoded_data = b""
    assert img.is_jpeg() is True


def test_is_jpeg_false_when_no_filters() -> None:
    img = PDInlineImage(_basic_dict(), b"\x00", None)
    assert img.is_jpeg() is False
    assert img.is_ccitt() is False


def test_is_ccitt_true_for_long_name() -> None:
    d = _basic_dict()
    d.set_item(
        COSName.get_pdf_name("F"), COSName.get_pdf_name("CCITTFaxDecode")
    )
    img = PDInlineImage.__new__(PDInlineImage)
    img._parameters = d
    img._resources = None
    img._raw_data = b""
    img._decoded_data = b""
    assert img.is_ccitt() is True
    assert img.is_jpeg() is False


def test_is_ccitt_true_for_short_abbreviation() -> None:
    d = _basic_dict()
    d.set_item(COSName.get_pdf_name("F"), COSName.get_pdf_name("CCF"))
    img = PDInlineImage.__new__(PDInlineImage)
    img._parameters = d
    img._resources = None
    img._raw_data = b""
    img._decoded_data = b""
    assert img.is_ccitt() is True


def test_is_jpeg_with_flate_returns_false() -> None:
    """A plain FlateDecode inline image is neither JPEG nor CCITT."""
    d = _basic_dict()
    d.set_item(COSName.get_pdf_name("F"), COSName.get_pdf_name("FlateDecode"))
    img = PDInlineImage(d, zlib.compress(b""), None)
    assert img.is_jpeg() is False
    assert img.is_ccitt() is False
    # Suffix dispatch agrees — png is the default for non-JPEG/non-CCITT.
    assert img.get_suffix() == "png"


def test_is_jpeg_inside_filter_chain() -> None:
    """A multi-filter chain that includes DCTDecode still classifies as
    JPEG — the predicate matches if any filter in the chain is DCT."""
    d = _basic_dict()
    arr = COSArray()
    arr.add(COSName.get_pdf_name("ASCIIHexDecode"))
    arr.add(COSName.get_pdf_name("DCTDecode"))
    d.set_item(COSName.get_pdf_name("F"), arr)
    img = PDInlineImage.__new__(PDInlineImage)
    img._parameters = d
    img._resources = None
    img._raw_data = b""
    img._decoded_data = b""
    assert img.is_jpeg() is True
