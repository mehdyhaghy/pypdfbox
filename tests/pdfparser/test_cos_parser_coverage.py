"""Wave 1323: coverage-boost tests for :mod:`pypdfbox.pdfparser.cos_parser`.

Targets the uncovered branches in COSParser's upstream-parity surface —
``check_pages`` / ``check_pages_dictionary`` kid-pruning, ``get_encryption``
/ ``get_access_permission`` / ``prepare_decryption`` accessors,
``get_startxref_offset`` edge cases, ``parse_trailer`` lenient branches,
``parse_xref`` chain walking, ``parse_xref_obj_stream``, ``parse_file_object``
stream branch, ``get_length`` indirect-reference flow, ``read_until_end_stream``
state machine, ``validate_stream_length`` size checks, the lenient
``check_x_ref_offset`` / ``check_x_ref_stream_offset`` paths,
``calculate_x_ref_fixed_offset``, ``validate_xref_offsets`` /
``check_xref_offsets``, and ``find_object_key`` generation-correction.
"""

from __future__ import annotations

from typing import Any

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSDocument,
    COSFloat,
    COSInteger,
    COSName,
    COSNull,
    COSObject,
    COSObjectKey,
)
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser import PDFParseError
from pypdfbox.pdfparser.cos_parser import COSParser

# ----------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------


def _make_parser(
    payload: bytes, document: COSDocument | None = None
) -> COSParser:
    return COSParser(RandomAccessReadBuffer(payload), document)


# ----------------------------------------------------------------------
# parse_header — empty version_bytes fallback (line 988)
# ----------------------------------------------------------------------


def test_parse_header_returns_default_when_no_version_digits() -> None:
    # Marker present but immediately followed by a newline — no version
    # digits to parse, so the helper returns ``default_version``.
    parser = _make_parser(b"%PDF-\n%%EOF\n")
    assert parser.parse_header("%PDF-", "1.4") == 1.4


def test_parse_header_raises_when_marker_missing() -> None:
    parser = _make_parser(b"not a pdf")
    with pytest.raises(PDFParseError, match="missing"):
        parser.parse_header("%PDF-", "1.4")


def test_parse_header_accepts_bytes_marker() -> None:
    parser = _make_parser(b"%PDF-1.7\n%%EOF\n")
    assert parser.parse_header(b"%PDF-", "1.4") == 1.7


# ----------------------------------------------------------------------
# check_pages + check_pages_dictionary
# ----------------------------------------------------------------------


def _root_with_pages(pages: COSDictionary | None) -> COSDictionary:
    root = COSDictionary()
    if pages is not None:
        root.set_item(COSName.get_pdf_name("Pages"), pages)
    return root


def test_check_pages_raises_when_pages_root_not_dict() -> None:
    parser = _make_parser(b"")
    root = COSDictionary()
    # No /Pages entry — get_dictionary_object returns None, not a dict.
    with pytest.raises(PDFParseError, match="Page tree root"):
        parser.check_pages(root)


def test_check_pages_invokes_kid_walker_when_trailer_rebuilt() -> None:
    parser = _make_parser(b"")
    parser._trailer_was_rebuild = True  # type: ignore[attr-defined]
    pages = COSDictionary()
    pages.set_item(COSName.get_pdf_name("Kids"), COSArray())
    pages.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("Pages"))
    root = _root_with_pages(pages)
    parser.check_pages(root)
    # /Count entry written by walker even for an empty /Kids array.
    count = pages.get_dictionary_object(COSName.get_pdf_name("Count"))
    assert isinstance(count, COSInteger)
    assert count.value == 0


def test_check_pages_dictionary_removes_non_cos_object_kid() -> None:
    parser = _make_parser(b"")
    pages = COSDictionary()
    kids = COSArray()
    # Kid is a plain dictionary (not a COSObject reference) -> pruned.
    raw_kid = COSDictionary()
    raw_kid.set_item(
        COSName.get_pdf_name("Type"), COSName.get_pdf_name("Page")
    )
    kids.add(raw_kid)
    pages.set_item(COSName.get_pdf_name("Kids"), kids)
    count = parser.check_pages_dictionary(pages, set())
    assert count == 0
    assert kids.size() == 0


def test_check_pages_dictionary_removes_seen_kid() -> None:
    parser = _make_parser(b"")
    page_dict = COSDictionary()
    page_dict.set_item(
        COSName.get_pdf_name("Type"), COSName.get_pdf_name("Page")
    )
    ref = COSObject(7, 0, resolved=page_dict)
    pages = COSDictionary()
    kids = COSArray()
    kids.add(ref)
    pages.set_item(COSName.get_pdf_name("Kids"), kids)
    # Pretend we already visited the reference -> pruned.
    seen: set[Any] = {ref}
    count = parser.check_pages_dictionary(pages, seen)
    assert count == 0
    assert kids.size() == 0


def test_check_pages_dictionary_removes_null_target_kid() -> None:
    parser = _make_parser(b"")
    null_ref = COSObject(3, 0, resolved=COSNull.NULL)
    pages = COSDictionary()
    kids = COSArray()
    kids.add(null_ref)
    pages.set_item(COSName.get_pdf_name("Kids"), kids)
    count = parser.check_pages_dictionary(pages, set())
    assert count == 0
    assert kids.size() == 0


def test_check_pages_dictionary_counts_leaf_pages() -> None:
    parser = _make_parser(b"")
    leaf = COSDictionary()
    leaf.set_item(
        COSName.get_pdf_name("Type"), COSName.get_pdf_name("Page")
    )
    ref = COSObject(11, 0, resolved=leaf)
    pages = COSDictionary()
    kids = COSArray()
    kids.add(ref)
    pages.set_item(COSName.get_pdf_name("Kids"), kids)
    assert parser.check_pages_dictionary(pages, set()) == 1


def test_check_pages_dictionary_recurses_into_pages_node() -> None:
    parser = _make_parser(b"")
    leaf = COSDictionary()
    leaf.set_item(
        COSName.get_pdf_name("Type"), COSName.get_pdf_name("Page")
    )
    leaf_ref = COSObject(22, 0, resolved=leaf)
    inner = COSDictionary()
    inner.set_item(
        COSName.get_pdf_name("Type"), COSName.get_pdf_name("Pages")
    )
    inner_kids = COSArray()
    inner_kids.add(leaf_ref)
    inner.set_item(COSName.get_pdf_name("Kids"), inner_kids)
    inner_ref = COSObject(21, 0, resolved=inner)
    root_kids = COSArray()
    root_kids.add(inner_ref)
    root = COSDictionary()
    root.set_item(COSName.get_pdf_name("Kids"), root_kids)
    assert parser.check_pages_dictionary(root, set()) == 1


# ----------------------------------------------------------------------
# encryption surface
# ----------------------------------------------------------------------


def test_get_encryption_raises_when_document_unbound() -> None:
    parser = _make_parser(b"")
    with pytest.raises(PDFParseError, match="parse the document first"):
        parser.get_encryption()


def test_get_encryption_returns_none_when_no_encrypt_dict() -> None:
    doc = COSDocument()
    parser = _make_parser(b"", doc)
    assert parser.get_encryption() is None


def test_get_encryption_returns_pd_encryption_when_present() -> None:
    doc = COSDocument()
    enc = COSDictionary()
    enc.set_item(
        COSName.get_pdf_name("Filter"), COSName.get_pdf_name("Standard")
    )
    enc.set_item(COSName.get_pdf_name("V"), COSInteger.get(1))
    enc.set_item(COSName.get_pdf_name("R"), COSInteger.get(2))
    trailer = COSDictionary()
    trailer.set_item(COSName.get_pdf_name("Encrypt"), enc)
    doc.set_trailer(trailer)
    parser = _make_parser(b"", doc)
    encryption = parser.get_encryption()
    # Either a PDEncryption wrapper or the raw dict (when the import path
    # is unavailable); both branches are valid per the source contract.
    assert encryption is not None


def test_get_access_permission_raises_when_document_unbound() -> None:
    parser = _make_parser(b"")
    with pytest.raises(PDFParseError, match="parse the document first"):
        parser.get_access_permission()


def test_get_access_permission_none_when_no_handler() -> None:
    parser = _make_parser(b"", COSDocument())
    assert parser.get_access_permission() is None


def test_get_access_permission_delegates_to_handler() -> None:
    parser = _make_parser(b"", COSDocument())

    class _StubHandler:
        def get_current_access_permission(self) -> str:
            return "perm-token"

    parser._security_handler = _StubHandler()  # type: ignore[attr-defined]
    assert parser.get_access_permission() == "perm-token"


def test_get_access_permission_returns_none_when_handler_lacks_method() -> None:
    parser = _make_parser(b"", COSDocument())
    parser._security_handler = object()  # type: ignore[attr-defined]
    assert parser.get_access_permission() is None


def test_prepare_decryption_no_op_without_document() -> None:
    parser = _make_parser(b"")
    parser.prepare_decryption()  # no raise


def test_prepare_decryption_no_op_without_encrypt_dict() -> None:
    parser = _make_parser(b"", COSDocument())
    parser.prepare_decryption()


def test_prepare_decryption_idempotent_with_handler_attached() -> None:
    doc = COSDocument()
    enc = COSDictionary()
    trailer = COSDictionary()
    trailer.set_item(COSName.get_pdf_name("Encrypt"), enc)
    doc.set_trailer(trailer)
    parser = _make_parser(b"", doc)
    parser._security_handler = object()  # type: ignore[attr-defined]
    sentinel = parser._security_handler  # type: ignore[attr-defined]
    parser.prepare_decryption()
    # Handler unchanged — early-return branch covered.
    assert parser._security_handler is sentinel  # type: ignore[attr-defined]


# ----------------------------------------------------------------------
# get_startxref_offset edge cases
# ----------------------------------------------------------------------


def test_get_startxref_offset_lenient_treats_missing_eof_as_end() -> None:
    # Has 'startxref' but no '%%EOF' — lenient mode tolerates that.
    payload = b"startxref\n123\n"
    parser = _make_parser(payload)
    offset = parser.get_startxref_offset()
    assert offset == payload.find(b"startxref")


def test_get_startxref_offset_strict_raises_on_missing_eof() -> None:
    parser = _make_parser(b"startxref\n123\n")
    parser.set_lenient(False)
    with pytest.raises(PDFParseError, match="end of file"):
        parser.get_startxref_offset()


def test_get_startxref_offset_raises_when_startxref_missing() -> None:
    parser = _make_parser(b"%%EOF\n")
    with pytest.raises(PDFParseError, match="startxref"):
        parser.get_startxref_offset()


def test_get_startxref_offset_raises_when_file_len_negative() -> None:
    parser = _make_parser(b"x")
    parser.set_file_len(-1)
    with pytest.raises(PDFParseError, match="source length"):
        parser.get_startxref_offset()


# ----------------------------------------------------------------------
# parse_start_xref + parse_trailer
# ----------------------------------------------------------------------


def test_parse_start_xref_reads_offset() -> None:
    parser = _make_parser(b"startxref\n42\n")
    assert parser.parse_start_xref() == 42


def test_parse_start_xref_returns_minus_one_when_keyword_absent() -> None:
    parser = _make_parser(b"trailer\n")
    assert parser.parse_start_xref() == -1


def test_parse_trailer_basic_success() -> None:
    payload = b"trailer\n<< /Size 5 >>\n"
    parser = _make_parser(payload)
    assert parser.parse_trailer() is True
    trailer = parser._last_parsed_trailer  # type: ignore[attr-defined]
    assert isinstance(trailer, COSDictionary)
    assert trailer.get_dictionary_object(
        COSName.get_pdf_name("Size")
    ).value == 5  # type: ignore[union-attr]


def test_parse_trailer_returns_false_when_no_trailer() -> None:
    parser = _make_parser(b"xref\n0 0\n")
    assert parser.parse_trailer() is False


def test_parse_trailer_lenient_skips_leading_digits() -> None:
    # PDFBOX-1739 — RegisSTAR documents prepend digit lines.
    parser = _make_parser(b"00000\ntrailer\n<< /Size 1 >>\n")
    assert parser.parse_trailer() is True


def test_parse_trailer_on_same_line_as_keyword() -> None:
    # EOL missing after 'trailer' — keyword is followed immediately by '<<'.
    parser = _make_parser(b"trailer<< /Size 9 >>\n")
    assert parser.parse_trailer() is True


def test_parse_trailer_returns_false_when_keyword_mismatched() -> None:
    parser = _make_parser(b"tEatlme\n")
    assert parser.parse_trailer() is False


def test_parse_trailer_sets_trailer_on_document() -> None:
    doc = COSDocument()
    parser = _make_parser(b"trailer\n<< /Size 7 >>\n", doc)
    parser.parse_trailer()
    trailer = doc.get_trailer()
    assert isinstance(trailer, COSDictionary)
    assert trailer.get_dictionary_object(
        COSName.get_pdf_name("Size")
    ).value == 7  # type: ignore[union-attr]


def test_parse_trailer_preserves_existing_trailer_on_document() -> None:
    doc = COSDocument()
    existing = COSDictionary()
    existing.set_item(COSName.get_pdf_name("Size"), COSInteger.get(99))
    doc.set_trailer(existing)
    parser = _make_parser(b"trailer\n<< /Size 7 >>\n", doc)
    parser.parse_trailer()
    # Original trailer kept; just the parser cache holds the second one.
    assert doc.get_trailer() is existing


# ----------------------------------------------------------------------
# get_length — indirect-reference resolution
# ----------------------------------------------------------------------


def test_get_length_returns_none_for_none() -> None:
    parser = _make_parser(b"")
    assert parser.get_length(None) is None


def test_get_length_returns_direct_integer() -> None:
    parser = _make_parser(b"")
    assert parser.get_length(COSInteger.get(42)) is COSInteger.get(42)


def test_get_length_returns_direct_float() -> None:
    parser = _make_parser(b"")
    length = COSFloat(3.14)
    assert parser.get_length(length) is length


def test_get_length_resolves_indirect_integer() -> None:
    parser = _make_parser(b"")
    inner = COSInteger.get(101)
    ref = COSObject(7, 0, resolved=inner)
    assert parser.get_length(ref) is inner


def test_get_length_returns_none_for_indirect_null() -> None:
    parser = _make_parser(b"")
    ref = COSObject(8, 0, resolved=COSNull.NULL)
    assert parser.get_length(ref) is None


def test_get_length_raises_when_indirect_target_unread() -> None:
    parser = _make_parser(b"")
    # COSObject with no resolved value and no loader -> get_object() yields None.
    ref = COSObject(9, 0)
    with pytest.raises(PDFParseError, match="content was not read"):
        parser.get_length(ref)


def test_get_length_raises_for_wrong_indirect_type() -> None:
    parser = _make_parser(b"")
    # Indirect reference to a dict — invalid /Length type.
    ref = COSObject(10, 0, resolved=COSDictionary())
    with pytest.raises(PDFParseError, match="Wrong type of referenced"):
        parser.get_length(ref)


def test_get_length_raises_for_wrong_direct_type() -> None:
    parser = _make_parser(b"")
    with pytest.raises(PDFParseError, match="Wrong type of length object"):
        parser.get_length(COSDictionary())


# ----------------------------------------------------------------------
# read_until_end_stream — state machine
# ----------------------------------------------------------------------


def test_read_until_end_stream_writes_body_until_endstream() -> None:
    parser = _make_parser(b"hello\nworld\nendstream\n")
    out = bytearray()
    consumed = parser.read_until_end_stream(out)
    # 'hello\nworld\n' = 12 bytes consumed before terminator.
    assert consumed == 12
    assert out == b"hello\nworld\n"


def test_read_until_end_stream_handles_endobj_alternate() -> None:
    # Producer omitted 'endstream' and went straight to 'endobj'.
    parser = _make_parser(b"abcdefendobj\n")
    out = bytearray()
    parser.read_until_end_stream(out)
    assert out.startswith(b"abcdef")


def test_read_until_end_stream_returns_at_eof_without_terminator() -> None:
    parser = _make_parser(b"hello")
    out = bytearray()
    consumed = parser.read_until_end_stream(out)
    assert consumed == 5
    assert out == b"hello"


def test_read_until_end_stream_with_none_buffer() -> None:
    # Bytes consumed but not recorded — out=None branch.
    parser = _make_parser(b"abcendstream\n")
    consumed = parser.read_until_end_stream(None)
    assert consumed == 3


def test_read_until_end_stream_handles_false_prefix_reset() -> None:
    # 'ende' is a false start — match resets, body keeps 'end'.
    parser = _make_parser(b"endeendstream\n")
    out = bytearray()
    parser.read_until_end_stream(out)
    assert b"ende" in bytes(out)


# ----------------------------------------------------------------------
# validate_stream_length
# ----------------------------------------------------------------------


def test_validate_stream_length_returns_false_for_zero() -> None:
    parser = _make_parser(b"endstream\n")
    assert parser.validate_stream_length(0) is False


def test_validate_stream_length_returns_false_for_negative() -> None:
    parser = _make_parser(b"endstream\n")
    assert parser.validate_stream_length(-5) is False


def test_validate_stream_length_returns_false_when_exceeds_file_len() -> None:
    parser = _make_parser(b"abcd")
    assert parser.validate_stream_length(1_000_000) is False


def test_validate_stream_length_returns_true_when_endstream_follows() -> None:
    # Body 'abcde' is 5 bytes; then 'endstream' is the terminator.
    payload = b"abcdeendstream\nrest"
    parser = _make_parser(payload)
    # Seek source past the body? Position starts at 0 — pass length 5.
    assert parser.validate_stream_length(5) is True


def test_validate_stream_length_returns_false_when_no_endstream() -> None:
    parser = _make_parser(b"abcdeXXXXX")
    assert parser.validate_stream_length(5) is False


# ----------------------------------------------------------------------
# check_x_ref_offset / check_x_ref_stream_offset
# ----------------------------------------------------------------------


def test_check_x_ref_offset_strict_returns_input() -> None:
    parser = _make_parser(b"any")
    parser.set_lenient(False)
    assert parser.check_x_ref_offset(42) == 42


def test_check_x_ref_offset_lenient_detects_literal_xref() -> None:
    payload = b"   xref\n0 1\n"
    parser = _make_parser(payload)
    # Pass offset 0 — skip_spaces will land at 'xref'.
    assert parser.check_x_ref_offset(0) == 0


def test_check_x_ref_offset_returns_minus_one_for_zero_when_no_xref() -> None:
    payload = b"%not-xref"
    parser = _make_parser(payload)
    assert parser.check_x_ref_offset(0) == -1


def test_check_x_ref_stream_offset_returns_true_when_zero() -> None:
    # offset == 0 short-circuits to True regardless of contents.
    parser = _make_parser(b"x")
    assert parser.check_x_ref_stream_offset(0) is True


def test_check_x_ref_stream_offset_returns_false_when_no_whitespace_before() -> None:
    # First byte not whitespace before offset -> reject.
    payload = b"x5 0 obj\n<< /Type /XRef >>\nendobj\n"
    parser = _make_parser(payload)
    assert parser.check_x_ref_stream_offset(1) is False


def test_check_x_ref_stream_offset_returns_false_when_not_digit() -> None:
    payload = b"\n%comment\n"
    parser = _make_parser(payload)
    # Offset after the leading newline — '%' is not a digit.
    assert parser.check_x_ref_stream_offset(1) is False


def test_check_x_ref_stream_offset_returns_true_for_xref_stream() -> None:
    payload = b"\n5 0 obj\n<< /Type /XRef >>\nendobj\n"
    parser = _make_parser(payload)
    # Offset 1 (after \n) — '5' is the start of the object number.
    assert parser.check_x_ref_stream_offset(1) is True


def test_check_x_ref_stream_offset_returns_false_for_non_xref_type() -> None:
    payload = b"\n5 0 obj\n<< /Type /Foo >>\nendobj\n"
    parser = _make_parser(payload)
    assert parser.check_x_ref_stream_offset(1) is False


def test_check_x_ref_stream_offset_returns_false_for_non_dict_body() -> None:
    payload = b"\n5 0 obj\n[1 2 3]\nendobj\n"
    parser = _make_parser(payload)
    assert parser.check_x_ref_stream_offset(1) is False


def test_check_x_ref_stream_offset_returns_false_on_parse_error() -> None:
    payload = b"\n@@@bad header"
    parser = _make_parser(payload)
    assert parser.check_x_ref_stream_offset(1) is False


# ----------------------------------------------------------------------
# calculate_x_ref_fixed_offset
# ----------------------------------------------------------------------


def test_calculate_x_ref_fixed_offset_negative_returns_zero() -> None:
    parser = _make_parser(b"")
    assert parser.calculate_x_ref_fixed_offset(-5) == 0


def test_calculate_x_ref_fixed_offset_no_match_returns_zero() -> None:
    # Source has no 'xref' keyword — brute force returns -1 -> 0.
    parser = _make_parser(b"%PDF-1.4\n%just-content\n")
    assert parser.calculate_x_ref_fixed_offset(50) == 0


def test_calculate_x_ref_fixed_offset_finds_literal_xref() -> None:
    payload = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\nxref\n0 1\n"
    parser = _make_parser(payload)
    found = parser.calculate_x_ref_fixed_offset(60)
    assert found == payload.find(b"xref\n")


# ----------------------------------------------------------------------
# validate_xref_offsets + check_xref_offsets + find_object_key
# ----------------------------------------------------------------------


def test_validate_xref_offsets_returns_true_for_none() -> None:
    parser = _make_parser(b"")
    assert parser.validate_xref_offsets(None) is True


def test_validate_xref_offsets_skips_negative_offsets() -> None:
    parser = _make_parser(b"")
    table: dict[COSObjectKey, int] = {COSObjectKey(1, 0): -1}
    assert parser.validate_xref_offsets(table) is True
    assert COSObjectKey(1, 0) in table


def test_validate_xref_offsets_succeeds_for_matching_object() -> None:
    payload = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n"
    parser = _make_parser(payload)
    offset = payload.find(b"1 0 obj")
    table = {COSObjectKey(1, 0): offset}
    assert parser.validate_xref_offsets(table) is True


def test_validate_xref_offsets_returns_false_on_missing_object() -> None:
    parser = _make_parser(b"%PDF-1.4\n%nothing\n")
    table = {COSObjectKey(99, 0): 0}
    assert parser.validate_xref_offsets(table) is False


def test_validate_xref_offsets_corrects_generation_number() -> None:
    # Object stored at offset declares generation 5 but the xref table
    # says 0 — lenient mode accepts the larger generation as correct.
    payload = b"%PDF-1.4\n1 5 obj\n<<>>\nendobj\n"
    parser = _make_parser(payload)
    offset = payload.find(b"1 5 obj")
    table = {COSObjectKey(1, 0): offset}
    assert parser.validate_xref_offsets(table) is True
    assert COSObjectKey(1, 5) in table
    assert COSObjectKey(1, 0) not in table


def test_check_xref_offsets_no_op_without_document() -> None:
    parser = _make_parser(b"")
    parser.check_xref_offsets()  # no raise, no doc to mutate


def test_check_xref_offsets_rebuilds_on_failure() -> None:
    payload = (
        b"%PDF-1.4\n"
        b"1 0 obj\n<<>>\nendobj\n"
        b"7 0 obj\n<<>>\nendobj\n"
        b"%%EOF\n"
    )
    doc = COSDocument()
    # Xref claims object 99 at offset 0 -> validate fails -> brute scan.
    doc.get_xref_table()[COSObjectKey(99, 0)] = 5
    parser = _make_parser(payload, doc)
    parser.check_xref_offsets()
    table = doc.get_xref_table()
    assert COSObjectKey(99, 0) not in table
    assert COSObjectKey(1, 0) in table


def test_find_object_key_returns_none_below_minimum_offset() -> None:
    parser = _make_parser(b"some-data")
    assert (
        parser.find_object_key(COSObjectKey(1, 0), 0, {})
        is None
    )


def test_find_object_key_returns_corrected_object_number_in_lenient() -> None:
    payload = b"%PDF-1.4\n2 0 obj\n<<>>\nendobj\n"
    parser = _make_parser(payload)
    offset = payload.find(b"2 0 obj")
    # Lookup with wrong object number (1) — lenient correction yields a
    # key with the actually-found object number (2).
    key = parser.find_object_key(COSObjectKey(1, 0), offset, {})
    assert key == COSObjectKey(2, 0)


def test_find_object_key_strict_rejects_object_number_mismatch() -> None:
    payload = b"%PDF-1.4\n2 0 obj\n<<>>\nendobj\n"
    parser = _make_parser(payload)
    parser.set_lenient(False)
    offset = payload.find(b"2 0 obj")
    assert (
        parser.find_object_key(COSObjectKey(1, 0), offset, {})
        is None
    )


def test_find_object_key_returns_none_on_parse_error() -> None:
    parser = _make_parser(b"garbage-no-header")
    # Offset is past header threshold but body is not a valid object.
    assert (
        parser.find_object_key(COSObjectKey(1, 0), 10, {})
        is None
    )


# ----------------------------------------------------------------------
# get_object_offset
# ----------------------------------------------------------------------


def test_get_object_offset_no_document_strict_raises() -> None:
    parser = _make_parser(b"")
    with pytest.raises(PDFParseError, match="Object must be defined"):
        parser.get_object_offset(COSObjectKey(1, 0), True)


def test_get_object_offset_no_document_non_strict_returns_none() -> None:
    parser = _make_parser(b"")
    assert (
        parser.get_object_offset(COSObjectKey(1, 0), False) is None
    )


def test_get_object_offset_returns_known_offset() -> None:
    doc = COSDocument()
    doc.get_xref_table()[COSObjectKey(2, 0)] = 99
    parser = _make_parser(b"", doc)
    assert parser.get_object_offset(COSObjectKey(2, 0), False) == 99


def test_get_object_offset_lenient_brute_force_records_recovered_offset() -> None:
    payload = b"%PDF-1.4\n5 0 obj\n<<>>\nendobj\n"
    doc = COSDocument()  # empty xref table
    parser = _make_parser(payload, doc)
    offset = parser.get_object_offset(COSObjectKey(5, 0), False)
    assert offset is not None
    # And the recovered offset is now stored back in the table.
    assert doc.get_xref_table()[COSObjectKey(5, 0)] == offset


def test_get_object_offset_strict_raises_when_compressed() -> None:
    doc = COSDocument()
    # Negative offset == compressed object indicator.
    doc.get_xref_table()[COSObjectKey(3, 0)] = -1
    parser = _make_parser(b"", doc)
    with pytest.raises(PDFParseError, match="Object must be defined"):
        parser.get_object_offset(COSObjectKey(3, 0), True)


# ----------------------------------------------------------------------
# parse_file_object — stream branch
# ----------------------------------------------------------------------


def test_parse_file_object_returns_direct_object_body() -> None:
    payload = b"1 0 obj\n<< /Size 1 >>\nendobj\n"
    parser = _make_parser(payload)
    parsed = parser.parse_file_object(0, COSObjectKey(1, 0))
    assert isinstance(parsed, COSDictionary)
    assert parsed.get_dictionary_object(
        COSName.get_pdf_name("Size")
    ).value == 1  # type: ignore[union-attr]


def test_parse_file_object_raises_on_object_key_mismatch() -> None:
    payload = b"2 0 obj\n<<>>\nendobj\n"
    parser = _make_parser(payload)
    with pytest.raises(PDFParseError, match="points to wrong object"):
        parser.parse_file_object(0, COSObjectKey(1, 0))


def test_parse_file_object_raises_when_stream_lacks_dict() -> None:
    # 'stream' keyword preceded by an integer (not a dict) — illegal.
    payload = b"1 0 obj\n42\nstream\nbody\nendstream\nendobj\n"
    parser = _make_parser(payload)
    with pytest.raises(PDFParseError, match="Stream not preceded by"):
        parser.parse_file_object(0, COSObjectKey(1, 0))


# ----------------------------------------------------------------------
# parse_xref + parse_xref_obj_stream
# ----------------------------------------------------------------------


def test_parse_xref_returns_trailer_for_traditional_xref() -> None:
    # A minimal one-section xref + trailer with no /Prev.
    body = (
        b"%PDF-1.4\n"
        b"1 0 obj\n<<>>\nendobj\n"
        b"xref\n"
        b"0 2\n"
        b"0000000000 65535 f \n"
        b"0000000009 00000 n \n"
        b"trailer\n"
        b"<< /Size 2 >>\n"
        b"startxref\n"
    )
    xref_offset = body.find(b"xref\n")
    payload = body + str(xref_offset).encode() + b"\n%%EOF\n"
    doc = COSDocument()
    parser = _make_parser(payload, doc)
    trailer = parser.parse_xref(payload.find(b"startxref"))
    assert isinstance(trailer, COSDictionary)
    assert trailer.get_dictionary_object(
        COSName.get_pdf_name("Size")
    ).value == 2  # type: ignore[union-attr]


def test_parse_xref_obj_stream_returns_minus_one_when_no_prev() -> None:
    # Object body: dict only (no stream keyword) — easy variant.
    payload = (
        b"5 0 obj\n<< /Type /XRef /Size 3 >>\nendobj\n"
    )
    parser = _make_parser(payload, COSDocument())
    prev = parser.parse_xref_obj_stream(0, True)
    assert prev == -1


def test_parse_xref_obj_stream_reads_prev() -> None:
    payload = b"5 0 obj\n<< /Type /XRef /Prev 12345 >>\nendobj\n"
    parser = _make_parser(payload, COSDocument())
    assert parser.parse_xref_obj_stream(0, True) == 12345


def test_parse_xref_obj_stream_raises_for_non_dict_body() -> None:
    payload = b"5 0 obj\n[1 2 3]\nendobj\n"
    parser = _make_parser(payload, COSDocument())
    with pytest.raises(PDFParseError, match="not a dictionary"):
        parser.parse_xref_obj_stream(0, True)


def test_parse_xref_obj_stream_non_standalone_does_not_register_trailer() -> None:
    doc = COSDocument()
    payload = b"5 0 obj\n<< /Type /XRef >>\nendobj\n"
    parser = _make_parser(payload, doc)
    parser.parse_xref_obj_stream(0, False)
    # is_standalone=False — trailer not set on doc.
    assert doc.get_trailer() is None


# ----------------------------------------------------------------------
# get_brute_force_parser
# ----------------------------------------------------------------------


def test_get_brute_force_parser_returns_self() -> None:
    parser = _make_parser(b"")
    assert parser.get_brute_force_parser() is parser


# ----------------------------------------------------------------------
# init — honors env override
# ----------------------------------------------------------------------


def test_init_no_op_when_env_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    parser = _make_parser(b"")
    monkeypatch.delenv(parser.SYSPROP_EOFLOOKUPRANGE, raising=False)
    parser.init()
    assert parser.get_eof_lookup_range() == COSParser.DEFAULT_TRAIL_BYTECOUNT


def test_init_applies_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        COSParser.SYSPROP_EOFLOOKUPRANGE, "4096"
    )
    parser = _make_parser(b"")
    parser.init()
    assert parser.get_eof_lookup_range() == 4096


def test_init_ignores_invalid_env_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(COSParser.SYSPROP_EOFLOOKUPRANGE, "not-a-number")
    parser = _make_parser(b"")
    parser.init()
    # Unchanged from the default — invalid override silently rejected.
    assert parser.get_eof_lookup_range() == COSParser.DEFAULT_TRAIL_BYTECOUNT
