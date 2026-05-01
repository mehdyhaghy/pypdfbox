"""Parity-name coverage for ``COSParser``.

Verifies the upstream-named accessors added to mirror
``org.apache.pdfbox.pdfparser.COSParser``. These tests do not exercise
behaviour beyond what the underlying internals already cover — they
exist to guarantee the upstream method names are reachable on the class
and behave as thin pass-throughs.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSDocument,
    COSFloat,
    COSInteger,
    COSName,
    COSObject,
    COSObjectKey,
    COSString,
)
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser import COSParser, PDFParseError


def _parser(data: bytes, document: COSDocument | None = None) -> COSParser:
    return COSParser(RandomAccessReadBuffer(data), document=document)


# ---------- alias existence ----------


@pytest.mark.parametrize(
    "method_name",
    [
        # Typed parse aliases
        "parse_cos_dictionary",
        "parse_cos_array",
        "parse_cos_string",
        "parse_cos_name",
        "parse_cos_number",
        "parse_cos_object_reference",
        # Indirect-object resolution
        "parse_object_dynamically",
        "parse_object_stream",
        # Tokenizer aliases
        "is_eof",
        "peek",
        "unread",
        # /XRef offset accessors
        "get_xref_offset",
        "set_xref_offset",
        # Document accessor
        "get_document",
        # Lenient toggle
        "set_lenient",
        "is_lenient",
        # Xref entry points
        "parse_xref_object_stream",
        "parse_xref_table",
        "parse_xref_stream",
        # Header
        "parse_pdf_header",
        # Brute-force scan helpers
        "bf_search_for_objects",
        "bf_search_for_xref",
        # Initial-parse / trailer-rebuild latches
        "is_initial_parse_done",
        "set_initial_parse_done",
        "is_trailer_was_rebuild",
        # File-length accessors
        "get_file_len",
        "set_file_len",
        # EOF lookup window
        "set_eof_lookup_range",
        "get_eof_lookup_range",
        # Match / search utilities
        "is_string",
        "last_index_of",
    ],
)
def test_alias_method_exists(method_name: str) -> None:
    assert hasattr(COSParser, method_name), (
        f"COSParser is missing upstream alias {method_name!r}"
    )
    assert callable(getattr(COSParser, method_name))


# ---------- typed parse aliases (round-trip) ----------


def test_parse_cos_dictionary_round_trip() -> None:
    p = _parser(b"<< /Type /Catalog /Count 3 /Open true >>")
    d = p.parse_cos_dictionary()
    assert isinstance(d, COSDictionary)
    assert d.get_dictionary_object(COSName.TYPE) is COSName.get_pdf_name("Catalog")
    count = d.get_dictionary_object(COSName.get_pdf_name("Count"))
    assert isinstance(count, COSInteger)
    assert count.value == 3


def test_parse_cos_array_round_trip() -> None:
    p = _parser(b"[ 1 2 3 ]")
    arr = p.parse_cos_array()
    assert isinstance(arr, COSArray)
    assert arr.size() == 3
    assert all(isinstance(arr.get(i), COSInteger) for i in range(3))


def test_parse_cos_string_literal() -> None:
    s = _parser(b"(hi)").parse_cos_string()
    assert isinstance(s, COSString)
    assert s.get_bytes() == b"hi"
    assert not s.is_force_hex_form()


def test_parse_cos_string_hex() -> None:
    s = _parser(b"<48656C6C6F>").parse_cos_string()
    assert isinstance(s, COSString)
    assert s.get_bytes() == b"Hello"
    assert s.is_force_hex_form()


def test_parse_cos_string_rejects_dictionary_marker() -> None:
    with pytest.raises(PDFParseError):
        _parser(b"<<>>").parse_cos_string()


def test_parse_cos_name_round_trip() -> None:
    n = _parser(b"/Catalog").parse_cos_name()
    assert isinstance(n, COSName)
    assert n is COSName.get_pdf_name("Catalog")


def test_parse_cos_number_integer() -> None:
    n = _parser(b"42").parse_cos_number()
    assert isinstance(n, COSInteger)
    assert n.value == 42


def test_parse_cos_number_float_preserves_form() -> None:
    n = _parser(b"1.500").parse_cos_number()
    assert isinstance(n, COSFloat)
    assert n.value == 1.5
    assert n.get_original_form() == "1.500"


def test_parse_cos_object_reference_returns_cos_object() -> None:
    doc = COSDocument()
    ref = _parser(b"7 0 R", document=doc).parse_cos_object_reference()
    assert isinstance(ref, COSObject)
    assert ref.object_number == 7
    assert ref.generation_number == 0
    # Same key should resolve to the same pooled instance.
    assert doc.get_object_from_pool(COSObjectKey(7, 0)) is ref


def test_parse_cos_object_reference_rejects_plain_number() -> None:
    with pytest.raises(PDFParseError):
        _parser(b"42").parse_cos_object_reference()


# ---------- parse_object_dynamically ----------


def test_parse_object_dynamically_unbound_returns_placeholder() -> None:
    p = _parser(b"")
    out = p.parse_object_dynamically(5, 0)
    assert isinstance(out, COSObject)
    assert out.object_number == 5
    assert out.generation_number == 0


def test_parse_object_dynamically_requires_existing_raises_when_missing() -> None:
    doc = COSDocument()
    p = _parser(b"", document=doc)
    with pytest.raises(PDFParseError):
        p.parse_object_dynamically(99, 0, requires_existing_not_compressed=True)


def test_parse_object_dynamically_resolves_pool_loader() -> None:
    doc = COSDocument()
    p = _parser(b"", document=doc)
    placeholder = doc.get_object_from_pool(COSObjectKey(3, 0))
    placeholder.set_object(COSInteger.get(123))
    resolved = p.parse_object_dynamically(3, 0)
    assert isinstance(resolved, COSInteger)
    assert resolved.value == 123


# ---------- xref / header / object-stream coverage ----------
#
# These methods used to be ``NotImplementedError`` placeholders. They
# now have real implementations on COSParser — ``parse_object_stream``
# requires a bound document, the others raise ``PDFParseError`` on
# malformed input. Behavioural tests live alongside in
# ``test_cos_parser_recovery.py`` (xref/object-stream cluster).


def test_parse_object_stream_without_document_raises_parse_error() -> None:
    from pypdfbox.pdfparser import PDFParseError

    p = _parser(b"")
    with pytest.raises(PDFParseError):
        p.parse_object_stream(12)


def test_parse_xref_object_stream_at_invalid_offset_raises() -> None:
    from pypdfbox.pdfparser import PDFParseError

    p = _parser(b"%PDF-1.4\n%%EOF")
    with pytest.raises(PDFParseError):
        p.parse_xref_object_stream(1024)


def test_parse_xref_table_at_invalid_offset_returns_false() -> None:
    p = _parser(b"%PDF-1.4\n%%EOF")
    # No 'xref' keyword at offset 1024 (out of bounds) — must return
    # False rather than crash.
    assert p.parse_xref_table(1024) is False


def test_parse_pdf_header_without_magic_raises() -> None:
    from pypdfbox.pdfparser import PDFParseError

    p = _parser(b"not a PDF")
    with pytest.raises(PDFParseError):
        p.parse_pdf_header()


# ``bf_search_for_objects`` / ``bf_search_for_xref`` were deferred
# placeholders until the recovery cluster — they're now real
# implementations covered by ``test_cos_parser_recovery.py``.


# ---------- /XRef offset accessor round-trip ----------


def test_get_xref_offset_default_is_minus_one() -> None:
    assert _parser(b"").get_xref_offset() == -1


def test_set_xref_offset_round_trip() -> None:
    p = _parser(b"")
    p.set_xref_offset(4096)
    assert p.get_xref_offset() == 4096
    p.set_xref_offset(0)
    assert p.get_xref_offset() == 0


# ---------- get_document ----------


def test_get_document_unbound_returns_none() -> None:
    assert _parser(b"").get_document() is None


def test_get_document_returns_bound_document() -> None:
    doc = COSDocument()
    p = _parser(b"", document=doc)
    assert p.get_document() is doc


# ---------- lenient toggle round-trip ----------


def test_lenient_default_is_true() -> None:
    # Match upstream PDFParser default (already permissive).
    assert _parser(b"").is_lenient() is True


def test_set_lenient_round_trip() -> None:
    p = _parser(b"")
    p.set_lenient(False)
    assert p.is_lenient() is False
    p.set_lenient(True)
    assert p.is_lenient() is True


def test_set_lenient_coerces_truthy_to_bool() -> None:
    p = _parser(b"")
    p.set_lenient(0)  # type: ignore[arg-type]
    assert p.is_lenient() is False
    p.set_lenient(1)  # type: ignore[arg-type]
    assert p.is_lenient() is True


# ---------- tokenizer aliases ----------


def test_is_eof_alias() -> None:
    p = _parser(b"")
    assert p.is_eof() is True


def test_peek_alias_does_not_consume() -> None:
    p = _parser(b"abc")
    assert p.peek() == ord("a")
    assert p.peek() == ord("a")  # still 'a' — peek did not advance


def test_unread_alias_rewinds_one_byte() -> None:
    p = _parser(b"abc")
    first = p.read_byte()
    assert first == ord("a")
    p.unread(first)
    assert p.peek() == ord("a")


# ---------- upstream class constants ----------


def test_sysprop_eof_lookup_range_constant_matches_upstream() -> None:
    # Upstream: COSParser.SYSPROP_EOFLOOKUPRANGE
    assert COSParser.SYSPROP_EOFLOOKUPRANGE == (
        "org.apache.pdfbox.pdfparser.nonSequentialPDFParser.eofLookupRange"
    )


def test_default_trail_bytecount_matches_upstream() -> None:
    # Upstream: COSParser.DEFAULT_TRAIL_BYTECOUNT (private; mirrored
    # public for parity).
    assert COSParser.DEFAULT_TRAIL_BYTECOUNT == 2048


def test_eof_and_obj_marker_constants() -> None:
    # Upstream: COSParser.EOF_MARKER / COSParser.OBJ_MARKER (char[];
    # we mirror as bytes).
    assert COSParser.EOF_MARKER == b"%%EOF"
    assert COSParser.OBJ_MARKER == b"obj"


# ---------- EOF lookup-range accessor ----------


def test_get_eof_lookup_range_default_is_2048() -> None:
    assert _parser(b"").get_eof_lookup_range() == COSParser.DEFAULT_TRAIL_BYTECOUNT


def test_set_eof_lookup_range_round_trip() -> None:
    p = _parser(b"")
    p.set_eof_lookup_range(4096)
    assert p.get_eof_lookup_range() == 4096


def test_set_eof_lookup_range_rejects_values_at_or_below_15() -> None:
    p = _parser(b"")
    p.set_eof_lookup_range(15)  # exactly the upstream rejection boundary
    assert p.get_eof_lookup_range() == COSParser.DEFAULT_TRAIL_BYTECOUNT
    p.set_eof_lookup_range(0)
    assert p.get_eof_lookup_range() == COSParser.DEFAULT_TRAIL_BYTECOUNT
    p.set_eof_lookup_range(-100)
    assert p.get_eof_lookup_range() == COSParser.DEFAULT_TRAIL_BYTECOUNT


def test_set_eof_lookup_range_accepts_16() -> None:
    p = _parser(b"")
    p.set_eof_lookup_range(16)
    assert p.get_eof_lookup_range() == 16


# ---------- file-length accessor ----------


def test_get_file_len_reflects_source_length() -> None:
    data = b"%PDF-1.7\n" + b"x" * 100
    p = _parser(data)
    assert p.get_file_len() == len(data)


def test_set_file_len_round_trip() -> None:
    p = _parser(b"abc")
    p.set_file_len(999)
    assert p.get_file_len() == 999


# ---------- initial-parse-done latch ----------


def test_is_initial_parse_done_default_is_false() -> None:
    assert _parser(b"").is_initial_parse_done() is False


def test_set_initial_parse_done_round_trip() -> None:
    p = _parser(b"")
    p.set_initial_parse_done(True)
    assert p.is_initial_parse_done() is True
    p.set_initial_parse_done(False)
    assert p.is_initial_parse_done() is False


def test_set_lenient_after_initial_parse_done_raises() -> None:
    # Upstream: setLenient throws IllegalArgumentException once
    # initialParseDone is true. We mirror with ValueError (Python's
    # spelling for the same contract).
    p = _parser(b"")
    p.set_initial_parse_done(True)
    with pytest.raises(ValueError):
        p.set_lenient(False)


def test_set_lenient_before_initial_parse_done_still_works() -> None:
    p = _parser(b"")
    p.set_lenient(False)
    assert p.is_lenient() is False


# ---------- trailer-was-rebuild latch ----------


def test_is_trailer_was_rebuild_default_is_false() -> None:
    assert _parser(b"").is_trailer_was_rebuild() is False


# ---------- isString — non-consuming match ----------


def test_is_string_matches_at_current_position() -> None:
    p = _parser(b"%PDF-1.7\n")
    assert p.is_string(b"%PDF-") is True
    # Match is non-consuming.
    assert p.position == 0


def test_is_string_returns_false_on_mismatch() -> None:
    p = _parser(b"%PDF-1.7\n")
    assert p.is_string(b"%FDF-") is False
    assert p.position == 0


def test_is_string_returns_false_at_eof() -> None:
    p = _parser(b"")
    assert p.is_string(b"x") is False


def test_is_string_accepts_str_argument() -> None:
    # Upstream signature is char[]; pypdfbox accepts str for parity
    # ergonomics — must behave identically to the bytes form.
    p = _parser(b"trailer\n")
    assert p.is_string("trailer") is True
    assert p.is_string("xref") is False


def test_is_string_does_not_consume_on_partial_match() -> None:
    # ``%P`` matches the first two bytes but ``D`` mismatches the third;
    # cursor must still be at offset 0.
    p = _parser(b"%PDF-1.7\n")
    assert p.is_string(b"%PX") is False
    assert p.position == 0


# ---------- lastIndexOf — backwards sub-byte search ----------


def test_last_index_of_finds_pattern() -> None:
    buf = b"abcdef-trailer-zzz"
    # end_off is exclusive — pass len(buf) to scan the whole buffer.
    assert _parser(b"").last_index_of(b"trailer", buf, len(buf)) == 7


def test_last_index_of_returns_minus_one_when_absent() -> None:
    buf = b"abcdef-zzz"
    assert _parser(b"").last_index_of(b"trailer", buf, len(buf)) == -1


def test_last_index_of_picks_last_occurrence() -> None:
    buf = b"xrefxref"
    # Two occurrences of "xref"; backwards walk should land on the
    # second (offset 4).
    assert _parser(b"").last_index_of(b"xref", buf, len(buf)) == 4


def test_last_index_of_respects_end_off_exclusive() -> None:
    buf = b"xrefxref"
    # end_off=4 should exclude bytes 4..7 — only the leading xref
    # (offset 0) is reachable.
    assert _parser(b"").last_index_of(b"xref", buf, 4) == 0


def test_last_index_of_empty_pattern_returns_minus_one() -> None:
    # Defensive: upstream's loop would never terminate for an empty
    # pattern; we early-return -1.
    assert _parser(b"").last_index_of(b"", b"abc", 3) == -1


def test_last_index_of_accepts_str_pattern() -> None:
    buf = b"prefix-OBJ-suffix"
    assert _parser(b"").last_index_of("OBJ", buf, len(buf)) == 7
