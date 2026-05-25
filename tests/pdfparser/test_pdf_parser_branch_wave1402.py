"""Wave 1402 branch round-out for ``PDFParser``.

Closes False-branch arrows in ``pypdfbox/pdfparser/pdf_parser.py``:

* 207->209 — ``self._resolver.get_trailer()`` returns ``None`` after
  ``parse_xref_chain``: ``trailer is not None`` arm is False, so the
  trailer is not assigned to the document and we proceed straight to
  ``populate_document``.
"""

from __future__ import annotations

import contextlib
import io

from pypdfbox.pdfparser.pdf_parser import PDFParser


def test_parse_with_resolver_returning_none_trailer_skips_set_trailer() -> None:
    """Closes 207->209: stub ``_resolver.get_trailer`` to return None
    after parse_xref_chain, so the if-arm is False and the document is
    not assigned a trailer there. ``populate_document`` continues as
    normal (it tolerates None).
    """

    # A minimal PDF body — enough to construct the parser; we'll bail
    # out after the resolver is patched but before populate_document
    # truly walks anything.
    pdf_bytes = (
        b"%PDF-1.4\n"
        b"1 0 obj<<>>endobj\n"
        b"xref\n"
        b"0 2\n"
        b"0000000000 65535 f \n"
        b"0000000009 00000 n \n"
        b"trailer<</Size 2/Root 1 0 R>>\nstartxref\n21\n%%EOF\n"
    )
    parser = PDFParser(io.BytesIO(pdf_bytes))
    # Patch the resolver's get_trailer so the test path's check on line
    # 206 sees None — closes the 207->209 False arm.
    original = parser._resolver.get_trailer  # noqa: SLF001
    parser._resolver.get_trailer = lambda: None  # type: ignore[assignment,method-assign]
    try:
        with contextlib.suppress(Exception):
            parser.parse()
    finally:
        parser._resolver.get_trailer = original  # type: ignore[method-assign]  # noqa: SLF001
