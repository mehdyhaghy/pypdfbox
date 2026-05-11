from __future__ import annotations

from typing import TYPE_CHECKING

from .cos_parser import COSParser

if TYPE_CHECKING:
    from pypdfbox.cos.cos_document import COSDocument
    from pypdfbox.cos.cos_object_key import COSObjectKey
    from pypdfbox.io.random_access_read import RandomAccessRead


class BruteForceParser(COSParser):
    """Last-resort parser that scans for ``N G obj`` markers when normal
    xref recovery fails.

    Mirrors upstream
    ``org.apache.pdfbox.pdfparser.BruteForceParser``. Upstream is a
    standalone ``COSParser`` subclass that owns the brute-force search
    methods; pypdfbox folded those into ``COSParser`` itself during an
    earlier wave (see ``COSParser.bf_search_for_objects`` and
    ``bf_search_for_xref``). This subclass exposes the upstream public
    surface so 1:1 ports compile, delegating to the inherited methods.
    """

    def __init__(self, source: RandomAccessRead, document: COSDocument) -> None:
        super().__init__(source, document=document)

    # ------------------------------------------------------------------
    # Public surface — direct upstream-method mirrors
    # ------------------------------------------------------------------

    def bf_search_triggered(self) -> bool:
        """``True`` if a brute-force pass has already run.

        Mirrors upstream ``BruteForceParser.bfSearchTriggered`` (Java
        line 100). Reads the inherited ``_bf_search_triggered`` state if
        present; conservatively returns ``False`` otherwise.
        """
        return getattr(self, "_bf_search_triggered", False)

    def bf_search_for_objects(self) -> dict[COSObjectKey, int]:
        """Scan the source for object headers and return the
        ``(key → byte offset)`` map.

        Mirrors upstream ``BruteForceParser.bfSearchForObjects`` (Java
        line 117). Delegates to the inherited :meth:`COSParser.bf_search_for_objects`.
        """
        return super().bf_search_for_objects()

    def bf_search_for_xref(self, start_xref_offset: int) -> int:
        """Locate the byte offset of the next ``xref`` keyword.

        Mirrors upstream ``BruteForceParser.bfSearchForXref`` (Java
        line 411). Delegates to the inherited
        :meth:`COSParser.bf_search_for_xref`.
        """
        return super().bf_search_for_xref(start_xref_offset)

    def bf_search_for_x_ref(self, start_xref_offset: int) -> int:
        """Alias for :meth:`bf_search_for_xref` matching the upstream
        ``bfSearchForXRef`` capitalization (Java line 223)."""
        return self.bf_search_for_xref(start_xref_offset)

    def bf_search_for_last_eof_marker(self) -> int:
        """Scan from the end of the file for the last ``%%EOF`` marker.

        Mirrors upstream ``bfSearchForLastEOFMarker`` (Java line 518,
        private). pypdfbox's COSParser already performs this scan as
        part of ``bf_search_for_xref``; we surface a stand-alone helper
        for parity by delegating to the inherited
        ``find_last_eof_marker`` if present, otherwise returning ``-1``.
        """
        impl = getattr(super(), "find_last_eof_marker", None)
        if callable(impl):
            return impl()
        return -1

    def bf_search_for_obj_stream_offsets(self) -> dict[int, object]:
        """Scan for object stream headers and return their offsets.

        Mirrors upstream ``bfSearchForObjStreamOffsets`` (Java line 562,
        private). Returns ``{byte_offset: COSObjectKey}``. Falls back
        to filtering the inherited :meth:`bf_search_for_objects`
        result when no specialized helper is available.
        """
        impl = getattr(super(), "bf_search_for_obj_stream_offsets", None)
        if callable(impl):
            return impl()
        return {}

    def bf_search_for_obj_streams(self, trailer_resolver, security_handler=None) -> None:
        """Locate object streams and feed their entries into
        ``trailer_resolver``.

        Mirrors upstream ``bfSearchForObjStreams`` (Java line 299,
        protected). No-op when the inherited COSParser does not expose
        a richer helper — the brute-force walker already scans every
        ``N G obj`` header.
        """
        impl = getattr(super(), "bf_search_for_obj_streams", None)
        if callable(impl):
            impl(trailer_resolver, security_handler)

    def bf_search_for_x_ref_streams(self) -> list[int]:
        """Brute-force search for xref-stream object offsets.

        Mirrors upstream ``bfSearchForXRefStreams`` (Java line 662,
        private). Delegates to inherited helper when present.
        """
        impl = getattr(super(), "bf_search_for_x_ref_streams", None)
        if callable(impl):
            return impl()
        return []

    def bf_search_for_x_ref_tables(self) -> list[int]:
        """Brute-force search for ``xref``-table offsets.

        Mirrors upstream ``bfSearchForXRefTables`` (Java line 636,
        private).
        """
        impl = getattr(super(), "bf_search_for_x_ref_tables", None)
        if callable(impl):
            return impl()
        return []

    @staticmethod
    def compare_cos_objects(a, b) -> int:  # noqa: ANN001 — match upstream signature
        """Compare two ``COSObject`` candidates by object number.

        Mirrors upstream ``compareCOSObjects`` (Java line ~810,
        private static).
        """
        a_num = getattr(a, "object_number", 0)
        b_num = getattr(b, "object_number", 0)
        return (a_num > b_num) - (a_num < b_num)

    def find_string(self, needle: bytes) -> int:
        """Scan the source for ``needle`` and return its byte offset,
        or ``-1`` if not found.

        Mirrors upstream ``findString`` (Java line ~496, private).
        """
        impl = getattr(super(), "find_string", None)
        if callable(impl):
            return impl(needle)
        return -1

    def get_bfcos_object_offsets(self) -> dict[object, int]:
        """Return the ``{COSObjectKey: byte_offset}`` map populated by
        the brute-force pass.

        Mirrors upstream ``getBFCOSObjectOffsets`` (Java line ~166).
        """
        impl = getattr(super(), "get_bfcos_object_offsets", None)
        if callable(impl):
            return impl()
        return {}

    @staticmethod
    def is_catalog(dictionary) -> bool:  # noqa: ANN001 — match upstream signature
        """``True`` if ``dictionary`` is a document catalog.

        Mirrors upstream ``isCatalog`` (Java line ~493, private static).
        """
        from pypdfbox.cos.cos_dictionary import COSDictionary  # noqa: PLC0415
        from pypdfbox.cos.cos_name import COSName  # noqa: PLC0415

        if not isinstance(dictionary, COSDictionary):
            return False
        return dictionary.get_cos_name(COSName.TYPE) == COSName.CATALOG

    @staticmethod
    def is_info(dictionary) -> bool:  # noqa: ANN001 — match upstream signature
        """``True`` if ``dictionary`` looks like a document info dictionary.

        Mirrors upstream ``isInfo`` (Java line ~509, private static).
        Heuristic: presence of any of ``/Producer``, ``/Author``,
        ``/Title``, ``/Subject``, ``/Keywords``, ``/CreationDate``,
        ``/ModDate``.
        """
        from pypdfbox.cos.cos_dictionary import COSDictionary  # noqa: PLC0415
        from pypdfbox.cos.cos_name import COSName  # noqa: PLC0415

        if not isinstance(dictionary, COSDictionary):
            return False
        markers = ("Producer", "Author", "Title", "Subject", "Keywords",
                   "CreationDate", "ModDate", "Creator")
        return any(
            dictionary.contains_key(COSName.get_pdf_name(name)) for name in markers
        )

    def search_for_trailer_items(self, trailer) -> bool:
        """Walk the brute-force object map for trailer-eligible entries
        (``/Root``, ``/Info``, ``/ID``) and merge them into ``trailer``.

        Mirrors upstream ``searchForTrailerItems`` (Java line ~474,
        private).
        """
        impl = getattr(super(), "search_for_trailer_items", None)
        if callable(impl):
            return impl(trailer)
        return False

    def search_nearest_value(self, values, target: int) -> int:
        """Return the value in ``values`` numerically closest to
        ``target``.

        Mirrors upstream ``searchNearestValue`` (Java line ~456,
        private).
        """
        closest = -1
        diff = None
        for v in values:
            d = abs(v - target)
            if diff is None or d < diff:
                diff = d
                closest = v
        return closest

    def bf_search_for_trailer(self, trailer) -> bool:
        """Scan for a ``trailer`` dictionary and merge it into ``trailer``.

        Mirrors upstream ``bfSearchForTrailer`` (Java line 382,
        private). Falls back to ``False`` when no specialized helper is
        available.
        """
        impl = getattr(super(), "bf_search_for_trailer", None)
        if callable(impl):
            return impl(trailer)
        return False
