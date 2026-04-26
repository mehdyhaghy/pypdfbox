from __future__ import annotations

from pypdfbox.cos import (
    COSArray,
    COSBase,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSString,
)
from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_attribute_object import (
    PDAttributeObject,
)

from .pd_four_colours import PDFourColours


class PDStandardAttributeObject(PDAttributeObject):
    """
    Abstract intermediate base for the seven owner-typed standard attribute
    objects defined in PDF 32000-1:2008 §14.8.5. Mirrors PDFBox
    ``PDStandardAttributeObject``.

    Provides typed ``_get_*`` / ``_set_*`` helpers used by the concrete
    subclasses. The PDFBox change-notification plumbing (``potentiallyNotifyChanged``)
    is deferred — setters mutate the dictionary directly.
    """

    UNSPECIFIED: float = -1.0

    def __init__(self, dictionary: COSDictionary | None = None) -> None:
        super().__init__(dictionary)

    # ---------- presence ----------

    def is_specified(self, name: str) -> bool:
        return self._dictionary.get_dictionary_object(name) is not None

    # ---------- string ----------

    def _get_string(self, name: str) -> str | None:
        return self._dictionary.get_string(name)

    def _set_string(self, name: str, value: str | None) -> None:
        if value is None:
            self._dictionary.remove_item(name)
        else:
            self._dictionary.set_string(name, value)

    # ---------- name ----------

    def _get_name(self, name: str, default: str | None = None) -> str | None:
        return self._dictionary.get_name(name, default)

    def _set_name(self, name: str, value: str | None) -> None:
        if value is None:
            self._dictionary.remove_item(name)
        else:
            self._dictionary.set_name(name, value)

    # ---------- integer / float ----------

    def _get_integer(self, name: str, default: int = -1) -> int:
        return self._dictionary.get_int(name, default)

    def _set_integer(self, name: str, value: int) -> None:
        self._dictionary.set_int(name, value)

    def _get_number(self, name: str, default: float = -1.0) -> float:
        return self._dictionary.get_float(name, default)

    def _set_number(self, name: str, value: float | int) -> None:
        if isinstance(value, int) and not isinstance(value, bool):
            self._dictionary.set_int(name, value)
        else:
            self._dictionary.set_float(name, float(value))

    # ---------- arrays ----------

    def _get_array(self, name: str) -> COSArray | None:
        v = self._dictionary.get_dictionary_object(name)
        if isinstance(v, COSArray):
            return v
        return None

    def _get_array_of_string(self, name: str) -> list[str] | None:
        v = self._dictionary.get_dictionary_object(name)
        if not isinstance(v, COSArray):
            return None
        out: list[str] = []
        for i in range(v.size()):
            item = v.get_object(i)
            if isinstance(item, COSName):
                out.append(item.name)
            elif isinstance(item, COSString):
                out.append(item.get_string())
        return out

    def _set_array_of_string(self, name: str, values: list[str]) -> None:
        array = COSArray()
        for value in values:
            array.add(COSString(value))
        self._dictionary.set_item(name, array)

    def _set_array_of_name(self, name: str, values: list[str]) -> None:
        array = COSArray()
        for value in values:
            array.add(COSName.get_pdf_name(value))
        self._dictionary.set_item(name, array)

    def _get_array_of_number(self, name: str) -> list[float] | None:
        v = self._dictionary.get_dictionary_object(name)
        if not isinstance(v, COSArray):
            return None
        out: list[float] = []
        for i in range(v.size()):
            item = v.get_object(i)
            if isinstance(item, (COSInteger, COSFloat)):
                out.append(float(item.value))
        return out

    def _set_array_of_number(self, name: str, values: list[float]) -> None:
        array = COSArray()
        for value in values:
            array.add(COSFloat(float(value)))
        self._dictionary.set_item(name, array)

    # ---------- color (single RGB / N-component) ----------

    def _get_color_value(self, key: COSName | str) -> tuple[float, ...] | None:
        v = self._dictionary.get_dictionary_object(key)
        if not isinstance(v, COSArray):
            return None
        out: list[float] = []
        for index in range(v.size()):
            item = v.get_object(index)
            if not isinstance(item, (COSInteger, COSFloat)):
                return None
            out.append(float(item.value))
        return tuple(out)

    def _set_color_value(
        self, key: COSName | str, rgb: tuple[float, ...] | None
    ) -> None:
        if rgb is None:
            self._dictionary.remove_item(key)
            return
        array = COSArray()
        for component in rgb:
            array.add(COSFloat(float(component)))
        self._dictionary.set_item(key, array)

    # ---------- four-side color (e.g. /BorderColor) ----------

    def _get_four_colours(self, key: COSName | str) -> PDFourColours | None:
        v = self._dictionary.get_dictionary_object(key)
        if not isinstance(v, COSArray):
            return None
        return PDFourColours(v)

    def _set_four_colours(
        self, key: COSName | str, four: PDFourColours | None
    ) -> None:
        if four is None:
            self._dictionary.remove_item(key)
        else:
            self._dictionary.set_item(key, four.get_cos_array())

    # ---------- gamma ----------

    def _get_gamma(self, key: COSName | str) -> float | None:
        v = self._dictionary.get_dictionary_object(key)
        if isinstance(v, (COSInteger, COSFloat)):
            return float(v.value)
        return None

    def _set_gamma(self, key: COSName | str, gamma: float | None) -> None:
        if gamma is None:
            self._dictionary.remove_item(key)
        else:
            self._dictionary.set_float(key, float(gamma))

    # ---------- raw item passthrough ----------

    def _get_item(self, name: str) -> COSBase | None:
        return self._dictionary.get_dictionary_object(name)

    def _set_item(self, name: str, value: COSBase | None) -> None:
        if value is None:
            self._dictionary.remove_item(name)
        else:
            self._dictionary.set_item(name, value)


__all__ = ["PDStandardAttributeObject"]
