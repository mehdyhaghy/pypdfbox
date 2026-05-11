from __future__ import annotations

from collections import deque
from collections.abc import Iterator
from typing import TYPE_CHECKING

from pypdfbox.cos import COSArray, COSDictionary, COSName

if TYPE_CHECKING:
    from .pd_document import PDDocument
    from .pd_page import PDPage


_TYPE: COSName = COSName.get_pdf_name("Type")
_PAGE: COSName = COSName.get_pdf_name("Page")
_KIDS: COSName = COSName.get_pdf_name("Kids")
_PAGES: COSName = COSName.get_pdf_name("Pages")


class PageIterator(Iterator["PDPage"]):
    """Iterator walking every leaf page in a page tree, in document order.

    Mirrors the private ``PDPageTree.PageIterator`` inner class (Java
    lines 192-263). Implemented with a queue that is filled at
    construction time by walking the tree; recursion is bounded by a
    ``seen`` set so malformed PDFs with circular ``/Kids`` references don't
    blow the stack (PDFBOX-5009, PDFBOX-3953).
    """

    def __init__(
        self,
        node: COSDictionary,
        document: PDDocument | None = None,
    ) -> None:
        self._document: PDDocument | None = document
        self._queue: deque[COSDictionary] = deque()
        self._seen: set[int] = set()
        self.enqueue_kids(node)
        self._seen.clear()  # release memory; not needed after the walk

    # ---------- internal helpers ----------

    def enqueue_kids(self, node: COSDictionary | None) -> None:
        if self._is_page_tree_node(node):
            assert node is not None
            kids = node.get_dictionary_object(_KIDS)
            if isinstance(kids, COSArray):
                for i in range(kids.size()):
                    kid = kids.get_object(i)
                    if not isinstance(kid, COSDictionary):
                        continue
                    if id(kid) in self._seen:
                        # PDFBOX-5009 / PDFBOX-3953: drop the duplicate edge.
                        continue
                    if kid.contains_key(_KIDS):
                        self._seen.add(id(kid))
                    self.enqueue_kids(kid)
        elif node is not None:
            type_name = node.get_dictionary_object(_TYPE)
            if isinstance(type_name, COSName) and type_name == _PAGE:
                self._queue.append(node)
            elif type_name is None and not node.contains_key(_KIDS):
                # No /Type but leaf-shaped — treat as a page (PDFBox is
                # lenient here; matches the broader pypdfbox treatment).
                self._queue.append(node)

    @staticmethod
    def _is_page_tree_node(node: COSDictionary | None) -> bool:
        if node is None:
            return False
        type_name = node.get_dictionary_object(_TYPE)
        if isinstance(type_name, COSName) and type_name == _PAGES:
            return True
        return node.contains_key(_KIDS)

    # ---------- iterator protocol ----------

    def has_next(self) -> bool:
        """Java-style alias — ``True`` when :meth:`__next__` will yield."""
        return bool(self._queue)

    def __iter__(self) -> PageIterator:
        return self

    def __next__(self) -> PDPage:
        if not self._queue:
            raise StopIteration
        # Local import to avoid a cycle (PDPage imports from pdmodel).
        from .pd_page import PDPage  # noqa: PLC0415

        cos_page = self._queue.popleft()
        # Sanitize the /Type entry — match upstream's repair logic.
        type_name = cos_page.get_dictionary_object(_TYPE)
        if type_name is None:
            cos_page.set_item(_TYPE, _PAGE)
        elif isinstance(type_name, COSName) and type_name != _PAGE:
            raise RuntimeError(f"Expected 'Page' but found {type_name}")
        resource_cache = (
            self._document.get_resource_cache()
            if self._document is not None
            and hasattr(self._document, "get_resource_cache")
            else None
        )
        return PDPage(cos_page, resource_cache=resource_cache)

    def next(self) -> PDPage:
        """Java-style alias for :meth:`__next__`."""
        return self.__next__()

    def remove(self) -> None:
        """Always raises — mirrors upstream's
        ``UnsupportedOperationException`` (Java line 261)."""
        raise NotImplementedError(
            "PageIterator.remove() is not supported"
        )


__all__ = ["PageIterator"]
