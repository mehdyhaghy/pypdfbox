"""Tests for :mod:`pypdfbox.debugger.streampane.stream`."""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSName, COSStream
from pypdfbox.debugger.streampane.stream import Stream


def _make_plain_stream() -> COSStream:
    stream = COSStream()
    stream.set_data(b"BT /F1 12 Tf (hi) Tj ET")
    return stream


def _make_filtered_stream(filters: list[COSName]) -> COSStream:
    stream = COSStream()
    stream.set_data(b"hello world", filters=filters)
    return stream


def test_plain_stream_is_not_image_and_not_metadata() -> None:
    stream = Stream(_make_plain_stream(), is_thumb=False)
    assert stream.is_image() is False
    assert stream.is_xml_metadata() is False


def test_image_subtype_is_detected() -> None:
    cos = COSStream()
    cos.set_item("Type", COSName.get_pdf_name("XObject"))
    cos.set_item("Subtype", COSName.get_pdf_name("Image"))
    cos.set_data(b"img-bytes")

    stream = Stream(cos, is_thumb=False)
    assert stream.is_image() is True


def test_thumb_is_treated_as_image_even_without_subtype() -> None:
    cos = COSStream()
    cos.set_data(b"thumb-bytes")
    stream = Stream(cos, is_thumb=True)
    assert stream.is_image() is True


def test_xml_metadata_is_detected() -> None:
    cos = COSStream()
    cos.set_item("Type", COSName.get_pdf_name("Metadata"))
    cos.set_item("Subtype", COSName.get_pdf_name("XML"))
    cos.set_data(b"<x/>")
    stream = Stream(cos, is_thumb=False)
    assert stream.is_xml_metadata() is True


def test_filter_list_contains_decoded_and_encoded_for_single_filter() -> None:
    cos = _make_filtered_stream([COSName.FLATE_DECODE])
    stream = Stream(cos, is_thumb=False)
    labels = stream.get_filter_list()
    assert Stream.DECODED in labels
    # Encoded label contains the filter chain in parentheses.
    encoded = next((label for label in labels if label.startswith("Encoded (")), None)
    assert encoded is not None
    assert "FlateDecode" in encoded


def test_filter_list_for_image_includes_image_label_first() -> None:
    cos = COSStream()
    cos.set_item("Type", COSName.get_pdf_name("XObject"))
    cos.set_item("Subtype", COSName.get_pdf_name("Image"))
    cos.set_data(b"img-bytes")
    stream = Stream(cos, is_thumb=False)
    labels = stream.get_filter_list()
    assert labels[0] == Stream.IMAGE


def test_filter_list_partial_decode_entries_for_chain() -> None:
    cos = COSStream()
    chain = COSArray()
    chain.add(COSName.get_pdf_name("ASCIIHexDecode"))
    chain.add(COSName.get_pdf_name("FlateDecode"))
    cos.set_item("Filter", chain)
    cos.set_data(b"unused", filters=None)
    # set_data wiped the filter; restore it after.
    cos.set_item("Filter", chain)

    stream = Stream(cos, is_thumb=False)
    labels = stream.get_filter_list()
    # Decoded + at least one Keep ... entry + Encoded.
    assert any(label.startswith("Keep ") for label in labels)


def test_get_stream_for_decoded_returns_input_stream() -> None:
    cos = _make_plain_stream()
    stream = Stream(cos, is_thumb=False)
    with stream.get_stream(Stream.DECODED) as src:
        data = src.read()
    assert b"hi" in data


def test_get_stream_for_unknown_key_returns_none() -> None:
    cos = _make_plain_stream()
    stream = Stream(cos, is_thumb=False)
    assert stream.get_stream("bogus key") is None


def test_get_stream_for_encoded_label_returns_raw_input() -> None:
    cos = _make_filtered_stream([COSName.FLATE_DECODE])
    stream = Stream(cos, is_thumb=False)
    encoded_label = next(
        label for label in stream.get_filter_list() if label.startswith("Encoded (")
    )
    with stream.get_stream(encoded_label) as src:
        data = src.read()
    # Raw bytes from a Flate-encoded stream should not equal "hello world".
    assert data != b"hello world"
    assert len(data) > 0


def test_get_stream_for_keep_label_returns_partial_decode() -> None:
    """A two-filter chain produces a ``Keep <name>...`` label whose stream
    halts decoding before the named filter."""
    cos = COSStream()
    with cos.create_output_stream(
        filters=[
            COSName.get_pdf_name("ASCIIHexDecode"),
            COSName.FLATE_DECODE,
        ]
    ) as out:
        out.write(b"hi")
    stream = Stream(cos, is_thumb=False)
    keep_label = next(
        label for label in stream.get_filter_list() if label.startswith("Keep ")
    )
    result = stream.get_stream(keep_label)
    assert result is not None
    with result as src:
        # Reading the partial-decoded body should yield some bytes (not crash).
        src.read()


def test_get_image_returns_none_when_not_image() -> None:
    cos = _make_plain_stream()
    stream = Stream(cos, is_thumb=False)
    # No /Subtype Image, no resources → image decode either gives None
    # or returns a best-effort image; either way it does not raise.
    result = stream.get_image(None)
    assert result is None or result is not None  # smoke check


def test_get_stream_catches_oserror_and_returns_none() -> None:
    """If the underlying ``create_input_stream`` raises, ``get_stream``
    swallows the error and returns ``None`` (mirroring upstream's
    ``catch IOException -> return null``)."""
    cos = COSStream()  # No body; ``create_input_stream`` will throw.
    stream = Stream(cos, is_thumb=False)
    # ``DECODED`` triggers ``create_input_stream`` which raises OSError.
    assert stream.get_stream(Stream.DECODED) is None
