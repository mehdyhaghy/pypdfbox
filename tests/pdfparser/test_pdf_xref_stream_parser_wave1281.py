"""Wave 1281: PDFXrefStreamParser port."""

from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDocument,
    COSInteger,
    COSName,
    COSStream,
)
from pypdfbox.pdfparser import PDFXrefStreamParser, XrefTrailerResolver
from pypdfbox.pdfparser.parse_error import PDFParseError


def _stream_with(w: list[int] | None, index: list[int] | None) -> COSStream:
    stream = COSStream()
    if w is not None:
        w_arr = COSArray()
        for v in w:
            w_arr.add(COSInteger.get(v))
        stream.set_item(COSName.W, w_arr)
    if index is not None:
        idx_arr = COSArray()
        for v in index:
            idx_arr.add(COSInteger.get(v))
        stream.set_item(COSName.INDEX, idx_arr)
    out = stream.create_raw_output_stream()
    try:
        out.write(b"")
    finally:
        out.close()
    return stream


def test_missing_w_raises() -> None:
    stream = _stream_with(None, [0, 1])
    with pytest.raises(PDFParseError):
        PDFXrefStreamParser(stream, COSDocument())


def test_wrong_w_length_raises() -> None:
    stream = _stream_with([1, 2], [0, 1])
    with pytest.raises(PDFParseError):
        PDFXrefStreamParser(stream, COSDocument())


def test_negative_w_value_raises() -> None:
    stream = _stream_with([1, -1, 1], [0, 1])
    with pytest.raises(PDFParseError):
        PDFXrefStreamParser(stream, COSDocument())


def test_w_widths_too_large_raises() -> None:
    stream = _stream_with([10, 10, 10], [0, 1])
    with pytest.raises(PDFParseError):
        PDFXrefStreamParser(stream, COSDocument())


def test_default_index_when_missing() -> None:
    stream = _stream_with([1, 2, 1], None)
    stream.set_item(COSName.SIZE, COSInteger.get(0))
    parser = PDFXrefStreamParser(stream, COSDocument())
    # No bytes in body → parse should run cleanly even with empty default.
    resolver = XrefTrailerResolver()
    resolver.begin_section(0)
    parser.parse(resolver)


def test_odd_length_index_rejected() -> None:
    stream = _stream_with([1, 2, 1], [0])
    with pytest.raises(PDFParseError):
        PDFXrefStreamParser(stream, COSDocument())
