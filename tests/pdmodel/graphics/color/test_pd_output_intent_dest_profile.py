from __future__ import annotations

import logging

from pypdfbox.cos import COSName, COSStream
from pypdfbox.pdmodel.common.pd_stream import PDStream
from pypdfbox.pdmodel.graphics.color import PDOutputIntent


_DEST_OUTPUT_PROFILE = COSName.get_pdf_name("DestOutputProfile")
_N = COSName.get_pdf_name("N")


def _icc_with_magic(payload_extra: bytes = b"\x00" * 64) -> bytes:
    # Build a byte string with the ICC "acsp" magic at offset 36 so the
    # signature sniff in set_data is satisfied.
    head = b"\x00" * 36
    return head + b"acsp" + payload_extra


def test_get_dest_output_profile_absent_returns_none() -> None:
    intent = PDOutputIntent()
    assert intent.get_dest_output_profile() is None


def test_get_dest_output_profile_present_returns_pd_stream() -> None:
    intent = PDOutputIntent()
    raw = COSStream()
    intent.get_cos_object().set_item(_DEST_OUTPUT_PROFILE, raw)
    wrapped = intent.get_dest_output_profile()
    assert isinstance(wrapped, PDStream)
    assert wrapped.get_cos_object() is raw


def test_set_dest_output_profile_none_removes_entry() -> None:
    intent = PDOutputIntent()
    intent.set_dest_output_profile(COSStream())
    assert intent.get_dest_output_profile() is not None
    intent.set_dest_output_profile(None)
    assert intent.get_dest_output_profile() is None
    assert intent.get_cos_object().get_dictionary_object(_DEST_OUTPUT_PROFILE) is None


def test_set_dest_output_profile_pd_stream_round_trip() -> None:
    intent = PDOutputIntent()
    pd_stream = PDStream()
    intent.set_dest_output_profile(pd_stream)
    fetched = intent.get_dest_output_profile()
    assert isinstance(fetched, PDStream)
    assert fetched.get_cos_object() is pd_stream.get_cos_object()


def test_set_data_populates_profile_and_n() -> None:
    intent = PDOutputIntent()
    blob = _icc_with_magic()
    intent.set_data(blob, num_components=3)
    cos = intent.get_cos_object().get_dictionary_object(_DEST_OUTPUT_PROFILE)
    assert isinstance(cos, COSStream)
    assert cos.get_int(_N) == 3
    # raw bytes round-trip
    wrapped = intent.get_dest_output_profile()
    assert wrapped is not None
    assert wrapped.to_byte_array() == blob


def test_set_data_without_acsp_magic_is_lenient(
    caplog: logging.LogCaptureFixture,
) -> None:
    intent = PDOutputIntent()
    blob = b"not an icc profile, no magic here"
    with caplog.at_level(logging.WARNING, logger="pypdfbox.pdmodel.graphics.color.pd_output_intent"):
        intent.set_data(blob, num_components=4)
    cos = intent.get_cos_object().get_dictionary_object(_DEST_OUTPUT_PROFILE)
    assert isinstance(cos, COSStream)
    assert cos.get_int(_N) == 4
    wrapped = intent.get_dest_output_profile()
    assert wrapped is not None
    assert wrapped.to_byte_array() == blob
    assert any("acsp" in rec.getMessage() for rec in caplog.records)
