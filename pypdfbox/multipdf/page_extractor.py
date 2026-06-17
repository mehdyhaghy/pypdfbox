from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pypdfbox.pdmodel.pd_document import PDDocument


_LOG = logging.getLogger(__name__)


class PageExtractor:
    """Extract one or more sequential pages and create a new
    :class:`PDDocument`. Mirrors
    ``org.apache.pdfbox.multipdf.PageExtractor``.

    Upstream delegates to :class:`Splitter` configured with a single split
    boundary covering ``[startPage..endPage]``, and so does this port now
    that :class:`Splitter` is fully ported (the earlier bespoke page-walk
    was a stop-gap while the ported ``Splitter`` did not yet exist — an
    earlier closed deferral). The extracted
    document therefore inherits all of Splitter's per-page behaviour:
    annotation cloning, ``/B`` bead removal, structure-tree clone,
    cross-chunk destination fix-up, and inherited page-geometry
    materialisation (``/MediaBox`` / ``/CropBox`` / ``/Rotate``).
    Document information and viewer preferences are carried across by
    Splitter's :meth:`Splitter.create_new_document`.

    Page numbers are **1-based and inclusive** at both ends, matching
    upstream:

    - ``startPage < 1``  -> clamped up to 1.
    - ``endPage > N``    -> clamped down to ``source.get_number_of_pages()``.
    - ``endPage - startPage + 1 <= 0`` (raw, pre-clamp) -> returns an
      empty ``PDDocument``.
    - a range entirely past the end of the document (``max(start, 1)`` >
      ``min(end, N)``) -> raises ``ValueError`` via Splitter's
      :meth:`Splitter.set_end_page` guard, mirroring upstream's
      ``IllegalArgumentException``.

    The :meth:`_copy_document_information` / :meth:`_copy_viewer_preferences`
    helpers are retained as no-longer-internally-called compatibility
    shims (Splitter now performs the copy); they remain available for
    callers / tests that invoked them directly.
    """

    def __init__(
        self,
        source_document: PDDocument,
        start_page: int = 1,
        end_page: int | None = None,
    ) -> None:
        self._source_document = source_document
        self._start_page = start_page
        # ``end_page=None`` mirrors upstream's no-arg constructor which sets
        # ``endPage = sourceDocument.getNumberOfPages()``.
        self._end_page = (
            source_document.get_number_of_pages() if end_page is None else end_page
        )

    # ---------- accessors (mirror upstream getters/setters) ----------

    def get_start_page(self) -> int:
        return self._start_page

    def set_start_page(self, start_page: int) -> None:
        self._start_page = start_page

    def get_end_page(self) -> int:
        return self._end_page

    def set_end_page(self, end_page: int) -> None:
        self._end_page = end_page

    # ---------- core ----------

    def extract(self) -> PDDocument:
        """Build and return a new :class:`PDDocument` containing the
        ``[start_page..end_page]`` range (1-based, inclusive on both ends).

        Mirrors upstream ``PageExtractor.extract`` **exactly**, including
        its delegation to :class:`Splitter`::

            if (endPage - startPage + 1 <= 0) return new PDDocument();
            Splitter splitter = new Splitter();
            splitter.setStartPage(Math.max(startPage, 1));
            splitter.setEndPage(Math.min(endPage, source.getNumberOfPages()));
            splitter.setSplitAtPage(getEndPage() - getStartPage() + 1);
            return splitter.split(sourceDocument).get(0);

        Earlier on, the page walk was re-implemented directly (the ported
        :class:`Splitter` did not exist yet — a previously-closed
        deferral). Now that :class:`Splitter` is a
        full port, delegating restores byte-for-byte parity: the extracted
        document inherits Splitter's annotation cloning, ``/B`` bead
        removal, structure-tree clone, destination fix-up, and
        inherited-attribute materialisation rather than the partial subset
        the bespoke walk re-applied. It also restores upstream's edge-case
        contract: an out-of-document range where ``max(start, 1)`` exceeds
        ``min(end, N)`` now raises (Splitter's ``set_end_page`` rejects
        ``end < start_page`` -> ``ValueError``, the Python analogue of
        Java's ``IllegalArgumentException``) instead of silently returning
        an empty document.
        """
        # Local import to dodge an import cycle: ``pypdfbox.pdmodel``
        # transitively imports lots of submodules and we don't want
        # ``import pypdfbox.multipdf`` to drag the entire pdmodel surface
        # in at module-load time.
        from pypdfbox.multipdf.splitter import Splitter
        from pypdfbox.pdmodel.pd_document import PDDocument

        # Degenerate range -- return a fresh empty document. Mirrors
        # upstream's ``if (endPage - startPage + 1 <= 0) return new
        # PDDocument();`` early-return (uses the RAW, unclamped bounds).
        if self._end_page - self._start_page + 1 <= 0:
            return PDDocument()

        n = self._source_document.get_number_of_pages()
        splitter = Splitter()
        splitter.set_start_page(max(self._start_page, 1))
        splitter.set_end_page(min(self._end_page, n))
        # Upstream feeds the RAW (pre-clamp) span to setSplitAtPage so the
        # whole clamped window lands in a single destination document.
        splitter.set_split_at_page(self._end_page - self._start_page + 1)
        split = splitter.split(self._source_document)
        return split[0]

    # ---------- helpers ----------

    def _copy_document_information(self, target: PDDocument) -> None:
        """Best-effort copy of the source ``/Info`` dictionary onto
        ``target``. Mirrors upstream's
        ``extractedDocument.setDocumentInformation(sourceDocument.
        getDocumentInformation())`` — failures are swallowed because
        an extracted document without /Info is still well-formed."""
        try:
            info = self._source_document.get_document_information()
        except Exception as exc:  # noqa: BLE001
            _LOG.debug("get_document_information failed: %s", exc)
            return
        if info is None:
            return
        try:
            target.set_document_information(info)
        except Exception as exc:  # noqa: BLE001
            _LOG.debug("set_document_information failed: %s", exc)

    def _copy_viewer_preferences(self, target: PDDocument) -> None:
        """Best-effort copy of the source catalog's ``/ViewerPreferences``
        onto ``target``'s catalog. Mirrors upstream's
        ``extractedDocument.getDocumentCatalog().setViewerPreferences(
        sourceDocument.getDocumentCatalog().getViewerPreferences())``."""
        try:
            src_catalog = self._source_document.get_document_catalog()
            dst_catalog = target.get_document_catalog()
        except Exception as exc:  # noqa: BLE001
            _LOG.debug("get_document_catalog failed: %s", exc)
            return
        try:
            prefs = src_catalog.get_viewer_preferences()
        except Exception as exc:  # noqa: BLE001
            _LOG.debug("get_viewer_preferences failed: %s", exc)
            return
        if prefs is None:
            return
        try:
            dst_catalog.set_viewer_preferences(prefs)
        except Exception as exc:  # noqa: BLE001
            _LOG.debug("set_viewer_preferences failed: %s", exc)


__all__ = ["PageExtractor"]
