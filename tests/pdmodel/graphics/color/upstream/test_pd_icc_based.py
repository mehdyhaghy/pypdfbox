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
