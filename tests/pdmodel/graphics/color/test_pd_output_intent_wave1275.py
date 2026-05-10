"""Wave 1275 — PDOutputIntent.configure_output_profile public helper."""

from __future__ import annotations

import io

import pytest

from pypdfbox.cos import COSName, COSStream
from pypdfbox.pdmodel.common.pd_stream import PDStream
from pypdfbox.pdmodel.graphics.color.pd_output_intent import PDOutputIntent
from pypdfbox.pdmodel.pd_document import PDDocument

_DEST_OUTPUT_PROFILE = COSName.get_pdf_name("DestOutputProfile")
_N = COSName.get_pdf_name("N")


def _icc_bytes(num_components: int = 3) -> bytes:
    """Build a minimum-viable ICC header for the colour-space sniffer."""
    sig_map = {1: b"GRAY", 3: b"RGB ", 4: b"CMYK"}
    header = bytearray(128)
    header[16:20] = sig_map[num_components]
    header[36:40] = b"acsp"
    return bytes(header)


def test_configure_returns_pdstream_with_n() -> None:
    intent = PDOutputIntent()
    doc = PDDocument()
    profile = _icc_bytes(num_components=3)

    result = intent.configure_output_profile(doc, profile)

    assert isinstance(result, PDStream)
    cos = intent.get_cos_object().get_dictionary_object(_DEST_OUTPUT_PROFILE)
    assert isinstance(cos, COSStream)
    assert cos.get_int(_N) == 3


def test_configure_accepts_input_stream_like() -> None:
    intent = PDOutputIntent()
    doc = PDDocument()
    profile_io = io.BytesIO(_icc_bytes(num_components=4))

    result = intent.configure_output_profile(doc, profile_io)

    assert isinstance(result, PDStream)
    assert result.get_cos_object().get_int(_N) == 4


def test_configure_with_explicit_num_components_overrides_inference() -> None:
    intent = PDOutputIntent()
    doc = PDDocument()
    profile = _icc_bytes(num_components=3)  # header says RGB

    result = intent.configure_output_profile(doc, profile, num_components=5)

    assert result.get_cos_object().get_int(_N) == 5


def test_configure_raises_on_unrecognised_colourspace_signature() -> None:
    intent = PDOutputIntent()
    doc = PDDocument()
    bad = bytearray(_icc_bytes(num_components=3))
    bad[16:20] = b"XXXX"  # not in the sniffer table

    with pytest.raises(ValueError, match="numComponents"):
        intent.configure_output_profile(doc, bytes(bad))


def test_configure_swaps_existing_dest_output_profile() -> None:
    intent = PDOutputIntent()
    doc = PDDocument()
    intent.set_data(_icc_bytes(num_components=3), num_components=3)
    first = intent.get_cos_object().get_dictionary_object(_DEST_OUTPUT_PROFILE)

    new_profile = _icc_bytes(num_components=4)
    intent.configure_output_profile(doc, new_profile)
    second = intent.get_cos_object().get_dictionary_object(_DEST_OUTPUT_PROFILE)

    assert isinstance(second, COSStream)
    assert second is not first
    assert second.get_int(_N) == 4
