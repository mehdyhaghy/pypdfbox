from __future__ import annotations

from typing import Any

from pypdfbox.cos import (
    COSArray,
    COSBase,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSNull,
)

from .pd_destination import PDDestination


class PDPageDestination(PDDestination):
    """
    Base for explicit page destinations backed by a destination array.
    Mirrors PDFBox ``PDPageDestination``.
    """

    def __init__(self, array: COSArray | None = None) -> None:
        self._array = array if array is not None else COSArray()
        self._array.grow_to_size(2, COSNull.NULL)

    def get_cos_object(self) -> COSArray:
        return self._array

    def get_cos_array(self) -> COSArray:
        """Return the underlying ``COSArray``. Mirrors upstream
        ``PDPageDestination.getCOSArray()``."""
        return self._array

    def get_page(self) -> COSDictionary | None:
        page = self._array.get_object(0)
        return page if isinstance(page, COSDictionary) else None

    def set_page(self, page: Any) -> None:
        if page is None:
            self._array.set(0, COSNull.NULL)
            return
        if isinstance(page, COSBase):
            self._array.set(0, page)
            return
        # PDPage (or any wrapper exposing get_cos_object()).
        get_cos = getattr(page, "get_cos_object", None)
        if callable(get_cos):
            self._array.set(0, get_cos())
            return
        raise TypeError(f"Cannot set page from {type(page).__name__}")

    def get_page_number(self) -> int:
        page = self._array.get_object(0)
        if isinstance(page, COSInteger):
            return page.value
        return -1

    def set_page_number(self, page_number: int) -> None:
        self._array.set(0, COSInteger.get(page_number))

    # ---------- predicate helpers ----------

    def has_page(self) -> bool:
        """``True`` when ``/D[0]`` is a page ``COSDictionary`` (local destination)."""
        return isinstance(self._array.get_object(0), COSDictionary)

    def has_page_number(self) -> bool:
        """``True`` when ``/D[0]`` is a page-index ``COSInteger`` (remote destination)."""
        return isinstance(self._array.get_object(0), COSInteger)

    def find_page_number(self, document=None) -> int:
        """Return the 0-based destination page index.

        ``/D[0]`` may be an integer page index, a direct page dictionary, or
        an indirect object that resolves to either. Page-object destinations
        require a ``PDDocument`` or ``PDPageTree`` context and are matched by
        underlying COS dictionary identity. Returns ``-1`` when the page can't
        be located.
        """
        page = self._array.get_object(0)
        if isinstance(page, COSInteger):
            return page.value
        if isinstance(page, COSDictionary):
            pages = self._resolve_page_tree(document)
            if pages is not None:
                return pages.index_of(page)
        return -1

    def retrieve_page_number(self, document=None) -> int:
        """Return the 0-based page index regardless of whether ``/D[0]`` is a
        page integer or a page dictionary.

        Mirrors upstream ``PDPageDestination#retrievePageNumber()``: when
        ``document`` is ``None`` and ``/D[0]`` is a page dictionary, walks
        the page's ``/Parent`` (or ``/P``) chain up to the page-tree root
        and uses :class:`PDPageTree` to compute the index. When no chain
        is found or the resolved root isn't a ``/Type /Pages`` node,
        returns ``-1``. When ``document`` is supplied, delegates to
        :meth:`find_page_number` for the document-rooted lookup.
        """
        if document is not None:
            return self.find_page_number(document)
        page = self._array.get_object(0)
        if isinstance(page, COSInteger):
            return page.value
        if not isinstance(page, COSDictionary):
            return -1
        # Walk /Parent (or /P) until we find a /Type /Pages root.
        parent_key = COSName.PARENT  # type: ignore[attr-defined]
        p_key = COSName.get_pdf_name("P")
        type_key = COSName.TYPE  # type: ignore[attr-defined]
        kids_key = COSName.KIDS  # type: ignore[attr-defined]
        pages_name = COSName.PAGES  # type: ignore[attr-defined]
        seen: set[int] = set()
        current = page
        while True:
            if id(current) in seen:
                # Cycle guard — bail safely.
                return -1
            seen.add(id(current))
            nxt = current.get_dictionary_object(parent_key)
            if not isinstance(nxt, COSDictionary):
                nxt = current.get_dictionary_object(p_key)
            if not isinstance(nxt, COSDictionary):
                break
            current = nxt
        # ``current`` is now the highest ancestor.
        if not isinstance(current.get_dictionary_object(kids_key), COSArray):
            return -1
        type_value = current.get_dictionary_object(type_key)
        if not (isinstance(type_value, COSName) and type_value == pages_name):
            return -1
        from pypdfbox.pdmodel.pd_page_tree import PDPageTree

        return PDPageTree(current).index_of(page)

    @staticmethod
    def _resolve_page_tree(context: Any) -> Any:
        if context is None:
            return None
        if hasattr(context, "index_of"):
            return context
        if hasattr(context, "get_pages"):
            return context.get_pages()
        return None

    def get_type(self) -> str | None:
        return self._array.get_name(1)

    def _set_type(self, type_name: str) -> None:
        self._array.set(1, COSName.get_pdf_name(type_name))

    def _get_float(self, index: int) -> float | None:
        value = self._array.get_object(index) if index < self._array.size() else None
        if isinstance(value, (COSInteger, COSFloat)):
            return float(value.value)
        return None

    def _set_float(self, index: int, value: float | None) -> None:
        self._array.grow_to_size(index + 1, COSNull.NULL)
        self._array.set(index, COSFloat(value) if value is not None else COSNull.NULL)

__all__ = ["PDPageDestination"]
