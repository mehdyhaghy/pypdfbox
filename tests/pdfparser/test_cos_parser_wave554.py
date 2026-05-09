from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSDocument,
    COSInteger,
    COSName,
    COSObject,
    COSObjectKey,
    COSStream,
    COSString,
)
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser import COSParser, PDFParseError


def _parser(data: bytes, document: COSDocument | None = None) -> COSParser:
    return COSParser(RandomAccessReadBuffer(data), document=document)


def test_wave554_parse_cos_string_accepts_literal_and_hex_forms() -> None:
    literal = _parser(b"   (hello)")
    hex_string = _parser(b" <6869>")

    parsed_literal = literal.parse_cos_string()
    parsed_hex = hex_string.parse_cos_string()

    assert isinstance(parsed_literal, COSString)
    assert parsed_literal.get_bytes() == b"hello"
    assert parsed_hex.get_bytes() == b"hi"
    assert parsed_hex.is_force_hex_form()


@pytest.mark.parametrize(
    ("data", "message"),
    [
        (b"<< /A 1 >>", "found dictionary"),
        (b"/Name", "expected COS string"),
    ],
)
def test_wave554_parse_cos_string_rejects_non_string_tokens(
    data: bytes, message: str
) -> None:
    with pytest.raises(PDFParseError, match=message):
        _parser(data).parse_cos_string()


def test_wave554_lenient_flag_cannot_change_after_initial_parse_done() -> None:
    parser = _parser(b"")

    assert parser.is_lenient()
    parser.set_lenient(False)
    assert not parser.is_lenient()
    parser.set_initial_parse_done(True)

    with pytest.raises(ValueError, match="Cannot change leniency"):
        parser.set_lenient(True)


def test_wave554_parse_object_dynamically_unbound_and_required_paths() -> None:
    unbound = _parser(b"")

    placeholder = unbound.parse_object_dynamically(7, 2)
    assert isinstance(placeholder, COSObject)
    assert placeholder.get_object_number() == 7
    assert placeholder.get_generation_number() == 2

    with pytest.raises(PDFParseError, match="no document bound"):
        unbound.parse_object_dynamically(7, 2, requires_existing_not_compressed=True)


def test_wave554_parse_object_dynamically_resolves_bound_document_pool() -> None:
    doc = COSDocument()
    parser = _parser(b"", document=doc)
    try:
        holder = doc.get_object_from_pool(COSObjectKey(4, 0))
        holder.set_object(COSInteger.get(123))

        assert parser.parse_object_dynamically(4, 0) is COSInteger.get(123)
        assert parser.parse_object_dynamically(99, 0) is None
        with pytest.raises(PDFParseError, match="object not present"):
            parser.parse_object_dynamically(
                100, 0, requires_existing_not_compressed=True
            )
    finally:
        doc.close()


def test_wave554_parse_object_stream_registers_all_packed_objects() -> None:
    doc = COSDocument()
    parser = _parser(b"", document=doc)
    try:
        obj_stream = COSStream(scratch_file=doc.scratch_file)
        obj_stream.set_item("Type", COSName.get_pdf_name("ObjStm"))
        obj_stream.set_item("N", COSInteger.get(2))
        obj_stream.set_item("First", COSInteger.get(8))
        obj_stream.set_raw_data(b"7 0 8 4\n123 /Name")
        doc.get_object_from_pool(COSObjectKey(5, 0)).set_object(obj_stream)

        parsed = parser.parse_object_stream(5)

        assert parsed == [COSInteger.get(123), COSName.get_pdf_name("Name")]
        assert doc.get_object_from_pool(COSObjectKey(7, 0)).get_object() is parsed[0]
        assert doc.get_object_from_pool(COSObjectKey(8, 0)).get_object() is parsed[1]
    finally:
        doc.close()


def test_wave554_parse_object_stream_requires_bound_document_and_stream() -> None:
    with pytest.raises(PDFParseError, match="no document bound"):
        _parser(b"").parse_object_stream(9)

    doc = COSDocument()
    parser = _parser(b"", document=doc)
    try:
        doc.get_object_from_pool(COSObjectKey(9, 0)).set_object(COSInteger.get(1))
        with pytest.raises(PDFParseError, match="is not a stream"):
            parser.parse_object_stream(9)
    finally:
        doc.close()


def test_wave554_parse_xref_object_stream_allows_non_standalone_missing_type() -> None:
    parser = _parser(b"9 0 obj\n<< /Length 0 >>\nstream\n\nendstream\nendobj\n")

    stream = parser.parse_xref_object_stream(0, is_standalone=False)

    assert isinstance(stream, COSStream)
    assert stream.get_dictionary_object(COSName.LENGTH) is COSInteger.get(0)  # type: ignore[attr-defined]
