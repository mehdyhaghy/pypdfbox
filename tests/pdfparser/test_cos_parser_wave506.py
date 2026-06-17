from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSObjectKey,
)
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser import COSParser, PDFParseError


def _parser(data: bytes) -> COSParser:
    return COSParser(RandomAccessReadBuffer(data))


def _xref_stream_dict(
    widths: list[object],
    *,
    index: list[object] | None = None,
    size: int | None = None,
) -> COSDictionary:
    d = COSDictionary()
    w = COSArray()
    for value in widths:
        if isinstance(value, int):
            w.add(COSInteger.get(value))
        elif isinstance(value, float):
            w.add(COSFloat(value))
        else:
            w.add(COSName.get_pdf_name(str(value)))
    d.set_item("W", w)
    if index is not None:
        idx = COSArray()
        for value in index:
            idx.add(COSInteger.get(value))
        d.set_item("Index", idx)
    if size is not None:
        d.set_int("Size", size)
    return d


def test_wave506_parse_xref_stream_defaults_index_and_accepts_float_widths() -> None:
    result = _parser(b"").parse_xref_stream(
        _xref_stream_dict([1.0, 1.0], size=3)
    )

    assert result == {
        COSObjectKey(0, 0): 0,
        COSObjectKey(1, 0): 2,
        COSObjectKey(2, 0): 4,
    }


@pytest.mark.parametrize(
    ("index", "message"),
    [
        ([-1, 1], "first object number is negative"),
        ([0, -1], "count is negative"),
    ],
)
def test_wave506_parse_xref_stream_rejects_negative_index_values(
    index: list[int], message: str
) -> None:
    with pytest.raises(PDFParseError, match=message):
        _parser(b"").parse_xref_stream(_xref_stream_dict([1, 1, 1], index=index))


def test_wave506_parse_xref_stream_non_integer_width_counts_as_absent() -> None:
    result = _parser(b"").parse_xref_stream(
        _xref_stream_dict([1, "ignored", 1], index=[4, 2])
    )

    assert result == {
        COSObjectKey(4, 0): 0,
        COSObjectKey(5, 0): 2,
    }


def test_wave506_parse_fdf_header_rejects_malformed_version() -> None:
    # Upstream raises only in STRICT mode; lenient defaults the version to 1.7
    # (NOT the FDF default 1.0, which applies only to the no-digits branch).
    p = _parser(b"%FDF-not-a-version\n")
    p.set_lenient(False)
    with pytest.raises(PDFParseError, match="Error getting header version"):
        p.parse_fdf_header()
    assert _parser(b"%FDF-not-a-version\n").parse_fdf_header() == 1.7
