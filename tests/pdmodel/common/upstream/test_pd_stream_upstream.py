"""Port of pdfbox/src/test/java/org/apache/pdfbox/pdmodel/common/PDStreamTest.java

Upstream baseline: PDFBox 3.0.7.

Upstream reads the stream byte-by-byte via ``InputStream.read()`` which
returns an ``int`` in ``0..255`` and ``-1`` at EOF. The Pythonic
``create_input_stream()`` returns a binary stream whose ``read(1)``
yields a one-byte ``bytes`` (``b""`` at EOF); the assertions are
translated accordingly.

The upstream stop-filter list is built from ``COSName.DCT_DECODE`` /
``COSName.DCT_DECODE_ABBREVIATION`` ``toString()`` values; since these
never match a real ``/Filter`` name they make the stop-filter a no-op,
so the bytes always round-trip verbatim. pypdfbox has no ``DCT_DECODE``
COSName constant — the equivalent name strings are used directly.
"""

from __future__ import annotations

import io

from pypdfbox import PDDocument
from pypdfbox.cos.cos_array import COSArray
from pypdfbox.pdmodel.common.pd_stream import PDStream

_STOP_FILTERS = ["DCTDecode", "DCT"]


def test_create_input_stream_null_filters() -> None:
    """Test for null filter list (PDFBOX-2948)."""
    with PDDocument() as doc:
        stream = io.BytesIO(bytes([12, 34, 56, 78]))
        pd_stream = PDStream(doc, stream, None)
        assert pd_stream.get_filters() == []

        ins = pd_stream.create_input_stream(_STOP_FILTERS)
        assert ins.read(1) == bytes([12])
        assert ins.read(1) == bytes([34])
        assert ins.read(1) == bytes([56])
        assert ins.read(1) == bytes([78])
        assert ins.read(1) == b""


def test_create_input_stream_empty_filters() -> None:
    """Test for empty filter list."""
    with PDDocument() as doc:
        stream = io.BytesIO(bytes([12, 34, 56, 78]))
        pd_stream = PDStream(doc, stream, COSArray())
        assert len(pd_stream.get_filters()) == 0

        ins = pd_stream.create_input_stream(_STOP_FILTERS)
        assert ins.read(1) == bytes([12])
        assert ins.read(1) == bytes([34])
        assert ins.read(1) == bytes([56])
        assert ins.read(1) == bytes([78])
        assert ins.read(1) == b""


def test_create_input_stream_null_stop_filters() -> None:
    """Test for null stop filters."""
    with PDDocument() as doc:
        stream = io.BytesIO(bytes([12, 34, 56, 78]))
        pd_stream = PDStream(doc, stream, COSArray())
        assert len(pd_stream.get_filters()) == 0

        ins = pd_stream.create_input_stream(None)
        assert ins.read(1) == bytes([12])
        assert ins.read(1) == bytes([34])
        assert ins.read(1) == bytes([56])
        assert ins.read(1) == bytes([78])
        assert ins.read(1) == b""
