"""Wave 1403 branch round-out for ``PDFParser.parse``.

Closes 207->209 — the ``if trailer is not None`` False arm: when
``self._resolver.get_trailer()`` returns ``None`` after ``parse_xref_chain``,
the document is *not* assigned a trailer there and ``parse`` proceeds straight
to ``populate_document``.

Wave 1402's attempt used a PDF that failed to parse before reaching line 206
(the ``contextlib.suppress`` masked the early failure), so line 207 was never
executed. Here we build a fully well-formed minimal PDF that parses cleanly
through ``parse_xref_chain`` and only then patch ``get_trailer`` to return
``None``.
"""

from __future__ import annotations

from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser.pdf_parser import PDFParser


def _minimal_pdf() -> bytes:
    body = b"%PDF-1.4\n"
    o1 = len(body)
    body += b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
    o2 = len(body)
    body += b"2 0 obj\n<< /Type /Pages /Kids [] /Count 0 >>\nendobj\n"
    xref_off = len(body)
    xref = b"xref\n0 3\n"
    xref += b"0000000000 65535 f \n"
    xref += b"%010d 00000 n \n" % o1
    xref += b"%010d 00000 n \n" % o2
    body += xref
    body += b"trailer\n<< /Size 3 /Root 1 0 R >>\n"
    body += b"startxref\n%d\n%%%%EOF\n" % xref_off
    return body


def test_parse_with_none_trailer_skips_set_trailer() -> None:
    """Closes 207->209: a clean parse reaches line 206 where ``get_trailer``
    is patched to None; ``set_trailer`` is skipped and parse completes."""
    parser = PDFParser(RandomAccessReadBuffer(_minimal_pdf()))
    parser._resolver.get_trailer = lambda: None  # type: ignore[assignment,method-assign]  # noqa: SLF001

    doc = parser.parse()
    # No trailer was assigned via the line-208 path.
    assert doc.get_trailer() is None
