"""
Ported from
pdfbox/src/test/java/org/apache/pdfbox/pdfparser/PDFObjectStreamParserTest.java
(Apache PDFBox 3.0.x).

Covers the PDF 1.5+ compressed-object-stream parser: reading the offset
table (``readObjectNumbers``), parsing a single object by number
(``parseObject``), parsing every object (``parseAllObjects``), and the
behaviour around the ``stream_index`` xref hint when the same object number
appears more than once in a single object stream.
"""

from __future__ import annotations

from pypdfbox.cos.cos_boolean import COSBoolean
from pypdfbox.cos.cos_document import COSDocument
from pypdfbox.cos.cos_integer import COSInteger
from pypdfbox.cos.cos_name import COSName
from pypdfbox.cos.cos_object_key import COSObjectKey
from pypdfbox.cos.cos_stream import COSStream
from pypdfbox.pdfparser.pdf_object_stream_parser import PDFObjectStreamParser


def _make_stream(n: int, first: int, body: bytes) -> COSStream:
    stream = COSStream()
    stream.set_item(COSName.N, COSInteger.get(n))
    stream.set_item(COSName.FIRST, COSInteger.get(first))
    with stream.create_output_stream() as out:
        out.write(body)
    return stream


def test_offset_parsing() -> None:
    stream = _make_stream(2, 8, b"4 0 6 5 true false")
    parser = PDFObjectStreamParser(stream, None)  # type: ignore[arg-type]
    object_numbers = parser.read_object_numbers()
    assert len(object_numbers) == 2
    assert object_numbers[4] == 0
    assert object_numbers[6] == 5

    parser = PDFObjectStreamParser(stream, None)  # type: ignore[arg-type]
    assert parser.parse_object(4) is COSBoolean.TRUE

    parser = PDFObjectStreamParser(stream, None)  # type: ignore[arg-type]
    assert parser.parse_object(6) is COSBoolean.FALSE


def test_parse_all_objects() -> None:
    stream = _make_stream(2, 8, b"6 0 4 5 true false")
    parser = PDFObjectStreamParser(stream, None)  # type: ignore[arg-type]
    object_numbers = parser.parse_all_objects()
    assert len(object_numbers) == 2
    assert object_numbers[COSObjectKey(6, 0)] is COSBoolean.TRUE
    assert object_numbers[COSObjectKey(4, 0)] is COSBoolean.FALSE


def test_parse_all_objects_indexed() -> None:
    # use object number 4 for two objects
    stream = _make_stream(3, 13, b"6 0 4 5 4 11 true false true")
    cos_doc = COSDocument()
    xref_table = cos_doc.get_xref_table()
    # select the second object from the stream for object number 4 by using
    # 2 as the value of the index.
    xref_table[COSObjectKey(6, 0, 0)] = -1
    xref_table[COSObjectKey(4, 0, 2)] = -1
    parser = PDFObjectStreamParser(stream, cos_doc)
    object_numbers = parser.parse_all_objects()
    assert len(object_numbers) == 2
    assert object_numbers[COSObjectKey(6, 0)] is COSBoolean.TRUE
    assert object_numbers[COSObjectKey(4, 0)] is COSBoolean.TRUE

    # select the first object from the stream for object number 4 by using 1
    # as the value of the index. Remove the old entry first to be sure it is
    # replaced.
    xref_table.pop(COSObjectKey(4, 0), None)
    xref_table[COSObjectKey(4, 0, 1)] = -1
    parser = PDFObjectStreamParser(stream, cos_doc)
    object_numbers = parser.parse_all_objects()
    assert len(object_numbers) == 2
    assert object_numbers[COSObjectKey(6, 0)] is COSBoolean.TRUE
    assert object_numbers[COSObjectKey(4, 0)] is COSBoolean.FALSE


def test_parse_all_objects_skip_malformed_index() -> None:
    stream = _make_stream(3, 13, b"6 0 4 5 5 11 true false true")
    cos_doc = COSDocument()
    xref_table = cos_doc.get_xref_table()
    # add an index for each object key which doesn't match with the index of
    # the object stream
    xref_table[COSObjectKey(6, 0, 10)] = -1
    xref_table[COSObjectKey(4, 0, 11)] = -1
    xref_table[COSObjectKey(5, 0, 12)] = -1
    parser = PDFObjectStreamParser(stream, cos_doc)
    # the index isn't taken into account as all object numbers of the stream
    # are unique; none of the objects is skipped so that all objects are read
    # and available.
    object_numbers = parser.parse_all_objects()
    assert len(object_numbers) == 3
    assert object_numbers[COSObjectKey(6, 0)] is COSBoolean.TRUE
    assert object_numbers[COSObjectKey(4, 0)] is COSBoolean.FALSE
    assert object_numbers[COSObjectKey(5, 0)] is COSBoolean.TRUE


def test_parse_all_objects_use_malformed_index() -> None:
    stream = _make_stream(3, 13, b"6 0 4 5 4 11 true false true")
    cos_doc = COSDocument()
    xref_table = cos_doc.get_xref_table()
    # add an index for each object key which doesn't match with the index of
    # the object stream; add two object keys only as the stream uses one
    # object number for two objects.
    xref_table[COSObjectKey(6, 0, 10)] = -1
    xref_table[COSObjectKey(4, 0, 11)] = -1
    parser = PDFObjectStreamParser(stream, cos_doc)
    # as the used object numbers aren't unique within the stream the index of
    # the object keys is used. All objects are dropped because the malformed
    # index values don't match the index of the object within the stream.
    object_numbers = parser.parse_all_objects()
    assert len(object_numbers) == 0
