from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSDocument,
    COSInteger,
    COSName,
    COSObjectKey,
)
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser import COSParser, PDFParseError, PDFParser
from pypdfbox.pdfparser.xref_trailer_resolver import XrefEntry, XrefType


def _parser(data: bytes = b"") -> PDFParser:
    return PDFParser(RandomAccessReadBuffer(data))


def _xref_stream(widths: list[int]) -> COSDictionary:
    stream = COSDictionary()
    w = COSArray()
    for width in widths:
        w.add(COSInteger.get(width))
    stream.set_item("W", w)
    stream.set_item("Size", COSInteger.get(1))
    return stream


def test_wave634_resolve_dict_entry_loads_uncompressed_reference_and_restores_cursor() -> None:
    data = b"4 0 obj\n<< /Filter /Standard >>\nendobj\ntrailing bytes"
    parser = _parser(data)
    doc = parser._document = COSDocument()  # noqa: SLF001
    parser._cos_parser = COSParser(parser._src, document=doc)  # noqa: SLF001
    parser.get_xref_trailer_resolver().begin_section(0)
    parser.get_xref_trailer_resolver().set_entry(
        COSObjectKey(4, 0),
        XrefEntry(type=XrefType.TABLE, offset=0),
    )
    ref = doc.get_object_from_pool(COSObjectKey(4, 0))
    trailer = COSDictionary()
    trailer.set_item("Encrypt", ref)
    parser._src.seek(len(data))

    try:
        resolved = parser._resolve_dict_entry(  # noqa: SLF001
            trailer,
            COSName.ENCRYPT,
        )

        assert isinstance(resolved, COSDictionary)
        assert resolved.get_name("Filter") == "Standard"
        assert parser._src.get_position() == len(data)
    finally:
        doc.close()


def test_wave634_decode_xref_stream_rejects_non_integer_width_entry() -> None:
    parser = _parser()
    parser.get_xref_trailer_resolver().begin_section(0)
    stream = _xref_stream([1, 1])
    widths = stream.get_dictionary_object("W")
    assert isinstance(widths, COSArray)
    widths.add(COSDictionary())

    with pytest.raises(PDFParseError, match=r"/W\[2\] is not an integer"):
        parser._decode_xref_stream_entries(stream)  # noqa: SLF001
