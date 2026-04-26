from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName

from .pd_color import PDColor
from .pd_color_space import PDColorSpace


_WHITE_POINT: COSName = COSName.get_pdf_name("WhitePoint")
_BLACK_POINT: COSName = COSName.get_pdf_name("BlackPoint")
_GAMMA: COSName = COSName.get_pdf_name("Gamma")
_MATRIX: COSName = COSName.get_pdf_name("Matrix")


def _read_float_array(
    dictionary: COSDictionary,
    key: COSName,
    default: list[float],
) -> list[float]:
    entry = dictionary.get_dictionary_object(key)
    if isinstance(entry, COSArray):
        out = entry.to_float_array()
        if out:
            return out
    return list(default)


class PDCalRGB(PDColorSpace):
    """A CalRGB color space. Mirrors PDFBox
    ``org.apache.pdfbox.pdmodel.graphics.color.PDCalRGB``.

    Array form: ``[/CalRGB <dictionary>]`` with dictionary keys
    ``/WhitePoint`` (required), ``/BlackPoint`` (default ``[0 0 0]``),
    ``/Gamma`` (default ``[1 1 1]``) and ``/Matrix`` (default identity
    ``[1 0 0 0 1 0 0 0 1]``).
    """

    NAME: str = "CalRGB"

    def __init__(self, array: COSArray | None = None) -> None:
        if array is None:
            array = COSArray()
            array.add(COSName.get_pdf_name(self.NAME))
            array.add(COSDictionary())
        super().__init__(array)
        self._initial_color = PDColor([0.0, 0.0, 0.0], self)

    # ---------- abstract surface ----------

    def get_name(self) -> str:
        return self.NAME

    def get_number_of_components(self) -> int:
        return 3

    def get_initial_color(self) -> PDColor:
        return self._initial_color

    # ---------- CIE dictionary access ----------

    def _dict(self) -> COSDictionary:
        assert self._array is not None
        entry = self._array.get_object(1)
        if not isinstance(entry, COSDictionary):
            raise TypeError(f"CalRGB array index 1 is not a dictionary: {entry!r}")
        return entry

    def get_white_point(self) -> list[float]:
        out = _read_float_array(self._dict(), _WHITE_POINT, [1.0, 1.0, 1.0])
        return out[:3] if len(out) >= 3 else out

    def set_white_point(self, white: list[float]) -> None:
        self._dict().set_item(_WHITE_POINT, COSArray.of_cos_floats(white))

    def get_black_point(self) -> list[float]:
        out = _read_float_array(self._dict(), _BLACK_POINT, [0.0, 0.0, 0.0])
        return out[:3] if len(out) >= 3 else out

    def set_black_point(self, black: list[float]) -> None:
        self._dict().set_item(_BLACK_POINT, COSArray.of_cos_floats(black))

    def get_gamma(self) -> list[float]:
        return _read_float_array(self._dict(), _GAMMA, [1.0, 1.0, 1.0])

    def set_gamma(self, gamma: list[float]) -> None:
        self._dict().set_item(_GAMMA, COSArray.of_cos_floats(gamma))

    def get_matrix(self) -> list[float] | None:
        entry = self._dict().get_dictionary_object(_MATRIX)
        if isinstance(entry, COSArray):
            return entry.to_float_array()
        return None

    def set_matrix(self, matrix: list[float] | None) -> None:
        d = self._dict()
        if matrix is None:
            d.remove_item(_MATRIX)
        else:
            d.set_item(_MATRIX, COSArray.of_cos_floats(matrix))


__all__ = ["PDCalRGB"]
