from __future__ import annotations

from pypdfbox.cos import (
    COSArray,
    COSInteger,
    COSName,
    COSNull,
    COSStream,
    COSString,
)

from .pd_color import PDColor
from .pd_color_space import PDColorSpace
from .pd_device_rgb import PDDeviceRGB


class PDIndexed(PDColorSpace):
    """An Indexed color space. Mirrors PDFBox
    ``org.apache.pdfbox.pdmodel.graphics.color.PDIndexed``.

    Array form: ``[/Indexed <base CS> <hival> <lookup>]``.

    Lite surface: ``to_rgb`` color-table conversion is deferred until
    rendering. PDFBox 4.0 removes the no-arg constructor and several
    helper methods (CLAUDE.md §PDFBox 4.0); we follow that decision.
    """

    NAME: str = "Indexed"

    def __init__(self, array: COSArray | None = None) -> None:
        if array is None:
            array = COSArray()
            array.add(COSName.get_pdf_name(self.NAME))
            array.add(PDDeviceRGB.INSTANCE.get_cos_object())
            array.add(COSInteger.get(255))
            array.add(COSNull.NULL)
        super().__init__(array)
        self._initial_color = PDColor([0.0], self)

    # ---------- abstract surface ----------

    def get_name(self) -> str:
        return self.NAME

    def get_number_of_components(self) -> int:
        return 1

    def get_initial_color(self) -> PDColor:
        return self._initial_color

    # ---------- indexed-specific ----------

    def get_base_color_space(self) -> PDColorSpace | None:
        assert self._array is not None
        base = self._array.get_object(1)
        if base is None:
            return None
        return PDColorSpace.create(base)

    def set_base_color_space(self, base: PDColorSpace) -> None:
        assert self._array is not None
        self._array.set(1, base.get_cos_object())

    def get_hival(self) -> int:
        assert self._array is not None
        return self._array.get_int(2, 0)

    def set_hival(self, hival: int) -> None:
        assert self._array is not None
        self._array.set(2, COSInteger.get(hival))

    def get_lookup_data(self) -> bytes | None:
        assert self._array is not None
        entry = self._array.get_object(3)
        if isinstance(entry, COSString):
            return entry.get_bytes()
        if isinstance(entry, COSStream):
            return entry.get_raw_data()
        return None

    def set_lookup_data(self, data: bytes | None) -> None:
        assert self._array is not None
        if data is None:
            self._array.set(3, COSNull.NULL)
        else:
            self._array.set(3, COSString(data))


__all__ = ["PDIndexed"]
