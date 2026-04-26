from __future__ import annotations

from pypdfbox.cos import COSArray, COSBase, COSName

from .pd_color import PDColor
from .pd_color_space import PDColorSpace


class PDSeparation(PDColorSpace):
    """A Separation color space. Mirrors PDFBox
    ``org.apache.pdfbox.pdmodel.graphics.color.PDSeparation``.

    Array form: ``[/Separation <colorant name> <alternate CS> <tint
    transform>]``.

    Lite surface: tint transform evaluation lives in the function
    module; ``get_tint_transform`` returns the raw COS object.
    """

    NAME: str = "Separation"

    # Array index constants — match upstream private fields.
    _COLORANT_NAMES = 1
    _ALTERNATE_CS = 2
    _TINT_TRANSFORM = 3

    def __init__(self, array: COSArray | None = None) -> None:
        if array is None:
            array = COSArray()
            array.add(COSName.get_pdf_name(self.NAME))
            # Placeholders matching upstream PDSeparation() default ctor.
            array.add(COSName.get_pdf_name(""))
            array.add(COSName.get_pdf_name(""))
            array.add(COSName.get_pdf_name(""))
        super().__init__(array)
        # Initial color per upstream is a single component at 1.0 (full
        # tint).
        self._initial_color = PDColor([1.0], self)

    # ---------- abstract surface ----------

    def get_name(self) -> str:
        return self.NAME

    def get_number_of_components(self) -> int:
        return 1

    def get_initial_color(self) -> PDColor:
        return self._initial_color

    # ---------- separation-specific ----------

    def get_colorant_name(self) -> str | None:
        assert self._array is not None
        entry = self._array.get_object(self._COLORANT_NAMES)
        if isinstance(entry, COSName):
            return entry.get_name()
        return None

    def set_colorant_name(self, name: str) -> None:
        assert self._array is not None
        self._array.set(self._COLORANT_NAMES, COSName.get_pdf_name(name))

    def get_alternate_color_space(self) -> PDColorSpace | None:
        assert self._array is not None
        entry = self._array.get_object(self._ALTERNATE_CS)
        if entry is None:
            return None
        return PDColorSpace.create(entry)

    def set_alternate_color_space(self, alternate: PDColorSpace) -> None:
        assert self._array is not None
        self._array.set(self._ALTERNATE_CS, alternate.get_cos_object())

    def get_tint_transform(self) -> COSBase | None:
        """Return the raw tint transform COS object (function dictionary
        or stream). Function evaluation lives in the function module."""
        assert self._array is not None
        return self._array.get_object(self._TINT_TRANSFORM)

    def set_tint_transform(self, transform: COSBase) -> None:
        assert self._array is not None
        self._array.set(self._TINT_TRANSFORM, transform)


__all__ = ["PDSeparation"]
