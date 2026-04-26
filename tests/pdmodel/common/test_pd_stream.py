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


def test_create_output_stream_with_filter_encodes_on_close() -> None:
    stream = PDStream()
    with stream.create_output_stream(COSName.FLATE_DECODE) as out:  # type: ignore[attr-defined]
        out.write(b"compress me")
    # /Filter is now set, raw bytes are compressed, decoded matches.
    assert stream.get_filters() == [COSName.FLATE_DECODE]  # type: ignore[attr-defined]
    assert stream.to_byte_array() == b"compress me"
    assert stream.create_raw_input_stream().read() != b"compress me"


def test_create_output_stream_with_chain_encodes_in_reverse() -> None:
    stream = PDStream()
    with stream.create_output_stream(["ASCII85Decode", "FlateDecode"]) as out:
        out.write(b"chained payload")
    assert [n.name for n in stream.get_filters()] == ["ASCII85Decode", "FlateDecode"]
    assert stream.to_byte_array() == b"chained payload"


def test_to_byte_array_on_empty_stream_returns_empty_bytes() -> None:
    stream = PDStream()
    assert stream.to_byte_array() == b""


def test_create_input_stream_on_empty_stream_returns_empty_bytes_io() -> None:
    stream = PDStream()
    assert stream.create_input_stream().read() == b""


def test_get_decode_parms_absent_returns_none() -> None:
    stream = PDStream(input_data=b"x")
    assert stream.get_decode_parms() is None


def test_set_and_get_decode_parms_single_dict() -> None:
    from pypdfbox.cos import COSDictionary

    stream = PDStream(input_data=b"x")
    parms = COSDictionary()
    parms.set_int("Predictor", 12)
    stream.set_decode_parms(parms)

    out = stream.get_decode_parms()
    assert out is not None
    assert len(out) == 1
    assert out[0].get_int("Predictor") == 12


def test_set_and_get_decode_parms_chain() -> None:
    from pypdfbox.cos import COSDictionary

    stream = PDStream(input_data=b"x")
    p1 = COSDictionary()
    p1.set_int("Predictor", 1)
    p2 = COSDictionary()
    p2.set_int("Predictor", 12)
    stream.set_decode_parms([p1, p2])

    out = stream.get_decode_parms()
    assert out is not None
    assert [d.get_int("Predictor") for d in out] == [1, 12]


def test_set_decode_parms_none_removes_entry() -> None:
    from pypdfbox.cos import COSDictionary

    stream = PDStream(input_data=b"x")
    stream.set_decode_parms(COSDictionary())
    assert stream.get_decode_parms() is not None
    stream.set_decode_parms(None)
    assert stream.get_decode_parms() is None


def test_get_metadata_absent_returns_none() -> None:
    stream = PDStream()
    assert stream.get_metadata() is None


def test_set_and_get_metadata_round_trip() -> None:
    stream = PDStream()
    meta = COSStream()
    meta.set_raw_data(b"<x:xmpmeta/>")
    stream.set_metadata(meta)
    assert stream.get_metadata() is meta


def test_set_metadata_none_removes_entry() -> None:
    stream = PDStream()
    stream.set_metadata(COSStream())
    assert stream.get_metadata() is not None
    stream.set_metadata(None)
    assert stream.get_metadata() is None


def test_get_length_absent_with_no_data_returns_none() -> None:
    stream = PDStream()
    assert stream.get_length() is None


def test_to_byte_array_delegates_to_cos_stream() -> None:
    payload = b"delegated"
    stream = PDStream(input_data=zlib.compress(payload), filters=COSName.FLATE_DECODE)  # type: ignore[attr-defined]
    assert stream.to_byte_array() == payload
