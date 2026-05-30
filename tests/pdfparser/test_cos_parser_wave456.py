from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDocument,
    COSObject,
    COSObjectKey,
    COSString,
)
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser import COSParser, PDFParseError


def _parser(data: bytes, document: COSDocument | None = None) -> COSParser:
    return COSParser(RandomAccessReadBuffer(data), document=document)


def _objstm(body: bytes, *, n: int, first: int) -> bytes:
    return (
        b"5 0 obj\n<< /Type /ObjStm /N "
        + str(n).encode("ascii")
        + b" /First "
        + str(first).encode("ascii")
        + b" /Length "
        + str(len(body)).encode("ascii")
        + b" >>\nstream\n"
        + body
        + b"\nendstream\nendobj\n"
    )


def test_wave456_is_string_accepts_str_and_restores_after_mismatch() -> None:
    parser = _parser(b"abcdef")
    parser.seek(2)

    assert parser.is_string("cde") is True
    assert parser.position == 2
    assert parser.is_string(b"cdf") is False
    assert parser.position == 2


def test_wave456_last_index_of_respects_exclusive_end_offset() -> None:
    parser = _parser(b"")
    buf = b"abc abc abc"

    assert parser.last_index_of("abc", buf, len(buf)) == 8
    assert parser.last_index_of(b"abc", buf, 8) == 4
    assert parser.last_index_of(b"xyz", buf, len(buf)) == -1
    assert parser.last_index_of(b"", buf, len(buf)) == -1


def test_wave456_parse_object_dynamically_paths() -> None:
    with pytest.raises(PDFParseError, match="no document bound"):
        _parser(b"").parse_object_dynamically(1, 0, True)

    placeholder = _parser(b"").parse_object_dynamically(1, 0)
    assert isinstance(placeholder, COSObject)
    assert placeholder.object_number == 1

    doc = COSDocument()
    try:
        parser = _parser(b"", document=doc)
        with pytest.raises(PDFParseError, match="object not present"):
            parser.parse_object_dynamically(2, 0, True)
        assert parser.parse_object_dynamically(2, 0) is None
    finally:
        doc.close()


def test_wave456_bf_search_for_objects_keeps_last_valid_header() -> None:
    data = (
        b"notobj\n"
        b"11 0 obj\n(first)\nendobj\n"
        b"111 0 objx\nignored\n"
        b"11 0 obj\n(second)\nendobj\n"
        b"12 3 obj\n<<>>\nendobj\n"
    )

    found = _parser(data).bf_search_for_objects()

    # Last occurrence wins (unconditional Map.put upstream): the duplicated
    # ``11 0 obj`` records the LATER offset, not the first.
    assert found[COSObjectKey(11, 0)] == data.rindex(b"11 0 obj")
    assert found[COSObjectKey(12, 3)] == data.index(b"12 3 obj")
    assert len(found) == 2


def test_wave456_bf_search_for_xref_falls_back_to_xref_stream_object() -> None:
    data = b"%PDF-1.5\n9 0 obj\n<< /Type /XRef /Size 0 >>\nstream\nendstream\n"

    assert _parser(data).bf_search_for_xref(12) == data.index(b"9 0 obj")


def test_wave456_rebuild_trailer_recovers_common_entries() -> None:
    data = (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Type /Catalog >>\nendobj\n"
        b"2 0 obj\n<< /Title (Doc) /Producer (pypdfbox) >>\nendobj\n"
        b"3 0 obj\n<< /Encrypt 4 0 R /ID [(abc) (def)] >>\nendobj\n"
    )

    trailer = _parser(data).rebuild_trailer()

    root = trailer.get_item("Root")
    info = trailer.get_item("Info")
    ids = trailer.get_dictionary_object("ID")
    assert isinstance(root, COSObject)
    assert root.object_number == 1
    assert isinstance(info, COSObject)
    assert info.object_number == 2
    assert trailer.get_int("Size") == 4
    assert isinstance(ids, COSArray)
    assert isinstance(ids.get(0), COSString)


@pytest.mark.parametrize(
    ("body", "n", "first", "message"),
    [
        (b"", 0, -1, "negative /First"),
        (b"10 0", 1, 6, "exceeds decoded length"),
        (b"10 ", 1, 3, "header truncated"),
        (b"-1 0\n42", 1, 5, "negative object number"),
        (b"10 2\n42", 1, 5, "outside payload length"),
    ],
)
def test_wave456_parse_object_stream_rejects_bad_header_metadata(
    body: bytes, n: int, first: int, message: str
) -> None:
    doc = COSDocument()
    try:
        _parser(_objstm(body, n=n, first=first), document=doc).parse_indirect_object_definition()

        with pytest.raises(PDFParseError, match=message):
            _parser(b"", document=doc).parse_object_stream(5)
    finally:
        doc.close()


def test_wave456_parse_xref_object_stream_rejects_non_dictionary_body() -> None:
    with pytest.raises(PDFParseError, match="body is not a dictionary"):
        _parser(b"5 0 obj\n42\nendobj\n").parse_xref_object_stream(0)
