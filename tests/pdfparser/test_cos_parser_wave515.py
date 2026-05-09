from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSInteger, COSName
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser import COSParser, PDFParseError


def _parser(data: bytes) -> COSParser:
    return COSParser(RandomAccessReadBuffer(data))


def _xref_stream_dict(widths: list[object], index: list[object] | None = None) -> COSDictionary:
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
            if isinstance(value, int):
                idx.add(COSInteger.get(value))
            else:
                idx.add(COSName.get_pdf_name(str(value)))
        d.set_item("Index", idx)
    return d


def test_wave515_stream_keyword_must_be_token_delimited() -> None:
    parser = _parser(b"4 0 obj\n<< /Length 4 >>\nstreamdata\nendstream\nendobj\n")

    with pytest.raises(PDFParseError, match="streamdata"):
        parser.parse_indirect_object_definition()


def test_wave515_stream_body_without_direct_length_defers_to_pdf_parser() -> None:
    parser = _parser(b"4 0 obj\n<< /Length 9 0 R >>\nstream\ndata\nendstream\nendobj\n")

    with pytest.raises(NotImplementedError, match="indirect or missing /Length"):
        parser.parse_indirect_object_definition()


def test_wave515_parse_xref_table_returns_false_for_bad_entry_flag() -> None:
    table = {}
    parser = _parser(
        b"xref\n"
        b"0 1\n"
        b"0000000000 65535 q \n"
        b"trailer\n<< /Size 1 >>\n"
    )

    assert parser.parse_xref_table(0, table) is False
    assert table == {}


@pytest.mark.parametrize(
    ("widths", "index", "message"),
    [
        ([1, 1, 1], [], "odd or empty length"),
        ([1, 1, 1], [0], "odd or empty length"),
        ([1, 1, 1], [0, "two"], "Index entries must be integers"),
        ([-1, 1, 1], None, "negative width"),
        ([10, 10, 1], None, "wider than 20 bytes"),
    ],
)
def test_wave515_parse_xref_stream_rejects_malformed_metadata(
    widths: list[object], index: list[object] | None, message: str
) -> None:
    with pytest.raises(PDFParseError, match=message):
        _parser(b"").parse_xref_stream(_xref_stream_dict(widths, index=index))


def test_wave515_header_predicates_restore_position_and_default_version() -> None:
    parser = _parser(b"junk\n%PDF-\nbody")
    parser.seek(3)

    assert parser.has_pdf_header()
    assert parser.position == 3
    assert parser.parse_pdf_header() == 1.4

    fdf_parser = _parser(b"%FDF-\n")
    assert fdf_parser.parse_fdf_header() == 1.0


def test_wave515_bf_search_for_xref_uses_nearest_traditional_xref() -> None:
    data = (
        b"%PDF-1.4\n"
        b"xref\n0 0\ntrailer\n<<>>\n"
        b"startxref\n999\n%%EOF\n"
        b"xref\n0 0\ntrailer\n<<>>\n"
    )

    assert _parser(data).bf_search_for_xref(len(data)) == data.rindex(b"xref")
