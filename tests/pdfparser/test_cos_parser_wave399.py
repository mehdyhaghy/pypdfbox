from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSDocument, COSFloat, COSInteger, COSName
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser import COSParser, PDFParseError


def _parser(data: bytes, document: COSDocument | None = None) -> COSParser:
    return COSParser(RandomAccessReadBuffer(data), document=document)


def _xref_stream_dict(
    w: list[object],
    *,
    index: list[int] | None = None,
    size: int | None = None,
) -> COSDictionary:
    d = COSDictionary()
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
            index_array.add(COSInteger.get(value))
        d.set_item("Index", index_array)
    if size is not None:
        d.set_int("Size", size)
    return d


def test_wave399_document_property_exposes_bound_document() -> None:
    doc = COSDocument()
    try:
        parser = _parser(b"", document=doc)
        assert parser.document is doc
        assert parser.get_document() is doc
    finally:
        doc.close()


def test_wave399_parse_cos_array_rejects_non_array_start() -> None:
    with pytest.raises(PDFParseError, match=r"expected array"):
        _parser(b"(not-array)").parse_cos_array()


def test_wave399_parse_cos_string_rejects_dictionary_start() -> None:
    with pytest.raises(PDFParseError, match="found dictionary"):
        _parser(b"<< /A 1 >>").parse_cos_string()


def test_wave399_parse_cos_name_and_number_aliases_skip_whitespace() -> None:
    assert _parser(b"   /Example").parse_cos_name() is COSName.get_pdf_name("Example")
    number = _parser(b"\n  -2.50").parse_cos_number()
    assert isinstance(number, COSFloat)
    assert number.get_original_form() == "-2.50"


def test_wave399_parse_cos_object_reference_rejects_plain_number() -> None:
    with pytest.raises(PDFParseError, match="expected indirect reference"):
        _parser(b"17").parse_cos_object_reference()


def test_wave399_parse_object_dynamically_without_document() -> None:
    parser = _parser(b"")

    created = parser.parse_object_dynamically(12, 3)
    assert created is not None
    assert created.get_object_number() == 12  # type: ignore[attr-defined]

    with pytest.raises(PDFParseError, match="no document bound"):
        parser.parse_object_dynamically(12, 3, requires_existing_not_compressed=True)


def test_wave399_parse_object_dynamically_requires_existing_pool_entry() -> None:
    doc = COSDocument()
    try:
        parser = _parser(b"", document=doc)
        with pytest.raises(PDFParseError, match="object not present"):
            parser.parse_object_dynamically(50, 0, requires_existing_not_compressed=True)
    finally:
        doc.close()


def test_wave399_is_string_accepts_str_and_preserves_position() -> None:
    parser = _parser(b"abcdef")

    assert parser.is_string("abc") is True
    assert parser.position == 0
    assert parser.is_string(b"abd") is False
    assert parser.position == 0


def test_wave399_last_index_of_handles_empty_and_partial_reset() -> None:
    parser = _parser(b"")

    assert parser.last_index_of(b"", b"abc", 3) == -1
    assert parser.last_index_of(b"aba", b"ababa", 5) == 2
    assert parser.last_index_of("zz", b"ababa", 5) == -1


def test_wave399_xref_stream_accepts_float_width_and_ignores_non_numeric_width() -> None:
    parser = _parser(b"")
    table = parser.parse_xref_stream(_xref_stream_dict([1.0, "ignored", 2], size=2))

    assert sorted(table.values()) == [0, 3]


def test_wave399_xref_stream_with_missing_size_defaults_to_empty_index() -> None:
    assert _parser(b"").parse_xref_stream(_xref_stream_dict([1, 2, 1])) == {}


def test_wave399_xref_stream_rejects_negative_index_first_and_count() -> None:
    parser = _parser(b"")

    with pytest.raises(PDFParseError, match="first object number is negative"):
        parser.parse_xref_stream(_xref_stream_dict([1, 2, 1], index=[-1, 1]))
    with pytest.raises(PDFParseError, match="count is negative"):
        parser.parse_xref_stream(_xref_stream_dict([1, 2, 1], index=[0, -1]))


def test_wave399_parse_xref_table_rejects_bad_flag_token() -> None:
    table: dict[object, int] = {}

    assert _parser(b"xref\n0 1\n0000000000 65535 nn \ntrailer\n<<>>").parse_xref_table(
        0, table  # type: ignore[arg-type]
    ) is False
    assert table == {}


def test_wave399_parse_object_stream_rejects_missing_stream_object() -> None:
    doc = COSDocument()
    try:
        with pytest.raises(PDFParseError, match="is not a stream"):
            _parser(b"", document=doc).parse_object_stream(99)
    finally:
        doc.close()
