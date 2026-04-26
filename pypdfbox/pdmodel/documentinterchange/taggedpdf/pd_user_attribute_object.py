from __future__ import annotations

from typing import Any

from pypdfbox.cos import (
    COSArray,
    COSBase,
    COSBoolean,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSString,
)

from .pd_standard_attribute_object import PDStandardAttributeObject


def _cos_to_py(value: COSBase | None) -> Any:
    """Best-effort scalar projection for /V values used in /P entries."""
    if value is None:
        return None
    if isinstance(value, COSBoolean):
        return value.value
    if isinstance(value, (COSInteger, COSFloat)):
        return value.value
    if isinstance(value, COSString):
        return value.get_string()
    if isinstance(value, COSName):
        return value.name
    return value


def _py_to_cos(value: Any) -> COSBase:
    """Inverse of ``_cos_to_py`` for accepted /V scalars."""
    if isinstance(value, COSBase):
        return value
    if isinstance(value, bool):
        return COSBoolean.get(value)
    if isinstance(value, int):
        return COSInteger.get(value)
    if isinstance(value, float):
        return COSFloat(value)
    if isinstance(value, str):
        return COSString(value)
    raise TypeError(f"Unsupported /V value type: {type(value).__name__}")


class PDUserAttributeObject(PDStandardAttributeObject):
    """
    A user-properties attribute object (``/O /UserProperties``). Mirrors
    PDFBox ``PDUserAttributeObject``.

    The lite surface returns/accepts ``/P`` entries as plain Python dicts
    (``{"N": str, "V": Any, "F": str | None, "H": bool}``) rather than the
    upstream ``PDUserProperty`` wrapper class — the wrapper plus
    structure-element change notification are deferred.
    """

    OWNER: str = "UserProperties"

    def __init__(self, dictionary: COSDictionary | None = None) -> None:
        super().__init__(dictionary)
        if dictionary is None:
            self.set_owner(self.OWNER)

    # ---------- /P ----------

    def get_property(self) -> list[dict[str, Any]]:
        v = self._dictionary.get_dictionary_object("P")
        if not isinstance(v, COSArray):
            return []
        out: list[dict[str, Any]] = []
        for i in range(v.size()):
            entry = v.get_object(i)
            if not isinstance(entry, COSDictionary):
                continue
            out.append(
                {
                    "N": entry.get_string("N"),
                    "V": _cos_to_py(entry.get_dictionary_object("V")),
                    "F": entry.get_string("F"),
                    "H": entry.get_boolean("H", False),
                }
            )
        return out

    def set_property(
        self,
        name: str,
        value: Any,
        format: str | None = None,
        hidden: bool = False,
    ) -> None:
        """Append a single user-property entry to ``/P``."""
        v = self._dictionary.get_dictionary_object("P")
        if isinstance(v, COSArray):
            array = v
        else:
            array = COSArray()
            self._dictionary.set_item("P", array)

        entry = COSDictionary()
        entry.set_string("N", name)
        entry.set_item("V", _py_to_cos(value))
        if format is not None:
            entry.set_string("F", format)
        if hidden:
            entry.set_boolean("H", True)
        array.add(entry)

    def __repr__(self) -> str:
        return (
            f"PDUserAttributeObject(O={self.get_owner()}, "
            f"properties={len(self.get_property())})"
        )


__all__ = ["PDUserAttributeObject"]
