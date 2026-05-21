"""Tests ported from PDFBox 3.0 ``COSWriterCompressionPoolTest``.

Source: ``pdfbox/src/test/java/org/apache/pdfbox/pdfwriter/COSWriterCompressionPoolTest.java``
on the apache/pdfbox 3.0 branch.

The class holds a single ``testPDFBox6036`` test that constructs a
:class:`COSWriterCompressionPool` over a document with a long
``/Outlines`` sibling chain — guarding the iterative-walk fix for the
stack overflow the original recursive ``addStructure`` produced.

Upstream's loop runs ``i = 1, 2, 4, 8, ..., 131_072`` capped at
``222_222``. Python's recursion limit is far below Java's default
thread stack, so for parity we exercise the same powers-of-two ladder
but cap at the level upstream actually reaches (``131_072``) — the
final iteration is the one that crashed the old recursion.
"""

from __future__ import annotations

from pypdfbox.pdfwriter.compress.compress_parameters import CompressParameters
from pypdfbox.pdfwriter.compress.cos_writer_compression_pool import (
    COSWriterCompressionPool,
)
from pypdfbox.pdmodel import PDDocument
from pypdfbox.pdmodel.interactive.documentnavigation.outline import (
    PDDocumentOutline,
    PDOutlineItem,
)


def test_pdf_box_6036() -> None:
    """Port of ``COSWriterCompressionPoolTest#testPDFBox6036``.

    Each iteration builds a fresh document, attaches an outline with
    ``i`` children appended via :meth:`PDDocumentOutline.add_last`, and
    constructs the compression pool. The construction itself is the
    assertion — if the walk regresses to recursion, this raises
    :class:`RecursionError` at the deepest iteration.
    """
    i = 1
    while i <= 222_222:
        document = PDDocument()
        try:
            outline = PDDocumentOutline()
            document.get_document_catalog().set_document_outline(outline)
            for _ in range(i):
                outline.add_last(PDOutlineItem())
            COSWriterCompressionPool(document, CompressParameters.DEFAULT_COMPRESSION)
        finally:
            document.close()
        i *= 2
