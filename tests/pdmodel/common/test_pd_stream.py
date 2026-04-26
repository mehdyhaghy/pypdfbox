from __future__ import annotations

import io
import zlib

from pypdfbox.cos import COSArray, COSName, COSStream
from pypdfbox.pdmodel.common import PDStream


def test_wraps_existing_cos_stream_and_returns_cos_object() -> None:
    cos_stream = COSStream()
    stream = PDStream(cos_stream)
    assert stream.get_cos_object() is cos_stream


def test_embeds_bytes_and_reports_current_body_length() -> None:
    stream = PDStream(input_data=b"abc123")
    assert stream.get_length() == 6
    assert stream.to_byte_array() == b"abc123"


def test_embeds_binary_stream_and_closes_input_quietly() -> None:
    source = io.BytesIO(b"payload")
    stream = PDStream(None, source)
    assert source.closed
    assert stream.create_raw_input_stream().read() == b"payload"


def test_set_filters_normalizes_single_name_to_array() -> None:
    stream = PDStream(input_data=b"abc")
    stream.set_filters(COSName.FLATE_DECODE)  # type: ignore[attr-defined]
    raw_filter = stream.get_cos_object().get_dictionary_object(COSName.FILTER)  # type: ignore[attr-defined]
    assert isinstance(raw_filter, COSArray)
    assert stream.get_filters() == [COSName.FLATE_DECODE]  # type: ignore[attr-defined]


def test_create_input_stream_decodes_registered_filters() -> None:
    encoded = zlib.compress(b"decoded")
    stream = PDStream(input_data=encoded, filters=COSName.FLATE_DECODE)  # type: ignore[attr-defined]
    assert stream.create_input_stream().read() == b"decoded"


def test_create_input_stream_stops_before_stop_filter() -> None:
    encoded = zlib.compress(b"decoded")
    stream = PDStream(input_data=encoded, filters=COSName.FLATE_DECODE)  # type: ignore[attr-defined]
    assert stream.create_input_stream(["FlateDecode"]).read() == encoded


def test_decoded_stream_length_round_trip() -> None:
    stream = PDStream(input_data=b"abc")
    assert stream.get_decoded_stream_length() == -1
    stream.set_decoded_stream_length(12)
    assert stream.get_decoded_stream_length() == 12
