"""Tree-view abstraction of a PDF document.

Ported from ``org.apache.pdfbox.debugger.ui.DocumentEntry``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .page_entry import PageEntry

if TYPE_CHECKING:
    from pypdfbox.pdmodel import PDDocument


class DocumentEntry:
    """Abstract view of a document in the tree view."""

    def __init__(self, doc: PDDocument, filename: str) -> None:
        self._doc = doc
        self._filename = filename

    def get_page_count(self) -> int:
        """Return the number of pages in the wrapped document."""
        return self._doc.get_pages().get_count()

    def get_page(self, index: int) -> PageEntry:
        """Build a :class:`PageEntry` for ``index`` (0-based)."""
        page = self._doc.get_pages().get(index)
        # ``PDFDebugger.getPageLabel`` returns ``None`` when labels aren't set;
        # the page-label module isn't required for headless tree-model use.
        page_label = _get_page_label(self._doc, index)
        return PageEntry(page.get_cos_object(), index + 1, page_label)

    def index_of(self, page: PageEntry) -> int:
        """Return the 0-based index of ``page`` in this document."""
        return page.get_page_num() - 1

    def to_string(self) -> str:
        """Return the upstream ``toString`` rendering — the wrapped filename."""
        return self._filename

    def __str__(self) -> str:
        return self.to_string()


def _get_page_label(doc: PDDocument, index: int) -> str | None:
    """Best-effort lookup of a PDF page-label for ``index``.

    Mirrors ``PDFDebugger.getPageLabel`` without forcing a dependency on the
    GUI entry point: returns ``None`` whenever the document has no label tree
    or the catalog can't be parsed.
    """

    try:
        catalog = doc.get_document_catalog()
        labels = catalog.get_page_labels()
        if labels is None:
            return None
        label_map = labels.get_labels_by_page_indices()
        # ``label_map`` may be a list (PDPageLabels) indexable by page number.
        if isinstance(label_map, list):
            if 0 <= index < len(label_map):
                return label_map[index]
            return None
        return label_map.get(index)
    except Exception:  # pragma: no cover - defensive, matches upstream nullability
        return None
