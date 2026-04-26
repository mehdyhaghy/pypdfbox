from __future__ import annotations

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

    def get_page(self) -> COSDictionary | None:
        page = self._array.get_object(0)
        return page if isinstance(page, COSDictionary) else None

    def set_page(self, page: COSBase | None) -> None:
        self._array.set(0, page if page is not None else COSNull.NULL)

    def get_page_number(self) -> int:
        page = self._array.get_object(0)
        if isinstance(page, COSInteger):
            return page.value
        return -1

    def set_page_number(self, page_number: int) -> None:
        self._array.set(0, COSInteger.get(page_number))

    def find_page_number(self, document=None) -> int:
        """0-based page index when /D[0] is a COSInteger; otherwise resolves
        /D[0] (a Page dict ref) against ``document``'s page tree by identity.
        Returns ``-1`` when ``/D[0]`` is a Page ref but no document is supplied
        or the page can't be located.
        """
        page = self._array.get_object(0)
        if isinstance(page, COSInteger):
            return page.value
        if isinstance(page, COSDictionary) and document is not None:
            from pypdfbox.pdmodel.pd_page import PDPage
            return document.get_pages().index_of(PDPage(page))
        return -1

    def retrieve_page_number(self, document=None) -> int:
        return self.find_page_number(document)

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
