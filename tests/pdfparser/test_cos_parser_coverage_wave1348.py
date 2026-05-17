"""Wave-1348 coverage-boost tests for ``pypdfbox.pdfparser.cos_parser``.

Closes the residual gaps after waves 1323 / 1332. Targets:

* ``get_startxref_offset`` short-read failure (line 1738);
* ``parse_xref`` ``/Prev`` loop detection (line 1840), parse_xref_table
  / parse_trailer failure (lines 1847-1852), xref-stream branch (line
  1859);
* ``parse_xref_obj_stream`` stream-body branch (lines 1893-1897);
* ``parse_file_object`` stream-after-dict branch (lines 1970, 1975-1977);
* ``check_x_ref_offset`` brute-force fallback (lines 2107-2109);
* ``check_x_ref_stream_offset`` parse-failure recovery (lines 2132-2134);
* ``find_object_key`` outer-except path (lines 2237-2239).
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSDictionary,
    COSDocument,
    COSInteger,
    COSName,
    COSObjectKey,
)
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser import PDFParseError
from pypdfbox.pdfparser.cos_parser import COSParser


def _parser(data: bytes, document: COSDocument | None = None) -> COSParser:
    return COSParser(RandomAccessReadBuffer(data), document=document)


# ---------- get_startxref_offset: short-read in trailing buffer ----------


def test_get_startxref_offset_raises_when_trailing_read_returns_less_than_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If the source short-reads inside the trailing-buffer loop the
    parser must raise a PDFParseError (line 1738)."""
    parser = _parser(b"%PDF-1.4\nstartxref\n9\n%%EOF\n")

    # Force read_into to consistently return 0 — simulates premature EOF
    # in the middle of the trailing-buffer fill.
    def _bad_read_into(buf, off, n):  # type: ignore[no-untyped-def]
        return 0

    monkeypatch.setattr(parser._src, "read_into", _bad_read_into)
    with pytest.raises(PDFParseError, match="No more bytes to read"):
        parser.get_startxref_offset()


# ---------- parse_xref: /Prev loop detection (line 1840) ----------


def test_parse_xref_detects_prev_loop() -> None:
    """A trailer whose /Prev points back to its own xref offset must
    raise ``/Prev loop at offset X``."""
    # Build a single xref section whose trailer's /Prev re-targets itself.
    body = (
        b"%PDF-1.4\n"
        b"1 0 obj\n<<>>\nendobj\n"
    )
    xref_start = len(body)
    xref_section = (
        b"xref\n"
        b"0 2\n"
        b"0000000000 65535 f \n"
        b"0000000009 00000 n \n"
        b"trailer\n"
        b"<< /Size 2 /Prev " + str(xref_start).encode() + b" >>\n"
        b"startxref\n" + str(xref_start).encode() + b"\n%%EOF\n"
    )
    payload = body + xref_section
    parser = _parser(payload, COSDocument())
    with pytest.raises(PDFParseError, match=r"/Prev loop"):
        parser.parse_xref(payload.find(b"startxref"))


# ---------- parse_xref: parse_xref_table failure raises (line 1847) ------


def test_parse_xref_raises_when_xref_table_malformed() -> None:
    """When the byte at the resolved offset is 'x' but the keyword isn't
    ``xref``, ``parse_xref_table`` returns False and ``parse_xref``
    raises ``Expected trailer object`` (line 1847)."""
    # Header → noise keyword starting with 'x' at the startxref target.
    body = (
        b"%PDF-1.4\n"
        b"xyz keyword here\n"  # offset 9: starts with 'x' but != 'xref'
    )
    xref_pos = body.find(b"xyz")
    payload = body + (
        b"startxref\n" + str(xref_pos).encode() + b"\n%%EOF\n"
    )
    parser = _parser(payload, COSDocument())
    parser.set_lenient(False)  # avoid brute-force recovery
    with pytest.raises(PDFParseError, match="Expected trailer object"):
        parser.parse_xref(payload.find(b"startxref"))


# ---------- parse_xref: xref-stream branch (line 1859) ----------


def test_parse_xref_handles_xref_stream_branch() -> None:
    """When the first byte at the resolved offset is not 'x' (xref
    table), the parser falls into the xref-stream-object branch
    (line 1859). An xref-stream-only file exercises that path."""
    # Synthetic minimal xref stream as a standalone object.
    body = (
        b"%PDF-1.5\n"
        b"5 0 obj\n<< /Type /XRef /Size 6 >>\nendobj\n"
    )
    obj_start = body.find(b"5 0 obj")
    payload = body + (
        b"startxref\n" + str(obj_start).encode() + b"\n%%EOF\n"
    )
    parser = _parser(payload, COSDocument())
    # Does not raise; the xref-stream path returns None trailer when no
    # traditional xref is present.
    parser.parse_xref(payload.find(b"startxref"))


# ---------- parse_xref_obj_stream: with stream body (lines 1893-1897) -----


def test_parse_xref_obj_stream_handles_stream_body() -> None:
    """When the xref-stream object has an actual ``stream/endstream``
    body the parser must consume it via the stream-body fast path."""
    body_bytes = b"\x00\x00\x00\x09\x00"
    # Minimal /Length to be present; we don't actually decode the body.
    payload = (
        b"7 0 obj\n"
        b"<< /Type /XRef /Length " + str(len(body_bytes)).encode() + b" >>\n"
        b"stream\n" + body_bytes + b"\nendstream\nendobj\n"
    )
    parser = _parser(payload, COSDocument())
    # Returns -1 because no /Prev entry.
    assert parser.parse_xref_obj_stream(0, True) == -1


# ---------- parse_file_object: stream-after-dict (lines 1970, 1975-1977) -


def test_parse_file_object_promotes_stream_after_dict() -> None:
    """When parse_file_object encounters a dict followed by ``stream``
    it must promote the dict to a COSStream via parse_cos_stream."""
    body_bytes = b"hello-stream"
    payload = (
        b"4 0 obj\n"
        b"<< /Length " + str(len(body_bytes)).encode() + b" >>\n"
        b"stream\n" + body_bytes + b"\nendstream\nendobj\n"
    )
    parser = _parser(payload, COSDocument())
    parsed = parser.parse_file_object(0, COSObjectKey(4, 0))
    # parse_cos_stream returned a stream object (COSStream subclasses
    # COSDictionary, so the parsed value is a dict).
    assert isinstance(parsed, COSDictionary)
    length_entry = parsed.get_dictionary_object(COSName.get_pdf_name("Length"))
    assert isinstance(length_entry, COSInteger)
    assert length_entry.int_value() == len(body_bytes)


# ---------- check_x_ref_offset brute-force fallback (lines 2107-2109) ----


def test_check_x_ref_offset_falls_through_to_brute_force() -> None:
    """When the claimed offset is non-zero and neither a literal ``xref``
    keyword nor a valid xref-stream object lives there, ``check_x_ref_offset``
    drops to ``calculate_x_ref_fixed_offset`` (lines 2107-2109)."""
    # Build a file with a valid xref further along, but point the parser
    # at a noise offset.
    body = (
        b"%PDF-1.4\n"
        b"1 0 obj\n<<>>\nendobj\n"
    )
    xref_pos = len(body)
    payload = body + (
        b"xref\n"
        b"0 2\n"
        b"0000000000 65535 f \n"
        b"0000000009 00000 n \n"
        b"trailer\n<< /Size 2 >>\nstartxref\n"
        + str(xref_pos).encode() + b"\n%%EOF\n"
    )
    parser = _parser(payload, COSDocument())
    parser.set_lenient(True)
    # Point check_x_ref_offset at a noisy mid-body offset (>0, not at
    # xref/xref-stream). Must be >0 to enter the brute-force branch
    # (lines 2106-2109).
    bad_offset = body.find(b"1 0 obj") + 2  # mid-token, not a real header
    assert bad_offset > 0
    result = parser.check_x_ref_offset(bad_offset)
    assert isinstance(result, int)


# ---------- check_x_ref_stream_offset parse-failure recovery -------------


def test_check_x_ref_stream_offset_recovers_after_parse_error() -> None:
    """A header that begins as a plausible object header but fails to
    parse exercises the ``(PDFParseError, ValueError)`` catch
    (lines 2132-2134)."""
    # Whitespace + digit start + 'obj' but with a malformed body that
    # blows up parse_direct_object.
    payload = b" 5 0 obj\n<< /Type /Bogus /K [ "  # unterminated array
    parser = _parser(payload, COSDocument())
    parser.set_lenient(True)
    # offset 1 satisfies the "whitespace-before-offset" precondition;
    # _src.seek(0) reads the leading space byte.
    assert parser.check_x_ref_stream_offset(1) is False


# ---------- find_object_key outer-except path (lines 2237-2239) ---------


def test_find_object_key_returns_none_on_keyword_failure() -> None:
    """When ``read_expected_string('obj')`` fails *after* reading the
    object/generation numbers, the outer ``except PDFParseError`` handler
    in ``find_object_key`` returns ``None`` (lines 2237-2238)."""
    # Object header missing the literal ``obj`` keyword. Place it past
    # MINIMUM_SEARCH_OFFSET (=6) so we don't trigger the early-return.
    payload = b"          5 0 not-obj\n<<>>\nendobj\n"
    parser = _parser(payload, COSDocument())
    parser.set_lenient(True)
    out = parser.find_object_key(COSObjectKey(5, 0), 10, {})
    assert out is None


def test_find_object_key_returns_none_strict_gen_mismatch() -> None:
    """Strict mode with mismatched generation number must fall through
    every return-path and hit the final ``return None`` (line 2239)."""
    payload = b"          5 7 obj\n<<>>\nendobj\n"
    parser = _parser(payload, COSDocument())
    parser.set_lenient(False)
    # Asked for generation 0; header says generation 7. Object number
    # matches so we don't return at 2227. Read succeeds so we don't hit
    # the except. gen != 0, and not lenient → both ifs fail → final
    # ``return None`` at 2239.
    out = parser.find_object_key(COSObjectKey(5, 0), 10, {})
    assert out is None
