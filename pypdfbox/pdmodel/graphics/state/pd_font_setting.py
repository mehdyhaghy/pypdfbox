from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.cos import (
    COSArray,
    COSBase,
    COSDictionary,
    COSFloat,
    COSNull,
    COSNumber,
)

if TYPE_CHECKING:
    from pypdfbox.pdmodel.font.pd_font import PDFont


class PDFontSetting:
    """A font setting used by an ExtGState — the ``/Font`` entry of an
    extended graphics state dictionary. Mirrors PDFBox
    ``PDFontSetting``.

    A font setting is a 2-element ``COSArray`` of the form
    ``[font, size]``: the first slot is a font dictionary (typically an
    indirect reference) and the second slot is a numeric point size.
    """

    def __init__(self, font_setting: COSBase | None = None) -> None:
        if font_setting is None:
            arr = COSArray()
            arr.add(COSNull.NULL)
            arr.add(COSFloat(0.0))
            self._array: COSArray = arr
            return
        if isinstance(font_setting, COSArray):
            self._array = font_setting
            return
        raise TypeError(
            f"PDFontSetting expects COSArray or None, "
            f"got {type(font_setting).__name__}"
        )

    # ---------- COS surface ----------

    def get_cos_object(self) -> COSArray:
        return self._array

    # ---------- font (slot 0) ----------

    def get_font(self) -> PDFont | None:
        from pypdfbox.pdmodel.font.pd_font_factory import PDFontFactory

        if self._array.size() < 1:
            return None
        entry = self._array.get_object(0)
        if isinstance(entry, COSDictionary):
            return PDFontFactory.create_font(entry)
        return None

    def set_font(self, font: PDFont | COSBase | None) -> None:
        self._array.grow_to_size(2)
        if font is None:
            self._array.set(0, COSNull.NULL)
            return
        if isinstance(font, COSBase):
            self._array.set(0, font)
            return
        # Typed PDFont — written as its underlying COS object so the
        # array continues to round-trip through the writer.
        self._array.set(0, font.get_cos_object())

    # ---------- size (slot 1) ----------

    def get_font_size(self) -> float:
        if self._array.size() < 2:
            return 0.0
        entry = self._array.get_object(1)
        if isinstance(entry, COSNumber):
            return float(entry.value)
        return 0.0

    def set_font_size(self, size: float) -> None:
        self._array.grow_to_size(2)
        self._array.set(1, COSFloat(float(size)))


__all__ = ["PDFontSetting"]
