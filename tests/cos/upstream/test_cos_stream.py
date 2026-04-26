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
    # ASCII85 alphabet (plus the ``~>`` terminator).
    raw = stream.create_raw_input_stream().read()
    assert raw.endswith(b"~>")
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
