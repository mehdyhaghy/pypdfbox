"""Ported parity tests for ``PDICCBased`` translated from upstream
Apache PDFBox 3.0.x ``PDICCBasedTest.java``.

Upstream test set is intentionally tiny (constructor smoke). We add a
small handful of mechanical checks for the surface methods this port
exposes that upstream covers indirectly through other tests
(``getColorSpaceType``, ``isSRGB``, ``setAlternateColorSpaces``,
``create``, ``getName``, ``toString``).
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSName, COSStream
from pypdfbox.pdmodel.graphics.color.pd_device_cmyk import PDDeviceCMYK
from pypdfbox.pdmodel.graphics.color.pd_device_gray import PDDeviceGray
from pypdfbox.pdmodel.graphics.color.pd_device_rgb import PDDeviceRGB
from pypdfbox.pdmodel.graphics.color.pd_icc_based import (
    TYPE_CMYK,
    TYPE_GRAY,
    TYPE_RGB,
    PDICCBased,
)


# Translated from PDICCBasedTest.testConstructor (PDFBOX-2812).
def test_constructor() -> None:
    icc_based = PDICCBased()
    assert icc_based.get_name() == "ICCBased"
    assert icc_based.get_pd_stream() is not None


# ---------- create() factory smoke ----------


def test_create_round_trips_array_form() -> None:
    arr = COSArray()
    arr.add(COSName.get_pdf_name("ICCBased"))
    stream = COSStream()
    stream.set_int("N", 3)
    arr.add(stream)
    cs = PDICCBased.create(arr, None)
    assert isinstance(cs, PDICCBased)
    assert cs.get_n() == 3


def test_create_rejects_too_short_array() -> None:
    arr = COSArray()
    arr.add(COSName.get_pdf_name("ICCBased"))
    with pytest.raises(OSError, match="must have two elements"):
        PDICCBased.create(arr, None)


def test_create_rejects_non_stream_second_element() -> None:
    arr = COSArray()
    arr.add(COSName.get_pdf_name("ICCBased"))
    arr.add(COSName.get_pdf_name("NotAStream"))
    with pytest.raises(OSError, match="must have a stream"):
        PDICCBased.create(arr, None)


# ---------- get_color_space_type ----------


def test_get_color_space_type_falls_back_to_n_for_gray() -> None:
    cs = PDICCBased()
    cs.set_n(1)
    assert cs.get_color_space_type() == TYPE_GRAY


def test_get_color_space_type_falls_back_to_n_for_rgb() -> None:
    cs = PDICCBased()
    cs.set_n(3)
    assert cs.get_color_space_type() == TYPE_RGB


def test_get_color_space_type_falls_back_to_n_for_cmyk() -> None:
    cs = PDICCBased()
    cs.set_n(4)
    assert cs.get_color_space_type() == TYPE_CMYK


def test_get_color_space_type_returns_minus_one_for_unknown_n() -> None:
    cs = PDICCBased()
    cs.set_n(7)
    assert cs.get_color_space_type() == -1


def test_get_color_space_type_reads_signature_from_profile_header() -> None:
    # Forge a minimal 128-byte ICC header with the RGB signature in
    # bytes 16..19. The remaining bytes can be anything since
    # get_color_space_type only consults this slice.
    header = bytearray(128)
    header[16:20] = b"RGB "
    cs = PDICCBased()
    underlying = cs.get_pdstream()
    assert isinstance(underlying, COSStream)
    underlying.set_raw_data(bytes(header))
    cs.set_n(1)  # mismatch on purpose — header signature wins.
    assert cs.get_color_space_type() == TYPE_RGB


def test_get_color_space_type_reads_cmyk_signature() -> None:
    header = bytearray(128)
    header[16:20] = b"CMYK"
    cs = PDICCBased()
    underlying = cs.get_pdstream()
    assert isinstance(underlying, COSStream)
    underlying.set_raw_data(bytes(header))
    assert cs.get_color_space_type() == TYPE_CMYK


# ---------- is_srgb ----------


def test_is_srgb_true_for_srgb_device_model() -> None:
    header = bytearray(128)
    # Bytes 84..87 carry the deviceModel ASCII signature.
    header[84:88] = b"sRGB"
    cs = PDICCBased()
    underlying = cs.get_pdstream()
    assert isinstance(underlying, COSStream)
    underlying.set_raw_data(bytes(header))
    assert cs.is_srgb() is True


def test_is_srgb_false_when_no_profile_and_alternate_not_rgb() -> None:
    cs = PDICCBased()
    cs.set_alternate(PDDeviceCMYK.INSTANCE)
    assert cs.is_srgb() is False


def test_is_srgb_true_when_alternate_is_device_rgb() -> None:
    cs = PDICCBased()
    cs.set_alternate(PDDeviceRGB.INSTANCE)
    assert cs.is_srgb() is True


def test_is_srgb_false_for_default_unset_state() -> None:
    cs = PDICCBased()
    assert cs.is_srgb() is False


# ---------- set_alternate_color_spaces (plural list form) ----------


def test_set_alternate_color_spaces_writes_array() -> None:
    cs = PDICCBased()
    cs.set_alternate_color_spaces(
        [PDDeviceRGB.INSTANCE, PDDeviceGray.INSTANCE]
    )
    underlying = cs.get_pdstream()
    assert isinstance(underlying, COSStream)
    alt = underlying.get_dictionary_object("Alternate")
    assert isinstance(alt, COSArray)
    # Each list entry contributes one COSName slot for a device
    # color space.
    assert alt.size() == 2


def test_set_alternate_color_spaces_none_clears_entry() -> None:
    cs = PDICCBased()
    cs.set_alternate_color_spaces([PDDeviceRGB.INSTANCE])
    cs.set_alternate_color_spaces(None)
    # Cleared entry — get_alternate now resolves to None.
    assert cs.get_alternate() is None


# ---------- toString ----------


def test_to_string_form() -> None:
    cs = PDICCBased()
    cs.set_n(3)
    assert str(cs) == "ICCBased{numberOfComponents: 3}"


def test_to_string_after_set_n() -> None:
    cs = PDICCBased()
    cs.set_n(4)
    assert str(cs) == "ICCBased{numberOfComponents: 4}"


# ---------- to_string explicit accessor ----------


def test_to_string_method_matches_str() -> None:
    cs = PDICCBased()
    cs.set_n(3)
    assert cs.to_string() == str(cs)
    assert cs.to_string() == "ICCBased{numberOfComponents: 3}"


# ---------- check_array (public alias) ----------


def test_check_array_accepts_well_formed_array() -> None:
    arr = COSArray()
    arr.add(COSName.get_pdf_name("ICCBased"))
    arr.add(COSStream())
    # Should not raise.
    PDICCBased.check_array(arr)


def test_check_array_rejects_short_array() -> None:
    arr = COSArray()
    arr.add(COSName.get_pdf_name("ICCBased"))
    with pytest.raises(OSError, match="must have two elements"):
        PDICCBased.check_array(arr)


def test_check_array_rejects_non_stream_second() -> None:
    arr = COSArray()
    arr.add(COSName.get_pdf_name("ICCBased"))
    arr.add(COSName.get_pdf_name("NotAStream"))
    with pytest.raises(OSError, match="must have a stream"):
        PDICCBased.check_array(arr)


# ---------- is_s_rgb (static helper) ----------


def test_is_s_rgb_true_for_srgb_device_model() -> None:
    header = bytearray(128)
    header[84:88] = b"sRGB"
    assert PDICCBased.is_s_rgb(bytes(header)) is True


def test_is_s_rgb_false_for_other_device_model() -> None:
    header = bytearray(128)
    header[84:88] = b"ABCD"
    assert PDICCBased.is_s_rgb(bytes(header)) is False


def test_is_s_rgb_false_for_short_buffer() -> None:
    assert PDICCBased.is_s_rgb(b"") is False
    assert PDICCBased.is_s_rgb(b"\x00" * 80) is False


# ---------- int_to_big_endian ----------


def test_int_to_big_endian_writes_four_bytes() -> None:
    buf = bytearray(8)
    PDICCBased.int_to_big_endian(0x12345678, buf, 2)
    assert buf == bytearray(b"\x00\x00\x12\x34\x56\x78\x00\x00")


def test_int_to_big_endian_truncates_to_low_32_bits() -> None:
    buf = bytearray(4)
    PDICCBased.int_to_big_endian(0x1FFFFFFFF, buf, 0)
    # 0x1_FFFFFFFF & 0xFFFFFFFF == 0xFFFFFFFF
    assert buf == bytearray(b"\xff\xff\xff\xff")


# ---------- ensure_display_profile ----------


def test_ensure_display_profile_returns_buffer_unchanged_when_already_display() -> None:
    header = bytearray(128)
    header[12:16] = b"mntr"  # icSigDisplayClass
    header[64:68] = (0).to_bytes(4, "big")  # Perceptual
    out = PDICCBased.ensure_display_profile(bytes(header))
    assert out[12:16] == b"mntr"


def test_ensure_display_profile_patches_perceptual_non_display() -> None:
    header = bytearray(128)
    header[12:16] = b"scnr"  # scanner class
    header[64:68] = (0).to_bytes(4, "big")  # Perceptual
    out = PDICCBased.ensure_display_profile(bytes(header))
    assert out[12:16] == b"mntr"


def test_ensure_display_profile_leaves_non_perceptual_unchanged() -> None:
    header = bytearray(128)
    header[12:16] = b"scnr"
    header[64:68] = (1).to_bytes(4, "big")  # Relative Colorimetric
    out = PDICCBased.ensure_display_profile(bytes(header))
    assert out[12:16] == b"scnr"


def test_ensure_display_profile_returns_short_buffer_unchanged() -> None:
    short = b"\x00" * 32
    assert PDICCBased.ensure_display_profile(short) == short


# ---------- fallback_to_alternate_color_space ----------


def test_fallback_to_alternate_color_space_returns_explicit_alternate() -> None:
    cs = PDICCBased()
    cs.set_alternate(PDDeviceCMYK.INSTANCE)
    fallback = cs.fallback_to_alternate_color_space(None)
    assert fallback is not None
    assert fallback.get_name() == "DeviceCMYK"


def test_fallback_to_alternate_color_space_infers_from_n_one() -> None:
    cs = PDICCBased()
    cs.set_n(1)
    fallback = cs.fallback_to_alternate_color_space(None)
    assert fallback is PDDeviceGray.INSTANCE


def test_fallback_to_alternate_color_space_infers_from_n_three() -> None:
    cs = PDICCBased()
    cs.set_n(3)
    fallback = cs.fallback_to_alternate_color_space(None)
    assert fallback is PDDeviceRGB.INSTANCE


def test_fallback_to_alternate_color_space_infers_from_n_four() -> None:
    cs = PDICCBased()
    cs.set_n(4)
    fallback = cs.fallback_to_alternate_color_space(None)
    assert fallback is PDDeviceCMYK.INSTANCE


def test_fallback_to_alternate_color_space_unknown_n_returns_none() -> None:
    cs = PDICCBased()
    cs.set_n(7)
    assert cs.fallback_to_alternate_color_space(None) is None


def test_fallback_to_alternate_color_space_accepts_error_argument() -> None:
    cs = PDICCBased()
    cs.set_n(3)
    # error arg is surface-only — must not change behaviour.
    fallback = cs.fallback_to_alternate_color_space(OSError("boom"))
    assert fallback is PDDeviceRGB.INSTANCE


# ---------- load_icc_profile ----------


def test_load_icc_profile_returns_empty_when_no_body() -> None:
    cs = PDICCBased()
    assert cs.load_icc_profile() == b""


def test_load_icc_profile_passes_through_well_formed_display_profile() -> None:
    header = bytearray(128)
    header[12:16] = b"mntr"
    header[64:68] = (1).to_bytes(4, "big")  # not perceptual
    cs = PDICCBased()
    underlying = cs.get_pdstream()
    assert isinstance(underlying, COSStream)
    underlying.set_raw_data(bytes(header))
    out = cs.load_icc_profile()
    assert out[12:16] == b"mntr"


def test_load_icc_profile_patches_perceptual_non_display_profile() -> None:
    header = bytearray(128)
    header[12:16] = b"scnr"
    header[64:68] = (0).to_bytes(4, "big")
    cs = PDICCBased()
    underlying = cs.get_pdstream()
    assert isinstance(underlying, COSStream)
    underlying.set_raw_data(bytes(header))
    out = cs.load_icc_profile()
    assert out[12:16] == b"mntr"


# ---------- clamp_colors ----------


def test_clamp_colors_uses_default_zero_one_range() -> None:
    cs = PDICCBased()
    cs.set_n(3)
    assert cs.clamp_colors([-0.5, 0.5, 1.5]) == [0.0, 0.5, 1.0]


def test_clamp_colors_honours_explicit_range() -> None:
    cs = PDICCBased()
    cs.set_n(3)
    rng = COSArray()
    from pypdfbox.cos import COSFloat

    for v in (-2.0, 2.0, 0.0, 1.0, -3.0, 3.0):
        rng.add(COSFloat(v))
    cs.set_range(rng)
    out = cs.clamp_colors([-5.0, 0.5, 4.0])
    assert out == [-2.0, 0.5, 3.0]


def test_clamp_colors_preserves_input_length() -> None:
    cs = PDICCBased()
    cs.set_n(3)
    out = cs.clamp_colors([0.5])
    assert out == [0.5]


# ---------- to_rgb_image / to_raw_image overrides ----------


def test_to_rgb_image_returns_pillow_image() -> None:
    pytest.importorskip("PIL")
    cs = PDICCBased()
    cs.set_n(3)
    cs.set_alternate(PDDeviceRGB.INSTANCE)
    raster = bytes([255, 0, 0, 0, 255, 0])  # 2x1 pixels
    img = cs.to_rgb_image(raster, 2, 1)
    assert img is not None
    assert img.size == (2, 1)


def test_to_raw_image_returns_pillow_image() -> None:
    pytest.importorskip("PIL")
    cs = PDICCBased()
    cs.set_n(3)
    cs.set_alternate(PDDeviceRGB.INSTANCE)
    raster = bytes([255, 0, 0, 0, 255, 0])
    img = cs.to_raw_image(raster, 2, 1)
    assert img is not None
    assert img.size == (2, 1)
