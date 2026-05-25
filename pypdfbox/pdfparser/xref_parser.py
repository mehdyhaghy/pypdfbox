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

    # ------------------------------------------------------------------
    # Upstream private-helper parity surface.
    #
    # PDFBox 3.0.x's ``XrefParser`` declares ten ``private`` helpers
    # (``parseTrailer``, ``parseXrefObjStream``, ``checkXRefOffset``,
    # ``calculateXRefFixedOffset``, ``checkXRefStreamOffset``,
    # ``validateXrefOffsets``, ``checkXrefOffsets``, ``findObjectKey``,
    # ``parseStartXref``, ``parseXrefTable``). pypdfbox keeps the
    # implementations inlined on :class:`COSParser`; the methods below
    # are thin façade delegators so the upstream surface is reachable
    # through ``XrefParser`` exactly as it is in Java. No behavioural
    # change — each forwards to the existing COSParser inlined version.
    # ------------------------------------------------------------------

    def parse_trailer(self) -> bool:
        """Mirror of upstream ``parseTrailer()``. Delegates to
        :meth:`COSParser.parse_trailer`."""
        return self._parser.parse_trailer()

    def parse_xref_obj_stream(
        self, obj_byte_offset: int, is_standalone: bool
    ) -> int:
        """Mirror of upstream ``parseXrefObjStream(long, boolean)``. Delegates
        to :meth:`COSParser.parse_xref_obj_stream`."""
        return self._parser.parse_xref_obj_stream(obj_byte_offset, is_standalone)

    def check_x_ref_offset(self, start_x_ref_offset: int) -> int:
        """Mirror of upstream ``checkXRefOffset(long)``. Delegates to
        :meth:`COSParser.check_x_ref_offset`."""
        return self._parser.check_x_ref_offset(start_x_ref_offset)

    def calculate_x_ref_fixed_offset(self, object_offset: int) -> int:
        """Mirror of upstream ``calculateXRefFixedOffset(long)``. Delegates
        to :meth:`COSParser.calculate_x_ref_fixed_offset`."""
        return self._parser.calculate_x_ref_fixed_offset(object_offset)

    def check_x_ref_stream_offset(self, start_x_ref_offset: int) -> bool:
        """Mirror of upstream ``checkXRefStreamOffset(long)``. Delegates to
        :meth:`COSParser.check_x_ref_stream_offset`."""
        return self._parser.check_x_ref_stream_offset(start_x_ref_offset)

    def validate_xref_offsets(
        self, xref_offset: dict[COSObjectKey, int] | None
    ) -> bool:
        """Mirror of upstream ``validateXrefOffsets(Map<COSObjectKey, Long>)``.
        Delegates to :meth:`COSParser.validate_xref_offsets`."""
        return self._parser.validate_xref_offsets(xref_offset)

    def check_xref_offsets(self) -> None:
        """Mirror of upstream ``checkXrefOffsets()``. Delegates to
        :meth:`COSParser.check_xref_offsets`."""
        self._parser.check_xref_offsets()

    def find_object_key(
        self,
        object_key: COSObjectKey,
        offset: int,
        xref_offset: dict[COSObjectKey, int],
    ) -> COSObjectKey | None:
        """Mirror of upstream
        ``findObjectKey(COSObjectKey, long, Map<COSObjectKey, Long>)``.
        Delegates to :meth:`COSParser.find_object_key`."""
        return self._parser.find_object_key(object_key, offset, xref_offset)

    def parse_start_xref(self) -> int:
        """Mirror of upstream ``parseStartXref()``. Delegates to
        :meth:`COSParser.parse_start_xref`."""
        return self._parser.parse_start_xref()

    def parse_xref_table(self, start_byte_offset: int) -> bool:
        """Mirror of upstream ``parseXrefTable(long)``. Delegates to
        :meth:`COSParser.parse_xref_table`."""
        return self._parser.parse_xref_table(start_byte_offset)
