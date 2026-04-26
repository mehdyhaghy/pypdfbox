from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName

from .pd_color import PDColor
from .pd_color_space import PDColorSpace


_WHITE_POINT: COSName = COSName.get_pdf_name("WhitePoint")
_BLACK_POINT: COSName = COSName.get_pdf_name("BlackPoint")
_GAMMA: COSName = COSName.get_pdf_name("Gamma")


def _read_tristimulus(
    dictionary: COSDictionary,
    key: COSName,
    default: list[float],
) -> list[float]:
    entry = dictionary.get_dictionary_object(key)
    if isinstance(entry, COSArray):
        out = entry.to_float_array()
        if len(out) >= 3:
            return out[:3]
    return list(default)


class PDCalGray(PDColorSpace):
    """A CalGray color space. Mirrors PDFBox
    ``org.apache.pdfbox.pdmodel.graphics.color.PDCalGray``.

    Array form: ``[/CalGray <dictionary>]`` with dictionary keys
    ``/WhitePoint`` (required), ``/BlackPoint`` (default ``[0 0 0]``)
    and ``/Gamma`` (default ``1``).
    """

    NAME: str = "CalGray"

    def __init__(self, array: COSArray | None = None) -> None:
        if array is None:
            array = COSArray()
            array.add(COSName.get_pdf_name(self.NAME))
            array.add(COSDictionary())
        super().__init__(array)
        self._initial_color = PDColor([0.0], self)

    # ---------- abstract surface ----------

    def get_name(self) -> str:
        return self.NAME

    def get_number_of_components(self) -> int:
        return 1

    def get_initial_color(self) -> PDColor:
        return self._initial_color

    # ---------- CIE dictionary access ----------

    def _dict(self) -> COSDictionary:
        assert self._array is not None
        entry = self._array.get_object(1)
        if not isinstance(entry, COSDictionary):
            raise TypeError(f"CalGray array index 1 is not a dictionary: {entry!r}")
        return entry

    def get_white_point(self) -> list[float]:
        return _read_tristimulus(self._dict(), _WHITE_POINT, [1.0, 1.0, 1.0])

    def set_white_point(self, white: list[float]) -> None:
        self._dict().set_item(_WHITE_POINT, COSArray.of_cos_floats(white))

    def get_black_point(self) -> list[float]:
        return _read_tristimulus(self._dict(), _BLACK_POINT, [0.0, 0.0, 0.0])

    def set_black_point(self, black: list[float]) -> None:
        self._dict().set_item(_BLACK_POINT, COSArray.of_cos_floats(black))

    def get_gamma(self) -> float:
        return self._dict().get_float(_GAMMA, 1.0)

    def set_gamma(self, gamma: float) -> None:
        self._dict().set_item(_GAMMA, COSFloat(gamma))


__all__ = ["PDCalGray"]
