"""Fuzz / parity hardening for ``PDFObjectStreamParser`` (wave 1571).

Hammers the PDF 1.5+ compressed-object-stream (``/ObjStm``) parser across:

* well-formed N-object streams (header ``(objnum offset)`` pairs + ``/First``);
* object retrieval by number (``parse_object``) and by index
  (``parse_all_objects``);
* offset-boundary cases (last object runs to end of the stream view);
* out-of-order offsets (spec says ascending, parser must tolerate descending —
  PDFBOX-4927);
* objects that are themselves dicts / arrays / numbers / booleans / null;
* malformed headers (N over-count with early break, /First missing,
  non-integer in the pair table, negative offset, offset past end);
* the empty (``/N 0``) degenerate stream;
* duplicate object numbers (``index_needed`` disambiguation path);
* an object number that never appears in the table.

Every assertion is anchored to upstream
``org.apache.pdfbox.pdfparser.PDFObjectStreamParser`` (Apache PDFBox 3.0.x)
behaviour, since the port mirrors that class line-for-line.

The fixtures are bare ``COSStream`` bodies — ``PDFObjectStreamParser`` consumes
a ``COSStream`` directly via ``create_view()``; no wrapping PDF is needed.
``read_object_number`` / ``read_long`` both skip leading PDF whitespace, so the
header pairs may be space-separated.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos.cos_array import COSArray
from pypdfbox.cos.cos_boolean import COSBoolean
from pypdfbox.cos.cos_dictionary import COSDictionary
from pypdfbox.cos.cos_document import COSDocument
from pypdfbox.cos.cos_integer import COSInteger
from pypdfbox.cos.cos_name import COSName
from pypdfbox.cos.cos_null import COSNull
from pypdfbox.cos.cos_object_key import COSObjectKey
from pypdfbox.cos.cos_stream import COSStream
from pypdfbox.pdfparser.parse_error import PDFParseError
from pypdfbox.pdfparser.pdf_object_stream_parser import PDFObjectStreamParser

# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------


def _make_stream(n: int, first: int, body: bytes) -> COSStream:
    """Build an ``/ObjStm`` body. ``body`` carries BOTH the header pair table
    and the object payload; ``first`` is the byte offset of the first object."""
    stream = COSStream()
    stream.set_item(COSName.N, COSInteger.get(n))
    stream.set_item(COSName.FIRST, COSInteger.get(first))
    with stream.create_output_stream() as out:
        out.write(body)
    return stream


def _no_doc() -> COSDocument | None:
    # Upstream tests pass a null document; the parser only needs it for
    # get_object_key xref reuse, which is exercised separately below.
    return None


# --------------------------------------------------------------------------
# well-formed N-object header table
# --------------------------------------------------------------------------


def test_read_object_numbers_two_pairs() -> None:
    stream = _make_stream(2, 8, b"4 0 6 5 /Aa /Bb")
    parser = PDFObjectStreamParser(stream, _no_doc())  # type: ignore[arg-type]
    table = parser.read_object_numbers()
    assert table == {4: 0, 6: 5}


def test_read_object_numbers_three_pairs() -> None:
    # header "1 0 2 3 3 7 " -> 12 bytes; bodies /A(0) /BB(3) /CCC(7); /First=12
    stream = _make_stream(3, 12, b"1 0 2 3 3 7 /A /BB /CCC")
    parser = PDFObjectStreamParser(stream, _no_doc())  # type: ignore[arg-type]
    table = parser.read_object_numbers()
    assert table == {1: 0, 2: 3, 3: 7}


def test_read_object_numbers_closes_document_after_call() -> None:
    stream = _make_stream(1, 4, b"7 0 /Z ")
    parser = PDFObjectStreamParser(stream, COSDocument())
    parser.read_object_numbers()
    assert parser._document is None


# --------------------------------------------------------------------------
# parse_object by number
# --------------------------------------------------------------------------


def test_parse_object_first_name() -> None:
    stream = _make_stream(2, 8, b"1 0 2 3 /A /BB")
    parser = PDFObjectStreamParser(stream, _no_doc())  # type: ignore[arg-type]
    obj = parser.parse_object(1)
    assert isinstance(obj, COSName)
    assert obj.get_name() == "A"
    # parsed objects are marked non-direct (upstream setDirect(false)).
    assert obj.is_direct() is False


def test_parse_object_second_name() -> None:
    stream = _make_stream(2, 8, b"1 0 2 3 /A /BB")
    parser = PDFObjectStreamParser(stream, _no_doc())  # type: ignore[arg-type]
    obj = parser.parse_object(2)
    assert isinstance(obj, COSName)
    assert obj.get_name() == "BB"


def test_parse_object_boolean_true() -> None:
    stream = _make_stream(2, 8, b"4 0 6 5 true false")
    parser = PDFObjectStreamParser(stream, _no_doc())  # type: ignore[arg-type]
    assert parser.parse_object(4) is COSBoolean.TRUE


def test_parse_object_boolean_false() -> None:
    stream = _make_stream(2, 8, b"4 0 6 5 true false")
    parser = PDFObjectStreamParser(stream, _no_doc())  # type: ignore[arg-type]
    assert parser.parse_object(6) is COSBoolean.FALSE


def test_parse_object_number_body() -> None:
    stream = _make_stream(1, 4, b"9 0 12345 ")
    parser = PDFObjectStreamParser(stream, _no_doc())  # type: ignore[arg-type]
    obj = parser.parse_object(9)
    assert isinstance(obj, COSInteger)
    assert obj.int_value() == 12345


def test_parse_object_null_body() -> None:
    stream = _make_stream(1, 4, b"9 0 null ")
    parser = PDFObjectStreamParser(stream, _no_doc())  # type: ignore[arg-type]
    assert parser.parse_object(9) is COSNull.NULL


def test_parse_object_unknown_number_returns_none() -> None:
    stream = _make_stream(2, 8, b"1 0 2 3 /A /BB")
    parser = PDFObjectStreamParser(stream, _no_doc())  # type: ignore[arg-type]
    assert parser.parse_object(99) is None


def test_parse_object_clears_document_on_success() -> None:
    stream = _make_stream(1, 4, b"3 0 /Q ")
    parser = PDFObjectStreamParser(stream, COSDocument())
    parser.parse_object(3)
    assert parser._document is None


def test_parse_object_clears_document_on_miss() -> None:
    stream = _make_stream(1, 4, b"3 0 /Q ")
    parser = PDFObjectStreamParser(stream, COSDocument())
    parser.parse_object(404)
    assert parser._document is None


# --------------------------------------------------------------------------
# parse_all_objects
# --------------------------------------------------------------------------


def test_parse_all_objects_two_names() -> None:
    stream = _make_stream(2, 8, b"1 0 2 3 /A /BB")
    parser = PDFObjectStreamParser(stream, _no_doc())  # type: ignore[arg-type]
    result = parser.parse_all_objects()
    by_num = {k.get_number(): v for k, v in result.items()}
    assert by_num[1].get_name() == "A"
    assert by_num[2].get_name() == "BB"


def test_parse_all_objects_keys_are_cos_object_keys() -> None:
    stream = _make_stream(2, 8, b"1 0 2 3 /A /BB")
    parser = PDFObjectStreamParser(stream, _no_doc())  # type: ignore[arg-type]
    result = parser.parse_all_objects()
    assert all(isinstance(k, COSObjectKey) for k in result)
    assert {k.get_generation() for k in result} == {0}


def test_parse_all_objects_marks_non_direct() -> None:
    stream = _make_stream(2, 8, b"1 0 2 3 /A /BB")
    parser = PDFObjectStreamParser(stream, _no_doc())  # type: ignore[arg-type]
    result = parser.parse_all_objects()
    assert all(v.is_direct() is False for v in result.values())


def test_parse_all_objects_clears_document() -> None:
    stream = _make_stream(2, 8, b"1 0 2 3 /A /BB")
    parser = PDFObjectStreamParser(stream, COSDocument())
    parser.parse_all_objects()
    assert parser._document is None


# --------------------------------------------------------------------------
# object bodies that are containers / mixed types
# --------------------------------------------------------------------------


def test_parse_object_dict_body() -> None:
    # body: '<</K 1>> ' at offset 0
    stream = _make_stream(1, 4, b"5 0 <</K 1>> ")
    parser = PDFObjectStreamParser(stream, _no_doc())  # type: ignore[arg-type]
    obj = parser.parse_object(5)
    assert isinstance(obj, COSDictionary)
    assert obj.get_int(COSName.get_pdf_name("K")) == 1


def test_parse_object_array_body() -> None:
    stream = _make_stream(1, 4, b"5 0 [1 2 3] ")
    parser = PDFObjectStreamParser(stream, _no_doc())  # type: ignore[arg-type]
    obj = parser.parse_object(5)
    assert isinstance(obj, COSArray)
    assert [e.int_value() for e in obj] == [1, 2, 3]


def test_parse_all_objects_mixed_types() -> None:
    # /A(0) [9](3) <</X 2>>(7) -> three distinct types; header is 12 bytes
    body = b"1 0 2 3 3 7 /A [9] <</X 2>>"
    stream = _make_stream(3, 12, body)
    parser = PDFObjectStreamParser(stream, _no_doc())  # type: ignore[arg-type]
    result = parser.parse_all_objects()
    by_num = {k.get_number(): v for k, v in result.items()}
    assert isinstance(by_num[1], COSName)
    assert isinstance(by_num[2], COSArray)
    assert isinstance(by_num[3], COSDictionary)


# --------------------------------------------------------------------------
# offset boundary: last object runs to end of the stream view
# --------------------------------------------------------------------------


def test_last_object_runs_to_end() -> None:
    # Two objects; the trailing object has no terminating whitespace and is
    # flush against the end of the stream view.
    stream = _make_stream(2, 8, b"1 0 2 3 /A /LAST")
    parser = PDFObjectStreamParser(stream, _no_doc())  # type: ignore[arg-type]
    obj = parser.parse_object(2)
    assert isinstance(obj, COSName)
    assert obj.get_name() == "LAST"


def test_single_object_flush_to_end() -> None:
    stream = _make_stream(1, 4, b"1 0 /ONLY")
    parser = PDFObjectStreamParser(stream, _no_doc())  # type: ignore[arg-type]
    obj = parser.parse_object(1)
    assert obj.get_name() == "ONLY"


# --------------------------------------------------------------------------
# out-of-order offsets (spec wants ascending; parser must tolerate otherwise)
# --------------------------------------------------------------------------


def test_out_of_order_offsets_parse_object() -> None:
    # header lists obj2 (offset 3) BEFORE obj1 (offset 0).
    stream = _make_stream(2, 8, b"2 3 1 0 /A /BB")
    parser = PDFObjectStreamParser(stream, _no_doc())  # type: ignore[arg-type]
    assert parser.parse_object(1).get_name() == "A"


def test_out_of_order_offsets_parse_object_second() -> None:
    stream = _make_stream(2, 8, b"2 3 1 0 /A /BB")
    parser = PDFObjectStreamParser(stream, _no_doc())  # type: ignore[arg-type]
    assert parser.parse_object(2).get_name() == "BB"


def test_out_of_order_offsets_parse_all_objects_sorted() -> None:
    # parse_all_objects must walk objects in ASCENDING offset order even when
    # the header lists them descending (PDFBOX-4927: the offset map is sorted).
    stream = _make_stream(2, 8, b"2 3 1 0 /A /BB")
    parser = PDFObjectStreamParser(stream, _no_doc())  # type: ignore[arg-type]
    result = parser.parse_all_objects()
    by_num = {k.get_number(): v for k, v in result.items()}
    assert by_num[1].get_name() == "A"
    assert by_num[2].get_name() == "BB"


def test_private_read_object_offsets_returns_sorted_by_offset() -> None:
    stream = _make_stream(2, 8, b"2 3 1 0 /A /BB")
    parser = PDFObjectStreamParser(stream, _no_doc())  # type: ignore[arg-type]
    offsets = parser.private_read_object_offsets()
    # keyed by offset, sorted ascending: {0: 1, 3: 2}
    assert list(offsets.items()) == [(0, 1), (3, 2)]


# --------------------------------------------------------------------------
# empty stream (/N 0)
# --------------------------------------------------------------------------


def test_empty_stream_read_object_numbers() -> None:
    stream = _make_stream(0, 0, b"")
    parser = PDFObjectStreamParser(stream, _no_doc())  # type: ignore[arg-type]
    assert parser.read_object_numbers() == {}


def test_empty_stream_parse_all_objects() -> None:
    stream = _make_stream(0, 0, b"")
    parser = PDFObjectStreamParser(stream, _no_doc())  # type: ignore[arg-type]
    assert parser.parse_all_objects() == {}


def test_empty_stream_parse_object_returns_none() -> None:
    stream = _make_stream(0, 0, b"")
    parser = PDFObjectStreamParser(stream, _no_doc())  # type: ignore[arg-type]
    assert parser.parse_object(1) is None


# --------------------------------------------------------------------------
# malformed headers
# --------------------------------------------------------------------------


def test_missing_n_raises() -> None:
    stream = COSStream()
    stream.set_item(COSName.FIRST, COSInteger.get(0))
    stream.create_output_stream().close()
    with pytest.raises(PDFParseError, match="/N entry missing"):
        PDFObjectStreamParser(stream, _no_doc())  # type: ignore[arg-type]


def test_missing_first_raises() -> None:
    stream = COSStream()
    stream.set_item(COSName.N, COSInteger.get(0))
    stream.create_output_stream().close()
    with pytest.raises(PDFParseError, match="/First entry missing"):
        PDFObjectStreamParser(stream, _no_doc())  # type: ignore[arg-type]


def test_negative_n_raises() -> None:
    # /N == -1 is indistinguishable from "missing" (getInt sentinel, both
    # upstream and port), so use -2 to reach the dedicated "Illegal /N" branch.
    stream = _make_stream(-2, 0, b"")
    with pytest.raises(PDFParseError, match="Illegal /N entry"):
        PDFObjectStreamParser(stream, _no_doc())  # type: ignore[arg-type]


def test_negative_first_raises() -> None:
    stream = _make_stream(0, -5, b"")
    with pytest.raises(PDFParseError, match="Illegal /First entry"):
        PDFObjectStreamParser(stream, _no_doc())  # type: ignore[arg-type]


def test_n_overcount_breaks_early_at_first_boundary() -> None:
    # /N declares 5 pairs but only 2 fit before /First=8; the walker breaks at
    # the first_object boundary instead of reading into object payload.
    stream = _make_stream(5, 8, b"1 0 2 3 /A /BB")
    parser = PDFObjectStreamParser(stream, _no_doc())  # type: ignore[arg-type]
    table = parser.read_object_numbers()
    assert table == {1: 0, 2: 3}


def test_n_overcount_parse_all_objects_still_resolves() -> None:
    stream = _make_stream(5, 8, b"1 0 2 3 /A /BB")
    parser = PDFObjectStreamParser(stream, _no_doc())  # type: ignore[arg-type]
    result = parser.parse_all_objects()
    by_num = {k.get_number(): v for k, v in result.items()}
    assert by_num[1].get_name() == "A"
    assert by_num[2].get_name() == "BB"


def test_non_integer_in_header_offset_raises() -> None:
    # offset slot is not a digit ("X") -> read_long raises while building the
    # header table; parse_all_objects propagates and still clears document.
    stream = _make_stream(1, 6, b"1 X   /A ")
    parser = PDFObjectStreamParser(stream, COSDocument())
    with pytest.raises(PDFParseError):
        parser.parse_all_objects()
    assert parser._document is None


def test_truncated_header_only_objnum_raises() -> None:
    # header has the object number but no offset before /First boundary.
    stream = _make_stream(1, 5, b"42   ")
    parser = PDFObjectStreamParser(stream, COSDocument())
    with pytest.raises(PDFParseError):
        parser.read_object_numbers()
    assert parser._document is None


def test_offset_past_end_parse_object_returns_none() -> None:
    # offset 999 jumps past the end of the view; parse_dir_object hits EOF and
    # returns None (mirrors upstream: source.skip then parseDirObject -> null).
    stream = _make_stream(1, 6, b"1 999 /A ")
    parser = PDFObjectStreamParser(stream, _no_doc())  # type: ignore[arg-type]
    assert parser.parse_object(1) is None


def test_negative_object_number_in_header_raises() -> None:
    # read_object_number rejects negatives (BaseParser threshold guard).
    stream = _make_stream(1, 6, b"-3 0 /A ")
    parser = PDFObjectStreamParser(stream, COSDocument())
    with pytest.raises(PDFParseError):
        parser.read_object_numbers()


# --------------------------------------------------------------------------
# duplicate object numbers (index_needed disambiguation)
# --------------------------------------------------------------------------


def test_duplicate_object_numbers_parse_all_objects() -> None:
    # object 1 appears twice (offsets 0 and 3); index_needed flips True.
    stream = _make_stream(2, 8, b"1 0 1 3 /A /BB")
    parser = PDFObjectStreamParser(stream, COSDocument())
    result = parser.parse_all_objects()
    # at least one survives the dedup loop; both share object number 1.
    assert len(result) >= 1
    assert all(k.get_number() == 1 for k in result)


def test_duplicate_object_numbers_index_continue_branch() -> None:
    # Pre-seed the xref with an index=1 key so iteration 0 (offset 0) is
    # skipped via the continue branch and the second entry is the one kept.
    doc = COSDocument()
    indexed_key = COSObjectKey(1, 0, index=1)
    doc.get_xref_table()[indexed_key] = 0
    stream = _make_stream(2, 8, b"1 0 1 3 /A /BB")
    parser = PDFObjectStreamParser(stream, doc)
    result = parser.parse_all_objects()
    assert indexed_key in result


# --------------------------------------------------------------------------
# get_object_key xref reuse
# --------------------------------------------------------------------------


def test_get_object_key_reuses_cached_instance() -> None:
    doc = COSDocument()
    cached = COSObjectKey(7, 0)
    doc.get_xref_table()[cached] = 10
    stream = _make_stream(0, 0, b"")
    parser = PDFObjectStreamParser(stream, doc)
    assert parser.get_object_key(7, 0) is cached


def test_get_object_key_constructs_fresh_when_absent() -> None:
    stream = _make_stream(0, 0, b"")
    parser = PDFObjectStreamParser(stream, COSDocument())
    key = parser.get_object_key(13, 0)
    assert key.get_number() == 13
    assert key.get_generation() == 0


# --------------------------------------------------------------------------
# parse_object after a read_object_numbers on a fresh parser instance
# --------------------------------------------------------------------------


def test_read_object_numbers_then_fresh_parse_object() -> None:
    # read_object_numbers closes the view; a second operation needs a fresh
    # parser (the source is single-shot, matching upstream).
    body = b"1 0 2 3 /A /BB"
    p1 = PDFObjectStreamParser(_make_stream(2, 8, body), _no_doc())  # type: ignore[arg-type]
    assert p1.read_object_numbers() == {1: 0, 2: 3}
    p2 = PDFObjectStreamParser(_make_stream(2, 8, body), _no_doc())  # type: ignore[arg-type]
    assert p2.parse_object(2).get_name() == "BB"


def test_three_objects_each_retrievable_by_number() -> None:
    body = b"1 0 2 3 3 7 /A /BB /CCC"
    for num, name in [(1, "A"), (2, "BB"), (3, "CCC")]:
        parser = PDFObjectStreamParser(
            _make_stream(3, 12, body),
            _no_doc(),  # type: ignore[arg-type]
        )
        assert parser.parse_object(num).get_name() == name
