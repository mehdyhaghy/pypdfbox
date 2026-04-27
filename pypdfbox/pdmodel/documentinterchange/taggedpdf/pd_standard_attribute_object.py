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

    # ---------- public typed helpers (PDFBox parity) ----------
    #
    # Mirror the protected ``getXxx``/``setXxx`` helpers on upstream
    # ``PDStandardAttributeObject``. The legacy ``_get_*`` / ``_set_*``
    # variants above remain unchanged for the existing typed subclasses.
    # These public wrappers add the PDFBox-style "set to default removes
    # the key" semantics for the value-typed setters.

    def has_attribute(self, name: str) -> bool:
        """Return ``True`` if ``name`` is present in the underlying dictionary."""
        return self._dictionary.get_dictionary_object(name) is not None

    def remove_attribute(self, name: str) -> None:
        """Remove ``name`` from the underlying dictionary if present."""
        self._dictionary.remove_item(name)

    # ---- string ----

    def get_string(self, name: str, default: str | None = None) -> str | None:
        value = self._dictionary.get_string(name)
        return value if value is not None else default

    def set_string(
        self, name: str, value: str | None, default: str | None = None
    ) -> None:
        if value is None or value == default:
            self._dictionary.remove_item(name)
        else:
            self._dictionary.set_string(name, value)

    # ---- name ----

    def get_name(self, name: str, default: str | None = None) -> str | None:
        return self._dictionary.get_name(name, default)

    def set_name(
        self, name: str, value: str | None, default: str | None = None
    ) -> None:
        if value is None or value == default:
            self._dictionary.remove_item(name)
        else:
            self._dictionary.set_name(name, value)

    # ---- integer / number ----

    def get_integer(self, name: str, default: int = 0) -> int:
        return self._dictionary.get_int(name, default)

    def set_integer(self, name: str, value: int, default: int = 0) -> None:
        if value == default:
            self._dictionary.remove_item(name)
        else:
            self._dictionary.set_int(name, value)

    def get_number(self, name: str, default: float = 0.0) -> float:
        return self._dictionary.get_float(name, default)

    def set_number(
        self, name: str, value: float | int, default: float = 0.0
    ) -> None:
        if float(value) == float(default):
            self._dictionary.remove_item(name)
        elif isinstance(value, int) and not isinstance(value, bool):
            self._dictionary.set_int(name, value)
        else:
            self._dictionary.set_float(name, float(value))

    # ---- arrays ----

    def get_array_of_string(self, name: str) -> list[str] | None:
        return self._get_array_of_string(name)

    def set_array_of_string(self, name: str, values: list[str] | None) -> None:
        if values is None:
            self._dictionary.remove_item(name)
        else:
            self._set_array_of_string(name, values)

    def get_array_of_name(self, name: str) -> list[str] | None:
        # Same shape as get_array_of_string but only collects COSName entries.
        v = self._dictionary.get_dictionary_object(name)
        if not isinstance(v, COSArray):
            return None
        out: list[str] = []
        for index in range(v.size()):
            item = v.get_object(index)
            if isinstance(item, COSName):
                out.append(item.name)
        return out

    def set_array_of_name(self, name: str, values: list[str] | None) -> None:
        if values is None:
            self._dictionary.remove_item(name)
        else:
            self._set_array_of_name(name, values)

    # ---- single-color and color-or-four-colours ----

    def get_color(self, name: str) -> tuple[float, ...] | None:
        return self._get_color_value(name)

    def set_color(self, name: str, rgb: tuple[float, ...] | None) -> None:
        self._set_color_value(name, rgb)

    def get_color_or_four_colors(
        self, name: str
    ) -> tuple[float, ...] | PDFourColours | None:
        v = self._dictionary.get_dictionary_object(name)
        if not isinstance(v, COSArray):
            return None
        if v.size() == 3:
            return self._get_color_value(name)
        if v.size() == 4:
            return PDFourColours(v)
        return None

    # ---- polymorphic name/number combinators ----

    def get_name_or_array_of_name(
        self, name: str, default: str | None = None
    ) -> str | list[str] | None:
        v = self._dictionary.get_dictionary_object(name)
        if isinstance(v, COSArray):
            out: list[str] = []
            for index in range(v.size()):
                item = v.get_object(index)
                if isinstance(item, COSName):
                    out.append(item.name)
            return out
        if isinstance(v, COSName):
            return v.name
        return default

    def get_number_or_array_of_number(
        self, name: str, default: float | None = None
    ) -> float | list[float] | None:
        v = self._dictionary.get_dictionary_object(name)
        if isinstance(v, COSArray):
            out: list[float] = []
            for index in range(v.size()):
                item = v.get_object(index)
                if isinstance(item, (COSInteger, COSFloat)):
                    out.append(float(item.value))
            return out
        if isinstance(v, (COSInteger, COSFloat)):
            return float(v.value)
        if default is None or default == self.UNSPECIFIED:
            return None
        return default

    def get_number_or_name(
        self, name: str, default: str | None = None
    ) -> float | str | None:
        v = self._dictionary.get_dictionary_object(name)
        if isinstance(v, (COSInteger, COSFloat)):
            return float(v.value)
        if isinstance(v, COSName):
            return v.name
        return default


__all__ = ["PDStandardAttributeObject"]
