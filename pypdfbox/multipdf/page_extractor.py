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

    Upstream delegates to ``Splitter`` configured with a single split
    boundary covering ``[startPage..endPage]``; we don't ship a ported
    ``Splitter`` yet, so this implementation walks the source page tree
    directly and deep-copies each page into a fresh ``PDDocument`` via
    :meth:`PDDocument.import_page` (which itself reuses the same deep-
    copy machinery as :class:`pypdfbox.multipdf.PDFCloneUtility`). After
    the page is imported the upstream-visible defensive setters
    (``set_media_box`` / ``set_crop_box`` / ``set_resources`` /
    ``set_rotation``) are re-applied so inheritable attributes that
    weren't materialised on the source page dict still land on the
    extracted page. Document information and viewer preferences are
    copied across as well, matching upstream byte-for-byte (see
    ``CHANGES.md`` for the deviation note about the Splitter delegation).

    Page numbers are **1-based and inclusive** at both ends, matching
    upstream:

    - ``startPage < 1``  -> clamped up to 1.
    - ``endPage > N``    -> clamped down to ``source.get_number_of_pages()``.
    - ``startPage > endPage`` (after clamping) -> returns an empty
      ``PDDocument``.
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
        clamped ``[start_page..end_page]`` range. Pages are deep-copied so
        the result owns its own resource graph, then the page setters
        upstream uses (``setMediaBox`` / ``setCropBox`` / ``setResources``
        / ``setRotation``) are re-applied so inheritable attributes
        survive the extraction. Document information and viewer
        preferences are copied across too."""
        # Local import to dodge an import cycle: ``pypdfbox.pdmodel``
        # transitively imports lots of submodules and we don't want
        # ``import pypdfbox.multipdf`` to drag the entire pdmodel surface
        # in at module-load time.
        from pypdfbox.pdmodel.pd_document import PDDocument

        # Degenerate range -- return a fresh empty document. Mirrors
        # upstream's ``if (endPage - startPage + 1 <= 0) return new
        # PDDocument();`` early-return.
        if self._end_page - self._start_page + 1 <= 0:
            return PDDocument()

        n = self._source_document.get_number_of_pages()
        start = max(self._start_page, 1)
        end = min(self._end_page, n)

        target = PDDocument()

        # Copy document information and viewer preferences -- upstream
        # does both before the page walk. Wrapped in best-effort try
        # blocks because the source may not have either populated and
        # neither is essential for a valid extracted document.
        self._copy_document_information(target)
        self._copy_viewer_preferences(target)

        # Walk every page so we mirror upstream's 1-based for-loop. The
        # upstream implementation iterates 1..N and only imports pages in
        # the [startPage..endPage] window; we do the same so that any
        # future per-page bookkeeping (e.g. struct-tree or annotation
        # remapping) has the full index context.
        for i in range(1, n + 1):
            if i < start or i > end:
                continue
            page = self._source_document.get_page(i - 1)
            imported = target.import_page(page)
            # Upstream re-applies the inheritable attributes via the
            # page setters so they materialise on the extracted page
            # dict even if the source had inherited them from a parent
            # node that didn't follow the extraction.
            try:
                imported.set_crop_box(page.get_crop_box())
            except Exception as exc:  # noqa: BLE001
                _LOG.debug("set_crop_box failed during extract: %s", exc)
            try:
                imported.set_media_box(page.get_media_box())
            except Exception as exc:  # noqa: BLE001
                _LOG.debug("set_media_box failed during extract: %s", exc)
            try:
                imported.set_resources(page.get_resources())
            except Exception as exc:  # noqa: BLE001
                _LOG.debug("set_resources failed during extract: %s", exc)
            try:
                imported.set_rotation(page.get_rotation())
            except Exception as exc:  # noqa: BLE001
                _LOG.debug("set_rotation failed during extract: %s", exc)
        return target

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
