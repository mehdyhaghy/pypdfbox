from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName

from .pd_color import PDColor
from .pd_color_space import PDColorSpace


_WHITE_POINT: COSName = COSName.get_pdf_name("WhitePoint")
_BLACK_POINT: COSName = COSName.get_pdf_name("BlackPoint")
_RANGE: COSName = COSName.get_pdf_name("Range")


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


class PDLab(PDColorSpace):
    """A Lab color space. Mirrors PDFBox
    ``org.apache.pdfbox.pdmodel.graphics.color.PDLab``.

    Array form: ``[/Lab <dictionary>]`` with dictionary keys
    ``/WhitePoint`` (required), ``/BlackPoint`` (default ``[0 0 0]``),
    and ``/Range`` (default ``[-100 100 -100 100]``) holding the a*/b*
    component bounds.
    """

    NAME: str = "Lab"

    def __init__(self, array: COSArray | None = None) -> None:
        if array is None:
            array = COSArray()
            array.add(COSName.get_pdf_name(self.NAME))
            array.add(COSDictionary())
        super().__init__(array)
        # Initial color per upstream: L=0, a=max(0, aMin), b=max(0, bMin)
        rng = self.get_range()
        a_min = rng[0] if len(rng) >= 1 else -100.0
        b_min = rng[2] if len(rng) >= 3 else -100.0
        self._initial_color = PDColor(
            [0.0, max(0.0, a_min), max(0.0, b_min)],
            self,
        )

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
            raise TypeError(f"Lab array index 1 is not a dictionary: {entry!r}")
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

    def get_range(self) -> list[float]:
        out = _read_float_array(
            self._dict(), _RANGE, [-100.0, 100.0, -100.0, 100.0]
        )
        return out[:4] if len(out) >= 4 else out

    def set_range(self, rng: list[float]) -> None:
        self._dict().set_item(_RANGE, COSArray.of_cos_floats(rng))

    # ---------- decode ----------

    def get_default_decode(self, bits_per_component: int) -> list[float]:
        """Default Lab decode per PDF 32000-1 §8.9.5.1 Table 90:
        ``[0, 100, a_min, a_max, b_min, b_max]``. ``L*`` always spans
        ``[0, 100]``; the ``a*``/``b*`` bounds come from ``/Range``
        (default ``[-100, 100, -100, 100]``).
        """
        rng = self.get_range()
        if len(rng) >= 4:
            return [0.0, 100.0, float(rng[0]), float(rng[1]), float(rng[2]), float(rng[3])]
        return [0.0, 100.0, -100.0, 100.0, -100.0, 100.0]


__all__ = ["PDLab"]
