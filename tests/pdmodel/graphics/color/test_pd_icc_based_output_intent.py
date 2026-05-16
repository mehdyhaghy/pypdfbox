"""Wave 1306 — wire ``PDICCBased`` typed colour-space integration with
``PDOutputIntent``. Covers the deferred line 238 in ``CHANGES.md``:
typed ``get_dest_output_profile_pdiccbased()`` accessor, typed setter
that accepts ``PDICCBased``, and ICC header signature accessors
(``get_device_class`` / ``get_color_space_signature`` /
``get_pcs_signature``) per ICC.1:2010 §7.2.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSName, COSStream
from pypdfbox.pdmodel.common.pd_stream import PDStream
from pypdfbox.pdmodel.graphics.color import PDOutputIntent
from pypdfbox.pdmodel.graphics.color.pd_icc_based import PDICCBased
from pypdfbox.pdmodel.pd_document import PDDocument

# --------------------------------------------------------------------- #
# helpers                                                               #
# --------------------------------------------------------------------- #

def _synthetic_icc_header(
    *,
    device_class: bytes = b"mntr",
    color_space: bytes = b"RGB ",
    pcs: bytes = b"XYZ ",
) -> bytes:
    """Build a minimal 128-byte ICC profile header carrying the magic
    ``"acsp"`` signature at offset 36 (ICC.1:2010 §7.2 table 17) plus
    custom device-class / color-space / PCS tags at the offsets the
    spec assigns.

    Layout:
      bytes 0..3   profile size (zero — we are not validating it)
      bytes 4..11  preferred CMM / version (zero)
      bytes 12..15 device class (table 16)
      bytes 16..19 data colour space (table 18)
      bytes 20..23 profile connection space
      bytes 24..35 creation date/time (zero)
      bytes 36..39 magic ``"acsp"``
      bytes 40..127 remainder (zero)
    """
    assert len(device_class) == 4
    assert len(color_space) == 4
    assert len(pcs) == 4

    header = bytearray(128)
    header[12:16] = device_class
    header[16:20] = color_space
    header[20:24] = pcs
    header[36:40] = b"acsp"
    return bytes(header)


# --------------------------------------------------------------------- #
# round-trip                                                            #
# --------------------------------------------------------------------- #

def test_get_dest_output_profile_pdiccbased_returns_typed_wrapper() -> None:
    doc = PDDocument()
    intent = PDOutputIntent(doc, _synthetic_icc_header())

    typed = intent.get_dest_output_profile_pdiccbased()

    assert typed is not None
    assert isinstance(typed, PDICCBased)


def test_get_dest_output_profile_pdiccbased_absent_returns_none() -> None:
    intent = PDOutputIntent()

    assert intent.get_dest_output_profile_pdiccbased() is None


def test_get_dest_output_profile_pdiccbased_round_trips_cos() -> None:
    doc = PDDocument()
    intent = PDOutputIntent(doc, _synthetic_icc_header())

    typed = intent.get_dest_output_profile_pdiccbased()

    # Slot 1 of the PDICCBased array IS the original /DestOutputProfile
    # COSStream — no copying, the typed view is just a thin wrapper.
    assert typed is not None
    assert typed.get_pdstream() is intent.get_dest_output_profile_cos()


def test_get_dest_output_profile_pdiccbased_propagates_n() -> None:
    doc = PDDocument()
    # Synthesise a CMYK profile so /N is 4 (not the RGB default 3).
    intent = PDOutputIntent(
        doc, _synthetic_icc_header(color_space=b"CMYK")
    )

    typed = intent.get_dest_output_profile_pdiccbased()

    assert typed is not None
    assert typed.get_n() == 4


def test_get_dest_output_profile_pdiccbased_rejects_wrong_cos_shape() -> None:
    intent = PDOutputIntent()
    intent.get_cos_object().set_item(
        COSName.get_pdf_name("DestOutputProfile"),
        COSName.get_pdf_name("Bad"),
    )

    with pytest.raises(TypeError, match="DestOutputProfile type"):
        intent.get_dest_output_profile_pdiccbased()


# --------------------------------------------------------------------- #
# typed setter                                                          #
# --------------------------------------------------------------------- #

def test_set_dest_output_profile_accepts_pdiccbased() -> None:
    # Hand-build an ICCBased so the typed setter has a real instance.
    icc_array = COSArray()
    icc_array.add(COSName.get_pdf_name("ICCBased"))
    icc_stream = COSStream()
    icc_stream.set_raw_data(_synthetic_icc_header(color_space=b"GRAY"))
    icc_stream.set_int(COSName.get_pdf_name("N"), 1)
    icc_array.add(icc_stream)
    icc = PDICCBased(icc_array)

    intent = PDOutputIntent()
    intent.set_dest_output_profile(icc)

    # /DestOutputProfile is the very same COSStream pypdfbox stored
    # inside the ICCBased array.
    assert intent.get_dest_output_profile_cos() is icc_stream

    # And round-tripping through the typed accessor returns an
    # equivalent PDICCBased view onto that same stream.
    typed = intent.get_dest_output_profile_pdiccbased()
    assert typed is not None
    assert typed.get_pdstream() is icc_stream
    assert typed.get_n() == 1


def test_set_dest_output_profile_pdiccbased_without_stream_raises() -> None:
    # An ICCBased whose slot 1 is a non-stream value — pathological,
    # but exercises the guard. We bypass the constructor's defaults by
    # building the array by hand.
    icc_array = COSArray()
    icc_array.add(COSName.get_pdf_name("ICCBased"))
    icc_array.add(COSStream())
    icc = PDICCBased(icc_array)
    # Knock the stream out of slot 1 *after* construction so we don't
    # trip the constructor's get_initial_color path.
    icc_array.set(1, COSName.get_pdf_name("Bogus"))

    intent = PDOutputIntent()
    with pytest.raises(ValueError, match="has no embedded ICC stream"):
        intent.set_dest_output_profile(icc)


def test_set_dest_output_profile_pdstream_still_supported() -> None:
    """Regression — back-compat path through PDStream is unchanged."""
    intent = PDOutputIntent()
    raw = COSStream()
    raw.set_raw_data(_synthetic_icc_header())
    pdstream = PDStream(raw)

    intent.set_dest_output_profile(pdstream)
    assert intent.get_dest_output_profile_cos() is raw


def test_set_dest_output_profile_none_clears_entry() -> None:
    """Regression — passing ``None`` removes ``/DestOutputProfile``."""
    doc = PDDocument()
    intent = PDOutputIntent(doc, _synthetic_icc_header())
    assert intent.has_dest_output_profile()

    intent.set_dest_output_profile(None)
    assert not intent.has_dest_output_profile()


def test_set_dest_output_profile_rejects_invalid_type() -> None:
    intent = PDOutputIntent()
    with pytest.raises(
        TypeError, match="expected PDStream, COSStream, or None"
    ):
        intent.set_dest_output_profile(42)  # type: ignore[arg-type]


# --------------------------------------------------------------------- #
# ICC header signature accessors                                        #
# --------------------------------------------------------------------- #

def test_pdiccbased_get_device_class_returns_scanner_signature() -> None:
    icc_array = COSArray()
    icc_array.add(COSName.get_pdf_name("ICCBased"))
    stream = COSStream()
    stream.set_raw_data(_synthetic_icc_header(device_class=b"scnr"))
    icc_array.add(stream)
    icc = PDICCBased(icc_array)

    assert icc.get_device_class() == "scnr"


def test_pdiccbased_get_device_class_round_trips_through_output_intent() -> None:
    doc = PDDocument()
    intent = PDOutputIntent(
        doc, _synthetic_icc_header(device_class=b"prtr")
    )

    typed = intent.get_dest_output_profile_pdiccbased()
    assert typed is not None
    assert typed.get_device_class() == "prtr"


def test_pdiccbased_get_color_space_signature_rgb() -> None:
    doc = PDDocument()
    intent = PDOutputIntent(doc, _synthetic_icc_header(color_space=b"RGB "))

    typed = intent.get_dest_output_profile_pdiccbased()
    assert typed is not None
    assert typed.get_color_space_signature() == "RGB "


def test_pdiccbased_get_color_space_signature_cmyk() -> None:
    doc = PDDocument()
    intent = PDOutputIntent(doc, _synthetic_icc_header(color_space=b"CMYK"))

    typed = intent.get_dest_output_profile_pdiccbased()
    assert typed is not None
    assert typed.get_color_space_signature() == "CMYK"


def test_pdiccbased_get_pcs_signature_xyz() -> None:
    doc = PDDocument()
    intent = PDOutputIntent(doc, _synthetic_icc_header(pcs=b"XYZ "))

    typed = intent.get_dest_output_profile_pdiccbased()
    assert typed is not None
    assert typed.get_pcs_signature() == "XYZ "


def test_pdiccbased_get_pcs_signature_lab() -> None:
    doc = PDDocument()
    intent = PDOutputIntent(doc, _synthetic_icc_header(pcs=b"Lab "))

    typed = intent.get_dest_output_profile_pdiccbased()
    assert typed is not None
    assert typed.get_pcs_signature() == "Lab "


def test_pdiccbased_header_accessors_return_none_without_profile() -> None:
    icc_array = COSArray()
    icc_array.add(COSName.get_pdf_name("ICCBased"))
    stream = COSStream()  # empty — no header bytes
    icc_array.add(stream)
    icc = PDICCBased(icc_array)

    assert icc.get_device_class() is None
    assert icc.get_color_space_signature() is None
    assert icc.get_pcs_signature() is None


def test_pdiccbased_header_accessors_return_none_when_truncated() -> None:
    # 18-byte profile body — has the colour-space signature start but
    # is too short to read PCS (need 24 bytes) or even all 4 bytes of
    # the colour-space tag (need 20 bytes).
    icc_array = COSArray()
    icc_array.add(COSName.get_pdf_name("ICCBased"))
    stream = COSStream()
    stream.set_raw_data(b"\x00" * 18)
    icc_array.add(stream)
    icc = PDICCBased(icc_array)

    assert icc.get_device_class() == "\x00\x00\x00\x00"  # 16 bytes is plenty
    assert icc.get_color_space_signature() is None  # offset 16, need 20
    assert icc.get_pcs_signature() is None  # offset 20, need 24
