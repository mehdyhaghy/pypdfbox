from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary, COSDocument
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser import PDFParseError, PDFParser
from pypdfbox.pdfparser.pdf_parser import SYSPROP_EOFLOOKUPRANGE
from pypdfbox.pdfparser.xref_trailer_resolver import XrefTrailerResolver
from pypdfbox.pdmodel.pd_document import PDDocument

# ---------- helpers ----------


def _build_pdf(objects: list[bytes], trailer: bytes, version: bytes = b"1.4") -> bytes:
    """Assemble a tiny but spec-compliant PDF (mirrors the helper in
    ``test_pdf_parser.py``)."""
    out = bytearray()
    out += b"%PDF-" + version + b"\n"
    offsets: list[int] = [0]
    for body in objects:
        offsets.append(len(out))
        out += body
        if not body.endswith(b"\n"):
            out += b"\n"
    xref_offset = len(out)
    out += b"xref\n"
    out += f"0 {len(offsets)}\n".encode("ascii")
    out += b"0000000000 65535 f \n"
    for off in offsets[1:]:
        out += f"{off:010d} 00000 n \n".encode("ascii")
    out += b"trailer\n"
    out += trailer + b"\n"
    out += b"startxref\n"
    out += f"{xref_offset}\n".encode("ascii")
    out += b"%%EOF"
    return bytes(out)


def _parser(pdf_bytes: bytes) -> PDFParser:
    return PDFParser(RandomAccessReadBuffer(pdf_bytes))


def _minimal_pdf_bytes() -> bytes:
    return _build_pdf(
        [
            b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj",
            b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj",
            b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\nendobj",
        ],
        b"<< /Size 4 /Root 1 0 R >>",
    )


# ---------- get_document ----------


def test_get_document_returns_none_before_parse() -> None:
    p = _parser(_minimal_pdf_bytes())
    assert p.get_document() is None


def test_get_document_returns_cos_document_after_parse() -> None:
    p = _parser(_minimal_pdf_bytes())
    p.parse()
    doc = p.get_document()
    assert doc is not None
    assert isinstance(doc, COSDocument)


def test_get_document_returns_same_instance_returned_by_parse() -> None:
    p = _parser(_minimal_pdf_bytes())
    parsed = p.parse()
    assert p.get_document() is parsed


# ---------- get_xref_offset ----------


def test_get_xref_offset_default_is_minus_one() -> None:
    p = _parser(_minimal_pdf_bytes())
    assert p.get_xref_offset() == -1


def test_get_xref_offset_records_startxref_after_parse() -> None:
    pdf = _minimal_pdf_bytes()
    expected = pdf.find(b"xref\n")
    assert expected >= 0

    p = _parser(pdf)
    doc = p.parse()
    try:
        assert p.get_xref_offset() == expected
        assert p.get_document() is doc
        assert doc.get_start_xref() == expected
    finally:
        doc.close()


# ---------- set_lenient / is_lenient ----------


def test_is_lenient_default_true() -> None:
    # The pypdfbox parser is permissive by default.
    p = _parser(_minimal_pdf_bytes())
    assert p.is_lenient() is True


def test_set_lenient_round_trip() -> None:
    p = _parser(_minimal_pdf_bytes())
    p.set_lenient(False)
    assert p.is_lenient() is False
    p.set_lenient(True)
    assert p.is_lenient() is True


def test_set_lenient_coerces_truthy_values() -> None:
    p = _parser(_minimal_pdf_bytes())
    p.set_lenient(0)  # type: ignore[arg-type]
    assert p.is_lenient() is False
    p.set_lenient(1)  # type: ignore[arg-type]
    assert p.is_lenient() is True


# ---------- get_password / set_password ----------


def test_get_password_default_is_none() -> None:
    p = _parser(_minimal_pdf_bytes())
    assert p.get_password() is None


def test_set_password_round_trip_str() -> None:
    p = _parser(_minimal_pdf_bytes())
    p.set_password("hunter2")
    assert p.get_password() == "hunter2"


def test_set_password_round_trip_bytes() -> None:
    p = _parser(_minimal_pdf_bytes())
    p.set_password(b"\x00\x01secret")
    assert p.get_password() == b"\x00\x01secret"


def test_set_password_can_clear_to_none() -> None:
    p = _parser(_minimal_pdf_bytes())
    p.set_password("first")
    p.set_password(None)
    assert p.get_password() is None


# ---------- get_pd_document ----------


def test_get_pd_document_returns_pd_document_after_parse() -> None:
    p = _parser(_minimal_pdf_bytes())
    p.parse()
    pd = p.get_pd_document()
    assert isinstance(pd, PDDocument)


def test_get_pd_document_is_cached() -> None:
    p = _parser(_minimal_pdf_bytes())
    p.parse()
    first = p.get_pd_document()
    second = p.get_pd_document()
    assert first is second


def test_get_pd_document_wraps_parsed_cos_document() -> None:
    p = _parser(_minimal_pdf_bytes())
    p.parse()
    pd = p.get_pd_document()
    # The wrapper must expose the same COSDocument returned by get_document().
    assert pd.get_document() is p.get_document()


def test_get_pd_document_before_parse_raises() -> None:
    p = _parser(_minimal_pdf_bytes())
    with pytest.raises(PDFParseError):
        p.get_pd_document()


# ---------- get_trailer / get_root / get_xref_trailer_resolver ----------


def test_get_trailer_returns_none_before_parse() -> None:
    p = _parser(_minimal_pdf_bytes())
    assert p.get_trailer() is None


def test_get_trailer_returns_dictionary_after_parse() -> None:
    p = _parser(_minimal_pdf_bytes())
    p.parse()
    trailer = p.get_trailer()
    assert isinstance(trailer, COSDictionary)
    assert trailer.get_int("Size") == 4


def test_get_root_returns_none_before_parse() -> None:
    p = _parser(_minimal_pdf_bytes())
    assert p.get_root() is None


def test_get_root_returns_catalog_after_parse() -> None:
    p = _parser(_minimal_pdf_bytes())
    p.parse()
    root = p.get_root()
    assert isinstance(root, COSDictionary)
    assert root.get_name("Type") == "Catalog"


def test_get_xref_trailer_resolver_returns_resolver() -> None:
    p = _parser(_minimal_pdf_bytes())
    resolver = p.get_xref_trailer_resolver()
    assert isinstance(resolver, XrefTrailerResolver)
    # Same instance on repeated calls.
    assert p.get_xref_trailer_resolver() is resolver


def test_get_xref_trailer_resolver_populated_after_parse() -> None:
    p = _parser(_minimal_pdf_bytes())
    p.parse()
    resolver = p.get_xref_trailer_resolver()
    xref = resolver.get_xref_table()
    # Three in-use objects from the minimal PDF.
    assert len(xref) >= 3


# ---------- set_eof_lookup_range / get_eof_lookup_range ----------


def test_eof_lookup_range_default_value() -> None:
    p = _parser(_minimal_pdf_bytes())
    # Default mirrors module-level _TAIL_SCAN_BYTES (4096).
    assert p.get_eof_lookup_range() == 4096


def test_set_eof_lookup_range_updates_value() -> None:
    p = _parser(_minimal_pdf_bytes())
    p.set_eof_lookup_range(8192)
    assert p.get_eof_lookup_range() == 8192


def test_set_eof_lookup_range_ignores_small_values() -> None:
    """Mirrors upstream's guard: byte_count <= 15 is a no-op."""
    p = _parser(_minimal_pdf_bytes())
    p.set_eof_lookup_range(8192)
    p.set_eof_lookup_range(15)  # ignored
    assert p.get_eof_lookup_range() == 8192
    p.set_eof_lookup_range(0)  # ignored
    assert p.get_eof_lookup_range() == 8192


def test_set_eof_lookup_range_does_not_break_parse() -> None:
    """A larger window should still find startxref correctly."""
    pdf = _minimal_pdf_bytes()
    p = _parser(pdf)
    p.set_eof_lookup_range(10_000)
    doc = p.parse()
    assert doc is not None


def test_sysprop_eof_lookup_range_constant() -> None:
    """Constant must match upstream verbatim for source-level parity."""
    assert SYSPROP_EOFLOOKUPRANGE == (
        "org.apache.pdfbox.pdfparser.nonSequentialPDFParser.eofLookupRange"
    )


# ---------- parse_pdf_header (Java-style boolean alias) ----------


def test_parse_pdf_header_returns_true_on_success() -> None:
    p = _parser(_minimal_pdf_bytes())
    assert p.parse_pdf_header() is True


def test_parse_pdf_header_returns_false_on_missing_header() -> None:
    p = _parser(b"not a pdf at all")
    assert p.parse_pdf_header() is False


def test_parse_pdf_header_returns_false_on_malformed_version() -> None:
    p = _parser(b"%PDF-bad\nrest")
    assert p.parse_pdf_header() is False


# ---------- constructor with decryption_password (Java line 58) ----------


def test_constructor_stages_decryption_password_str() -> None:
    """Mirrors ``PDFParser(RandomAccessRead, String)`` (Java line 58):
    the password is staged identically to ``set_password``."""
    p = PDFParser(RandomAccessReadBuffer(_minimal_pdf_bytes()), "hunter2")
    assert p.get_password() == "hunter2"


def test_constructor_stages_decryption_password_bytes() -> None:
    p = PDFParser(RandomAccessReadBuffer(_minimal_pdf_bytes()), b"\x00secret")
    assert p.get_password() == b"\x00secret"


def test_constructor_default_password_is_none() -> None:
    p = PDFParser(RandomAccessReadBuffer(_minimal_pdf_bytes()))
    assert p.get_password() is None


# ---------- parse(lenient) overload (Java line 149) ----------


def test_parse_with_lenient_true_keeps_lenient_flag() -> None:
    """Mirrors ``PDFParser.parse(boolean)`` whose first line is
    ``setLenient(lenient)`` (Java line 151)."""
    p = _parser(_minimal_pdf_bytes())
    p.set_lenient(False)
    p.parse(lenient=True)
    assert p.is_lenient() is True


def test_parse_with_lenient_false_toggles_lenient_off() -> None:
    p = _parser(_minimal_pdf_bytes())
    assert p.is_lenient() is True
    p.parse(lenient=False)
    assert p.is_lenient() is False


def test_parse_no_arg_preserves_existing_lenient_flag() -> None:
    p = _parser(_minimal_pdf_bytes())
    p.set_lenient(False)
    # Note: with strict mode the minimal PDF still parses (header is
    # well-formed), so the parse itself succeeds; we just verify the
    # flag was not silently changed.
    p.parse()
    assert p.is_lenient() is False


# ---------- initial_parse (Java line 105) ----------


def test_initial_parse_marks_initial_parse_done_flag() -> None:
    """Calling ``initial_parse()`` flips the cos_parser's
    ``initial_parse_done`` flag — mirrors the upstream
    ``initialParseDone = true`` line at the end of ``initialParse()``
    (Java line 122)."""
    p = _parser(_minimal_pdf_bytes())
    p.parse()
    cos = p._cos_parser  # type: ignore[attr-defined]
    assert cos is not None
    # Not auto-set by pypdfbox's parse() (kept lazy); explicit call flips.
    p.initial_parse()
    assert cos.is_initial_parse_done() is True


def test_initial_parse_raises_when_root_missing() -> None:
    """Mirrors upstream ``Missing root object specification in trailer.``
    error (Java line 112). pypdfbox's :meth:`parse` does not auto-call
    ``initial_parse`` (kept lazy for compat with synthetic fixtures);
    the public hook surfaces the missing-root error explicitly."""
    pdf = _build_pdf(
        [b"1 0 obj\n<< /Type /Pages /Kids [] /Count 0 >>\nendobj"],
        b"<< /Size 2 >>",  # no /Root
    )
    p = _parser(pdf)
    p.parse()  # parse() itself does not validate /Root
    with pytest.raises(PDFParseError, match="Missing root"):
        p.initial_parse()


def test_initial_parse_lenient_repairs_missing_catalog_type() -> None:
    """Mirrors the upstream ``isLenient() && !root.containsKey(TYPE)``
    branch (Java lines 115-118)."""
    # Build a PDF whose root dict omits /Type. The minimal builder always
    # writes /Type /Catalog, so synthesize the bytes manually.
    pdf = _build_pdf(
        [
            b"1 0 obj\n<< /Pages 2 0 R >>\nendobj",  # no /Type
            b"2 0 obj\n<< /Type /Pages /Kids [] /Count 0 >>\nendobj",
        ],
        b"<< /Size 3 /Root 1 0 R >>",
    )
    p = _parser(pdf)
    # Lenient by default; running initial_parse explicitly should
    # inject the missing /Type /Catalog (parse() leaves the resolver
    # untouched per pypdfbox's lazy contract).
    p.parse()
    p.initial_parse()
    root = p.get_root()
    assert isinstance(root, COSDictionary)
    assert root.get_name("Type") == "Catalog"


# ---------- create_document (Java line 194) ----------


def test_create_document_returns_pd_document() -> None:
    """Mirrors upstream ``PDFParser.createDocument()`` (Java line 194)."""
    p = _parser(_minimal_pdf_bytes())
    p.parse()
    pd = p.create_document()
    assert pd is not None
    # Same wrapper as ``get_pd_document`` — upstream's ``createDocument``
    # is the construction point that ``parse`` ultimately returns.
    assert pd is p.get_pd_document()


def test_create_document_before_parse_raises() -> None:
    p = _parser(_minimal_pdf_bytes())
    with pytest.raises(PDFParseError):
        p.create_document()
