from __future__ import annotations

from pypdfbox.cos import COSArray, COSName

from .pd_color import PDColor
from .pd_color_space import PDColorSpace


class PDDeviceN(PDColorSpace):
    """A DeviceN color space. Mirrors PDFBox
    ``org.apache.pdfbox.pdmodel.graphics.color.PDDeviceN``.

    Array form: ``[/DeviceN <colorant names array> <alternate CS>
    <tint transform> <attributes dict>?]``.

    Lite surface: tint transform evaluation and attribute (process
    colorants, mixing hints) parsing land alongside the function and
    rendering modules.
    """

    NAME: str = "DeviceN"

    # Array index constants — match upstream private fields.
    _COLORANT_NAMES = 1
    _ALTERNATE_CS = 2
    _TINT_TRANSFORM = 3
    _DEVICEN_ATTRIBUTES = 4

    def __init__(self, array: COSArray | None = None) -> None:
        if array is None:
            array = COSArray()
            array.add(COSName.get_pdf_name(self.NAME))
            array.add(COSArray())  # empty colorant names
            array.add(COSName.get_pdf_name(""))  # alternate CS placeholder
            array.add(COSName.get_pdf_name(""))  # tint transform placeholder
        super().__init__(array)
        # Initial color: 1.0 per component (full tint of every colorant)
        # — upstream constructs this lazily once colorant names are set.
        n = self.get_number_of_components()
        self._initial_color = PDColor([1.0] * n, self)

    # ---------- abstract surface ----------

    def get_name(self) -> str:
        return self.NAME

    def get_number_of_components(self) -> int:
        return len(self.get_colorant_names())

    def get_initial_color(self) -> PDColor:
        # Refresh in case colorant names changed after construction.
        n = self.get_number_of_components()
        if len(self._initial_color.get_components()) != n:
            self._initial_color = PDColor([1.0] * n, self)
        return self._initial_color

    # ---------- DeviceN-specific ----------

    def get_colorant_names(self) -> list[str]:
        assert self._array is not None
        entry = self._array.get_object(self._COLORANT_NAMES)
        if not isinstance(entry, COSArray):
            return []
        out: list[str] = []
        for item in entry:
            if isinstance(item, COSName):
                out.append(item.get_name())
        return out

    def set_colorant_names(self, names: list[str]) -> None:
        assert self._array is not None
        self._array.set(self._COLORANT_NAMES, COSArray.of_cos_names(names))

    def get_alternate_color_space(self) -> PDColorSpace | None:
        assert self._array is not None
        entry = self._array.get_object(self._ALTERNATE_CS)
        if entry is None:
            return None
        return PDColorSpace.create(entry)

    def set_alternate_color_space(self, alternate: PDColorSpace) -> None:
        assert self._array is not None
        self._array.set(self._ALTERNATE_CS, alternate.get_cos_object())


__all__ = ["PDDeviceN"]
