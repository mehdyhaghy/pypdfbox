"""Wave 272 — PDStream parity round-out tests."""

from __future__ import annotations

import io

from pypdfbox.cos import COSName, COSStream
from pypdfbox.pdmodel.common import PDStream

# ---------- get_byte_array() — alias of to_byte_array() ----------


def test_get_byte_array_returns_decoded_body_wave272() -> None:
    stream = PDStream(input_data=b"plain bytes")
    assert stream.get_byte_array() == b"plain bytes"


def test_get_byte_array_decodes_through_filter_chain_wave272() -> None:
    # Embed encodes the decoded payload through /Filter; get_byte_array()
    # decodes it back.
    stream = PDStream(input_data=b"compressed payload", filters=COSName.FLATE_DECODE)  # type: ignore[attr-defined]
    assert stream.get_byte_array() == b"compressed payload"


def test_get_byte_array_empty_for_fresh_stream_wave272() -> None:
    stream = PDStream()
    assert stream.get_byte_array() == b""


def test_get_byte_array_matches_to_byte_array_wave272() -> None:
    """The aliases must agree byte-for-byte."""
    stream = PDStream(input_data=b"matched")
    assert stream.get_byte_array() == stream.to_byte_array()


# ---------- get_filtered_stream_length() ----------


def test_get_filtered_stream_length_returns_recorded_length_wave272() -> None:
    """When ``/Length`` is recorded in the dictionary the value is
    returned verbatim — matches the parser-populated path."""
    stream = PDStream()
    stream.set_length(42)
    assert stream.get_filtered_stream_length() == 42


def test_get_filtered_stream_length_records_length_wave272() -> None:
    """Embedding unfiltered bytes records ``/Length`` (wave 1563: ``set_raw_data``
    now syncs ``/Length`` to mirror upstream ``createOutputStream(null)``), so
    ``get_filtered_stream_length()`` reads the recorded entry — the encoded
    byte count."""
    # Embed unfiltered bytes via set_raw_data: /Length is synced to the body so
    # COSStream.get_length() (which reads the dict entry, per upstream) and
    # get_filtered_stream_length() both report the real encoded length.
    stream = PDStream(input_data=b"hello")
    cos = stream.get_cos_object()
    assert cos.contains_key(COSName.LENGTH)  # type: ignore[attr-defined]
    assert cos.get_int(COSName.LENGTH) == len(b"hello")  # type: ignore[attr-defined]
    assert stream.get_filtered_stream_length() == len(b"hello")


def test_get_filtered_stream_length_empty_returns_minus_one_wave272() -> None:
    stream = PDStream()
    assert stream.get_filtered_stream_length() == -1


# ---------- copy_to() — decoded sink copy ----------


def test_copy_to_writes_decoded_body_to_sink_wave272() -> None:
    stream = PDStream(input_data=b"streamed payload", filters=COSName.FLATE_DECODE)  # type: ignore[attr-defined]
    sink = io.BytesIO()
    written = stream.copy_to(sink)
    assert written == len(b"streamed payload")
    assert sink.getvalue() == b"streamed payload"


def test_copy_to_empty_stream_writes_zero_bytes_wave272() -> None:
    stream = PDStream()
    sink = io.BytesIO()
    assert stream.copy_to(sink) == 0
    assert sink.getvalue() == b""


# ---------- copy_raw_to() — encoded sink copy ----------


def test_copy_raw_to_writes_encoded_body_verbatim_wave272() -> None:
    stream = PDStream(input_data=b"encoded payload", filters=COSName.FLATE_DECODE)  # type: ignore[attr-defined]
    encoded = stream.create_raw_input_stream().read()
    sink = io.BytesIO()
    written = stream.copy_raw_to(sink)
    assert written == len(encoded)
    assert sink.getvalue() == encoded


def test_copy_raw_to_returns_unfiltered_when_no_filter_wave272() -> None:
    """Without a filter chain, raw and decoded copy paths must produce
    the same bytes."""
    stream = PDStream(input_data=b"unfiltered")
    raw_sink = io.BytesIO()
    decoded_sink = io.BytesIO()
    assert stream.copy_raw_to(raw_sink) == stream.copy_to(decoded_sink)
    assert raw_sink.getvalue() == decoded_sink.getvalue() == b"unfiltered"


# ---------- get_cos_stream / get_stream — sanity of existing aliases ----------


def test_get_cos_stream_alias_returns_same_object_wave272() -> None:
    cos = COSStream()
    stream = PDStream(cos)
    assert stream.get_cos_stream() is cos
    assert stream.get_stream() is cos
    assert stream.get_cos_object() is cos
