"""
Ported from Apache PDFBox 3.0:
  pdfbox/src/test/java/org/apache/pdfbox/cos/TestCOSStream.java

Every compressed-stream test exercises ``pypdfbox.filter`` (FlateDecode,
ASCII85Decode), which is a separate cluster (PRD §6.4) not yet ported.
They are skipped here. Only the uncompressed and ``hasData`` tests run.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSStream


def test_uncompressed_stream_encode() -> None:
    test_string = b"This is a test string to be used as input for TestCOSStream"
    stream = COSStream()
    with stream.create_output_stream() as out:
        out.write(test_string)
    decoded = stream.create_raw_input_stream().read()
    stream.close()
    assert decoded == test_string


def test_uncompressed_stream_decode() -> None:
    test_string = b"This is a test string to be used as input for TestCOSStream"
    stream = COSStream()
    with stream.create_output_stream() as out:
        out.write(test_string)
    decoded = stream.create_input_stream().read()
    stream.close()
    assert decoded == test_string


@pytest.mark.skip(reason="needs FlateDecode in pypdfbox.filter (filter cluster, not yet ported)")
def test_compressed_stream1_encode() -> None:
    pass


@pytest.mark.skip(reason="needs FlateDecode in pypdfbox.filter (filter cluster, not yet ported)")
def test_compressed_stream1_decode() -> None:
    pass


@pytest.mark.skip(reason="needs ASCII85Decode/FlateDecode (filter cluster, not yet ported)")
def test_compressed_stream2_encode() -> None:
    pass


@pytest.mark.skip(reason="needs ASCII85Decode/FlateDecode (filter cluster, not yet ported)")
def test_compressed_stream2_decode() -> None:
    pass


@pytest.mark.skip(reason="needs FlateDecode in pypdfbox.filter (filter cluster, not yet ported)")
def test_compressed_stream_double_close() -> None:
    pass


def test_has_stream_data() -> None:
    stream = COSStream()
    assert not stream.has_data()
    with pytest.raises(OSError):
        stream.create_input_stream()

    test_string = b"This is a test string to be used as input for TestCOSStream"
    with stream.create_output_stream() as out:
        out.write(test_string)
    assert stream.has_data()
    stream.close()
