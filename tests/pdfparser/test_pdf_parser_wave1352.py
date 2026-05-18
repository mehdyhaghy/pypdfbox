"""Wave 1352 coverage-boost tests for :mod:`pypdfbox.pdfparser.pdf_parser`.

Closes the remaining uncovered branches:

* line 227 — :meth:`PDFParser.initial_parse` "missing trailer" raise.
* lines 784-787 — hybrid ``/XRefStm`` parse failure under lenient mode
  (the ``except PDFParseError`` / ``if not lenient: raise`` /
  ``_LOG.exception`` triple).
* line 1265 — :meth:`PDFParser._read_until_endstream` EOF raise.
* line 1267 — partial-read trim path (``n < remaining``).
* line 1272 — missing ``endstream`` marker raise.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSObjectKey, COSStream
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser import PDFParseError, PDFParser


def _parser(data: bytes) -> PDFParser:
    return PDFParser(RandomAccessReadBuffer(data))


# ---------- line 227: initial_parse with no trailer ----------


def test_initial_parse_without_trailer_raises() -> None:
    """``PDFParser.initial_parse`` runs against the
    xref-trailer-resolver's current trailer. When no parse has happened
    and the resolver has no trailer, the method raises
    :class:`PDFParseError` with the documented message."""
    parser = _parser(b"%PDF-1.4\n%%EOF\n")
    # No parse() invoked → resolver has no trailer.
    with pytest.raises(PDFParseError, match="Missing trailer"):
        parser.initial_parse()


# ---------- lines 784-787: hybrid /XRefStm parse failure (lenient) ----------


def _hybrid_pdf_with_bad_xrefstm_offset(bad_offset: int) -> bytes:
    """Tiny PDF with a traditional xref table whose trailer carries
    ``/XRefStm <bad_offset>`` pointing into garbage. The xref-table parse
    succeeds; the hybrid /XRefStm follow-up raises PDFParseError and the
    lenient-fallback log path fires."""
    out = bytearray(b"%PDF-1.5\n")
    obj_offset = len(out)
    out += b"1 0 obj\n<< /Type /Catalog >>\nendobj\n"
    xref_offset = len(out)
    out += b"xref\n0 2\n"
    out += b"0000000000 65535 f \n"
    out += f"{obj_offset:010d} 00000 n \n".encode("ascii")
    out += (
        b"trailer\n<< /Size 2 /Root 1 0 R /XRefStm "
        + str(bad_offset).encode("ascii")
        + b" >>\n"
    )
    out += b"startxref\n" + str(xref_offset).encode("ascii") + b"\n%%EOF"
    return bytes(out)


def test_hybrid_xrefstm_bad_offset_logged_under_lenient_mode(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Parsing a hybrid /XRefStm whose offset is junk must not abort the
    whole parse in lenient mode — it logs the failure via
    ``_LOG.exception`` (lines 784-787) and keeps going. The base xref
    table alone is still enough to load the catalog."""
    pdf = _hybrid_pdf_with_bad_xrefstm_offset(bad_offset=5)
    parser = _parser(pdf)
    parser.set_lenient(True)
    caplog.set_level("ERROR")
    # Should not raise — the catalog is reachable via the legacy xref
    # table.
    parser.parse()
    # The logger emitted via ``_LOG.exception`` carries this prefix.
    assert any(
        "failed to parse hybrid /XRefStm" in r.getMessage()
        for r in caplog.records
    )


def test_hybrid_xrefstm_bad_offset_raises_when_strict() -> None:
    """The same junk /XRefStm offset propagates as PDFParseError when
    lenient mode is off (line 786: ``raise``)."""
    pdf = _hybrid_pdf_with_bad_xrefstm_offset(bad_offset=5)
    parser = _parser(pdf)
    parser.set_lenient(False)
    with pytest.raises(PDFParseError):
        parser.parse()


# ---------- lines 1265, 1267, 1272: _read_until_endstream paths ----------


def _build_pdf_with_lenient_stream(
    body: bytes, *, trailing: bytes = b"endstream\nendobj\n"
) -> bytes:
    """Wrap ``body`` in a single indirect ``stream`` object with NO
    ``/Length`` entry — forces the parser into the lenient
    :meth:`_read_until_endstream` fallback. ``trailing`` is appended
    verbatim after the body (typical: ``"endstream\nendobj\n"``)."""
    out = bytearray(b"%PDF-1.4\n")
    obj_offset = len(out)
    out += b"1 0 obj\n<< /Type /Stream >>\nstream\n"
    out += body
    out += trailing
    catalog_offset = len(out)
    out += b"2 0 obj\n<< /Type /Catalog >>\nendobj\n"
    xref_offset = len(out)
    out += b"xref\n0 3\n"
    out += b"0000000000 65535 f \n"
    out += f"{obj_offset:010d} 00000 n \n".encode("ascii")
    out += f"{catalog_offset:010d} 00000 n \n".encode("ascii")
    out += b"trailer\n<< /Size 3 /Root 2 0 R >>\n"
    out += b"startxref\n" + str(xref_offset).encode("ascii") + b"\n%%EOF"
    return bytes(out)


def test_read_until_endstream_finds_marker_via_lenient_recovery() -> None:
    """Sanity: a stream object with no /Length but a clean
    ``endstream`` marker is recovered. Hits the ``marker_at >= 0``
    happy path so the line-1272 negative-branch test is meaningful."""
    pdf = _build_pdf_with_lenient_stream(b"abcdef\n")
    parser = _parser(pdf)
    parser.set_lenient(True)
    doc = parser.parse()
    # Force resolution of object 1, which triggers _read_stream_body and,
    # because /Length is missing, _read_until_endstream.
    obj1 = doc.get_object_from_pool(COSObjectKey(1, 0))
    stream = obj1.get_object()
    assert isinstance(stream, COSStream)
    with stream.create_input_stream() as src:
        # Lenient recovery trims trailing EOL before "endstream".
        assert src.read().startswith(b"abcdef")


def test_read_until_endstream_missing_marker_raises() -> None:
    """A stream-body region with no ``endstream`` marker anywhere in
    the rest of the file → line 1272 raise."""
    # Body has no "endstream" sequence at all.
    out = bytearray(b"%PDF-1.4\n")
    out += b"1 0 obj\n<< /Type /Stream >>\nstream\n"
    out += b"plain bytes with no marker\n"
    # No "endstream" anywhere — EOF terminator only.
    out += b"\n%%EOF"
    parser = _parser(bytes(out))
    parser.set_lenient(True)
    # Drive the resolver directly: parse triggers initial trailer search
    # via brute-force in lenient mode.
    with pytest.raises(PDFParseError):
        parser.parse()


def test_read_until_endstream_direct_call_eof_raises() -> None:
    """Call ``_read_until_endstream`` against a parser whose source
    reports a non-zero remaining length but whose bulk read returns the
    EOF sentinel — hits line 1264-1265.

    ``RandomAccessReadBuffer`` never gets into that state in practice
    (seek clamps to ``length()``), but the spec allows it for
    non-seekable / stream-fed sources. We stub a minimal
    ``RandomAccessRead`` whose ``length()`` lies about the available
    bytes so the parser computes ``remaining > 0`` while ``read_into``
    returns ``EOF``.
    """
    from pypdfbox.io import RandomAccessRead

    class _FakeEOFSource(RandomAccessRead):
        def __init__(self) -> None:
            self._pos = 0
            self._closed = False

        def read(self) -> int:
            return self.EOF

        def read_into(
            self,
            buf: bytearray,
            offset: int = 0,
            length: int | None = None,
        ) -> int:
            return self.EOF

        def get_position(self) -> int:
            return self._pos

        def seek(self, position: int) -> None:
            self._pos = position

        def length(self) -> int:
            # Lie about having bytes available.
            return 64

        def close(self) -> None:
            self._closed = True

        def is_closed(self) -> bool:
            return self._closed

    parser = _parser(b"")
    parser._src = _FakeEOFSource()  # noqa: SLF001
    with pytest.raises(PDFParseError, match="expected 'endstream'"):
        parser._read_until_endstream()  # noqa: SLF001


def test_read_until_endstream_partial_read_trims_buffer() -> None:
    """A source that returns fewer bytes than the caller requested
    triggers the ``del buf[n:]`` trim at line 1267. The resulting
    truncated buffer still has an ``endstream`` marker so the lenient
    recovery succeeds."""
    from pypdfbox.io import RandomAccessRead

    payload = b"abc\nendstream after\n"

    class _ShortReadSource(RandomAccessRead):
        def __init__(self) -> None:
            self._pos = 0
            self._closed = False

        def read(self) -> int:
            if self._pos >= len(payload):
                return self.EOF
            b = payload[self._pos]
            self._pos += 1
            return b

        def read_into(
            self,
            buf: bytearray,
            offset: int = 0,
            length: int | None = None,
        ) -> int:
            if length is None:
                length = len(buf) - offset
            if self._pos >= len(payload):
                return self.EOF if length > 0 else 0
            # Always serve fewer bytes than requested — the real bytes
            # are still less than ``self.length()`` so the caller's
            # ``remaining`` overcounts.
            available = len(payload) - self._pos
            n = min(length, available)
            buf[offset : offset + n] = payload[self._pos : self._pos + n]
            self._pos += n
            return n

        def get_position(self) -> int:
            return self._pos

        def seek(self, position: int) -> None:
            self._pos = position

        def length(self) -> int:
            # Pretend to be longer than the real payload.
            return len(payload) + 32

        def close(self) -> None:
            self._closed = True

        def is_closed(self) -> bool:
            return self._closed

    parser = _parser(b"")
    parser._src = _ShortReadSource()  # noqa: SLF001
    body = parser._read_until_endstream()  # noqa: SLF001
    # Body lands before the marker and after EndstreamFilterStream's
    # trailing-EOL trim.
    assert body.startswith(b"abc")
    assert b"endstream" not in body


def test_read_until_endstream_direct_call_missing_marker_raises() -> None:
    """Call ``_read_until_endstream`` against a buffer that has bytes
    but no ``endstream`` marker — hits line 1272."""
    parser = _parser(b"no marker in here at all\n")
    with pytest.raises(PDFParseError, match="expected 'endstream'"):
        parser._read_until_endstream()  # noqa: SLF001


def test_read_until_endstream_direct_call_recovers_body() -> None:
    """Happy path through ``_read_until_endstream`` — body bytes plus a
    valid marker. Asserts the returned body and the cursor position
    landing immediately past the marker."""
    payload = b"hello world\n"
    data = payload + b"endstream tail"
    parser = _parser(data)
    out = parser._read_until_endstream()  # noqa: SLF001
    # Lenient recovery trims the trailing EOL inside the EndstreamFilterStream.
    assert out.startswith(b"hello world")
    # Cursor sits just past 'endstream'.
    pos = parser._src.get_position()  # noqa: SLF001
    assert data[pos : pos + len(b" tail")] == b" tail"
