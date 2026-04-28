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
        # Header
        "parse_pdf_header",
        # Brute-force scan helpers
        "bf_search_for_objects",
        "bf_search_for_xref",
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
