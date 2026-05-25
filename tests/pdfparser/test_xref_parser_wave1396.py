"""Wave 1396 — XrefParser façade exposes upstream private-helper surface.

PDFBox 3.0.x's ``XrefParser`` declares ten ``private`` helpers
(``parseTrailer``, ``parseXrefObjStream``, ``checkXRefOffset``,
``calculateXRefFixedOffset``, ``checkXRefStreamOffset``,
``validateXrefOffsets``, ``checkXrefOffsets``, ``findObjectKey``,
``parseStartXref``, ``parseXrefTable``). Wave 1389 added the public
``getXrefTable`` / ``parseXref`` façade; wave 1396 closes the remaining
parity gap by exposing the private helpers as delegators on the wrapper
that forward to the inlined COSParser implementation. These tests verify
both that the surface is present and that each delegator preserves the
underlying behaviour.
"""

from __future__ import annotations

import inspect

from pypdfbox.cos import COSDocument, COSObjectKey
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser import COSParser, XrefParser

_HELPERS = (
    "parse_trailer",
    "parse_xref_obj_stream",
    "check_x_ref_offset",
    "calculate_x_ref_fixed_offset",
    "check_x_ref_stream_offset",
    "validate_xref_offsets",
    "check_xref_offsets",
    "find_object_key",
    "parse_start_xref",
    "parse_xref_table",
)


def _build_minimal_pdf() -> bytes:
    body = b"%PDF-1.4\n1 0 obj\n<< /Answer 42 >>\nendobj\n"
    xref_start = len(body)
    xref_section = (
        b"xref\n"
        b"0 2\n"
        b"0000000000 65535 f \n"
        b"0000000009 00000 n \n"
        b"trailer\n<< /Size 2 >>\nstartxref\n"
        + str(xref_start).encode()
        + b"\n%%EOF\n"
    )
    return body + xref_section


def test_wave1396_facade_exposes_all_upstream_private_helpers() -> None:
    """All 10 upstream private helper names are present on the wrapper."""
    members = {
        name
        for name, _ in inspect.getmembers(XrefParser, predicate=inspect.isfunction)
    }
    for helper in _HELPERS:
        assert helper in members, f"missing façade method: {helper}"


def test_wave1396_parse_start_xref_delegates_to_cos_parser() -> None:
    """``parse_start_xref`` returns the same value as the inlined COSParser
    method when both are pointed at the same ``startxref`` marker."""
    payload = _build_minimal_pdf()
    doc = COSDocument()
    try:
        cos = COSParser(RandomAccessReadBuffer(payload), document=doc)
        xref = XrefParser(cos)
        cos._src.seek(payload.find(b"startxref"))
        via_facade = xref.parse_start_xref()
        # Direct call on the wrapped parser at the same position should yield
        # the exact same value.
        cos._src.seek(payload.find(b"startxref"))
        via_inline = cos.parse_start_xref()
        assert via_facade == via_inline
        # And the value is the offset of the xref table in the PDF body.
        assert via_facade == payload.find(b"xref\n0 2")
    finally:
        doc.close()


def test_wave1396_validate_xref_offsets_none_returns_true() -> None:
    """Upstream ``validateXrefOffsets(null)`` short-circuits to true; the
    façade preserves that behaviour."""
    doc = COSDocument()
    try:
        cos = COSParser(RandomAccessReadBuffer(b""), document=doc)
        xref = XrefParser(cos)
        assert xref.validate_xref_offsets(None) is True
    finally:
        doc.close()


def test_wave1396_check_x_ref_stream_offset_zero_returns_true() -> None:
    """Upstream ``checkXRefStreamOffset(0)`` short-circuits to true; the
    façade preserves that behaviour."""
    doc = COSDocument()
    try:
        cos = COSParser(RandomAccessReadBuffer(b""), document=doc)
        xref = XrefParser(cos)
        assert xref.check_x_ref_stream_offset(0) is True
    finally:
        doc.close()


def test_wave1396_find_object_key_below_minimum_offset_returns_none() -> None:
    """Upstream ``findObjectKey`` returns null for offsets below
    ``MINIMUM_SEARCH_OFFSET``; the façade preserves that behaviour."""
    doc = COSDocument()
    try:
        cos = COSParser(RandomAccessReadBuffer(b""), document=doc)
        xref = XrefParser(cos)
        # offset 3 < MINIMUM_SEARCH_OFFSET (6) — must short-circuit to None.
        assert xref.find_object_key(COSObjectKey(1, 0), 3, {}) is None
    finally:
        doc.close()


def test_wave1396_check_xref_offsets_delegates_without_error() -> None:
    """``check_xref_offsets`` is a void delegate; with an empty xref table
    the call must complete without raising."""
    doc = COSDocument()
    try:
        cos = COSParser(RandomAccessReadBuffer(b""), document=doc)
        xref = XrefParser(cos)
        # Should not raise even when the xref table is empty.
        xref.check_xref_offsets()
    finally:
        doc.close()
