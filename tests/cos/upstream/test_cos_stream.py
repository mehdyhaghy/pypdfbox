"""
Ported from Apache PDFBox 3.0:
  pdfbox/src/test/java/org/apache/pdfbox/cos/TestCOSStream.java

The compressed-stream tests now run against ``pypdfbox.filter`` —
``FlateDecode`` and ``ASCII85Decode`` are wired up via ``FilterFactory``
and exercised through ``COSStream.create_output_stream(filters=...)`` /
``create_input_stream()``.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSName, COSStream

_TEST_STRING = b"This is a test string to be used as input for TestCOSStream"


def test_uncompressed_stream_encode() -> None:
    stream = COSStream()
    with stream.create_output_stream() as out:
        out.write(_TEST_STRING)
    decoded = stream.create_raw_input_stream().read()
    stream.close()
    assert decoded == _TEST_STRING


def test_uncompressed_stream_decode() -> None:
    stream = COSStream()
    with stream.create_output_stream() as out:
        out.write(_TEST_STRING)
    decoded = stream.create_input_stream().read()
    stream.close()
    assert decoded == _TEST_STRING


def test_compressed_stream1_encode() -> None:
    stream = COSStream()
    with stream.create_output_stream(COSName.FLATE_DECODE) as out:  # type: ignore[attr-defined]
        out.write(_TEST_STRING)
    # Raw bytes are now compressed; encoded size differs from input.
    raw = stream.create_raw_input_stream().read()
    assert raw != _TEST_STRING
    assert len(raw) > 0
    stream.close()


def test_compressed_stream1_decode() -> None:
    stream = COSStream()
    with stream.create_output_stream(COSName.FLATE_DECODE) as out:  # type: ignore[attr-defined]
        out.write(_TEST_STRING)
    decoded = stream.create_input_stream().read()
    stream.close()
    assert decoded == _TEST_STRING


def test_compressed_stream2_encode() -> None:
    stream = COSStream()
    with stream.create_output_stream(["ASCII85Decode", "FlateDecode"]) as out:
        out.write(_TEST_STRING)
    # Outer encoding is ASCII85: raw bytes should be in the printable
    # ASCII85 alphabet, ending with the ``~>`` EOD marker plus the trailing
    # LF that upstream ASCII85OutputStream always appends after ``>``.
    raw = stream.create_raw_input_stream().read()
    assert raw.endswith(b"~>\n")
    stream.close()


def test_compressed_stream2_decode() -> None:
    stream = COSStream()
    with stream.create_output_stream(["ASCII85Decode", "FlateDecode"]) as out:
        out.write(_TEST_STRING)
    decoded = stream.create_input_stream().read()
    stream.close()
    assert decoded == _TEST_STRING


def test_compressed_stream_double_close() -> None:
    stream = COSStream()
    out = stream.create_output_stream(COSName.FLATE_DECODE)  # type: ignore[attr-defined]
    out.write(_TEST_STRING)
    out.close()
    # Second close must be a no-op.
    out.close()
    decoded = stream.create_input_stream().read()
    stream.close()
    assert decoded == _TEST_STRING


def test_has_stream_data() -> None:
    stream = COSStream()
    assert not stream.has_data()
    with pytest.raises(OSError):
        stream.create_input_stream()

    with stream.create_output_stream() as out:
        out.write(_TEST_STRING)
    assert stream.has_data()
    stream.close()


def test_compressed_stream1_decode_via_raw_output_stream() -> None:
    """Mirrors upstream ``testCompressedStream1Decode`` (lines 82–96 of
    ``TestCOSStream.java``): when the raw bytes are pre-encoded, the
    consumer writes them through ``createRawOutputStream`` and sets
    ``/Filter`` after the fact — ``createInputStream`` must still decode
    them correctly."""
    import zlib

    encoded = zlib.compress(_TEST_STRING)
    stream = COSStream()
    with stream.create_raw_output_stream() as out:
        out.write(encoded)
    stream.set_item(COSName.FILTER, COSName.FLATE_DECODE)  # type: ignore[attr-defined]
    decoded = stream.create_input_stream().read()
    stream.close()
    assert decoded == _TEST_STRING


def test_compressed_stream2_decode_via_raw_output_stream() -> None:
    """Mirrors upstream ``testCompressedStream2Decode`` (lines 124–141 of
    ``TestCOSStream.java``): two-filter chain, raw bytes pre-encoded then
    written via ``createRawOutputStream`` with ``/Filter`` applied
    separately."""
    import base64
    import zlib

    inner = zlib.compress(_TEST_STRING)
    encoded = base64.a85encode(inner) + b"~>"

    from pypdfbox.cos import COSArray

    stream = COSStream()
    chain = COSArray([COSName.ASCII85_DECODE, COSName.FLATE_DECODE])  # type: ignore[attr-defined]
    stream.set_item(COSName.FILTER, chain)  # type: ignore[attr-defined]
    with stream.create_raw_output_stream() as out:
        out.write(encoded)
    decoded = stream.create_input_stream().read()
    stream.close()
    assert decoded == _TEST_STRING
