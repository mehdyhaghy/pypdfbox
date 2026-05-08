"""
Filter encode/decode integration on ``COSStream`` — exercises the
``pypdfbox.filter`` plumbing wired into ``create_output_stream(filters)``
and ``create_input_stream()``.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSName, COSStream


def test_round_trip_no_filter_returns_written_bytes() -> None:
    payload = b"hello, world!"
    with COSStream() as s:
        with s.create_output_stream() as out:
            out.write(payload)
        assert s.create_input_stream().read() == payload
        assert s.to_byte_array() == payload
        assert s.to_raw_byte_array() == payload


def test_flate_decode_round_trip() -> None:
    payload = b"the quick brown fox jumps over the lazy dog" * 8
    with COSStream() as s:
        with s.create_output_stream(COSName.FLATE_DECODE) as out:  # type: ignore[attr-defined]
            out.write(payload)
        # /Filter is recorded.
        assert s.get_filter_list() == [COSName.FLATE_DECODE]  # type: ignore[attr-defined]
        # Raw bytes are compressed (different from payload, smaller for
        # this redundant input).
        raw = s.to_raw_byte_array()
        assert raw != payload
        assert len(raw) < len(payload)
        # Decoded round-trip.
        assert s.to_byte_array() == payload
        assert s.create_input_stream().read() == payload


def test_multi_filter_chain_ascii85_then_flate_round_trip() -> None:
    payload = b"chain me through both filters please" * 4
    with COSStream() as s:
        # Decoding order: ASCII85 first (outermost), then Flate. So
        # encoding goes Flate first, then ASCII85.
        with s.create_output_stream(["ASCII85Decode", "FlateDecode"]) as out:
            out.write(payload)
        names = [n.name for n in s.get_filter_list()]
        assert names == ["ASCII85Decode", "FlateDecode"]
        # Raw bytes end with ASCII85 terminator.
        raw = s.to_raw_byte_array()
        assert raw.endswith(b"~>")
        # Round-trip yields the original payload.
        assert s.to_byte_array() == payload


def test_empty_stream_to_byte_array_returns_empty_bytes() -> None:
    with COSStream() as s:
        assert s.to_byte_array() == b""
        assert s.to_raw_byte_array() == b""


def test_create_input_stream_on_empty_stream_raises() -> None:
    with COSStream() as s, pytest.raises(OSError):
        s.create_input_stream()


def test_set_data_with_filters_encodes_on_write() -> None:
    payload = b"set_data convenience helper"
    with COSStream() as s:
        s.set_data(payload, [COSName.FLATE_DECODE])  # type: ignore[attr-defined]
        assert s.get_filter_list() == [COSName.FLATE_DECODE]  # type: ignore[attr-defined]
        assert s.to_byte_array() == payload


def test_set_data_without_filters_stores_raw() -> None:
    payload = b"raw bytes only"
    with COSStream() as s:
        s.set_data(payload)
        assert s.get_filter_list() == []
        assert s.to_raw_byte_array() == payload
        assert s.to_byte_array() == payload


def test_create_input_stream_with_stop_filter_short_circuits() -> None:
    # Encode through Flate, then ask the reader to stop *before* applying
    # the FlateDecode filter — we should get back the raw compressed bytes.
    payload = b"image-like payload"
    with COSStream() as s:
        with s.create_output_stream(COSName.FLATE_DECODE) as out:  # type: ignore[attr-defined]
            out.write(payload)
        raw = s.to_raw_byte_array()
        assert s.create_input_stream(stop_filters=["FlateDecode"]).read() == raw


def test_create_output_stream_accepts_cos_array_of_names() -> None:
    payload = b"cos array form of filters"
    chain = COSArray(
        [COSName.get_pdf_name("ASCII85Decode"), COSName.get_pdf_name("FlateDecode")]
    )
    with COSStream() as s:
        with s.create_output_stream(chain) as out:
            out.write(payload)
        assert s.to_byte_array() == payload
