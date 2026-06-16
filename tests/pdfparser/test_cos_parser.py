from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSArray,
    COSBoolean,
    COSDictionary,
    COSDocument,
    COSFloat,
    COSInteger,
    COSName,
    COSNull,
    COSObject,
    COSObjectKey,
    COSString,
)
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser import COSParser, PDFParseError


def parser(data: bytes, document: COSDocument | None = None) -> COSParser:
    return COSParser(RandomAccessReadBuffer(data), document=document)


# ---------- primitive direct objects ----------


def test_parses_true() -> None:
    assert parser(b"true").parse_direct_object() is COSBoolean.TRUE


def test_parses_false() -> None:
    assert parser(b"false").parse_direct_object() is COSBoolean.FALSE


def test_parses_null() -> None:
    assert parser(b"null").parse_direct_object() is COSNull.NULL


def test_parses_name() -> None:
    obj = parser(b"/Type").parse_direct_object()
    assert obj is COSName.get_pdf_name("Type")


def test_parses_literal_string() -> None:
    obj = parser(b"(hello)").parse_direct_object()
    assert isinstance(obj, COSString)
    assert obj.get_bytes() == b"hello"
    assert not obj.is_force_hex_form()


def test_parses_hex_string_marks_force_hex_form() -> None:
    obj = parser(b"<48656C6C6F>").parse_direct_object()
    assert isinstance(obj, COSString)
    assert obj.get_bytes() == b"Hello"
    assert obj.is_force_hex_form()


def test_parses_integer() -> None:
    obj = parser(b"42").parse_direct_object()
    assert isinstance(obj, COSInteger)
    assert obj.value == 42


def test_parses_negative_integer() -> None:
    obj = parser(b"-7").parse_direct_object()
    assert isinstance(obj, COSInteger)
    assert obj.value == -7


def test_parses_float_preserves_original_form() -> None:
    obj = parser(b"1.500").parse_direct_object()
    assert isinstance(obj, COSFloat)
    assert obj.value == 1.5
    assert obj.get_original_form() == "1.500"


def test_parses_leading_decimal_float() -> None:
    obj = parser(b".5").parse_direct_object()
    assert isinstance(obj, COSFloat)
    assert obj.value == 0.5


# ---------- arrays ----------


def test_empty_array() -> None:
    obj = parser(b"[]").parse_direct_object()
    assert isinstance(obj, COSArray)
    assert obj.size() == 0


def test_array_of_mixed_primitives() -> None:
    obj = parser(b"[ 1 2.5 (hi) /Foo true null ]").parse_direct_object()
    assert isinstance(obj, COSArray)
    items = obj.to_list()
    assert items[0] == COSInteger(1)
    assert isinstance(items[1], COSFloat)
    assert items[1].value == 2.5
    assert isinstance(items[2], COSString)
    assert items[3] is COSName.get_pdf_name("Foo")
    assert items[4] is COSBoolean.TRUE
    assert items[5] is COSNull.NULL


def test_nested_arrays() -> None:
    obj = parser(b"[[1 2] [3 4]]").parse_direct_object()
    assert isinstance(obj, COSArray)
    assert obj.size() == 2
    inner_a = obj.get(0)
    inner_b = obj.get(1)
    assert isinstance(inner_a, COSArray) and inner_a.size() == 2
    assert isinstance(inner_b, COSArray) and inner_b.size() == 2


def test_unterminated_array_raises() -> None:
    with pytest.raises(PDFParseError):
        parser(b"[1 2").parse_direct_object()


# ---------- dictionaries ----------


def test_empty_dictionary() -> None:
    obj = parser(b"<<>>").parse_direct_object()
    assert isinstance(obj, COSDictionary)
    assert obj.size() == 0


def test_simple_dictionary() -> None:
    obj = parser(b"<< /Type /Page /Length 42 >>").parse_direct_object()
    assert isinstance(obj, COSDictionary)
    assert obj.get_name("Type") == "Page"
    assert obj.get_int("Length") == 42


def test_dictionary_with_nested_array_and_dict() -> None:
    obj = parser(b"<< /Kids [/A /B] /Resources << /Font /Helv >> >>").parse_direct_object()
    assert isinstance(obj, COSDictionary)
    kids = obj.get_dictionary_object("Kids")
    assert isinstance(kids, COSArray)
    assert kids.size() == 2
    res = obj.get_dictionary_object("Resources")
    assert isinstance(res, COSDictionary)
    assert res.get_name("Font") == "Helv"


def test_dictionary_value_position_must_be_name() -> None:
    with pytest.raises(PDFParseError):
        parser(b"<< 7 8 >>").parse_direct_object()


def test_unterminated_dictionary_raises() -> None:
    with pytest.raises(PDFParseError):
        parser(b"<< /A 1 ").parse_direct_object()


# ---------- indirect references ----------


def test_indirect_reference_outside_document_returns_unbound_cosobject() -> None:
    obj = parser(b"7 0 R").parse_direct_object()
    assert isinstance(obj, COSObject)
    assert obj.object_number == 7
    assert obj.generation_number == 0
    assert obj.get_object() is None


def test_indirect_reference_inside_document_uses_pool() -> None:
    doc = COSDocument()
    obj1 = parser(b"7 0 R", document=doc).parse_direct_object()
    obj2 = parser(b"7 0 R", document=doc).parse_direct_object()
    assert obj1 is obj2  # same pool entry
    assert doc.has_object(COSObjectKey(7, 0))


def test_wave330_indirect_reference_requires_r_token_boundary() -> None:
    obj = parser(b"7 0 R2").parse_direct_object()
    assert isinstance(obj, COSInteger)
    assert obj.value == 7


def test_lone_integer_does_not_become_indirect_ref() -> None:
    obj = parser(b"42 ").parse_direct_object()
    assert isinstance(obj, COSInteger)


def test_two_integers_without_R_are_two_objects() -> None:
    p = parser(b"42 99 ")
    a = p.parse_direct_object()
    b = p.parse_direct_object()
    assert isinstance(a, COSInteger) and a.value == 42
    assert isinstance(b, COSInteger) and b.value == 99


def test_indirect_ref_in_array() -> None:
    obj = parser(b"[ 1 0 R 5 ]").parse_direct_object()
    assert isinstance(obj, COSArray)
    assert obj.size() == 2
    assert isinstance(obj.get(0), COSObject)
    assert isinstance(obj.get(1), COSInteger)


def test_indirect_ref_in_dictionary() -> None:
    obj = parser(b"<< /Pages 3 0 R /Count 5 >>").parse_direct_object()
    assert isinstance(obj, COSDictionary)
    pages = obj.get_item("Pages")
    assert isinstance(pages, COSObject)
    assert pages.object_number == 3
    assert obj.get_int("Count") == 5


def test_negative_first_int_is_not_indirect_ref() -> None:
    p = parser(b"-1 0 R")
    obj = p.parse_direct_object()
    assert isinstance(obj, COSInteger)
    assert obj.value == -1


def test_first_float_is_not_indirect_ref() -> None:
    p = parser(b"1.5 0 R")
    obj = p.parse_direct_object()
    assert isinstance(obj, COSFloat)


# ---------- indirect object definitions ----------


def test_parse_indirect_object_definition_basic() -> None:
    p = parser(b"7 0 obj << /Type /Page >> endobj")
    obj = p.parse_indirect_object_definition()
    assert isinstance(obj, COSObject)
    assert obj.object_number == 7
    body = obj.get_object()
    assert isinstance(body, COSDictionary)
    assert body.get_name("Type") == "Page"


def test_parse_indirect_object_registers_in_document_pool() -> None:
    doc = COSDocument()
    p = parser(b"3 0 obj 42 endobj", document=doc)
    obj = p.parse_indirect_object_definition()
    pooled = doc.get_object_from_pool(COSObjectKey(3, 0))
    assert pooled is obj
    assert pooled.is_object_loaded()
    body = pooled.get_object()
    assert isinstance(body, COSInteger) and body.value == 42


def test_parse_indirect_object_with_direct_length_stream_returns_stream() -> None:
    # Direct-/Length stream bodies are handled inline by COSParser; only
    # indirect-/Length resolution still defers to PDFParser.
    from pypdfbox.cos import COSStream

    p = parser(b"4 0 obj << /Length 5 >> stream\nABCDE\nendstream endobj")
    obj = p.parse_indirect_object_definition()
    assert isinstance(obj, COSObject)
    body = obj.get_object()
    assert isinstance(body, COSStream)
    assert body.get_raw_data() == b"ABCDE"


def test_parse_indirect_object_with_indirect_length_raises_not_implemented() -> None:
    # Indirect-/Length stream bodies still belong to PDFParser cluster #3.
    p = parser(b"4 0 obj << /Length 99 0 R >> stream\nABCDE\nendstream endobj")
    with pytest.raises(NotImplementedError):
        p.parse_indirect_object_definition()


def test_parse_indirect_object_missing_obj_keyword_raises() -> None:
    with pytest.raises(PDFParseError):
        parser(b"7 0 nope 5 endobj").parse_indirect_object_definition()


def test_parse_indirect_object_missing_endobj_raises() -> None:
    with pytest.raises(PDFParseError):
        parser(b"7 0 obj 5 nope").parse_indirect_object_definition()


# ---------- whitespace / comments ----------


def test_whitespace_and_comments_around_object() -> None:
    obj = parser(b"  % a comment\n  /Foo").parse_direct_object()
    assert obj is COSName.get_pdf_name("Foo")


def test_eof_at_object_start_raises() -> None:
    with pytest.raises(PDFParseError):
        parser(b"   ").parse_direct_object()


def test_unknown_starting_byte_raises() -> None:
    with pytest.raises(PDFParseError):
        parser(b"@").parse_direct_object()


def test_unknown_keyword_raises() -> None:
    with pytest.raises(PDFParseError):
        parser(b"truthy").parse_direct_object()


def test_wave330_boolean_keyword_requires_token_boundary() -> None:
    with pytest.raises(PDFParseError, match="unexpected keyword"):
        parser(b"true1").parse_direct_object()


# ---------- realistic compound input ----------


def test_realistic_page_dictionary() -> None:
    src = (
        b"<< /Type /Page /Parent 1 0 R /Resources << /Font << /F1 7 0 R >> >> "
        b"/MediaBox [0 0 612 792] /Contents 9 0 R >>"
    )
    obj = parser(src).parse_direct_object()
    assert isinstance(obj, COSDictionary)
    assert obj.get_name("Type") == "Page"
    parent = obj.get_item("Parent")
    assert isinstance(parent, COSObject)
    res = obj.get_dictionary_object("Resources")
    assert isinstance(res, COSDictionary)
    fonts = res.get_dictionary_object("Font")
    assert isinstance(fonts, COSDictionary)
    f1 = fonts.get_item("F1")
    assert isinstance(f1, COSObject) and f1.object_number == 7
    media = obj.get_dictionary_object("MediaBox")
    assert isinstance(media, COSArray)
    assert media.size() == 4
    assert media.to_float_array() == [0.0, 0.0, 612.0, 792.0]
    contents = obj.get_item("Contents")
    assert isinstance(contents, COSObject) and contents.object_number == 9


# ---------- direct-/Length stream bodies ----------


def test_stream_body_with_direct_length_round_trips() -> None:
    from pypdfbox.cos import COSStream

    p = parser(b"5 0 obj << /Length 11 >> stream\nhello world\nendstream endobj")
    obj = p.parse_indirect_object_definition()
    body = obj.get_object()
    assert isinstance(body, COSStream)
    assert body.get_raw_data() == b"hello world"


def test_stream_body_crlf_eol_after_stream_keyword() -> None:
    from pypdfbox.cos import COSStream

    pdf = b"5 0 obj << /Length 5 >> stream\r\nABCDE\nendstream endobj"
    body = parser(pdf).parse_indirect_object_definition().get_object()
    assert isinstance(body, COSStream)
    assert body.get_raw_data() == b"ABCDE"


def test_stream_body_truncated_raises() -> None:
    p = parser(b"5 0 obj << /Length 99 >> stream\nshort\nendstream endobj")
    with pytest.raises(PDFParseError):
        p.parse_indirect_object_definition()


def test_stream_body_negative_length_raises() -> None:
    p = parser(b"5 0 obj << /Length -1 >> stream\nABCDE\nendstream endobj")
    with pytest.raises(PDFParseError):
        p.parse_indirect_object_definition()


# ---------- parse_pdf_header ----------


def test_parse_pdf_header_basic() -> None:
    p = parser(b"%PDF-1.7\nbody...")
    assert p.parse_pdf_header() == 1.7


def test_parse_pdf_header_tolerates_leading_garbage() -> None:
    p = parser(b"junk garbage\nMore garbage\n%PDF-1.4\n")
    assert p.parse_pdf_header() == 1.4


def test_parse_pdf_header_missing_magic_raises() -> None:
    with pytest.raises(PDFParseError):
        parser(b"this is not a PDF").parse_pdf_header()


def test_parse_pdf_header_malformed_version_raises() -> None:
    with pytest.raises(PDFParseError):
        parser(b"%PDF-bad\n").parse_pdf_header()


# ---------- parse_xref_table ----------


def test_parse_xref_table_traditional_section() -> None:
    pdf = (
        b"xref\n0 3\n"
        b"0000000000 65535 f \n"
        b"0000000017 00000 n \n"
        b"0000000089 00000 n \n"
        b"trailer << /Size 3 >>\n"
    )
    table: dict[COSObjectKey, int] = {}
    assert parser(pdf).parse_xref_table(0, table) is True
    assert table[COSObjectKey(0, 65535)] == -1  # free entry
    assert table[COSObjectKey(1, 0)] == 17
    assert table[COSObjectKey(2, 0)] == 89


def test_parse_xref_table_returns_false_when_keyword_missing() -> None:
    p = parser(b"not an xref")
    assert p.parse_xref_table(0) is False


def test_parse_xref_table_first_write_wins_for_duplicate_keys() -> None:
    # Two adjacent subsections with overlapping ranges — first wins.
    pdf = (
        b"xref\n0 1\n0000000000 65535 f \n"
        b"0 1\n0000000999 00000 n \n"
        b"trailer << /Size 1 >>\n"
    )
    table: dict[COSObjectKey, int] = {}
    parser(pdf).parse_xref_table(0, table)
    # First write wins — the "f" entry at offset 0.
    assert table[COSObjectKey(0, 65535)] == -1


# ---------- parse_xref_object_stream ----------


def test_parse_xref_object_stream_returns_stream_with_dict() -> None:
    from pypdfbox.cos import COSStream

    body = b"\x00\x00\x00\x00"  # 4-byte body, content irrelevant for shape test
    pdf = (
        b"5 0 obj\n"
        b"<< /Type /XRef /Length 4 /W [1 2 1] /Size 1 >>\n"
        b"stream\n" + body + b"\nendstream\nendobj\n"
    )
    p = parser(pdf)
    s = p.parse_xref_object_stream(0)
    assert isinstance(s, COSStream)
    assert s.get_name("Type") == "XRef"
    assert s.is_skip_encryption()
    assert s.get_raw_data() == body


def test_parse_xref_object_stream_rejects_non_xref_when_standalone() -> None:
    pdf = (
        b"5 0 obj\n"
        b"<< /Type /Other /Length 4 >>\n"
        b"stream\nDATA\nendstream\nendobj\n"
    )
    with pytest.raises(PDFParseError):
        parser(pdf).parse_xref_object_stream(0)


def test_parse_xref_object_stream_tolerates_non_xref_when_not_standalone() -> None:
    pdf = (
        b"5 0 obj\n"
        b"<< /Type /Other /Length 4 >>\n"
        b"stream\nDATA\nendstream\nendobj\n"
    )
    s = parser(pdf).parse_xref_object_stream(0, is_standalone=False)
    assert s.get_name("Type") == "Other"


# ---------- parse_object_stream ----------


def test_parse_object_stream_decodes_packed_objects() -> None:
    # ObjStm with N=2, First=8, two integers stored at offsets 0 and 3.
    # Header: "10 0 11 3" (no filter applied for simplicity).
    body = b"10 0 11 3\n42  99"  # 16 bytes
    # Now stand up a document containing that ObjStm at obj 5.
    doc = COSDocument()
    pdf = (
        b"5 0 obj\n"
        b"<< /Type /ObjStm /N 2 /First 10 /Length 16 >>\n"
        b"stream\n" + body + b"\nendstream\nendobj\n"
    )
    p = parser(pdf, document=doc)
    # Parse the ObjStm object so the pool entry is populated.
    p.parse_indirect_object_definition()
    # Now decode it.
    p2 = parser(b"", document=doc)
    items = p2.parse_object_stream(5)
    assert len(items) == 2
    assert items[0] == COSInteger(42)
    assert items[1] == COSInteger(99)
    # Pool should have entries for obj 10 and obj 11 (gen 0 by spec).
    assert doc.has_object(COSObjectKey(10, 0))
    assert doc.has_object(COSObjectKey(11, 0))
    assert doc.get_object_from_pool(COSObjectKey(10, 0)).get_object() == COSInteger(42)


def test_parse_object_stream_without_document_raises() -> None:
    p = parser(b"")
    with pytest.raises(PDFParseError):
        p.parse_object_stream(5)


def test_parse_object_stream_missing_n_or_first_raises() -> None:
    # ObjStm dict lacks /N — must raise.
    body = b""
    doc = COSDocument()
    pdf = (
        b"5 0 obj\n"
        b"<< /Type /ObjStm /Length 0 >>\n"
        b"stream\n" + body + b"\nendstream\nendobj\n"
    )
    p = parser(pdf, document=doc)
    p.parse_indirect_object_definition()
    p2 = parser(b"", document=doc)
    with pytest.raises(PDFParseError):
        p2.parse_object_stream(5)


# ---------- reset_trailer_resolver / retrieve_trailer ----------


def test_reset_trailer_resolver_default_true() -> None:
    assert parser(b"").reset_trailer_resolver() is True


def test_retrieve_trailer_returns_existing_document_trailer() -> None:
    doc = COSDocument()
    expected = COSDictionary()
    expected.set_item(COSName.get_pdf_name("Root"), COSObject(1, 0))
    doc.set_trailer(expected)
    assert parser(b"", document=doc).retrieve_trailer() is expected


def test_retrieve_trailer_strict_without_document_raises() -> None:
    p = parser(b"")
    p.set_lenient(False)
    with pytest.raises(PDFParseError):
        p.retrieve_trailer()


def test_retrieve_trailer_lenient_falls_through_to_rebuild() -> None:
    # Brute-force rebuild on a tiny empty source produces an empty
    # trailer, but the latch should flip.
    p = parser(b"")
    assert p.is_lenient() is True
    trailer = p.retrieve_trailer()
    assert isinstance(trailer, COSDictionary)
    assert p.is_trailer_was_rebuild() is True


# ---------- dereference_cos_object ----------


def test_dereference_cos_object_resolves_via_pool() -> None:
    doc = COSDocument()
    pdf = b"5 0 obj\n42\nendobj\n"
    p = parser(pdf, document=doc)
    p.parse_indirect_object_definition()
    obj = COSObject(5, 0)
    # Position parser somewhere — dereference should preserve cursor.
    p.seek(3)
    pre = p.position
    resolved = p.dereference_cos_object(obj)
    assert isinstance(resolved, COSInteger)
    assert resolved.value == 42
    assert p.position == pre


# ---------- create_random_access_read_view ----------


def test_create_random_access_read_view_returns_sliced_view() -> None:
    p = parser(b"abcdef")
    view = p.create_random_access_read_view(2, 3)
    try:
        buf = bytearray(3)
        n = view.read_into(buf)
        assert n == 3
        assert bytes(buf) == b"cde"
    finally:
        view.close()


# ---------- parse_object_stream_object ----------


def test_parse_object_stream_object_returns_specific_entry() -> None:
    body = b"10 0 11 3\n42  99"
    doc = COSDocument()
    pdf = (
        b"5 0 obj\n"
        b"<< /Type /ObjStm /N 2 /First 10 /Length 16 >>\n"
        b"stream\n" + body + b"\nendstream\nendobj\n"
    )
    p = parser(pdf, document=doc)
    p.parse_indirect_object_definition()
    p2 = parser(b"", document=doc)
    obj = p2.parse_object_stream_object(5, COSObjectKey(11, 0))
    assert isinstance(obj, COSInteger)
    assert obj.value == 99


def test_parse_object_stream_object_missing_key_returns_none() -> None:
    body = b"10 0\n42"
    doc = COSDocument()
    pdf = (
        b"5 0 obj\n"
        b"<< /Type /ObjStm /N 1 /First 5 /Length 7 >>\n"
        b"stream\n" + body + b"\nendstream\nendobj\n"
    )
    p = parser(pdf, document=doc)
    p.parse_indirect_object_definition()
    p2 = parser(b"", document=doc)
    assert p2.parse_object_stream_object(5, COSObjectKey(99, 0)) is None


def test_parse_object_stream_object_without_document_raises() -> None:
    with pytest.raises(PDFParseError):
        parser(b"").parse_object_stream_object(5, COSObjectKey(1, 0))


# ---------- parse_cos_stream ----------


def test_parse_cos_stream_reads_body_with_direct_length() -> None:
    body_bytes = b"DATA"
    pdf = b"stream\n" + body_bytes + b"\nendstream\n"
    doc = COSDocument()
    p = parser(pdf, document=doc)
    dic = COSDictionary()
    dic.set_item(COSName.LENGTH, COSInteger.get(len(body_bytes)))
    stream = p.parse_cos_stream(dic)
    with stream.create_input_stream() as src:
        assert src.read() == body_bytes


def test_parse_cos_stream_requires_stream_keyword() -> None:
    p = parser(b"endobj")
    dic = COSDictionary()
    dic.set_item(COSName.LENGTH, COSInteger.get(0))
    with pytest.raises(PDFParseError):
        p.parse_cos_stream(dic)


# ---------- check_pages ----------


def test_check_pages_rejects_non_dictionary_pages() -> None:
    root = COSDictionary()
    # No /Pages at all.
    p = parser(b"")
    with pytest.raises(PDFParseError):
        p.check_pages(root)


def test_check_pages_accepts_dictionary_pages() -> None:
    pages = COSDictionary()
    pages.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("Pages"))
    pages.set_item(COSName.get_pdf_name("Count"), COSInteger.get(0))
    pages.set_item(COSName.get_pdf_name("Kids"), COSArray())
    root = COSDictionary()
    root.set_item(COSName.get_pdf_name("Pages"), pages)
    parser(b"").check_pages(root)  # no raise


# ---------- get_encryption / get_access_permission / prepare_decryption ----------


def test_get_encryption_without_document_raises() -> None:
    with pytest.raises(PDFParseError):
        parser(b"").get_encryption()


def test_get_encryption_returns_none_when_unencrypted() -> None:
    doc = COSDocument()
    assert parser(b"", document=doc).get_encryption() is None


def test_get_access_permission_without_document_raises() -> None:
    with pytest.raises(PDFParseError):
        parser(b"").get_access_permission()


def test_get_access_permission_returns_none_when_no_handler() -> None:
    doc = COSDocument()
    assert parser(b"", document=doc).get_access_permission() is None


def test_prepare_decryption_no_document_is_noop() -> None:
    parser(b"").prepare_decryption()  # no raise


def test_prepare_decryption_unencrypted_document_is_noop() -> None:
    doc = COSDocument()
    parser(b"", document=doc).prepare_decryption()  # no raise


# ---------- wave 1243: 1:1 parity surface for COSParser ----------


def test_init_without_env_override_is_noop() -> None:
    # init() consults SYSPROP_EOFLOOKUPRANGE; with no override it should
    # leave the lookup range at its DEFAULT value.
    p = parser(b"")
    p.init()
    assert p.get_eof_lookup_range() == COSParser.DEFAULT_TRAIL_BYTECOUNT


def test_init_applies_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(COSParser.SYSPROP_EOFLOOKUPRANGE, "4096")
    p = parser(b"")
    p.init()
    assert p.get_eof_lookup_range() == 4096


def test_init_ignores_non_integer_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(COSParser.SYSPROP_EOFLOOKUPRANGE, "not-a-number")
    p = parser(b"")
    p.init()
    assert p.get_eof_lookup_range() == COSParser.DEFAULT_TRAIL_BYTECOUNT


def test_get_startxref_offset_basic() -> None:
    pdf = b"%PDF-1.4\n... body ...\nstartxref\n123\n%%EOF\n"
    p = parser(pdf)
    off = p.get_startxref_offset()
    # The marker should land on the literal 'startxref' bytes.
    assert pdf[off:off + 9] == b"startxref"


def test_get_startxref_offset_missing_eof_strict_raises() -> None:
    p = parser(b"... body without EOF marker ...startxref\n55\n")
    p.set_lenient(False)
    # In strict mode the missing %%EOF triggers an error.
    with pytest.raises(PDFParseError):
        p.get_startxref_offset()


def test_get_startxref_offset_missing_startxref_raises() -> None:
    p = parser(b"%PDF-1.4\nbody\n%%EOF\n")
    with pytest.raises(PDFParseError):
        p.get_startxref_offset()


def test_parse_start_xref_reads_offset() -> None:
    p = parser(b"startxref\n12345\n")
    assert p.parse_start_xref() == 12345


def test_parse_start_xref_returns_negative_when_keyword_missing() -> None:
    p = parser(b"trailer\n<< >>\n")
    assert p.parse_start_xref() == -1


def test_parse_trailer_basic() -> None:
    p = parser(b"trailer\n<< /Size 5 /Root 1 0 R >>\n")
    assert p.parse_trailer() is True
    last = p._last_parsed_trailer  # noqa: SLF001 — surface latched by parse
    assert last.get_dictionary_object(COSName.get_pdf_name("Size")).int_value() == 5


def test_parse_trailer_returns_false_when_keyword_missing() -> None:
    p = parser(b"<< /Size 5 >>\n")
    assert p.parse_trailer() is False


def test_get_length_direct_integer_returns_input() -> None:
    p = parser(b"")
    n = COSInteger.get(42)
    assert p.get_length(n) is n


def test_get_length_none_returns_none() -> None:
    p = parser(b"")
    assert p.get_length(None) is None


def test_get_length_indirect_reference_resolved() -> None:
    p = parser(b"")
    obj = COSObject(7, 0, resolved=COSInteger.get(99))
    out = p.get_length(obj)
    assert isinstance(out, COSInteger)
    assert out.int_value() == 99


def test_get_length_indirect_reference_to_null_returns_none() -> None:
    p = parser(b"")
    obj = COSObject(7, 0, resolved=COSNull.NULL)
    assert p.get_length(obj) is None


def test_get_length_wrong_type_raises() -> None:
    p = parser(b"")
    bad = COSDictionary()  # not a number
    with pytest.raises(PDFParseError):
        p.get_length(bad)


def test_validate_stream_length_returns_false_for_zero() -> None:
    p = parser(b"some body bytes\nendstream\n")
    assert p.validate_stream_length(0) is False


def test_validate_stream_length_returns_false_for_negative() -> None:
    p = parser(b"some body bytes\nendstream\n")
    assert p.validate_stream_length(-1) is False


def test_validate_stream_length_returns_true_when_endstream_aligns() -> None:
    body = b"hello world"
    pdf = body + b"\nendstream\n"
    p = parser(pdf)
    assert p.validate_stream_length(len(body)) is True


def test_validate_stream_length_returns_false_when_endstream_missing() -> None:
    body = b"hello world"
    pdf = body + b"\nNOTendstream\n"
    p = parser(pdf)
    assert p.validate_stream_length(len(body)) is False


def test_check_x_ref_offset_strict_returns_input() -> None:
    p = parser(b"xref\n0 1\n")
    p.set_lenient(False)
    assert p.check_x_ref_offset(0) == 0


def test_check_x_ref_offset_lenient_locates_xref_keyword() -> None:
    p = parser(b"xref\n0 1\n0000000000 65535 f \n")
    assert p.check_x_ref_offset(0) == 0


def test_check_x_ref_offset_lenient_minus_one_when_no_table() -> None:
    p = parser(b"")
    assert p.check_x_ref_offset(0) == -1


def test_check_x_ref_stream_offset_strict_returns_true() -> None:
    p = parser(b"")
    p.set_lenient(False)
    assert p.check_x_ref_stream_offset(0) is True


def test_check_x_ref_stream_offset_zero_offset_returns_true() -> None:
    p = parser(b"")
    assert p.check_x_ref_stream_offset(0) is True


def test_calculate_x_ref_fixed_offset_negative_returns_zero() -> None:
    p = parser(b"")
    assert p.calculate_x_ref_fixed_offset(-1) == 0


def test_calculate_x_ref_fixed_offset_returns_recovered_offset() -> None:
    # The ``xref`` keyword must sit past MINIMUM_SEARCH_OFFSET (= 6) —
    # upstream ``bfSearchForXRefTables`` seeks to that offset before scanning,
    # so an ``xref`` buried inside the first six bytes is never recovered.
    pdf = b"\n\n\n\n\n\n\nxref\n0 1\n0000000000 65535 f \n"
    p = parser(pdf)
    fixed = p.calculate_x_ref_fixed_offset(2)
    # Should recover the 'xref' keyword offset.
    assert fixed == pdf.find(b"xref")


def test_validate_xref_offsets_none_returns_true() -> None:
    p = parser(b"")
    assert p.validate_xref_offsets(None) is True


def test_validate_xref_offsets_empty_dict_returns_true() -> None:
    p = parser(b"")
    assert p.validate_xref_offsets({}) is True


def test_check_xref_offsets_without_document_is_noop() -> None:
    parser(b"").check_xref_offsets()  # no raise


def test_get_brute_force_parser_returns_self() -> None:
    p = parser(b"")
    assert p.get_brute_force_parser() is p


def test_check_pages_dictionary_counts_kids() -> None:
    # Build a /Pages dictionary with two /Page kids and one nested
    # /Pages with one kid — total 3 pages.
    p = parser(b"")
    type_name = COSName.get_pdf_name("Type")
    page_name = COSName.get_pdf_name("Page")
    pages_name = COSName.get_pdf_name("Pages")
    kids_name = COSName.get_pdf_name("Kids")
    count_name = COSName.get_pdf_name("Count")

    leaf1 = COSDictionary()
    leaf1.set_item(type_name, page_name)
    leaf2 = COSDictionary()
    leaf2.set_item(type_name, page_name)
    leaf3 = COSDictionary()
    leaf3.set_item(type_name, page_name)
    inner = COSDictionary()
    inner.set_item(type_name, pages_name)
    inner_kids = COSArray([COSObject(3, 0, resolved=leaf3)])
    inner.set_item(kids_name, inner_kids)

    root = COSDictionary()
    root.set_item(type_name, pages_name)
    root.set_item(
        kids_name,
        COSArray(
            [
                COSObject(1, 0, resolved=leaf1),
                COSObject(2, 0, resolved=leaf2),
                COSObject(4, 0, resolved=inner),
            ]
        ),
    )
    total = p.check_pages_dictionary(root, set())
    assert total == 3
    assert root.get_dictionary_object(count_name).int_value() == 3


def test_parse_header_via_public_alias() -> None:
    # parse_header is the renamed shared marker scanner; both
    # parse_pdf_header and parse_fdf_header route through it.
    p = parser(b"%PDF-2.0\n")
    assert p.parse_header(b"%PDF-", "1.4") == 2.0


def test_parse_header_falls_back_to_default_when_no_digits() -> None:
    p = parser(b"%PDF-\n")  # no version digits
    assert p.parse_header(b"%PDF-", "1.4") == 1.4


def test_get_object_offset_without_document_raises_in_strict() -> None:
    p = parser(b"")
    with pytest.raises(PDFParseError):
        p.get_object_offset(COSObjectKey(1, 0), True)


def test_get_object_offset_unknown_returns_none() -> None:
    doc = COSDocument()
    p = parser(b"", document=doc)
    assert p.get_object_offset(COSObjectKey(99, 0), False) is None


def test_parse_file_object_validates_object_key_mismatch() -> None:
    pdf = b"3 0 obj\n42\nendobj\n"
    p = parser(pdf, document=COSDocument())
    with pytest.raises(PDFParseError):
        # claim object 5 lives at offset 0 — header says 3 — must reject.
        p.parse_file_object(0, COSObjectKey(5, 0))


def test_parse_file_object_returns_direct_object() -> None:
    pdf = b"3 0 obj\n42\nendobj\n"
    p = parser(pdf, document=COSDocument())
    out = p.parse_file_object(0, COSObjectKey(3, 0))
    assert isinstance(out, COSInteger)
    assert out.int_value() == 42
