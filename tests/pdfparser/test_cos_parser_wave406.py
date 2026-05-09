from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSDocument,
    COSFloat,
    COSInteger,
    COSName,
    COSObjectKey,
)
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser import COSParser, PDFParseError


def _parser(data: bytes, document: COSDocument | None = None) -> COSParser:
    return COSParser(RandomAccessReadBuffer(data), document=document)


def _xref_stream_dict(
    w: list[object] | None = None,
    *,
    index: list[object] | None = None,
    size: int | None = None,
) -> COSDictionary:
    d = COSDictionary()
    if w is not None:
        w_array = COSArray()
        for value in w:
            if isinstance(value, int):
                w_array.add(COSInteger.get(value))
            elif isinstance(value, float):
                w_array.add(COSFloat(value))
            else:
                w_array.add(COSName.get_pdf_name(str(value)))
        d.set_item("W", w_array)
    if index is not None:
        index_array = COSArray()
        for value in index:
            if isinstance(value, int):
                index_array.add(COSInteger.get(value))
            else:
                index_array.add(COSName.get_pdf_name(str(value)))
        d.set_item("Index", index_array)
    if size is not None:
        d.set_int("Size", size)
    return d


def _objstm_source(body: bytes, *, entries: bytes) -> bytes:
    return (
        b"5 0 obj\n"
        + entries
        + b" /Length "
        + str(len(body)).encode("ascii")
        + b" >>\nstream\n"
        + body
        + b"\nendstream\nendobj\n"
    )


def test_wave406_header_defaults_and_predicates_preserve_position() -> None:
    parser = _parser(b"junk\n%PDF-\nbody")
    parser.seek(2)

    assert parser.has_pdf_header() is True
    assert parser.position == 2
    assert parser.parse_pdf_header() == 1.4

    fdf = _parser(b"%FDF-\n")
    assert fdf.has_fdf_header() is True
    assert fdf.parse_fdf_header() == 1.0
    assert _parser(b"%PDF-1.4\n").has_fdf_header() is False


def test_wave406_state_latches_and_eof_lookup_guard() -> None:
    parser = _parser(b"abc")

    assert parser.get_xref_offset() == -1
    parser.set_xref_offset(12)
    parser.set_file_len(99)
    parser.set_eof_lookup_range(15)

    assert parser.get_xref_offset() == 12
    assert parser.get_file_len() == 99
    assert parser.get_eof_lookup_range() == COSParser.DEFAULT_TRAIL_BYTECOUNT
    assert parser.is_initial_parse_done() is False
    assert parser.is_trailer_was_rebuild() is False

    parser.set_initial_parse_done(True)
    with pytest.raises(ValueError, match="Cannot change leniency"):
        parser.set_lenient(False)


def test_wave406_parse_xref_object_stream_rejects_bad_header_keyword() -> None:
    with pytest.raises(PDFParseError, match="expected 'obj'"):
        _parser(b"5 0 nope\n<< /Type /XRef >>").parse_xref_object_stream(0)


def test_wave406_parse_xref_object_stream_tolerates_missing_stream_keyword() -> None:
    stream = _parser(
        b"5 0 obj\n<< /Type /XRef /Size 0 /W [1 1 1] >>\nendobj\n"
    ).parse_xref_object_stream(0)

    assert isinstance(stream, COSDictionary)
    assert stream.get_name("Type") == "XRef"
    assert not stream.is_skip_encryption()


def test_wave406_parse_xref_table_false_on_eof_and_bad_subsection_header() -> None:
    assert _parser(b"xref\n").parse_xref_table(0) is False
    assert _parser(b"xref\nbad header\ntrailer\n<<>>").parse_xref_table(0) is False


@pytest.mark.parametrize(
    ("xref_dict", "message"),
    [
        (_xref_stream_dict(None, size=1), "missing /W array"),
        (_xref_stream_dict([1, 1, 1], index=[]), "odd or empty"),
        (_xref_stream_dict([1, 1, 1], index=[0]), "odd or empty"),
        (_xref_stream_dict([1, 1, 1], index=[0, "bad"]), "entries must be integers"),
        (_xref_stream_dict([-1, 1, 1], size=1), "negative width"),
        (_xref_stream_dict([0, 0, 0], size=1), "zero-byte entry"),
        (_xref_stream_dict([8, 8, 8], size=1), "wider than 20 bytes"),
    ],
)
def test_wave406_parse_xref_stream_rejects_malformed_metadata(
    xref_dict: COSDictionary, message: str
) -> None:
    with pytest.raises(PDFParseError, match=message):
        _parser(b"").parse_xref_stream(xref_dict)


def test_wave406_parse_xref_stream_appends_to_existing_table() -> None:
    table = {}
    result = _parser(b"").parse_xref_stream(
        _xref_stream_dict([1, 2], index=[3, 2]), table
    )

    assert result is table
    assert table == {
        COSObjectKey(3, 0): 0,
        COSObjectKey(4, 0): 3,
    }


def test_wave406_bf_search_for_xref_returns_minus_one_without_candidates() -> None:
    assert _parser(b"%PDF-1.4\nno cross-reference section").bf_search_for_xref(100) == -1


def test_wave406_rebuild_trailer_empty_when_no_objects_found() -> None:
    trailer = _parser(b"%PDF-1.4\nno indirect objects").rebuild_trailer()

    assert trailer.size() == 0


def test_wave406_object_stream_requires_type_objstm_and_nonnegative_n() -> None:
    doc = COSDocument()
    try:
        parser = _parser(
            _objstm_source(
                b"",
                entries=b"<< /Type /NotObjStm /N 0 /First 0",
            ),
            document=doc,
        )
        parser.parse_indirect_object_definition()
        with pytest.raises(PDFParseError, match="missing /Type /ObjStm"):
            _parser(b"", document=doc).parse_object_stream(5)
    finally:
        doc.close()

    doc = COSDocument()
    try:
        parser = _parser(
            _objstm_source(
                b"",
                entries=b"<< /Type /ObjStm /N -1 /First 0",
            ),
            document=doc,
        )
        parser.parse_indirect_object_definition()
        with pytest.raises(PDFParseError, match="negative /N"):
            _parser(b"", document=doc).parse_object_stream(5)
    finally:
        doc.close()
