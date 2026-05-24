"""Wave 1389 — verify :class:`pypdfbox.pdfparser.XrefParser` façade.

The pypdfbox XrefParser is a thin wrapper that mirrors the upstream
PDFBox public surface (``getXrefTable`` / ``parseXref``) while
delegating to inlined methods on
:class:`pypdfbox.pdfparser.cos_parser.COSParser`. These tests confirm
both that the upstream public surface is reachable through the façade
and that the underlying inlined behaviour still produces correct
xref output.
"""

from __future__ import annotations

import inspect

import pytest

from pypdfbox.cos import COSDictionary, COSDocument, COSObjectKey
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser import COSParser, PDFParseError, XrefParser


def _build_parser(payload: bytes, document: COSDocument) -> COSParser:
    return COSParser(RandomAccessReadBuffer(payload), document=document)


# ---------------------------------------------------------------------------
# Public surface — constructor + accessor + driver
# ---------------------------------------------------------------------------


def test_wave1389_xref_parser_exposes_upstream_public_surface() -> None:
    """The façade must expose the exact upstream public methods:
    constructor, ``get_xref_table``, ``parse_xref``."""
    members = {
        name
        for name, _ in inspect.getmembers(XrefParser, predicate=inspect.isfunction)
    }
    # Snake-case form of upstream public Java surface.
    assert "get_xref_table" in members
    assert "parse_xref" in members
    # The constructor must accept a single COSParser positional argument.
    sig = inspect.signature(XrefParser.__init__)
    params = [p for p in sig.parameters.values() if p.name != "self"]
    assert len(params) == 1
    assert params[0].name == "cos_parser"


def test_wave1389_constructor_binds_to_cos_parser() -> None:
    """Constructor stores the wrapped COSParser without copying."""
    doc = COSDocument()
    try:
        cos = _build_parser(b"", doc)
        xref = XrefParser(cos)
        # Internal binding is the same object — façade does not clone.
        assert xref._parser is cos
    finally:
        doc.close()


def test_wave1389_get_xref_table_returns_empty_without_document() -> None:
    """A bare COSParser (no document) yields an empty xref table."""
    cos = COSParser(RandomAccessReadBuffer(b""))
    xref = XrefParser(cos)
    assert xref.get_xref_table() == {}


def test_wave1389_get_xref_table_returns_document_table() -> None:
    """When a document is bound, the façade returns its xref table."""
    doc = COSDocument()
    try:
        # Inject one xref entry directly onto the document.
        key = COSObjectKey(7, 0)
        doc.add_x_ref_table({key: 42})

        xref = XrefParser(_build_parser(b"", doc))
        table = xref.get_xref_table()
        assert table.get(key) == 42
        # None keys are filtered out (upstream returns Map<COSObjectKey,Long>;
        # pypdfbox's COSDocument allows None placeholders internally).
        assert None not in table
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# parse_xref — drives the chain through to the merged trailer
# ---------------------------------------------------------------------------


def _minimal_pdf_with_xref(prev_offset: int | None = None) -> bytes:
    """Build a minimal PDF with one traditional xref table + trailer.

    When ``prev_offset`` is supplied it is added to the trailer as
    ``/Prev`` — used to exercise the loop-detection path."""
    body = b"%PDF-1.4\n1 0 obj\n<< /Answer 42 >>\nendobj\n"
    xref_start = len(body)
    trailer = b"<< /Size 2"
    if prev_offset is not None:
        trailer += b" /Prev " + str(prev_offset).encode()
    trailer += b" >>\n"
    xref_section = (
        b"xref\n"
        b"0 2\n"
        b"0000000000 65535 f \n"
        b"0000000009 00000 n \n"
        b"trailer\n" + trailer
        + b"startxref\n" + str(xref_start).encode() + b"\n%%EOF\n"
    )
    return body + xref_section


def test_wave1389_parse_xref_returns_trailer_dictionary() -> None:
    """End-to-end: a real-shaped PDF with one xref section gets a
    trailer dictionary back from the façade."""
    payload = _minimal_pdf_with_xref()
    doc = COSDocument()
    try:
        cos = _build_parser(payload, doc)
        xref = XrefParser(cos)
        # Pass a *different* document instance to confirm the façade
        # rebinds it onto the wrapped parser (matches upstream where the
        # document is supplied per-call, not per-constructor).
        fresh_doc = COSDocument()
        try:
            trailer = xref.parse_xref(fresh_doc, payload.find(b"startxref"))
            assert isinstance(trailer, COSDictionary)
            assert cos.document is fresh_doc
        finally:
            fresh_doc.close()
    finally:
        doc.close()


def test_wave1389_parse_xref_detects_prev_loop() -> None:
    """The wrapper inherits cycle detection from the inlined
    implementation: a self-referencing /Prev raises ``/Prev loop``."""
    body = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n"
    xref_start = len(body)
    # Trailer's /Prev points back to its own xref offset.
    payload = body + (
        b"xref\n"
        b"0 2\n"
        b"0000000000 65535 f \n"
        b"0000000009 00000 n \n"
        b"trailer\n"
        b"<< /Size 2 /Prev " + str(xref_start).encode() + b" >>\n"
        b"startxref\n" + str(xref_start).encode() + b"\n%%EOF\n"
    )
    doc = COSDocument()
    try:
        cos = _build_parser(payload, doc)
        xref = XrefParser(cos)
        with pytest.raises(PDFParseError, match=r"/Prev loop"):
            xref.parse_xref(doc, payload.find(b"startxref"))
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# Parity with upstream constants
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("attr", "expected"),
    [
        ("_X", 0x78),
        ("_XREF_TABLE", b"xref"),
        ("_STARTXREF", b"startxref"),
        ("_MINIMUM_SEARCH_OFFSET", 6),
    ],
    ids=["X-byte", "XREF-keyword", "STARTXREF-keyword", "MIN-SEARCH-OFFSET"],
)
def test_wave1389_upstream_private_constants_mirrored(
    attr: str, expected: object
) -> None:
    """Upstream's private finals are mirrored on the wrapper for
    parity-audit visibility; verify each is present and correctly
    valued."""
    assert getattr(XrefParser, attr) == expected
