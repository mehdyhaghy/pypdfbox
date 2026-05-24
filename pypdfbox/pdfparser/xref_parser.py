"""Cross-reference table / stream parser facade.

Mirrors upstream ``org.apache.pdfbox.pdfparser.XrefParser`` (PDFBox 3.0.x
extracted xref-assembly + trailer parsing out of ``PDFParser`` /
``COSParser`` into a small standalone class). pypdfbox keeps the actual
implementation inlined on :class:`pypdfbox.pdfparser.cos_parser.COSParser`
(``parse_xref``, ``parse_xref_table``, ``parse_xref_obj_stream``,
``parse_trailer``, ``parse_start_xref``, ``check_x_ref_offset``,
``check_x_ref_stream_offset``, ``calculate_x_ref_fixed_offset``,
``validate_xref_offsets``, ``check_xref_offsets``, ``find_object_key``)
plus xref-table assembly on
:class:`pypdfbox.pdfparser.xref_trailer_resolver.XrefTrailerResolver`.

This module exposes the same constructor / method shape as upstream so
ported callers that say::

    XrefParser(cos_parser).parse_xref(document, start_offset)

work without modification. It is a thin façade — no new behaviour.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.cos import COSDictionary, COSObjectKey

if TYPE_CHECKING:
    from pypdfbox.cos import COSDocument

    from .cos_parser import COSParser

__all__ = ["XrefParser"]


class XrefParser:
    """Parser façade for cross-reference tables and xref-stream objects.

    Mirrors upstream ``XrefParser``. The constructor wraps an existing
    :class:`COSParser` (which holds the source + document references)
    and forwards each public method to the equivalent inlined method on
    that parser.

    The upstream public surface (PDFBox 3.0.x) is exactly:

    * ``XrefParser(COSParser cosParser)`` — constructor.
    * ``Map<COSObjectKey, Long> getXrefTable()`` — accessor for the
      resolved xref table.
    * ``COSDictionary parseXref(COSDocument document, long startXRefOffset)``
      — drive the full xref-chain walk and return the merged trailer.
    """

    # Upstream private constants exposed as class-level for parity with
    # the Java source's static finals. They are not part of the public
    # API but having them here makes the wrapper self-documenting and
    # matches the upstream file shape.
    _X: int = 0x78  # 'x'
    _XREF_TABLE: bytes = b"xref"
    _STARTXREF: bytes = b"startxref"
    _MINIMUM_SEARCH_OFFSET: int = 6

    def __init__(self, cos_parser: COSParser) -> None:
        """Build an XrefParser bound to ``cos_parser``.

        Mirrors upstream ``XrefParser(COSParser)``. The wrapped parser
        owns the ``RandomAccessRead`` source and the ``COSDocument``;
        no copies are made."""
        self._parser = cos_parser

    # ------------------------------------------------------------------
    # Public surface (mirrors upstream).
    # ------------------------------------------------------------------

    def get_xref_table(self) -> dict[COSObjectKey, int]:
        """Return the resolved cross-reference table.

        Mirrors upstream ``getXrefTable()``. The result is the same
        mapping the wrapped parser populated on the bound
        :class:`COSDocument`. When no document is attached (e.g. a bare
        COSParser used for ad-hoc parsing), an empty dict is returned."""
        document = self._parser.document
        if document is None:
            return {}
        # COSDocument.get_xref_table mirrors upstream's same accessor —
        # see pypdfbox/cos/cos_document.py:get_xref_table.
        table = document.get_xref_table()
        # Strip None keys and coerce to a plain dict so callers get the
        # exact upstream surface (``Map<COSObjectKey, Long>``).
        return {k: v for k, v in table.items() if k is not None}

    def parse_xref(
        self, document: COSDocument, start_x_ref_offset: int
    ) -> COSDictionary | None:
        """Parse the full xref chain starting at ``start_x_ref_offset``.

        Mirrors upstream ``parseXref(COSDocument, long)``. The wrapped
        :class:`COSParser` already attaches the document at construction
        time; the ``document`` argument here is rebound onto the parser
        so callers that build the COSParser without one (or with a
        different one) still get upstream-correct behaviour.

        Returns the merged trailer dictionary, or ``None`` when the
        chain is empty."""
        # Upstream's parseXref takes the document fresh — match that.
        self._parser._document = document  # noqa: SLF001 — façade boundary
        return self._parser.parse_xref(start_x_ref_offset)
