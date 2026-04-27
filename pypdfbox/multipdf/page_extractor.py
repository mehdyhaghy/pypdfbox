from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pypdfbox.pdmodel.pd_document import PDDocument


class PageExtractor:
    """Extract one or more sequential pages and create a new
    :class:`PDDocument`. Mirrors
    ``org.apache.pdfbox.multipdf.PageExtractor``.

    Upstream delegates to ``Splitter`` configured with a single split
    boundary covering ``[startPage..endPage]``; we don't ship a ported
    ``Splitter`` yet, so this implementation walks the source page tree
    directly and deep-copies each page into a fresh ``PDDocument`` via
    :meth:`PDDocument.import_page`. The user-visible contract — page
    counts, clamping rules, and the "blank doc when range is degenerate"
    behaviour — matches upstream byte-for-byte (see ``CHANGES.md`` for the
    deviation note).

    Page numbers are **1-based and inclusive** at both ends, matching
    upstream:

    - ``startPage < 1``  → clamped up to 1.
    - ``endPage > N``    → clamped down to ``source.get_number_of_pages()``.
    - ``startPage > endPage`` (after clamping) → returns an empty
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
        the result owns its own resource graph."""
        # Local import to dodge an import cycle: ``pypdfbox.pdmodel``
        # transitively imports lots of submodules and we don't want
        # ``import pypdfbox.multipdf`` to drag the entire pdmodel surface
        # in at module-load time.
        from pypdfbox.pdmodel.pd_document import PDDocument

        # Degenerate range — return a fresh empty document. Mirrors
        # upstream's ``if (endPage - startPage + 1 <= 0) return new
        # PDDocument();`` early-return.
        if self._end_page - self._start_page + 1 <= 0:
            return PDDocument()

        n = self._source_document.get_number_of_pages()
        start = max(self._start_page, 1)
        end = min(self._end_page, n)

        target = PDDocument()
        # Convert from 1-based inclusive to 0-based half-open for the
        # source-side index walk.
        for idx in range(start - 1, end):
            page = self._source_document.get_page(idx)
            target.import_page(page)
        return target


__all__ = ["PageExtractor"]
